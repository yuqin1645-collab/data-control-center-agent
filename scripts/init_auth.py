"""初始化认证数据库: 建表 + 预置用户."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import os
from core.auth import hash_password

AUTH_DB_PATH = "data/agent_auth.db"


def init_auth_db():
    """创建用户表 + 预置 3 个用户."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(AUTH_DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            dept_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 预置用户
    preset_users = [
        ("admin", "admin123", "ADMIN", "admin"),
        ("sales_mgr", "sales123", "SALES", "manager"),
        ("hr_analyst", "hr123", "HR", "analyst"),
    ]

    for username, password, dept_id, role in preset_users:
        # 检查是否已存在
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            print(f"  用户 {username} 已存在, 跳过")
            continue
        cur.execute(
            "INSERT INTO users (username, password_hash, dept_id, role) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), dept_id, role),
        )
        print(f"  创建用户: {username} ({role}, 部门={dept_id})")

    conn.commit()
    conn.close()
    print(f"\n认证数据库初始化完成: {AUTH_DB_PATH}")
    print("预置用户:")
    print("  admin / admin123     (管理员, 全部门访问)")
    print("  sales_mgr / sales123 (销售部经理, 本部门)")
    print("  hr_analyst / hr123   (HR分析师, 本部门)")


if __name__ == "__main__":
    init_auth_db()
