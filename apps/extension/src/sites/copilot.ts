import { enterSubmits, firstMatch, type SiteModule } from "./types";

// A VERIFICAR: seletores escritos a partir do conhecimento do site, NÃO conferidos contra a página real
// (copilot.microsoft.com não é acessível do ambiente de desenvolvimento). Integração EXPERIMENTAL.
// Cobre só o Microsoft Copilot na web. O GitHub Copilot em github.com/copilot NÃO é coberto (um módulo por host inteiro injetaria em todo o github.com).
const INPUT = ["textarea#userInput", 'textarea[data-testid="composer-input"]', 'textarea[placeholder]', 'div[contenteditable="true"][role="textbox"]'];
const SEND = ['button[data-testid="submit-button"]', 'button[aria-label="Submit message"]', 'button[title="Submit message"]', 'button[aria-label="Enviar mensagem"]'];

export const copilot: SiteModule = {
  id: "copilot",
  app: "copilot_web",
  matches: (h) => h === "copilot.microsoft.com",
  findInput: (doc) => firstMatch(doc, INPUT),
  findSend: (doc) => firstMatch(doc, SEND),
  isSubmitKey: enterSubmits,
};
