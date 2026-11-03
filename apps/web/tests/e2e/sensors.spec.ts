import { expect, test, type Page } from "@playwright/test";
import { expectAccessible, login, USERS } from "./helpers";

const API = "http://127.0.0.1:8099";

async function newToken(page: Page): Promise<string> {
  await page.goto("/devices");
  await page.getByLabel("Nome (ex.: piloto TI)").fill("sensores e2e");
  await page.getByRole("button", { name: "Criar token" }).click();
  const token = (await page.getByTestId("new-token").textContent())!.trim();
  await page.getByRole("button", { name: "Já guardei" }).click();
  return token;
}

async function send(page: Page, key: string, app: string, text: string) {
  const r = await page.request.post(`${API}/v1/events`, {
    headers: { "X-API-Key": key },
    data: {
      event_id: crypto.randomUUID(), occurred_at: new Date().toISOString(),
      source: { channel: app.endsWith("_web") ? "browser" : "agent_hook", app, integration_status: "experimental" },
      actor: { user_id: "pessoa.simulada@empresa-exemplo.com.br" }, kind: "prompt", content: { text },
      context: { session_id: "s1", personal_account: false },
    },
  });
  expect(r.status()).toBe(200);
}

test("sensores: hostname, IAs habilitadas por máquina, evidência de captura, filtros e detalhe", async ({ page }) => {
  await login(page, USERS.admin);
  const token = await newToken(page);
  const enroll = async (hostname: string, ias: string[], tools: string[]) => {
    const r = await page.request.post(`${API}/v1/enroll`, { data: { token, hostname, os: "Windows", client_version: "0.1", tools, ias } });
    expect(r.status()).toBe(201);
    return (await r.json()).api_key as string;
  };
  const keyAna = await enroll("SENS-E2E-ANA", ["chatgpt_web", "claude_code", "codex_cli"], ["claude_code", "browser_extension"]);
  await enroll("SENS-E2E-BRUNO", ["gemini_web"], ["browser_extension"]);
  await enroll("SENS-E2E-LEGADO", [], ["claude_code"]);              // sensor antigo: não informou as IAs
  await send(page, keyAna, "chatgpt_web", "SIMULADO: oi do navegador");
  await send(page, keyAna, "claude_code", "SIMULADO: oi do terminal");

  await page.goto("/sensors");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Sensores");
  await page.getByLabel("Nome da máquina").fill("SENS-E2E");
  const rows = page.getByTestId("sensor-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText("SENS-E2E-ANA");                                 // hostname aparece
  const ana = page.getByRole("row", { name: /SENS-E2E-ANA/ });
  await expect(ana.getByTestId("ia-chip").filter({ hasText: "ChatGPT (web)" })).toContainText("capturando");
  await expect(ana.getByTestId("ia-chip").filter({ hasText: "Claude Code (CLI)" })).toContainText("capturando");
  await expect(ana.getByTestId("ia-chip").filter({ hasText: "Codex (CLI)" })).toContainText("manual");   // sem como provar: não finge
  const bruno = page.getByRole("row", { name: /SENS-E2E-BRUNO/ });
  await expect(bruno.getByTestId("ia-chip")).toContainText("Gemini (web) · aguardando evento");           // habilitada, mas sem evento ainda
  await expect(page.getByRole("row", { name: /SENS-E2E-LEGADO/ })).toContainText("não informado");
  await expect(page.getByTestId("sem-ias")).toContainText("1 sensor");

  // filtro por IA habilitada
  await page.getByLabel("IA habilitada").selectOption("gemini_web");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("SENS-E2E-BRUNO");
  await page.getByRole("button", { name: "Limpar filtros" }).click();
  await page.getByLabel("Nome da máquina").fill("legado");                                  // sem diferenciar maiúsculas
  await expect(rows).toHaveCount(1);
  await page.getByLabel("Nome da máquina").fill("SENS-E2E-ANA");

  // detalhe: eventos por IA
  await page.getByRole("button", { name: "Ver detalhes da máquina SENS-E2E-ANA" }).click();
  const detail = page.getByTestId("sensor-detail");
  await expect(detail).toContainText("SENS-E2E-ANA");
  const chat = detail.getByTestId("ia-detail").getByRole("row", { name: /ChatGPT \(web\)/ });
  await expect(chat).toContainText("extensão do navegador");
  await expect(chat).toContainText("capturando");
  await expect(chat.getByRole("cell").nth(3)).toHaveText("1");                              // 1 evento nos últimos 7 dias
  await expect(detail.getByTestId("ia-detail").getByRole("row", { name: /Codex \(CLI\)/ })).toContainText("configuração manual");
  await expectAccessible(page);
  await page.getByRole("button", { name: "Fechar" }).first().click();

  // revogar sai do total de "instalados" e entra em "revogados"
  const installed = page.getByTestId("sensor-kpis").getByTestId("kpi").filter({ hasText: "Sensores instalados" });
  const before = Number((await installed.locator(".font-mono").textContent())!.trim());
  await page.getByRole("button", { name: "Ver detalhes da máquina SENS-E2E-ANA" }).click();
  page.once("dialog", (d) => void d.accept());
  await page.getByTestId("sensor-detail").getByRole("button", { name: "Revogar" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Máquina revogada." })).toBeVisible();
  await expect(installed.locator(".font-mono")).toHaveText(String(before - 1));
});

test("sensores: leitura vê o painel mas não revoga; tema escuro e tablet sem rolagem horizontal da página", async ({ page }) => {
  await login(page, USERS.leitura);
  await page.goto("/sensors");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Sensores");
  await expect(page.getByTestId("sensor-kpis")).toBeVisible();
  const first = page.getByTestId("sensor-row").first();
  if (await first.count()) {
    await first.getByRole("button").first().click();
    await expect(page.getByTestId("sensor-detail")).toBeVisible();
    await expect(page.getByTestId("sensor-detail").getByRole("button", { name: "Revogar" })).toHaveCount(0);
    await page.getByRole("button", { name: "Fechar" }).first().click();
  }
  await page.setViewportSize({ width: 768, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.getByRole("button", { name: "Tema escuro" }).click();
  await expectAccessible(page);
});
