# ADR-005 — Plataforma multissetorial por configuração, minas/radiológico, denúncia para a empresa e avaliação da IA

Data: 07/11/2026 · Estado: aceito (demo)

## Contexto
A LexIA (antiga Torre Regulatória 360°) estava concentrada em barragens de mineração. A proposta de melhorias pede um núcleo escalável para mineração, energia, saneamento e indústria; mais cobertura de mineração (tipo de lavra, substância, locais radioativos/CNEN); denúncia endereçada à empresa responsável; avaliação contínua da IA; e custo medido por cliente e funcionalidade.

## Decisões
1. **Setor = configuração, não código.** `data/setores.json` define, por setor, os tipos de ativo (símbolo, aba, documentos com base legal, indicadores com limites e sentido), reguladores, abas e o roteamento padrão por ocorrência → papéis. Cada empresa (`data/empresas_demo.json`, fictícias) liga ou desliga abas e mapeia papel → função de usuário. O motor `app/ativos.py` (regra `ativos-v1`) é único e determinístico.
2. **Roteamento: a informação certa para a pessoa certa.** Os alertas carregam `recipients` (papéis). As notificações usam audiências `org:<cnpj8>` e `orgfunc:<cnpj8>:<função>`: outra empresa e o cidadão não recebem.
3. **Minas (SIGMINE/ANM).** Conector `app/connectors/sigmine.py` coleta só as fases de lavra (concessão e lavra garimpeira) do serviço público ArcGIS da ANM, guarda o centro aproximado da área (não o polígono) e o nome do titular só quando é pessoa jurídica. A verificação TLS nunca é desligada (curl do sistema completa a cadeia). Classificação por regra (`sigmine-v1`); urânio/tório → nuclear; terras raras, monazita, zircônio, ilmenita, nióbio/columbita, fosfato etc. → radioatividade natural associada (CNEN NN 4.01). É **sinal para avaliação**, não conclusão.
4. **Denúncia para a empresa.** Depois que a pessoa confirma, a denúncia vai para a caixa da empresa responsável (`denuncia_destino`) e um e-mail com texto, normas do catálogo e hash é enfileirado para compliance/jurídico (`email_outbox`, SES opcional). Anônima para a empresa por padrão. O órgão oficial continua recebendo pelo envio da própria pessoa.
5. **Avaliação da IA (eval-v1).** `data/eval/ia_eval.json` + `app/ia_eval.py`: 7 categorias (relevância, normas corretas, versão vigente, roteamento, resposta com fonte ou abstenção, sem alucinação, isolamento). Gabarito anotado pela equipe; **não** validado por especialista externo. Roda em teste unitário e em `/api/ai/eval`, sem custo de IA. Na primeira execução encontrou um erro real: a regra radiológica casava “tório” dentro de “escritório/relatório/território”. Corrigido com limite de palavra e coberto por teste.
6. **Custo.** `meter_request` marca cada requisição com cliente e funcionalidade; regras, cache, chamadas pagas e tokens estimados são somados por cliente e por funcionalidade. Valor em dinheiro só com preço configurado (`TORRE_LLM_USD_POR_MTOK`): não inventamos custo. Upload idêntico (mesmo SHA-256, mesmo cliente) é reaproveitado.
7. **Bedrock por empresa (desenho, não executado).** Uma Knowledge Base com metadados `customer_id`, `setor`, `ativo_id`, `vigencia_inicio/fim`, `fonte_id`; toda consulta filtra por `customer_id` do usuário autenticado (nunca pelo texto da pergunta); a resposta mostra trechos e fontes; sem trecho suficiente, a LexIA se abstém. Modelo leve para filtros e resumos, padrão para perguntas e denúncias (`TASK_TIER`).

## Consequências
- Demo de dois+ cenários (mineração e energia/saneamento) só trocando a empresa selecionada.
- Discurso: plataforma de risco, conformidade e manutenção preventiva; mineração é o primeiro caso de uso.
- Não testado: envio real por SES, Knowledge Base Bedrock, sensores reais (as leituras são sintéticas).
