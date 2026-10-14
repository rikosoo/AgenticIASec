"""Categorias de negócio e conformidade por dicionários. São as mais frágeis: ver relatório."""
from __future__ import annotations

import re

from ..models import Context, Finding


def _terms(*words: str) -> re.Pattern[str]:
    return re.compile(r"(?i)\b(?:" + "|".join(words) + r")\b")


HEALTH_STRONG = _terms(r"prontu[áa]rio", r"cid-?10", r"diagn[óo]stico", r"laudo m[ée]dico", r"medical record",
                       r"diagnosis", r"hiv", r"hemograma", r"receita m[ée]dica", r"prescription", r"exame de sangue")
HEALTH_WEAK = _terms(r"paciente", r"patient", r"medica[çc][ãa]o", r"medication", r"\d+\s?mg", r"sintomas?", r"symptoms?",
                     r"tratamento", r"treatment", r"cirurgia", r"surgery", r"diabetes", r"hipertens[ãa]o", r"c[âa]ncer")
CID_CODE = re.compile(r"\bCID[-: ]*[A-TV-Z]\d{2}(?:\.\d)?\b", re.I)
HR_TERMS = _terms(r"folha de pagamento", r"payroll", r"sal[áa]rio", r"salary", r"avalia[çc][ãa]o de desempenho",
                  r"performance review", r"demiss[ãa]o", r"desligamento", r"termination", r"advert[êe]ncia",
                  r"b[ôo]nus", r"plano de carreira", r"banco de horas", r"atestado", r"admiss[ãa]o")
CLIENT_TERMS = _terms(r"lista de clientes", r"base de clientes", r"customer list", r"export(?:a[çc][ãa]o)? do crm",
                      r"customer database", r"carteira de clientes")
MA_TERMS = _terms(r"due diligence", r"term sheet", r"valuation", r"fus[ãa]o", r"aquisi[çc][ãa]o", r"merger",
                  r"acquisition", r"m&a", r"carta de inten[çc][ãa]o", r"letter of intent", r"oferta p[úu]blica",
                  r"data room", r"cap table")
MA_STRONG = _terms(r"due diligence", r"term sheet", r"data room", r"m&a")
LEGAL_TERMS = _terms(r"cl[áa]usula", r"rescis[ãa]o", r"lit[íi]gio", r"contrato social", r"nda", r"acordo de confidencialidade",
                     r"parecer jur[íi]dico", r"indeniza[çc][ãa]o", r"liminar", r"contract clause", r"lawsuit",
                     r"settlement", r"arbitragem", r"procura[çc][ãa]o")
CNJ = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
IP_TERMS = _terms(r"patente", r"patent", r"segredo industrial", r"trade secret", r"propriedade intelectual",
                  r"intellectual property", r"f[óo]rmula (?:secreta|propriet[áa]ria)", r"know-how propriet[áa]rio",
                  r"pedido de patente", r"prot[óo]tipo confidencial")
TOXIC = re.compile(
    r"(?i)\b(?:idiota|imbecil|in[úu]til|burro|estúpido|vagabund[oa]|idiot|moron|stupid|shut up|piece of trash)\b|"
    r"vou (?:te )?(?:matar|acabar com voc[êe]|destruir voc[êe])|i(?:'ll| will) (?:kill|destroy) you|"
    r"(?:voc[êe]|you) (?:[ée]|are) (?:um |uma |a |an )?(?:lixo|fracassad[oa]|loser|worthless)")
PERSONAL = _terms(r"receita de (?:bolo|pão|torta|macarr[ãa]o)", r"horóscopo", r"hor[óo]scopo", r"viagem de f[ée]rias",
                  r"recipe for", r"horoscope", r"meu namorad[oa]", r"minha namorad[oa]", r"my boyfriend", r"my girlfriend",
                  r"presente de anivers[áa]rio", r"birthday gift", r"fim de semana", r"weekend plans", r"filme para assistir",
                  r"time de futebol", r"jogo de ontem")
WORK = _terms(r"resum[ae]\w*", r"summari[sz]e", r"traduz\w*", r"translate", r"escreva (?:um|uma) (?:e-?mail|texto|relat[óo]rio)",
              r"draft (?:an? )?(?:email|memo)", r"explique", r"explain", r"refator\w*", r"refactor", r"teste?s? (?:unit[áa]rios?|em pytest)",
              r"unit tests?", r"ata de reuni[ãa]o", r"meeting notes", r"t[íi]tulo para", r"formate", r"corrija o texto",
              r"proofread", r"pytest", r"o que [ée]", r"what is", r"diferen[çc]a entre", r"difference between", r"como (?:fa[çc]o|escrevo|uso)",
              r"how (?:do i|to)", r"rod[ae] os testes", r"corrij\w+", r"run the tests", r"fix the")


def _count(rx: re.Pattern[str], t: str) -> int:
    return len({m.group().lower() for m in rx.finditer(t)})


def detect(ctx: Context) -> list[Finding]:
    t, out = ctx.text, []
    strong, weak = _count(HEALTH_STRONG, t), _count(HEALTH_WEAK, t)
    if CID_CODE.search(t) or strong >= 2 or (strong >= 1 and weak >= 1):
        out.append(Finding("saude", 0.85 if CID_CODE.search(t) or strong >= 2 else 0.7, "Termos clínicos"))
    if _count(HR_TERMS, t) >= 2 or (_count(HR_TERMS, t) >= 1 and re.search(r"R\$\s?\d|\d+\s?(?:mil|k)\b", t)):
        out.append(Finding("rh", 0.75, "Termos de folha, desempenho ou desligamento"))
    contact_lines = [ln for ln in t.splitlines() if re.search(r"@[\w-]+\.|\d{3}\.\d{3}\.\d{3}-\d{2}|\(\d{2}\)\s?\d", ln)]
    if len(contact_lines) >= 3 or (CLIENT_TERMS.search(t) and (len(contact_lines) >= 1 or ctx.kind == "file_upload")):
        out.append(Finding("cliente", 0.8 if len(contact_lines) >= 3 else 0.65, "Várias linhas com dados de contato ou termo de base de clientes"))
    ma = _count(MA_TERMS, t)
    if ma >= 2 or MA_STRONG.search(t):
        out.append(Finding("estrategia_ma", 0.75, "Termos de fusões e aquisições"))
    legal = _count(LEGAL_TERMS, t)
    if CNJ.search(t) or legal >= 2:
        out.append(Finding("juridico", 0.8 if CNJ.search(t) else 0.65, "Termos jurídicos ou processo CNJ"))
    if _count(IP_TERMS, t) >= 2 or re.search(r"(?i)segredo industrial|trade secret|pedido de patente", t):
        out.append(Finding("propriedade_intelectual", 0.7, "Termos de patente ou segredo industrial"))
    if TOXIC.search(t):
        out.append(Finding("conteudo_toxico", 0.7, "Ofensa ou ameaça"))
    if PERSONAL.search(t):
        out.append(Finding("uso_pessoal", 0.7, "Tema pessoal"))
    return out


def productive(ctx: Context) -> bool:
    return ctx.kind in ("prompt", "response") and bool(WORK.search(ctx.text))
