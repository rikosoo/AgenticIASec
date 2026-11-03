import { describe, expect, it } from "vitest";
import { EVIDENCE_LABEL, filterSensors, IA_INFO, iaLabel, iaState, sensorStatus, STATUS_LABEL, summarize } from "./sensors";
import type { DeviceRow } from "./types";

const NOW = new Date("2026-11-03T12:00:00Z");
const ago = (h: number) => new Date(NOW.getTime() - h * 3_600_000).toISOString();
const dev = (over: Partial<DeviceRow>): DeviceRow => ({ id: "1", hostname: "NB-01", os: "Windows", client_version: "0.1", tools: [], enrolled_at: ago(500), last_seen_at: ago(1), revoked: false, ias: [], activity: {}, ...over });

describe("sensorStatus", () => {
  it("separa ativo, sem atividade, inativo, nunca e revogado pelas bordas de 24 h e 7 dias", () => {
    expect(sensorStatus(dev({ last_seen_at: ago(24) }), NOW)).toBe("ativo");
    expect(sensorStatus(dev({ last_seen_at: ago(25) }), NOW)).toBe("quieto");
    expect(sensorStatus(dev({ last_seen_at: ago(24 * 7) }), NOW)).toBe("quieto");
    expect(sensorStatus(dev({ last_seen_at: ago(24 * 7 + 1) }), NOW)).toBe("inativo");
    expect(sensorStatus(dev({ last_seen_at: null }), NOW)).toBe("nunca");
    expect(sensorStatus(dev({ revoked: true, last_seen_at: ago(1) }), NOW)).toBe("revogado");
  });
  it("todo estado tem rótulo", () => {
    for (const s of ["ativo", "quieto", "inativo", "nunca", "revogado"] as const) expect(STATUS_LABEL[s].length).toBeGreaterThan(3);
  });
});

describe("iaState: só diz 'capturando' com evento de verdade", () => {
  const act = { chatgpt_web: { events_7d: 4, events_30d: 9, last_at: ago(2) }, gemini_web: { events_7d: 0, events_30d: 3, last_at: ago(24 * 10) } };
  it("capturando, parou e aguardando", () => {
    expect(iaState({ activity: act }, "chatgpt_web")).toMatchObject({ evidence: "capturando", events7d: 4, events30d: 9 });
    expect(iaState({ activity: act }, "gemini_web")).toMatchObject({ evidence: "parou", events7d: 0, events30d: 3 });
    expect(iaState({ activity: act }, "claude_web")).toMatchObject({ evidence: "aguardando", lastAt: null });
  });
  it("manual e indisponível não fingem evidência, mesmo que haja evento de outra IA", () => {
    expect(iaState({ activity: { claude_code: { events_7d: 50, events_30d: 50, last_at: ago(1) } } }, "claude_desktop").evidence).toBe("manual");
    expect(iaState({ activity: {} }, "codex_cli").evidence).toBe("manual");
    expect(iaState({ activity: {} }, "codex_desktop").evidence).toBe("indisponivel");
    expect(iaState({ activity: {} }, "copilot_desktop").evidence).toBe("indisponivel");
  });
  it("id desconhecido (sensor mais novo que o console) aparece com o próprio id, sem quebrar", () => {
    const s = iaState({ activity: {} }, "ia_nova");
    expect(s.label).toBe("ia_nova");
    expect(iaLabel("ia_nova")).toBe("ia_nova");
    expect(s.evidence).toBe("manual");
  });
  it("o catálogo do console cobre as 10 IAs do sensor, e cada evidência tem texto", () => {
    expect(Object.keys(IA_INFO).sort()).toEqual(["chatgpt_web", "claude_code", "claude_desktop", "claude_web", "codex_cli", "codex_desktop", "copilot_desktop", "copilot_web", "gemini_web", "github_copilot_cli"]);
    for (const v of Object.values(EVIDENCE_LABEL)) expect(v.length).toBeGreaterThan(3);
  });
});

describe("filterSensors e summarize", () => {
  const list = [
    dev({ id: "a", hostname: "NB-ANA", ias: ["chatgpt_web", "claude_code"], last_seen_at: ago(2) }),
    dev({ id: "b", hostname: "nb-bruno", ias: ["gemini_web"], last_seen_at: ago(100) }),
    dev({ id: "c", hostname: "SRV-10", ias: [], last_seen_at: null }),
    dev({ id: "d", hostname: "NB-DEL", ias: ["chatgpt_web"], revoked: true }),
    dev({ id: "e", hostname: "SRV-2", ias: ["claude_code"], last_seen_at: ago(24 * 20) }),
  ];
  const none = { q: "", ia: "", status: "" as const };
  it("busca por hostname sem diferenciar maiúsculas", () => {
    expect(filterSensors(list, { ...none, q: "nb-" }, NOW).map((d) => d.id)).toEqual(["a", "b", "d"]);
    expect(filterSensors(list, { ...none, q: "  SRV " }, NOW).map((d) => d.id)).toEqual(["e", "c"])   // SRV-2 antes de SRV-10 (ordem natural);
  });
  it("filtra por IA e por situação, juntos", () => {
    expect(filterSensors(list, { ...none, ia: "chatgpt_web" }, NOW).map((d) => d.id)).toEqual(["a", "d"]);
    expect(filterSensors(list, { ...none, ia: "chatgpt_web", status: "ativo" }, NOW).map((d) => d.id)).toEqual(["a"]);
    expect(filterSensors(list, { ...none, status: "revogado" }, NOW).map((d) => d.id)).toEqual(["d"]);
    expect(filterSensors(list, { ...none, ia: "inexistente" }, NOW)).toEqual([]);
  });
  it("ordena por hostname (número natural) ou pelo envio mais recente", () => {
    expect(filterSensors(list, none, NOW).map((d) => d.hostname)).toEqual(["NB-ANA", "nb-bruno", "NB-DEL", "SRV-2", "SRV-10"]);
    expect(filterSensors(list, none, NOW, "recente").map((d) => d.id)[0]).toBe("d");   // d tem last_seen de ago(1) por padrão: o mais recente
  });
  it("resume sem contar revogado no total e conta os sem IA informada", () => {
    expect(summarize(list, NOW)).toEqual({ total: 4, ativo: 1, quieto: 1, inativo: 1, nunca: 1, revogado: 1, semIas: 1 });
  });
});
