"""图构建: 三元组 -> networkx Graph -> pickle 持久化."""
import os
import pickle
from typing import List, Tuple
import networkx as nx


GRAPH_PATH = "data/graph.pkl"


def build_graph(triples: List[Tuple[str, str, str]], path: str = GRAPH_PATH) -> nx.Graph:
    """从三元组构建无向图."""
    G = nx.Graph()
    for h, r, t in triples:
        G.add_node(h)
        G.add_node(t)
        G.add_edge(h, t, relation=r)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(G, f)
    return G


def load_graph(path: str = GRAPH_PATH) -> nx.Graph:
    """加载图, 不存在返回空图."""
    if not os.path.exists(path):
        return nx.Graph()
    with open(path, "rb") as f:
        return pickle.load(f)


def graph_stats(G: nx.Graph) -> dict:
    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
    }
