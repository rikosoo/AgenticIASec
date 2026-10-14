# Arquitetura

```
coletor -> evento universal -> motor de detecção -> política -> console
```

| Parte | Pasta | Estado |
|---|---|---|
| API (FastAPI) | `apps/api` | ingestão, políticas, incidentes, auditoria; RLS por tenant (Etapa 3) |
| Console (Next.js) | `apps/web` | console (Etapa 6): BFF com cookie httpOnly e proxy `/api/proxy/v1/*` para a API |
| Motor de detecção | `packages/detection` | motor de detecção (ver `docs/deteccao.md`) |
| Taxonomia | `packages/taxonomy` | `taxonomy.yaml` com 30 categorias |
| Adaptador Claude Code | `packages/adapters/claude_code_hook` | hook de comando (Etapa 4) |
| Adaptadores restantes | `packages/adapters` | inference hooks (Etapa 8) |
| Extensão | `apps/extension` | Chrome/Edge MV3 para ChatGPT web e Claude.ai (Etapa 5, EXPERIMENTAL) |

Banco: PostgreSQL 16. Row-level security entra na Etapa 3, junto com as tabelas de eventos.

Protótipo de interface sem backend: `prototipo/console.html` (dados simulados).
Matriz de viabilidade das integrações: `docs/viabilidade.md`.

## Console (Etapa 6)

```
navegador --cookie httpOnly--> Next.js (BFF) --Bearer--> API --RLS--> PostgreSQL
```

O token nunca chega ao JavaScript do navegador. O proxy só aceita `/v1/...` e exige cabeçalho `X-Requested-With` e `Origin` igual ao `Host` nas mutações. Login: `mock` (desenvolvimento) ou OIDC Authorization Code + PKCE (não testado contra provedor real). Todas as telas usam a mesma janela de tempo (`window_start`: 00:00 UTC do primeiro de N dias) para que os números de visão geral, lista e categorias batam.

## Alertas, SIEM e relatórios (Etapa 7)

```
ingestão -> análise -> incidente/alerta (deduplicado) -> fila de envio (outbox) -> worker -> webhook | Slack | Teams | e-mail | syslog/CEF
                                                                              \-> relatórios agendados (PDF/CSV)
```

Tudo roda sobre o mesmo PostgreSQL com RLS. O worker (`python -m app.worker`) usa o papel restrito; só `list_tenant_ids()` (função SECURITY DEFINER que devolve ids) cruza tenants. Detalhes, estado de cada integração e mapeamento de campos: `docs/siem.md`.
