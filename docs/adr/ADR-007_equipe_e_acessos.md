# ADR-007 — Equipe e acessos por frente e por módulo

**Data:** 08/11/2026 · **Situação:** aceita · **Regras:** `acessos-v1`, `equipe-import-v1`, `relatorio-empresa-v1`

## Contexto
A gestão da empresa precisa dar acesso a funcionários sem depender da equipe LexIA. Uma organização pode ter várias frentes
(mineradora, energia, saneamento, nuclear), e quem trabalha numa frente não deve ver as outras. O acesso tem de poder ser
retirado a qualquer momento.

## Decisão
- **Frente:** quem entra por convite fica preso à empresa (frente) em que foi cadastrado (`users.empresa_id`). O servidor só
  devolve essa empresa (`allowed_companies`).
- **Módulos:** a gestão marca num checklist o que a pessoa acessa: Visão Executiva, Operação & Ativos, Alertas e mudanças
  normativas, Norma → obrigação, Denúncias recebidas, Documentos, Central de IA e Relatório da empresa (`users.modulos`).
  O acesso inicial vem da função e pode ser ajustado.
- **Bloqueio de verdade:** além de sumir do menu, a API do módulo desmarcado responde 403 (`API_MODULO` em `server.py`).
- **Revogar:** suspende a pessoa e apaga as sessões na hora; devolver o acesso reativa.
- **Cadastro em lote:** CSV, Excel, PDF com texto ou lista colada. A leitura é por regra (um e-mail por linha; o resto vira
  nome e cargo), sem IA. A gestão vê a prévia e confirma antes de qualquer convite.
- **Sem AWS para isso:** as regras ficam no próprio servidor. Na implantação, o envio do convite usa o Amazon SES, que já
  está previsto. Na demonstração o e-mail não sai: o link aparece para ser copiado.
- **Relatório da empresa:** saiu do site público. Cada frente gera o próprio relatório dentro da conta (operação, alertas com
  base legal, obrigações confirmadas, denúncias e dados públicos encontrados pelo CNPJ) e salva em PDF pelo navegador.

## Consequências
- Contas antigas e de demonstração (`modulos` nulo) mantêm o acesso completo do papel. Assim os testes e a demonstração
  continuam funcionando.
- Toda mudança de acesso fica na trilha de auditoria (`equipe.convite`, `equipe.acesso`, `equipe.alteracao`).
- Não testado: envio real de e-mail (SES) e PDF escaneado sem texto. Para PDF sem texto, a tela pede CSV ou Excel.
