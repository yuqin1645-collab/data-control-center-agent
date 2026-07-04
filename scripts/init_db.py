"""初始化样本 SQLite 数据库: 销售 + HR 表.
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

造测试数据, 让 Text-to-SQL 和 SAG 路径能跑通.
"""
import os
import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "data/sample_db.sqlite"


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ---- 建表 ----
    cur.executescript("""
    CREATE TABLE customers (
        customer_id TEXT PRIMARY KEY,
        customer_name TEXT,
        region TEXT,
        level TEXT,
        created_at TEXT
    );
    CREATE TABLE products (
        product_id TEXT PRIMARY KEY,
        product_name TEXT,
        category TEXT,
        price REAL
    );
    CREATE TABLE orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT,
        product_id TEXT,
        region TEXT,
        amount REAL,
        quantity INTEGER,
        status TEXT,
        order_date TEXT,
        dept_id TEXT
    );
    CREATE TABLE departments (
        dept_id TEXT PRIMARY KEY,
        dept_name TEXT
    );
    CREATE TABLE employees (
        employee_id TEXT PRIMARY KEY,
        employee_name TEXT,
        dept_id TEXT,
        position TEXT,
        hire_date TEXT
    );
    CREATE TABLE salaries (
        employee_id TEXT,
        base_salary REAL,
        bonus REAL,
        pay_date TEXT
    );
    """)

    # ---- 客户 ----
    regions = ["华东", "华南", "华北", "西南", "西北"]
    levels = ["VIP", "高级会员", "普通会员", "新客户"]
    customers = []
    for i in range(1, 51):
        customers.append((
            f"C{i:03d}", f"客户{i}公司", random.choice(regions),
            random.choice(levels), f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        ))
    cur.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

    # ---- 产品 ----
    categories = ["电子", "服装", "食品", "家居", "办公"]
    products = []
    for i in range(1, 31):
        products.append((
            f"P{i:03d}", f"产品{i}", random.choice(categories),
            round(random.uniform(50, 5000), 2)
        ))
    cur.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

    # ---- 部门 ----
    depts = [("D01", "销售部"), ("D02", "客服部"), ("D03", "人力资源部"),
             ("D04", "技术部"), ("D05", "市场部")]
    cur.executemany("INSERT INTO departments VALUES (?,?)", depts)

    # ---- 员工 ----
    positions = ["经理", "主管", "专员", "实习生"]
    employees = []
    for i in range(1, 41):
        employees.append((
            f"E{i:03d}", f"员工{i}", f"D{random.randint(1,5):02d}",
            random.choice(positions),
            f"202{random.randint(2,5)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        ))
    cur.executemany("INSERT INTO employees VALUES (?,?,?,?,?)", employees)

    # ---- 薪资 ----
    salaries = []
    base = datetime(2025, 1, 1)
    for e in employees:
        for m in range(6):
            salaries.append((
                e[0], round(random.uniform(8000, 25000), 2),
                round(random.uniform(0, 5000), 2),
                (base + timedelta(days=30*m)).strftime("%Y-%m-%d")
            ))
    cur.executemany("INSERT INTO salaries VALUES (?,?,?,?)", salaries)

    # ---- 订单 ----
    statuses = ["已完成", "退货", "处理中", "已取消"]
    orders = []
    base = datetime(2025, 5, 1)
    for i in range(1, 501):
        cust = random.choice(customers)
        prod = random.choice(products)
        dt = base + timedelta(days=random.randint(0, 60))
        qty = random.randint(1, 20)
        orders.append((
            f"O{i:04d}", cust[0], prod[0], cust[2],
            round(prod[3] * qty, 2), qty,
            random.choice(statuses), dt.strftime("%Y-%m-%d"),
            f"D{random.randint(1,5):02d}"
        ))
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)", orders)

    conn.commit()
    conn.close()
    print(f"样本数据库已创建: {DB_PATH}")
    print(f"  customers: {len(customers)} 行")
    print(f"  products: {len(products)} 行")
    print(f"  orders: {len(orders)} 行")
    print(f"  employees: {len(employees)} 行")
    print(f"  salaries: {len(salaries)} 行")

    # 顺便构建 schema 知识库
    print("\n构建 schema 知识库...")
    from retrieval.text_to_sql.schema_kb import build_schema_kb
    n = build_schema_kb()
    print(f"  已索引 {n} 张表 schema")


if __name__ == "__main__":
    init_db()
