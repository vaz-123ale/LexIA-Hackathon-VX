# Modelo de dados e APIs

## Entidades previstas

| Entidade | Chaves mínimas |
|---|---|
| Organization | id, category, legal_entity, jurisdiction; nunca presumir incidência pelo nome |
| Site / Asset | id, synthetic, activity, place, facility_kind, facts, owner_role |
| Document | id, issuer, legal_nature, number, title, canonical_url, license, hash, collected_at, verification_level |
| DocumentVersion | id, document_id, published_at, effective intervals, superseded_by, status |
| Provision | id, document_version, article/item/annex, excerpt_pointer, scope, exception, reviewer_status |
| ObligationCandidate | id, provision_id, subject, condition, action, deadline_source, evidence_expected, status |
| ApplicabilityFinding | id, asset_id, provision_id, assumptions, missing, exclusions, evidence_refs, review_status |
| GraphEdge | id, from, to, relation_type, provenance, approved_by |
| ReviewDecision | id, finding_id, decision, reviewer_role, timestamp, rationale, source_version |
| Task | id, finding_id, owner_role, planned_date, legal_deadline nullable, state |
| Evidence | id, task_id, kind, document_version, authorization, hash, storage_uri, verified_by |
| RegulatoryEvent | id, base_act, modifier_act, detected_at, affected_provisions, effective_phases |
| InstitutionalContact | id, organization, topic, public_url, purpose, checked_at, permitted_scope |

## Estados recomendados

`DOCUMENT_REVIEW_PENDING → CURATED → ACTIVE_FOR_DEMO` ou `REJECTED`.
`DETECTED → CANDIDATE_IMPACT → REVIEW_PENDING → CONFIRMED | DISCARDED → ACTION_TRACKING`.
`ABSTAIN`, `INSUFFICIENT`, `OUT_OF_SCOPE`, `NO_LINK` são resultados de triagem, não sanções.

## API atual (funciona no protótipo)

| Método | Rota | Função |
|---|---|---|
| GET | `/api/health` | estado do servidor e modo sem LLM |
| GET | `/api/assets` | 5 ativos sintéticos |
| GET | `/api/sources` | catálogo de 42 fontes |
| GET | `/api/scenarios` | cenários NR-20 e ANM |
| GET | `/api/graph` | grafo demonstrativo |
| POST | `/api/analyze` | `{ "asset_id":"A-01", "scenario_id":"nr20" }` |
| POST | `/api/ask` | `{ "question":"O que mudou na NR-20?", "profile":"tecnico" }` |

O `POST /api/ask` usa respostas fixas de demonstração; **não é RAG, não consulta a web em tempo real e não deve ser promovido como IA integrada**.

## API alvo (não implementada)

`POST /v1/documents/ingest` (ingestão autorizada e versionada); `GET /v1/provisions/{id}`; `POST /v1/events/diff`; `POST /v1/applicability/check` (com evidência); `POST /v1/queries` (RAG fundamentado); `POST /v1/reviews` (aprovação humana); `GET /v1/assets?geo=`; `GET /v1/graph/subgraph`; `POST /v1/evidence/verify`; `GET /v1/audit/export`.

## Dados e regras

`data/sources.json`: F01–F42, verificação T/C/I, URLs originais do PDF. `data/assets.json`: A-01…B-01, atributos fictícios. `data/scenarios.json`: descrição de eventos. `app/engine.py`: regras de triagem auditáveis com prioridade a escopo e insuficiência; `app/server.py`: HTTP local sem dependências.

**Observação:** o documento e os links foram auditados no escopo restrito do dossiê em 05/11/2026; o protótipo não possui verificador automático de atualização, hash de captura ou autorização de indexação do conteúdo de cada fonte.
