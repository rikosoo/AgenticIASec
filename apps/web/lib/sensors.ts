import type { AppActivity, DeviceRow } from "./types";

/** Como cada IA do catálogo do sensor é monitorada (espelha packages/adapters/claude_code_hook/.../ias.py). `app` liga a IA ao `source.app` dos eventos. */
export type IaMode = "automatico" | "extensao" | "manual" | "indisponivel";
export const IA_INFO: Record<string, { label: string; mode: IaMode; app?: string }> = {
  chatgpt_web: { label: "ChatGPT (web)", mode: "extensao", app: "chatgpt_web" },
  copilot_web: { label: "Copilot (web)", mode: "extensao", app: "copilot_web" },
  gemini_web: { label: "Gemini (web)", mode: "extensao", app: "gemini_web" },
  codex_desktop: { label: "Codex (app desktop)", mode: "indisponivel" },
  claude_desktop: { label: "Claude (app desktop)", mode: "manual" },
  claude_code: { label: "Claude Code (CLI)", mode: "automatico", app: "claude_code" },
  codex_cli: { label: "Codex (CLI)", mode: "manual" },
  copilot_desktop: { label: "Copilot (app desktop)", mode: "indisponivel" },
  github_copilot_cli: { label: "GitHub Copilot CLI", mode: "automatico", app: "github_copilot_cli" },
  claude_web: { label: "Claude (web)", mode: "extensao", app: "claude_web" },
};
export const MODE_LABEL: Record<IaMode, string> = { automatico: "automática", extensao: "extensão do navegador", manual: "configuração manual", indisponivel: "indisponível hoje" };
export const iaLabel = (id: string) => IA_INFO[id]?.label ?? id;

/** O que se sabe de uma IA numa máquina. "capturando" só quando chegou evento de verdade; o resto é honesto sobre o que falta. */
export type IaEvidence = "capturando" | "parou" | "aguardando" | "manual" | "indisponivel";
export const EVIDENCE_LABEL: Record<IaEvidence, string> = {
  capturando: "capturando", parou: "sem eventos há mais de 7 dias", aguardando: "aguardando o primeiro evento", manual: "manual, sem como confirmar", indisponivel: "indisponível hoje",
};

export interface IaState { id: string; label: string; mode: IaMode; evidence: IaEvidence; events7d: number; events30d: number; lastAt: string | null }

export function iaState(d: Pick<DeviceRow, "activity">, id: string): IaState {
  const info = IA_INFO[id] ?? { label: id, mode: "manual" as IaMode };
  const act: AppActivity | undefined = info.app ? d.activity?.[info.app] : undefined;
  let evidence: IaEvidence;
  if (info.mode === "indisponivel") evidence = "indisponivel";
  else if (!info.app) evidence = "manual";
  else if (act && act.events_7d > 0) evidence = "capturando";
  else if (act && act.events_30d > 0) evidence = "parou";
  else evidence = "aguardando";
  return { id, label: info.label, mode: info.mode, evidence, events7d: act?.events_7d ?? 0, events30d: act?.events_30d ?? 0, lastAt: act?.last_at ?? null };
}

/** O sensor só fala com o servidor quando alguém usa uma IA: "sem atividade" NÃO quer dizer que quebrou. */
export type SensorStatus = "ativo" | "quieto" | "inativo" | "nunca" | "revogado";
export const STATUS_LABEL: Record<SensorStatus, string> = {
  ativo: "Ativo (24 h)", quieto: "Sem atividade (1 a 7 dias)", inativo: "Inativo (mais de 7 dias)", nunca: "Nunca enviou", revogado: "Revogado",
};
const DAY = 86_400_000;

export function sensorStatus(d: Pick<DeviceRow, "revoked" | "last_seen_at">, now: Date): SensorStatus {
  if (d.revoked) return "revogado";
  if (!d.last_seen_at) return "nunca";
  const age = now.getTime() - new Date(d.last_seen_at).getTime();
  return age <= DAY ? "ativo" : age <= 7 * DAY ? "quieto" : "inativo";
}

export interface SensorFilter { q: string; ia: string; status: SensorStatus | "" }
export type SensorSort = "hostname" | "recente";

export function filterSensors(devices: DeviceRow[], f: SensorFilter, now: Date, sort: SensorSort = "hostname"): DeviceRow[] {
  const q = f.q.trim().toLowerCase();
  const out = devices.filter((d) =>
    (!q || d.hostname.toLowerCase().includes(q)) &&
    (!f.ia || (d.ias ?? []).includes(f.ia)) &&
    (!f.status || sensorStatus(d, now) === f.status));
  return out.sort(sort === "recente"
    ? (a, b) => (b.last_seen_at ?? "").localeCompare(a.last_seen_at ?? "") || a.hostname.localeCompare(b.hostname, "pt-BR")
    : (a, b) => a.hostname.localeCompare(b.hostname, "pt-BR", { numeric: true }));
}

export interface SensorSummary { total: number; ativo: number; quieto: number; inativo: number; nunca: number; revogado: number; semIas: number }

export function summarize(devices: DeviceRow[], now: Date): SensorSummary {
  const s: SensorSummary = { total: 0, ativo: 0, quieto: 0, inativo: 0, nunca: 0, revogado: 0, semIas: 0 };
  for (const d of devices) {
    const st = sensorStatus(d, now);
    s[st] += 1;
    if (st !== "revogado") {
      s.total += 1;
      if (!(d.ias ?? []).length) s.semIas += 1;
    }
  }
  return s;
}
