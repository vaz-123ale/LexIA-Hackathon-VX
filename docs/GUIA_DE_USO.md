# Guia de uso — LexIA v3

## Iniciar
`python -m app.server` na raiz → http://localhost:8765. Banco local em `var/torre.db` (descartável). Roteiro de apresentação: `docs/DEMO_PITCH_5_MIN.md`.

## Topo (vale para todas as áreas)
- **Busca global:** leva ao Atlas já filtrado.
- **Data-base:** recalcula vigência e triagem. A pílula "Simulando…" volta para hoje.
- **SIGBM · 902 · hoje:** fonte oficial carregada e idade do snapshot.
- **Usuário de demonstração:** define o que você pode alterar. Visitante só lê.
- **Perguntar sobre esta análise:** abre o assistente com o contexto atual.

## 1. Visão Executiva
Três métricas, cada uma com o "i" explicando o cálculo; fila por prioridade (passe o mouse na prioridade para ver a fórmula); marcos dos próximos 12 meses.

## 2. Atlas Empresarial
1. Digite uma empresa, CNPJ, município ou ID. Organizações correspondentes aparecem com a confiança do vínculo cadastral e o aviso "vínculo a confirmar".
2. **Filtrar por CNPJ** isola as estruturas daquele CNPJ.
3. Filtros: UF, situação operacional, PNSB, CRI/DPA (categorias oficiais), enquadramento LexIA.
4. Camadas: dado oficial (●) e cenário hipotético (◆). Ao ativar a hipotética, escolha a norma.
5. Clique no mapa ou na tabela para abrir a ficha: Situação · Por que foi selecionado · O que está faltando · Ações possíveis.
6. "Globo (opcional)" mostra os mesmos pontos em 3D.

## 3. Laboratório de Impacto
Escolha a norma e use os atalhos de data. Veja o diff por dispositivo, a carteira impactada (oficial para ANM), a cascata do item selecionado e, em ativos hipotéticos, o "e se". O grafo abre em **Ver dependências**.

## 4. Decisão & Execução
- **Revisões:** quadro por estado de fluxo; atribuir função; mover com fundamentação obrigatória. Confirmar/rejeitar exige jurídico, compliance ou especialista.
- **Evidências:** matriz de lacunas; registro com SHA-256.
- **Decision Lab:** premissas mín/base/máx por opção → total, memória de cálculo, sensibilidade; salvar vinculado a uma revisão.
- **Dossiês de decisão:** exportar o Decision Pack (imprimir ou salvar como PDF).
- **Calendário de marcos:** datas por dispositivo; licenças sem fonte conectada.

## 5. Fontes & Governança
Conectores e snapshots (qualidade, linhas rejeitadas, sincronizar), fontes (42), ingestão com casos-limite, auditoria encadeada, pipeline de IA e checklist, usuários e permissões, maturidade por vertical.

## Reiniciar a demo
Entre como *Gabi (curadoria)* → **Reiniciar estado DEMO** (menu lateral). Fontes, snapshots e originais são preservados.
