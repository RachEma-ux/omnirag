/**
 * Typed API client for OmniRAG backend.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";

export async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  health: () => fetchAPI<{ status: string; version: string }>("/health"),
  ports: () => fetchAPI<{ ports: Record<string, number> }>("/ports"),

  // Intake
  ingest: (source: string, config = {}) =>
    fetchAPI("/intake", { method: "POST", body: JSON.stringify({ source, config }) }),
  listJobs: () => fetchAPI<any[]>("/intake"),
  getJob: (id: string) => fetchAPI(`/intake/${id}`),

  // Search
  search: (query: string, top_k = 10) =>
    fetchAPI("/v1/search", { method: "POST", body: JSON.stringify({ query, top_k }) }),

  // GraphRAG
  graphQuery: (mode: string, query: string) =>
    fetchAPI(`/graphrag/query/${mode}`, { method: "POST", body: JSON.stringify({ query, user_principal: "public" }) }),
  graphStats: () => fetchAPI("/graphrag/stats"),
  graphRoute: (query: string) =>
    fetchAPI("/graphrag/query/route", { method: "POST", body: JSON.stringify({ query, user_principal: "public" }) }),

  // Analytics
  analyticsSummary: () => fetchAPI("/v1/analytics/summary"),
  analyticsEntities: () => fetchAPI<any[]>("/v1/analytics/entities"),
  analyticsCommunities: () => fetchAPI<any[]>("/v1/analytics/communities"),

  // Workflows
  runWorkflow: (type: string, inputs = {}) =>
    fetchAPI("/v1/workflows/run", { method: "POST", body: JSON.stringify({ workflow_type: type, inputs }) }),
  listWorkflows: () => fetchAPI("/v1/workflows"),

  // MCP
  listTools: () => fetchAPI<any[]>("/v1/mcp/tools"),
  callTool: (name: string, params = {}) =>
    fetchAPI("/v1/mcp/call", { method: "POST", body: JSON.stringify({ tool_name: name, params }) }),
};
