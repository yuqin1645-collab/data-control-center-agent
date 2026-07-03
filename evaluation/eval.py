"""评估脚本: 路由准确率 + 各路径召回 + 端到端回答准确率.

用法:
    python evaluation/eval.py
    python evaluation/eval.py --router-only
"""
import sys
import os
import json
import argparse

# 标注测试集: (问题, 期望路由)
TEST_CASES = [
    ("上个月华东区销售额是多少", "text_to_sql"),
    ("订单 O0001 的状态是什么", "text_to_sql"),
    ("公司报销流程是什么", "traditional_rag"),
    ("退货政策是怎样的", "traditional_rag"),
    ("张三和李四之间有什么业务关联", "graph_rag"),
    ("产品P005和产品P010有什么关系", "graph_rag"),
    ("端午节是哪天有什么习俗", "wiki_rag"),
    ("端午节是几月几日", "wiki_rag"),
    ("客户C001买了哪些产品以及这些产品的同类产品还有谁在买", "sag"),
    ("华东区退货率多少,退货流程是什么", "hybrid"),
]


def eval_router():
    """路由准确率."""
    from core.router import IntentRouter
    router = IntentRouter.get()
    correct = 0
    results = []
    for q, expected in TEST_CASES:
        try:
            r = router.route(q)
            pred = r.get("label", "?")
            ok = pred == expected
            if ok:
                correct += 1
            results.append({"q": q, "expected": expected, "pred": pred, "ok": ok,
                            "reason": r.get("reason", "")})
        except Exception as e:
            results.append({"q": q, "expected": expected, "pred": "ERROR", "ok": False,
                            "reason": str(e)})
    acc = correct / len(TEST_CASES) * 100
    print(f"\n路由准确率: {correct}/{len(TEST_CASES)} = {acc:.1f}%\n")
    for r in results:
        mark = "✓" if r["ok"] else "✗"
        print(f"  {mark} [{r['expected']}>{r['pred']}] {r['q']}")
        if not r["ok"]:
            print(f"      理由: {r['reason'][:80]}")
    return acc


def eval_e2e():
    """端到端: 跑通每条路径."""
    from agent import DataControlCenterAgent
    agent = DataControlCenterAgent()
    print("\n端到端测试:")
    for q, expected in TEST_CASES:
        try:
            res = agent.ask(q)
            ok = "✓" if res.get("answer") and "失败" not in res["answer"][:20] else "✗"
            print(f"  {ok} [{res['route'].get('label')}] {q} -> {res['latency']}s")
        except Exception as e:
            print(f"  ✗ [{expected}] {q} -> ERROR: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--router-only", action="store_true")
    args = parser.parse_args()

    if args.router_only:
        eval_router()
    else:
        eval_router()
        eval_e2e()
