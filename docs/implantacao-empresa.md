# Implantação na empresa inteira (proposta, nada disso foi construído ou testado)

Objetivo comercial: o administrador baixa **um arquivo por sistema operacional** (gerado para o tenant dele), distribui pelo que a empresa já usa (Intune, Jamf, GPO, script) e cada máquina passa a enviar eventos das ferramentas de IA configuradas, sem o funcionário fazer nada. Isto é pacote e distribuição dos coletores que já existem; **não** é agente de desktop nem proxy (ambos fora do escopo, ver `CLAUDE.md`).

Status: **proposta**. O que existe hoje é o assistente por usuário (`python -m promptshield_claude_hook setup`). Nada abaixo foi executado em MDM, GPO ou máquina de cliente.

## O que cada ferramenta permite em nível de máquina (fontes)

| Ferramenta | Mecanismo administrativo | Fonte | Situação |
|---|---|---|---|
| Claude Code | `managed-settings.json` (Windows `C:\Program Files\ClaudeCode\`, macOS `/Library/Application Support/ClaudeCode/`, Linux `/etc/claude-code/`) com os hooks; `allowManagedHooksOnly` é opcional e perigoso | `docs/claude-code-hooks.md` (documentação oficial, lida em 2026-10-14) | exemplo e instalador Linux/macOS existem; Windows por arquivo de exemplo |
| GitHub Copilot CLI | hooks de **política**: `/etc/github-copilot/policy.d/*.json`, `C:\ProgramData\GitHub\Copilot\policy.d\*.json` ou `HKLM\Software\Policies\GitHub\Copilot`; exigem privilégio elevado e o usuário não consegue alterar | `github/docs`, `content/copilot/reference/hooks-reference.md`, lido em 2026-10-17 (versão do produto desconhecida) | adaptador EXPERIMENTAL existe; entrega por política **não construída** |
| ChatGPT e Claude no navegador | política de instalação forçada de extensão no Chrome e no Edge. Fora das lojas, o Windows exige domínio (AD, Azure AD ou Chrome Enterprise Core) | `apps/extension/README.md`; o restante **A VERIFICAR** | extensão EXPERIMENTAL, não publicada em loja |
| Codex (OpenAI) | existe `allow_managed_hooks_only` em `requirements.toml`, mas o formato dos hooks não pôde ser lido | `openai/codex` `docs/config.md` | **A VERIFICAR**, não suportado |
| Copilot no VS Code, apps desktop de chat, celular | sem hooks nas fontes lidas | | **não coberto**; só o inference hook do Claude Enterprise (servidor) enxerga tudo, e nunca foi testado |

## Decisões que precisam do dono do produto (caras de desfazer)

1. **Credencial por máquina.** Hoje a chave `ps_...` fica em arquivo legível pela máquina. Um arquivo de instalação com a chave do tenant, copiado por qualquer funcionário, permite falsificar eventos. Proposta: o instalador leva só um **token de matrícula** (revogável, com validade e limite de uso) que a máquina troca por uma **chave própria do dispositivo**. Exige endpoint novo, tabela de dispositivos, revogação por máquina e uma página "Dispositivos" no console (cobertura: quantas máquinas e de qual ferramenta). Alternativa mais simples e mais fraca: uma chave por instalador.
2. **Executável sem Python.** O hook é Python (biblioteca padrão). Máquinas de empresa muitas vezes não têm Python. Proposta: gerar um executável único por sistema (PyInstaller, compilado no CI em runner de cada SO) e **assinar** (certificado de assinatura de código, custo e prazo reais). Alternativa: exigir Python instalado (frágil para vender).
3. **Onde roda o servidor.** SaaS multi-tenant gerenciado por nós (o desenho atual) ou uma instalação por cliente. Versão on-premise está fora do escopo agora. A nuvem de produção ainda não foi escolhida.

## Peças a construir, em ordem

| # | Peça | Observação |
|---|---|---|
| 1 | Gerador de instalador por tenant (`.ps1` e `.sh`; depois `.msi`/`.pkg`), silencioso, idempotente, com desinstalação e relatório de saída | sem decisão 1 e 2 resolvidas, usa chave do tenant e exige Python |
| 2 | Entrega por política: Claude Code (managed-settings), Copilot CLI (policy.d / registro), navegador (forcelist), sempre com cópia de segurança e remoção | cada mecanismo precisa de teste em máquina real |
| 3 | Matrícula e dispositivos (decisão 1) | |
| 4 | Painel de cobertura no console: dispositivos matriculados, última comunicação, ferramenta por dispositivo, máquinas sem coletor | é o que um comprador pede para provar valor |
| 5 | Piloto com 1 cliente e cerca de 50 máquinas, usando `docs/roteiro-testes-reais.md` e `docs/piloto.md` | |

## O que o comprador vai pedir (e o estado atual)

| Pedido | Estado |
|---|---|
| Prova de cobertura por ferramenta e máquina | não existe (peça 4) |
| Aviso e base legal para os empregados | modelos em `docs/lgpd.md`, **precisam de advogado**; a instalação silenciosa não dispensa o aviso |
| Login corporativo (SSO) | OIDC genérico implementado, **nunca testado com provedor real** |
| Texto sensível protegido, retenção, auditoria | implementado e testado com dados sintéticos |
| Integração com o SIEM | CEF/syslog e webhook implementados, nunca testados contra receptor real |
| Teste de invasão, questionário de segurança | teste externo não feito; modelo de ameaças em `docs/ameacas.md` |
| Preço, planos e cobrança | **fora do escopo** do projeto neste momento (`CLAUDE.md`) |

## Riscos novos desta proposta
- Instalar em massa um coletor de prompts é decisão de privacidade do cliente: o instalador deve **exigir** que o administrador confirme que os empregados foram avisados, e o aviso é obrigação do cliente.
- Política de nível de máquina que o usuário não consegue remover aumenta o impacto de um erro nosso (bug, API fora do ar). Padrão: sombra, modo de falha aberto, desinstalação testada.
- Um executável assinado e instalado em milhares de máquinas vira alvo de ataque à cadeia de suprimentos: assinatura, hash publicado e processo de release são requisitos, não detalhes.
