# ADR 004 — sete fluxos de acompanhamento e projetos

06/11/2026. Manter Python/SQLite/JavaScript. Acrescentar armazenamento de resultados por conta e um núcleo local de acompanhamento, sem LLM ou novos serviços. PDFs continuam efêmeros; somente resultados/trechos autorizados são salvos após botão e consentimento explícitos. Dossiê exporta os fatos e decisões registrados, não cria parecer jurídico.

Aceite: (1) referências normativas estruturadas e propostas de reavaliação sem sobrescrever decisão anterior; (2) mostrar temas fora do recorte e motivos, sem declarar não incidência; (3) perguntas técnicas respondidas explicitamente, inclusive desconhecido e conflito; (4) comparar versões salvas do projeto, seus fatos e candidatos; (5) extrair condicionantes com trecho/página, campos desconhecidos e aceite humano; (6) resumo desde cursor de leitura por conta, atualizado somente por aceite; (7) dossiê HTML exportável com hash, fontes, fatos, lacunas e decisões.

Positivos: mudança de versão/fatos detectada, evidência ausente explícita, condicionante com trecho aceita por função competente. Negativos: proibir acesso a projetos de outra conta, conta cidadã/anônima e aceite por função sem competência. Falta: nenhuma referência antiga estruturada significa referência ausente, não norma desatualizada; ausência de data/responsável não gera prazo ou pessoa fictícios. Conflito: respostas opostas à menção ficam visíveis; candidato não é conclusão; reavaliação não modifica workflow legal automaticamente. Histórico e auditoria preservados. Resumo é de eventos da conta e revisões autorizadas; não há isolamento multiempresa dos fluxos legados da demo.

Sem documentos privados reais, envio externo, OCR, interpretação de plantas ou garantia de extração completa. O extrator de condicionantes é lexical, local e explicitamente rotulado. As novas funções não alegam leitura generativa, validade jurídica ou redução de multas.

## Implementação e artefatos

- `app/workbench.py`: tabelas aditivas `wb_*`, resultados por conta, vínculos com revisão, extração de condicionantes, histórico de referências/reavaliação, marcadores de leitura e dossiê HTML escapado.
- `app/project_screen.py`: perguntas, fatos explícitos, conflitos a conferir e justificativas dos temas fora do recorte. Não transforma resposta negativa em dispensa automática.
- `app/server.py`: rotas autenticadas `/api/workbench/*`, escopo de carteira, decisão por papel competente e referência ao confirmar uma revisão; auditoria/eventos legados filtram registros novos por proprietário.
- `web/js/project_screen.js`: entrevista, atualização após respostas, consentimento e salvamento de versão.
- `web/js/workbench.js` e `web/js/ws_decision.js`: área Projetos & acompanhamento, comparação, licenças, vínculos, propostas e exportação.
- `web/js/drawer.js`: resumo de retorno e navegação para acompanhamento; resposta de outra conta em requisição anterior não é reapresentada.
- `web/styles.css`, `web/main.js` e `web/sw.js`: componentes responsivos, fechamento do assistente ao navegar e exclusão de cache compartilhado para dados novos por conta.

Nenhuma norma, snapshot oficial ou regra jurídica foi alterada. O banco recebe tabelas novas e registros somente por ações autorizadas; PDFs integrais não são persistidos. Relatórios de projetos preservam a data-base e o resultado salvo, e identificam o estado das revisões consultadas na exportação. A decisão de revalidação preserva a referência anterior e exige novo aceite se o corpus mudar outra vez.

## Verificação e limites

Testes cobrem propriedade por conta, negação e desconhecido, referências ausentes, mudanças de versão/data-base, aceite/rejeição por papel, preservação do workflow, eventos novos durante a leitura, dossiê escapado, vínculos de escopo e vazamento por rotas legadas. Há testes Node para renderização vazia/preenchida e para não reutilizar cache de outra conta.

A tentativa de QA nativo foi interrompida pelo controle do computador por não conseguir determinar com confiança a URL atual do Chrome. Portanto, navegação visual, teclado e responsividade real continuam não verificados nesta entrega; testes de geração de HTML não substituem essa inspeção.

Resultado final: **139 testes Python e 12 testes Node aprovados**. Sintaxe dos módulos alterados validada. Smoke HTTP na instância local `http://localhost:8766`: projetos, resumo, reavaliações e exclusões retornaram corretamente; triagem retornou perguntas e recorte; módulo JS servido como `text/javascript`. O teste local não salvou projetos fictícios no banco em uso. Os ensaios com salvamento, condicionantes, comparação, vínculos e decisões usaram SQLite em memória.
