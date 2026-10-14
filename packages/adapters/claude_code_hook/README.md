# Adaptador do Claude Code

Hook de comando que o Claude Code chama em `UserPromptSubmit`, `PreToolUse` e `PostToolUse`. Converte a entrada em evento universal, envia a `POST /v1/events` e responde com a decisão. Só usa a biblioteca padrão do Python (3.9 ou mais novo).

Documentação do formato e do que foi verificado: [`docs/claude-code-hooks.md`](../../../docs/claude-code-hooks.md).

## Como se comporta

| Situação | Resultado |
|---|---|
| Política em **monitorar** (padrão) | a API devolve sempre `allow`: o Claude Code nunca é interrompido; a decisão hipotética fica no console |
| Política em **aplicar**, `block` | prompt bloqueado / ferramenta negada (`deny`) |
| `mask` ou `ask_justification` | em prompt: bloqueia e mostra a versão mascarada (o hook não pode reescrever o prompt); em ferramenta: pede confirmação (`ask`) |
| API fora do ar, `fail_mode: open` | segue; grava só **metadados** em `~/.promptshield/claude-hook-spool.jsonl` (nunca o conteúdo) |
| API fora do ar, `fail_mode: closed` | bloqueia, com mensagem |
| Timeout da API (`timeout_seconds`, padrão 3 s), chave errada, erro interno | tratado como "API fora do ar" |

O adaptador sempre termina com código 0 e JSON válido: nunca derruba o Claude Code. No fail-closed o instalador também define `onFailure: "block"` no hook (versão 2.1.295 ou mais nova), para cobrir o caso de o próprio processo travar.

## Instalar em uma máquina de teste (Linux e macOS)

Pré-requisitos: `python3`, Claude Code, e uma chave de API do tenant (`python -m app.cli create-tenant ...`, ver README da raiz).

```bash
cd packages/adapters/claude_code_hook
sudo ./install/install.sh --api-url https://sua-api.exemplo --api-key ps_XXXX --fail-mode open --department Engenharia
PROMPTSHIELD_HOOK_CONFIG=/etc/promptshield/claude-code-hook.json /usr/local/lib/promptshield/promptshield-claude-hook check
```

Use `--dry-run` para ver o que será feito. O instalador mescla os hooks no `managed-settings.json` (mantém o que já existe e faz cópia `.bak-…`). Para remover: `sudo ./install/uninstall.sh`.

Windows **não tem instalador**. O caminho da política é `C:\Program Files\ClaudeCode\managed-settings.json`; o exemplo está em `examples/managed-settings.json` (ajuste o caminho do comando).

Avisos:
- A chave fica legível por todos os usuários da máquina (o hook roda como o usuário). Ela só envia eventos. Rotação de chaves entra na Etapa 9.
- O hook envia prompts e ações dos agentes. **Avise os colaboradores** antes de ligar.
- O hook não sabe se a conta é pessoal ou corporativa (o Claude Code não informa) e identifica o usuário pelo usuário do sistema operacional, salvo `user_id` na configuração.
- Textos acima de `max_text_chars` (200.000) são cortados antes do envio.
- O instalador **não** liga `allowManagedHooksOnly` (que bloquearia os hooks próprios do cliente) a menos que você passe `--managed-only-hooks`.

## Verificar em um Claude Code de verdade (checklist)

Sem alterar a política da máquina, use `--settings` com um arquivo de hooks (modelo em `examples/managed-settings.json`) e um arquivo de configuração do hook (`examples/claude-code-hook.json`):

```bash
export PROMPTSHIELD_HOOK_CONFIG=/caminho/hook.json
claude -p "use a chave AKIAEXEMPLOEXEMPLO123 no deploy" --settings /caminho/settings.json     # com a política de segredos em aplicar: bloqueado
claude -p "rode: cat ~/.aws/credentials" --settings /caminho/settings.json --allowedTools Bash  # com a política de leitura de credenciais em aplicar: ação negada
```

Resultado de 2026-10-14 com Claude Code 2.1.296: os dois casos foram bloqueados (detalhes e o que ficou sem testar em `docs/claude-code-hooks.md`).

## Testes

```bash
make test        # unitários do adaptador e o ponta a ponta (apps/api/tests/test_claude_hook_e2e.py, com PostgreSQL)
```
