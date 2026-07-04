import { Badge } from "./ui";

const PATHS = [
  { key: "query_sql", label: "Text-to-SQL", icon: "SQL" },
  { key: "search_documents", label: "RAG", icon: "DOC" },
  { key: "query_graph", label: "GraphRAG", icon: "GRAPH" },
  { key: "search_wiki", label: "Wiki", icon: "WIKI" },
  { key: "query_sag", label: "SAG", icon: "SAG" },
];

export default function RouteFlow({ route }: { route: { label: string; reason: string } }) {
  const activeLabel = route?.label || "";

  // 支持 LLM 多工具调用: label 可能是 "query_sql+search_documents"
  const activeTools = activeLabel.split("+").filter(Boolean);

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
        <span className="text-sm font-medium">Agent 工具调用</span>
        <span className="text-xs text-muted-foreground">— {route?.reason || ""}</span>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <div className="px-3 py-2 rounded-lg bg-secondary text-xs font-medium border border-border">
          自然语言查询
        </div>
        <Arrow />
        <div className="px-3 py-2 rounded-lg bg-secondary text-xs font-medium border border-border">
          LLM 决策
        </div>
        <Arrow />
        <div className="flex gap-1.5">
          {PATHS.map((p) => {
            const active = activeTools.includes(p.key);
            return (
              <div
                key={p.key}
                className={`px-3 py-2 rounded-lg text-xs font-medium border ${
                  active
                    ? "bg-primary/20 text-primary route-active glow"
                    : "bg-secondary/50 text-muted-foreground border-border"
                }`}
              >
                {p.label}
              </div>
            );
          })}
        </div>
        <Arrow />
        <div className="px-3 py-2 rounded-lg bg-success/20 text-xs font-medium border border-success">
          生成回答
        </div>
      </div>
    </div>
  );
}

function Arrow() {
  return (
    <svg className="w-4 h-4 text-muted-foreground flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7-7 7m7-7H3" />
    </svg>
  );
}
