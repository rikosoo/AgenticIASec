import type { Action, IncidentStatus, Severity } from "./types";

export const SEVERITY_LABEL: Record<Severity, string> = { baixo: "Baixo", medio: "Médio", alto: "Alto", critico: "Crítico" };
export const SEVERITY_CLASS: Record<Severity, string> = {
  baixo: "bg-low-bg text-low", medio: "bg-med-bg text-med", alto: "bg-high-bg text-high", critico: "bg-crit-bg text-crit",
};
export const STATUS_LABEL: Record<IncidentStatus, string> = { aberto: "Aberto", "em analise": "Em análise", resolvido: "Resolvido", "falso positivo": "Falso positivo" };
export const STATUSES = Object.keys(STATUS_LABEL) as IncidentStatus[];
export const ACTION_LABEL: Record<Action, string> = {
  allow: "Permitir", mask: "Mascarar", block: "Bloquear", ask_justification: "Pedir justificativa", alert: "Alertar",
};
export const ROLE_LABEL = { admin: "Administrador", analista: "Analista", auditor: "Auditor", leitura: "Leitura" } as const;
export const APP_LABEL: Record<string, string> = {
  claude_code: "Claude Code", chatgpt_web: "ChatGPT (web)", claude_web: "Claude (web)", cursor: "Cursor",
};

export const appLabel = (a: string) => APP_LABEL[a] ?? a;

/** Severidade a partir do score (mesma régua da API: 80+ crítico, 60+ alto, 30+ médio). */
export function severityOf(score: number): Severity {
  return score >= 80 ? "critico" : score >= 60 ? "alto" : score >= 30 ? "medio" : "baixo";
}
