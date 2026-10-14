"""Injection, jailbreak, extração de system prompt, envenenamento de MCP, exfiltração em texto.

Classificador local (modelo aberto) é opcional via `InjectionClassifier`; nenhum modelo é
empacotado nem baixado (pendente: medir um modelo aberto antes de adotar, ver docs).
"""
from __future__ import annotations

import re
from typing import Protocol

from ..models import Context, Finding


class InjectionClassifier(Protocol):
    def score(self, text: str) -> float: ...


I = re.I  # noqa: E741
IGNORE = re.compile(
    r"(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+|the\s+|your\s+)*(?:previous|prior|above|earlier|system)?\s*"
    r"(?:instructions?|rules?|guidelines?|prompts?)|"
    r"(?:ignor[ea]|desconsidere|esque[çc]a|descarte)\s+(?:todas?\s+)?(?:as\s+)?(?:regras|instru[çc][õo]es|orienta[çc][õo]es)"
    r"(?:\s+anteriores)?|a partir de agora,? (?:voc[êe]|ignore)|you are now (?:in )?(?:a |an )?(?!going)\w+ mode|"
    r"new instructions?:|novas instru[çc][õo]es:", I)
AGENT_ADDRESS = re.compile(
    r"(?:ai|llm|assistant|agent|claude|copilot|assistente)[ ,:]+(?:you must|must|please|should|voc[êe] deve|execute|run)|"
    r"(?:you must|voc[êe] deve) (?:now )?(?:run|execute|send|read|executar|enviar|ler)|"
    r"(?:agora|now) (?:execute|run|envie|send)|"
    r"do not (?:tell|mention|inform) the user|n[ãa]o (?:avise|diga|informe|mencione) (?:ao )?usu[áa]rio|"
    r"ai agent,|agente de ia,", I)
EXFIL_IN_TEXT = re.compile(
    r"!\[[^\]]*\]\(https?://[^)\s]+\?[^)\s]*(?:=|%3d)[^)\s]*\)|"
    r"(?:send|post|upload|envie|enviar|exfiltrate)[^\n]{0,60}?(?:to|para)\s+https?://\S+", I)
SYSPROMPT = re.compile(
    r"(?:repeat|reveal|show|print|output|display|repita|revele|mostre|exiba|imprima|diga)[^.\n]{0,50}"
    r"(?:system prompt|prompt de sistema|prompt do sistema|instru[çc][õo]es (?:do sistema|iniciais|internas)|"
    r"your (?:initial |hidden )?instructions|suas instru[çc][õo]es (?:iniciais|internas|ocultas))|"
    r"what (?:is|are) your (?:system prompt|initial instructions)|qual (?:[ée] )?(?:o )?seu prompt de sistema", I)
JAILBREAK = re.compile(
    r"\bDAN\b(?: mode|,)|do anything now|developer mode (?:enabled|on)|modo (?:DAN|desenvolvedor)|"
    r"(?:you (?:have|are (?:with)?)|voc[êe] (?:n[ãa]o tem|est[áa] sem)|respond|answer|act|responda|aja|atue)[^.\n]{0,25}"
    r"\b(?:no|without|sem)\s+(?:ethical |[ée]ticas? )?(?:restrictions|limitations|restri[çc][õo]es|limites)|"
    r"pretend (?:you|that you) (?:have no|are not bound)|finja que n[ãa]o tem (?:regras|restri[çc][õo]es)|"
    r"without (?:any )?(?:filters|censorship)|sem (?:filtros|censura)", I)
MCP_POISON = re.compile(
    r"<IMPORTANT>|<!--\s*(?:ai|assistant|agent)|before (?:using|calling) this tool,? (?:you must )?(?:read|send|include)|"
    r"antes de usar esta ferramenta,? (?:voc[êe] deve )?(?:ler|leia|envie|inclua)|"
    r"(?:do not|don't|n[ãa]o) (?:mention|tell|reveal|diga|avise|mencione)[^.\n]{0,30}(?:user|usu[áa]rio)|"
    r"read\s+~?/?\.?(?:ssh|aws|env)\S*", I)
HIDDEN_CHARS = re.compile("[\U000e0000-\U000e007f\u200b-\u200f\u2060-\u2064]{3,}")


def detect(ctx: Context, classifier: InjectionClassifier | None = None) -> list[Finding]:
    t, out = ctx.text, []
    indirect = ctx.kind in ("tool_result", "file_upload")
    ign = IGNORE.search(t)
    addr = AGENT_ADDRESS.search(t)
    if ign:
        conf = 0.9 if indirect else 0.85
        if indirect and addr:
            conf = 0.95
        cat = "injection_indireta" if indirect else "injection_direta"
        out.append(Finding(cat, conf, "Instrução para ignorar regras" + (" dentro de conteúdo lido" if indirect else ""),
                           "injection", ign.start(), ign.end(), "[trecho suspeito]"))
    elif indirect and addr and not MCP_POISON.search(t):
        out.append(Finding("injection_indireta", 0.75, "Texto imperativo dirigido ao agente em conteúdo lido",
                           "injection", addr.start(), addr.end(), "[trecho suspeito]"))
    sp = SYSPROMPT.search(t)
    if sp:
        out.append(Finding("extracao_system_prompt", 0.85, "Pedido para revelar o prompt do sistema",
                           "injection", sp.start(), sp.end(), "[trecho suspeito]"))
    jb = JAILBREAK.search(t)
    if jb:
        out.append(Finding("jailbreak", 0.8, "Padrão de jailbreak", "injection", jb.start(), jb.end(), "[trecho suspeito]"))
    poison = MCP_POISON.search(t)
    if poison and (indirect or ctx.kind == "tool_call" or ctx.tool_name or "<IMPORTANT>" in t):
        out.append(Finding("envenenamento_mcp", 0.85, "Instrução oculta em descrição/resultado de ferramenta",
                           "injection", poison.start(), poison.end(), "[trecho suspeito]"))
    hc = HIDDEN_CHARS.search(t)
    if hc:
        out.append(Finding("envenenamento_mcp", 0.8, "Sequência de caracteres invisíveis (possível instrução oculta)",
                           "hidden_chars", hc.start(), hc.end(), "[caracteres ocultos]"))
    ex = EXFIL_IN_TEXT.search(t)
    if ex and (indirect or addr or ign):
        out.append(Finding("exfiltracao_ferramenta", 0.8, "Envio de dados para URL externa instruído no texto",
                           "injection", ex.start(), ex.end(), "[trecho suspeito]"))
    if classifier is not None and not any(f.category.startswith("injection") for f in out):
        s = classifier.score(t)
        if s >= 0.5:
            out.append(Finding("injection_indireta" if indirect else "injection_direta", min(s, 0.99),
                               "Classificador local de injection"))
    return out
