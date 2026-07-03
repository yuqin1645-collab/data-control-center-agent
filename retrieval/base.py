"""Retriever 基类: 所有检索路径实现这个接口."""
from abc import ABC, abstractmethod


class BaseRetriever(ABC):
    path_name: str = "base"

    @abstractmethod
    def retrieve(self, query: str) -> dict:
        """返回 {"context": str, "raw": ..., "meta": {...}}.

        context: 拼装好给 LLM 的文本上下文
        raw: 原始检索结果 (供前端展示)
        meta: 元信息 (来源、命中数等)
        """
        ...
