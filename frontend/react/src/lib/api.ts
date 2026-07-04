const API_BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("token");
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/login";
    throw new Error("未认证");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "请求失败");
  }
  return res.json();
}

export const api = {
  login: (username: string, password: string) =>
    request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  me: () => request("/auth/me"),

  query: (query: string, conversationId?: string) =>
    request("/query", {
      method: "POST",
      body: JSON.stringify({ query, conversation_id: conversationId || null }),
    }),

  queryStream: async (
    query: string,
    conversationId: string | null,
    onEvent: (event: any) => void
  ): Promise<void> => {
    const token = getToken();
    const res = await fetch(`${API_BASE}/query/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ query, conversation_id: conversationId || null }),
    });

    if (res.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
      throw new Error("未认证");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "请求失败");
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const event = JSON.parse(line.slice(6));
            onEvent(event);
          } catch (e) {
            // ignore parse errors
          }
        }
      }
    }
    if (buffer.startsWith("data: ")) {
      try {
        const event = JSON.parse(buffer.slice(6));
        onEvent(event);
      } catch (e) {
        // ignore
      }
    }
  },

  createConversation: (title?: string) =>
    request("/conversations", {
      method: "POST",
      body: JSON.stringify({ title: title || "" }),
    }),

  listConversations: () => request("/conversations"),

  getConversation: (id: string) => request(`/conversations/${id}`),

  deleteConversation: (id: string) =>
    request(`/conversations/${id}`, { method: "DELETE" }),

  dataSources: () => request("/data-sources"),
  stats: () => request("/stats"),
  users: () => request("/auth/users"),
  register: (data: { username: string; password: string; dept_id: string; role: string }) =>
    request("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  health: () => request("/health"),
};

export type QueryResult = {
  query_id: string;
  status: string;
  elapsed_ms: number;
  route: { label: string; reason: string; subqueries?: any[] };
  cache_hit: boolean;
  path_details: any;
  answer: string;
  user: { username: string; role: string; dept_id: string };
  conversation_id?: string;
};

export type Conversation = {
  id: string;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  msg_count: number;
};

export type Message = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  metadata_json: string;
  created_at: string;
};

export type ConversationDetail = Conversation & {
  messages: Message[];
};

export type DataSource = {
  name: string;
  type: string;
  status: string;
  stats: Record<string, any>;
};

export type SystemStats = {
  cache_hit_rate: number;
  sql_accuracy: number;
  router_accuracy: number;
  avg_latency_ms: number;
};
