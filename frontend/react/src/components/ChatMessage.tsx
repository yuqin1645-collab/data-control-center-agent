import { useState } from "react";
import { Badge, Table, Th, Td, Tr } from "./ui";
import type { QueryResult } from "../lib/api";

export default function ChatMessage({ result, query }: { result: QueryResult; query: string }) {
  const [showSql, setShowSql] = useState(false);

  const isPending = result.status === "pending" || result.query_id === "pending";
  const isStreaming = result.status === "streaming" || result.query_id === "streaming";

  const routeLabel = result.route?.label || "unknown";
  const pathDetails = result.path_details || {};
  const hasSql = !!pathDetails?.sql;
  const hasRows = !!pathDetails?.rows?.length;
  const hasColumns = !!pathDetails?.columns?.length;

  const highlightSql = (sql: string) => {
    const keywords = ["SELECT", "FROM", "WHERE", "AND", "OR", "GROUP BY", "ORDER BY", "LIMIT", "JOIN", "LEFT", "RIGHT", "INNER", "ON", "AS", "DESC", "ASC", "COUNT", "SUM", "AVG", "MAX", "MIN", "DISTINCT", "HAVING", "UNION"];
    let highlighted = sql;
    keywords.forEach((kw) => {
      const regex = new RegExp(`\\b${kw}\\b`, "gi");
      highlighted = highlighted.replace(regex, `<span class="sql-keyword">${kw}</span>`);
    });
    highlighted = highlighted.replace(/'([^']*)'/g, '<span class="sql-string">"$1"</span>');
    highlighted = highlighted.replace(/(--.*$)/gm, '<span class="sql-comment">$1</span>');
    return highlighted;
  };

  return (
    <>
      {/* User Query */}
      <div className="flex justify-end slide-in">
        <div className="max-w-2xl px-4 py-3 rounded-2xl rounded-tr-sm bg-primary text-primary-foreground">
          {query}
        </div>
      </div>

      {/* Assistant Response (skip if pending) */}
      {!isPending && (
        <div className="flex gap-3 slide-in">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center text-xs font-bold flex-shrink-0">
            AI
          </div>
          <div className="flex-1 space-y-3">
            {/* Route Badges */}
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="primary">{routeLabel}</Badge>
              <Badge variant={result.cache_hit ? "success" : "muted"}>
                {result.cache_hit ? "缓存命中" : "缓存未命中"}
              </Badge>
              <Badge variant="muted">耗时 {(result.elapsed_ms / 1000).toFixed(1)}s</Badge>
              {hasSql && pathDetails.attempts !== undefined && (
                <Badge variant="muted">SQL 纠错: {pathDetails.attempts - 1}次</Badge>
              )}
              {pathDetails.tables && (
                <Badge variant="muted">Schema: {Array.isArray(pathDetails.tables) ? pathDetails.tables.length : 0}表</Badge>
              )}
            </div>

            {/* Answer */}
            <div className="p-4 rounded-xl bg-card border border-border glow">
              {/* Data Table */}
              {hasRows && hasColumns && (
                <div className="mb-3 overflow-x-auto">
                  <Table>
                    <thead>
                      <tr>
                        {pathDetails.columns.map((col: string, i: number) => (
                          <Th key={i}>{col}</Th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {pathDetails.rows.slice(0, 20).map((row: any[], i: number) => (
                        <Tr key={i}>
                          {row.map((cell, j) => (
                            <Td key={j}>{String(cell)}</Td>
                          ))}
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                  {pathDetails.rows.length > 20 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      共 {pathDetails.rows.length} 行, 仅显示前 20 行
                    </p>
                  )}
                </div>
              )}

              {/* Answer Text (with streaming cursor) */}
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {result.answer}
                {isStreaming && (
                  <span className="inline-block w-2 h-4 bg-primary ml-0.5 animate-pulse align-middle" />
                )}
              </p>
            </div>

            {/* SQL Detail */}
            {hasSql && (
              <details className="rounded-lg border border-border overflow-hidden" open={showSql}>
                <summary
                  className="px-4 py-2.5 text-xs text-muted-foreground cursor-pointer hover:bg-secondary/50 transition flex items-center gap-2"
                  onClick={(e) => {
                    e.preventDefault();
                    setShowSql(!showSql);
                  }}
                >
                  <svg
                    className={`w-3 h-3 transition-transform ${showSql ? "rotate-90" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  查看 SQL 详情
                </summary>
                <div className="p-4 bg-secondary/30 border-t border-border">
                  <pre
                    className="text-xs font-mono overflow-x-auto"
                    dangerouslySetInnerHTML={{ __html: highlightSql(pathDetails.sql) }}
                  />
                  {pathDetails.attempts !== undefined && (
                    <p className="text-xs text-muted-foreground mt-2">
                      生成尝试: {pathDetails.attempts} 次
                      {pathDetails.attempts > 1 && " (含自纠错)"}
                    </p>
                  )}
                </div>
              </details>
            )}

            {/* Graph edges */}
            {pathDetails.edges && (
              <details className="rounded-lg border border-border overflow-hidden">
                <summary className="px-4 py-2.5 text-xs text-muted-foreground cursor-pointer hover:bg-secondary/50 transition">
                  查看知识图谱子图 ({pathDetails.nodes?.length || 0} 节点, {pathDetails.edges?.length || 0} 边)
                </summary>
                <div className="p-4 bg-secondary/30 border-t border-border">
                  <Table>
                    <thead>
                      <tr>
                        <Th>实体 A</Th>
                        <Th>关系</Th>
                        <Th>实体 B</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {pathDetails.edges.slice(0, 20).map((e: any, i: number) => (
                        <Tr key={i}>
                          <Td>{e.u}</Td>
                          <Td>{e.relation}</Td>
                          <Td>{e.v}</Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              </details>
            )}

            {/* Wiki passages */}
            {pathDetails.passages && (
              <details className="rounded-lg border border-border overflow-hidden">
                <summary className="px-4 py-2.5 text-xs text-muted-foreground cursor-pointer hover:bg-secondary/50 transition">
                  查看 Wiki 检索结果 ({pathDetails.titles?.length || 0} 条)
                </summary>
                <div className="p-4 bg-secondary/30 border-t border-border space-y-2">
                  {pathDetails.passages.map((p: string, i: number) => (
                    <div key={i} className="text-xs text-muted-foreground p-2 rounded bg-secondary/50">
                      {p}
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Document chunks */}
            {pathDetails.chunks && (
              <details className="rounded-lg border border-border overflow-hidden">
                <summary className="px-4 py-2.5 text-xs text-muted-foreground cursor-pointer hover:bg-secondary/50 transition">
                  查看文档检索块 ({pathDetails.chunks?.length || 0} 块)
                </summary>
                <div className="p-4 bg-secondary/30 border-t border-border space-y-2">
                  {pathDetails.chunks.map((c: string, i: number) => (
                    <div key={i} className="text-xs text-muted-foreground p-2 rounded bg-secondary/50">
                      {c.slice(0, 200)}...
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* SAG hypergraph */}
            {pathDetails.hypergraph_stats && (
              <details className="rounded-lg border border-border overflow-hidden">
                <summary className="px-4 py-2.5 text-xs text-muted-foreground cursor-pointer hover:bg-secondary/50 transition">
                  查看超图扩展详情
                </summary>
                <div className="p-4 bg-secondary/30 border-t border-border text-xs space-y-1">
                  <div>超图统计: {pathDetails.hypergraph_stats}</div>
                  <div>种子实体: {pathDetails.seeds?.slice(0, 5).join(", ")}</div>
                  <div>扩展实体: {pathDetails.expanded?.slice(0, 5).join(", ")}</div>
                </div>
              </details>
            )}
          </div>
        </div>
      )}
    </>
  );
}
