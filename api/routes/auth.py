"""认证路由: 登录 / 当前用户 / 注册."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.auth import authenticate, create_token, create_user, list_users
from api.deps import get_current_user, get_admin_user_dep

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    dept_id: str
    role: str


@router.post("/login")
async def login(req: LoginRequest):
    """登录, 返回 JWT + 用户信息."""
    user = authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user)
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "dept_id": user["dept_id"],
            "role": user["role"],
        },
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """当前用户信息."""
    return user


@router.get("/users")
async def users(user: dict = Depends(get_admin_user_dep)):
    """列出所有用户 (仅 admin)."""
    return list_users()


@router.post("/register")
async def register(req: RegisterRequest, user: dict = Depends(get_admin_user_dep)):
    """注册新用户 (仅 admin)."""
    if req.role not in ("admin", "manager", "analyst"):
        raise HTTPException(status_code=400, detail="角色必须是 admin/manager/analyst")
    try:
        new_user = create_user(req.username, req.password, req.dept_id, req.role)
        return {"message": "用户创建成功", "user": new_user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
