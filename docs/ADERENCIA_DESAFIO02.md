# Confrontação com o briefing oficial VX/D02

Verificado em 06/11/2026 pelo Drive indicado pelo usuário. Fontes: [Desafio 02 — LexIA de controle regulatória](https://drive.google.com/file/d/1HIrd1PRfI_KdEm39khbA2WAJA3cic5uJ/view), cinco páginas, e [Guia dos desafios](https://drive.google.com/file/d/11V89ShPDy3d0wMDcw8zzyazLeAVdFEw-/view), quatro páginas. Leitura integral do texto, preservando distinção dos exemplos fictícios. Não foram baixados ou redistribuídos os PDFs na aplicação.

## O problema central confirmado

O desafio aborda publicações oficiais dispersas, excesso ou falta de alertas, contexto operacional de cada empresa e transformação de mudanças em trabalho atribuível e comprovável. Também exige pensar em normas que modificam obrigações já mapeadas. Não restringe o time a mineração, a uma empresa determinada ou ao DOU como única fonte. O guia aceita um recorte bem resolvido; pede MVP funcional, mercado e pitch de cinco minutos.

## Aderência real

| Necessidade no D02 | Estado do projeto | O que demonstrar ou corrigir |
|---|---|---|
| Fontes oficiais e coleta | PARCIAL: SIGBM e monitor; acervo curado | Diferenciar dado de estrutura, texto normativo e mudança de página; DOU não integrado |
| Relevância por atividade e território | PARCIAL: regras, atributos, mapa e triagem de projeto | Não confundir palavra-chave, nome ou proximidade com incidência |
| Pouco ruído sem ocultar o que importa | PARCIAL: triagem com estados/lacunas | Falta caixa de exclusões com motivo, possibilidade de revisão e teste de itens não mostrados |
| Unidade afetada | IMPLEMENTADO no recorte de ativos e cenários | Mostrar uma unidade no escopo, outra fora e outra incompleta |
| Obrigação com prazo, função e evidência | PARCIAL: workflow e checklist locais | Prazo legal somente com dispositivo; extrator LLM ainda não implementado |
| Norma nova altera obrigação existente | PARCIAL: diff e temporalidade; reabertura automática ausente | Prioridade alta: propor reavaliação com comparação e aceite, preservando a decisão antiga |
| Quem precisa saber e quando | PARCIAL: contas/funções, agenda e notificações | Lembrete pessoal não significa notificação jurídica entregue; sem envio externo automático |
| Demonstração, mercado e pitch | Documentação + pesquisa entregues | Ainda faltam entrevistas, mensuração e QA visual do fluxo novo |

## Prioridades revisadas

1. **Caixa de impacto da mudança:** mostrar o dispositivo alterado, a condição modificada e as unidades candidatas.
2. **Revisão de decisão anterior:** apontar que uma decisão usou versão antiga e sugerir revalidação, sem substituir automaticamente a decisão ou seu prazo.
3. **Transparência do filtro:** permitir examinar descartados e lacunas, além dos alertas relevantes. Medir omissões com gabarito, não apenas quantos alertas foram reduzidos.
4. **Projeto como contexto:** PDF/descrição → fatos propostos → confirmação → alimentação do enquadramento. A primeira versão entregue apenas recupera candidatos no corpus limitado; não extrai obrigação por IA.
5. **Assistente por conta:** explicar o que mudou, quem revisa por função, que evidência falta e como abrir a ação existente.

Essas prioridades correspondem ao tema do D02. Outras áreas do evento — cadastro de materiais, negociação de dívidas e redesenho de processos — não foram adotadas como novos escopos da LexIA. A arquitetura pode aproveitar técnicas de extração ou descoberta sem mudar de desafio.

## Proposta de demonstração em cinco minutos

- 0:00–0:40: dor concreta e persona; evidência pública e hipótese ainda a entrevistar.
- 0:40–1:20: uma mudança normativa curada e sua versão; explicar coleta e cobertura.
- 1:20–2:10: condição alterada e três ativos: candidato, exclusão e lacuna.
- 2:10–2:50: projeto sintético em PDF como entrada de contexto; aceitar atividade só após conferir trecho.
- 2:50–3:50: atribuir revisão, fundamentar decisão e registrar evidência; fonte e data visíveis.
- 3:50–4:25: mostrar diff e explicar limite atual de atualização de obrigação; não simular reabertura inexistente como real.
- 4:25–5:00: comprador, concorrentes, hipótese de receita, testes e próximo experimento.

Não usar como regra real os prazos fictícios do briefing. Não prometer evitar multas ou reduzir custos em percentuais sem ensaio. Não afirmar uso de IA generativa no fluxo de PDF implementado por regras. O ponto técnico ainda mais relevante para evoluir é extrair candidatos fundamentados e ligar mudanças novas às decisões já existentes.
