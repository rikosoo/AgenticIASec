"""Distribuição do sensor (EXPERIMENTAL): o servidor entrega um instalador de uma linha e o próprio sensor (.pyz, só biblioteca padrão).
As rotas são públicas por desenho: não contêm segredo nenhum (o token de matrícula vai na linha de comando da máquina, nunca na URL).
Em produção isto precisa de HTTPS e de binário assinado (docs/implantacao-empresa.md): por HTTP, quem estiver no caminho pode trocar o script."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import zipfile
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

router = APIRouter(prefix="/sensor", tags=["sensor"])
PKG = "promptshield_claude_hook"

PS1 = r"""# PromptShield sensor (EXPERIMENTAL). Uso: $env:PS_API='http://servidor:8000'; $env:PS_TOKEN='pse_...'; irm "$env:PS_API/sensor/install.ps1" | iex
$ErrorActionPreference = 'Stop'
$api = $env:PS_API; $tok = $env:PS_TOKEN
if (-not $api -or -not $tok) { throw 'Defina PS_API e PS_TOKEN (o console mostra o comando pronto, na pagina Dispositivos).' }
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) {
  Write-Host 'Python nao encontrado. Tentando instalar com winget...'
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  throw 'Python instalado. Feche este PowerShell, abra outro e rode o comando de novo.'
}
Write-Host ''
Write-Host "PromptShield: este computador vai enviar para a sua empresa ($api) os prompts que voce digita e as acoes de ferramentas de IA"
Write-Host '(Claude Code e GitHub Copilot CLI). O texto sensivel e mascarado no servidor. Voce pode remover quando quiser.'
if ($env:PS_NOTIFIED -ne '1') { if ((Read-Host "Digite 'sim' para instalar") -ne 'sim') { throw 'Cancelado.' } }
$dir = Join-Path $env:USERPROFILE '.promptshield\sensor'
New-Item -ItemType Directory -Force $dir | Out-Null
$pyz = Join-Path $dir 'promptshield-sensor.pyz'
Invoke-WebRequest "$api/sensor/promptshield-sensor.pyz" -OutFile $pyz -UseBasicParsing
$m = Invoke-RestMethod "$api/sensor/manifest.json"
if ((Get-FileHash $pyz -Algorithm SHA256).Hash.ToLower() -ne $m.sha256) { throw 'O SHA-256 do sensor nao confere. Nada foi instalado.' }
& $py $pyz deploy --user --api-url $api --token $tok --confirm-employees-notified
Write-Host 'Pronto. Abra o Claude Code normalmente. Para remover: python' $pyz 'deploy --user --uninstall --confirm-employees-notified'
"""

SH = r"""#!/bin/sh
# PromptShield sensor (EXPERIMENTAL). Uso: curl -fsSL "$PS_API/sensor/install.sh" | PS_API=http://servidor:8000 PS_TOKEN=pse_... sh
set -eu
[ -n "${PS_API:-}" ] && [ -n "${PS_TOKEN:-}" ] || { echo "Defina PS_API e PS_TOKEN (o console mostra o comando pronto, na pagina Dispositivos)." >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 nao encontrado. Instale o Python 3.9 ou mais novo e rode de novo." >&2; exit 1; }
echo
echo "PromptShield: este computador vai enviar para a sua empresa ($PS_API) os prompts que voce digita e as acoes de ferramentas de IA"
echo "(Claude Code e GitHub Copilot CLI). O texto sensivel e mascarado no servidor. Voce pode remover quando quiser."
if [ "${PS_NOTIFIED:-}" != "1" ]; then
  printf "Digite 'sim' para instalar: "; read -r ok < /dev/tty
  [ "$ok" = "sim" ] || { echo "Cancelado."; exit 1; }
fi
DIR="$HOME/.promptshield/sensor"; mkdir -p "$DIR"; PYZ="$DIR/promptshield-sensor.pyz"
curl -fsSL "$PS_API/sensor/promptshield-sensor.pyz" -o "$PYZ"
WANT=$(curl -fsSL "$PS_API/sensor/manifest.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha256"])')
GOT=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$PYZ")
[ "$WANT" = "$GOT" ] || { echo "O SHA-256 do sensor nao confere. Nada foi instalado." >&2; rm -f "$PYZ"; exit 1; }
python3 "$PYZ" deploy --user --api-url "$PS_API" --token "$PS_TOKEN" --confirm-employees-notified
echo "Pronto. Para remover: python3 $PYZ deploy --user --uninstall --confirm-employees-notified"
"""


@lru_cache(maxsize=1)
def _pyz() -> bytes:
    spec = importlib.util.find_spec(PKG)
    if spec is None or not spec.submodule_search_locations:
        raise FileNotFoundError(PKG)
    src = Path(next(iter(spec.submodule_search_locations)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        main = zipfile.ZipInfo("__main__.py", (2026, 1, 1, 0, 0, 0))
        z.writestr(main, "import sys\nfrom promptshield_claude_hook.cli import main\nsys.exit(main())\n")
        for f in sorted(src.rglob("*.py")):
            info = zipfile.ZipInfo(f"{PKG}/{f.relative_to(src).as_posix()}", (2026, 1, 1, 0, 0, 0))  # data fixa: o hash é reproduzível
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes())
    return b"#!/usr/bin/env python3\n" + buf.getvalue()


def _need_pyz() -> bytes:
    try:
        return _pyz()
    except FileNotFoundError as exc:
        raise HTTPException(503, "sensor indisponível neste servidor") from exc


@router.get("/install.ps1", response_class=Response, summary="Instalador de uma linha para Windows (PowerShell)")
def install_ps1() -> Response:
    return Response(PS1, media_type="text/plain; charset=utf-8")


@router.get("/install.sh", response_class=Response, summary="Instalador de uma linha para Linux e macOS")
def install_sh() -> Response:
    return Response(SH, media_type="text/plain; charset=utf-8")


@router.get("/promptshield-sensor.pyz", response_class=Response, summary="O sensor: um arquivo .pyz, só biblioteca padrão")
def sensor_pyz() -> Response:
    return Response(_need_pyz(), media_type="application/octet-stream")


@router.get("/manifest.json", summary="SHA-256 do sensor, para o instalador conferir a integridade do download")
def manifest() -> dict:
    data = _need_pyz()
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "name": "promptshield-sensor.pyz"}
