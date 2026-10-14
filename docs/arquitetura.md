# Arquitetura (Etapa 1: esqueleto)

```
coletor -> evento universal -> motor de detecção -> política -> console
```

| Parte | Pasta | Estado |
|---|---|---|
| API (FastAPI) | `apps/api` | ingestão, políticas, incidentes, auditoria; RLS por tenant (Etapa 3) |
| Console (Next.js) | `apps/web` | página inicial que consulta `/health` da API |
| Motor de detecção | `packages/detection` | motor de detecção (ver `docs/deteccao.md`) |
| Taxonomia | `packages/taxonomy` | `taxonomy.yaml` com 30 categorias |
| Adaptador Claude Code | `packages/adapters/claude_code_hook` | hook de comando (Etapa 4) |
| Adaptadores restantes | `packages/adapters` | extensão (Etapa 5) e inference hooks (Etapa 8) |
| Extensão | `apps/extension` | não criada (Etapa 5) |

Banco: PostgreSQL 16. Row-level security entra na Etapa 3, junto com as tabelas de eventos.

Protótipo de interface sem backend: `prototipo/console.html` (dados simulados).
Matriz de viabilidade das integrações: `docs/viabilidade.md`.
