# PromptShield

Plataforma que observa o uso de IA por funcionários e agentes, classifica cada evento, calcula risco explicável e aplica políticas. Contexto completo em [`CLAUDE.md`](CLAUDE.md).

**Estado:** Etapa 9 (endurecimento e preparação do piloto). As Etapas 0 a 9 estão feitas; leia as pendências em cada documento antes de ir a produção. O que existe:

| Pasta | O que tem |
|---|---|
| `apps/api` | FastAPI: ingestão de eventos, políticas, incidentes, auditoria, multi-tenant com RLS (ver seção abaixo) |
| `apps/web` | console Next.js: visão geral, prompts, incidentes, políticas, risco por usuário, alertas e SIEM, relatórios (ver o README da pasta) |
| `infra/vm-setup.sh` | sobe o servidor de teste em uma VM Linux com um comando (não executado em máquina real) |
| `docs/teste-vm.md` | servidor em uma VM e coletor no seu computador, via túnel SSH (não executado ainda) |
| `docs/teste-windows.md` | passo a passo para rodar os testes reais em uma máquina Windows (não executado ainda) |
| `docs/guia-simples.md` | servidor (hive) e sensor em cada máquina, em dois passos (experimental) |
| `docs/implantacao-empresa.md` | proposta de instalação na empresa inteira, com as decisões em aberto (nada construído) |
| `docs/roteiro-testes-reais.md` | roteiro para validar as integrações em serviços reais (nenhum passo executado ainda) |
| `packages/detection` | motor de detecção, com taxonomia em `packages/taxonomy` (`docs/deteccao.md`, `docs/relatorio-etapa2.md`) |
| `apps/extension` | extensão Chrome/Edge para ChatGPT web e Claude.ai (EXPERIMENTAL; ver o README da pasta) |
| `packages/adapters/inference_hooks` | biblioteca dos inference hooks do Claude Enterprise (assinatura, frames, veredito; ver `docs/inference-hooks.md`) |
| `packages/adapters/claude_code_hook` | hook do Claude Code (instalação, modo de falha, testes; ver o README da pasta) |
| `prototipo/console.html` | protótipo visual com **dados simulados** (abre direto no navegador) |
| `docs/` | `viabilidade.md` (captura por ferramenta), `arquitetura.md`, `decisoes.md`, `siem.md` (alertas, CEF, relatórios), `inference-hooks.md`, `ameacas.md` (STRIDE), `lgpd.md` (LGPD, GDPR, EUA: modelos para advogado), `operacao.md`, `piloto.md` |

## Requisitos

Docker com Compose (para `make up`). Para `make test` e `make lint` sem Docker: Python 3.12 ou superior e Node 22.

## Passo a passo

```bash
git clone <este repositório> && cd AgenticIASec
make up        # cria .env a partir de .env.example, sobe db, api e web
```

Depois de subir:

- API: <http://localhost:8000/health> (responde `{"status":"ok"}`) e <http://localhost:8000/docs>
- Console: <http://localhost:3000> (login por OIDC; para desenvolvimento veja `apps/web/README.md`, modo `mock`, e `seed-demo` para dados sintéticos)

Para parar: `Ctrl+C` e `make down`.

Segredos: `.env` fica fora do git. Troque a senha do banco em `.env` e na `DATABASE_URL` se for expor a porta 5432.

## Testes e lint

```bash
make test      # pytest (api e detection) e vitest (web)
make lint      # ruff e tsc
```

O teste de migração roda em um Postgres de verdade quando `DATABASE_URL_TEST` está definida; sem ela é pulado.

```bash
DATABASE_URL_TEST=postgresql+psycopg://usuario:senha@localhost:5432/banco_de_teste make test
```

O banco de teste precisa ser UTF8; o teste cria e remove a tabela `tenants`.

## Protótipo do console

Abra `prototipo/console.html` no navegador. Usuários, prompts e comandos são fictícios e o detector é uma heurística em JavaScript, não o motor real.

## API de ingestão (Etapa 3)

Documentação interativa em <http://localhost:8000/docs> (OpenAPI em `/openapi.json`).

1. Crie um tenant (com administrador, uma chave de API e as políticas padrão, **todas em modo monitorar**):

   ```bash
   docker compose exec api python -m app.cli create-tenant \
     --name "Empresa Exemplo" --slug exemplo --admin-email admin@empresa-exemplo.com.br
   ```

   A chave `ps_...` aparece uma única vez. Só o hash dela fica no banco.

