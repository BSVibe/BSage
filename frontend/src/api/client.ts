import type {
  ChatRequest,
  ChatResponse,
  ConfigUpdate,
  CredentialFieldsResponse,
  EntryMeta,
  RuntimeConfig,
  VaultFileResponse,
  VaultTreeEntry,
} from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  plugins: () => request<EntryMeta[]>("/plugins"),

  skills: () => request<EntryMeta[]>("/skills"),

  run: (name: string) =>
    request<{ name: string; results: unknown[] }>(`/run/${name}`, { method: "POST" }),

  chat: (body: ChatRequest) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(body) }),

  getConfig: () => request<RuntimeConfig>("/config"),

  updateConfig: (update: ConfigUpdate) =>
    request<RuntimeConfig>("/config", { method: "PATCH", body: JSON.stringify(update) }),

  actions: () => request<string[]>("/vault/actions"),

  // Credential setup
  credentialFields: (name: string) =>
    request<CredentialFieldsResponse>(`/entries/${name}/credentials/fields`),

  storeCredentials: (name: string, credentials: Record<string, string>) =>
    request<{ status: string; name: string }>(`/entries/${name}/credentials`, {
      method: "POST",
      body: JSON.stringify({ credentials }),
    }),

  // Enable/Disable toggle
  toggleEntry: (name: string) =>
    request<{ name: string; enabled: boolean }>(`/entries/${name}/toggle`, { method: "POST" }),

  // Vault browser
  vaultTree: () => request<VaultTreeEntry[]>("/vault/tree"),

  vaultFile: (path: string) =>
    request<VaultFileResponse>(`/vault/file?path=${encodeURIComponent(path)}`),
};
