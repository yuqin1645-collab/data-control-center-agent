"""执行编排层: 任务分解 -> 子任务执行 -> 结果聚合.

- 熔断器: 连续失败 N 次打开熔断, 直接降级
- 指数退避重试: 2^n + jitter
- 多路结果聚合
"""
import time
import random
from typing import List, Dict
import yaml

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)


class CircuitBreaker:
    """简单熔断器."""

    def __init__(self, threshold=5, cooldown=30):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.opened_at = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.time() - self.opened_at > self.cooldown:
            # 半开: 放行试探
            self.opened_at = None
            self.failures = 0
            return True
        return False

    def record_success(self):
        self.failures = 0
        self.opened_at = None

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.time()


def with_retry(fn, max_retries=3, backoff_base=2):
    """指数退避重试."""
    last_err = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < max_retries - 1:
                wait = backoff_base ** (attempt + 1) + random.uniform(0, backoff_base * 0.3)
                time.sleep(wait)
    raise last_err


class Orchestrator:
    """编排器: 接收路由结果, 调用对应 retriever, 聚合结果."""

    _instance = None

    def __init__(self):
        self.breakers = {}  # path -> CircuitBreaker
        cfg = SETTINGS["orchestrator"]
        self.max_retries = cfg["max_retries"]
        self.backoff_base = cfg["backoff_base"]
        self.threshold = cfg["circuit_failure_threshold"]
        self.cooldown = cfg["circuit_cooldown"]
        self._retrievers = {}

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_retriever(self, path: str):
        """延迟加载 retriever, 避免启动时全加载."""
        if path in self._retrievers:
            return self._retrievers[path]
        r = self._instantiate(path)
        self._retrievers[path] = r
        return r

    def _instantiate(self, path: str):
        if path == "text_to_sql":
            from retrieval.text_to_sql.retriever import TextToSQLRetriever
            return TextToSQLRetriever()
        if path == "traditional_rag":
            from retrieval.traditional_rag.retriever import TraditionalRAGRetriever
            return TraditionalRAGRetriever()
        if path == "graph_rag":
            from retrieval.graph_rag.retriever import GraphRAGRetriever
            return GraphRAGRetriever()
        if path == "wiki_rag":
            from retrieval.wiki_rag.retriever import WikiRAGRetriever
            return WikiRAGRetriever()
        if path == "sag":
            from retrieval.sag.retriever import SAGRetriever
            return SAGRetriever()
        raise ValueError(f"未知检索路径: {path}")

    def _breaker(self, path: str) -> CircuitBreaker:
        if path not in self.breakers:
            self.breakers[path] = CircuitBreaker(self.threshold, self.cooldown)
        return self.breakers[path]

    def execute_path(self, path: str, query: str) -> dict:
        """执行单条路径. 返回 {"path":..., "query":..., "result":..., "error":...}."""
        breaker = self._breaker(path)
        if not breaker.allow():
            return {"path": path, "query": query, "result": None, "error": "circuit_open"}
        try:
            retriever = self._get_retriever(path)

            def _do():
                return retriever.retrieve(query)

            result = with_retry(_do, self.max_retries, self.backoff_base)
            breaker.record_success()
            return {"path": path, "query": query, "result": result, "error": None}
        except Exception as e:
            breaker.record_failure()
            return {"path": path, "query": query, "result": None, "error": str(e)}

    def run(self, route_result: dict, query: str) -> List[dict]:
        """根据路由结果执行. 返回各路径结果列表."""
        label = route_result["label"]
        if label == "hybrid":
            subqueries = route_result.get("subqueries", [])
            if not subqueries:
                # 路由没拆出来, 降级全跑
                subqueries = [{"q": query, "path": p} for p in ["text_to_sql", "traditional_rag"]]
            results = [self.execute_path(sq["path"], sq["q"]) for sq in subqueries]
            return results
        return [self.execute_path(label, query)]
