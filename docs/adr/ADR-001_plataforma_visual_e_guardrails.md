# ADR-001 — Plataforma visual completa sem dependências, com IA opcional verificada

**Data:** 06/11/2026 · **Status:** aceito

## Contexto
A demo inicial tinha 6 telas e respostas fixas. O objetivo do hackathon pede um sistema com cara de produto técnico: mapa, globo 3D, integrações e um papel claro da IA, sem violar a regra nº 1 do AGENTS.md (a IA propõe, regras verificam, humano confirma).

## Decisão
1. **Sem frameworks novos.** Backend continua em Python padrão (`http.server`, `sqlite3`); frontend em ES modules puros. Abre com `python -m app.server`, sem `npm install`.
2. **Camadas separadas:** `engine.py` (regras), `temporal.py` (vigência por dispositivo), `chain.py` (cadeia explicável + grafo), `ai.py` (recuperação + IA opcional + verificador), `ingest.py` (guardrails de ingestão), `store.py` (revisão humana, evidências, caixa de saída, auditoria com hash).
3. **IA opcional:** só liga com o pacote `anthropic` instalado e `ANTHROPIC_API_KEY` definida. O modelo recebe apenas os trechos recuperados e devolve JSON com citações; um verificador determinístico descarta citações que não existam literalmente no trecho. Sem citação válida, a resposta vira ABSTAIN. Modelo padrão: `claude-opus-5-5` (ajustável por `TORRE_LLM_MODEL`), com fallback do servidor ligado para recusas.
4. **Integrações honestas:** conectores aparecem com status SIMULADO/PLANEJADO. O envio de achados vai para uma caixa de saída local e o servidor recusa enviar qualquer achado que não esteja CONFIRMADO por um humano com papel de decisão.
5. **Globo 3D em canvas** com Natural Earth 1:110m (domínio público). Não usa tiles remotos.

## Consequências
- Funciona offline e roda em qualquer máquina com Python 3.10+.
- O banco `var/torre.db` é local e descartável (botão "Restaurar demo").
- Não há autenticação: o papel do revisor é declarado e registrado na trilha. SSO/RBAC continuam planejados.
- As etapas de IA da cadeia (Curador, Versionador, Extrator) mostram extrações de referência curadas e são rotuladas assim; não são saídas de um modelo.

## Critérios de aceite (todos cobertos em `tests/test_platform.py`)
- Positivo: A-01/NR-20 → REVIEW; B-01/ANM em 22/04/2027 → REVIEW só com arts. 76–77.
- Negativo: B-03 (pilha, não barragem) → OUT_OF_SCOPE; operação não confirma achado.
- Falta de dados: A-02 → INSUFFICIENT; simulador com dados preenchidos → REVIEW.
- Conflito/adversarial: citação falsa da IA → ABSTAIN; URL redirecionada → QUARENTENA; texto com "ignore as instruções" → QUARENTENA; registro de auditoria adulterado → cadeia quebrada.
