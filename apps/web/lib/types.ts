/** Formatos devolvidos pela API (apps/api). Nenhum valor fixo: tudo vem de /v1/*. */
export type Role = "admin" | "analista" | "auditor" | "leitura";
export type Severity = "baixo" | "medio" | "alto" | "critico";
export type IncidentStatus = "aberto" | "em analise" | "resolvido" | "falso positivo";
export type Action = "allow" | "mask" | "block" | "ask_justification" | "alert";

export interface Me { kind: string; id: string; tenant_id: string; role: Role | null; email: string | null }
export interface Tenant {
  id: string; name: string; failure_mode: "open" | "closed"; retention_days: number; store_original: boolean;
  policy_url: string | null; monitored_domains: string[]; is_demo: boolean; volume_threshold_per_hour: number;
}
export interface Category { id: string; confidence: number }
export interface TaxonomyItem { id: string; nome: string; grupo: string; risco_padrao: string }

export interface Overview {
  days: number;
  high_risk_threshold: number;
  totals: { events: number; high_risk: number; with_code: number; with_sensitive: number; agent_actions: number; blocked: number; would_block: number; users: number };
  daily: { date: string; events: number; high_risk: number }[];
  by_department: { department: string; events: number; high_risk: number }[];
  by_app: { app: string; corporate: number; personal: number }[];
}

export interface PromptRow {
  event_id: string; occurred_at: string; app: string; channel: string; user_id: string; department: string | null; kind: string;
  personal_account: boolean; masked_text: string; has_original: boolean; categories: Category[];
  flags: { has_code: boolean; has_sensitive: boolean; is_agent_action: boolean };
  risk_score: number; reasons: { rule: string; contribution: number; category?: string }[];
  decision: Action; would_decide: Action; policy_hits: { policy_id: string; name: string; action: string; mode: string }[];
  incident_id: string | null;
}

export interface Incident {
  id: string; severity: Severity; status: IncidentStatus; assignee_id: string | null; assignee_email: string | null; confidence: number;
  created_at: string; event_id: string; user_id: string; app: string; department: string | null; personal_account: boolean;
  masked_text: string; has_original: boolean; categories: Category[]; risk_score: number;
  reasons: { rule: string; contribution: number }[]; decision: Action; would_decide: Action;
  timeline?: { at: string; what: string }[]; recommendations?: string[];
}

export interface Policy {
  id: string; name: string; description: string | null; enabled: boolean; scope: Record<string, string[]>;
  match: { categories?: string[]; min_confidence?: number; min_score?: number }; action: Action; mode: "monitor" | "enforce";
  version: number; updated_at: string;
}
export type PolicyDraft = Omit<Policy, "id" | "version" | "updated_at">;

export interface Simulation {
  days: number; events_in_period: number; events_evaluated: number; truncated: boolean; matched: number; matched_users: number;
  would_be_stronger_than_current: number; examples: { event_id: string; user_id: string; risk_score: number; masked_text: string; current_decision: string }[];
  action: string; mode: string; ignored_scope: string[]; note: string;
}
export interface DirectoryUser { id: string; email: string; display_name: string | null; role: Role }

export interface RiskUser { user_id: string; department: string | null; score: number; reasons: { rule: string; contribution: number }[]; events: number; high_events: number; series: number[] }
export interface RiskDept { department: string; score: number; users: number; users_high: number; events: number; series: number[] }
export interface RiskStats { score_version: string; disclaimer: string; days: string[]; users: RiskUser[]; departments: RiskDept[] }

export interface AlertRow {
  id: string; rule: string; rule_label: string; severity: Severity; title: string; user_id: string; department: string | null;
  count: number; first_seen: string; last_seen: string; incident_id: string | null; score: number | null; categories: string[];
}
export type ChannelKind = "webhook" | "slack" | "teams" | "email" | "syslog_cef" | "siem_webhook";
export interface Channel {
  id: string; kind: ChannelKind; name: string; target: string; enabled: boolean; integration_status: "real" | "parcial" | "experimental";
  min_severity: Severity | null; min_score: number | null; proto: string | null; has_secret: boolean; outbox: Record<string, number>;
}
export interface ReportRow { id: string; kind: "executivo" | "lgpd"; format: "pdf" | "csv"; period_start: string; period_end: string; sha256: string; created_by: string; created_at: string; size: number; scheduled: boolean }
export interface ScheduleRow { id: string; kind: "executivo" | "lgpd"; format: "pdf" | "csv"; frequency: "mensal" | "semanal"; recipients: string[]; enabled: boolean; last_period_end: string | null }
