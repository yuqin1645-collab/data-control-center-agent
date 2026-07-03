"""构建样本知识图谱 (GraphRAG 路径用).

两种模式:
1. 从样本文档抽取三元组 (LLM 抽取, 慢但真实)
2. 直接用预置三元组 (快, 用于 demo)

默认用模式 2, 加 --extract 启用模式 1.
"""
import sys
import pickle
import os
from retrieval.graph_rag.graph_builder import build_graph, load_graph, graph_stats, GRAPH_PATH

# 预置三元组: 模拟公司业务关系
PRESET_TRIPLES = [
    # 人员关系
    ("张三", "隶属", "销售部"),
    ("李四", "隶属", "客服部"),
    ("王五", "隶属", "技术部"),
    ("赵六", "隶属", "销售部"),
    ("张三", "管理", "赵六"),
    ("李四", "协作", "张三"),
    ("李四", "协作", "王五"),
    # 客户关系
    ("客户C001", "供货", "产品P005"),
    ("客户C001", "归属", "华东区"),
    ("客户C002", "供货", "产品P005"),
    ("客户C002", "归属", "华北区"),
    ("客户C003", "供货", "产品P010"),
    # 产品关系
    ("产品P005", "属于", "电子类"),
    ("产品P010", "属于", "服装类"),
    ("产品P005", "同类", "产品P006"),
    ("产品P010", "同类", "产品P011"),
    # 部门关系
    ("销售部", "服务", "华东区"),
    ("销售部", "服务", "华南区"),
    ("客服部", "服务", "华东区"),
    ("技术部", "支持", "销售部"),
    # 供应商
    ("供应商S01", "供应", "产品P005"),
    ("供应商S02", "供应", "产品P010"),
]


def build_preset():
    G = build_graph(PRESET_TRIPLES)
    stats = graph_stats(G)
    print(f"预置知识图谱已构建: {stats['nodes']} 节点 / {stats['edges']} 边")
    print(f"保存到: {GRAPH_PATH}")


def build_from_docs():
    """从文档抽取三元组 (慢, 需 LLM)."""
    import glob
    from retrieval.graph_rag.extractor import extract_triples
    all_triples = []
    files = glob.glob("data/documents/**/*.md", recursive=True)
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()
        # 分段抽取
        for i in range(0, len(text), 1500):
            chunk = text[i:i+1500]
            try:
                _, triples = extract_triples(chunk)
                all_triples.extend(triples)
                print(f"  {fpath}: +{len(triples)} 三元组")
            except Exception as e:
                print(f"  {fpath} 抽取失败: {e}")
    # 合并预置
    all_triples.extend(PRESET_TRIPLES)
    G = build_graph(all_triples)
    stats = graph_stats(G)
    print(f"\n知识图谱构建完成: {stats['nodes']} 节点 / {stats['edges']} 边 (含抽取+预置)")


if __name__ == "__main__":
    if "--extract" in sys.argv:
        build_from_docs()
    else:
        build_preset()
