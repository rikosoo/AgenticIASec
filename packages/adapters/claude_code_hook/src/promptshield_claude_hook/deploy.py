"""Instalação silenciosa em NÍVEL DE MÁQUINA, para o TI distribuir por MDM, GPO ou script. EXPERIMENTAL: nunca rodou em MDM real.

    promptshield-claude-hook deploy --api-url https://api.empresa --token pse_... --confirm-employees-notified [--tools claude_code,github_copilot_cli]
    promptshield-claude-hook deploy --uninstall --confirm-employees-notified

Exige administrador (grava em C:\\ProgramData, C:\\Program Files, /etc, /Library). Faz, de forma idempotente e com cópia de segurança:
  1. troca o token de matrícula por uma chave PRÓPRIA desta máquina (POST /v1/enroll) e grava a configuração de máquina;
  2. Claude Code: mescla os hooks no managed-settings.json (documentado em docs/claude-code-hooks.md);
  3. GitHub Copilot CLI: grava um arquivo de hooks de política (policy.d), que o usuário não consegue alterar (fonte: github/docs, hooks-reference.md).
Avisos: a chave da máquina fica legível pelos usuários locais (o hook roda como o usuário); ela só envia eventos e é revogável no console.
O aviso aos empregados é obrigação do cliente: por isso a confirmação é exigida como argumento. Nada de captura oculta (princípio 2).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from . import browser, client, config, ias, setup
from .config import Config

CLIENT_VERSION = "0.1"
ALL_TOOLS = ("claude_code", "github_copilot_cli", "browser_extension")
DEFAULT_TOOLS = ("claude_code", "github_copilot_cli")   # a extensão do navegador exige um clique da pessoa: só entra se pedida (--tools)


def paths(root: Path | None = None, user: bool = False) -> dict[str, Path]:
    """Caminhos de máquina por sistema operacional. `root` prefixa tudo (testes). `user`: nível do usuário, sem administrador."""
    if user:
        return {"claude": setup.claude_settings_path(), "copilot": setup.copilot_hooks_path(), "config": Path(config.user_config_path())}
    sysname = platform.system()
    if sysname == "Windows":
        p = {"claude": Path("C:/Program Files/ClaudeCode/managed-settings.json"),
             "copilot": Path("C:/ProgramData/GitHub/Copilot/policy.d/promptshield.json"),
             "config": Path("C:/ProgramData/PromptShield/hook.json")}
    elif sysname == "Darwin":
        p = {"claude": Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
             "copilot": Path("/etc/github-copilot/policy.d/promptshield.json"),
             "config": Path("/Library/Application Support/PromptShield/claude-code-hook.json")}
    else:
        p = {"claude": Path("/etc/claude-code/managed-settings.json"), "copilot": Path("/etc/github-copilot/policy.d/promptshield.json"),
             "config": Path("/etc/promptshield/claude-code-hook.json")}
    if root is not None:
        p = {k: root / str(v).lstrip("/\\").replace(":", "") for k, v in p.items()}
    return p


def enroll(api_url: str, token: str, tools: list[str]) -> dict[str, Any]:
    if not api_url.lower().startswith(("http://", "https://")):
        raise client.ApiError("api_url precisa começar com https:// (http:// só em testes)")
    body = {"token": token, "hostname": socket.gethostname()[:200], "os": platform.system(), "client_version": CLIENT_VERSION, "tools": tools}
    req = urllib.request.Request(api_url.rstrip("/") + "/v1/enroll", data=json.dumps(body).encode(), method="POST",  # noqa: S310
                                 headers={"Content-Type": "application/json", "User-Agent": "promptshield-deploy/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        raise client.ApiError(f"matrícula recusada pela API ({exc.code}): token inválido, expirado, revogado ou esgotado", status=exc.code) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise client.ApiError(f"API indisponível ({type(exc).__name__})") from exc


def _write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    try:
        path.chmod(mode)
    except OSError:
        pass


def install(api_url: str, token: str, tools: list[str], department: str | None, fail_mode: str, root: Path | None, force: bool,
            say=print, user: bool = False) -> int:
    p = paths(root, user)
    existing = None
    if p["config"].is_file():
        try:
            existing = json.loads(p["config"].read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            existing = None
    if existing and existing.get("api_key") and not force:
        say("Esta máquina já está matriculada (use --force para matricular de novo).")
        key = existing["api_key"]
    else:
        try:
            key = enroll(api_url, token, tools)["api_key"]
        except client.ApiError as exc:
            say(f"FALHOU: {exc}")
            return 1
        cfg: dict[str, Any] = {"api_url": api_url.rstrip("/"), "api_key": key, "fail_mode": fail_mode, "timeout_seconds": 3,
                               "integration_status": "partial"}
        if department:
            cfg["department"] = department
        _write(p["config"], json.dumps(cfg, indent=2) + "\n")
        say(f"Matriculada. Configuração: {p['config']}")
    if "claude_code" in tools:
        data = setup.merge_hooks(setup.read_settings(p["claude"]))
        backup = setup.write_settings(p["claude"], data)
        say(f"Claude Code: hooks em {p['claude']}" + (f" (cópia: {backup})" if backup else ""))
    if "github_copilot_cli" in tools:
        _write(p["copilot"], json.dumps(setup.copilot_doc(), indent=2) + "\n")
        say(f"GitHub Copilot CLI: hooks de política em {p['copilot']}")
    if "browser_extension" in tools:
        try:
            browser.install_extension(api_url, key, department, say=say, open_browser=root is None)
        except (client.ApiError, OSError, ValueError, zipfile.BadZipFile) as exc:
            say(f"AVISO: a extensão do navegador não foi preparada ({exc}). O resto foi instalado.")
    try:
        cfg_obj = Config(api_url=api_url.rstrip("/"), api_key=key, timeout_seconds=5)
        client.get_hook_config(cfg_obj)
        say("Conexão testada: OK.")
    except client.ApiError as exc:
        say(f"AVISO: instalado, mas o teste de conexão falhou ({exc}).")
    return 0


def uninstall(root: Path | None, say=print, user: bool = False) -> int:
    p = paths(root, user)
    if p["claude"].is_file():
        data = setup.read_settings(p["claude"])
        if setup.is_installed(data):
            setup.write_settings(p["claude"], setup.remove_ours(data))
            say(f"Claude Code: hooks removidos de {p['claude']}")
    ext = browser.default_dir()
    if user and ext.is_dir():
        import shutil
        shutil.rmtree(ext)
        say(f"Removida a pasta da extensão: {ext} (remova também a extensão em chrome://extensions)")
    for k in ("copilot", "config"):
        if p[k].is_file():
            p[k].unlink()
            say(f"Removido: {p[k]}")
    say("Revogue o dispositivo no console (a chave desta máquina continua válida até lá).")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="promptshield-claude-hook deploy", description="Instalação silenciosa em nível de máquina (EXPERIMENTAL).")
    ap.add_argument("--api-url")
    ap.add_argument("--token", help="token de matrícula (pse_...) criado no console")
    ap.add_argument("--tools", default=",".join(DEFAULT_TOOLS), help=f"lista separada por vírgula entre: {', '.join(ALL_TOOLS)} (padrão: {', '.join(DEFAULT_TOOLS)})")
    ap.add_argument("--ias", help="números das IAs a monitorar, separados por vírgula (ver --list-ias); substitui --tools")
    ap.add_argument("--list-ias", action="store_true", help="mostra a lista numerada de IAs e sai")
    ap.add_argument("--department")
    ap.add_argument("--fail-mode", choices=("open", "closed"), default="open")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--user", action="store_true", help="instala só para o usuário atual (sem administrador): ~/.claude, ~/.copilot, ~/.promptshield")
    ap.add_argument("--force", action="store_true", help="matricula de novo mesmo que já exista chave nesta máquina")
    ap.add_argument("--root", type=Path, help="prefixo para teste: grava tudo sob esta pasta")
    ap.add_argument("--confirm-employees-notified", action="store_true",
                    help="confirma que os empregados foram avisados sobre o monitoramento (exigido)")
    a = ap.parse_args(argv)
    if a.list_ias:
        print(ias.render_list())
        return 0
    if not a.confirm_employees_notified:
        print("RECUSADO: confirme com --confirm-employees-notified que os empregados foram avisados (obrigação do cliente).")
        return 2
    chosen: list[int] = []
    if a.ias:
        chosen, errs = ias.parse_selection(a.ias)
        if errs:
            print("; ".join(errs))
            return 2
        tools = ias.tools_for(chosen)
    else:
        tools = [t.strip() for t in a.tools.split(",") if t.strip()]
    bad = [t for t in tools if t not in ALL_TOOLS]
    if bad:
        print(f"Ferramenta desconhecida: {', '.join(bad)}. Disponíveis: {', '.join(ALL_TOOLS)}.")
        return 2
    if not a.user and os.name != "nt" and a.root is None and hasattr(os, "geteuid") and os.geteuid() != 0:
        print("Precisa de administrador (root) para gravar em nível de máquina.")
        return 1
    if a.uninstall:
        return uninstall(a.root, user=a.user)
    if not a.api_url or not a.token:
        print("Informe --api-url e --token.")
        return 2
    code = install(a.api_url, a.token, tools, a.department, a.fail_mode, a.root, a.force, user=a.user)
    if code == 0 and chosen:
        exe, args = setup.self_command()
        command = " ".join([f'"{exe}"'] + [f'"{x}"' for x in args])
        print("\n===== Passo a passo de cada IA escolhida =====")
        for n in chosen:
            print("\n" + ias.guide(n, command))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
