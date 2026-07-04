"""缓存层: Redis 结果缓存 + 语义去重.

缓存按 (scope, query 语义) 二维寻址:
  - scope = f"{role}:{dept_id}", 由用户权限决定 (admin/manager/analyst × 部门)
  - 相同 scope 内, query embedding 余弦 >= 0.92 视为同一问题, 命中缓存
  - 不同 scope (不同权限) 互相隔离, 避免经理的缓存答案泄漏给分析师

agent.ask() 入口的缓存命中/写入都必须传 user, 否则会跨权限命中或污染缓存.
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

# 未传 user 时 (CLI 测试等) 的兜底 scope
DEFAULT_SCOPE = "anon:anon"


class EmbeddingCache:
    _instance = None

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "")
        self._mem = {}
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
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _scope(user: Optional[dict]) -> str:
        """从 user dict 派生权限 scope. 同一 scope 的用户共享缓存."""
        if not user:
            return DEFAULT_SCOPE
        role = user.get("role") or "anon"
        dept = user.get("dept_id") or "anon"
        return f"{role}:{dept}"

    def _embed(self, text: str) -> np.ndarray:
        from retrieval.traditional_rag.indexer import get_embedder
        emb = get_embedder().encode([text], normalize=True)[0]
        return np.asarray(emb, dtype=np.float32)

    def _cosine(self, a, b) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    def get(self, query: str, user: Optional[dict] = None):
        """语义查找缓存. 仅在同一 scope 内匹配, 命中返回 (result, True)."""
        scope = self._scope(user)
        q_emb = self._embed(query)
        if self._r is None:
            now = time.time()
            prefix = f"{scope}|"
            for k, (emb, val, ts) in self._mem.items():
                if not k.startswith(prefix):
                    continue
                if now - ts > self.ttl:
                    continue
                # emb 可能是 bytes (旧格式) 或 ndarray (新格式)
                if isinstance(emb, bytes):
                    emb = np.frombuffer(emb, dtype=np.float32)
                if self._cosine(q_emb, emb) >= self.threshold:
                    return val, True
            return None, False
        now = time.time()
        # Redis key 格式: dcca:q:{scope}:{md5}
        for k in self._r.scan_iter(match=f"dcca:q:{scope}:*"):
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

    def set(self, query: str, result, user: Optional[dict] = None):
        """写入缓存, key 同时编码 scope 和 query 文本."""
        scope = self._scope(user)
        q_emb = self._embed(query)
        ts = time.time()
        md5 = hashlib.md5(query.encode()).hexdigest()
        if self._r is None:
            key = f"{scope}|{md5}"
            # 直接存 ndarray, 避免 bytes 转换问题
            self._mem[key] = (q_emb, json.dumps(result, ensure_ascii=False), ts)
            if len(self._mem) > 500:
                oldest = min(self._mem, key=lambda k: self._mem[k][2])
                del self._mem[oldest]
            return
        key = f"dcca:q:{scope}:{md5}"
        payload = json.dumps([q_emb.tobytes().hex(), json.dumps(result, ensure_ascii=False), ts])
        self._r.set(key, payload)
