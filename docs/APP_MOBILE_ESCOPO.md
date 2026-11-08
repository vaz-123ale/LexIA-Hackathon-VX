# LexIA no celular — inventário da plataforma e escopo do app

Data: 07/11/2026. Base: código atual (`web/main.js`, `app/server.py`). Tudo que está marcado como **existe** já funciona na plataforma web e tem API pronta; **novo** precisa ser construído.

---

## 1. Inventário: tudo o que a plataforma tem hoje

### 1.1 Site público (sem login)
| Tela | Rota | O que faz | APIs |
|---|---|---|---|
| Início | `#/inicio` | Proposta, números oficiais (902 barragens, 18.899 minas), globo, setores | `/api/health`, `/api/minas?limit=1` |
| Portal da Transparência | `#/transparencia` | Barragens/minas oficiais, casos crítica/alta, empresas (dados públicos), denúncias só em números | `/api/transparencia` |
| Sobre / privacidade | `#/sobre` | LGPD, limites, fontes | — |
| Entrar / Criar conta | `#/entrar`, `#/cadastro` | Empresa ou cidadão; contas demo | `/api/auth/login`, `/api/auth/register`, `/api/demo/users` |

### 1.2 Empresa (menu em 4 áreas; o **perfil da empresa** no topo troca módulos, dados e imagem)
**Visão Executiva** (`#/exec`): indicadores, operação da empresa do perfil, mudanças normativas, fila prioritária, marcos, insight. APIs: `/api/executive`, `/api/insight`, `/api/ativos`.

**Operação & Ativos** — abas mudam por setor:
| Aba | Rota | Setores | O que faz | APIs |
|---|---|---|---|---|
| Mapa de ativos | `#/ativos` | todos | Ativos da empresa no mapa (forma = tipo, cor = situação), documentos, sensores (z-score), alertas com destinatário; modo “empresa real · dados públicos” na mineração | `/api/ativos`, `/api/ativos/empresas`, `/api/empresa-publica`, `/api/transparencia` |
| Minas | `#/minas` | mineração | 18.899 títulos por tipo/substância, sinal radiológico (CNEN) | `/api/minas` |
| Fechamento de minas | `#/fechamento` | mineração | Radar `minas-v1` (fechamento, caducidade, renúncia, suspensão) + barragens a ≤5 km | `/api/radar-setor?tipo=fechamento` |
| Barragens de mineração | `#/radar` | mineração | Radar de abandono `abandono-v1` (SIGBM+SNISB), ficha, plano de contingência, rascunho de representação | `/api/radar/*` |
| Atlas ANM | `#/atlas` | mineração | Mapa/tabela das 902 barragens, busca por empresa/CNPJ, carteira | `/api/official/sigbm*`, `/api/entities/*`, `/api/watchlist` |
| Usinas e outorgas | `#/outorgas` | energia | Radar `outorgas-v1` (ANEEL/SIGA) + barragens de usinas (SNISB/ANEEL) | `/api/radar-setor?tipo=outorgas|barragens_usinas` |
| Reservatórios (ONS) | `#/hidro` | energia | 175 reservatórios, z-score sazonal, casos análogos (KNN) | `/api/hidro` |
| Barragens de abastecimento | `#/abastecimento` | saneamento | Radar `abastecimento-v1` (SNISB) | `/api/radar-setor?tipo=abastecimento` |

**Conformidade:**
| Aba | Rota | O que faz | APIs |
|---|---|---|---|
| Alertas | `#/compliance` | Alertas jurídicos/compliance com nível, base legal, prazo, dono; transições (aberto → regularização → resolvido); denúncias recebidas e resposta; documentos S3 por cliente | `/api/compliance*`, `/api/denuncias/recebidas`, `/api/denuncias/responder`, `/api/docs*` |
| Mudanças normativas | `#/impact` | Vigência por artigo, laboratório de impacto, triagem de projeto | `/api/findings`, `/api/analyze`, `/api/diff`, `/api/projects/screen` |
| Decisão & execução | `#/decision` | Revisões por função, evidências com hash, trilha, dossiê | `/api/reviews*`, `/api/export/decision-pack`, `/api/audit*` |
| Denúncias | `#/denuncia` | Denúncia assistida (também para empresa) | `/api/denuncia*` |
| Fontes & governança | `#/gov` | Conectores oficiais, monitor de fontes, qualidade, auditoria | `/api/connectors/*`, `/api/monitor*`, `/api/sources` |

**Central de IA** (`#/ia`): conversa, agente, predição (2 modelos), ciclo campeão × desafiante, consulta → filtros, inconsistências, avaliação (`eval-v2`, 50 casos + matriz de cobertura), rascunhos, custo por cliente/funcionalidade. APIs: `/api/ai/*`, `/api/agent*`, `/api/ml/*`, `/api/cobertura`.

