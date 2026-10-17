#!/usr/bin/env bash
# Abre o console (e, se pedir, a API) da VM de TESTE para fora, SEM túnel. O banco nunca é exposto.
#   ./infra/expose.sh --public-ip 3.134.84.250 --web          # só o console, porta 3000
#   ./infra/expose.sh --public-ip 3.134.84.250 --web --api    # também a API, porta 8000 (veja o aviso)
#   ./infra/expose.sh --close                                 # volta para 127.0.0.1 (só túnel)
# Pré-requisito que NÃO é deste script: no firewall da nuvem, libere 3000 (e 8000) SÓ para o seu IP.
# Riscos (leia): o login do console está em modo MOCK (qualquer pessoa que alcançar a porta entra com um e-mail cadastrado) e o tráfego
# é HTTP sem cifra. O console só mostra texto mascarado, mas o HOOK envia o texto ORIGINAL dos prompts para a API: se você expuser
# a API em HTTP, esse texto cruza a internet sem cifra. Por isso a API não é aberta a menos que você peça (--api).
# Status: NÃO EXECUTADO em máquina real.
set -euo pipefail
IP=""; WEB=0; API=0; CLOSE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --public-ip) IP=$2; shift 2;;
    --web) WEB=1; shift;;
    --api) API=1; shift;;
    --close) CLOSE=1; shift;;
    -h|--help) sed -n '2,12p' "$0"; exit 0;;
    *) echo "opção desconhecida: $1" >&2; exit 2;;
  esac
done
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "sem .env: rode ./infra/vm-setup.sh primeiro" >&2; exit 1; }
DOCKER="docker"; docker info >/dev/null 2>&1 || DOCKER="sudo docker"
setenv() { if grep -q "^$1=" .env; then sed -i "s#^$1=.*#$1=$2#" .env; else echo "$1=$2" >> .env; fi; }
unsetenv() { sed -i "/^$1=/d" .env; }

if [ "$CLOSE" = 1 ]; then
  for k in WEB_BIND API_BIND EXPOSE_CONFIRMED; do unsetenv "$k"; done
  setenv PUBLIC_BASE_URL http://localhost:3000
  $DOCKER compose up -d
  echo "Fechado: portas só em 127.0.0.1. Use o túnel SSH."
  exit 0
fi
[ -n "$IP" ] && [ "$WEB$API" != "00" ] || { echo "informe --public-ip IP e --web e/ou --api" >&2; exit 2; }
echo "ATENÇÃO: você vai abrir ${WEB:+o console (3000)} ${API:+e a API (8000)} em http://$IP"
echo "  1. O firewall da nuvem DEVE limitar essas portas ao SEU IP."
echo "  2. Login MOCK: quem alcançar a porta entra como qualquer e-mail cadastrado."
echo "  3. HTTP sem cifra.${API:+ A API recebe o texto ORIGINAL dos prompts: ele cruzaria a internet sem cifra.}"
read -r -p "Digite 'entendi' para continuar: " ok
[ "$ok" = "entendi" ] || { echo "cancelado"; exit 1; }
setenv EXPOSE_CONFIRMED 1
[ "$WEB" = 1 ] && setenv WEB_BIND 0.0.0.0 && setenv PUBLIC_BASE_URL "http://$IP:3000"
[ "$API" = 1 ] && setenv API_BIND 0.0.0.0
$DOCKER compose up -d
echo "Pronto. Console: http://$IP:3000"
[ "$API" = 1 ] && echo "API: http://$IP:8000 (use este endereço como api_url do hook)"
echo "Para voltar ao modo seguro: ./infra/expose.sh --close"
