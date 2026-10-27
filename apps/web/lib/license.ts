import type { LicenseStateId, LicenseStatus } from "./types";

export interface LicenseNotice { level: "crit" | "warn"; title: string; text: string; href: string }

export const STATE_LABEL: Record<LicenseStateId, string> = {
  nao_ativado: "Não ativado", ativo: "Ativo", sem_contato: "Sem contato com o licenciamento", em_tolerancia: "Em tolerância", expirado: "Expirado", encerrado: "Encerrado",
};

/** O que cada estado permite, em palavras que o administrador entende (espelha packages/licensing/states.py; nada apaga dados). */
export const STATE_EFFECT: Record<LicenseStateId, string> = {
  nao_ativado: "Sem inspeção e sem matrícula de máquinas até informar o código de ativação. Consulta e exportação funcionam.",
  ativo: "Tudo funciona conforme o contrato.",
  sem_contato: "Tudo funciona com a autorização local, que ainda vale. O servidor tenta renovar sozinho.",
  em_tolerancia: "Tudo funciona. O contrato venceu e há um prazo para regularizar.",
  expirado: "Novas máquinas não podem ser matriculadas. A inspeção, a consulta e a exportação continuam.",
  encerrado: "Novas máquinas não podem ser matriculadas. A inspeção segue o que o contrato prevê; consulta e exportação continuam.",
};

/** Faixa de aviso para o console. Estado ativo, ou licenciamento desligado (SaaS/desenvolvimento), não mostra nada. */
export function licenseNotice(s: LicenseStatus | undefined | null): LicenseNotice | null {
  if (!s || s.mode !== "onprem" || s.state === "ativo") return null;
  const href = "/license";
  switch (s.state) {
    case "nao_ativado": return { level: "crit", title: "Instalação sem ativação", text: s.message, href };
    case "sem_contato": return { level: "warn", title: "Sem contato com o licenciamento", text: s.message, href };
    case "em_tolerancia": return { level: "warn", title: "Contrato vencido, em tolerância", text: s.message, href };
    case "expirado": return { level: "crit", title: "Licença expirada", text: s.message, href };
    case "encerrado": return { level: "crit", title: s.inspecting ? "Contrato encerrado" : "Contrato encerrado: inspeção parada", text: s.message, href };
  }
}
