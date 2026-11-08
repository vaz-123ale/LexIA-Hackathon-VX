# Especificação funcional — LexIA

**Objetivo:** converter evidências normativas curadas em triagem de aplicabilidade, simulação e tarefas candidatas, com revisão humana. **Não** é certificação jurídica, ambiental, operacional ou nuclear.

## Personas
- Jurídico/compliance: fonte, alcance, exceção, vigência, revisão e registro de decisão.
- Operação/engenharia: atributo do ativo, próximos passos, checklist e limite de competência.
- Compras/fornecedor: distinguir lei, condição contratual, política e orientação.
- Gestor: mapa, carteira, tendências e pendências; jamais KPI de risco inventado.
- Auditor: trilha imutável fonte→extração→decisão→evidência.

## Funcionalidades e prioridades

| ID | Capacidade | MVP | Evolução |
|---|---|---|---|
| F01 | Catálogo com URLs, níveis T/C/I, versões | Sim | Verificação automática |
| F02 | Dois perfis com fatos idênticos | Sim, respostas controladas | RAG com revisão |
| F03 | Mapa de ativos fictícios e camadas de triagem | Sim | Geocercas e jurisdições reais autorizadas |
| F04 | What-if Lab (NR-20 e ANM) | Sim, regras hardcoded | Motor de regras configurável |
| F05 | RegulaGraph de relações | Visual demonstrativo | Grafo persistente/versionado |
| F06 | Quadro de obrigações candidatas | Sim, textos de triagem | Workflow com tarefas revisadas |
| F07 | Evidence Gap AI | Conceito e lacunas visíveis | Extração documental e auditoria |
| F08 | Time Machine / vigência granular | Demonstração | Base completa por dispositivo |
| F09 | Assistente RAG auditável | Não | Implementar após corpus válido |
| F10 | Agentes especializados | Não | Implementar se testes indicarem ganho |
| F11 | Diretório humano com fonte e finalidade | Previsto | Cadastro institucional verificado |
| F12 | Globo 3D | Ilustração | Visualização geoespacial opcional |
| F13 | Integrações ERP/GRC/documentos | Não | Via autorização e autenticação |
| F14 | Alertas, relatórios e exportações | Não | Após validação do fluxo |

## Regra → ferramenta especializada
- Limite numérico → cálculo determinístico com unidade e comparação a valor observado, se norma e medição verificadas.
- Prazo expresso → timeline por dispositivo, evento e origem do prazo; nunca inventar período.
- Evidência documental → checklist, versão, validade e pendência, sem declarar conformidade.
- Alcance territorial → mapa com órgão e jurisdição; geocodificação confiável.
- Licença → etapas, condicionantes e documentos; sem aprovação automática.
- Treinamento → matriz de função × requisito × evidência autorizada.
- Produto regulado → ingrediente/atividade/mercado/registro e revisão.
- Alteração normativa → diff e propagação de candidatos ao RegulaGraph.

## Telas da demo que já existem
1. **Visão geral:** KPIs de catálogo e dados sintéticos, globo decorativo, mapa e radar de triagem.
2. **Mapa operacional:** geometria geral do Brasil e marcadores fictícios; clique mostra status e fontes.
3. **Simulador:** mudança NR-20 histórica e fases ANM futuras; múltiplos ativos.
4. **RegulaGraph:** grafo simplificado demonstrativo, não persistente.
5. **Fontes:** consulta local a 42 URLs com status e limites.
6. **Assistente:** temas NR-20, ANM, CNEN/ANSN com respostas fixas e abstenção fora da base.

## Casos de teste de produto
- A-01/NR-20: REVIEW; A-02/NR-20: INSUFFICIENT; A-03/NR-20: OUT_OF_SCOPE; A-04/NR-20: NO_LINK.
- B-01/ANM: FUTURE_REVIEW; demais ativos/ANM: OUT_OF_SCOPE no contexto escolhido.
- Mudança da NR-20 pela Portaria MTE 60/2025 é **histórica** quando demonstrada em nov/2026.
- Fases ANM: 22/04/2027 (arts. 76–77), 02/08/2027 (regra geral), 26/12/2029 (§1º art. 7º) — conforme dossiê F40, sujeito a conferir para uso real.
- A pergunta sobre multa automática sem base gera ABSTAIN, não número ou sanção.
- Dois perfis alteram a linguagem, preservam referências e limitações.

## Acessibilidade
Navegação por teclado, contraste suficiente, texto alternativo, foco visível, estados em texto e não apenas por cor, layout responsivo; testar especialmente marcadores do SVG e formulários.

## Segurança de apresentação
Todos os ativos são **fictícios**, coordenadas ilustrativas e nomes de empresas apenas para pesquisa setorial; nunca como alegação de acesso, cliente, parceria ou instalações reais. Resultados de performance e ROI são hipóteses até serem medidos.
