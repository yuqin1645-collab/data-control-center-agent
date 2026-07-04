"""Text-to-SQL 检索路径: 对外 BaseRetriever 接口."""
from retrieval.base import BaseRetriever
from retrieval.text_to_sql.sql_generator import SQLGenerator


class TextToSQLRetriever(BaseRetriever):
    path_name = "text_to_sql"

    def __init__(self):
        self.gen = SQLGenerator()

    def retrieve(self, query: str, user: dict = None) -> dict:
        out = self.gen.generate_and_execute(query, user=user)
        if out["error"]:
            return {
                "context": f"(SQL 生成失败: {out['error']})",
                "raw": out,
                "meta": {"path": self.path_name, "tables": out.get("tables", [])},
            }
        # 拼装上下文
        res = out["result"]
        rows = res["rows"]
        cols = res["columns"]
        # 限制上下文长度
        import json
        preview = rows[:50]
        context = f"SQL: {out['sql']}\n命中表: {out.get('tables', [])}\n列: {cols}\n行数: {len(rows)}\n数据(前50行): {json.dumps(preview, ensure_ascii=False)}"
        return {
            "context": context,
            "raw": {
                "sql": out["sql"],
                "columns": cols,
                "rows": rows,
                "row_count": len(rows),
                "attempts": out.get("attempts"),
            },
            "meta": {
                "path": self.path_name,
                "tables": out.get("tables", []),
            },
        }
