# Checklist completo — LexIA

> Gerado de `data/checklist.json` por `scripts/gerar_checklist.py`. A mesma lista aparece na tela **Checklist & papel da IA**.

## Regra de ouro

**A IA propõe → regras versionadas verificam → humano competente decide → o sistema registra.**

| Ator | O que faz | O que nunca faz |
|---|---|---|
| ✦ **IA** | Classifica fontes; compara versões; extrai obrigações candidatas com trecho; sugere vínculos com ativos; redige em linguagem simples e técnica; se abstém sem base | Decidir conformidade; inventar prazo, multa ou sanção; inferir obrigação pelo nome da empresa; publicar tarefa |
| ⚙ **Regra** | Calcula vigência por dispositivo; testa condições/exceções; agente crítico; verifica cada citação da IA; bloqueia ingestão interna, protegida ou suspeita | Interpretar texto livre |
| ◉ **Humano** | Confirma/rejeita achados (jurídico, compliance, especialista); registra motivo e versão; anexa evidência; autoriza envios | — |
| ▣ **Sistema** | Gêmeo digital; trilha de auditoria com hash; grafo com proveniência; conectores e exportações | Enviar algo para fora sem aceite humano |

## Placar

- Feito: **59** · Simulado: **5** · Planejado: **11** (total 75)
- Por ator: IA 7 · Regra 33 · Humano 4 · Sistema 31

Legenda: `[x]` feito e testado · `[~]` funciona com dados/conectores simulados · `[ ]` planejado.

## 00. v4 — site e contas

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Site público: início, sobre (LGPD), entrar e cadastro | SISTEMA | #/inicio, #/sobre, #/entrar, #/cadastro | E2E: 01_inicio, 02_sobre |
| [x] | Duas contas separadas: cidadão e empresa, com experiências diferentes | SISTEMA | app/accounts.py · web/js/site.js | test_company_role_from_function_and_login_kind; E2E portal do cidadão |
| [x] | Senha com PBKDF2 (200 mil iterações), sessão em cookie HttpOnly, proteção de origem | REGRA | app/accounts.py · app/server.py | test_password_is_hashed; test_cross_origin_post_blocked |
| [x] | Validação de CNPJ por dígito verificador e consentimento LGPD | REGRA | app/accounts.py | test_cnpj_validation; test_register_validations |
| [x] | Carteira da empresa / acompanhamento do cidadão alimentam indicadores e avisos | SISTEMA | /api/watchlist | E2E: carteira 9 → 10 |

## 00. v4 — monitor

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Monitor de fontes oficiais com robots.txt, intervalo e alerta no sino | SISTEMA | app/monitor.py · Governança › Monitor | test_robots_respected; test_change_detection_ignores_scripts_and_notifies |
| [x] | SIGBM atualizado automaticamente quando a ANM publica nova versão | SISTEMA | app/monitor.py | test_sigbm_new_version_triggers_sync |
| [x] | DOU (site) e LexML declarados como bloqueados, sem contornar proteção | REGRA | BLOCKED_CHANNELS | test_monitor_endpoint_lists_blocked_channels |
| [ ] | Diário Oficial via INLABS | SISTEMA | Conector a criar | Exige credencial da Imprensa Nacional |

## 00. v4 — visual

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Identidade visual da referência: navy + azul, 4 indicadores, mapa por UF, fila, marcos e insight | SISTEMA | Visão Executiva | E2E: 04_exec |
| [x] | Globo sem corte e com ficha ao clicar | SISTEMA | Atlas › Globo | E2E: globo ocupa o quadro; ficha visível |
| [x] | Insight rotulado como “Regras” quando a IA está desligada | REGRA | /api/insight | test_executive_insight_and_portfolio |

## 0. v3 — dados oficiais

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Conector real ANM SIGBM com snapshot imutável (SHA-256, horário, Last-Modified) | SISTEMA | Fontes & Governança › Conectores · app/connectors/sigbm.py | test_snapshot_roundtrip_offline / snapshot real 902 aceitas |
| [x] | Detecção de encoding/delimitador e divergência com o dicionário oficial | REGRA | app/connectors/sigbm.py | test_encoding_and_delimiter_detection |
| [x] | Schema drift interrompe a importação | REGRA | SchemaDriftError | test_schema_drift_is_detected |
| [x] | Coordenadas inválidas rejeitadas com motivo (sem correção por adivinhação) | REGRA | Relatório de qualidade | test_counts_rejections_and_duplicates |
| [x] | CPF de pessoa física ocultado | REGRA | app/connectors/sigbm.py | test_personal_data_hidden |
| [x] | Registro de organizações por CNPJ; correspondência por nome nunca vira vínculo | REGRA | app/entities.py · Atlas | test_textual_match_is_not_a_link |
| [x] | Camadas DADO OFICIAL e CENÁRIO HIPOTÉTICO separadas (forma e rótulo) | SISTEMA | Atlas | E2E: ficha com rótulo de origem |

