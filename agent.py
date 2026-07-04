"""数据中控 Agent: 多步 Agent Loop + Function Calling.

参考 Claude Code 的 query.ts while-true loop:
  1. LLM 收到用户问题 + 可用工具列表
  2. LLM 决定: 直接回答 OR 调用工具
  3. 如果调用工具 → 执行 → 结果追加到 messages → 回到步骤 1
  4. 如果直接回答 → 返回最终答案
  5. 最大 5 轮迭代防止死循环

替代了旧的「规则路由器 → 编排器 → 生成器」单次流水线,
实现了 LLM 自主决策 + 多步推理.
"""
import time
import json
from typing import List, Dict, Optional, Generator
from core.llm import LLMClient
from core.tool_registry import ToolRegistry
from core.cache import EmbeddingCache
from core.compact import ContextCompactor

MAX_ITERATIONS = 5

# 工具选择用快速模型 (qwen-turbo ~1.5s), 回答生成用大模型 (qwen-plus ~6s)
ROUTE_MODEL = "qwen-turbo"
ANSWER_MODEL = None  # None = 用默认模型 (qwen-plus)

# 关键词快速路由: 命中则跳过 LLM 工具选择, 直接到工具执行 (省 1.5s)
KEYWORD_ROUTES = {
    "query_sql": ["销售额", "订单", "库存", "统计", "排名", "数量", "总计", "平均",
                   "合计", "同比", "环比", "多少", "计数", "汇总", "分组", "排名前",
                   "产品", "客户", "供应商", "员工", "部门", "区域", "月", "季度",
                   "年", "利润", "成本", "价格", "金额"],
    "search_documents": ["流程", "制度", "手册", "规定", "政策", "报销", "年假",
                          "考勤", "操作", "指南", "规范", "审批", "请假"],
    "query_graph": ["关系", "关联", "人际关系", "组织架构", "多跳", "认识",
                     "上下级", "汇报", "合作"],
    "search_wiki": ["什么是", "百科", "历史", "由来", "定义", "概念",
                     "原理", "解释一下"],
    "query_sag": ["以及相关", "扩展", "同类", "还买了", "也买了"],
}


def _fast_route(query: str) -> Optional[str]:
    """关键词快速路由: 命中返回工具名, 否则 None (走 LLM Agent Loop).

    设计参考: 混合路由 = 规则 (快) + LLM (准)
    简单查询走规则 (0ms), 复杂/模糊查询走 LLM (1.5s)
    """
    for tool_name, keywords in KEYWORD_ROUTES.items():
        if any(kw in query for kw in keywords):
            return tool_name
    return None

SYSTEM_PROMPT = """你是数据中控 Agent, 一个企业级数据分析助手.

你可以调用以下工具来回答用户问题:
- query_sql: 查询结构化数据库 (销售额、订单、统计)
- search_documents: 检索公司文档 (流程、制度、手册)
- query_graph: 查询知识图谱 (实体关系、多跳关联)
- search_wiki: 检索 Wikipedia (外部通用知识)
- query_sag: SQL + 关联实体扩展 (查实体 + 关联扩展)

工作流程:
1. 分析用户问题, 决定是否需要调用工具
2. 如果需要, 选择最合适的工具调用 (一次可以调用多个)
3. 查看工具返回结果, 判断是否足够回答
4. 如果不够, 继续调用其他工具 (多步推理)
5. 基于工具返回的数据, 生成最终回答

要求:
- 基于工具返回的数据回答, 不要编造
- 数据不足时明确说明 "根据现有数据无法完全回答"
- 涉及数值给出具体数字
- 简洁专业"""


