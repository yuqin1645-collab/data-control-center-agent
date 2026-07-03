"""SAG: SQL-Retrieval Augmented Generation with query-time dynamic hyperedges.

核心思想:
1. 先用 Text-to-SQL 检索出基础结果行
2. 从结果行**查询时动态**构建超图 (hypergraph):
   - 节点 = 行中的实体值 (如 customer_id='C001', product_id='P005', region='华东')
   - 超边 = 每一行构成一条 hyperedge, 连接该行所有实体值
     (一行同时含 customer+product+region, 这是天然的多元关系, 比两两 pairwise 更准)
   - 另加"类型超边": 所有 customer 值构成一条, 所有 product 值构成一条
3. 在超图上做多跳扩展, 找到 SQL 直接结果之外的关联实体
4. 把扩展实体的额外信息(更多行、关联文档)拉回来, 增强生成上下文

"动态" = 超图每个查询现构建, 不持久化
"超边" = 一条边可连 2+ 节点, 捕捉多元共现关系
"""
import yaml
from typing import List, Dict, Set, Tuple
from retrieval.text_to_sql.sql_generator import SQLGenerator
from retrieval.sag.hypergraph import HyperGraph

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

CFG = SETTINGS["sag"]

# 实体字段识别: 这些列名视为"实体值"参与超图
ENTITY_COLUMN_HINTS = {
    "customer", "customer_id", "customer_name",
    "product", "product_id", "product_name",
    "region", "area", "dept", "department", "dept_id",
    "employee", "employee_id", "employee_name",
    "supplier", "supplier_id",
    "category", "category_name",
}


def _is_entity_column(col: str) -> bool:
    c = col.lower()
    return any(h in c for h in ENTITY_COLUMN_HINTS)


def _classify_entity(col: str) -> str:
    """从列名推断实体类型."""
    c = col.lower()
    if "customer" in c:
        return "customer"
    if "product" in c:
        return "product"
    if "region" in c or "area" in c:
        return "region"
    if "dept" in c or "department" in c:
        return "department"
    if "employee" in c:
        return "employee"
    if "supplier" in c:
        return "supplier"
    if "category" in c:
        return "category"
    return col.lower()


def build_hypergraph_from_rows(columns: List[str], rows: List[List]) -> HyperGraph:
    """从 SQL 结果行查询时构建超图.

    每行 -> 一条 hyperedge (连接该行所有实体列的值)
    每个实体列 -> 一条类型 hyperedge (连接该列所有值)
    """
    hg = HyperGraph()
    # 找出实体列下标
    entity_cols = [(i, c) for i, c in enumerate(columns) if _is_entity_column(c)]

    # 类型超边: 每个实体列所有值构成一条
    type_edges = {}
    for i, c in entity_cols:
        etype = _classify_entity(c)
        type_edges.setdefault(etype, set())

    for row in rows:
        # 行超边: 该行所有实体值
        row_nodes = set()
        for i, c in entity_cols:
            val = row[i] if i < len(row) else None
            if val is None or val == "":
                continue
            etype = _classify_entity(c)
            node = (etype, str(val))
            row_nodes.add(node)
            type_edges[etype].add(node)
        if len(row_nodes) >= 2:
            hg.add_hyperedge(row_nodes, edge_type="row")

    # 加类型超边
    for etype, nodes in type_edges.items():
        if len(nodes) >= 2:
            hg.add_hyperedge(nodes, edge_type=f"type:{etype}")

    return hg


def expand_entities(hg: HyperGraph, seeds: Set, max_hops: int, max_entities: int) -> Set:
    """在超图上从 seeds 多跳扩展关联实体."""
    visited = set(seeds)
    frontier = set(seeds)
    for hop in range(max_hops):
        if len(visited) >= max_entities:
            break
        next_frontier = set()
        for node in frontier:
            for edge in hg.hyperedges_of(node):
                for nb in edge:
                    if nb not in visited:
                        next_frontier.add(nb)
        if not next_frontier:
            break
        visited |= next_frontier
        if len(visited) >= max_entities:
            visited = set(list(visited)[:max_entities])
            break
        frontier = next_frontier
    return visited - set(seeds), visited
