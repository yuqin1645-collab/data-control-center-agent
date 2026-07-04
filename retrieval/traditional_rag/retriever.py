"""传统 RAG 检索路径: 向量检索 + 简单 rerank."""
import os
import yaml
from typing import List
from retrieval.base import BaseRetriever
from retrieval.traditional_rag.indexer import get_embedder, get_chroma_collection

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

CFG = SETTINGS["traditional_rag"]


def _simple_rerank(query: str, chunks: List[str], top_k: int) -> List[str]:
    """简单 rerank: 用 embedding 相似度重排 (演示版, 生产可换 bge-reranker)."""
    if not chunks:
        return []
    embedder = get_embedder()
    q_emb = embedder.encode_one(query)
    c_embs = embedder.encode(chunks)
    scores = (c_embs @ q_emb)
    order = scores.argsort()[::-1][:top_k]
    return [chunks[i] for i in order]


class TraditionalRAGRetriever(BaseRetriever):
    path_name = "traditional_rag"

    def __init__(self):
        self.embedder = get_embedder()
        self.coll = get_chroma_collection("company_docs")
        self.retrieve_top_k = CFG["retrieve_top_k"]
        self.rerank_top_k = CFG["rerank_top_k"]

    def retrieve(self, query: str, user: dict = None) -> dict:
        q_emb = self.embedder.encode_one(query).tolist()
        # 粗排: chroma 向量检索
        try:
            res = self.coll.query(query_embeddings=[q_emb], n_results=self.retrieve_top_k)
        except Exception as e:
            return {"context": f"(文档检索失败: {e})", "raw": None, "meta": {"path": self.path_name}}

        if not res["ids"][0]:
            return {"context": "(文档库为空或无匹配, 请先运行 scripts/index_documents.py)",
                    "raw": None, "meta": {"path": self.path_name}}

        chunks = res["documents"][0]
        sources = [m.get("source", "?") for m in res["metadatas"][0]]
        # 精排
        reranked = _simple_rerank(query, chunks, self.rerank_top_k)
        context = "\n---\n".join(reranked)
        return {
            "context": context,
            "raw": {"chunks": reranked, "sources": sources[:len(reranked)]},
            "meta": {"path": self.path_name, "chunk_count": len(reranked)},
        }
