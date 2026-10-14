# Motor de detecção (Etapa 2)

Biblioteca Python em `packages/detection`, sem rede, sem banco e sem LLM externo. Taxonomia em `packages/taxonomy/taxonomy.yaml`.

```python
from promptshield_detection import analyze
a = analyze({"kind": "prompt", "content": {"text": "Cliente CPF 529.982.247-25"}, "context": {}})
a.category_ids()      # {'pii'}
a.masked_text         # 'Cliente CPF ***.***.***-25'
a.risk                # {'score': 58, 'reasons': [...]}
a.decision            # decisão SUGERIDA pelo motor; a política do tenant (Etapa 3) é quem decide
```

Para comandos de agente, use `kind: "tool_call"` com `content.tool_input.command` (ou `content.text`).
Ferramentas de arquivo (`Write`, `Edit`, `Read`) usam `content.tool_name` e `tool_input.file_path`.

## Como funciona

| Módulo | O que faz |
|---|---|
| `detectors/pii.py` | CPF e CNPJ com dígito verificador, RG com contexto, e-mail, telefone, cartão (Luhn e prefixo de bandeira), agência e conta |
| `detectors/secrets.py` | Formatos conhecidos (AWS, GCP, GitHub, Slack, Stripe, JWT, chave privada, Azure), string de conexão com senha, entropia perto de palavra-chave, lista de exemplos de documentação (confiança baixa) |
| `detectors/code.py` | Presença de código, SQL, IaC, logs, arquitetura, revisão de código, código proprietário (cabeçalho, caminho interno, nomes de projeto do tenant; licença aberta reduz) |
| `detectors/injection.py` | Heurísticas de injection direta e indireta, jailbreak, extração de system prompt, envenenamento de MCP, caracteres invisíveis, exfiltração por texto; gancho para classificador local |
| `detectors/agent.py` | Parser de shell (`shlex`): `rm -rf` em alvo amplo, `dd`, `mkfs`, `chmod` amplo, leitura de credenciais, rede para hosts fora da lista, upload, instalação de pacote de origem não padrão, escrita fora do projeto |
| `detectors/business.py` | Dicionários para saúde, RH, base de clientes, M&A, jurídico, propriedade intelectual, tóxico, uso pessoal e produtividade |
| `scoring.py` | Score 0 a 100 determinístico e versionado (`SCORE_VERSION`): maior contribuição inteira, demais com fator 0,3, bônus de contexto para ação de agente e conta pessoal; devolve os motivos |
| `masking.py` | Mascara spans sem sobreposição; o span mais longo vence (evita vazar segredo) |

Categoria só conta com confiança de 0,5 ou mais. Pesos por risco padrão: baixo 15, médio 35, alto 60, crítico 80.

## Limites conhecidos (não esconder)

- **Presidio (nomes e endereços) não está ligado.** Nomes de pessoas e endereços não são detectados. Pendente.
- **Classificador de injection:** nenhum modelo está empacotado nem foi medido. Só há a interface `InjectionClassifier` e as heurísticas. O download de modelos aberto não foi tentado neste ambiente. Pendente: escolher um modelo aberto, medir no conjunto e decidir.
- **E-mail em `tool_call` é ignorado** (evita falso positivo em `ssh user@host`); um e-mail dentro de um `curl -d` não será visto como PII.
- **Shell:** o parser divide por `;`, `&&`, `||`, `|`. Não entende subshell, `eval`, variáveis expandidas, aliases nem comandos ofuscados (base64 e depois shell). Um atacante determinado contorna.
- **Categorias de negócio** (jurídico, M&A, saúde, RH, PI, tóxico, uso pessoal) usam dicionários curtos. São as menos confiáveis.
- **Conjunto de teste:** 388 exemplos sintéticos escritos pela mesma autoria do motor. A concordância alta mede consistência, não generalização. Ver `docs/relatorio-etapa2.md`.
- **Repetição** (parte do score previsto na Etapa 7) não existe aqui: o motor não guarda histórico.
- `decision` é uma sugestão simples (bloquear segredos e ações destrutivas, mascarar PII, alertar injection) para testes; não substitui a política.
- Taxonomia: carregada por caminho relativo ao monorepo ou por `PROMPTSHIELD_TAXONOMY`. Instalação fora do monorepo precisa dessa variável.
- OWASP LLM Top 10 e MITRE ATLAS **não** foram mapeados: exigem abrir as versões atuais antes (regra do CLAUDE.md).

## Reproduzir

```bash
make test                                   # inclui metas de precisão, recall e latência
.venv/bin/python tests/fixtures/generate.py   # regenera o conjunto (semente fixa; segredos viram marcadores expandidos por tests/fixtures/synth.py)
.venv/bin/python packages/detection/scripts/evaluate.py --report docs/relatorio-etapa2.md
```
