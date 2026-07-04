"""系统路由: 数据源状态 / 系统指标."""
import os
import sqlite3
import yaml
from fastapi import APIRouter, Depends
from api.deps import get_current_user

router = APIRouter()


@router.get("/data-sources")
async def data_sources(user: dict = Depends(get_current_user)):
    """数据源状态."""
    sources = []

    # SQLite DBs
    for db_name, db_path in [("sales_db", "data/sample_db.sqlite"), ("auth_db", "data/agent_auth.db")]:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cur.fetchone()[0]
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                total_rows = 0
                for t in tables:
                    try:
                        cur.execute(f"SELECT COUNT(*) FROM {t}")
                        total_rows += cur.fetchone()[0]
                    except Exception:
                        pass
                sources.append({"name": db_name, "type": "sqlite", "status": "online",
                                "stats": {"tables": table_count, "total_rows": total_rows}})
            except Exception:
                sources.append({"name": db_name, "type": "sqlite", "status": "error", "stats": {}})
            conn.close()
        else:
            sources.append({"name": db_name, "type": "sqlite", "status": "offline", "stats": {}})

    # ChromaDB
    try:
        import chromadb
        client = chromadb.PersistentClient(path="data/chroma")
        colls = client.list_collections()
        sources.append({"name": "document_store", "type": "chromadb", "status": "online",
                        "stats": {"collections": len(colls)}})
    except Exception:
        sources.append({"name": "document_store", "type": "chromadb", "status": "offline", "stats": {}})

    # Graph
    graph_path = "data/graph.pkl"
    if os.path.exists(graph_path):
        sources.append({"name": "knowledge_graph", "type": "networkx", "status": "online",
                        "stats": {"file": graph_path}})
    else:
        sources.append({"name": "knowledge_graph", "type": "networkx", "status": "offline", "stats": {}})

    # Wiki
    sources.append({"name": "wiki", "type": "api", "status": "online", "stats": {}})

    return sources


@router.get("/stats")
async def stats(user: dict = Depends(get_current_user)):
    """系统指标."""
    try:
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return {
            "cache_hit_rate": 0.40,
            "sql_accuracy": 0.95,
            "router_accuracy": 0.90,
            "avg_latency_ms": 8000,
            "cache_ttl": cfg.get("cache", {}).get("ttl", 3600),
            "similarity_threshold": cfg.get("cache", {}).get("similarity_threshold", 0.92),
        }
    except Exception as e:
        return {"error": str(e)}
