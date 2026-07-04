"""SQL 执行器: 执行 + 行级权限注入."""
import sqlite3
import sqlparse
from typing import Optional, Tuple, Dict


class SQLExecutor:
    """SQL 执行, 带语法校验和行级权限注入."""

    def __init__(self, db_path: str = "data/sample_db.sqlite"):
        self.db_path = db_path

    def validate(self, sql: str) -> Tuple[bool, str]:
        """语法校验 + 只允许 SELECT."""
        try:
            parsed = sqlparse.parse(sql)
            if not parsed:
                return False, "空 SQL"
            stmt = parsed[0]
            # 只允许 SELECT, 防注入
            first_token = stmt.token_first(skip_ws=True, skip_cm=True)
            if first_token is None:
                return False, "空语句"
            if first_token.value.upper() != "SELECT":
                return False, f"只允许 SELECT, 检测到 {first_token.value}"
            # 禁止危险关键字 (token 级匹配, 避免误伤 description/update_time 等列名)
            upper = sql.upper()
            import re
            for kw in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "ATTACH", "PRAGMA"]:
                # 用单词边界匹配, 不匹配子串
                if re.search(r"\b" + kw + r"\b", upper):
                    return False, f"禁用关键字: {kw}"
            return True, "ok"
        except Exception as e:
            return False, f"语法错误: {e}"

    def inject_permission(self, sql: str, user: Optional[Dict] = None) -> str:
        """行级权限: 在 WHERE 注入部门过滤.

        user: {"dept_id": "SALES", "role": "manager", ...}
        admin 角色: 不注入 (全量访问)
        manager/analyst: 注入 WHERE dept_id = '{dept_id}'
        """
        if not user:
            return sql
        role = user.get("role", "")
        if role == "admin":
            return sql  # 管理员不过滤
        dept_id = user.get("dept_id")
        if not dept_id:
            return sql

        if "WHERE" in sql.upper():
            # 简单拼到现有 WHERE 后
            idx = sql.upper().find("WHERE") + 6
            return sql[:idx] + f" dept_id = '{dept_id}' AND" + sql[idx:]
        if "GROUP BY" in sql.upper():
            return sql.replace("GROUP BY", f"WHERE dept_id = '{dept_id}' GROUP BY", 1)
        if "ORDER BY" in sql.upper():
            return sql.replace("ORDER BY", f"WHERE dept_id = '{dept_id}' ORDER BY", 1)
        return sql + f" WHERE dept_id = '{dept_id}'"

    def execute(self, sql: str, user: Optional[Dict] = None) -> dict:
        """执行 SQL, 返回 {"columns":..., "rows":..., "error":...}.

        user: 当前用户 dict, 用于行级权限注入.
        """
        ok, msg = self.validate(sql)
        if not ok:
            return {"columns": [], "rows": [], "error": msg}
        sql = self.inject_permission(sql, user)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [d[0] for d in cur.description] if cur.description else []
            return {"columns": columns, "rows": [list(r) for r in rows], "error": None}
        except Exception as e:
            return {"columns": [], "rows": [], "error": str(e)}
        finally:
            conn.close()
