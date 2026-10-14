# Decisões

Uma linha por decisão: contexto, escolha, alternativas.

| Data | Contexto | Escolha | Alternativas |
|---|---|---|---|
| 2026-10-14 | Ordem de integração do MVP | Hook do Claude Code primeiro; inference hooks depois, só com design partner Claude Enterprise | Inference hooks primeiro (Prioridade 1 do plano de negócio): testável só com tenant Enterprise e em beta |
| 2026-10-14 | Codex CLI e Cursor | Fora do MVP até haver acesso à documentação primária e cliente que use | Integrar já com base em resumos de busca (rejeitado: viola "não inventar") |
| 2026-10-14 | Tema do console | Claro por padrão, com alternância para escuro (pedido do usuário) | Escuro por padrão como no CLAUDE.md original |
| 2026-10-14 | Lint do web | `tsc --noEmit` | `next lint` (removido nas versões recentes do Next); ESLint pode entrar depois |
| 2026-10-14 | Tipos do banco | `Uuid` e `DateTime(timezone=True)` genéricos do SQLAlchemy | Tipos específicos do Postgres (menos portáveis; sem ganho nesta etapa) |
