"""Tool 注册表: 把检索路径封装为 Agent 可调用的 Tool.

参考 Claude Code 的 Tool.ts + tools.ts 设计:
  - 每个 Tool 有 name, description, parameters (JSON schema)
  - call() 执行并返回结果
  - ToolRegistry 单例管理所有已注册 Tool
  - to_openai_tools() 导出为 OpenAI function calling 格式

这把 Agent 从「规则路由器 if-else」升级为「LLM 自主决策调用工具」.
"""
import json
from typing import Dict, List, Any, Optional


class Tool:
    """Tool 基类. 参考 Claude Code buildTool() 工厂模式."""

    name: str = ""
    description: str = ""
    parameters: dict = {}  # JSON schema

    def call(self, **kwargs) -> str:
        """执行 Tool, 返回字符串结果 (给 LLM 看)."""
        raise NotImplementedError

    def to_openai_schema(self) -> dict:
        """导出为 OpenAI function calling 格式."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Tool 注册表单例. 管理 Tool 的注册/查询/执行."""

    _instance: Optional["ToolRegistry"] = None

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_defaults()

    @classmethod
    def get(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> List[dict]:
        """导出所有 Tool 的 OpenAI function calling schema."""
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        """执行指定 Tool, 返回结果字符串."""
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        try:
            return tool.call(**arguments)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def _register_defaults(self):
        """注册默认 Tool (5 条检索路径)."""
        from core.tools import (
            SQLQueryTool,
            DocumentSearchTool,
            GraphQueryTool,
            WikiSearchTool,
            SAGQueryTool,
        )

        self.register(SQLQueryTool())
        self.register(DocumentSearchTool())
        self.register(GraphQueryTool())
        self.register(WikiSearchTool())
        self.register(SAGQueryTool())
