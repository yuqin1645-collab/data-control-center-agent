"""FastAPI 后端: 数据中控 Agent API 服务.

启动: uvicorn api.main:app --reload --port 8000
"""
import os
import sys
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="数据中控 Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def preload_retrievers():
    """启动时预加载所有 retriever + 嵌入模型, 避免首次查询卡 25s."""
    print("[Startup] 预加载 retriever 开始...")
    t0 = time.time()
    from core.orchestrator import Orchestrator
    orch = Orchestrator.get()
    for path in ["text_to_sql", "traditional_rag", "graph_rag", "wiki_rag", "sag"]:
        try:
            t = time.time()
            orch._get_retriever(path)
            print(f"[Startup]   {path} 加载完成, 耗时 {round(time.time()-t,2)}s")
        except Exception as e:
            print(f"[Startup]   {path} 加载失败: {e}")
    print(f"[Startup] 预加载完成, 总耗时 {round(time.time()-t0,2)}s")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "data-control-center-agent"}


from api.routes import auth, query, system, conversations  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(query.router, prefix="/api/query", tags=["查询"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["会话"])
app.include_router(system.router, prefix="/api", tags=["系统"])
