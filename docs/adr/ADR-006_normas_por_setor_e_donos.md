# ADR-006 — Normas filtradas por setor, nenhum alerta sem dono e prova de cobertura

Data: 07/11/2026 · Estado: aceito (demo)

## Problema
1. O catálogo de normas era de barragem de mineração e não tinha setor: uma denúncia sobre o vertedouro de uma **usina** citava a Res. ANM 95 (só mineração). A Central de IA buscava em todas as normas.
2. Alerta cujo papel não tinha pessoa cadastrada **não chegava a ninguém**, em silêncio.
3. Não havia como provar que o catálogo cobre cada setor e área.

## Decisões
1. **Metadados por norma** (`app/normas_setor.py`, regra `normas-setor-v1`): setores, tipos de ativo, áreas (jurídico, operacional, segurança, ambiental, trabalhista, radiológico, documental), órgão e nível de verificação (T/C/I).
2. **Filtrar antes de buscar.** A denúncia descobre o setor e o tipo do alvo (ativo da empresa, barragem SIGBM, mina SIGMINE, barragem sem dono SNISB) e só considera normas aplicáveis. As regras listam equivalentes por setor (ex.: estrutura com trinca → Res. ANM 95 | REN ANEEL 1.064 | Res. ANA 236), e o filtro escolhe. A Central de IA recebe o setor do perfil e retira do corpus dispositivos de órgãos de outro setor; se a pergunta cita órgão de outro setor, responde com aviso.
3. **Barreira na saída.** Norma proposta pela IA que não se aplica ao setor/tipo é recusada e listada em "normas descartadas", com o motivo.
4. **Lacuna não some.** Tema reconhecido sem norma específica aplicável → `lacuna: true`, aviso de curadoria; a denúncia segue com a base geral. Norma sem metadados → "sem classificação" (fila da curadoria; não é usada).
5. **Nenhum alerta sem dono** (`app/ativos.py`): papel sem pessoa cadastrada fica marcado; se nenhum papel da rota tem pessoa, o alerta escala para compliance → gestão → curadoria da LexIA. Ocorrência sem rota configurada vai para compliance. O servidor verifica as pessoas reais da organização (contas empresa por função). Indicador "sem dono" sempre visível (meta: 0).
6. **Multi-área.** Uma ocorrência pode pertencer a várias áreas (ex.: licença vencida = jurídico + ambiental + documental).
7. **Prova.** Avaliação `eval-v2` (50 casos): novas categorias `setor_normas` (8 casos, incluindo a mesma denúncia em mineração × energia × saneamento, barragem sem dono só com normas gerais e lacuna → curadoria) e `donos` (5 casos). Matriz de cobertura setor × área em Central de IA → Avaliação (`/api/cobertura`).

## Normas novas (verificadas em 07/11/2026; conferir texto consolidado antes de uso oficial)
- REN ANEEL 1.064/2023 (alterada pela REN 1.129/2025) — barragens de usinas hidrelétricas.
- Resolução ANA 236/2017 (alterada pela Res. ANA 121/2022) — barragens de usos múltiplos em rios federais (em rios estaduais, órgão estadual).
- Portaria GM/MS 888/2021 — potabilidade.
- NR-22 (mineração) e NR-10 (eletricidade), MTE.

## Limites conhecidos
- A matriz conta normas do catálogo curado; não substitui a revisão de um especialista por setor. Os gabaritos são da equipe, não validados por especialista externo.
- O fiscalizador de barragens de saneamento depende do rio (federal/estadual) e do uso: o sistema diz "ANA ou órgão estadual" e pede confirmação.
- Notificação para a curadoria usa a audiência `func:curadoria` da demonstração.
