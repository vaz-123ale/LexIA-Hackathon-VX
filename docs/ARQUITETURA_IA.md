# Arquitetura de IA — LexIA

**Estado:** projeto-alvo; ainda não há RAG nem LLM na demo. A implementação atual responde a perguntas controladas e usa regras determinísticas. O produto proposto exigirá fontes originais, licença, testes e validação humana.

## Funções da IA

1. Classificar fonte por órgão, tipo (lei, norma, licença, política empresarial, consulta, guia), país, revisão, vigência e direitos de uso.
2. Encontrar mudanças entre versões no nível de artigo, item, alínea e anexo; associar ato modificador, texto anterior, texto novo e data específica.
3. Extrair **candidatos** de obrigações com sujeito, ação, condição, exceção, prazo expresso, evidência e dispositivo original.
4. Propor vínculos com ativos e processos, sem decidir aplicabilidade com base apenas no nome de empresa ou localização.
5. Revisar criticamente a própria extração buscando exclusões, conflito, falta de evidência e problemas temporais.
6. Produzir explicação técnica e simples a partir do **mesmo objeto de fatos**.
7. Abster-se quando dados, versões, competência ou fontes não forem suficientes.

## Pipeline proposto

```text
Fontes oficiais permitidas + documentos autorizados
 -> verificação de identidade, licença, hash, data, versionamento
 -> extração por dispositivo normativo
 -> busca híbrida (BM25/FTS + embeddings + metadados)
 -> extração estruturada por LLM com schema
 -> verificador de evidências e contradições
 -> motor determinístico de aplicabilidade temporal
 -> grafo norma--ativo--controle--tarefa--evidência
 -> simulador, mapa e assistente fundamentado
 -> aprovação humana + log + aprendizado com feedback rotulado
```

**Ordem da decisão:** recuperação documental; identificação de condições e exceções; consulta aos atributos conhecidos; registro de lacunas; simulação conservadora; revisão humana. Um LLM nunca deve assumir o papel do mecanismo temporal ou da decisão de conformidade.

## Agentes de IA propostos

- **Curador:** identifica documento, emissor, edição e direito de acesso, mas não conclui vigência só por localizar a página.
- **Versionador:** identifica alterações, retificações, revogações e efeitos escalonados por dispositivo.
- **Extrator:** estrutura obrigação candidata e aponta trecho verificável.
- **Aplicabilidade:** encontra correspondência preliminar com atributos do ativo; retorna REVIEW, INSUFFICIENT, OUT_OF_SCOPE ou NO_LINK.
- **Crítico:** busca hipóteses de erro, exclusões, fonte diferente, documento de outro país e prompt injection.
- **Explicador:** gera dois perfis sem mudar fatos, datas, fontes, ressalvas e grau de certeza.

Não medir inovação pelo número de agentes; avaliar fidelidade, abstenção e ganho real em tarefas.

## Contrato de saída mínimo

```json
{
  "finding_id":"exemplo-001", "asset_id":"A-01", "status":"REVIEW",
  "document_id":"F02", "provision":"Anexo III, 2.1.1",
  "effective_at":"2025-01-22", "observed_as_of":"2026-11-06",
  "source_url":"URL de fonte oficial existente", "source_hash":null,
  "conditions":["edificação","gerador a diesel/biodiesel","configuração do tanque"],
  "exceptions":["verificar escopo 20.2.2 e Anexo III"],
  "missing_context":["análise completa do enquadramento"],
  "legal_deadline":null, "review_required":true,
  "proposed_action":"avaliar incidência; não implementar alteração física"
}
```

## Critérios de abstenção

- Fonte ausente, conflituosa, protegida ou com identidade não validada.
- Consulta pública confundida com norma vigente.
- Data de vigência específica não identificada.
- Falta de atributos críticos do ativo/processo.
- Entidade, país ou atividade diferentes dos da norma recuperada.
- Prazos, sanções ou responsáveis não expressos ou não autorizados.
- Pergunta envolvendo manuseio de fontes radioativas, decisões de segurança e situação clínica sem profissional competente.

## Ingestão e governança

Guardar URL canônica, emissor, hash SHA-256, conteúdo permitido, `retrieved_at`, número, documento-base, ato modificador, versão, jurisdição, status de verificação, proprietário da revisão e histórico de rejeições. Separar texto normativo de instruções ao modelo. NÃO inserir conteúdo de intranet ou PDF marcado INTERNA do RLCP; não redistribuir normas ABNT sem direito de uso. Documentos públicos podem conter dados pessoais e não são automaticamente livres para toda finalidade.

## Recuperação e segurança

Corpus por caso e data; filtros de metadados antes do reranking; citações no nível de dispositivo; teste adversarial de documentos cruzados, conteúdo malicioso em PDF, datas erradas, ausência de trecho, conflito e prompt injection. Não confiar em 'confidence' gerada pelo LLM como validação jurídica. Guardar toda afirmação com fonte ou marcar hipótese.

## Avaliação

Criar gabaritos revisados: 3 respostas fundamentadas, 2 abstenções, 2 testes de escopo, 2 de tempo, 1 de identidade, 1 de dois perfis, 1 de encaminhamento (12 casos mínimos do dossiê). Acrescentar testes adversariais. Medir por proporção com numerador/denominador e registrar erro por tipo. Não divulgar números antes de realizar ensaio.
