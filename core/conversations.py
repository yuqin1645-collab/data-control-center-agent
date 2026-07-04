"""会话管理: 多轮对话持久化.

参考 Claude Code 的 session persistence 模式:
  - 每个会话独立存储 (conversations + messages 表)
  - append-only: 消息只追加不修改
  - resume: 按 conversation_id 加载历史消息重建上下文
"""
import sqlite3
import uuid
import time
from typing import Optional, Dict, List

AUTH_DB_PATH = "data/agent_auth.db"


def _ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def _ensure_tables():
    """确保会话表存在."""
    conn = sqlite3.connect(AUTH_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def create_conversation(user_id: int, title: str = "") -> Dict:
    """创建新会话, 返回 {id, user_id, title, created_at, updated_at}."""
    _ensure_tables()
    cid = uuid.uuid4().hex[:12]
    now = _ts()
    conn = sqlite3.connect(AUTH_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (cid, user_id, title, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": cid, "user_id": user_id, "title": title, "created_at": now, "updated_at": now}


def list_conversations(user_id: int, limit: int = 50) -> List[Dict]:
    """列出用户的会话, 按更新时间倒序."""
    _ensure_tables()
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """SELECT c.*, (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) as msg_count
           FROM conversations c WHERE c.user_id = ?
           ORDER BY c.updated_at DESC LIMIT ?""",
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_conversation(cid: str, user_id: int) -> Optional[Dict]:
    """获取会话 + 所有消息."""
    _ensure_tables()
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (cid, user_id))
    conv = cur.fetchone()
    if not conv:
        conn.close()
        return None
    cur.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (cid,),
    )
    msgs = cur.fetchall()
    conn.close()
    result = dict(conv)
    result["messages"] = [dict(m) for m in msgs]
    return result


def delete_conversation(cid: str, user_id: int) -> bool:
    """删除会话 (消息级联删除)."""
    _ensure_tables()
    conn = sqlite3.connect(AUTH_DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE conversation_id = ?", (cid,))
    cur.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (cid, user_id))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def add_message(cid: str, role: str, content: str, metadata: str = "") -> Dict:
    """追加消息到会话, 自动更新会话 updated_at."""
    _ensure_tables()
    mid = uuid.uuid4().hex[:12]
    now = _ts()
    conn = sqlite3.connect(AUTH_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (id, conversation_id, role, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (mid, cid, role, content, metadata, now),
    )
    cur.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, cid))
    # 如果会话没有 title 且这是第一条 user 消息, 用消息内容做 title
    cur.execute("SELECT title FROM conversations WHERE id = ?", (cid,))
    row = cur.fetchone()
    if row and not row[0] and role == "user":
        title = content[:30] + ("..." if len(content) > 30 else "")
        cur.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, cid))
    conn.commit()
    conn.close()
    return {"id": mid, "conversation_id": cid, "role": role, "content": content, "metadata_json": metadata, "created_at": now}