**Conta:** Meu perfil (`#/perfil`: nome, foto, cargo, telefone, local), notificações (sino), perfil da empresa (topo). APIs: `/api/account/profile`, `/api/notifications*`.

**Só para a equipe/banca (fora do menu):** Negócio & impacto (`#/negocio`), Contas-alvo (`#/contas`).

### 1.3 Cidadão (LexIA Cidadão)
| Tela | Rota | O que faz | APIs |
|---|---|---|---|
| Minha região | `#/cidadao` | Barragens oficiais perto da cidade escolhida, explicação simples, acompanhar | `/api/official/sigbm`, `/api/watchlist` |
| Fazer denúncia | `#/denuncia` | Relato → normas do setor certo → documento → confirmação; **localização em tempo real** acha a estrutura mais próxima; vai direto à empresa (se usa a LexIA) ou ao órgão | `/api/proximos`, `/api/denuncia`, `/api/docs/upload` |
| Transparência | `#/transparencia` | Portal público | `/api/transparencia` |
| Barragens sem manutenção | `#/radar` | Radar público | `/api/radar/*` |
| Central de IA | `#/ia` | Perguntas em linguagem simples | `/api/ai/quick` |

---

## 2. Princípio do app
O app **não é o site encolhido**. No computador a pessoa analisa; no celular ela **fica sabendo, decide e prova**. Cada tela do app responde a uma pergunta curta:
- Empresário/gestor: *“Tem algo grave hoje? O que eu preciso aprovar? Já resolvi?”*
- Equipe de campo: *“Qual é o problema neste ativo e como registro o que fiz?”*
- Cidadão: *“Tem risco perto de mim? Como eu denuncio agora?”*

Recomendação técnica: **um app só, com as duas experiências** (empresa e cidadão, escolhidas no login, como no site), feito primeiro como **PWA** (já instalável hoje, mesmo backend e mesmas APIs). App nativo depois, só se faltar algo que o PWA não faz bem (ex.: push no iPhone antigo, biometria).

---

## 3. App da empresa — 5 abas na barra inferior

### Aba 1 · Hoje (tela inicial)
O que mostrar, nesta ordem:
1. **Crítico agora** — alertas Crítico/Alto do perfil (ativos, compliance, sensores), com dono e prazo. *(existe: `/api/ativos`, `/api/compliance`)*
2. **Para você aprovar** — decisões e rascunhos que esperam o seu papel (regra: a IA propõe, humano confirma). *(existe: `/api/reviews`, `/api/agent`, `/api/radar/drafts`)*
3. **Vence esta semana** — documentos e licenças. *(existe: documentos em `/api/ativos`)*
4. **Denúncias sem resposta**. *(existe: `/api/denuncias/recebidas`)*
5. Um número por linha: ativos críticos · alertas sem dono (meta 0) · prazos da semana.

### Aba 2 · Alertas
- Lista filtrável por nível; cartão com: o que é, ativo, base legal (1 linha + “ver norma”), prazo, quem recebe.
- **Ações de um toque**: “Assumir”, “Em regularização”, “Resolvido” (exige evidência), “Encaminhar a outro papel”. *(existe: `/api/compliance/transition`)*
- **Evidência pela câmera** (foto/documento) → cofre com hash. *(existe o cofre: `/api/docs/upload`; **novo**: captura direta pela câmera no app)*
- Denúncias recebidas: ler, mudar situação, responder. *(existe)*

### Aba 3 · Ativos
- Mapa compacto (região dos ativos) + lista; filtro por situação.
- Ficha do ativo: situação, documentos com vencimento, último valor dos sensores e tendência, alertas abertos. *(existe: `/api/ativos`)*
- **Registrar inspeção / ocorrência** no ativo com foto, localização e observação. *(**novo**)*
- Radar do setor em versão resumida (só Crítica/Alta perto dos meus ativos). *(existe: `/api/radar-setor`; **novo**: filtro “perto dos meus ativos”)*

### Aba 4 · Aprovar
- Fila de decisões do meu papel (revisões, rascunhos de ofício/representação, ações do agente).
- Ler resumo + fonte → **Aprovar / Rejeitar com motivo**. Nada sai sem esse toque. *(existe: `/api/reviews/transition`, `/api/agent/decide`, `/api/radar/draft/decide`)*

### Aba 5 · Perguntar (IA)
- Pergunta curta sobre normas **do setor do perfil**, com fonte e aviso quando a norma é de outro setor; abstenção quando não sabe. *(existe: `/api/ai/quick`, `/api/ask` com `setor`)*
- **Novo (opcional)**: ditar a pergunta por voz (recurso do próprio teclado do celular já resolve no PWA).

