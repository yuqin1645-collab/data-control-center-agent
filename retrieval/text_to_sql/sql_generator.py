"""Text-to-SQL 生成 + 自纠错链路.

流程: 问题 + schema -> LLM 生成 SQL -> 语法校验 -> 字段校验 -> 执行
       -> 失败则错误回传 LLM 重试, 最多 max_retries 次
"""
import yaml
from core.llm import LLMClient
from retrieval.text_to_sql.schema_kb import SchemaKB
from retrieval.text_to_sql.executor import SQLExecutor

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

CFG = SETTINGS["text_to_sql"]


def _format_schema_for_prompt(tables: list) -> str:
    """把检索到的表 schema 拼成 prompt 文本."""
    lines = []
    for t in tables:
        if not t["schema"]:
            lines.append(t["description"])
            continue
        cols = ", ".join(f"{c['name']} {c['type']}" for c in t["schema"]["columns"])
        sample = ""
        if t["schema"]["sample_rows"]:
            sample = " 示例: " + str(t["schema"]["sample_rows"][:2])
        lines.append(f"表 {t['table']} (字段: {cols}){sample}")
    return "\n".join(lines)


class SQLGenerator:
    """Text-to-SQL 生成器, 带自纠错."""

    def __init__(self):
        self.llm = LLMClient.get()
        self.schema_kb = SchemaKB.get()
        self.executor = SQLExecutor()
        self.max_retries = CFG["max_retries"]

    def _generate_sql(self, query: str, schema_text: str, error: str = None, prev_sql: str = None) -> str:
        """调用 LLM 生成 SQL. error 非空时为纠错模式."""
        if error:
            prompt = f"""你是 SQL 专家. 你之前生成的 SQL 执行失败了, 请根据错误修正.

表结构:
{schema_text}

问题: {query}
上次生成的 SQL: {prev_sql}
错误信息: {error}

只输出修正后的 SQLite SQL, 不要解释, 不要 markdown 代码块."""
        else:
            prompt = f"""你是 SQL 专家. 根据表结构把问题翻译成 SQLite SQL.

表结构:
{schema_text}

问题: {query}

要求:
1. 只输出 SQL, 不要解释, 不要 markdown 代码块
2. 只用上面给出的表和字段, 不要编造
3. 用 SQLite 方言
4. 只读 SELECT, 禁止 DROP/DELETE/UPDATE"""
        messages = [{"role": "user", "content": prompt}]
        sql = self.llm.chat(messages, temperature=0.0, max_tokens=512)
        # 去掉 markdown 代码块
        sql = sql.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1] if "\n" in sql else sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()
        return sql

    def generate_and_execute(self, query: str) -> dict:
        """完整链路: schema 检索 -> 生成 -> 校验 -> 执行 -> 自纠错."""
        # 1. 检索相关 schema
        tables = self.schema_kb.retrieve(query)
        if not tables:
            return {"sql": None, "result": None, "error": "无可用 schema", "tables": []}
        schema_text = _format_schema_for_prompt(tables)

        # 2. 自纠错循环
        sql = None
        error = None
        for attempt in range(self.max_retries):
            sql = self._generate_sql(query, schema_text, error=error, prev_sql=sql)
            # 3. 校验 + 执行
            res = self.executor.execute(sql)
            if res["error"] is None:
                return {
                    "sql": sql,
                    "result": res,
                    "error": None,
                    "tables": [f"{t['source']}.{t['table']}" for t in tables],
                    "attempts": attempt + 1,
                }
            error = res["error"]
        # 全部失败
        return {
            "sql": sql,
            "result": None,
            "error": f"自纠错 {self.max_retries} 次仍失败: {error}",
            "tables": [f"{t['source']}.{t['table']}" for t in tables],
            "attempts": self.max_retries,
        }
