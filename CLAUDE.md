# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

数据中控 Agent (Data Control Center Agent) — an enterprise data-access agent. Users ask natural-language questions; the agent decides intent, routes to one of five retrieval paths, executes, and synthesizes an answer with citations/charts. The codebase is written in Chinese (comments, prompts, docs); keep that convention.

The defining feature is the **intent routing layer** (now an LLM Agent Loop with function-calling, not a rule router) — this is what distinguishes "中控" from a "single-RAG toolbox".

## Architecture

Request flow (top-down):

1. **FastAPI** (`api/main.py` + `api/routes/`) — HTTP layer. `query.py` exposes sync `POST /api/query` and SSE `POST /api/query/stream`. Auth via JWT in `api/deps.py` → `core/auth.py`. Conversations persisted in `core/conversations.py`.
2. **Agent loop** (`agent.py`) — the brain. Modeled on Claude Code's `query.ts` `while-true`: LLM gets the question + tool schemas → either calls a tool (append result, loop) or returns the answer. Capped at `MAX_ITERATIONS = 5`.
   - **Hybrid routing**: a keyword fast-path (`KEYWORD_ROUTES` / `_fast_route`) bypasses the LLM tool-selection call for obvious queries (~1.5s saved); everything else goes through the full Agent Loop where the LLM picks tools itself.
   - **Two-model split**: `ROUTE_MODEL = "qwen-turbo"` for fast tool-selection / SQL generation, default `qwen-plus` for final answer generation. Override per-call via `model=` on `LLMClient`.
3. **Tool registry** (`core/tool_registry.py` + `core/tools.py`) — the 5 retrieval paths wrapped as OpenAI function-calling tools (`query_sql`, `search_documents`, `query_graph`, `search_wiki`, **`query_sag`**). Each tool delegates to `Orchestrator.execute_path(path_name, query, user)`. Adding a retrieval path = add one `Tool` subclass + one `_instantiate` branch.
4. **Orchestrator** (`core/orchestrator.py`) — lazy-loads retrievers, wraps each call in a `CircuitBreaker` + `with_retry` (exponential backoff + jitter). `execute_path` returns `{path, query, result, error}`.
5. **Retrievers** (`retrieval/`) — each implements `BaseRetriever.retrieve(query, user) -> {context, raw, meta}`. The 5 paths:
   - `text_to_sql/` — **Schema-Aware**: `schema_kb` embeds table schemas, retrieves only the relevant ones (token ↓ ~80%), then `sql_generator` runs a self-correction loop (generate → syntax/field validate → execute → feed error back to LLM, max `max_retries`).
   - `traditional_rag/` — chunk + bge-m3 vector retrieve + rerank.
   - `graph_rag/` — entity/relation extraction → networkx graph → subgraph retrieval (multi-hop).
   - `wiki_rag/` — Wikipedia API.
   - `sag/` — SQL retrieve + dynamic hypergraph (one hyperedge per row's multi-values) for multi-hop entity expansion.
6. **Cross-cutting**: `core/cache.py` (Redis or in-memory, semantic-dedup cache, sim threshold 0.92), `core/compact.py` (conversation history compaction), `core/permissions.py` (RBAC + row-level dept filter), `core/llm.py` (OpenAI-compatible client, supports Qwen/Deepseek/OpenAI/vLLM).

Config is YAML-driven: `config/settings.yaml` (all tunable params per path) and `config/data_sources.yaml`. Several modules read `settings.yaml` at import time (`core/orchestrator.py`, `retrieval/text_to_sql/sql_generator.py`) — **run from the project root** so the `config/` relative path resolves.

Singletons (`LLMClient.get()`, `ToolRegistry.get()`, `Orchestrator.get()`, `EmbeddingCache.get_instance()`, `ContextCompactor.get()`) are used throughout — call the `.get()` classmethod, don't instantiate directly.

## Commands

All commands run from the project root (`data-control-center-agent/`). Use `PYTHONPATH=.` for scripts that import `core`/`retrieval`/`agent`.

### Setup
```bash
pip install -r requirements.txt          # full; or requirements_minimal.txt for a lean install
cp .env.example .env                     # then fill LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
```

### Initialize data (run once, in order)
```bash
PYTHONPATH=. python scripts/init_db.py           # sample SQLite db + schema KB
PYTHONPATH=. python scripts/init_auth.py         # auth db + preset users
PYTHONPATH=. python scripts/index_documents.py   # index docs into Chroma
PYTHONPATH=. python scripts/build_graph.py       # build knowledge graph → data/graph.pkl
```

### Run
```bash
# Backend API (FastAPI, port 8000) — preloads all retrievers on startup to avoid 25s cold-start
PYTHONPATH=. python -m uvicorn api.main:app --reload --port 8000

# Frontend (React/Vite, port 3000)
cd frontend/react && npm install && npm run dev

# CLI one-shot query (no server needed)
PYTHONPATH=. python agent.py "上个月华东区销售额是多少"

# Windows one-shot launcher (starts both backend + frontend)
start.bat
```

### Test & evaluate
```bash
PYTHONPATH=. python -m tests.test_e2e            # end-to-end across all 5 paths (also: pytest tests/test_e2e.py -v)
PYTHONPATH=. python evaluation/eval.py           # route accuracy / recall / answer accuracy
PYTHONPATH=. python evaluation/ragas_eval.py     # RAGAS metrics
```

## Conventions

- **Language**: code comments, LLM prompts, log strings, and user-facing text are in Chinese. Match this when editing.
- **Tool results**: `core/tools._format_result` flattens `raw` fields (sql, rows, columns, edges, chunks…) to the top level so the frontend's `path_details` can access `pathDetails.sql` directly. Preserve this contract when adding fields.
- **Row-level security**: every retriever receives `user` (from JWT) and must apply dept filtering via `core/permissions.PermissionContext`. Don't bypass by passing `user=None` in production paths.
- **Demo vs production backends**: ChromaDB / networkx / SQLite / in-memory cache are the demo defaults; Milvus / Neo4j / PostgreSQL / Redis are switchable via `.env` flags (`VECTOR_STORE`, `GRAPH_STORE`, `REDIS_URL`). Don't hardcode the demo backend inside retrievers.

## Preset login users (demo)

| username | password | role | dept |
|----------|----------|------|------|
| admin | admin123 | admin | 全部门 |
| sales_mgr | sales123 | manager | 销售部 |
| hr_analyst | hr123 | analyst | HR部 |

## Known gotchas

- `config/settings.yaml` is opened with a **relative path** at module import time in `core/orchestrator.py` and `retrieval/text_to_sql/sql_generator.py`. Always run with cwd = project root (or `PYTHONPATH=.` from root).
- `.bashrc` on this machine emits a stray `export` parse error on shell startup; it's harmless but appears as the first line of every Bash command output.
- `data/` contents (chroma, graph.pkl, sample_db.sqlite, documents) are gitignored and regenerated by the `scripts/` initializers.