### Fixos no topo
Perfil da empresa (trocar setor), sino de notificações, foto → Meu perfil / sair.

---

## 4. App do cidadão (LexIA Cidadão) — 4 abas
1. **Perto de mim** — localização em tempo real → barragens, minas e ativos próximos com nível de atenção em linguagem simples. *(existe: `/api/proximos`)*
2. **Denunciar** — botão grande; estrutura mais próxima já escolhida; relato + fotos da câmera; normas certas do setor; confirmar; vai à empresa ou ao órgão; protocolo. *(existe; **novo**: câmera direta e rascunho offline)*
3. **Minhas denúncias** — situação (recebida, em apuração, respondida) e a resposta da empresa. *(existe parcialmente: `/api/denuncias`; **novo**: mostrar a resposta da empresa para quem denunciou)*
4. **Transparência** — versão curta do portal (números, casos da minha UF, ranking de respostas das empresas). *(existe: `/api/transparencia`)*

Sempre visível: **botão de emergência** (199 Defesa Civil / 193 Bombeiros) com toque direto para ligar.

---

## 5. O que fica só no computador (não vai para o app)
| Funcionalidade | Por quê |
|---|---|
| Atlas ANM completo, tabelas grandes, exportar CSV | Análise em tela grande |
| Mudanças normativas / laboratório de impacto / triagem de projeto (PDF) | Leitura longa e comparação lado a lado |
| Dossiê de decisão e trilha de auditoria completa | Documento extenso (no app: só “aprovar”) |
| Fontes & governança, conectores, monitor | Administração |
| Central de IA avançada: predição, ciclo de modelos, avaliação, matriz de cobertura, custo | Equipe técnica |
| Configuração do setor, rotas de alerta, papéis | Administrador da empresa |
| Upload de documentos grandes (laudos, licenças em PDF) | Melhor no computador; no app só foto/evidência |
| Negócio & impacto, Contas-alvo | Material interno da equipe |

---

## 6. O que é novo e precisa ser construído para o celular
| # | Item | Para quê | Onde mexe |
|---|---|---|---|
| 1 | **Notificação push** (Web Push no PWA) para alertas Crítico/Alto do meu papel, denúncia recebida e aprovação pendente | Saber sem abrir o app | Service worker + chave VAPID + tabela de inscrições; reaproveita o roteamento por papel (`orgfunc:`) |
| 2 | **Prazo de ciência + escalonamento automático** (se ninguém abrir em X horas, sobe de nível) | Nenhum alerta esquecido | `ComplianceDesk` + agendador; hoje existe o escalonamento por papel vazio |
| 3 | **Evidência pela câmera** (foto + hora + localização opcional) | Provar no campo | `<input capture>` → `/api/docs/upload` (cofre com hash) |
| 4 | **Registro de inspeção/ocorrência** no ativo | Equipe de campo | Novo endpoint ligado ao ativo e ao alerta |
| 5 | **Tela “Hoje”** agregada (um endpoint só, leve) | Abrir rápido em 4G | Novo `/api/mobile/hoje` juntando ativos, compliance, reviews e denúncias |
| 6 | **Modo offline**: últimos alertas e fichas dos meus ativos em cache; rascunho de denúncia offline | Mina e barragem têm sinal ruim | Service worker (cache por usuário) + fila de envio |
| 7 | **Resposta da empresa visível para quem denunciou** | Fechar o ciclo da denúncia | `/api/denuncias` incluir situação/resposta da empresa |
| 8 | **Login rápido** (manter sessão no aparelho com PIN/biometria do sistema) | Uso diário | Sessão longa por dispositivo + revogação no perfil |
| 9 | **HTTPS publicado** | Localização, câmera e push só funcionam em HTTPS fora do computador local | Hospedagem (ex.: AWS) |

---

## 7. Ordem sugerida (MVP do app)
1. Empresa: **Hoje + Alertas (com ações e foto) + Aprovar** — é o que o empresário resolve no celular.
2. Cidadão: **Perto de mim + Denunciar + Minhas denúncias** + botão de emergência.
3. Push e prazo de ciência.
4. Ativos com registro de inspeção e modo offline.
5. Perguntar (IA) e Transparência curta.

## 8. Regras que o app precisa manter (iguais às da plataforma)
- A IA propõe; regras verificam; **humano confirma** — nenhum envio ou tarefa legal sem o toque de aprovação.
- Normas só do setor do perfil; lacuna vai para a curadoria.
- Nenhum alerta sem dono.
- Localização do cidadão não é gravada; pessoa física não tem nome exibido; denúncia anônima para a empresa por padrão.
- Dados das empresas da demonstração são fictícios; empresas reais aparecem só com dados públicos.
