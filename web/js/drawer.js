// Assistente contextual em gaveta: recebe a seleção atual e mostra trechos, verificação e abstenção.
import { state, data, api, e, fmtDate, refs, scenarioById, icon, currentUser, refreshReviews, refreshMe, perfilSetor } from './core.js';
import { accountBriefing, accountIntent } from './account_assistant.mjs';
import { summaryHtml, bindSummary } from './workbench.js';

let last = null, activeTab = 'chat', busy = false, error = '', lastKey = '', returnFocus = null;
let agendaReady = false, agendaFilter = 'all';
let accountSummary = null;
let changedReferences = 0;
function agendaHtml() {
  if (!agendaReady) return '<p class="hint">Atualizando sua agenda…</p>';
  const b = accountBriefing(currentUser(), data.reviews, data.me.watchlist, data.templates, data.provisions, state.asOf);
  const items = b.items.filter((x) => agendaFilter === 'all' || x.kind === agendaFilter);
  return `<section class="account-agenda"><h3>Olá, ${e(b.name)}. Vamos organizar sua próxima ação?</h3><p class="hint">${e(b.scope)}</p><p class="hint">Resumo por regras · data-base ${fmtDate(state.asOf)} · nenhuma decisão automática.</p><div class="chips">${[['all','Resumo'],['review','Revisões'],['evidence','Evidências'],['milestone','Marcos']].map(([k,l]) => `<button class="chip-btn" data-agenda-filter="${k}" aria-pressed="${agendaFilter === k}">${l}</button>`).join('')}</div>${items.map((x) => `<article class="agenda-item"><span class="assistant-mode">${e({review:'Revisão pendente',evidence:'Lacuna de evidência',milestone:'Marco futuro'}[x.kind])}</span><h4>${e(x.title)}</h4><p>${e(x.text)}</p>${x.missing ? `<details><summary>Itens a conferir</summary><ul>${x.missing.map((m) => `<li>${e(m)}</li>`).join('')}</ul></details>` : ''}${x.sources ? `<p class="sm">${refs(x.sources)} · ${e(x.version || 'Versão não informada')}</p>` : ''}<button class="btn sm" ${x.kind === 'review' ? `data-open-review="${e(x.id)}"` : x.kind === 'evidence' ? `data-agenda-evidence="${e(x.id)}"` : `data-go="impact"`}>${e(x.action)}</button></article>`).join('') || '<p class="warn-note">Não há itens nesse recorte dos dados disponíveis. Isso não significa ausência de obrigações. Adicione ativos à carteira e confira os registros.</p>'}</section>`;
}
export function closeDrawer() { document.getElementById('drawer')?.classList.remove('open'); returnFocus?.focus?.(); }
export function context() {
  const review = state.ws === 'decision' ? state.openReview : null;
  const sel = review || (state.ws === 'impact' ? state.lab?.sel : state.selection && (state.selection.kind === 'official' ? `anm:${state.selection.id}` : `${state.atlas.synScenario || 'nr20'}:${state.selection.id}`));
  const [sc, asset] = (sel || `${state.scenario}:`).split(':');
  return { cenario: scenarioById(sc)?.name || sc, ativo: asset || '—', data_base: state.asOf, area: state.ws };
}
function suggestions(ctx) {
  const n = ctx.cenario.toLowerCase();
  if (n.includes('barrag')) return ['Quando os dispositivos da Resolução ANM 220/2025 entram em vigor?', 'A ANM 245/2026 mudou o quê na 220/2025?', 'Esta barragem está segura?'];
  if (n.includes('nr-20')) return ['O que mudou na NR-20 sobre tanques de gerador?', 'A exceção vale para plataforma marítima?', 'Qual multa devo pagar?'];
  if (n.includes('anp')) return ['A consulta pública 21/2026 da ANP já obriga alguma coisa?'];
  return ['As normas da CNEN ainda valem com esse nome?'];
}
function body() {
  const ctx = context();
  const r = last;
  const role = `<section class="assistant-purpose"><span class="assistant-mode">${data.health.llm.enabled ? 'IA generativa conectada' : 'Modo controlado · sem IA generativa'}</span><h3>Da fonte à explicação, com revisão humana</h3><p>Consulte o dossiê curado, entenda as mudanças e identifique o que precisa ser conferido.</p></section>`;
  return `<header class="drawer-h"><div><strong>Perguntar sobre esta análise</strong><small>Contexto: ${e(ctx.cenario)} · ${e(ctx.ativo)} · ${fmtDate(ctx.data_base)}</small></div><button class="icon-btn" data-close aria-label="Fechar">×</button></header>
  <div class="assistant-tabs" role="tablist" aria-label="Áreas do assistente">${[['agenda','Minha agenda'],['chat','Conversar'],['context','Fontes'],['role','Papel da IA']].map(([id,label]) => `<button role="tab" aria-selected="${activeTab === id}" data-assistant-view="${id}" class="${activeTab === id ? 'on' : ''}">${label}</button>`).join('')}</div>
  <div class="drawer-b">${activeTab === 'agenda' ? agendaHtml() + (changedReferences ? `<p class="warn-note">${changedReferences} referência(s) com mudança no corpus ou na situação temporal da data-base. Confira a comparação antes de revalidar.</p>` : '') + (accountSummary ? summaryHtml(accountSummary) : '') + '<button class="btn mt12" data-go-tab="decision:workbench">Projetos, versões e reavaliações</button>' : role}
    ${activeTab === 'agenda' ? '' : `
    ${activeTab === 'role' ? `<div class="assistant-capabilities"><h3>O que está disponível</h3><ul><li>Buscar trechos nos resumos de dispositivos e notas das fontes do dossiê local.</li><li>Responder sobre NR-20, transição ANM, consulta ANP e redesignação CNEN/ANSN, dentro da base.</li><li>Exibir fontes, trechos recuperados, lacunas e rastro de execução.</li><li>Alternar linguagem simples e técnica.</li><li>Com provedor configurado: redigir propostas e conferir a existência literal das citações nos trechos recuperados.</li></ul><h3>O que usa regras</h3><p>Vigência por dispositivo, triagem de ativos, indicadores e workflow. O monitor detecta mudança de conteúdo; não interpreta a norma.</p><h3>O que exige revisão</h3><p>A conferência de citações não valida todas as afirmações nem resolve conflitos jurídicos. Aplicabilidade e ações legais precisam de pessoa competente.</p><h3>Ainda não implementado</h3><p>Extração automática de obrigações por LLM e explicação automática do impacto empresarial. Nenhuma tarefa é publicada pelo assistente.</p><button class="btn" data-go-tab="gov:ai">Ver diagnóstico e checklist</button></div>` : activeTab === 'context' ? `<h3>Contexto selecionado</h3><dl class="kv"><dt>Área</dt><dd>${e(ctx.area)}</dd><dt>Cenário</dt><dd>${e(ctx.cenario)}</dd><dt>Ativo</dt><dd>${e(ctx.ativo)}</dd><dt>Data-base</dt><dd>${fmtDate(ctx.data_base)}</dd></dl><p class="warn-note">O contexto identifica a tela. A resposta atual busca pela pergunta no dossiê; não l? automaticamente a ficha do ativo nem recalcula sua aplicabilidade.</p><h3>Fontes da última resposta</h3>${r?.source_ids.length ? `<p>${refs(r.source_ids)}</p>` : '<p class="muted">Faça uma pergunta para consultar fontes e trechos recuperados.</p>'}<ul class="history">${(r?.passages || []).map((p) => `<li><strong>${e(p.title)}</strong><small>${e(p.version || '')}</small><p>${e(p.text)}</p></li>`).join('')}</ul><button class="btn" data-go-tab="gov:sources">Abrir catálogo de fontes</button>` : `

    <p class="hint">${data.health.llm.enabled ? 'IA conectada: só exibe resposta cujas citações passem no verificador.' : 'Modo controlado: recuperação local + respostas pré-validadas; sem IA generativa.'} Os dois perfis mudam o texto, nunca fontes, datas ou certeza.</p>
    <form id="ask"><textarea id="q" rows="3" maxlength="1500" aria-label="Pergunta">${e(state.question || suggestions(ctx)[0])}</textarea>
      <div class="row between"><div class="seg"><button type="button" data-p="simples" class="${state.profile === 'simples' ? 'on' : ''}">Simples</button><button type="button" data-p="tecnico" class="${state.profile === 'tecnico' ? 'on' : ''}">Técnico</button></div><button class="btn primary" ${busy ? 'disabled' : ''}>${busy ? 'Consultando…' : 'Perguntar'}</button></div></form>
    <div class="chips">${suggestions(ctx).map((s) => `<button class="chip-btn" data-s="${e(s)}">${e(s)}</button>`).join('')}</div>
    <div class="chips" aria-label="Perguntas sobre sua conta">${['Minhas pendências','Minhas revisões','Minhas evidências','Próximos marcos'].map((s) => `<button class="chip-btn" data-s="${e(s)}">${e(s)}</button>`).join('')}</div>
    <button class="btn" data-project-open>Analisar PDF ou descrição de projeto</button>
    ${error ? `<p class="warn-note" role="alert">${e(error)}</p>` : ''}
    ${r ? `<div class="answer-box" aria-live="polite"><div class="row between"><b>${e({ ABSTAIN: 'Abstenção', GROUNDED_DEMO: 'Resposta com base curada', AI_VERIFIED: 'IA · citações verificadas', AI_PARTIAL: 'IA · verificação parcial' }[r.state] || r.state)}</b><span class="muted sm">${e(r.mode)}</span></div>
      <p>${e(state.profile === 'tecnico' ? r.answer_technical : r.answer_simple)}</p>${r.source_ids.length ? `<p class="sm">Documentos: ${refs(r.source_ids)}</p>` : ''}
      ${r.aviso_setor ? `<p class="warn-note">${e(r.aviso_setor)}</p>` : ''}
      ${r.perspectiva ? `<div class="persp"><b>Para você · ${e(r.perspectiva.rotulo)}</b><small>${e(r.perspectiva.foco)}</small>${r.perspectiva.pontos.map((x) => `<span>• ${e(x)}</span>`).join('')}<span class="persp-next">→ ${e(r.perspectiva.proximo_passo)}</span><small class="muted">${e(r.perspectiva.nota)}</small></div>` : ''}
      ${r.missing.length ? `<p class="sm"><b>Falta:</b> ${e(r.missing.join('; '))}</p>` : ''}<p class="hint">${e(r.disclaimer)}</p>
      <details><summary>Rastro (${r.trace.length} etapas) e trechos recuperados</summary><ol class="history">${r.trace.map((t) => `<li><strong>${e(t.step)} · ${e(t.actor)}</strong><small>${e(t.detail)}</small></li>`).join('')}</ol>
      <ul class="history">${(r.passages || []).map((p) => `<li><strong>${e(p.title)}</strong><small>${e(p.text)}</small></li>`).join('') || '<li class="muted">Nenhum trecho relevante.</li>'}</ul></details></div>` : ''}
    `}`}
  </div>`;
}
export function openDrawer(tab = 'agenda') {
  activeTab = ['agenda', 'chat', 'context', 'role'].includes(tab) ? tab : 'agenda';
  const key = JSON.stringify([currentUser()?.id, context()]);
  if (lastKey !== key) { last = null; error = ''; state.question='';lastKey = key; }
  returnFocus = document.activeElement;
  let d = document.getElementById('drawer');
  if (!d) { d = document.createElement('aside'); d.id = 'drawer'; d.className = 'drawer'; d.setAttribute('role', 'dialog'); d.setAttribute('aria-label', 'Assistente da LexIA'); document.body.appendChild(d); }
  const render = () => {
    d.innerHTML = body(); d.classList.add('open');
    bindSummary(d,async()=>{accountSummary=await api('/api/workbench/summary');render();});
    d.querySelector('[data-close]').addEventListener('click', closeDrawer);
    d.querySelectorAll('[data-assistant-view]').forEach((b) => b.addEventListener('click', () => { activeTab = b.dataset.assistantView; render(); }));
    d.querySelectorAll('[data-agenda-filter]').forEach((b) => b.addEventListener('click', () => { agendaFilter = b.dataset.agendaFilter; render(); }));
    d.querySelectorAll('[data-agenda-evidence]').forEach((b) => b.addEventListener('click', () => { state.openReview = b.dataset.agendaEvidence; state.tab.decision = 'evidence'; closeDrawer(); if (location.hash === '#/decision') document.querySelector('[data-tab="decision:evidence"]')?.click(); else location.hash = '#/decision'; }));
    d.querySelectorAll('[data-p]').forEach((b) => b.addEventListener('click', () => { state.profile = b.dataset.p; render(); }));
    const send = async (q) => {
      if (busy || !q.trim()) return;
      const intent = accountIntent(q);
      if (intent) { state.question = q; agendaFilter = intent; activeTab = 'agenda'; render(); return; }
      state.question = q; busy = true; error = ''; const requestKey = JSON.stringify([currentUser()?.id,context()]); render();
      try { const response = await api('/api/ask', { question: q, profile: state.profile, context: context(), setor: perfilSetor() }); if (requestKey === JSON.stringify([currentUser()?.id,context()])) last = response; }
      catch (err) { last = null; error = 'Não foi possível consultar o assistente. ' + err.message; }
      finally { busy = false; if (d.classList.contains('open')) render(); }
    };
    d.querySelector('#ask')?.addEventListener('submit', (ev) => { ev.preventDefault(); send(d.querySelector('#q').value); });
    d.querySelectorAll('[data-s]').forEach((b) => b.addEventListener('click', () => send(b.dataset.s)));
    d.querySelector('#q')?.focus();
  };
  agendaReady = false;
  accountSummary = null;
  changedReferences = 0;
  render();
  const uid = currentUser()?.id;
  Promise.all([refreshMe(), refreshReviews(),api('/api/workbench/summary'),api(`/api/workbench/revalidations?as_of=${state.asOf}`)]).then(([, , s, r]) => { if (uid === currentUser()?.id) { accountSummary=s;changedReferences=r.items.filter(x=>x.status==='MUDANCA_DETECTADA').length;agendaReady = true; if (d.classList.contains('open')) render(); } }).catch((err) => { agendaReady = false; error = err.message; if (d.classList.contains('open')) { render(); d.querySelector('.drawer-b').insertAdjacentHTML('afterbegin', `<p class="warn-note" role="alert">Não foi possível atualizar sua agenda: ${e(err.message)}. Feche e abra para tentar novamente.</p>`); } });
}
document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closeDrawer(); });
