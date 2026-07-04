# 数据中控 Agent — 快速启动指南

## 一、环境准备

### Python 后端
```bash
cd data-control-center-agent
pip install -r requirements.txt
```

### 配置 LLM
编辑 `.env` 文件，填入你的百炼 API Key：
```
LLM_API_KEY=sk-your-actual-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
```

### React 前端
```bash
cd frontend/react
npm install
```

## 二、初始化数据

```bash
cd data-control-center-agent

# 1. 创建样本数据库 + Schema 知识库
PYTHONPATH=. python scripts/init_db.py

# 2. 创建认证数据库 + 预置用户
PYTHONPATH=. python scripts/init_auth.py

# 3. 索引文档到向量库
PYTHONPATH=. python scripts/index_documents.py

# 4. 构建知识图谱
PYTHONPATH=. python scripts/build_graph.py
```

## 三、启动服务

### 后端 API
```bash
cd data-control-center-agent
PYTHONPATH=. python -m uvicorn api.main:app --reload --port 8000
```

### 前端
```bash
cd frontend/react
npm run dev
```
打开 http://localhost:3000

## 四、登录

| 用户名 | 密码 | 角色 | 部门 |
|--------|------|------|------|
| admin | admin123 | 管理员 | 全部门 |
| sales_mgr | sales123 | 经理 | 销售部 |
| hr_analyst | hr123 | 分析师 | HR部 |

## 五、测试

### 端到端测试
```bash
cd data-control-center-agent
PYTHONPATH=. python -m tests.test_e2e
```

### RAGAS 评估
```bash
cd data-control-center-agent
PYTHONPATH=. python evaluation/ragas_eval.py
```
