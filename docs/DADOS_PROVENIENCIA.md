# Dados e proveniência — LexIA v3

## 1. ANM · SIGBM (dado oficial, conectado)

| Campo | Valor |
|---|---|
| Fonte | Agência Nacional de Mineração — Sistema Integrado de Gestão de Barragens de Mineração |
| Listagem | https://dadosabertos.anm.gov.br/SIGBM/ |
| Arquivo | `Barragens.csv` (+ dicionário `metadados-sigbm.ods`) |
| Frequência declarada | Diária |
| Licença | **A confirmar.** Dados abertos governamentais publicados pela ANM; o portal não exibe licença explícita na listagem. Antes de redistribuir o snapshot fora da equipe, conferir os termos no catálogo dados.gov.br |
| Coleta | Manual (endpoint `POST /api/connectors/sigbm/sync`, papel curador). Nunca roda a cada carregamento de página |
| Robots | `robots.txt` responde 403 (página de bloqueio); fizemos uma coleta única do arquivo listado publicamente, com User-Agent identificado |

### Snapshot incluído no repositório
`data/snapshots/sigbm/sigbm-20261106T195313/`

| Item | Valor |
|---|---|
| Coletado em | 2026-11-06T19:53:13Z |
| Last-Modified na fonte | Fri, 06 Nov 2026 09:18:44 GMT |
| Tamanho | 3.386.460 bytes |
| SHA-256 | `6aa5f152db495348d9e22abbc0bcdc4cba17fc6f4070772b279f445b18ee574a` |
| Linhas lidas / aceitas / rejeitadas / duplicadas | 908 / **902** / 6 / 0 |
| Codificação / separador detectados | cp1252 / vírgula |
| Divergência com o dicionário | O dicionário declara ponto e vírgula; o arquivo usa vírgula |
| Colunas | 124 na fonte; 22 mapeadas (`data/connectors/sigbm_schema.json`) |

Arquivos do snapshot: `Barragens.csv` (original, intocado), `manifest.json` (metadados + relatório de qualidade) e `records.json` (normalizado).

### Regras de qualidade
- Coordenadas no formato oficial `sGG°MM'SS.SSS''`. Minutos ou segundos ≥ 60, latitude incoerente com o hemisfério declarado ou ponto fora do território → linha **rejeitada com motivo**. Nada é corrigido por suposição. No snapshot, as 6 rejeições são minutos/segundos ≥ 60 na própria fonte (IDs 9540, 9171, 9051, 9050, 10256, 9818).
- Deduplicação pelo ID oficial.
- `-` e vazio viram ausente, nunca "Não".
- Schema drift (coluna obrigatória ausente) interrompe a importação (`SchemaDriftError`).

### Dados pessoais
A coluna `CPF_CNPJ` mistura CNPJ e CPF. Em 102 registros a fonte publica CPF parcialmente mascarado (`***nnnnnn***`). A LexIA **não exibe nem indexa** esses documentos e substitui o nome por "Pessoa física (nome não exibido)".

### Categorias oficiais
CRI (Categoria de Risco) e DPA (Dano Potencial Associado) são **categorias** Baixa/Média/Alta definidas pela fonte. A LexIA as mostra como estão, nunca como volume, probabilidade ou prioridade, e não infere risco de rompimento, segurança ou irregularidade.

## 2. Registro de organizações e vínculo de empresa
- `organization_registry` é agrupado por CNPJ completo; pessoa física não é agrupada.
- Busca: CNPJ idêntico (confiança 0,95), mesma raiz de CNPJ (0,85) ou correspondência textual (≤ 0,6).
- `entity_match_confidence` mede o vínculo **cadastral**, não certeza jurídica nem grupo econômico. Todo vínculo aparece como **"a confirmar"**; a confirmação humana (`POST /api/entities/link`) fica na trilha de auditoria.
- Exemplo verificável: o CNPJ 33.592.510/0001-54 (VALE S.A. no SIGBM) tem **104** estruturas no snapshot. "Vale Verde Mineração" ou qualquer nome com "Vale" é só correspondência textual.

## 3. Corpus normativo (curado, sem texto integral)
- `data/sources.json`: 42 fontes do dossiê de 05/11/2026 (níveis T/C/I).
- `data/provisions.json`: 9 dispositivos com `valid_from`, `valid_to`, `observed_at`, `source_published_at`, `ingested_at`, `superseded_by` e `source_snapshot_id`. Este último é `null` porque não há snapshot do texto.
- Textos oficiais apontados: NR-20 atualizada 2025 (gov.br/MTE) e Resolução ANM 245/2026 (anmlegis).

## 4. Dados sintéticos
`data/assets.json`: 12 ativos **fictícios**, rotulados "CENÁRIO HIPOTÉTICO" e desenhados com outra forma de marcador (losango). Nunca se misturam com coordenadas oficiais sob a mesma legenda.

## 5. Adaptadores não conectados
SIGMINE, SNISB, ANP E&P, Ibama, AGROFIT, Anvisa e Anatel aparecem em `data/connectors.json` com estado `NAO_CONECTADO`. Nenhuma coleta é feita até verificar formato, termos e licença.

## 6. Malha das UFs (IBGE)
`web/br_uf.json` foi gerado da **API de malhas v3 do IBGE** (`servicodados.ibge.gov.br/api/v3/malhas/paises/BR?intrarregiao=UF&qualidade=minima`), coletada em 06/11/2026 e projetada para as coordenadas do mapa. São dados públicos do IBGE.

## 7. Monitor de fontes oficiais (v4)
- Verifica a cada 6 h (`TORRE_MONITOR_MIN`) e sob demanda (curadoria): a listagem do SIGBM, as fontes T/C do catálogo em domínios oficiais e os textos oficiais dos dispositivos (NR-20 PDF, ANM Legis).
- Respeita o `robots.txt` de cada host, faz uma requisição por vez com 1 s de intervalo, identifica o User-Agent, usa timeout e limita o download a 8 MB.
- Compara o SHA-256 do texto normalizado (sem scripts e estilos). Se mudou, gera uma notificação "requer curadoria". **Nunca altera regra, vigência ou triagem sozinho.**
- SIGBM: se a listagem oficial muda (data/tamanho), coleta e valida um novo snapshot automaticamente.
- Não coletados, por decisão de conformidade: **site do DOU** (`robots.txt` com `Disallow: /`; o caminho oficial é o INLABS, com credencial) e **LexML** (verificação anti-robô).

## 8. Contas e dados pessoais
Cadastro: nome, e-mail, tipo; empresa: razão social, CNPJ (validado por dígito verificador) e função; cidadão: UF e município opcionais. Senha com PBKDF2-HMAC-SHA256 (200 mil iterações, sal aleatório). Sessão em cookie HttpOnly, com só o hash do token no banco. Consentimento LGPD registrado com data. A organização das contas demo, "Mineradora Exemplo S.A.", é fictícia.
