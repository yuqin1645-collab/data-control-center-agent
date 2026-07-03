"""共享 embedder + 文档索引.

get_embedder() 是全局单例, core/cache 和各 retriever 都用这个.
"""
import os
from typing import List
import numpy as np

_EMBEDDER = None


class Embedder:
    """sentence-transformers 封装."""

    def __init__(self, model_name: str = None):
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self._model = SentenceTransformer(self.model_name)

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        embs = self._model.encode(texts, normalize_embeddings=normalize, show_progress_bar=False)
        return np.asarray(embs, dtype=np.float32)

    def encode_one(self, text: str, normalize: bool = True) -> np.ndarray:
        return self.encode([text], normalize=normalize)[0]


def get_embedder() -> Embedder:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = Embedder()
    return _EMBEDDER


# ---- 文档索引 (传统 RAG 用) ----

def get_chroma_collection(collection_name: str = "company_docs"):
    """获取 chroma collection (单例)."""
    import chromadb
    client = chromadb.PersistentClient(path=os.path.join("data", "chroma"))
    return client.get_or_create_collection(name=collection_name)


def index_documents(doc_dir: str, collection_name: str = "company_docs", chunk_size: int = 400, overlap: int = 50):
    """读取 doc_dir 下所有 .txt/.md 文件, 分块索引到 chroma."""
    import glob
    coll = get_chroma_collection(collection_name)
    embedder = get_embedder()
    files = glob.glob(os.path.join(doc_dir, "**", "*.txt"), recursive=True) + \
            glob.glob(os.path.join(doc_dir, "**", "*.md"), recursive=True)
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = chunk_text(text, chunk_size, overlap)
        if not chunks:
            continue
        embs = embedder.encode(chunks).tolist()
        ids = [f"{os.path.basename(fpath)}_{i}" for i in range(len(chunks))]
        metas = [{"source": fpath, "chunk_idx": i} for i in range(len(chunks))]
        # upsert 避免重复
        coll.upsert(ids=ids, embeddings=embs, documents=chunks, metadatas=metas)
    return len(files)


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """按字数分块, 句号优先切."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            # 优先在句号/换行处切
            for sep in ["。", "！", "？", "\n\n", ". "]:
                pos = text.rfind(sep, start, end)
                if pos > start:
                    end = pos + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap if end - overlap > start else end
    return [c for c in chunks if c]
