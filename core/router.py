"""意图路由层: 数据中控的"大脑".

判断一个自然语言问题应该走哪条检索路径:
- text_to_sql: 结构化数据查询 (销售额、订单数、员工数)
- traditional_rag: 文档知识查询 (报销流程、规章制度)
- graph_rag: 关系推理 (A 和 B 的关系、多跳关联)
- wiki_rag: 外部通用知识 (公历节日、地理、历史)
- sag: SQL + 关联扩展 (查某客户买了什么 + 关联产品)
- hybrid: 混合查询, 多路编排
"""
import json
from typing import List
from core.llm import LLMClient

# few-shot 示例
ROUTER_FEW_SHOT = [
    {
        "q": "上个月华东区销售额是多少",
        "label": "text_to_sql",
        "reason": "查询结构化销售数据,需要 SQL 聚合",
    },
    {
        "q": "公司报销流程是什么",
        "label": "traditional_rag",
        "reason": "查询文档资料,需要向量检索",
    },
    {
        "q": "张三和李四之间有什么业务关联",
        "label": "graph_rag",
        "reason": "关系推理,需要图谱多跳查询",
    },
    {
        "q": "端午节是哪天,有什么习俗",
        "label": "wiki_rag",
        "reason": "外部通用知识,公司知识库没有",
    },
    {
        "q": "客户 C001 买了哪些产品,这些产品的同类产品还有谁在买",
        "label": "sag",
        "reason": "需要 SQL 检索 + 关联实体扩展",
    },
    {
        "q": "华东区退货率多少,退货流程是什么",
        "label": "hybrid",
        "reason": "前半结构化查询走 SQL,后半文档查询走 RAG",
    },
]


class IntentRouter:
    _instance = None

    def __init__(self):
        self.llm = LLMClient.get()

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def route(self, query: str, history: List[dict] = None) -> dict:
        """返回 {"label": ..., "reason": ..., "subqueries": [...]}.

        hybrid 时 subqueries 拆出子任务及各自路径.
        """
        examples = "\n".join(
            f'问题: {e["q"]}\n分类: {e["label"]}\n理由: {e["reason"]}'
            for e in ROUTER_FEW_SHOT
        )
        prompt = f"""你是数据中控 Agent 的意图路由器. 判断用户问题应该走哪条检索路径.

可选路径:
- text_to_sql: 结构化数据库查询 (数值、统计、聚合)
- traditional_rag: 公司文档资料问答 (流程、制度)
- graph_rag: 实体关系推理 (多跳关联)
- wiki_rag: 外部通用知识 (公司知识库不覆盖的常识)
- sag: SQL 检索 + 关联实体扩展 (查实体 + 同类关联)
- hybrid: 混合查询 (多个路径组合)

示例:
{examples}

现在判断下面这个问题:
问题: {query}

输出 JSON 格式:
{{"label": "路径名", "reason": "理由", "subqueries": [{{"q": "子问题", "path": "路径名"}}]}}

注意:
- 如果是 hybrid, subqueries 必须有 2 个以上元素, 否则 subqueries 为空数组
- 非 hybrid 的 subqueries 为空数组"""
        messages = [{"role": "user", "content": prompt}]
        result = self.llm.chat_json(messages, temperature=0.0, max_tokens=512)
        # 容错: 缺字段补默认
        result.setdefault("label", "traditional_rag")
        result.setdefault("reason", "")
        result.setdefault("subqueries", [])
        return result
