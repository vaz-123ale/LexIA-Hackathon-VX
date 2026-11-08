# ADR 003 — PDF de projeto para normas candidatas

Data: 06/11/2026. Usar análise local efêmera e duas etapas: extrair trechos e sugerir temas; usuário confirma escopo; recuperar exclusivamente dispositivos do corpus curado. Nome empresarial é rótulo, nunca critério de incidência. Sem gravação do PDF, inclusão de norma no corpus, chamada LLM ou criação automática de revisão.

Aceite: conta empresarial autenticada, autorização explícita do documento, PDF textual até 1 MB/40 páginas ou descrição até 60 mil caracteres; SHA-256; trechos por página; temas candidatos e confirmação humana; cada dispositivo com URL original, versão, jurisdição, vigência na data-base, condições, exceções e lacunas. Bloquear marcação interna, injeção conhecida, PDF inválido/cifrado e tamanho excedido. Extração em subprocesso com timeout. PDF digitalizado pede texto/OCR, sem inventar conteúdo. Extração não equivale a compreender desenhos, tabelas ou determinar aplicabilidade.

Casos positivos: gerador/tanque e escopo NR-20 confirmado recuperam dispositivos curados. Negativos: nome de empresa sem atividade não gera norma; cidadão e anônimo não processam documentos. Falta de dados: município/UF/atributos ausentes ficam explícitos; cobertura fora das quatro famílias gera abstenção. Conflito: menção negada é apenas menção, não fato; seleção humana explícita é necessária; nenhum resultado declara conformidade. Consulta pública não vira obrigação.

Dependência opcional: pypdf para PDF. Descrição textual funciona sem ela. Não ampliar o corpus com os resultados de pesquisa deste estudo sem curadoria versionada. Não afirmar acesso integral/licença a todas as normas. Textos ABNT/ISO não são baixados ou redistribuídos.

Verificação: 113 testes Python passaram (100 anteriores + 13 novos), incluindo extração textual de PDF por página, autenticação, ausência de mutação e casos negativos. Os 7 testes Node da agenda passaram. Sintaxe JavaScript conferida. O fluxo visual no navegador não foi validado. A implementação é triagem por regras; a evolução de extração por LLM está pendente.
