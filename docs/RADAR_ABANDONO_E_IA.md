# Radar de abandono, barragens órfãs e Central de IA (v5)

## ADR-007: sinais de abandono por regra versionada, não por modelo
**Contexto.** Barragem sem manutenção é risco quando o dono some (prejuízo, falência, pessoa física sem estrutura). A lei já define quem responde, mas ninguém cruza os dados públicos para mostrar onde isso está acontecendo.
**Decisão.** Os sinais e o nível de atenção são regras explicáveis (`app/abandono.py`, `abandono-v1`). Cada sinal mostra o campo e o valor da fonte e cita o artigo da Lei 12.334/2010. A IA generativa (opcional) só converte pedidos em português em filtros, e um verificador descarta qualquer valor fora do vocabulário.
**Consequências.** O resultado é auditável e reproduzível; nenhuma barragem é declarada "abandonada". Crítica/Alta exigem pelo menos um sinal central (sinais genéricos como "autuada" ou "inspeção antiga" não bastam).

## Dados novos
| Fonte | Como | Arquivo |
|---|---|---|
| ANA · SNISB (serviço ArcGIS público) | `app/connectors/snisb.py`, paginação de 2000 com pausa de 1 s | `data/snapshots/snisb/<id>/orphans.json` (7.937 sem empreendedor), `mining.json` (908 complementos por ID SIGBM), `manifest.json` com SHA-256 |
| ANM · SIGBM | esquema ampliado (`sigbm_schema.json` v2026-11-07): situação, DCE, descaracterização, população a jusante, conservação, alturas/volumes | `records.json` regenerado do CSV bruto quando o esquema muda |

Privacidade: nome do empreendedor do SNISB não é coletado; colunas `RT/Declaração` e `RT/Empreendimento` do SIGBM são excluídas; pessoa física aparece como "Pessoa física (nome não exibido)".

## Base legal usada (texto compilado no Planalto)
Art. 2º IV (empreendedor; proprietário do terreno subsidiário) · Art. 4º III (responsabilidade objetiva) · Art. 17 I (responsável até a descaracterização) · Art. 17 §2º (caução/seguro) · Art. 17-A §2º e §3º (representação; dever de apurar) · Art. 18 caput, §2º e §3º (recuperar/descaracterizar; Defesa Civil na omissão; monitoramento pelo sucessor) · Art. 18-A (ZAS) · CF art. 129 III (MP).

## Funções
- **Radar de abandono** (`#/radar`): KPIs clicáveis, consulta em português, mapa por UF + pontos, lista por atenção, ficha com abas Sinais · Responsáveis · Plano de contingência · Representação · Inconsistências; Panorama do setor; Como funciona; exportação CSV.
- **Plano de contingência:** etapas condicionais (garantia só para rejeitos com CRI/DPA médio-alto; ZAS só com população), dependências, complexidade e custo relativo, viabilidade e caminho mais rápido. "Feito" exige evidência; tudo vai para a trilha de auditoria.
- **Representação:** rascunho com os campos da fonte, marcado "NÃO FOI ENVIADO". Quem gera não aprova (quatro olhos); justificativa obrigatória. Cidadão só baixa o texto.
- **Notificações:** resumo no primeiro cálculo e aviso quando barragens entram em Crítica após novo snapshot (SIGBM ou SNISB, inclusive pelo monitor).
- **Central de IA** (`#/ia`): conversa, consulta → filtros (mostra de onde veio cada filtro), inconsistências (regras de coerência + mediana/MAD em escala log), rascunhos, transparência. Sem chave, nada é rotulado como IA generativa.
- **Mini-chat:** bolinha flutuante em todas as páginas do painel (oculta na página IA). O topo tem só um botão pequeno "IA"; o trilho lateral antigo foi removido.

## Detector de risco oculto (aprendizado de máquina) — ADR-008
**O que é.** Regressão logística L2 (implementação própria, `app/risk_model.py`, `risco-oculto-v1`) treinada nas barragens da PNSB do SIGBM para reconhecer o perfil técnico declarado das que estão em nível de emergência. Aponta as que têm esse perfil mas se declaram "sem emergência" (pedido de conferência, não diagnóstico).
**Vazamentos evitados.** Sem DCE (a norma da ANM já leva DCE não atestada à emergência), sem CRI/DPA e sem população a jusante; treino só com barragens da PNSB (as únicas que declaram nível).
**Validação (snapshot 06/11/2026, calculada pelo próprio sistema).** AUC 0,87 em validação cruzada estratificada de 5 dobras; 70% das 50 mais suspeitas estavam de fato em emergência (taxa-base 17%, 4,2×). 28 barragens sinalizadas. Os números mudam com novos snapshots.
**Explicação.** Cada barragem mostra os 3 campos que mais empurram a parecença acima da média do campo.

## Mapa clicável e satélite
- Clicar num número (agrupamento) abre um cartão com a lista das estruturas, a imagem de satélite da área e os botões "Aproximar" e "Google Maps".
- A ficha de cada barragem oficial mostra o recorte de satélite (Esri World Imagery, com atribuição) e atalhos para o Google Maps.
- Pontos de cenário hipotético não recebem imagem: as coordenadas são ilustrativas.
- No portal do cidadão, clicar num ponto mostra a barragem, o satélite e o atalho para o Radar. No Radar, clicar num estado filtra a lista.

## Critérios de aceite e casos testados (`tests/test_radar.py`, `scripts/e2e_radar_ia.mjs`)
- Positivo: inativa sem projeto + DCE não enviada + população → Crítica, com evidência e artigo em cada sinal.
- Negativo: barragem regular → "Sem sinal"; sinais genéricos sozinhos nunca chegam a Alta.
- Falta de dados: órfã → empreendedor "faltando", proprietário do terreno a identificar, viabilidade Baixa.
- Conflito: altura atual > licenciada, inativa em emergência, DPA alta fora da PNSB → inconsistências.
- IA: proposta com UF/sinal inventado é filtrada; falha do provedor volta para as regras.
- Permissões: auditor não edita plano; operação não aprova rascunho; autor não aprova o próprio rascunho.
- E2E: 23 verificações, desktop 1440 e celular 390 sem rolagem horizontal. Capturas em `docs/screenshots/radar_ia/`.

## Não testado / limites
- Interpretação de filtros com Claude real (sem `ANTHROPIC_API_KEY` neste ambiente; testada com gerador falso).
- Identificação do proprietário do terreno (CAR/SIGEF/cartório) não é automatizada.
- Pesos e limiares (`abandono-v1`) são escolha da equipe, não calibrados com desfechos reais.
- `scripts/e2e_cdp.mjs` foi atualizado para a Visão Executiva e o Laboratório redesenhados (47 verificações, sem erros).
- Imagens de satélite dependem de internet e dos termos de uso da Esri; para uso comercial, confirmar licença ou trocar por provedor contratado.
