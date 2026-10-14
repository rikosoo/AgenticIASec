# Decisões

Uma linha por decisão: contexto, escolha, alternativas.

| Data | Contexto | Escolha | Alternativas |
|---|---|---|---|
| 2026-10-14 | Ordem de integração do MVP | Hook do Claude Code primeiro; inference hooks depois, só com design partner Claude Enterprise | Inference hooks primeiro (Prioridade 1 do plano de negócio): testável só com tenant Enterprise e em beta |
| 2026-10-14 | Codex CLI e Cursor | Fora do MVP até haver acesso à documentação primária e cliente que use | Integrar já com base em resumos de busca (rejeitado: viola "não inventar") |
| 2026-10-14 | Tema do console | Claro por padrão, com alternância para escuro (pedido do usuário) | Escuro por padrão como no CLAUDE.md original |
| 2026-10-14 | Lint do web | `tsc --noEmit` | `next lint` (removido nas versões recentes do Next); ESLint pode entrar depois |
| 2026-10-14 | Tipos do banco | `Uuid` e `DateTime(timezone=True)` genéricos do SQLAlchemy | Tipos específicos do Postgres (menos portáveis; sem ganho nesta etapa) |
| 2026-10-14 | Presidio e classificador de injection na Etapa 2 | Não incluídos; motor determinístico com gancho `InjectionClassifier` | Baixar modelos agora (sem rede para modelos neste ambiente; adotar sem medir viola o prompt da etapa) |
| 2026-10-14 | Regras do ruff | `E,F,I,B` explícitas, E501 ignorado nos pacotes | Conjunto padrão do ruff 0.17 (mais amplo, ruidoso para regex) |
| 2026-10-14 | Decisão no resultado do motor | Sugestão simples (`decision`); política real na Etapa 3 | Omitir o campo (quebraria o contrato do CLAUDE.md) |
| 2026-10-14 | E-mail em tool_call | Ignorado | Detectar (falso positivo em `ssh user@host`) |
| 2026-10-14 | Push protection do GitHub bloqueou chaves sintéticas no conjunto de teste | Fixtures guardam marcadores `@@aws:1@@`; `tests/fixtures/synth.py` gera os valores ao carregar | Liberar o bloqueio pelo link (contorna uma proteção do repositório); chaves fixas no arquivo |
