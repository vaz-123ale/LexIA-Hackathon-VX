# ADR 002 — acompanhamento por conta

Data: 06/11/2026. Decisão: calcular lembretes locais a partir da sessão, carteira, revisões, checklist e dispositivos. Não enviar o perfil ou os registros da conta ao modelo generativo. A conversa normativa continua separada em `/api/ask`. Sem nova persistência ou envio externo.

Aceite: saudação por nome, agenda com origem e ações de navegação; perguntas sobre minhas pendências, revisões, evidências e marcos respondidas com dados locais. Não confirmar, atribuir ou publicar tarefas automaticamente. Atualizar o resumo ao abrir o assistente.

Positivo: revisão da carteira pendente e evidência ausente geram lembretes. Negativo: ativo fora da carteira não aparece para conta comum; cidadão não recebe agenda empresarial. Ausência: carteira vazia informa falta de dados, sem afirmar ausência de obrigações. Conflito: função atribuída não significa responsabilidade pessoal; início de vigência não significa prazo pessoal. Contas demo podem ver os cenários sintéticos compartilhados, explicitamente rotulados. Esta mudança não implanta isolamento multiempresa.

Limites: conversa pessoal usa intenções controladas, não diálogo generativo livre. Sem lembretes por e-mail, push, memória de conversa ou criação automática de tarefas. Fontes e revisão normativa permanecem nos fluxos existentes.

Implementado: módulo `web/js/account_assistant.mjs`, aba Minha agenda e perguntas pessoais em `web/js/drawer.js`, acesso inicial à agenda em `web/main.js`, estilos locais e cache PWA atualizado. Nenhum dado normativo ou snapshot alterado. Corrigidos caracteres acentuados do painel.

Verificação: 100 testes Python e 7 testes Node passaram. Casos Node cobrem carteira, exclusão de registros alheios ao recorte, conta cidadã, demo, revisão encerrada, evidência existente, atribuição por função e distinção de intenções. Sintaxe JavaScript validada. Validação visual e navegação de ponta a ponta não executadas: conexão de navegador indisponível conforme inspeção anterior.

Próximas possibilidades, ainda não implementadas: resumo de retorno com mudanças desde a última visita; adiamento de lembretes sem alterar prazo legal; preferências de frequência e canal; preparação de rascunho de encaminhamento sujeito a aceite; memória de conversa consentida por conta; explicações de prioridade com evidências. Antes de uso multiempresa, implementar isolamento e autorização no servidor.
