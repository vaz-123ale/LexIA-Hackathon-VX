# Testes e evidências — LexIA v3 (06/11/2026)

## Resultados reais
| Verificação | Resultado |
|---|---|
| `python -m unittest discover -s tests -v` | **99 testes, 99 passando, 0 ignorados** (44 da v2 + 36 da v3 + 19 da v4: contas, sessões, carteira, notificações, monitor) |
| `node --check` em `web/main.js` e `web/js/*.js` | sem erro |
| E2E no navegador (`scripts/e2e_cdp.mjs`, Chrome headless via DevTools) | **44 verificações OK, 0 falhas** na última execução: site público, login empresa e cidadão, cadastro (CNPJ inválido/válido), carteira, globo, decisão, dossiê, monitor, notificações e 390/768/1366 px sem rolagem lateral (`docs/screenshots/e2e_report.txt`) |
| Console do navegador | Nenhum erro de JavaScript. Um 400 registrado é proposital: o teste de cadastro com CNPJ inválido |
| Monitor real (servidor ligado) | Primeira rodada automática: 24 fontes oficiais verificadas, 0 erros, 48,6 s; linha de base registrada |

## Falhas reais encontradas e corrigidas durante a v3
1. **Leituras SQLite concorrentes** quebravam requisições (`IndexError`) quando o navegador carregava várias rotas ao mesmo tempo. Corrigido com trava em todo acesso ao banco e coberto por `test_concurrent_reads_do_not_break_sqlite`.
2. **Diff** classificava mudança de data como "adicionado". Corrigido para "vigência alterada".
3. **Aviso temporal** ("atributos atuais projetados") ficava escondido num bloco recolhido. Agora está sempre visível.
4. Teste HTTP antigo esperava 409 numa mutação sem login. Atualizado para enviar token, mantendo o que ele verifica; o caso sem login agora é coberto por testes de 401/403.

## Falhas reais encontradas e corrigidas na v4
1. **Conflito de nome de classe CSS** (`.lg` da legenda do mapa × `.btn.lg`) encolhia os botões da página inicial para 46 px. Encontrado por inspeção do estilo computado no navegador; a classe da legenda foi renomeada para `.lgi`.
2. **Reinício da demo não limpava carteiras**, o que deixava o E2E dependente do estado anterior. Agora a carteira faz parte do estado DEMO.
3. Seletor do E2E pegava o cartão errado do kanban; o servidor recusou corretamente a transição inválida (409), e o seletor foi corrigido.

## O que os testes cobrem (v3)
Importação real e com fixture; detecção de encoding e delimitador; schema drift; coordenadas DMS, minutos ≥ 60, hemisfério incoerente, fora do Brasil; deduplicação; CPF oculto; categorias não numéricas; snapshot offline; contagem exata na API; correspondência de entidade (textual × CNPJ × raiz); quatro eixos independentes; falta de dado nunca vira "não aplicável"; escopo × sem vínculo; decisão humana muda a aplicabilidade; consulta = proposta; prioridade ignora CRI/DPA; três datas da ANM; atributos atuais não viram históricos; abstenção; permissões (401, 403, token falso, ator do token); fluxo completo até o Decision Pack; Decision Lab reproduzível e validado; diff; concorrência.

## Fluxo E2E verificado no navegador
Visão Executiva → Atlas → busca "Vale" (vínculo a confirmar) → filtro por CNPJ (104 estruturas) → ficha em 4 seções → visitante sem botão de mutação → operação abre revisão → Laboratório (hoje e 02/08/2027) → operação encaminha → jurídico atribui função e confirma → evidência → Decision Pack → Decision Lab → assistente → app registrado (PWA) → Governança → 1366×768, 768×1024 e 390×844 sem rolagem horizontal.

## Mockado ou sintético
- 12 ativos e todos os cenários NR-20/ANP/ANSN (CENÁRIO HIPOTÉTICO).
- Conectores ERP, GRC, GED, tarefas e notificações: caixa de saída local.
- Autenticação: tokens de demonstração fixos.
- Etapas Curador, Versionador e Extrator da cadeia: extrações de referência curadas.

## Não implementado ou não testado
- Extrator de obrigações por LLM (Etapa E). O caminho de LLM do assistente foi testado só com geradores falsos (sem chave no ambiente).
- Conjunto de avaliação anotado por humano: nenhum número de acurácia é alegado.
- Modo claro, MapLibre/satélite, SSO real, Permit Radar com licenças reais, PostgreSQL/PostGIS.
- Auditoria formal de acessibilidade com leitor de tela.
- Execução em Python < 3.12 e em Linux (o código evita sintaxe exclusiva da 3.12, mas não foi executado nessas versões).
