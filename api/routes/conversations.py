"""会话路由: 多轮对话管理 API.

参考 Claude Code 的 session 机制:
  - POST   /conversations          — 新建会话 (相当于 Claude Code 的 /new)
  - GET    /conversations          — 列出用户会话
  - GET    /conversations/{id}     — 加载会话 + 消息 (resume)
  - DELETE /conversations/{id}     — 删除会话
  - POST   /conversations/{id}/messages — 追加消息
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.deps import get_current_user
from core.conversations import (
    create_conversation,
    list_conversations,
    get_conversation,
    delete_conversation,
    add_message,
)

router = APIRouter()


class CreateConvRequest(BaseModel):
    title: Optional[str] = ""


class AddMessageRequest(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    metadata: Optional[str] = ""


@router.post("")
async def create_conv(req: CreateConvRequest, user: dict = Depends(get_current_user)):
    """新建会话."""
    conv = create_conversation(user["id"], req.title or "")
    return conv


@router.get("")
async def list_conv(user: dict = Depends(get_current_user)):
    """列出当前用户的所有会话."""
    return list_conversations(user["id"])


@router.get("/{cid}")
async def get_conv(cid: str, user: dict = Depends(get_current_user)):
    """获取会话详情 (含所有消息)."""
    conv = get_conversation(cid, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.delete("/{cid}")
async def del_conv(cid: str, user: dict = Depends(get_current_user)):
    """删除会话."""
    ok = delete_conversation(cid, user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "deleted", "id": cid}


@router.post("/{cid}/messages")
async def append_msg(cid: str, req: AddMessageRequest, user: dict = Depends(get_current_user)):
    """追加消息到会话."""
    # 验证会话属于当前用户
    conv = get_conversation(cid, user["id"])
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    msg = add_message(cid, req.role, req.content, req.metadata)
    return msg
