"""GraphRAG 检索路径: 种子实体 -> BFS 子图 -> 文本化上下文."""
import yaml
import networkx as nx
from retrieval.base import BaseRetriever
from retrieval.graph_rag.extractor import extract_entities_from_query
from retrieval.graph_rag.graph_builder import load_graph

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

CFG = SETTINGS["graph_rag"]


def _subgraph_to_text(subgraph: nx.Graph, seeds: list) -> str:
    """把子图文本化为可喂 LLM 的上下文."""
    if subgraph.number_of_nodes() == 0:
        return ""
    lines = []
    for u, v, data in subgraph.edges(data=True):
        rel = data.get("relation", "关联")
        lines.append(f"{u} --[{rel}]--> {v}")
    return "\n".join(lines)


class GraphRAGRetriever(BaseRetriever):
    path_name = "graph_rag"

    def __init__(self):
        self.G = load_graph()
        self.max_hops = CFG["max_hops"]
        self.max_nodes = CFG["max_nodes"]

    def retrieve(self, query: str, user: dict = None) -> dict:
        if self.G.number_of_nodes() == 0:
            return {"context": "(知识图谱为空, 请先运行 scripts/build_graph.py)",
                    "raw": None, "meta": {"path": self.path_name}}

        # 1. 从问题抽种子实体
        seeds = extract_entities_from_query(query)
        # 也用问题中的原词做兜底匹配
        for w in query.replace(",", " ").replace("?", " ").split():
            if w in self.G:
                seeds.append(w)

        # 图里不存在的种子过滤掉, 做模糊匹配
        matched_seeds = []
        for s in seeds:
            if s in self.G:
                matched_seeds.append(s)
            else:
                # 模糊匹配: 包含关系
                for node in self.G.nodes:
                    if s in node or node in s:
                        matched_seeds.append(node)
                        break

        if not matched_seeds:
            return {"context": f"(图中未找到相关实体, 抽取的种子: {seeds})",
                    "raw": None, "meta": {"path": self.path_name, "seeds": seeds}}

        # 2. BFS 取子图
        visited = set()
        frontier = list(set(matched_seeds))
        for hop in range(self.max_hops):
            if len(visited) >= self.max_nodes:
                break
            next_frontier = []
            for node in frontier:
                if node in visited or len(visited) >= self.max_nodes:
                    break
                visited.add(node)
                for nb in self.G.neighbors(node):
                    if nb not in visited:
                        next_frontier.append(nb)
            frontier = next_frontier
            if not frontier:
                break

        # 超限裁剪
        if len(visited) > self.max_nodes:
            visited = set(list(visited)[:self.max_nodes])

        sub = self.G.subgraph(visited).copy()
        context = _subgraph_to_text(sub, matched_seeds)
        return {
            "context": f"种子实体: {matched_seeds}\n关联子图:\n{context}",
            "raw": {
                "seeds": matched_seeds,
                "nodes": list(sub.nodes),
                "edges": [{"u": u, "v": v, "relation": d.get("relation", "")}
                          for u, v, d in sub.edges(data=True)],
            },
            "meta": {"path": self.path_name, "subgraph_nodes": sub.number_of_nodes(),
                     "subgraph_edges": sub.number_of_edges()},
        }
