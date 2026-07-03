"""超图 (HyperGraph) 数据结构.

- 节点 = (entity_type, value) 元组
- 超边 = 一组节点 (set), 可连接 2+ 节点
- 查询时动态构建, 不持久化

区别于普通图: 一条超边可同时连接多个节点,
捕捉"一行数据中 customer+product+region 共现"这种多元关系.
"""
from typing import Set, Tuple, List


class HyperEdge:
    def __init__(self, nodes: Set[Tuple[str, str]], edge_type: str = "default"):
        self.nodes = set(nodes)
        self.edge_type = edge_type

    def __len__(self):
        return len(self.nodes)

    def __iter__(self):
        return iter(self.nodes)

    def __contains__(self, node):
        return node in self.nodes

    def __repr__(self):
        return f"HyperEdge({self.edge_type}, {self.nodes})"


class HyperGraph:
    def __init__(self):
        self._edges: List[HyperEdge] = []
        self._node_edges: dict = {}  # node -> list of edge indices

    def add_hyperedge(self, nodes: Set[Tuple[str, str]], edge_type: str = "default"):
        """添加一条超边. nodes 是 (entity_type, value) 元组集合."""
        if len(nodes) < 2:
            return
        idx = len(self._edges)
        self._edges.append(HyperEdge(nodes, edge_type))
        for n in nodes:
            self._node_edges.setdefault(n, []).append(idx)

    def hyperedges_of(self, node) -> List[HyperEdge]:
        """返回包含某节点的所有超边."""
        return [self._edges[i] for i in self._node_edges.get(node, [])]

    def neighbors(self, node) -> Set:
        """返回与某节点通过任一超边相连的所有其他节点."""
        result = set()
        for edge in self.hyperedges_of(node):
            result |= edge.nodes
        result.discard(node)
        return result

    @property
    def num_nodes(self):
        return len(self._node_edges)

    @property
    def num_edges(self):
        return len(self._edges)

    def stats(self) -> dict:
        type_counts = {}
        for e in self._edges:
            type_counts[e.edge_type] = type_counts.get(e.edge_type, 0) + 1
        return {
            "nodes": self.num_nodes,
            "edges": self.num_edges,
            "edge_types": type_counts,
        }
