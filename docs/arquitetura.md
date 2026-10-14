# Arquitetura (Etapa 1: esqueleto)

```
coletor -> evento universal -> motor de detecção -> política -> console
```

| Parte | Pasta | Estado |
|---|---|---|
| API (FastAPI) | `apps/api` | `GET /health`, `GET /version`, migração `tenants` |
| Console (Next.js) | `apps/web` | página inicial que consulta `/health` da API |
| Motor de detecção | `packages/detection` | motor de detecção (ver `docs/deteccao.md`) |
| Taxonomia | `packages/taxonomy` | `taxonomy.yaml` com 30 categorias |
| Adaptadores | `packages/adapters` | vazio (Etapas 4, 5, 8) |
| Extensão | `apps/extension` | não criada (Etapa 5) |

Banco: PostgreSQL 16. Row-level security entra na Etapa 3, junto com as tabelas de eventos.

Protótipo de interface sem backend: `prototipo/console.html` (dados simulados).
Matriz de viabilidade das integrações: `docs/viabilidade.md`.
