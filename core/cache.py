"""缓存层: Redis 结果缓存 + 语义去重.

- 查询结果按 key embedding 缓存
- 新查询来了先 embedding 检索相似历史问题, 相似度 > 阈值直接返回缓存
- 无 Redis 时降级为内存缓存
"""
import os
import hashlib
import json
import time
from typing import Optional
import numpy as np

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class EmbeddingCache:
    """缓存问题 embedding 用于语义去重."""
    _instance = None

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "")
        self._mem = {}  # 降级内存缓存: {key: (embedding, value, ts)}
        self.threshold = 0.92
        self.ttl = 3600
        self._r = None
        if REDIS_AVAILABLE and self.redis_url:
            try:
                self._r = redis.from_url(self.redis_url, decode_responses=False)
                self._r.ping()
            except Exception:
                self._r = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _embed(self, text: str) -> np.ndarray:
        # 延迟导入避免循环依赖
        from retrieval.traditional_rag.indexer import get_embedder
        emb = get_embedder().encode([text], normalize=True)[0]
        return np.asarray(emb, dtype=np.float32)

    def _cosine(self, a, b) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    def get(self, query: str):
        """语义查找缓存. 命中返回 (result, True), 未命中返回 (None, False)."""
        q_emb = self._embed(query)
        # 内存模式遍历
        if self._r is None:
            now = time.time()
            for k, (emb, val, ts) in self._mem.items():
                if now - ts > self.ttl:
                    continue
                if self._cosine(q_emb, emb) >= self.threshold:
                    return val, True
            return None, False
        # redis 模式: 遍历 keys (量小可接受)
        now = time.time()
        for k in self._r.scan_iter(match="dcca:q:*"):
            data = self._r.get(k)
            if not data:
                continue
            try:
                payload = json.loads(data)
                hex_str, val_json, ts = payload
                if now - ts > self.ttl:
                    continue
                emb = np.frombuffer(bytes.fromhex(hex_str), dtype=np.float32)
                if self._cosine(q_emb, emb) >= self.threshold:
                    return json.loads(val_json), True
            except Exception:
                continue
        return None, False

    def set(self, query: str, result):
        q_emb = self._embed(query)
        ts = time.time()
        if self._r is None:
            key = hashlib.md5(query.encode()).hexdigest()
            self._mem[key] = (q_emb.tobytes(), json.dumps(result, ensure_ascii=False), ts)
            # 内存模式做简单 LRU
            if len(self._mem) > 500:
                oldest = min(self._mem, key=lambda k: self._mem[k][2])
                del self._mem[oldest]
            return
        key = f"dcca:q:{hashlib.md5(query.encode()).hexdigest()}"
        payload = json.dumps([q_emb.tobytes().hex(), json.dumps(result, ensure_ascii=False), ts])
        self._r.set(key, payload)
