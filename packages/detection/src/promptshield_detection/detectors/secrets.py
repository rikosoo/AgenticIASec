"""Segredos: formatos conhecidos, entropia perto de palavras-chave, exemplos de documentação."""
from __future__ import annotations

import re

from ..models import Context, Finding
from ..validators import entropy

DOC_EXAMPLES = {
    "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
}
PLACEHOLDER = re.compile(
    r"(?i)^(?:x{4,}|\*{3,}|\.{3,}|<.*>|\$\{.*\}|\{\{.*\}\}|your[-_ ]|change[-_]?me|example|exemplo|"
    r"placeholder|senha|password|secret|token|dummy|test(?:e)?$|todo)")

RULES: list[tuple[re.Pattern[str], str, str, float, str]] = [
    (re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{16}\b"), "aws_access_key", "Chave de acesso AWS", 0.97, "AKIA****"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "gcp_api_key", "Chave de API do Google", 0.93, "AIza****"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"), "github_token", "Token do GitHub", 0.98, "gh*_****"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "slack_token", "Token do Slack", 0.97, "xox*-****"),
    (re.compile(r"\b[sr]k_live_[A-Za-z0-9]{16,}\b"), "stripe_key", "Chave Stripe de produção", 0.98, "sk_live_****"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "jwt", "JWT", 0.85, "eyJ****"),
    (re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY(?: BLOCK)?-----"), "private_key", "Chave privada", 0.99, "-----BEGIN ****-----"),
    (re.compile(r"AccountKey=[A-Za-z0-9+/]{40,}={0,2}"), "azure_storage_key", "Chave de conta Azure Storage", 0.96, "AccountKey=****"),
    (re.compile(r"(?i)\bsig=[A-Za-z0-9%+/]{30,}={0,2}"), "azure_sas", "Assinatura SAS do Azure", 0.9, "sig=****"),
    (re.compile(r"(?i)aws_secret_access_key\W{0,4}([A-Za-z0-9/+=]{40})\b"), "aws_secret_key", "Chave secreta AWS", 0.96, "****"),
    (re.compile(r'"private_key"\s*:\s*"-----BEGIN'), "gcp_service_account", "Service account do GCP", 0.98, '"private_key": "****'),
]
CONN_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://([^\s:@/]+):([^\s@/]{3,})@[^\s]+", re.I)
KEYWORD_RE = re.compile(
    r"(?i)(?:api[_-]?key|secret|token|passw(?:or)?d|passwd|senha|credential|access[_-]?key|auth)"
    r"[\w-]*\s*[:=]\s*[\"']?([A-Za-z0-9/+_\-=.]{16,})[\"']?")


def _placeholder(value: str) -> bool:
    return bool(PLACEHOLDER.match(value)) or len(set(value)) <= 3


def detect(ctx: Context) -> list[Finding]:
    t, out, taken = ctx.text, [], []
    for rx, span_type, rule, conf, masked in RULES:
        for m in rx.finditer(t):
            value = m.group(1) if m.groups() else m.group(0)
            c = conf
            if value in DOC_EXAMPLES or "EXAMPLE" in value:
                c, rule_txt = 0.25, rule + " (igual ao exemplo da documentação)"
            elif _placeholder(value.split("_", 1)[-1]):
                c, rule_txt = 0.2, rule + " (placeholder)"
            else:
                rule_txt = rule
            s, e = (m.start(1), m.end(1)) if m.groups() else (m.start(), m.end())
            out.append(Finding("segredo", c, rule_txt, span_type, s, e, masked))
            taken.append((s, e))
    for m in CONN_RE.finditer(t):
        if _placeholder(m.group(2)) or m.group(2).startswith(("$", "{", "<")):
            continue
        out.append(Finding("segredo", 0.9, "String de conexão com senha", "conn_string",
                           m.start(), m.end(), "****://usuario:****@…"))
        taken.append((m.start(), m.end()))
    for m in KEYWORD_RE.finditer(t):
        value = m.group(1)
        if any(a <= m.start(1) < b for a, b in taken) or value in DOC_EXAMPLES:
            continue
        if _placeholder(value) or entropy(value) < 3.3:
            continue
        out.append(Finding("segredo", 0.8, "Valor de alta entropia perto de palavra-chave de segredo",
                           "high_entropy", m.start(1), m.end(1), value[:2] + "****"))
    return out
