"""RAGAS 评估: 对 5 条检索路径进行量化评估.

指标:
  - faithfulness: 答案是否忠于检索上下文 (不编造)
  - answer_relevancy: 答案是否切题
  - context_precision: 检索上下文精确率
  - context_recall: 检索上下文召回率

用法:
    cd data-control-center-agent
    PYTHONPATH=. python evaluation/ragas_eval.py

需要:
    - .env 配置好 LLM_API_KEY (百炼/DashScope)
    - 数据源已初始化 (scripts/init_*.py)
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agent import DataControlCenterAgent

TEST_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ragas_test_data.json")
RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ragas_results.json")

# admin 用户 (全部门访问)
TEST_USER = {"id": 1, "username": "admin", "dept_id": "ADMIN", "role": "admin"}


def run_ragas_eval():
    """运行 RAGAS 评估."""
    print("=" * 60)
    print("数据中控 Agent — RAGAS 评估")
    print("=" * 60)

    # 1. 加载测试数据
    with open(TEST_DATA_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)
    print(f"\n加载 {len(test_cases)} 个测试用例")

    # 2. 初始化 Agent
    print("\n初始化 Agent...")
    agent = DataControlCenterAgent()

    # 3. 对每个测试用例运行查询
    print("\n运行查询...")
    results = []
    for i, tc in enumerate(test_cases):
        print(f"  [{i+1}/{len(test_cases)}] [{tc['path']}] {tc['question'][:30]}...", end=" ")
        t0 = time.time()
        try:
            result = agent.ask(tc["question"], user=TEST_USER)
            elapsed = round(time.time() - t0, 2)

            # 提取回答和上下文
            answer = result.get("answer", "")
            context = ""
            for pr in result.get("path_results", []):
                if pr.get("result") and pr["result"].get("context"):
                    context += pr["result"]["context"] + "\n"

            results.append({
                "path": tc["path"],
                "question": tc["question"],
                "answer": answer,
                "context": context,
                "reference_answer": tc["reference_answer"],
                "reference_context": tc["reference_context"],
                "elapsed": elapsed,
                "route": result.get("route", {}).get("label", ""),
                "error": None,
            })
            print(f"✅ ({elapsed}s)")
        except Exception as e:
            elapsed = round(time.time() - t0, 2)
            results.append({
                "path": tc["path"],
                "question": tc["question"],
                "answer": "",
                "context": "",
                "reference_answer": tc["reference_answer"],
                "reference_context": tc["reference_context"],
                "elapsed": elapsed,
                "route": "",
                "error": str(e),
            })
            print(f"❌ ({elapsed}s) {e}")

    # 4. 用 RAGAS 评估
    print("\n运行 RAGAS 评估...")
    try:
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from datasets import Dataset

        # 构造 RAGAS 数据集
        data = {
            "question": [r["question"] for r in results],
            "answer": [r["answer"] for r in results],
            "contexts": [[r["context"]] if r["context"] else ["(无上下文)"] for r in results],
            "ground_truth": [r["reference_answer"] for r in results],
            "ground_truth_contexts": [[r["reference_context"]] for r in results],
        }
        ds = Dataset.from_dict(data)

        # 使用项目配置的 LLM
        from core.llm import LLMClient
        llm_client = LLMClient.get()

        # RAGAS 评估
        scores = evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        scores_df = scores.to_pandas()

        # 按路径分组计算平均分
        print("\n" + "=" * 60)
        print("RAGAS 评估结果")
        print("=" * 60)
        print(f"{'路径':<20} {'faithfulness':<15} {'answer_relevancy':<20} {'context_precision':<20} {'context_recall':<18}")
        print("-" * 90)

        path_scores = {}
        for i, r in enumerate(results):
            path = r["path"]
            if path not in path_scores:
                path_scores[path] = {"faithfulness": [], "answer_relevancy": [], "context_precision": [], "context_recall": []}
            path_scores[path]["faithfulness"].append(float(scores_df.iloc[i].get("faithfulness", 0)))
            path_scores[path]["answer_relevancy"].append(float(scores_df.iloc[i].get("answer_relevancy", 0)))
            path_scores[path]["context_precision"].append(float(scores_df.iloc[i].get("context_precision", 0)))
            path_scores[path]["context_recall"].append(float(scores_df.iloc[i].get("context_recall", 0)))

        all_faith = []
        all_rel = []
        all_prec = []
        all_rec = []

        for path, scores in sorted(path_scores.items()):
            f = sum(scores["faithfulness"]) / len(scores["faithfulness"])
            a = sum(scores["answer_relevancy"]) / len(scores["answer_relevancy"])
            p = sum(scores["context_precision"]) / len(scores["context_precision"])
            r = sum(scores["context_recall"]) / len(scores["context_recall"])
            print(f"{path:<20} {f:<15.2f} {a:<20.2f} {p:<20.2f} {r:<18.2f}")
            all_faith.append(f)
            all_rel.append(a)
            all_prec.append(p)
            all_rec.append(r)

        print("-" * 90)
        print(f"{'总体平均':<20} {sum(all_faith)/len(all_faith):<15.2f} {sum(all_rel)/len(all_rel):<20.2f} {sum(all_prec)/len(all_prec):<20.2f} {sum(all_rec)/len(all_rec):<18.2f}")

        # 保存结果
        output = {
            "metrics_by_path": {
                path: {
                    "faithfulness": sum(s["faithfulness"]) / len(s["faithfulness"]),
                    "answer_relevancy": sum(s["answer_relevancy"]) / len(s["answer_relevancy"]),
                    "context_precision": sum(s["context_precision"]) / len(s["context_precision"]),
                    "context_recall": sum(s["context_recall"]) / len(s["context_recall"]),
                }
                for path, s in path_scores.items()
            },
            "overall": {
                "faithfulness": sum(all_faith) / len(all_faith),
                "answer_relevancy": sum(all_rel) / len(all_rel),
                "context_precision": sum(all_prec) / len(all_prec),
                "context_recall": sum(all_rec) / len(all_rec),
            },
            "individual_results": results,
        }
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存: {RESULTS_PATH}")

    except ImportError:
        print("⚠️  ragas 未安装, 跳过 RAGAS 评估")
        print("安装: pip install ragas datasets")
        # 保存原始结果
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"individual_results": results}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  RAGAS 评估失败: {e}")
        # 保存原始结果
        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"individual_results": results, "ragas_error": str(e)}, f, ensure_ascii=False, indent=2)

    print("\n✅ 评估完成")


if __name__ == "__main__":
    run_ragas_eval()
