# 数据中控 Agent (Data Control Center Agent)

企业内部统一的**数据访问与分析智能体**。用户用自然语言提问,Agent 自动判断意图,路由到对应的检索路径(Text-to-SQL / 传统 RAG / GraphRAG / Wiki RAG / SAG),执行查询、聚合结果、生成图表与洞察。

> 这不是 5 个 RAG 的简单堆砌,核心是**意图路由层**——它决定一个问题该走哪条路径,以及混合查询时如何多路编排。这是"中控"区别于"单 RAG 工具箱"的关键。

## 架构

```
                    ┌─────────────────────┐
                    │   用户自然语言提问   │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  交互层 (多轮/指代)  │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  意图路由层 (Planner)│  ← 中控大脑
                    └──────────┬──────────┘
                               ▼
        ┌────────────┬─────────┼─────────┬────────────┐
        ▼            ▼         ▼         ▼            ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Text2SQL │ │ 传统RAG │ │GraphRAG │ │Wiki RAG │ │  SAG    │
   │结构化   │ │ 文档    │ │ 知识图  │ │ 外部知识│ │SQL+超图 │
   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
        └────────────┴─────────┼─────────┴────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  执行编排+结果聚合  │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │  LLM 综合生成回答   │  + 图表 + 引用
                    └─────────────────────┘
```

## 5 条检索路径

| 路径 | 解决什么 | 技术要点 |
|------|----------|----------|
| **Text-to-SQL** | 结构化数据库查询 | Schema RAG(只检索相关表 schema)+ SQL 自纠错(语法/字段校验+失败回传重试) |
| **传统 RAG** | 文档资料问答 | 分块 + bge-m3 向量检索 + rerank 精排 |
| **GraphRAG** | 多跳关系推理 | 实体/关系抽取 → 知识图谱 → 子图检索,擅长"A 和 B 之间有什么联系" |
| **Wiki RAG** | 外部通用知识 | Wikipedia API 检索,补足公司知识库盲区 |
| **SAG** | SQL 结果的关联扩展 | SQL 检索 + 查询时动态构建超图(hyperedge 连接同行多实体),做多跳关联扩展 |

## 快速开始

```bash
git clone https://github.com/<你的用户名>/data-control-center-agent.git
cd data-control-center-agent
pip install -r requirements.txt

# 配置 LLM API (OpenAI 兼容协议,支持 Qwen/Deepseek/OpenAI)
cp .env.example .env
# 编辑 .env 填入 API key 和 base_url

# 初始化样本数据
python scripts/init_db.py        # 建样本 SQLite 数据库
python scripts/index_documents.py  # 索引样本文档

# 启动
streamlit run frontend/app.py
```

## 技术栈

- **LLM**: OpenAI 兼容协议(支持 Qwen / Deepseek / OpenAI)
- **向量库**: ChromaDB(演示) / Milvus(生产可切换)
- **图存储**: networkx(演示) / Neo4j(生产可切换)
- **数据库**: SQLite(演示,可切 PostgreSQL/MySQL)
- **缓存**: Redis(结果缓存 + 语义去重)
- **外部知识**: Wikipedia API
- **前端**: Streamlit

## 项目结构

```
data-control-center-agent/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.yaml          # 全局配置
│   └── data_sources.yaml      # 数据源 MCP 风格配置
├── core/
│   ├── llm.py                 # LLM 封装
│   ├── cache.py               # Redis 缓存 + 语义去重
│   ├── router.py              # 意图路由
│   └── orchestrator.py        # 执行编排
├── retrieval/
│   ├── base.py
│   ├── text_to_sql/           # Schema RAG + SQL 自纠错
│   ├── traditional_rag/       # 文档向量检索
│   ├── graph_rag/             # 知识图谱
│   ├── wiki_rag/              # Wikipedia
│   └── sag/                   # SQL + 动态超图
├── frontend/
│   └── app.py                 # Streamlit
├── scripts/
│   ├── init_db.py
│   └── index_documents.py
├── evaluation/
│   └── eval.py
└── data/
```

## 核心设计亮点

1. **Schema-Aware Text-to-SQL**:不把全库 schema 塞给 LLM,先 embedding 检索相关表,只给相关 schema,token 降 80%
2. **SQL 自纠错链路**:生成→语法校验→字段校验→执行→失败回传 LLM 重试,最多 3 次
3. **意图路由**:不是所有问题都走 SQL,文档走 RAG、外部走 Wiki、关系推理走 GraphRAG,混合查询多路编排
4. **SAG 动态超图**:查询时从 SQL 结果提取实体,同行多值构成一条 hyperedge,做多跳关联扩展
5. **结果缓存 + 语义去重**:Redis 缓存,embedding 相似度 > 0.92 命中缓存
6. **熔断器 + 指数退避**:多源调用稳定性保障

## 评估

```bash
python evaluation/eval.py
```

指标:路由准确率、各路径召回率、端到端回答准确率(对比标注答案)。

## License

MIT
