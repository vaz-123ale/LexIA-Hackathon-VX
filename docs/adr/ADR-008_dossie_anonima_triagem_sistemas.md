# ADR-008 — Dossiê da denúncia, denúncia anônima, triagem e impacto em sistemas

**Data:** 08/11/2026 · **Situação:** aceita · **Regras:** `dossie-v1`, `triagem-v1`, `sistemas-v1`

## Contexto
- O cidadão conta o caso como uma história. A empresa precisa receber um relato formal, saber quais normas podem estar sendo
  descumpridas, o que isso pode custar e por onde começar a resolver.
- Nem todo cidadão quer criar conta.
- Quem recebe um item fora da sua área (por exemplo, o gestor recebe algo do jurídico) precisa repassar sem perder o rastro.
- Em entrevista, um profissional de compliance apontou o próximo passo: mapear os sistemas afetados por uma norma e as alterações
  de código necessárias, num portfólio de mais de 2.000 aplicações.

## Decisão
- **Dossiê (`app/denuncia_dossie.py`):**
  - **Relato formal:** a IA redige por um canal separado (`llm_redacao`). As normas continuam escolhidas pelas regras.
  - **Verificador:** recusa número ou nome próprio que não esteja no relato. Sem IA, a redação é por regra e cita a fala original.
  - **Normas possivelmente descumpridas:** vêm com o trecho do relato que motivou cada uma.
  - **Implicações:** a faixa de multa é a do texto legal, com a fonte, marcada como "conferir" (nível C). Não é estimativa do valor do caso.
  - **Caminhos:** cada passo tem papel, prazo sugerido (não legal) e evidência. A empresa marca o que fez, e fica na trilha.
- **Denúncia anônima:**
  - Página pública, sem conta.
  - **Dono da denúncia:** é o hash do código de acompanhamento (`LX-XXXX-XXXX-XXXX`). Só a pessoa tem o código.
  - **Sem identificação:** não há anexo nem opção de se identificar. Há limite de 5 denúncias por hora por endereço.
- **Triagem (`app/triagem.py`):** o repasse vale para alerta, mudança normativa, denúncia e impacto em sistema. Notifica a função de destino, registra autor e nota e aparece no item.
- **Impacto em sistemas (`app/sistemas.py`):**
  - **Portfólio:** cada aplicação declara domínios regulatórios. O cruzamento é por domínio, em milissegundos, para 2.140 aplicações fictícias.
  - **Código:** nos repositórios conectados, detectores versionados (`data/requisitos_sistemas.json`) apontam arquivo, linha e diff. A IA pode sugerir outros pontos, e só é aceita se o trecho citado existir.
  - **Sem valor inventado:** quando o detector só pode pedir revisão (NR-20), ele não propõe valor.
  - **Aprovação:** uma pessoa aprova ou descarta com motivo, e a aprovação vira tarefa da equipe dona.

## Consequências
- O portfólio de sistemas e os repositórios são fictícios e sinalizados. As normas e datas vêm do catálogo da LexIA.
- Na implantação, a leitura de código passa por conectores Git (GitHub, GitLab ou Azure DevOps) com permissão de leitura do cliente.
- **Não testado:**
  - envio real de e-mail;
  - conectores Git reais;
  - abuso em larga escala da denúncia anônima (o limite por endereço é básico).
