import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Button, Card, CardContent, Input, Table, Th, Td, Tr, Badge } from "../components/ui";

export default function Admin() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState<any[]>([]);
  const [form, setForm] = useState({ username: "", password: "", dept_id: "", role: "analyst" });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!loading && !user) navigate("/login");
    if (user && user.role !== "admin") navigate("/");
  }, [user, loading, navigate]);

  const fetchUsers = async () => {
    try {
      const res = await api.users();
      setUsers(res);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => {
    if (user?.role === "admin") fetchUsers();
  }, [user]);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await api.register(form);
      setSuccess(`用户 ${form.username} 创建成功`);
      setForm({ username: "", password: "", dept_id: "", role: "analyst" });
      fetchUsers();
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (loading || !user) return null;

  const roleLabel = (r: string) => (r === "admin" ? "管理员" : r === "manager" ? "经理" : "分析师");

  return (
    <div className="min-h-screen p-6 grid-bg">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">用户管理</h1>
        <Button variant="outline" onClick={() => navigate("/")}>
          返回主页
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* User List */}
        <Card>
          <CardContent className="p-4">
            <h2 className="font-medium mb-3">用户列表 ({users.length})</h2>
            <Table>
              <thead>
                <tr>
                  <Th>ID</Th>
                  <Th>用户名</Th>
                  <Th>部门</Th>
                  <Th>角色</Th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <Tr key={u.id}>
                    <Td>{u.id}</Td>
                    <Td className="font-medium">{u.username}</Td>
                    <Td>{u.dept_id}</Td>
                    <Td>
                      <Badge variant={u.role === "admin" ? "primary" : u.role === "manager" ? "success" : "muted"}>
                        {roleLabel(u.role)}
                      </Badge>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </CardContent>
        </Card>

        {/* Add User Form */}
        <Card>
          <CardContent className="p-4">
            <h2 className="font-medium mb-3">添加用户</h2>
            <form onSubmit={handleRegister} className="space-y-3">
              <div>
                <label className="text-xs text-muted-foreground">用户名</label>
                <Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">密码</label>
                <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">部门</label>
                <select
                  className="w-full rounded-lg border border-border bg-secondary/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={form.dept_id}
                  onChange={(e) => setForm({ ...form, dept_id: e.target.value })}
                  required
                >
                  <option value="">选择部门</option>
                  <option value="SALES">销售部</option>
                  <option value="HR">人力资源</option>
                  <option value="TECH">技术部</option>
                  <option value="FINANCE">财务部</option>
                  <option value="ADMIN">管理部</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">角色</label>
                <select
                  className="w-full rounded-lg border border-border bg-secondary/50 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                >
                  <option value="analyst">分析师 (本部门只读)</option>
                  <option value="manager">经理 (本部门)</option>
                  <option value="admin">管理员 (全部门)</option>
                </select>
              </div>
              {error && <p className="text-sm text-danger">{error}</p>}
              {success && <p className="text-sm text-success">{success}</p>}
              <Button type="submit" className="w-full">
                创建用户
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
