"""LLM 封装: OpenAI 兼容协议, 支持 Qwen / Deepseek / OpenAI / 本地 vLLM."""
import os
import json
from typing import Optional
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

    def chat(self, messages, temperature=0.0, max_tokens=2048, response_format=None):
        """标准对话."""
        if not self.client:
            raise RuntimeError("LLM_API_KEY 未配置,请检查 .env")
        resp = self.client.chat.completions.create(
            model=self.model,
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
            # 部分模型不严格遵守 json_object, 做容错
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            raise
