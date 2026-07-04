"""API 依赖: JWT 认证 + 角色检查."""
from fastapi import Request, HTTPException
from core.auth import decode_token


def get_current_user(request: Request) -> dict:
    """从 Authorization header 提取 JWT, 返回 user dict."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证 token")
    token = auth_header[7:]
    user = decode_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return user


def get_admin_user(user: dict = None) -> dict:
    """要求 admin 角色. 用法: Depends(get_admin_user_dep)."""
    if user is None:
        # 直接调用时给个提示
        raise HTTPException(status_code=401, detail="未认证")
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def get_admin_user_dep(request: Request) -> dict:
    """FastAPI 依赖: 认证 + admin 角色检查."""
    user = get_current_user(request)
    return get_admin_user(user)
