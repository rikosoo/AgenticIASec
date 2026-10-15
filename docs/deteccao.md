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

- **NER (Presidio + spaCy) é opcional** (`make ner`, `analyze(..., ner=NerDetector())`). Só nomes completos (2+ palavras) contam; nome solto, cidades e nomes de empresa não. Custa cerca de 30 ms a mais por texto de 2.000 caracteres (p95 43 ms no relatório, perto do teto de 50 ms): usar em fila assíncrona ou aceitar o custo. Modelos pequenos do spaCy erram em nomes raros, estrangeiros e apelidos. Endereço (Rua/Av. com número), CEP e street address em inglês são regex e não dependem de NER.
- **Classificador de injection:** nenhum modelo está empacotado nem foi medido. Só há a interface `InjectionClassifier` e as heurísticas. O download falhou: o `huggingface.co` é bloqueado pela política de rede deste ambiente (proxy responde 403). Pendente até liberar o host.
- **E-mail em `tool_call` é ignorado** (evita falso positivo em `ssh user@host`); um e-mail dentro de um `curl -d` não será visto como PII.
- **Shell:** o parser divide por `;`, `&&`, `||`, `|`. Não entende subshell, `eval`, variáveis expandidas, aliases nem comandos ofuscados (base64 e depois shell). Um atacante determinado contorna.
- **Categorias de negócio** (jurídico, M&A, saúde, RH, PI, tóxico, uso pessoal) usam dicionários curtos. São as menos confiáveis.
- **Conjunto de teste:** os números altos medem consistência com um gabarito escrito pela mesma autoria do motor, não generalização. Ver a seção "Avaliação em português e inglês" abaixo e `docs/relatorio-etapa2.md`.
- **Repetição** (parte do score previsto na Etapa 7) não existe aqui: o motor não guarda histórico.
- `decision` é uma sugestão simples (bloquear segredos e ações destrutivas, mascarar PII, alertar injection) para testes; não substitui a política.
- Taxonomia: carregada por caminho relativo ao monorepo ou por `PROMPTSHIELD_TAXONOMY`. Instalação fora do monorepo precisa dessa variável.
- OWASP LLM Top 10 e MITRE ATLAS **não** foram mapeados: exigem abrir as versões atuais antes (regra do CLAUDE.md).

## Avaliação em português e inglês (Etapa 9b)

Reforço para os dois idiomas: comparação sem acento e sem caixa com offsets preservados (`textnorm.fold`), validadores de IBAN e ABA, formatos de documento e telefone dos EUA, Reino Unido e Brasil, mais tokens de provedores, comandos de agente (Windows, nuvem, persistência, shell reverso) e paráfrases de injection/jailbreak.

Metodologia: quatro conjuntos sintéticos, cada um escrito depois de ver os erros dos anteriores. Só o D nunca foi usado para ajustar regra.

| Conjunto | Exemplos | 1ª medição (às cegas) | Depois do ajuste | Papel hoje |
|---|---|---|---|---|
| Original | 425 | n/d | 0 divergências | desenvolvimento |
| A | 266 | 68,0% | 96,2% | desenvolvimento |
| B | 194 | 81,4% | 97,9% | desenvolvimento |
| C | 168 | 84,5% | 97,6% | desenvolvimento |
| **D** | 152 | **82,2%** (F1 0,818; PT 81,4%, EN 82,8%; negativos difíceis limpos 67/70) | não ajustado | **estimativa independente** |

Leitura honesta: a estimativa de generalização é a primeira medição de cada conjunto novo (cerca de 82% de acerto exato, F1 0,82), não os 96% a 98% dos conjuntos já ajustados. As lacunas conhecidas do D: paráfrases de injection e extração de system prompt, `conteudo_toxico` e `uso_pessoal` coloquiais, remuneração/comissão em RH, divulgação de condição de saúde em primeira pessoa, cláusulas contratuais, e falsos positivos em e-mail de exemplo e cartão de teste. Ajustar contra o D o tornaria conjunto de desenvolvimento e exigiria um conjunto E; por isso ele fica como está. `produtividade_legitima` é neutra na medição. Alguns rótulos foram corrigidos durante a revisão (cartão e IBAN isolados não são `pii`), e isso está nos próprios arquivos.

Medição de verdade só vem do piloto (amostra aleatória de sinalizados, ver `docs/piloto.md`).

```bash
.venv/bin/python packages/detection/scripts/holdout.py holdout_d --misses
```

## Reproduzir

```bash
make test                                   # inclui metas de precisão, recall e latência
.venv/bin/python tests/fixtures/generate.py   # regenera o conjunto (semente fixa; segredos viram marcadores expandidos por tests/fixtures/synth.py)
.venv/bin/python packages/detection/scripts/evaluate.py --report docs/relatorio-etapa2.md
```
