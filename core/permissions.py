"""权限上下文: RBAC + 行级权限辅助."""
from typing import Optional, Dict, Tuple


# 角色权限矩阵
ROLE_PERMISSIONS = {
    "admin": {
        "description": "管理员: 全部门访问, 可管理用户",
        "dept_filter": None,        # 不过滤
        "can_manage_users": True,
        "tables": "*",              # 所有表
    },
    "manager": {
        "description": "部门经理: 本部门数据访问",
        "dept_filter": "own",       # 本部门
        "can_manage_users": False,
        "tables": ["orders", "customers", "products", "employees", "salaries", "departments"],
    },
    "analyst": {
        "description": "数据分析师: 本部门只读",
        "dept_filter": "own",
        "can_manage_users": False,
        "tables": ["orders", "customers", "products", "employees"],
    },
}


class PermissionContext:
    """封装当前用户的权限上下文, 供 executor 等模块使用."""

    def __init__(self, user: Optional[Dict] = None):
        self.user = user or {}
        self.role = self.user.get("role", "analyst")
        self.dept_id = self.user.get("dept_id")
        self.permissions = ROLE_PERMISSIONS.get(self.role, ROLE_PERMISSIONS["analyst"])

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def can_manage_users(self) -> bool:
        return self.permissions.get("can_manage_users", False)

    def get_dept_filter(self) -> Optional[str]:
        """返回部门过滤值, admin 返回 None (不过滤)."""
        if self.permissions["dept_filter"] is None:
            return None
        return self.dept_id

    def can_access_table(self, table_name: str) -> bool:
        """检查用户是否能访问某张表."""
        if self.permissions["tables"] == "*":
            return True
        return table_name.lower() in [t.lower() for t in self.permissions["tables"]]

    def to_dict(self) -> dict:
        return {
            "username": self.user.get("username", "anonymous"),
            "role": self.role,
            "dept_id": self.dept_id,
            "is_admin": self.is_admin,
        }


def make_permission_context(user: Optional[Dict] = None) -> PermissionContext:
    """工厂函数."""
    return PermissionContext(user)
