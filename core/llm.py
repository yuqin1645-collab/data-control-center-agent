"""LLM 封装: OpenAI 兼容协议, 支持 Qwen / Deepseek / OpenAI / 本地 vLLM.

支持:
  - chat(): 标准对话
  - chat_json(): JSON 输出
  - chat_with_tools(): Function Calling (工具调用)
  - chat_stream(): 流式输出 (SSE)
"""
import os
import json
from typing import Optional, List, Dict, Any, Generator
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    _instance: Optional["LLMClient"] = None

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "")
        self.model = os.getenv("LLM_MODEL", "qwen2.5-7b-instruct")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url) if self.api_key else None

    @classmethod
    def get(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def chat(self, messages, temperature=0.0, max_tokens=2048, response_format=None, model=None):
        """标准对话. model 可指定不同模型."""
        if not self.client:
            raise RuntimeError("LLM_API_KEY 未配置,请检查 .env")
        resp = self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        return resp.choices[0].message.content

    def chat_json(self, messages, temperature=0.0, max_tokens=2048):
        """要求 JSON 输出."""
        if not self.client:
            raise RuntimeError("LLM_API_KEY 未配置,请检查 .env")
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise

    def chat_with_tools(self, messages, tools=None, temperature=0.0, max_tokens=2048, model=None):
        """Function Calling: LLM 可以选择调用工具或直接回答.

        返回 message 对象 (含 content 和 tool_calls).
        参考 Claude Code: stop_reason == "tool_use" 决定是否继续循环.
        model: 可指定不同模型 (如 qwen-turbo 做快速工具选择)
        """
        if not self.client:
            raise RuntimeError("LLM_API_KEY 未配置,请检查 .env")
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message

    def chat_stream(self, messages, tools=None, temperature=0.0, max_tokens=2048, model=None) -> Generator:
        """流式输出: 逐 token 返回.

        yield 的事件格式:
          {"type": "text", "content": "..."}        — 文本块
          {"type": "tool_call", "name": "...", "arguments": {...}} — 工具调用
          {"type": "done"}                           — 结束
        model: 可指定不同模型 (如 qwen-turbo 做快速工具选择)
        """
        if not self.client:
            raise RuntimeError("LLM_API_KEY 未配置,请检查 .env")
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self.client.chat.completions.create(**kwargs)

        # 支持多个 tool_call: 用 list 按 index 跟踪
        tool_calls_buffer = []

        for chunk in resp:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # 文本内容 (逐 token yield)
            if delta.content:
                yield {"type": "text", "content": delta.content}

            # 工具调用 (流式累积 arguments)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index if hasattr(tc, "index") and tc.index is not None else 0
                    while len(tool_calls_buffer) <= idx:
                        tool_calls_buffer.append({"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        tool_calls_buffer[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_buffer[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_buffer[idx]["arguments"] += tc.function.arguments

            # 结束: 把所有 tool_call 一次性 yield
            if chunk.choices[0].finish_reason:
                for tc_buf in tool_calls_buffer:
                    if tc_buf["name"]:
                        try:
                            args = json.loads(tc_buf["arguments"])
                        except json.JSONDecodeError:
                                                        args = {"query": tc_buf["arguments"]}
                        yield {"type": "tool_call", "name": tc_buf["name"], "arguments": args}
                yield {"type": "done"}
                break
