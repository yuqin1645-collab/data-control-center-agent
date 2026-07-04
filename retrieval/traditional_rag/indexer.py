"""共享 embedder + 文档索引.

get_embedder() 是全局单例, core/cache 和各 retriever 都用这个.
优先用 sentence-transformers (bge-m3), 不可用时降级到 hash embedder.
"""
import os
import hashlib
from typing import List
import numpy as np

_EMBEDDER = None

# 降级 embedder 的向量维度 (和 bge-m3 一致, 方便切换)
FALLBACK_DIM = 768


class HashEmbedder:
    """轻量级 hash embedder: 字符 n-gram hashing → 固定维度向量.

    不需要 torch/sentence-transformers, 适合 demo 和 CI.
    效果不如 bge-m3 但 cosine 相似度可用.
    """

    def __init__(self, dim: int = FALLBACK_DIM):
        self.dim = dim

    def _text_to_ngrams(self, text: str) -> list:
        """提取字符 2-gram + 词级特征."""
        text = text.lower().strip()
        # 字符 2-gram (适合中文)
        chars = list(text.replace(" ", ""))
        char_grams = ["".join(chars[i:i + 2]) for i in range(len(chars) - 1)]
        # 词级 (按空格/标点分)
        words = []
        for sep in [" ", "\n", "\t", "，", "。", "、", "；", "？", "！"]:
            text = text.replace(sep, " ")
        words = [w for w in text.split() if w]
        return char_grams + words

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        embs = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            grams = self._text_to_ngrams(text)
            for g in grams:
                # hash 到 [0, dim)
                h = int(hashlib.md5(g.encode()).hexdigest(), 16) % self.dim
                embs[i, h] += 1.0
        # L2 normalize
        if normalize:
            norms = np.linalg.norm(embs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embs = embs / norms
        return embs

    def encode_one(self, text: str, normalize: bool = True) -> np.ndarray:
        return self.encode([text], normalize=normalize)[0]


class Embedder:
    """sentence-transformers 封装, 降级到 HashEmbedder."""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self._model = None
        self._fallback = None
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except Exception:
            print(f"[Embedder] sentence-transformers 不可用, 降级到 HashEmbedder (dim={FALLBACK_DIM})")
            self._fallback = HashEmbedder(FALLBACK_DIM)

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        if self._model:
            embs = self._model.encode(texts, normalize_embeddings=normalize, show_progress_bar=False)
            return np.asarray(embs, dtype=np.float32)
        return self._fallback.encode(texts, normalize=normalize)

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
