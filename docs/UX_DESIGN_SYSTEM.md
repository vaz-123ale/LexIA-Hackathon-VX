# UX e design system — LexIA v3

## Revisão das imagens locais (v13)
O painel empresarial usa Inter Variable incorporada, distribuída sob SIL OFL (`web/fonts/OFL.txt`), com pesos reais de 100 a 900. A paisagem e os ícones de banco de dados e alvo fornecidos em `imagens` são usados sem alterar seus arquivos originais. O enquadramento é feito em CSS. A implementação está em `reference.css` e `precision.css`; o tema público continua em `styles.css`.

No Atlas, em 1672 × 941, lateral = 276 px, cabeçalho = 64 px, banner = 104 px e filtros = 143 px. Mapa e ficha iniciam em y = 357 px; o mapa tem 506 px de altura útil. A Visão Executiva substitui o mapa por mudanças, dispositivos, fontes e lacunas. O mapa completo permanece no Atlas. As cores cartográficas são decorativas e os clusters representam os dados filtrados, não contagens fixadas na imagem.

Capturas e medidas da inspeção: `docs/screenshots/v13-final/`. Critérios e limites: `docs/REVISAO_VISUAL_V13.md`. As descrições históricas abaixo documentam versões anteriores.

## Princípios
1. Densidade controlada: na tela principal, só a próxima ação e no máximo duas informações secundárias. O detalhe fica na ficha.
2. A fonte aparece ao lado da afirmação.
3. Cor nunca é o único indicador: todo rótulo semântico tem ícone e texto.
4. Dado oficial e cenário hipotético nunca se misturam: rótulos permanentes e marcadores com formas diferentes (● oficial, ◆ hipotético).
5. O papel da IA fica na trilha e na explicação, não em selos repetidos em todos os cards.

## Identidade visual "Painel institucional" (rev. 5, baseada na referência aprovada)
Tema claro, com menu lateral azul-marinho em gradiente e item ativo em azul cheio com sombra. A topbar é branca e traz:
- busca com atalho **Ctrl + K**;
- seletores de data-base, fontes oficiais e modo da IA;
- sino com ponto de não lidas e avatar com as iniciais.

O conteúdo usa cartões brancos com borda clara e sombra suave. A Visão Executiva segue a referência:
- banner "Panorama Regulatório da Operação" com ilustração vetorial própria e corte diagonal azul;
- 4 indicadores com ícone em fundo tingido e borda colorida à esquerda;
- mapa por UF (malha IBGE) com legenda "Resultado da triagem";
- fila prioritária com ícones de traço por tipo de ativo e selo de prioridade rosado;
- marcos em linha do tempo e faixa "Insight da LexIA".

## Tokens
| Token | Valor | Uso |
|---|---|---|
| `--navy` / `--navy2` | #0B1F3A / #12305A | menu lateral, cabeçalhos escuros, site |
| `--blue` | #1570EF | ação principal, item ativo, links |
| `--bg` / `--card` | #F4F6FA / #FFFFFF | fundo / cartões |
| `--line` / `--line2` | #E5EAF1 / #D3DCE8 | bordas |
| `--text` / `--text2` / `--text3` | #0F172A / #475569 / #8392A7 | texto |
| Indicadores | #2F6FED · #F59E0B · #3B82F6 · #7C5CFF | borda e ícone dos 4 KPIs |
| Triagem | candidato #F5B301 · dados insuficientes #8B5CF6 · transição #3B82F6 · consulta #10B981 · fora do escopo #CBD5E1 · sem vínculo #64748B | pontos e legenda do mapa |
| Prioridade alta | fundo #FDE2E4, texto #D63A3F | selo "Alta" |
| Raio / sombra | 14 px · `0 6px 18px rgba(16,24,40,.05)` | cartões |
| Tipografia | Segoe UI Variable / Inter; títulos 800; números tabulares | — |

## Três experiências
- **Site público** (`#/inicio`, `#/sobre`, `#/entrar`, `#/cadastro`): cabeçalho branco, abertura navy com globo real das 902 barragens, seções de problema, como funciona, públicos, canais oficiais e chamada final.
- **Portal do cidadão** (`#/cidadao`): linguagem simples, barragens da região (UF/município), emergência (199/193), regras em etapas, avisos, glossário e "Acompanhar".
- **Painel da empresa** (5 áreas): visual da referência.

## App (PWA)
- `web/manifest.webmanifest` (standalone, ícones 192/512 e SVG, atalhos para Atlas, Laboratório e Decisão) e `web/sw.js`.
- O service worker é sempre **rede primeiro**: a versão mais nova aparece em cada atualização, e o cache só entra quando o servidor está inacessível. POST nunca é armazenado.
- Abaixo de 800 px: barra de navegação inferior com as 5 áreas, topo compacto (busca, data, usuário, "✦ Perguntar"), margens seguras do iPhone (`safe-area-inset`).
- Botão **Instalar app** aparece quando o navegador oferece a instalação (Chrome/Edge; no iPhone, use Compartilhar → Adicionar à Tela de Início).

## Layout
- Sidebar com 5 áreas e ícones lineares em SVG. A topbar tem busca global, data-base, estado da fonte (SIGBM · registros · idade), usuário de demonstração e "Perguntar sobre esta análise".
- Grades `8/4` e `6/6`, que viram uma coluna abaixo de 1100 px. Abaixo de 1100 px a sidebar vira gaveta (☰).
- Verificado sem rolagem horizontal em 1440×900, 1366×768, 768×1024 e 390×844 (E2E).

## Componentes
| Componente | Onde |
|---|---|
| `tag` (eixo + ícone + texto) | ciclo normativo, aplicabilidade, fluxo, prioridade |
| `origin` (DADO OFICIAL / CENÁRIO HIPOTÉTICO) | tabelas, fichas, cartões, dossiê |
| Ficha lateral em 4 seções | Atlas: Situação · Por que foi selecionado · O que está faltando · Ações possíveis |
| Diff lado a lado | Laboratório (antes/depois por dispositivo; tabela compacta quando não há versão anterior) |
| Cascata | norma → dispositivo → obrigação → ativo → processo → controle → evidência → contrato/projeto → decisão (lacunas tracejadas) |
| Kanban por eixo de fluxo | Decisão & Execução |
| Gaveta do assistente | global, recebe o contexto atual, mostra trechos e abstenção |
| Mapa SVG com clusters | Atlas (roda, arraste, +/−, enquadrar; Tab e Enter nos marcadores) |

## Estados
Carregando ("Carregando…"), vazio (caixa tracejada com instrução), erro recuperável ("Tentar novamente"), sem permissão (botão desabilitado + dica do papel exigido), toast de sucesso/erro, filtro ativo ("Limpar filtros") e data simulada (pílula "Simulando dd/mm/aaaa ×").

## Acessibilidade
Link "pular para o conteúdo"; `aria-current` no menu; `role="tab"`/`aria-selected`; marcadores e clusters focáveis com rótulo; `prefers-reduced-motion` respeitado; contraste do texto principal e secundário acima de AA sobre `--s1`. Pendente: auditoria formal com leitor de tela.

## Modo claro
Não implementado. Muitas cores de estado ainda estão fixas no código e um tema claro exigiria revisão de contraste. Ficou no roadmap para não criar regressão.
