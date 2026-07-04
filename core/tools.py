"""Tool 实现: 把 5 条检索路径封装为 Agent Tool.

每个 Tool 包装一个 retriever, 定义 JSON schema 参数,
LLM 通过 function calling 自主选择调用哪个 Tool.

参考 Claude Code: "Adding a tool = adding one handler"
"""
import json
import time
from core.tool_registry import Tool
from core.orchestrator import Orchestrator


class SQLQueryTool(Tool):
    """结构化数据库查询 (SQL)."""

    name = "query_sql"
    description = (
        "查询结构化数据库 (SQLite). 适用于: 销售额、订单数、库存、统计、排名、聚合等. "
        "会自动生成 SQL 并执行, 返回查询结果. 支持行级权限隔离."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言查询, 如 '华东区上个月销售额' 或 '销售额排名前5的产品'",
            }
        },
        "required": ["query"],
    }

    def call(self, query: str = "", **kwargs) -> str:
        user = kwargs.get("user")
        t0 = time.time()
        orch = Orchestrator.get()
        print(f"[Tool] execute_path 开始")
        result = orch.execute_path("text_to_sql", query, user=user)
        print(f"[Tool] execute_path 完成, 耗时 {round(time.time()-t0,2)}s")
        t_fmt = time.time()
        formatted = _format_result(result)
        print(f"[Tool] _format_result 完成, 耗时 {round(time.time()-t_fmt,2)}s, len={len(formatted)}")
        return formatted


class DocumentSearchTool(Tool):
    """文档知识检索 (RAG)."""

    name = "search_documents"
    description = (
        "检索公司内部文档资料 (向量检索). 适用于: 报销流程、规章制度、操作手册、"
        "政策文件等非结构化知识. 基于 embedding 语义匹配."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言查询, 如 '员工报销流程是什么' 或 '年假制度'",
            }
        },
        "required": ["query"],
    }

    def call(self, query: str = "", **kwargs) -> str:
        user = kwargs.get("user")
        orch = Orchestrator.get()
        result = orch.execute_path("traditional_rag", query, user=user)
        return _format_result(result)


class GraphQueryTool(Tool):
    """知识图谱关系查询."""

    name = "query_graph"
    description = (
        "查询知识图谱中的实体关系. 适用于: 人际关系、组织架构、多跳关联推理, "
        "如 '张三和李四有什么关系' 或 '产品A的供应商的客户是谁'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言关系查询, 如 '张三和李四的关系'",
            }
        },
        "required": ["query"],
    }

    def call(self, query: str = "", **kwargs) -> str:
        user = kwargs.get("user")
        orch = Orchestrator.get()
        result = orch.execute_path("graph_rag", query, user=user)
        return _format_result(result)


class WikiSearchTool(Tool):
    """外部通用知识检索 (Wikipedia)."""

    name = "search_wiki"
    description = (
        "检索 Wikipedia 外部通用知识. 适用于: 公司知识库不覆盖的常识、"
        "百科、历史、地理、科学概念等, 如 '什么是机器学习' 或 '端午节由来'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言查询, 如 '什么是机器学习'",
            }
        },
        "required": ["query"],
    }

    def call(self, query: str = "", **kwargs) -> str:
        user = kwargs.get("user")
        orch = Orchestrator.get()
        result = orch.execute_path("wiki_rag", query, user=user)
        return _format_result(result)


class SAGQueryTool(Tool):
    """SQL + 关联实体扩展查询 (SAG)."""

    name = "query_sag"
    description = (
        "SQL 查询 + 超图关联实体扩展. 适用于: 查某实体并扩展到关联实体, "
        "如 '客户C001买了什么产品以及相关产品' 或 '和产品A同类的产品还有谁在买'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "自然语言查询, 如 '客户C001买了什么产品以及相关产品'",
            }
        },
        "required": ["query"],
    }

    def call(self, query: str = "", **kwargs) -> str:
        user = kwargs.get("user")
        orch = Orchestrator.get()
        result = orch.execute_path("sag", query, user=user)
        return _format_result(result)


def _format_result(path_result: dict) -> str:
    """把 Orchestrator 返回的结果格式化为 LLM 可读的字符串."""
    if path_result.get("error"):
        return json.dumps(
            {"path": path_result["path"], "error": path_result["error"]},
            ensure_ascii=False,
        )
    r = path_result.get("result")
    if not r:
        return json.dumps({"path": path_result["path"], "result": "(无结果)"}, ensure_ascii=False)

    context = r.get("context", "")
    raw = r.get("raw", {})
    # 把 raw 的字段 (sql, rows, columns, edges, chunks 等) 展平到顶层
    # 这样前端 path_details 可以直接访问 pathDetails.sql 等
    result = {"path": path_result["path"], "context": context[:2000] if context else ""}
    if raw:
        result.update(raw)
    return json.dumps(result, ensure_ascii=False)
