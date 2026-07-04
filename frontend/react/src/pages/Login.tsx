import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Button, Card, CardContent, Input } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(username, password);
      navigate("/");
    } catch (err: any) {
      setError(err.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = (u: string, p: string) => {
    setUsername(u);
    setPassword(p);
  };

  return (
    <div className="min-h-screen flex items-center justify-center grid-bg">
      <Card className="w-[400px] glow">
        <CardContent className="p-8">
          <div className="flex flex-col items-center mb-6">
            <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mb-3">
              <svg className="w-7 h-7 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold gradient-text">数据中控 Agent</h1>
            <p className="text-sm text-muted-foreground mt-1">Enterprise Data Control Center</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground">用户名</label>
              <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="输入用户名" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">密码</label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="输入密码" />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "登录中..." : "登录"}
            </Button>
          </form>

          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs text-muted-foreground mb-2">快捷登录 (点击自动填充):</p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="text-xs flex-1" onClick={() => quickLogin("admin", "admin123")}>
                管理员
              </Button>
              <Button variant="outline" size="sm" className="text-xs flex-1" onClick={() => quickLogin("sales_mgr", "sales123")}>
                销售经理
              </Button>
              <Button variant="outline" size="sm" className="text-xs flex-1" onClick={() => quickLogin("hr_analyst", "hr123")}>
                HR分析师
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
