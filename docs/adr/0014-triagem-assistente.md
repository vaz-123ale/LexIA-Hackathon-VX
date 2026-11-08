# Triagem do assistente e avaliação de coerência

Decisão: compartilhar a triagem por regras entre a consulta normativa e o miniassistente. Emergência, recusa de julgamento, idioma e ajuda da plataforma antecedem geração e filtros. Município restringe o conjunto antes de filtrar; setor não oculta norma explicitamente solicitada.

Aceite: executar os 100 casos herdados com respostas completas e identificação de modo. Casos positivos cobrem normas catalogadas e municípios; negativos cobrem assuntos estranhos, normas desconhecidas e injeção; falta de dados exige abstenção; conflito entre perfil e assunto preserva o assunto. Erros HTTP e falhas do provedor não contam como respostas corretas. Resultado zero de filtro é válido. Testes controlados não medem a qualidade do LLM.

Limite: citações literais validam a existência do trecho, não provam que toda inferência é correta. A avaliação não certifica conformidade nem ausência de alucinações para perguntas arbitrárias.

Se o LLM se abstiver em uma pergunta de síntese já coberta pelo dossiê, o sistema pode mostrar a síntese controlada do tema, identificada como `controlado`, com o motivo e a verificação original na trilha. Isso não transforma uma recusa do modelo em resposta generativa aprovada. Perguntas específicas sem cobertura continuam sem resposta normativa.

Os telefones de emergência foram conferidos em 08/11/2026: https://prefeitura.sp.gov.br/web/defesa_civil/w/noticias/184619 e https://www.bombeiros.pr.gov.br/servicos/Defesa-Civil/Emergencia/Acionar-Corpo-de-Bombeiros-193-0A30a4rk .
