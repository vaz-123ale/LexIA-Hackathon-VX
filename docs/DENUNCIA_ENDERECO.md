# Endereço informado na denúncia

Aceite: nos fluxos público/anônimo e após login, permitir informar endereço do ocorrido ou ponto de referência sem GPS, conservar o texto ao mudar de etapa e incluí-lo no relato e no resumo revisável. Campo opcional de até 300 caracteres; entrada vazia não avança pelo botão específico. O mapa e a estrutura escolhida não são inferidos pelo endereço. Em conflito com uma estrutura selecionada, ambos são mostrados para revisão humana. Sem endereço, os fluxos existentes continuam disponíveis.

O endereço digitado faz parte da denúncia persistida; a localização do GPS continua sendo usada apenas na busca. Não há geocodificação ou envio novo para serviços externos. O texto é escapado na interface. Datas contidas no endereço não são usadas como data do ocorrido. Não houve alteração de schema, fontes ou normas. O cache da interface recebeu nova versão.

Validação: suíte Python e teste Node dos dois formulários, conservação e envio do campo. Não foi realizada verificação visual no navegador.