## 0. v3 — decisão

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Quatro eixos independentes: ciclo normativo, aplicabilidade, fluxo, prioridade | REGRA | app/assessment.py | test_axes_are_independent |
| [x] | Prioridade com fórmula e justificativa, sem usar CRI/DPA | REGRA | app/assessment.py | test_priority_does_not_use_cri |
| [x] | Atributos atuais não apresentados como históricos | REGRA | analyze_official_anm | test_current_attributes_not_presented_as_historical |
| [x] | Permissões por papel nas mutações; ator vem do token | SISTEMA | app/server.py · data/demo_users.json | test_rbac_on_mutations |
| [x] | Decision Pack imprimível | SISTEMA | /api/export/decision-pack | test_full_flow_and_decision_pack |
| [x] | Decision Lab com premissas mín/base/máx, memória e sensibilidade | REGRA | app/finance.py · Decisão & Execução | test_finance_reproducible |
| [x] | Diff por dispositivo (metadados e resumo curado) | REGRA | app/diff.py · Laboratório | test_diff_nr20 |
| [ ] | Extrator LLM de obrigações com JSON validado | IA | Etapa E | Não implementado nesta versão |

## 1. Fontes e curadoria

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Catálogo de 42 fontes com URL, nível T/C/I e data de verificação | SISTEMA | Tela Fontes · data/sources.json | Teste test_catalog_42 |
| [ ] | Classificar fonte por órgão, tipo, jurisdição e direito de uso | IA | Agente Curador | Comparar com rótulos humanos em amostra |
| [x] | Ingestão curada com SHA-256, data de coleta e status | SISTEMA | Tela Fontes › Ingestão · app/ingest.py | Testes de ingestão |
| [x] | Bloquear documento marcado INTERNA/CONFIDENCIAL | REGRA | app/ingest.py | test_ingest_blocks_internal |
| [x] | Quarentena para domínio não oficial ou URL redirecionada a outro emissor | REGRA | app/ingest.py | test_ingest_redirect_quarantine |
| [x] | Bloquear norma técnica protegida (ABNT/ISO) | REGRA | app/ingest.py | test_ingest_license_block |
| [x] | Detectar instruções dirigidas à IA dentro do documento (prompt injection) | REGRA | app/ingest.py + prompt do sistema | test_ingest_injection |
| [ ] | Vigilância automática do DOU e portais (sem scraping agressivo) | SISTEMA | Conector SRC-DOU | Respeitar robots/termos; log de coleta |

## 2. Versão e vigência

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Vigência por DISPOSITIVO (não por norma inteira) | REGRA | app/temporal.py · Máquina do tempo | Testes em 06/11/2026, 22/04/2027, 02/08/2027, 26/12/2029 |
| [x] | Estados: em consulta, vigente, histórica, futura, revogada, a conferir | REGRA | app/temporal.py | test_temporal_states |
| [ ] | Detectar mudança entre versões (diff por artigo/item/alínea) | IA | Agente Versionador | Casos com ato modificador conhecido |
| [x] | Data não conferida nunca vira 'vigente' (A_CONFERIR) | REGRA | app/temporal.py | test_temporal_states |

## 3. Extração de obrigações

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [~] | Extrair sujeito, ação, condição, exceção, prazo expresso e evidência | IA | Cadeia de decisão (extrações de referência curadas) | Fidelidade campo a campo vs. anotação humana |
| [x] | Prazo só quando expresso na fonte (senão null) | REGRA | app/engine.py · agente Crítico | test_nr20_case (legal_deadline None) |

## 4. Aplicabilidade

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Triagem determinística: REVIEW, INSUFFICIENT, OUT_OF_SCOPE, NO_LINK, FUTURE_REVIEW, MONITOR | REGRA | app/engine.py | Testes de motor (12 ativos × 4 cenários) |
| [ ] | Propor vínculo norma ↔ ativo a partir de atributos | IA | Agente Aplicabilidade | Nunca pelo nome da organização |
| [x] | Agente Crítico procura exclusões, fontes fracas, datas futuras e prazos inventados | REGRA | app/chain.py · Cadeia de decisão | Painel do Crítico em cada achado |
| [x] | Pedir somente os dados faltantes | REGRA | Achado INSUFFICIENT | test_missing_info |

