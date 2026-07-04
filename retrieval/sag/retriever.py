"""SAG 检索路径: SQL 检索 -> 查询时动态超图 -> 关联扩展 -> 增强上下文."""
import json
import yaml
from retrieval.base import BaseRetriever
from retrieval.text_to_sql.sql_generator import SQLGenerator
from retrieval.sag.sql_retrieval import (
    build_hypergraph_from_rows, expand_entities, _is_entity_column, _classify_entity
)
from retrieval.text_to_sql.executor import SQLExecutor

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

CFG = SETTINGS["sag"]


class SAGRetriever(BaseRetriever):
    path_name = "sag"

    def __init__(self):
        self.gen = SQLGenerator()
        self.executor = SQLExecutor()
        self.expand_hops = CFG["expand_hops"]
        self.max_expand = CFG["max_expand_entities"]

    def retrieve(self, query: str, user: dict = None) -> dict:
        # 1. SQL 检索基础结果
        out = self.gen.generate_and_execute(query, user=user)
        if out["error"]:
            return {"context": f"(SAG 基础 SQL 失败: {out['error']})",
                    "raw": None, "meta": {"path": self.path_name}}
        res = out["result"]
        columns, rows = res["columns"], res["rows"]
        if not rows:
            return {"context": "(SAG: SQL 无结果, 无法构建超图)",
                    "raw": None, "meta": {"path": self.path_name}}

        # 2. 查询时动态构建超图
        hg = build_hypergraph_from_rows(columns, rows)

        # 3. 提取种子实体 (SQL 结果中的所有实体值)
        seeds = set()
        entity_cols = [(i, c) for i, c in enumerate(columns) if _is_entity_column(c)]
        for row in rows:
            for i, c in entity_cols:
                val = row[i] if i < len(row) else None
                if val is not None and val != "":
                    seeds.add((_classify_entity(c), str(val)))

        if not seeds:
            # 没有实体列, 退化为纯 SQL 结果
            return {
                "context": f"SQL: {out['sql']}\n结果: {json.dumps(rows[:50], ensure_ascii=False)}",
                "raw": {"sql": out["sql"], "rows": rows, "hypergraph": None},
                "meta": {"path": self.path_name, "note": "无实体列, 未构建超图"},
            }

        # 4. 超图多跳扩展
        expanded, all_entities = expand_entities(hg, seeds, self.expand_hops, self.max_expand)

        # 5. 为扩展实体拉回额外数据 (用每个扩展实体值做二次 SQL)
        expansion_context = []
        for etype, value in list(expanded)[:self.max_expand]:
            # 简单做: 用该值在所有表查相关行 (演示版, 生产可更智能)
            extra = self._fetch_related_rows(etype, value, user=user)
            if extra:
                expansion_context.append(f"[关联 {etype}={value}]: {extra}")

        # 6. 拼装增强上下文
        base_ctx = f"SQL: {out['sql']}\n基础结果({len(rows)}行): {json.dumps(rows[:30], ensure_ascii=False)}"
        hg_stats = hg.stats()
        expand_ctx = "\n".join(expansion_context) if expansion_context else "(无扩展实体)"
        context = f"""{base_ctx}

--- 超图扩展 ---
种子实体: {list(seeds)[:10]}
超图统计: {hg_stats}
扩展实体({len(expanded)}个): {list(expanded)[:10]}
扩展上下文:
{expand_ctx}"""
        return {
            "context": context,
            "raw": {
                "sql": out["sql"],
                "base_rows": rows,
                "columns": columns,
                "hypergraph_stats": hg_stats,
                "seeds": list(seeds),
                "expanded": list(expanded),
            },
            "meta": {
                "path": self.path_name,
                "base_row_count": len(rows),
                "expanded_entity_count": len(expanded),
                "hypergraph": hg_stats,
            },
        }

    def _fetch_related_rows(self, etype: str, value: str, user: dict = None) -> str:
        """为扩展实体查相关行. 演示版: 在 sample db 的相关列做精确匹配."""
        # 简单策略: 拼 SELECT * FROM <可能表> WHERE <可能列> = value
        # 生产版应该用 schema_kb 找到正确表和列
        col_candidates = {
            "customer": ["customer_id", "customer_name"],
            "product": ["product_id", "product_name"],
            "region": ["region"],
            "department": ["dept_id"],
            "employee": ["employee_id"],
        }
        cols = col_candidates.get(etype, [f"{etype}_id"])
        results = []
        for col in cols:
            # 在几个常见表里找
            for tbl in ["orders", "customers", "products", "employees", "salaries"]:
                sql = f"SELECT * FROM {tbl} WHERE {col} = '{value}' LIMIT 5"
                r = self.executor.execute(sql, user=user)
                if r["rows"]:
                    results.append(f"{tbl}: {r['rows']}")
        return " | ".join(results) if results else ""
