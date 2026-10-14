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
| 2026-10-14 | Nomes de pessoas | Presidio + spaCy opcional (`[ner]`), só nome completo, ignora empresas; endereço e CEP por regex | NER ligado por padrão (custa ~30 ms por texto); reportar nome solto (muitos falsos positivos) |
| 2026-10-14 | CPF digitado com erro ("meu cpf é 3444353432123") | Palavra CPF/CNPJ/RG antes de um número conta como dado pessoal mesmo com dígito inválido | Exigir dígito verificador válido (deixava vazar o dado declarado; LGPD/GDPR tratam como dado pessoal) |
| 2026-10-14 | Papel do banco | API usa `promptshield_app` (sem BYPASSRLS); migrações e CLI usam o dono (`ADMIN_DATABASE_URL`) | Um único papel superuser (RLS seria ignorado) |
| 2026-10-14 | Login antes de saber o tenant | Funções SECURITY DEFINER `auth_api_key` e `auth_user_by_email` | Desligar RLS em `api_keys` e `users` |
| 2026-10-14 | Chave de API | Formato `ps_<prefixo>_<segredo>`, SHA-256 no banco (192 bits de entropia), mostrada uma vez | bcrypt/argon2 (desnecessário para segredo aleatório longo, e lento por requisição) |
| 2026-10-14 | Texto original | Opcional por tenant (`store_original`), Fernet com chave derivada por HKDF da chave mestra; leitura exige justificativa e vai para `audit_log` | Sempre guardar (viola privacidade por padrão); KMS por tenant fica para a Etapa 9 |
| 2026-10-14 | Usuário de teste de banco | Testes usam o superuser de `DATABASE_URL_TEST` só para migrar e limpar; todo o resto roda com o papel restrito | Rodar tudo como superuser (esconderia falhas de RLS) |
| 2026-10-14 | Um tenant por e-mail | `lower(email)` único globalmente (login OIDC resolve tenant pelo e-mail) | E-mail repetido em vários tenants (exigiria escolher tenant no login) |
