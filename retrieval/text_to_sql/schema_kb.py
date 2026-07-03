"""Schema 知识库: 提取表结构 + 语义描述 + embedding 入 Chroma.

查询时检索 top-k 相关表 schema, 而不是把全库 schema 塞给 LLM.
"""
import os
import sqlite3
import json
from typing import List, Dict
import yaml

from retrieval.traditional_rag.indexer import get_embedder, get_chroma_collection

with open("config/data_sources.yaml", "r", encoding="utf-8") as f:
    SOURCES_CFG = yaml.safe_load(f)

SCHEMA_COLLECTION = "schema_kb"


def _get_sqlite_tables(db_path: str) -> List[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    return tables


def _get_table_schema(db_path: str, table: str) -> Dict:
    """返回 {table, columns: [{name, type, notnull, pk, default}], sample_rows}."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [
        {"name": r[1], "type": r[2], "notnull": r[3], "default": r[4], "pk": bool(r[5])}
        for r in cur.fetchall()
    ]
    # 取 3 行示例
    try:
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        rows = [list(r) for r in cur.fetchall()]
    except Exception:
        rows = []
    conn.close()
    return {"table": table, "columns": cols, "sample_rows": rows}


def _make_schema_text(table_info: Dict, source_name: str, description: str) -> str:
    """拼成可 embedding 也可喂 LLM 的文本."""
    cols = ", ".join(f"{c['name']}({c['type']})" for c in table_info["columns"])
    sample = ""
    if table_info["sample_rows"]:
        sample = "示例: " + str(table_info["sample_rows"][:2])
    return f"数据源: {source_name} | 描述: {description} | 表: {table_info['table']} | 字段: {cols} | {sample}"


def build_schema_kb():
    """扫描所有 sqlite 数据源, 构建或重建 schema 知识库."""
    embedder = get_embedder()
    coll = get_chroma_collection(SCHEMA_COLLECTION)
    # 重建: 先清空
    try:
        coll.delete(where={"source_type": "sqlite"})
    except Exception:
        pass

    total = 0
    for src in SOURCES_CFG["sources"]:
        if src["type"] != "sqlite":
            continue
        db_path = src["config"]["db_path"]
        if not os.path.exists(db_path):
            continue
        tables = src.get("tables") or _get_sqlite_tables(db_path)
        for t in tables:
            info = _get_table_schema(db_path, t)
            text = _make_schema_text(info, src["name"], src["description"])
            emb = embedder.encode_one(text).tolist()
            coll.upsert(
                ids=[f"{src['name']}__{t}"],
                embeddings=[emb],
                documents=[text],
                metadatas=[{
                    "source": src["name"],
                    "table": t,
                    "source_type": "sqlite",
                    "schema_json": json.dumps(info, ensure_ascii=False),
                }],
            )
            total += 1
    return total


class SchemaKB:
    """Schema 检索器."""

    _instance = None

    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.embedder = get_embedder()
        self.coll = get_chroma_collection(SCHEMA_COLLECTION)

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def retrieve(self, query: str) -> List[Dict]:
        """检索与 query 最相关的 top-k 表 schema."""
        q_emb = self.embedder.encode_one(query).tolist()
        res = self.coll.query(query_embeddings=[q_emb], n_results=self.top_k)
        results = []
        for i in range(len(res["ids"][0])):
            meta = res["metadatas"][0][i]
            doc = res["documents"][0][i]
            try:
                info = json.loads(meta["schema_json"])
            except Exception:
                info = None
            results.append({
                "source": meta["source"],
                "table": meta["table"],
                "schema": info,
                "description": doc,
                "distance": res["distances"][0][i] if "distances" in res else None,
            })
        return results


if __name__ == "__main__":
    n = build_schema_kb()
    print(f"已索引 {n} 张表 schema")
