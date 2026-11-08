# Análise própria: porte do empreendedor × situação declarada das barragens de mineração

**Autoria:** equipe LexIA, a partir de dados públicos da ANM.
**Atenção:** os percentuais abaixo **não** foram publicados pela ANM nem por terceiros. São um cálculo da equipe, reproduzível com `python scripts/analise_porte_sigbm.py`.

## Fonte dos dados (oficial)
| Item | Valor |
|---|---|
| Base | SIGBM — Sistema Integrado de Gestão de Barragens de Mineração, ANM |
| Página oficial de dados abertos | https://dadosabertos.anm.gov.br/SIGBM/ |
| Arquivo | https://dadosabertos.anm.gov.br/SIGBM/Barragens.csv |
| Dicionário de dados | https://dadosabertos.anm.gov.br/SIGBM/metadados-sigbm.ods |
| Catálogo de bases da ANM | https://www.gov.br/anm/pt-br/acesso-a-informacao/dados-abertos/bases-de-dados |
| Versão usada | coletada em 06/11/2026 19:53 UTC (Last-Modified na fonte: 06/11/2026 09:18 GMT) |
| SHA-256 do arquivo | `6aa5f152db495348d9e22abbc0bcdc4cba17fc6f4070772b279f445b18ee574a` |
| Cópia local | `data/snapshots/sigbm/sigbm-20261106T195313/Barragens.csv` |

O arquivo é atualizado diariamente pela ANM. Uma coleta em outro dia pode dar números um pouco diferentes.

## Definições usadas (escolha da equipe)
- **Empreendedor:** mesmo valor na coluna `CPF_CNPJ`.
- **Pequeno:** empreendedor com até 5 barragens, cooperativa (nome contém "cooperativa") ou pessoa física (documento em formato de CPF, já mascarado pela ANM).
- **Grande:** empreendedor com mais de 5 barragens.
- **Emergência:** coluna "Nível de Emergência" diferente de "Sem emergência". O nível é **declarado pelo empreendedor**.
- **População a jusante:** coluna "Existência de população a jusante" = "Existente" (pessoas morando permanentemente na área afetada).

## Resultados (versão de 06/11/2026)
| Indicador | Valor |
|---|---|
| Barragens no SIGBM | 908 |
| Empreendedores distintos | 301 |
| Empreendedores pequenos | **278 (92%)** |
| Barragens de pequenos | **512 (56%)** |
| Barragens com nível de emergência declarado | 77 |
| … delas, de empreendedores pequenos | **56 (73%)** |
| Taxa de emergência entre pequenos × grandes | **11% × 5%** |
| Em emergência com população permanente a jusante | 25, sendo **17** de pequenos |
| Barragens em nome de pessoa física | **102**, de **67** pessoas; 44 inseridas na PNSB; 99 em MT |
| Declaração de estabilidade (RISR) não atestada ou não enviada, entre as da PNSB | cooperativas **20%** × grandes **6%** |

## Como interpretar (e como não interpretar)
- Mostra **concentração** nos dados declarados. **Não** prova causa e **não** indica culpa ou negligência de ninguém.
- O nível de emergência é **autodeclarado** e pode ter muitas causas (idade da estrutura, tipo de barragem, critério técnico).
- Não citar nomes de empreendedores, e nunca de pessoas físicas (dado pessoal).
- Forma sugerida de citar: *"Análise da equipe sobre dados públicos do SIGBM/ANM (versão de 06/11/2026)."*

## Contexto externo usado no pitch (reportagens; conferir datas antes de usar no slide)
- TCU: a ANM não tem pessoal nem estrutura para auditar periodicamente as barragens, e a tarefa recai sobre as próprias mineradoras — [IHU/Unisinos](https://ihu.unisinos.br/categorias/586635-orgao-federal-que-fiscaliza-barragens-e-o-2-mais-exposto-a-fraudes-e-corrupcao-diz-tcu); documento do TCU no [Senado](https://legis.senado.leg.br/sdleg-getter/documento/download/bdb8d105-4a07-4863-a484-ca5cb3d4cc6f).
- Quadro de servidores da ANM em 62% da necessidade — [Brasil de Fato](https://brasildefato.com.br/?p=635940).
- Brumadinho: engenheiros que assinaram a declaração de estabilidade respondem criminalmente — [Lex](https://www.lex.com.br/stj-mantem-acoes-penais-contra-engenheiros-da-vale-e-tuv-sud-por-rompimento-da-barragem-em-brumadinho/), [ECCHR](https://www.ecchr.eu/fileadmin/Pressemitteilung_weitere_Sprachen/PR_PORT_Um_ano_depois_do_rompimento.pdf).
- Cerca de 860 normas editadas por dia útil no Brasil (IBPT, até set/2024) — [Monitor Mercantil](https://monitormercantil.com.br/constituicao-faz-36-anos-com-cerca-de-78-milhoes-de-normas-editadas-595-por-dia/).
- CNI, Sondagem Especial nº 100 (mar/2026): 34% têm dificuldade de encontrar as regras e 41% de entendê-las — [Agência CNI](https://noticias.portaldaindustria.com.br/noticias/politica-industrial/cni-41-das-empresas-tem-dificuldade-para-entender-normas-e-reprovam-ambiente-regulatorio/).