class DataControlCenterAgent:
    """数据中控 Agent (多步 Agent Loop)."""

    def __init__(self):
        self.llm = LLMClient.get()
        self.tools = ToolRegistry.get()
        self.cache = EmbeddingCache.get_instance()
        self.compactor = ContextCompactor.get()

    def ask(self, query: str, user: dict = None, history: List[dict] = None) -> Dict:
        """主入口: 多步 Agent Loop.

        参考 Claude Code query.ts:
          while True:
              response = LLM(messages, tools)
              if response.has_tool_calls:
                  execute tools, append results
                  continue
              else:
                  return response.text
        """
        t0 = time.time()

        # 1. 缓存命中检查 (按 user scope 隔离, 避免跨权限命中)
        cached, hit = self.cache.get(query, user=user)
        if hit:
            return {
                "answer": cached.get("answer", ""),
                "route": cached.get("route", {"label": "cached", "reason": "语义缓存命中"}),
                "path_results": cached.get("path_results", []),
                "latency": 0.0,
                "cached": True,
                "iterations": 0,
            }

        # 2. 构造消息列表 (参考 Claude Code messages[])
        messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # 多轮对话历史 (压缩后)
        if history:
            compacted = self.compactor.compact_if_needed(history)
            for h in compacted:
                messages.append({"role": h["role"], "content": h["content"]})

        messages.append({"role": "user", "content": query})

        # 3. 工具 schema
        tool_schemas = self.tools.to_openai_tools()

        # 4. Agent Loop (参考 Claude Code while-true)
        path_results = []
        route_label = ""
        route_reason = ""
        iterations = 0

        for iteration in range(MAX_ITERATIONS):
            iterations = iteration + 1
            msg = self.llm.chat_with_tools(
                messages, tools=tool_schemas, temperature=0.0, max_tokens=1024
            )

            # 如果 LLM 没有调用工具, 说明它已经有了答案
            if not msg.tool_calls:
                answer = msg.content or "无法回答该问题"
                break

            # 把 assistant 的 tool_call 消息加入历史
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            # 记录路由信息 (第一次调用的工具作为路由标签)
            if iteration == 0:
                tool_names = [tc.function.name for tc in msg.tool_calls]
                route_label = "+".join(tool_names)
                route_reason = f"LLM 自主选择: {', '.join(tool_names)}"

            # 执行每个工具调用
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"query": tc.function.arguments}

                # 传入 user 用于行级权限
                if user:
                    args["user"] = user

                result_str = self.tools.execute(tool_name, args)

                # 记录 path_result (兼容前端展示)
                path_results.append({
                    "path": tool_name,
                    "query": args.get("query", ""),
                    "result": {
                        "context": result_str[:2000],
                        "raw": _safe_json(result_str),
                    },
                    "error": None,
                })

                # 把工具结果加入消息 (参考 Claude Code: append tool_result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })
        else:
            # 达到最大迭代次数
            answer = self.llm.chat(
                messages + [{"role": "user", "content": "请基于以上信息给出最终回答, 如果信息不足请说明."}],
                temperature=0.0,
                max_tokens=1024,
            )
            if not route_label:
                route_label = "max_iterations"
                route_reason = f"达到最大迭代次数 {MAX_ITERATIONS}"

        latency = round(time.time() - t0, 2)

        result = {
            "answer": answer,
            "route": {"label": route_label, "reason": route_reason},
            "path_results": path_results,
            "latency": latency,
            "cached": False,
            "iterations": iterations,
        }

        # 写缓存 (按 user scope 隔离, 避免污染其他权限的缓存)
        if answer and "无法" not in answer[:10]:
            self.cache.set(query, {
                "answer": answer,
                "route": result["route"],
                "path_results": [
                    {"path": r["path"], "query": r["query"], "result": r["result"]}
                    for r in path_results
                ],
            }, user=user)

        return result

    def ask_stream(self, query: str, user: dict = None, history: List[dict] = None) -> Generator:
        """流式版: 逐事件 yield.

        事件类型:
          {"type": "route", "label": ..., "reason": ...}   — 路由决策
          {"type": "tool_call", "name": ..., "args": ...}  — 工具调用开始
          {"type": "tool_result", "name": ..., "result": ..} — 工具返回
          {"type": "text", "content": "..."}               — 文本块 (逐字)
          {"type": "done", "latency": ..., "iterations": ..} — 结束
        """
        t0 = time.time()
        messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if history:
            compacted = self.compactor.compact_if_needed(history)
            for h in compacted:
                messages.append({"role": h["role"], "content": h["content"]})

        messages.append({"role": "user", "content": query})
        tool_schemas = self.tools.to_openai_tools()
        path_results = []
        iterations = 0

        # === 快速路由: 关键词命中则跳过 LLM 工具选择 (省 1.5s) ===
        fast_tool = _fast_route(query)
        if fast_tool:
            print(f"[Agent] 关键词快速路由: {fast_tool}")
            yield {"type": "route", "label": fast_tool, "reason": "关键词快速路由 (跳过 LLM)"}
            yield {"type": "tool_call", "name": fast_tool, "args": {"query": query}}
            yield {"type": "status", "message": f"正在执行 {fast_tool}..."}

            args = {"query": query}
            if user:
                args["user"] = user

            t_tool = time.time()
            result_str = self.tools.execute(fast_tool, args)
            print(f"[Agent] 快速路由工具执行: {fast_tool}, 耗时 {round(time.time()-t_tool,2)}s")
            raw_data = _safe_json(result_str)

            path_results.append({
                "path": fast_tool,
                "query": query,
                "result": {"context": result_str[:2000], "raw": raw_data},
                "error": None,
            })
            yield {"type": "tool_result", "name": fast_tool, "result": result_str[:500], "raw": raw_data}

            # 构造消息: 模拟 tool_call + tool_result, 让 LLM 直接生成回答
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_fast",
                    "type": "function",
                    "function": {"name": fast_tool, "arguments": json.dumps({"query": query}, ensure_ascii=False)},
                }],
            })
            messages.append({"role": "tool", "tool_call_id": "call_fast", "content": result_str})

            # LLM 生成回答 (流式)
            yield {"type": "status", "message": "正在生成回答..."}
            t_ans = time.time()
            print(f"[Agent] 快速路由回答生成开始 (model={ANSWER_MODEL or 'default'})")
            for event in self.llm.chat_stream(messages, tools=None, temperature=0.0, max_tokens=768, model=ANSWER_MODEL):
                if event["type"] == "text":
                    yield {"type": "text", "content": event["content"]}
                elif event["type"] == "done":
                    break
            print(f"[Agent] 快速路由回答生成完成, 耗时 {round(time.time()-t_ans,2)}s")

            latency = round(time.time() - t0, 2)
            yield {"type": "done", "latency": latency, "iterations": 1, "path_results": path_results}
            return

        # === 未命中关键词, 走完整 Agent Loop ===
        yield {"type": "status", "message": "正在分析问题..."}

        for iteration in range(MAX_ITERATIONS):
            iterations = iteration + 1
            has_tool_call = False
            tool_calls_data = []
            current_text = ""

            route_model = ROUTE_MODEL if iteration == 0 else ANSWER_MODEL
            t_llm = time.time()
            print(f"[Agent] 迭代{iterations} LLM调用开始 (model={route_model or 'default'})")

            for event in self.llm.chat_stream(messages, tools=tool_schemas, temperature=0.0, max_tokens=768, model=route_model):
                if event["type"] == "text":
                    current_text += event["content"]
                    yield {"type": "text", "content": event["content"]}
                elif event["type"] == "tool_call":
                    has_tool_call = True
                    tool_calls_data.append(event)
                    yield {"type": "tool_call", "name": event["name"], "args": event.get("arguments", {})}
                elif event["type"] == "done":
                    break

            print(f"[Agent] 迭代{iterations} LLM调用完成, 耗时 {round(time.time()-t_llm,2)}s, tool_call={has_tool_call}")

            if not has_tool_call:
                latency = round(time.time() - t0, 2)
                yield {"type": "done", "latency": latency, "iterations": iterations, "path_results": path_results}
                return

            messages.append({
                "role": "assistant",
                "content": current_text,
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                        },
                    }
                    for i, tc in enumerate(tool_calls_data)
                ],
            })

            if iteration == 0:
                tool_names = [tc["name"] for tc in tool_calls_data]
                yield {"type": "route", "label": "+".join(tool_names), "reason": f"LLM 自主选择: {', '.join(tool_names)}"}

            for i, tc in enumerate(tool_calls_data):
                tool_name = tc["name"]
                args = tc.get("arguments", {})
                if user:
                    args["user"] = user

                yield {"type": "status", "message": f"正在执行 {tool_name}..."}

                t_tool = time.time()
                print(f"[Agent] 工具执行开始: {tool_name}, query={args.get('query','')[:50]}")
                result_str = self.tools.execute(tool_name, args)
                print(f"[Agent] 工具执行完成: {tool_name}, 耗时 {round(time.time()-t_tool,2)}s")
                raw_data = _safe_json(result_str)

                path_results.append({
                    "path": tool_name,
                    "query": args.get("query", ""),
                    "result": {"context": result_str[:2000], "raw": raw_data},
                    "error": None,
                })

                yield {"type": "tool_result", "name": tool_name, "result": result_str[:500], "raw": raw_data}

                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{i}",
                    "content": result_str,
                })

            yield {"type": "status", "message": "正在生成回答..."}

        latency = round(time.time() - t0, 2)
        yield {"type": "done", "latency": latency, "iterations": iterations, "path_results": path_results}


def _safe_json(s: str) -> dict:
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {"raw": s[:500]}


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "上个月华东区销售额是多少"
    default_user = {"id": 0, "username": "cli", "dept_id": "ADMIN", "role": "admin"}
    agent = DataControlCenterAgent()
    res = agent.ask(q, user=default_user)
    print(f"\n问题: {q}")
    print(f"路由: {res['route'].get('label')} ({res['route'].get('reason')})")
    print(f"迭代: {res.get('iterations', 1)} 轮 | 耗时: {res['latency']}s | 缓存: {res['cached']}")
    print(f"\n回答:\n{res['answer']}")
