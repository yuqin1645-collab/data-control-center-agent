"""查询路由: 同步 + 流式 (SSE).

同步: POST /api/query - 等待完成, 返回完整结果
流式: POST /api/query/stream - SSE 逐事件推送
"""
import time
import uuid
import sys
import os
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from api.deps import get_current_user
from core.conversations import create_conversation, add_message, get_conversation

router = APIRouter()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


@router.post("")
async def submit_query(req: QueryRequest, user: dict = Depends(get_current_user)):
    """同步查询: 等待完成, 返回完整结果."""
    from agent import DataControlCenterAgent

    query_id = str(uuid.uuid4())[:8]
    t0 = time.time()

    agent = DataControlCenterAgent()

    history = None
    cid = req.conversation_id
    if cid:
        conv = get_conversation(cid, user["id"])
        if conv:
            # 传完整历史, 由 ContextCompactor 在超过 MAX_MESSAGES 条时自动摘要压缩.
            # 之前只取 msgs[-6:], 而 compact 阈值是 20, 导致 autoCompact 永不触发.
            msgs = conv.get("messages", [])
            history = [{"role": m["role"], "content": m["content"]} for m in msgs]
        else:
            cid = None

    result = agent.ask(req.query, user=user, history=history)
    elapsed_ms = int((time.time() - t0) * 1000)

    path_details = None
    if result.get("path_results"):
        pr = result["path_results"][0]
        if pr.get("result") and pr["result"].get("raw"):
            path_details = pr["result"]["raw"]
            path_details["path"] = pr["path"]
        else:
            path_details = {"path": pr["path"], "error": pr.get("error")}

    response_data = {
        "query_id": query_id,
        "status": "completed",
        "elapsed_ms": elapsed_ms,
        "route": result.get("route", {}),
        "cache_hit": result.get("cached", False),
        "path_details": path_details,
        "answer": result.get("answer", ""),
        "iterations": result.get("iterations", 1),
        "user": {
            "username": user.get("username"),
            "role": user.get("role"),
            "dept_id": user.get("dept_id"),
        },
        "conversation_id": cid,
    }

    if not cid:
        conv = create_conversation(user["id"])
        cid = conv["id"]
        response_data["conversation_id"] = cid

    add_message(cid, "user", req.query)
    add_message(
        cid, "assistant", result.get("answer", ""),
        json.dumps({
            "route": result.get("route"),
            "path_details": path_details,
            "elapsed_ms": elapsed_ms,
            "cache_hit": result.get("cached", False),
            "iterations": result.get("iterations", 1),
        }, ensure_ascii=False),
    )

    return response_data


_SENTINEL = object()


@router.post("/stream")
async def stream_query(req: QueryRequest, user: dict = Depends(get_current_user)):
    """流式查询 (SSE): 逐事件推送.

    事件类型:
      {"type": "status", "message": "..."}              - 进度状态
      {"type": "route", "label": ..., "reason": ...}     - 路由决策
      {"type": "tool_call", "name": ..., "args": {...}}  - 工具调用
      {"type": "tool_result", "name": ..., "result": ..} - 工具返回
      {"type": "text", "content": "..."}                 - 逐字文本
      {"type": "done", ...}                              - 结束
    """
    from agent import DataControlCenterAgent

    agent = DataControlCenterAgent()
    t0 = time.time()

    history = None
    cid = req.conversation_id
    if cid:
        conv = get_conversation(cid, user["id"])
        if conv:
            # 传完整历史, 由 ContextCompactor 在超过 MAX_MESSAGES 条时自动摘要压缩.
            # 之前只取 msgs[-6:], 而 compact 阈值是 20, 导致 autoCompact 永不触发.
            msgs = conv.get("messages", [])
            history = [{"role": m["role"], "content": m["content"]} for m in msgs]
        else:
            cid = None

    async def event_stream():
        """异步 SSE 生成器: 在线程池中运行同步 agent, 逐事件推送."""
        loop = asyncio.get_event_loop()
        gen = agent.ask_stream(req.query, user=user, history=history)

        full_answer = ""
        path_results = []
        route_info = {"label": "", "reason": ""}

        def safe_next():
            try:
                return next(gen)
            except StopIteration:
                return _SENTINEL

        while True:
            try:
                event = await loop.run_in_executor(None, safe_next)
            except Exception as e:
                err_event = {"type": "error", "message": "Agent error: " + str(e)}
                yield "data: " + json.dumps(err_event, ensure_ascii=False) + "\n\n"
                break

            if event is _SENTINEL:
                break

            etype = event.get("type")

            if etype == "route":
                route_info = {"label": event["label"], "reason": event["reason"]}

            elif etype == "text":
                full_answer += event["content"]

            elif etype == "tool_result":
                path_results.append({
                    "path": event["name"],
                    "result": {
                        "context": event.get("result", ""),
                        "raw": event.get("raw"),
                    },
                })

            elif etype == "done":
                nonlocal_cid = cid
                if not nonlocal_cid:
                    new_conv = create_conversation(user["id"])
                    nonlocal_cid = new_conv["id"]

                path_details = None
                if path_results:
                    pr = path_results[0]
                    if pr.get("result") and pr["result"].get("raw"):
                        path_details = pr["result"]["raw"]
                        path_details["path"] = pr["path"]

                add_message(nonlocal_cid, "user", req.query)
                add_message(
                    nonlocal_cid, "assistant", full_answer,
                    json.dumps({
                        "route": route_info,
                        "path_details": path_details,
                        "elapsed_ms": int((time.time() - t0) * 1000),
                        "iterations": event.get("iterations", 1),
                    }, ensure_ascii=False),
                )

                event["latency"] = round(time.time() - t0, 2)
                event["conversation_id"] = nonlocal_cid
                event["route"] = route_info
                event["path_results"] = path_results

            yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        },
    )