## 5. Visual e geocontexto

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Centro de comando com KPIs, radar e próximos marcos | SISTEMA | Tela Centro de comando | Abrir a tela |
| [x] | Mapa operacional com camadas, filtros, zoom e data simulada | SISTEMA | Tela Mapa operacional | Selecionar ativos e mudar data |
| [x] | Globo 3D interativo (arrastar, girar, clicar ativo) | SISTEMA | Tela Globo 3D | Arrastar o globo; clicar em um ativo |
| [ ] | Geocercas e jurisdições reais | SISTEMA | Conector GIS | Somente dados licenciados e autorizados |

## 6. Simulação (What-if)

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Alterar atributos do ativo e ver o estado mudar | REGRA | Tela Simulador | Preencher dados de A-02 → muda de INSUFFICIENT |
| [x] | Máquina do tempo: carteira e dispositivos em qualquer data | REGRA | Tela Máquina do tempo | Arrastar para 2027/2029 |

## 7. RegulaGraph

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Grafo tipado fonte–documento–dispositivo–achado–ativo–revisão–evidência | SISTEMA | Tela RegulaGraph · /api/graph | Clicar nó abre proveniência |
| [x] | Toda aresta com source_id e review_status | SISTEMA | app/chain.py | test_graph_edges_have_provenance |

## 8. Revisão humana

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Fluxo DRAFT → REVIEW_PENDING → CONFIRMED/REJECTED → ACTION_TRACKING → CLOSED | HUMANO | Tela Revisão humana · app/store.py | Testes de workflow |
| [x] | Toda transição registra quem, papel, quando, motivo e versão da fonte | SISTEMA | app/store.py | test_transition_requires_reason |
| [x] | Somente jurídico/compliance/especialista confirma ou rejeita | REGRA | app/store.py | test_operacao_cannot_confirm |
| [ ] | Autenticação real / SSO e RBAC | SISTEMA | Conector IAM | Na demo o papel é declarado |

## 9. Evidência e auditoria

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Evidence Gap: evidências exigidas × registradas por achado | SISTEMA | Tela Evidências | Registrar evidência e ver lacuna fechar |
| [x] | Trilha de auditoria encadeada por hash (detecção de adulteração) | SISTEMA | Tela Revisão › Auditoria · /api/audit/verify | test_audit_chain_detects_tampering |
| [x] | Encerrar achado exige evidência registrada | REGRA | app/store.py | test_close_requires_evidence |

## 10. Assistente de IA

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Recuperação local (BM25) sobre dispositivos e fontes curadas | SISTEMA | app/ai.py | test_retrieval_nr20 |
| [~] | Geração com Claude (opcional, por variável de ambiente) com saída JSON estruturada | IA | app/ai.py · ANTHROPIC_API_KEY | Desligado por padrão; ligar e repetir perguntas |
| [x] | Verificador: citação precisa existir literalmente no trecho recuperado | REGRA | app/ai.py › verify | test_verifier_rejects_fake_quote |
| [x] | Abstenção fora da base / pedido de multa | REGRA | Assistente | test_non_observed_question_abstains |
| [~] | Dois perfis (simples/técnico) com os mesmos fatos e fontes (pré-redigidos no modo controlado; gerados pela IA quando conectada) | IA | Assistente | test_two_profiles_preserve_sources |

## 11. Integrações

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Catálogo de conectores com contrato de dados e status honesto | SISTEMA | Tela Integrações · data/connectors.json | Status SIMULADO/PLANEJADO visível |
| [~] | Envio a GRC/tarefas só após CONFIRMED (caixa de saída local) | REGRA | Tela Integrações · /api/integrations/dispatch | test_dispatch_requires_confirmed |
| [x] | Exportação CSV/JSON de achados e auditoria | SISTEMA | /api/export/* | Baixar pela tela Integrações |
| [~] | Barramento de eventos (regulatory.change → triage → review → task) | SISTEMA | Tela Integrações › Fluxo | Eventos vêm da trilha de auditoria real |
| [ ] | Conexão real com ERP, GRC, GED, tarefas | SISTEMA | Conectores | Exige autorização, credenciais e contrato |

## 12. Segurança e ética

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [x] | Ativos 100% fictícios; nenhuma marca real como cliente | HUMANO | data/assets.json | Revisão de conteúdo |
| [x] | Nenhuma ação externa automática | REGRA | app/store.py › dispatch | Sem chamadas de rede no envio |
| [x] | Chave de IA só por variável de ambiente, nunca no código | SISTEMA | app/ai.py | grep por chaves |

## 13. Avaliação

| | Item | Ator | Onde | Como verificar |
|---|---|---|---|---|
| [ ] | 12 casos base do dossiê + 10 adversariais com numerador/denominador | HUMANO | Tarefa 09 | Não inventar métricas |
| [ ] | Medir tempo de triagem antes/depois com usuários reais | HUMANO | Pesquisa com profissionais | Sem ROI até medir |
