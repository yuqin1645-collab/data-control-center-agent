"""数据中控 Agent 主入口: 路由 -> 编排 -> 聚合 -> 生成."""
import time
from typing import List, Dict
from core.router import IntentRouter
from core.orchestrator import Orchestrator
from core.cache import EmbeddingCache
from core.llm import LLMClient


class DataControlCenterAgent:
    """数据中控 Agent.

    用法:
        agent = DataControlCenterAgent()
        result = agent.ask("上个月华东区销售额多少")
        print(result["answer"])
    """

    def __init__(self):
        self.router = IntentRouter.get()
        self.orchestrator = Orchestrator.get()
        self.cache = EmbeddingCache.get()
        self.llm = LLMClient.get()

    def _aggregate_context(self, path_results: List[Dict]) -> str:
        """把多路检索结果拼成统一上下文."""
        parts = []
        for r in path_results:
            if r["error"]:
                parts.append(f"[{r['path']}] 失败: {r['error']}")
                continue
            ctx = r["result"]["context"] if r["result"] else "(无结果)"
            parts.append(f"[{r['path']}] 查询: {r['query']}\n{ctx}")
        return "\n\n=====\n\n".join(parts)

    def _generate_answer(self, query: str, context: str, route_label: str) -> str:
        prompt = f"""你是数据中控 Agent 的回答生成器. 根据检索到的上下文回答用户问题.

用户问题: {query}
检索路径: {route_label}
检索上下文:
{context}

要求:
1. 基于上下文回答, 不要编造
2. 上下文不足时明确说明 "根据现有数据无法完全回答"
3. 涉及数值给出具体数字
4. 简洁专业"""
        messages = [{"role": "user", "content": prompt}]
        return self.llm.chat(messages, temperature=0.0, max_tokens=1024)

    def ask(self, query: str, history: List[dict] = None) -> Dict:
        """主入口."""
        t0 = time.time()

        # 1. 缓存命中检查
        cached, hit = self.cache.get(query)
        if hit:
            return {"answer": cached.get("answer", ""), "route": cached.get("route"),
                    "path_results": cached.get("path_results"), "latency": 0.0,
                    "cached": True}

        # 2. 意图路由
        route = self.router.route(query, history)

        # 3. 执行编排
        path_results = self.orchestrator.run(route, query)

        # 4. 聚合上下文
        context = self._aggregate_context(path_results)

        # 5. 生成回答
        answer = self._generate_answer(query, context, route.get("label", ""))

        latency = round(time.time() - t0, 2)
        result = {
            "answer": answer,
            "route": route,
            "path_results": path_results,
            "latency": latency,
            "cached": False,
        }

        # 6. 写缓存 (只缓存成功的)
        if answer and "无法" not in answer[:10]:
            self.cache.set(query, {
                "answer": answer,
                "route": route,
                "path_results": [{"path": r["path"], "query": r["query"],
                                  "result": r["result"]} for r in path_results],
            })

        return result


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "上个月华东区销售额是多少"
    agent = DataControlCenterAgent()
    res = agent.ask(q)
    print(f"\n问题: {q}")
    print(f"路由: {res['route'].get('label')} ({res['route'].get('reason')})")
    print(f"耗时: {res['latency']}s | 缓存命中: {res['cached']}")
    print(f"\n回答:\n{res['answer']}")
