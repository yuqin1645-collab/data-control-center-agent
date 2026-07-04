"""认证模块: JWT 签发/验证 + 用户管理."""
import sqlite3
import time
import secrets
import os
from typing import Optional, Dict
from jose import jwt, JWTError
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# JWT 密钥: 持久化到文件, 重启不变 (避免 token 失效)
JWT_SECRET_FILE = "data/.jwt_secret"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
AUTH_DB_PATH = "data/agent_auth.db"


def _load_or_create_secret() -> str:
    """从文件加载 JWT 密钥, 不存在则生成并保存."""
    if os.path.exists(JWT_SECRET_FILE):
        with open(JWT_SECRET_FILE, "r") as f:
            return f.read().strip()
    secret = secrets.token_urlsafe(32)
    os.makedirs("data", exist_ok=True)
    with open(JWT_SECRET_FILE, "w") as f:
        f.write(secret)
    return secret


JWT_SECRET = _load_or_create_secret()


def create_token(user: Dict, secret: str = None) -> str:
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "dept_id": user["dept_id"],
        "role": user["role"],
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, secret or JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, secret: str = None) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, secret or JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "id": int(payload["sub"]),
            "username": payload["username"],
            "dept_id": payload["dept_id"],
            "role": payload["role"],
        }
    except (JWTError, KeyError, ValueError):
        return None


def get_user_by_username(username: str) -> Optional[Dict]:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def get_user_by_id(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, username, dept_id, role FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_users() -> list:
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, username, dept_id, role, created_at FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_user(username: str, password: str, dept_id: str, role: str) -> Dict:
    conn = sqlite3.connect(AUTH_DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, dept_id, role) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), dept_id, role),
        )
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError(f"用户名已存在: {username}")
    conn.close()
    return {"id": user_id, "username": username, "dept_id": dept_id, "role": role}


def authenticate(username: str, password: str) -> Optional[Dict]:
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "dept_id": user["dept_id"],
        "role": user["role"],
    }
