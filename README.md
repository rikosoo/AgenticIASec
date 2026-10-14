# PromptShield

Plataforma que observa o uso de IA por funcionários e agentes, classifica cada evento, calcula risco explicável e aplica políticas. Contexto completo em [`CLAUDE.md`](CLAUDE.md).

**Estado:** Etapa 2 (motor de detecção). Ainda não há captura, API de ingestão nem políticas. O que existe:

| Pasta | O que tem |
|---|---|
| `apps/api` | FastAPI com `GET /health` e `GET /version`, Alembic com a tabela `tenants` |
| `apps/web` | Next.js com uma página que mostra se a API está online |
| `packages/detection` | motor de detecção, com taxonomia em `packages/taxonomy` (`docs/deteccao.md`, `docs/relatorio-etapa2.md`) |
| `prototipo/console.html` | protótipo visual com **dados simulados** (abre direto no navegador) |
| `docs/` | `viabilidade.md` (captura por ferramenta), `arquitetura.md`, `decisoes.md` |

## Requisitos

Docker com Compose (para `make up`). Para `make test` e `make lint` sem Docker: Python 3.12 ou superior e Node 22.

## Passo a passo

```bash
git clone <este repositório> && cd AgenticIASec
make up        # cria .env a partir de .env.example, sobe db, api e web
```

Depois de subir:

- API: <http://localhost:8000/health> (responde `{"status":"ok"}`) e <http://localhost:8000/docs>
- Console: <http://localhost:3000>

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
