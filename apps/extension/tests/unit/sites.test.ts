// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { chatgpt } from "../../src/sites/chatgpt";
import { claude } from "../../src/sites/claude";
import { enterSubmits } from "../../src/sites/types";

const page = (html: string) => new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");

describe("módulos de site (seletores A VERIFICAR contra as páginas reais)", () => {
  it("só casam com o próprio domínio", () => {
    expect(chatgpt.matches("chatgpt.com")).toBe(true);
    expect(chatgpt.matches("chatgpt.com.malicioso.test")).toBe(false);
    expect(claude.matches("claude.ai")).toBe(true);
    expect(claude.matches("claude.ai")).toBe(true);
    expect(claude.matches("chatgpt.com")).toBe(false);
  });
  it("chatgpt: acha campo e botão, com alternativas", () => {
    const d = page('<div id="prompt-textarea" contenteditable="true"></div><button data-testid="send-button"></button>');
    expect(chatgpt.findInput(d)?.id).toBe("prompt-textarea");
    expect(chatgpt.findSend(d)?.getAttribute("data-testid")).toBe("send-button");
    const alt = page('<textarea data-testid="prompt-textarea"></textarea><button aria-label="Send prompt"></button>');
    expect(chatgpt.findInput(alt)?.tagName).toBe("TEXTAREA");
    expect(chatgpt.findSend(alt)).not.toBeNull();
  });
  it("claude: acha campo e botão, com alternativas", () => {
    const d = page('<div contenteditable="true" class="ProseMirror"></div><button aria-label="Send message"></button>');
    expect(claude.findInput(d)).not.toBeNull();
    expect(claude.findSend(d)).not.toBeNull();
  });
  it("quando o site muda, devolve null em vez de errar", () => {
    const d = page("<p>nada aqui</p>");
    expect(chatgpt.findInput(d)).toBeNull();
    expect(claude.findSend(d)).toBeNull();
  });
  it("Enter envia; Shift+Enter, Ctrl+Enter e IME não", () => {
    const k = (init: KeyboardEventInit) => new KeyboardEvent("keydown", init);
    expect(enterSubmits(k({ key: "Enter" }))).toBe(true);
    expect(enterSubmits(k({ key: "Enter", shiftKey: true }))).toBe(false);
    expect(enterSubmits(k({ key: "Enter", ctrlKey: true }))).toBe(false);
    expect(enterSubmits(k({ key: "Enter", isComposing: true }))).toBe(false);
    expect(enterSubmits(k({ key: "a" }))).toBe(false);
  });
});
