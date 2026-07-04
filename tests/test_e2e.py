"""端到端测试: 验证 5 条检索路径全链路跑通.

用法:
    cd data-control-center-agent
    python -m tests.test_e2e

或用 pytest:
    pytest tests/test_e2e.py -v
"""
import sys
import os
import time

# 确保项目根在 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试用例: 每条路径一个代表性问题
TEST_CASES = [
    {
        "path": "text_to_sql",
        "query": "销售额排名前5的产品",
        "expect_route": "text_to_sql",
        "description": "结构化数据查询",
    },
    {
        "path": "traditional_rag",
        "query": "员工报销流程是什么",
        "expect_route": "traditional_rag",
        "description": "文档知识查询",
    },
    {
        "path": "graph_rag",
        "query": "张三和李四有什么关系",
        "expect_route": "graph_rag",
        "description": "关系推理查询",
    },
    {
        "path": "wiki_rag",
        "query": "什么是机器学习",
        "expect_route": "wiki_rag",
        "description": "外部通用知识",
    },
    {
        "path": "sag",
        "query": "客户C001买了什么产品以及相关产品",
        "expect_route": "sag",
        "description": "SQL+关联扩展",
    },
]

# admin 用户 (全部门访问, 测试用)
TEST_USER = {"id": 1, "username": "admin", "dept_id": "ADMIN", "role": "admin"}


def check_prerequisites():
    """检查数据源是否已初始化."""
    issues = []

    # 检查 sample_db
    if not os.path.exists("data/sample_db.sqlite"):
        issues.append("data/sample_db.sqlite 不存在, 请先运行: python scripts/init_db.py")

    # 检查 auth_db
    if not os.path.exists("data/agent_auth.db"):
        issues.append("data/agent_auth.db 不存在, 请先运行: python scripts/init_auth.py")

    # 检查知识图谱
    if not os.path.exists("data/graph.pkl"):
        issues.append("data/graph.pkl 不存在, 请先运行: python scripts/build_graph.py")

    # 检查 .env
    if not os.path.exists(".env") and not os.environ.get("LLM_API_KEY"):
        issues.append("LLM_API_KEY 未设置, 请配置 .env 文件")

    return issues


def run_e2e_test():
    """运行端到端测试."""
    print("=" * 60)
    print("数据中控 Agent — 端到端测试")
    print("=" * 60)

    # 1. 前置检查
    print("\n[1/3] 前置检查...")
    issues = check_prerequisites()
    if issues:
        print("\n❌ 前置检查失败:")
        for issue in issues:
            print(f"   - {issue}")
        print("\n请先运行初始化:")
        print("  python scripts/init_db.py")
        print("  python scripts/init_auth.py")
        print("  python scripts/index_documents.py")
        print("  python scripts/build_graph.py")
        return False

    print("   ✅ 数据源检查通过")

    # 2. 初始化 Agent
    print("\n[2/3] 初始化 Agent...")
    try:
        from agent import DataControlCenterAgent
        agent = DataControlCenterAgent()
        print("   ✅ Agent 初始化成功")
    except Exception as e:
        print(f"   ❌ Agent 初始化失败: {e}")
        return False

    # 3. 逐路径测试
    print("\n[3/3] 逐路径测试...")
    results = []
    all_passed = True

    for tc in TEST_CASES:
        print(f"\n   测试: [{tc['path']}] {tc['query']}")
        t0 = time.time()
        try:
            result = agent.ask(tc["query"], user=TEST_USER)
            elapsed = round(time.time() - t0, 2)

            # 验证
            route_label = result.get("route", {}).get("label", "")
            answer = result.get("answer", "")
            cached = result.get("cached", False)
            has_error = result.get("path_results", [{}])[0].get("error") if result.get("path_results") else None

            checks = {
                "路由正确": route_label == tc["expect_route"],
                "回答非空": bool(answer and len(answer) > 10),
                "无异常": has_error is None,
                "耗时<30s": elapsed < 30,
            }

            passed = all(checks.values())
            status = "✅ PASS" if passed else "❌ FAIL"
            all_passed = all_passed and passed

            print(f"   {status} ({elapsed}s, 缓存={cached})")
            for check_name, check_result in checks.items():
                print(f"      {'✅' if check_result else '❌'} {check_name}")

            if not passed:
                print(f"      路由: 期望={tc['expect_route']}, 实际={route_label}")
                print(f"      回答前100字: {answer[:100]}...")
                if has_error:
                    print(f"      异常: {has_error}")

            results.append({
                "path": tc["path"],
                "query": tc["query"],
                "passed": passed,
                "elapsed": elapsed,
                "cached": cached,
                "route": route_label,
                "answer_preview": answer[:200],
            })

        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            print(f"   ❌ ERROR ({elapsed}s): {e}")
            all_passed = False
            results.append({
                "path": tc["path"],
                "query": tc["query"],
                "passed": False,
                "elapsed": elapsed,
                "error": str(e),
            })

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    passed_count = sum(1 for r in results if r["passed"])
    print(f"通过: {passed_count}/{len(results)}")
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"  {status} [{r['path']}] {r.get('elapsed', 0)}s")

    if all_passed:
        print("\n🎉 全部测试通过!")
    else:
        print("\n⚠️  部分测试失败, 请检查上方日志")

    return all_passed


if __name__ == "__main__":
    success = run_e2e_test()
    sys.exit(0 if success else 1)
