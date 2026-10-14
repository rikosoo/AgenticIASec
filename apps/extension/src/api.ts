import type { ApiResult, FullConfig } from "./types";

export interface PromptInput {
  app: string;
  text: string;
  sessionPath: string;
}

export function buildEvent(input: PromptInput, cfg: FullConfig, installId: string, profileEmail: string, now = new Date()) {
  const actor: Record<string, unknown> = { user_id: profileEmail || cfg.userId || "desconhecido", device_id: installId };
  if (cfg.department) actor.department = cfg.department;
  return {
    event_id: crypto.randomUUID(),
    occurred_at: now.toISOString(),
    // integração por extensão: EXPERIMENTAL (seletores dos sites não verificados contra as páginas reais)
    source: { channel: "browser", app: input.app, integration_status: "experimental" },
    actor,
    kind: "prompt",
    content: { text: input.text },
    // a extensão não sabe se a conta do site é pessoal ou corporativa
    context: { session_id: input.sessionPath.slice(0, 200) || null, personal_account: false },
  };
}

async function call<T>(cfg: FullConfig, method: string, path: string, body?: unknown, expectJson = true): Promise<T> {
  if (!cfg.apiUrl || !cfg.apiKey) throw new Error("extensão sem configuração (api_url e api_key)");
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), cfg.timeoutMs);
  try {
    const r = await fetch(cfg.apiUrl + path, {
      method,
      signal: ctl.signal,
      headers: { "X-API-Key": cfg.apiKey, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`API respondeu ${r.status}`);
    return (expectJson ? await r.json() : undefined) as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw new Error("tempo esgotado ao consultar a API");
    throw e instanceof Error ? e : new Error(String(e));
  } finally {
    clearTimeout(timer);
  }
}

export const postEvent = (cfg: FullConfig, event: unknown) => call<ApiResult>(cfg, "POST", "/v1/events", event);
export const postJustification = (cfg: FullConfig, eventId: string, justification: string) =>
  call<void>(cfg, "POST", `/v1/events/${eventId}/justification`, { justification }, false);
export const getRemoteConfig = (cfg: FullConfig) =>
  call<{ failure_mode: "open" | "closed"; domains: string[]; policy_url: string | null }>(cfg, "GET", "/v1/extension-config");