2. Envie um evento sintético com CPF:

   ```bash
   curl -s -X POST http://localhost:8000/v1/events \
     -H "X-API-Key: ps_SUA_CHAVE" -H "Content-Type: application/json" -d '{
       "event_id": "7d1f6d0e-3b5e-4f3a-9c55-0a1b2c3d4e5f",
       "occurred_at": "2026-10-14T12:00:00Z",
       "source": {"channel": "agent_hook", "app": "claude_code", "integration_status": "partial"},
       "actor": {"user_id": "rafael.moreira", "department": "Engenharia"},
       "kind": "prompt",
       "content": {"text": "Cliente CPF 529.982.247-25, pode revisar o contrato?"}
     }'
   ```

   Resposta (resumida), verificada contra a API rodando com PostgreSQL 16:

   ```json
   {"decision": "allow", "would_decide": "mask", "enforced": false,
    "masked_text": "Cliente CPF ***.***.***-25, pode revisar o contrato?",
    "categories": [{"id": "pii", "confidence": 0.97}], "risk": {"score": 58, "...": "..."}}
   ```

   Em modo monitorar a decisão devolvida é sempre `allow`; `would_decide` mostra o que a política faria. Repetir o mesmo `event_id` devolve a mesma resposta (`"duplicate": true`) sem gravar de novo.

3. Console: `OIDC_MODE=mock` (só desenvolvimento) habilita `POST /dev/token` com `{"email": "..."}`; use o token como `Authorization: Bearer`. O e-mail precisa existir em `users`. Papéis: `admin`, `analista`, `auditor`, `leitura`. Para produção use `OIDC_MODE=oidc` com `OIDC_ISSUER`, `OIDC_AUDIENCE` e `OIDC_JWKS_URL` (**não testado contra um provedor real**, só com chaves geradas nos testes).

### Como o isolamento entre tenants funciona

Todas as tabelas de dados têm `tenant_id` e row-level security forçada. A API conecta com o papel `promptshield_app` (sem superuser e sem `BYPASSRLS`) e, a cada transação, define `app.tenant_id`. Sem essa variável, nenhuma linha é visível. A autenticação usa duas funções `SECURITY DEFINER` (`auth_api_key`, `auth_user_by_email`), as únicas que cruzam tenants.

Limite honesto: o papel da aplicação consegue executar `SET app.tenant_id`. O RLS protege contra consulta sem filtro, bug de código e SQL fixo; não protege contra quem já executa SQL arbitrário com esse papel. `audit_log` é só de inserção (gatilho no banco), até para o dono.

### Testes da API

```bash
DATABASE_URL_TEST=postgresql+psycopg://usuario:senha@localhost:5432/banco_de_teste make test
```

O usuário precisa ser dono do banco (cria o papel `promptshield_app`) e o banco precisa ser UTF8. O teste recria o esquema (`alembic downgrade base` e `upgrade head`) e apaga os dados entre testes: **nunca aponte para um banco com dados**.

## Alertas, SIEM e relatórios (Etapa 7)

O serviço `worker` do compose entrega a fila de notificações e gera relatórios agendados (`python -m app.worker`, ou `--once`). Canais, regras, formatos e o estado de cada integração (Teams é EXPERIMENTAL e A VERIFICAR; e-mail e Slack são PARCIAIS): [`docs/siem.md`](docs/siem.md). Para e-mail, configure `SMTP_*` no `.env`.

## Inference hooks do Claude Enterprise (Etapa 8)

Endpoint `POST /v1/inference-hook` e tela **Inference hooks** no console. **Depende do plano Claude Enterprise e de uma funcionalidade em beta da Anthropic (o suporte também é beta).** O protocolo foi lido na documentação oficial e o endpoint é testado com requisições simuladas conforme essa documentação; **nunca foi chamado por um tenant Enterprise real** (PARCIAL). Nasce em modo **sombra** (sempre permite e registra o que teria feito). Passo a passo do administrador do cliente, requisitos (HTTPS na porta 443, certificado público) e latência medida: [`docs/inference-hooks.md`](docs/inference-hooks.md) e o README de [`packages/adapters/inference_hooks`](packages/adapters/inference_hooks/README.md).

## Privacidade, segurança e piloto (Etapa 9)

- **Privacidade por padrão:** guarda só texto com identificadores mascarados; texto livre de saúde **não é guardado**; o original é opt-in, cifrado e apagado mais cedo; retenção configurável com job diário; acesso e eliminação por titular; mapa de dados por tenant. Documento jurídico (**modelo para revisão de advogado**, LGPD, GDPR e EUA): [`docs/lgpd.md`](docs/lgpd.md).
- **Segurança:** modelo de ameaças [`docs/ameacas.md`](docs/ameacas.md); limite de requisições por credencial, rotação de chaves, cabeçalhos de segurança, logs sem conteúdo; `make audit` (dependências) e as regras de segurança no `make lint`.
- **Operação:** backup e restauração testados (`infra/backup.sh`, `infra/restore.sh`), chaves, retenção, métricas: [`docs/operacao.md`](docs/operacao.md).
- **Piloto de 30 dias:** roteiro, checklist e métricas em [`docs/piloto.md`](docs/piloto.md); tela **Piloto** e relatório final em PDF.
