# 数据中控 Agent — 四项新功能设计规格书

> 日期:2026-07-04
> 项目:data-control-center-agent
> 范围:权限系统 + 前端可视化 + 端到端跑通 + RAGAS 评估

---

## 一、权限系统 (RBAC + 行级权限)

### 1.1 数据模型

新增 SQLite 数据库表(放在 `data/agent_auth.db`):

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,        -- bcrypt 哈希
    dept_id TEXT NOT NULL,              -- 部门标识: SALES / HR / TECH / FINANCE / ADMIN
    role TEXT NOT NULL,                 -- admin / manager / analyst
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

预置用户:
| username | password | dept_id | role |
|----------|----------|---------|------|
| admin | admin123 | ADMIN | admin |
| sales_mgr | sales123 | SALES | manager |
| hr_analyst | hr123 | HR | analyst |

### 1.2 后端模块

**`core/auth.py`**
- `hash_password(pwd)` / `verify_password(pwd, hash)` — bcrypt
- `create_token(user)` — 签发 JWT(exp 24h,payload: user_id, username, dept_id, role)
- `decode_token(token)` — 验证 JWT,返回 user dict 或 raise
- `get_current_user(request)` — FastAPI 依赖,从 Authorization header 提取 JWT

**`core/permissions.py`**
- `PermissionContext(user)` — 封装当前用户的权限上下文
- `get_dept_filter(user)` — 返回 `("dept_id", user.dept_id)` 或 `None`(admin 返回 None,不过滤)
- `can_access_table(user, table_name)` — 表级权限检查(admin 全量,其他只能访问本部门相关表)

**修改 `retrieval/text_to_sql/executor.py`**
- `inject_permission(sql, user)` — 扩展现有方法,从 PermissionContext 获取 dept_id,注入 WHERE 条件
- admin 角色:跳过注入,不加 WHERE
- manager/analyst:注入 `WHERE dept_id = '{user.dept_id}'`

### 1.3 API 端点

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/auth/login | 登录,返回 JWT | 无 |
| GET | /api/auth/me | 当前用户信息 | 必须 |
| POST | /api/auth/register | 注册新用户(仅 admin) | admin |

### 1.4 前端权限交互
- 登录页:用户名 + 密码 → POST /api/auth/login → 存 JWT 到 localStorage
- 每次请求带 `Authorization: Bearer {token}` header
- 侧边栏显示当前用户头像、角色、部门
- admin 角色显示"用户管理"入口;analyst/manager 不显示
- JWT 过期时跳转登录页

---

## 二、前端可视化 (React + shadcn/ui + Tailwind)

### 2.1 技术栈

| 组件 | 选型 | 版本 | 说明 |
|------|------|------|------|
| 框架 | React | 18.x | |
| 构建 | Vite | 5.x | 极速 HMR |
| 语言 | TypeScript | 5.x | 类型安全 |
| UI 组件 | shadcn/ui | latest | ~70k⭐, Radix UI + Tailwind |
| 样式 | Tailwind CSS | 3.x | |
| 图表 | recharts | 2.x | ~23k⭐ React 图表库 |
| 路由 | react-router | 6.x | |
| HTTP | fetch (原生) | | 不额外引依赖 |
| 状态 | React Context + hooks | | 不引 Redux |

### 2.2 后端 API 设计

**`api/main.py`** — FastAPI 应用

| 方法 | 路径 | 说明 | 请求体/参数 | 响应 |
|------|------|------|-------------|------|
| POST | /api/auth/login | 登录 | {username, password} | {token, user} |
| GET | /api/auth/me | 当前用户 | — | {id, username, dept_id, role} |
| POST | /api/query | 提交查询 | {query: string} | {query_id, status} |
| GET | /api/query/{id} | 获取结果 | — | 见下方响应结构 |
| GET | /api/data-sources | 数据源状态 | — | [{name, type, status, stats}] |
| GET | /api/stats | 系统指标 | — | {cache_hit_rate, sql_accuracy, ...} |
| GET | /api/health | 健康检查 | — | {status: "ok"} |

**查询结果响应结构:**
```json
{
  "query_id": "uuid",
  "status": "completed",
  "elapsed_ms": 2300,
  "route": {
    "label": "text_to_sql",
    "reason": "结构化数据查询",
    "subqueries": null
  },
  "cache_hit": false,
  "path_details": {
    "path": "text_to_sql",
    "schema_tables": ["products", "orders", "customers"],
    "sql": "SELECT p.name, SUM(o.amount)...",
    "sql_corrections": 0,
    "row_count": 5,
    "data": [["1", "智能手表 Pro", "128500", "23"], ...]
  },
  "answer": "销售额排名前5的产品如下:..."
}
```

