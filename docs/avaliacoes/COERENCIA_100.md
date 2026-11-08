# Avaliação de coerência — 08/11/2026

Foram retomados os 100 casos deixados em `scripts/teste_coerencia_ia.py`. O arquivo estava sem commit e não havia relatório final encontrado. O avaliador foi corrigido: falha HTTP não é abstenção; filtro com resultado zero pode estar correto; perguntas vagas sobre uma “nova lei” pedem identificação do ato. O relatório guarda respostas completas, fontes, verificação e trilha.

| Execução | Critérios atendidos | Evidência |
|---|---:|---|
| Render antes das mudanças, LLM desligado | 41/100 | [JSON](coerencia-render-antes.json) |
| Local corrigido, modo controlado | 100/100 | [JSON](coerencia-controlado.json) |
| Local corrigido, Gemini 2.5 Flash ativo e política qualidade | 100/100 | [JSON](coerencia-gemini.json) |

Na execução com Gemini, 18 respostas foram geradas com citações aceitas; 13 foram sínteses controladas (8 após erro do provedor — timeout/HTTP — e 5 após abstenção). Os outros casos foram 40 abstenções, 14 consultas ao cadastro, 8 orientações de emergência, 6 ajudas da plataforma e 1 pedido de contexto. Não foram 100 respostas generativas: as regras devem resolver emergências, filtros, recusas e falta de base. O status `AI_VERIFIED` significa que as citações passaram nas verificações implementadas; não comprova todas as inferências da resposta.

Os casos incluem português técnico, coloquial, abreviações, erros de digitação, inglês, espanhol e francês. A interface responde em português e solicita reformulação quando não cobre o idioma. A bateria mede critérios automatizados de intenção, conteúdo esperado e proteção; **não é taxa de acurácia jurídica, avaliação independente nem garantia de ausência de alucinação**. A cobertura atual de outros idiomas é limitada.

Correções: prioridade para emergência e recusas; município antes dos filtros; norma desconhecida não vira resposta sobre outra norma do mesmo órgão; aliases para recuperação; EIR separado da transição ANM; ambos os perfis preservam as datas ANM; rejeição de citação inválida bloqueia a proposta inteira; número ausente na evidência bloqueia a resposta; abstenção não exibe texto não validado do modelo; falhas e fallback aparecem na trilha. O setor do perfil não impede consulta explícita a outro setor.

## Reprodução

```powershell
python -m unittest discover -s tests -v
python -m app.server --port 8765
python scripts/teste_coerencia_ia.py http://127.0.0.1:8765 var/coerencia.json
```

Para uma execução real, configure as variáveis do `.env.example` no ambiente. `TORRE_LLM_POLICY=qualidade` faz o caminho normativo tentar o LLM antes do fallback. Sem chave, o relatório é de modo controlado. Nunca publicar `.env` no Git.

## Implantação e limites

A chave local Gemini foi validada em chamadas reais. O `.env` local recebeu provedor, modelo e política validados e permanece ignorado pelo Git. Na verificação inicial, o Render respondia HTTP 200 e informava LLM desligado. A configuração de segredos no Render depende de acesso ao serviço; publicar código no GitHub não transfere variáveis locais ou segredos do GitHub automaticamente.

No serviço Render, usar **Environment → Add from .env**, importar o arquivo local e escolher **Save, rebuild, and deploy** ([documentação](https://render.com/docs/configure-environment-variables)). Conferir `/api/health`: `assistant_policy=triagem-v1`, revisão esperada, `llm.enabled=true`, provedor Gemini. Depois executar novamente a bateria contra o endereço público.

Não foram feitos novos testes visuais de navegador, auditoria jurídica das fontes, teste de carga, cobertura universal de idiomas nem garantia de disponibilidade do provedor. A revisão humana permanece obrigatória. Os testes usam perguntas sintéticas; não houve coleta de dados privados. Dados e dispositivos normativos não foram alterados.
