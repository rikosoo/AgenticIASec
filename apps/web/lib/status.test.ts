import { describe, expect, it } from "vitest";
import { parseHealth } from "./status";

describe("parseHealth", () => {
  it("reconhece a resposta saudável", () => {
    expect(parseHealth({ status: "ok" })).toBe("ok");
  });
  it("trata qualquer outra coisa como indisponível", () => {
    expect(parseHealth(null)).toBe("indisponivel");
    expect(parseHealth({ status: "erro" })).toBe("indisponivel");
  });
});