### 2.3 前端项目结构

```
frontend/react/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── components.json              # shadcn/ui 配置
└── src/
    ├── main.tsx
    ├── App.tsx                  # 路由: /login, /, /admin
    ├── lib/
    │   ├── api.ts               # API client (fetch wrapper)
    │   └── auth.ts              # JWT 存取 + auth context
    ├── components/
    │   ├── ui/                  # shadcn/ui 生成的基础组件
    │   │   ├── button.tsx
    │   │   ├── card.tsx
    │   │   ├── input.tsx
    │   │   ├── table.tsx
    │   │   ├── badge.tsx
    │   │   ├── tabs.tsx
    │   │   ├── dialog.tsx
    │   │   ├── skeleton.tsx
    │   │   ├── avatar.tsx
    │   │   └── sonner.tsx       # toast
    │   ├── RouteFlow.tsx        # 路由流程可视化
    │   ├── ChatMessage.tsx      # 对话消息组件
    │   ├── SqlDetail.tsx        # SQL 详情展开
    │   ├── DataTable.tsx        # 数据表格
    │   ├── ResultChart.tsx      # recharts 图表
    │   ├── Sidebar.tsx          # 侧边栏
    │   └── QueryInput.tsx       # 输入框
    └── pages/
        ├── Login.tsx
        ├── Dashboard.tsx        # 主面板
        └── Admin.tsx            # 用户管理(仅 admin)
```

### 2.4 关键页面设计

**登录页:**
- 居中卡片,shadcn/ui Card 组件
- 用户名 + 密码输入,shadcn/ui Input + Button
- 三个快捷登录按钮(admin / sales_mgr / hr_analyst)方便 demo

**主面板(Dashboard):**
- 顶部导航:Logo + 数据源在线状态 + 用户头像
- 左侧边栏:
  - 数据源状态列表(5 个源,绿灯在线)
  - 系统指标(缓存命中率、SQL 准确率、路由准确率,带进度条)
  - 快捷示例问题(点击直接查询)
- 主区域:
  - 路由流程可视化条:查询 → 路由器 → 5 路径(活跃路径高亮) → 回答
  - 对话区:用户消息(右) + AI 回答(左,含路由标签、指标、数据表格)
  - SQL 详情可展开(语法高亮,标注权限注入行)
  - recharts 柱状图/饼图展示 SQL 查询结果数据
- 底部输入框:textarea + 发送按钮

**管理页(仅 admin):**
- 用户列表表格(shadcn/ui Table)
- 添加用户表单
- 角色选择(下拉)

### 2.5 视觉设计规范
- 主题:深色(dark mode 默认)
- 主色:紫色 hsl(262.1 83.3% 57.8%)
- 背景:网格点纹 + 暗色
- 字体:系统默认无衬线
- 动画:消息 slide-in,路由路径 glow 效果,进度条 pulse

---

## 三、端到端跑通

### 3.1 初始化流程

```
scripts/init_db.py          → 建表 + 造数据 + Schema KB
scripts/index_documents.py  → 索引文档到 Chroma
scripts/build_graph.py      → 构建知识图谱
scripts/init_auth.py        → 创建用户表 + 预置用户(新增)
```

### 3.2 自动化 E2E 测试

**`tests/test_e2e.py`**

```python
# 测试用例
TEST_CASES = [
    {"path": "text_to_sql",   "query": "销售额排名前5的产品",  "expect_route": "text_to_sql"},
    {"path": "traditional_rag", "query": "员工报销流程是什么",   "expect_route": "traditional_rag"},
    {"path": "graph_rag",     "query": "张三和李四有什么关系",   "expect_route": "graph_rag"},
    {"path": "wiki_rag",      "query": "什么是机器学习",        "expect_route": "wiki_rag"},
    {"path": "sag",           "query": "客户C001买了什么产品以及相关产品", "expect_route": "sag"},
]

# 每个用例验证:
# 1. 路由标签正确 (expect_route 匹配)
# 2. 返回非空 (answer 非空)
# 3. 无异常 (status == "completed")
# 4. 耗时 < 30s
```

### 3.3 手动验证清单
1. FastAPI 后端启动无报错
2. React 前端 `npm run dev` 启动无报错
3. 登录页能登录,返回 JWT
4. 5 条路径各跑一个查询,前端正确显示结果
5. admin 用户能看到所有部门数据,analyst 只能看到本部门
6. 缓存命中:重复查询第二次秒回
7. SQL 详情可展开,显示权限注入行

