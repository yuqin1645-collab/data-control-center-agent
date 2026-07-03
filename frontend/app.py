"""Streamlit 前端: 数据中控 Agent demo."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

# 检查依赖
try:
    from agent import DataControlCenterAgent
except Exception as e:
    st.error(f"Agent 加载失败: {e}")
    st.info("请先运行: pip install -r requirements.txt")
    st.stop()


st.set_page_config(page_title="数据中控 Agent", page_icon=":brain:", layout="wide")
st.title("数据中控 Agent")
st.caption("自然语言一键查询企业数据: SQL / 文档 / 知识图谱 / Wiki / 超图扩展")

# 初始化 agent (缓存到 session)
@st.cache_resource
def get_agent():
    return DataControlCenterAgent()

agent = get_agent()

# 侧边栏: 状态
with st.sidebar:
    st.header("系统状态")
    try:
        from retrieval.text_to_sql.schema_kb import SchemaKB
        SchemaKB.get()
        st.success("Schema 知识库 ✓")
    except Exception:
        st.warning("Schema 知识库未构建")
    try:
        from retrieval.graph_rag.graph_builder import load_graph, graph_stats
        G = load_graph()
        stats = graph_stats(G)
        st.success(f"知识图谱 ✓ ({stats['nodes']} 节点 / {stats['edges']} 边)")
    except Exception:
        st.warning("知识图谱未构建")
    st.divider()
    st.header("示例问题")
    examples = [
        "上个月华东区销售额是多少",
        "公司报销流程是什么",
        "张三和李四之间有什么业务关联",
        "端午节是哪天有什么习俗",
        "客户 C001 买了哪些产品,这些产品的同类产品还有谁在买",
        "华东区退货率多少,退货流程是什么",
    ]
    for ex in examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state["query_input"] = ex

# 主区域
query = st.text_input("请输入问题:", value=st.session_state.get("query_input", ""),
                      placeholder="例如: 上个月华东区销售额是多少")

if st.button("查询", type="primary") and query:
    with st.spinner("Agent 思考中..."):
        try:
            res = agent.ask(query)
        except Exception as e:
            st.error(f"执行失败: {e}")
            st.stop()

    # 路由信息
    route = res.get("route", {})
    col1, col2, col3 = st.columns(3)
    col1.metric("检索路径", route.get("label", "?"))
    col2.metric("耗时", f"{res['latency']}s")
    col3.metric("缓存命中", "是" if res.get("cached") else "否")
    if route.get("reason"):
        st.caption(f"路由理由: {route['reason']}")

    # 回答
    st.subheader("回答")
    st.write(res["answer"])

    # 各路径结果详情
    if res.get("path_results"):
        st.subheader("检索详情")
        for pr in res["path_results"]:
            with st.expander(f"[{pr['path']}] {pr['query']}" + (f"  ❌ {pr['error']}" if pr["error"] else "  ✓")):
                if pr["error"]:
                    st.error(pr["error"])
                    continue
                raw = pr["result"].get("raw") if pr["result"] else None
                if raw is None:
                    st.write(pr["result"].get("context", "(空)"))
                    continue

                # 按路径类型展示
                if pr["path"] == "text_to_sql":
                    st.code(raw.get("sql", ""), language="sql")
                    if raw.get("columns"):
                        df = pd.DataFrame(raw["rows"], columns=raw["columns"])
                        st.dataframe(df, use_container_width=True)
                        st.caption(f"共 {raw.get('row_count', len(raw.get('rows', [])))} 行, 重试 {raw.get('attempts', '?')} 次")

                elif pr["path"] == "traditional_rag":
                    for i, chunk in enumerate(raw.get("chunks", [])):
                        st.text(f"--- chunk {i+1} ---")
                        st.write(chunk)
                    st.caption(f"来源: {raw.get('sources', [])}")

                elif pr["path"] == "graph_rag":
                    st.write("种子实体:", raw.get("seeds", []))
                    edges = raw.get("edges", [])
                    if edges:
                        edge_df = pd.DataFrame(edges)
                        st.dataframe(edge_df, use_container_width=True)
                    st.caption(f"子图: {raw.get('nodes', [])[:20]}")

                elif pr["path"] == "wiki_rag":
                    for p in raw.get("passages", []):
                        st.write(p)

                elif pr["path"] == "sag":
                    st.code(raw.get("sql", ""), language="sql")
                    st.write("基础结果:")
                    if raw.get("columns"):
                        df = pd.DataFrame(raw.get("base_rows", []), columns=raw["columns"])
                        st.dataframe(df, use_container_width=True)
                    st.write("超图统计:", raw.get("hypergraph_stats", {}))
                    st.write("种子实体:", raw.get("seeds", [])[:10])
                    st.write("扩展实体:", raw.get("expanded", [])[:10])
