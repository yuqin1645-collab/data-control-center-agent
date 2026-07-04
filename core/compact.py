"""Context 压缩: 多轮对话历史自动压缩.

参考 Claude Code 的 autoCompact 机制:
  - 当消息数超过阈值时, 把旧消息压缩为摘要
  - 插入 compact_boundary 标记, 保留最近 N 条完整消息
  - 压缩后的摘要 + 最近消息 = 新的 messages[]

三种压缩策略 (参考 Claude Code):
  1. autoCompact: LLM 摘要旧消息 (主要策略)
  2. snipCompact: 截断超长单条消息 (辅助)
  3. 保留最近 RECENT 条消息完整不动
"""
import json
from typing import List, Dict, Optional
from core.llm import LLMClient

# 压缩阈值: 超过这么多条消息就触发压缩
MAX_MESSAGES = 20
# 压缩后保留最近多少条完整消息
RECENT_KEEP = 6
# 单条消息最大字符数 (超过截断)
MAX_MSG_CHARS = 2000


class ContextCompactor:
    """Context 自动压缩器. 单例."""

    _instance: Optional["ContextCompactor"] = None

    def __init__(self):
        self.llm = LLMClient.get()

    @classmethod
    def get(cls) -> "ContextCompactor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def compact_if_needed(self, messages: List[dict]) -> List[dict]:
        """如果消息太多, 压缩旧消息为摘要.

        参考 Claude Code autoCompact:
          messages[] ──> getMessagesAfterCompactBoundary()
          旧消息 ──> LLM 摘要 ──> [summary] + [compact_boundary] + [recent messages]
        """
        if not messages or len(messages) <= MAX_MESSAGES:
            return messages

        # 分割: 旧的要压缩, 最近的保留
        old_messages = messages[:-RECENT_KEEP]
        recent_messages = messages[-RECENT_KEEP:]

        # 先做 snipCompact: 截断超长消息
        old_snipped = [self._snip(m) for m in old_messages]

        # autoCompact: LLM 摘要
        summary = self._summarize(old_snipped)

        # 构造压缩后的消息列表
        compacted = [
            {
                "role": "system",
                "content": f"[compact_boundary] 以下是之前 {len(old_messages)} 条消息的摘要:\n\n{summary}\n\n=== 以下是最近 {RECENT_KEEP} 条消息 ===",
            }
        ]
        compacted.extend(recent_messages)

        return compacted

    def _snip(self, msg: dict) -> dict:
        """snipCompact: 截断超长单条消息."""
        content = msg.get("content", "")
        if len(content) > MAX_MSG_CHARS:
            msg = {**msg, "content": content[:MAX_MSG_CHARS] + "...[已截断]"}
        return msg

    def _summarize(self, messages: List[dict]) -> str:
        """autoCompact: 用 LLM 摘要旧消息."""
        # 构造对话文本
        lines = []
        for m in messages:
            role = m.get("role", "?")
            content = m.get("content", "")[:500]
            lines.append(f"[{role}] {content}")

        dialog = "\n".join(lines)

        prompt = f"""请将以下对话历史压缩为简洁的摘要, 保留关键信息 (实体、数值、结论).

对话历史:
{dialog}

输出格式: 3-5 句话的摘要, 保留:
1. 用户问了什么问题
2. 调用了什么工具/路径
3. 关键数据结果
4. 已得出的结论"""

        try:
            return self.llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=512,
            )
        except Exception as e:
            # 压缩失败时降级: 取每条消息的前 100 字
            return " | ".join(
                f"[{m.get('role', '?')}] {m.get('content', '')[:100]}"
                for m in messages
            )