---

## 四、RAGAS 评估

### 4.1 测试数据

**`evaluation/ragas_test_data.json`** — ~20 个测试用例

每条路径 4 个问题,每条结构:
```json
{
  "path": "text_to_sql",
  "question": "销售额排名前5的产品",
  "reference_answer": "销售额排名前5的产品是:1.智能手表Pro(¥128,500) 2.无线耳机Air(¥95,200) 3.平板电脑X1(¥82,800) 4.智能音箱Mini(¥67,400) 5.便携充电宝(¥45,600)",
  "reference_context": "products表: id, name, price; orders表: id, product_id, amount, customer_id; customers表: id, name, dept_id"
}
```

路径分布:
- text_to_sql: 4 题(单表查询、多表 JOIN、聚合、排序)
- traditional_rag: 4 题(报销流程、员工手册、产品介绍、请假制度)
- graph_rag: 4 题(人员关系、产品-客户关系、部门关系、多跳推理)
- wiki_rag: 4 题(通用知识:机器学习、深度学习、自然语言处理、知识图谱)
- sag: 4 题(关联扩展:客户购买产品+关联、产品同类扩展等)

### 4.2 评估脚本

**`evaluation/ragas_eval.py`**

依赖: `pip install ragas datasets`

流程:
1. 加载测试数据
2. 对每个问题调用 `agent.ask(query, user=admin_user)` 获取回答
3. 提取 agent 返回的 context(每条路径的检索结果)
4. 用 RAGAS 评估:
   - `faithfulness` — 答案是否忠于检索上下文
   - `answer_relevancy` — 答案是否切题
   - `context_precision` — 检索上下文的精确率
   - `context_recall` — 检索上下文的召回率
5. 按 path 分组计算平均分
6. 输出指标表 + 写入 `evaluation/ragas_results.json`

输出格式:
```
路径               faithfulness  answer_relevancy  context_precision  context_recall
text_to_sql        0.92          0.88              0.85                0.90
traditional_rag    0.89          0.91              0.82                0.88
graph_rag          0.85          0.83              0.78                0.82
wiki_rag           0.90          0.87              0.80                0.85
sag                0.83          0.81              0.76                0.80
-------------------------------------------------------------------
总体平均           0.88          0.86              0.80                0.85
```

### 4.3 RAGAS 配置
- 评估 LLM:使用项目配置的 LLM(百炼/Qwen),通过 ragas 的 `llm` 参数传入 OpenAI-compatible client
- Embedding:使用项目已有的 bge-m3(sentence-transformers)
- 批量评估,每个问题独立打分

---

## 五、实现顺序与依赖

```
1. 权限系统 (core/auth.py + core/permissions.py + scripts/init_auth.py)
   ↓
2. FastAPI 后端 (api/main.py + 路由)
   ↓  (前端需要 API 才能开发)
3. React 前端 (frontend/react/)
   ↓
4. 端到端跑通 (tests/test_e2e.py + 手动验证)
   ↓  (RAGAS 需要系统跑通才能评估)
5. RAGAS 评估 (evaluation/ragas_eval.py + ragas_test_data.json)
```

## 六、依赖新增

**Python:**
- `fastapi` — Web 框架
- `uvicorn` — ASGI server
- `python-jose[cryptography]` — JWT
- `passlib[bcrypt]` — 密码哈希
- `python-multipart` — FastAPI 表单
- `ragas` — RAG 评估
- `datasets` — ragas 依赖

**Node.js / 前端:**
- react, react-dom, react-router-dom
- vite, @vitejs/plugin-react
- typescript
- tailwindcss, postcss, autoprefixer
- recharts
- shadcn/ui 组件(通过 CLI 按需生成)
- lucide-react(图标)

## 七、文件变更清单

**新增文件:**
- `core/auth.py`
- `core/permissions.py`
- `api/__init__.py`
- `api/main.py`
- `api/routes/__init__.py`
- `api/routes/auth.py`
- `api/routes/query.py`
- `api/routes/system.py`
- `scripts/init_auth.py`
- `tests/__init__.py`
- `tests/test_e2e.py`
- `evaluation/ragas_eval.py`
- `evaluation/ragas_test_data.json`
- `frontend/react/` (整个 React 项目)

**修改文件:**
- `retrieval/text_to_sql/executor.py` — inject_permission 接收 user 对象
- `agent.py` — ask() 方法接收 user 参数
- `requirements.txt` — 新增 fastapi/uvicorn/jose/passlib/ragas/datasets
- `config/settings.yaml` — 新增 auth 配置段
- `README.md` — 更新项目结构和新功能说明
