import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeAll, describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "../..");
const prod = (f: string) => readFileSync(resolve(root, "dist/prod", f), "utf8");

describe("build de produção", () => {
  beforeAll(() => {
    execFileSync("node", ["build.mjs"], { cwd: root, stdio: "ignore" });
  }, 60_000);

  it("só injeta em chatgpt.com e claude.ai, sem hosts extras", () => {
    const m = JSON.parse(prod("manifest.json"));
    expect(m.content_scripts[0].matches).toEqual(["https://chatgpt.com/*", "https://claude.ai/*"]);
    expect(m.host_permissions).toBeUndefined();
    expect(m.permissions.sort()).toEqual(["alarms", "identity", "identity.email", "storage"]);
    expect(m.storage.managed_schema).toBe("managed_schema.json");
    expect(m.options_page).toBeUndefined();
  });
  it("não leva nada de teste: site local, configuração local, shadow DOM aberto", () => {
    const code = prod("content.js") + prod("background.js");
    expect(code).not.toContain("127.0.0.1");
    expect(code).not.toContain("devConfig");
    expect(code).not.toContain("localtest");
    expect(code).toContain('mode:"closed"');
  });
  it("o content script não conhece a chave de API", () => {
    expect(prod("content.js")).not.toContain("X-API-Key");
    expect(prod("content.js")).not.toContain("api_key");
  });
});
