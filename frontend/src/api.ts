import type { ConfigStatus, Decision, KnowledgeGraph, RagResponse, Textbook } from "./types";

const BASE_PATH = import.meta.env.BASE_URL.replace(/\/$/, "");
const API_PREFIX = `${BASE_PATH}/api`;

function apiPath(path: string): string {
  return path.startsWith("/api") ? `${API_PREFIX}${path.slice(4)}` : `${BASE_PATH}${path}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(apiPath(path), {
    headers: options?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  config: () => request<ConfigStatus>("/api/config/status"),
  textbooks: () => request<Textbook[]>("/api/textbooks"),
  textbook: (id: string) => request<Textbook>(`/api/textbooks/${id}`),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ textbook: Textbook; graph_stats: Record<string, unknown> }>("/api/upload", {
      method: "POST",
      body: form
    });
  },
  graph: (id: string) => request<KnowledgeGraph>(`/api/knowledge/graph/${id}`),
  mergedGraph: () => request<KnowledgeGraph>("/api/knowledge/graph/merged"),
  extract: (id: string) => request<Record<string, unknown>>(`/api/knowledge/extract/${id}`, { method: "POST" }),
  integrate: () => request<Record<string, unknown>>("/api/integrate/start", { method: "POST" }),
  stats: () => request<Record<string, number | boolean>>("/api/integrate/stats"),
  decisions: () => request<Decision[]>("/api/integrate/decisions"),
  ragIndex: () => request<Record<string, unknown>>("/api/rag/index", { method: "POST" }),
  ragStatus: () => request<Record<string, unknown>>("/api/rag/status"),
  ragQuery: (question: string) =>
    request<RagResponse>("/api/rag/query", {
      method: "POST",
      body: JSON.stringify({ question })
    }),
  chat: (message: string, session_id = "default") =>
    request<RagResponse>("/api/chat/message", {
      method: "POST",
      body: JSON.stringify({ message, session_id })
    }),
  game: () => request<Record<string, unknown>>("/api/game/skill-tree"),
  report: () => request<{ markdown: string }>("/api/report/generate")
};
