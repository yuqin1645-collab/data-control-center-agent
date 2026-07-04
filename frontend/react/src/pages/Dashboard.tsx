import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import {
  api,
  QueryResult,
  Conversation,
  ConversationDetail,
  DataSource,
  SystemStats,
} from "../lib/api";
import {
  Button,
  Textarea,
  Badge,
  Table,
  Th,
  Td,
  Tr,
  Avatar,
  Skeleton,
} from "../components/ui";
import RouteFlow from "../components/RouteFlow";
import ChatMessage from "../components/ChatMessage";

const EXAMPLES = [
  "销售额排名前5的产品",
  "员工报销流程是什么",
  "张三和李四有什么关系",
  "什么是机器学习",
  "客户C001买了什么产品以及相关产品",
];

type ChatItem = { query: string; result: QueryResult };

export default function Dashboard() {
  const { user, logout, loading } = useAuth();
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [sending, setSending] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sidebarTab, setSidebarTab] = useState<"chats" | "data">("chats");
  const [loadingConv, setLoadingConv] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
    } catch (e) {}
  }, []);

  useEffect(() => {
    if (!loading && !user) navigate("/login");
  }, [user, loading, navigate]);

  useEffect(() => {
    if (user) {
      loadConversations();
      api.dataSources().then(setDataSources).catch(() => {});
      api.stats().then(setStats).catch(() => {});
    }
  }, [user]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewChat = () => {
    setActiveConvId(null);
    setMessages([]);
    setInput("");
  };

  const handleSelectConv = async (cid: string) => {
    if (cid === activeConvId) return;
    setLoadingConv(true);
    try {
      const conv: ConversationDetail = await api.getConversation(cid);
      const items: ChatItem[] = [];
      for (let i = 0; i < conv.messages.length; i++) {
        const msg = conv.messages[i];
        if (msg.role === "user") {
          const next = conv.messages[i + 1];
          if (next && next.role === "assistant") {
            let meta: any = {};
            try { meta = JSON.parse(next.metadata_json || "{}"); } catch (e) {}
            items.push({
              query: msg.content,
              result: {
                query_id: msg.id,
                status: "completed",
                elapsed_ms: meta.elapsed_ms || 0,
                route: meta.route || { label: "unknown", reason: "" },
                cache_hit: meta.cache_hit || false,
                path_details: meta.path_details || null,
                answer: next.content,
                user: { username: user?.username || "", role: user?.role || "", dept_id: user?.dept_id || "" },
                conversation_id: cid,
              },
            });
          }
        }
      }
      setActiveConvId(cid);
      setMessages(items);
    } catch (err) { console.error("load conv error", err); }
    finally { setLoadingConv(false); }
  };

  const handleDeleteConv = async (e: React.MouseEvent, cid: string) => {
    e.stopPropagation();
    try {
      await api.deleteConversation(cid);
      setConversations((prev) => prev.filter((c) => c.id !== cid));
      if (cid === activeConvId) { setActiveConvId(null); setMessages([]); }
    } catch (e2) {}
  };

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    const query = input.trim();
    setInput("");
    setSending(true);
    setStatusMsg("正在分析问题...");
    const tempItem: ChatItem = {
      query,
      result: {
        query_id: "streaming", status: "streaming", elapsed_ms: 0,
        route: { label: "", reason: "" }, cache_hit: false,
        path_details: null, answer: "",
        user: { username: user?.username || "", role: user?.role || "", dept_id: user?.dept_id || "" },
      },
    };
    setMessages((prev) => [...prev, tempItem]);
    try {
      await api.queryStream(query, activeConvId, (event) => {
        if (event.type === "status") {
          setStatusMsg(event.message || "");
        } else if (event.type === "error") {
          setStatusMsg("");
          setMessages((prev) => {
            const u = [...prev]; const l = u[u.length - 1];
            u[u.length - 1] = { ...l, result: { ...l.result, status: "error", answer: "错误: " + event.message, route: { label: "error", reason: event.message } } };
            return u;
          });
        } else if (event.type === "route") {
          setMessages((prev) => {
            const u = [...prev]; const l = u[u.length - 1];
            u[u.length - 1] = { ...l, result: { ...l.result, route: { label: event.label, reason: event.reason } } };
            return u;
          });
        } else if (event.type === "tool_call") {
          setMessages((prev) => {
            const u = [...prev]; const l = u[u.length - 1];
            const pd = l.result.path_details || {}; pd.path = event.name;
            u[u.length - 1] = { ...l, result: { ...l.result, path_details: pd } };
            return u;
          });
        } else if (event.type === "tool_result") {
          setMessages((prev) => {
            const u = [...prev]; const l = u[u.length - 1];
            let pd = l.result.path_details || {};
            if (event.raw) {
              pd = { ...event.raw, path: event.name };
            }
            u[u.length - 1] = { ...l, result: { ...l.result, path_details: pd } };
            return u;
          });
        } else if (event.type === "text") {
          setStatusMsg("");
          setMessages((prev) => {
            const u = [...prev]; const l = u[u.length - 1];
            u[u.length - 1] = { ...l, result: { ...l.result, answer: l.result.answer + event.content } };
            return u;
          });
        } else if (event.type === "done") {
          setMessages((prev) => {
            const u = [...prev]; const l = u[u.length - 1];
            let pd = l.result.path_details;
            if (event.path_results && event.path_results.length > 0) {
              const pr = event.path_results[0];
              if (pr.result && pr.result.raw) {
                pd = pr.result.raw;
                pd.path = pr.path;
              } else {
                pd = { path: pr.path, error: pr.error };
              }
            }
            u[u.length - 1] = { ...l, result: { ...l.result, status: "completed", query_id: "done",
              elapsed_ms: event.latency ? Math.round(event.latency * 1000) : 0,
              conversation_id: event.conversation_id,
              path_details: pd } };
            return u;
          });
          if (!activeConvId && event.conversation_id) setActiveConvId(event.conversation_id);
          loadConversations();
        }
      });
    } catch (err: any) {
      setStatusMsg("");
      setMessages((prev) => {
        const u = [...prev];
        u[u.length - 1] = { query, result: {
          query_id: "error", status: "error", elapsed_ms: 0,
          route: { label: "error", reason: err.message }, cache_hit: false,
          path_details: null, answer: "查询失败: " + err.message,
          user: { username: user?.username || "", role: user?.role || "", dept_id: user?.dept_id || "" },
        }};
        return u;
      });
    } finally { setSending(false); setStatusMsg(""); }
  };

  if (loading) return (<div className="min-h-screen flex items-center justify-center"><Skeleton className="w-8 h-8 rounded-full" /></div>);
  if (!user) return null;
  const onlineSources = dataSources.filter((s) => s.status === "online").length;
  const initials = user.username.slice(0, 2).toUpperCase();

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top Nav */}
      <nav className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center justify-between px-6 h-14">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <svg className="w-5 h-5 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
              </svg>
            </div>
            <div>
              <span className="font-bold text-lg gradient-text">数据中控 Agent</span>
              <span className="text-xs text-muted-foreground ml-2">Enterprise Data Control Center</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm">
              <div className="w-2 h-2 rounded-full bg-success pulse-dot" />
              <span className="text-muted-foreground">{onlineSources} 数据源在线</span>
            </div>
            {user.role === "admin" && (
              <Button variant="ghost" className="text-sm" onClick={() => navigate("/admin")}>用户管理</Button>
            )}
            <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-secondary">
              <Avatar initials={initials} className="w-7 h-7" />
              <div className="text-sm">
                <div className="font-medium">{user.username}</div>
                <div className="text-xs text-muted-foreground">
                  {user.role === "admin" ? "管理员" : user.role === "manager" ? "经理" : "分析师"} · {user.dept_id}
                </div>
              </div>
            </div>
            <Button variant="ghost" className="text-sm" onClick={logout}>退出</Button>
          </div>
        </div>
      </nav>

      <div className="flex flex-1 h-[calc(100vh-3.5rem)]">
        {/* Sidebar */}
        <aside className="w-72 border-r border-border bg-card/30 flex flex-col overflow-hidden">
          <div className="p-3 border-b border-border">
            <Button variant="default" className="w-full justify-center gap-2" onClick={handleNewChat}>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
              </svg>
              新建对话
            </Button>
          </div>

          <div className="flex border-b border-border">
            <button className={`flex-1 py-2 text-xs font-medium transition ${sidebarTab === "chats" ? "text-primary border-b-2 border-primary bg-primary/5" : "text-muted-foreground hover:text-foreground"}`} onClick={() => setSidebarTab("chats")}>
              对话历史 ({conversations.length})
            </button>
            <button className={`flex-1 py-2 text-xs font-medium transition ${sidebarTab === "data" ? "text-primary border-b-2 border-primary bg-primary/5" : "text-muted-foreground hover:text-foreground"}`} onClick={() => setSidebarTab("data")}>
              数据 指标
            </button>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin">
            {sidebarTab === "chats" ? (
              <div className="p-2 space-y-0.5">
                {loadingConv && <div className="px-3 py-2 text-xs text-muted-foreground">加载中...</div>}
                {conversations.length === 0 && !loadingConv && (
                  <div className="px-3 py-8 text-center text-xs text-muted-foreground">暂无对话历史<br />点击上方按钮开始新对话</div>
                )}
                {conversations.map((conv) => (
                  <div key={conv.id} className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition ${conv.id === activeConvId ? "bg-primary/10 text-primary" : "hover:bg-secondary text-foreground"}`} onClick={() => handleSelectConv(conv.id)}>
                    <svg className="w-3.5 h-3.5 flex-shrink-0 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm truncate">{conv.title || "(新对话)"}</div>
                      <div className="text-xs text-muted-foreground">{conv.msg_count} 条消息 · {conv.updated_at?.slice(5, 16) || ""}</div>
                    </div>
                    <button className="opacity-0 group-hover:opacity-100 transition text-muted-foreground hover:text-danger flex-shrink-0" onClick={(e) => handleDeleteConv(e, conv.id)} title="删除对话">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-3 space-y-4">
                <div>
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">数据源状态</div>
                  <div className="space-y-2">
                    {dataSources.map((s) => (
                      <div key={s.name} className="flex items-center justify-between px-3 py-2 rounded-lg bg-secondary/50">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${s.status === "online" ? "bg-success" : "bg-danger"}`} />
                          <span className="text-sm">{s.name}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">{s.type === "sqlite" ? `${s.stats?.total_rows || 0}行` : s.type}</span>
                      </div>
                    ))}
                    {dataSources.length === 0 && <Skeleton className="h-8 w-full" />}
                  </div>
                </div>
                {stats && (
                  <div>
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">系统指标</div>
                    <div className="space-y-3">
                      {[{ label: "缓存命中率", value: stats.cache_hit_rate, color: "bg-success" }, { label: "SQL准确率", value: stats.sql_accuracy, color: "bg-success" }, { label: "路由准确率", value: stats.router_accuracy, color: "bg-warning" }].map((m) => (
                        <div key={m.label}>
                          <div className="flex justify-between text-xs mb-1"><span className="text-muted-foreground">{m.label}</span><span className="font-medium">{Math.round(m.value * 100)}%</span></div>
                          <div className="h-1.5 rounded-full bg-secondary overflow-hidden"><div className={`h-full ${m.color} rounded-full`} style={{ width: `${m.value * 100}%` }} /></div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">快捷示例</div>
                  <div className="space-y-1">
                    {EXAMPLES.map((ex) => (<button key={ex} className="w-full text-left px-3 py-1.5 text-xs rounded-lg hover:bg-secondary text-muted-foreground transition" onClick={() => setInput(ex)}>{ex}</button>))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 flex flex-col grid-bg">
          {activeConvId && (
            <div className="px-6 py-1.5 border-b border-border bg-card/20 text-xs text-muted-foreground flex items-center gap-2">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M7 21l5-5 5 5M7 3l5 5 5-5" /></svg>
              会话: {conversations.find((c) => c.id === activeConvId)?.title || "新对话"}
            </div>
          )}
          {messages.length > 0 && messages[messages.length - 1].result.route?.label && (
            <div className="border-b border-border p-4 bg-card/30"><RouteFlow route={messages[messages.length - 1].result.route} /></div>
          )}
          <div className="flex-1 overflow-y-auto scrollbar-thin p-6 space-y-4">
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                  </div>
                  <h2 className="text-lg font-medium mb-2">数据中控 Agent</h2>
                  <p className="text-sm text-muted-foreground">输入自然语言查询, Agent 自动路由到最佳检索路径</p>
                  <div className="flex flex-wrap justify-center gap-2 mt-4">
                    {EXAMPLES.map((ex) => (<Button key={ex} variant="outline" className="text-xs" onClick={() => setInput(ex)}>{ex}</Button>))}
                  </div>
                </div>
              </div>
            )}
            {messages.map((msg, i) => (<ChatMessage key={i} result={msg.result} query={msg.query} />))}
            {sending && messages.length > 0 && !messages[messages.length - 1].result.answer && (
              <div className="flex gap-3 slide-in">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center text-xs font-bold flex-shrink-0">AI</div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  {statusMsg || "正在查询..."}
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="border-t border-border p-4 bg-card/50 backdrop-blur-sm">
            <div className="flex gap-2 items-end">
              <Textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }} rows={1} placeholder="输入你的问题" className="flex-1" />
              <Button onClick={handleSend} disabled={sending || !input.trim()}>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
                发送
              </Button>
            </div>
            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
              <span>Enter 发送 / Shift+Enter 换行</span><span>·</span>
              <span>当前角色: {user.role === "admin" ? "管理员 (全部门访问)" : user.role === "manager" ? "经理 (" + user.dept_id + ")" : "分析师 (" + user.dept_id + ")"}</span>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
