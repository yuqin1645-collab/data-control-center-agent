# 快速上手 & 推送 GitHub

## 1. 安装依赖
```bash
cd data-control-center-agent
pip install -r requirements.txt
```

## 2. 配置 LLM
```bash
cp .env.example .env
# 编辑 .env, 填入:
# LLM_API_KEY=sk-xxx (DashScope/Deepseek/OpenAI 任一)
# LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  (Qwen)
# LLM_MODEL=qwen2.5-7b-instruct
```

支持的平台(任选一个,都用 OpenAI 兼容协议):

| 平台 | base_url | model 示例 |
|------|----------|-----------|
| 阿里 Qwen DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen2.5-7b-instruct` |
| Deepseek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| 本地 vLLM | `http://localhost:8000/v1` | `Qwen2.5-7B-Instruct` |

## 3. 初始化样本数据
```bash
python scripts/init_db.py           # 建 SQLite + schema 知识库
python scripts/index_documents.py   # 建样本文档 + 索引到 Chroma
python scripts/build_graph.py       # 建知识图谱 (加 --extract 用 LLM 抽取, 慢)
```

## 4. 启动
```bash
# 命令行测试
python agent.py "上个月华东区销售额是多少"

# Streamlit 前端
streamlit run frontend/app.py
```

## 5. 评估
```bash
python evaluation/eval.py --router-only   # 只测路由准确率
python evaluation/eval.py                  # 全量端到端
```

## 6. 推送到 GitHub
```bash
# 6.1 在 GitHub 网页上手动创建空仓库 (不要勾 README/.gitignore/license):
#     仓库名: data-control-center-agent

# 6.2 本地初始化并推送
git init
git add .
git commit -m "feat: 数据中控 Agent - 5路检索 (Text-to-SQL/传统RAG/GraphRAG/Wiki/SAG)"
git branch -M main
git remote add origin https://github.com/<你的用户名>/data-control-center-agent.git
git push -u origin main
```

## 常见问题

**Q: `sentence-transformers` 下载 bge-m3 模型慢?**
设镜像: `export HF_ENDPOINT=https://hf-mirror.com` 后重跑。或改 `.env` 的 `EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5`(更小更快)。

**Q: Wikipedia 检索超时?**
Wiki RAG 路径对网络敏感。可在 `config/settings.yaml` 把 `wiki_rag.max_results` 改小,或路由时少走 wiki。

**Q: 没有 GPU 跑不动?**
本项目只用 API 调用 LLM,不本地推理,普通笔记本 CPU 即可。embedding 模型本地跑(bge-m3 ~2GB 内存)。

**Q: Chroma 报错?**
删 `data/chroma/` 目录后重跑 `scripts/init_db.py` 和 `scripts/index_documents.py`。
