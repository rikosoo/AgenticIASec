"""PII brasileira e dados financeiros. Presidio (nomes e endereços) NÃO está ligado: pendente."""
from __future__ import annotations

import re

from ..models import Context, Finding
from ..validators import card_plausible, cnpj_valid, cpf_valid, digits

CPF_RE = re.compile(r"(?<![\d.\-/])(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{11})(?![\d]|[.\-/]\d)")
CNPJ_RE = re.compile(r"(?<![\d.\-/])(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})(?![\d]|[.\-/]\d)")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
PHONE_RE = re.compile(r"(?<![\d])(?:\+55[ -]?)?\(?\d{2}\)?[ -]?9?\d{4}[ -]\d{4}(?!\d)|\+55\d{10,11}")
RG_RE = re.compile(r"(?<![\d.])\d{1,2}\.\d{3}\.\d{3}-?[\dxX](?![\d])")
CARD_RE = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
BANK_RE = re.compile(r"ag[eê]ncia\W{0,3}\d{3,5}\W{0,12}conta\W{0,3}\d{4,}-?\d?", re.I)
# Número declarado como documento ("meu cpf é 3444353432123"): é dado pessoal mesmo com dígito inválido,
# erro de digitação ou tamanho errado. Só vale quando a palavra vem ANTES do número.
CPF_DECL_RE = re.compile(r"(?i)\b(?:cpf|c\.p\.f)\b[^\d\n.;]{0,20}?(\d[\d.\-]{6,17}\d)")
CNPJ_DECL_RE = re.compile(r"(?i)\bcnpj\b[^\d\n.;]{0,20}?(\d[\d.\-/]{9,20}\d)")
RG_DECL_RE = re.compile(r"(?i)\b(?:rg|identidade|registro geral)\b[^\d\n.;]{0,15}?(\d[\d.\-]{4,13}[\dxX])")
CEP_RE = re.compile(r"(?<![\d-])\d{5}-\d{3}(?![\d-])")
ADDR_PT_RE = re.compile(
    r"\b(?:Rua|R\.|Avenida|Av\.|Alameda|Travessa|Pra[çc]a|Estrada|Rodovia)\s+[^,\n\d]{3,50}?,?\s*(?:n[ºo°.]?\s*)?\d{1,5}\b")
ADDR_EN_RE = re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Drive)\b")
CTX_CPF = re.compile(r"cpf|c\.p\.f|cadastro de pessoa", re.I)
CTX_CNPJ = re.compile(r"cnpj", re.I)
CTX_RG = re.compile(r"\brg\b|identidade|registro geral", re.I)


def _near(text: str, start: int, end: int, ctx: re.Pattern[str], window: int = 25) -> bool:
    return bool(ctx.search(text[max(0, start - window):end + 5]))


def detect(ctx: Context) -> list[Finding]:
    t, out = ctx.text, []
    for m in CPF_RE.finditer(t):
        raw = m.group(1)
        if not cpf_valid(raw):
            continue
        formatted = "." in raw
        if formatted:
            conf = 0.97
        elif _near(t, m.start(), m.end(), CTX_CPF):
            conf = 0.9
        else:
            conf = 0.55  # 11 dígitos válidos sem pontuação nem contexto: pode ser telefone
        out.append(Finding("pii", conf, "CPF com dígito verificador válido", "cpf",
                           m.start(1), m.end(1), "***.***.***-" + digits(raw)[-2:]))
    for m in CNPJ_RE.finditer(t):
        raw = m.group(1)
        if not cnpj_valid(raw):
            continue
        conf = 0.95 if "/" in raw or _near(t, m.start(), m.end(), CTX_CNPJ) else 0.6
        out.append(Finding("pii", conf, "CNPJ com dígito verificador válido", "cnpj",
                           m.start(1), m.end(1), "**.***.***/****-" + digits(raw)[-2:]))
    for m in RG_RE.finditer(t):
        if _near(t, m.start(), m.end(), CTX_RG, 20):
            out.append(Finding("pii", 0.85, "RG com contexto", "rg", m.start(), m.end(), "**.***.***-*"))
    for rx, lo, hi, kind, label, masked in (
        (CPF_DECL_RE, 9, 14, "cpf", "CPF informado (dígito verificador inválido ou formato incomum)", "[CPF]"),
        (CNPJ_DECL_RE, 12, 16, "cnpj", "CNPJ informado (dígito verificador inválido ou formato incomum)", "[CNPJ]"),
        (RG_DECL_RE, 6, 12, "rg", "RG informado", "[RG]"),
    ):
        for m in rx.finditer(t):
            if lo <= len(digits(m.group(1))) <= hi:
                out.append(Finding("pii", 0.8, label, kind, m.start(1), m.end(1), masked))
    for m in EMAIL_RE.finditer(t):
        out.append(Finding("pii", 0.75, "Endereço de e-mail", "email", m.start(), m.end(),
                           "***@" + m.group().split("@")[1]))
    for m in PHONE_RE.finditer(t):
        d = digits(m.group())
        if 10 <= len(d) <= 13:
            out.append(Finding("pii", 0.7, "Telefone brasileiro", "telefone", m.start(), m.end(),
                               "(**) *****-" + d[-4:]))
    for m in CARD_RE.finditer(t):
        d = digits(m.group())
        if card_plausible(d) and not (len(d) == 11 or cpf_valid(d)):
            out.append(Finding("financeiro", 0.93, "Número de cartão com Luhn válido", "cartao",
                               m.start(), m.end(), "**** **** **** " + d[-4:]))
    for m in ADDR_PT_RE.finditer(t):
        out.append(Finding("pii", 0.8, "Endereço residencial ou comercial", "endereco", m.start(), m.end(), "[endereço]"))
    for m in ADDR_EN_RE.finditer(t):
        out.append(Finding("pii", 0.75, "Street address", "endereco", m.start(), m.end(), "[endereço]"))
    for m in CEP_RE.finditer(t):
        out.append(Finding("pii", 0.7, "CEP", "cep", m.start(), m.end(), "*****-***"))
    for m in BANK_RE.finditer(t):
        out.append(Finding("financeiro", 0.8, "Agência e conta bancária", "conta_bancaria",
                           m.start(), m.end(), "[conta bancária]"))
    return out
