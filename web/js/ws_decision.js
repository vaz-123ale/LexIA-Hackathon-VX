// Área 4: Decisão & Execução — revisões por função, evidências, Decision Lab, dossiês e calendário de marcos.
import { state, data, api, e, fmtDate, fmtDateTime, fmtMoney, tag, originTag, card, empty, tabs, curTab, toast, can, currentUser, AXES, REVIEW_STATE, FUNCTIONS, scenarioById, refreshReviews } from './core.js';
import { workbenchHtml, mountWorkbench } from './workbench.js';

const NEXT = { DRAFT: ['REVIEW_PENDING'], REVIEW_PENDING: ['CONFIRMED', 'REJECTED', 'DRAFT'], CONFIRMED: ['ACTION_TRACKING'], REJECTED: ['DRAFT'], ACTION_TRACKING: ['CLOSED'], CLOSED: [] };
const versionOf = (r) => r.provisions.map((pid) => { const p = data.provisions.find((x) => x.id === pid); return p ? `${pid} (${p.version})` : pid; }).join('; ') || r.source_ids.join(', ');
const loginHint = (perm) => can(perm) ? '' : `<p class="hint warn-note">Seu usuário atual (${e(currentUser()?.name || 'nenhum')}) não tem permissão para esta ação. Troque o usuário de demonstração no topo.</p>`;

function reviewsTab() {
  if (!state.openReview && data.reviews.length) state.openReview = data.reviews[0].id;
  const cols = Object.keys(AXES.workflow).map((w) => {
    const items = data.reviews.filter((r) => r.axes?.workflow_state === w);
    return `<div class="kcol"><div class="kcol-h">${tag('workflow', w)}<span>${items.length}</span></div>${items.map((r) => `<button class="kcard ${state.openReview === r.id ? 'sel' : ''}" data-review="${e(r.id)}">
      <span class="row between">${originTag(r.origin)}${tag('priority', r.axes?.priority.level)}</span><strong>${e(r.asset_name)}</strong><small>${e(scenarioById(r.scenario)?.name)}</small>
      <small>${r.assigned_function ? 'Função: ' + e(FUNCTIONS[r.assigned_function]) : 'Sem função atribuída'}</small></button>`).join('') || '<p class="muted sm">—</p>'}</div>`;
  }).join('');
  const r = data.reviews.find((x) => x.id === state.openReview);
  const detail = r ? `<div class="row between"><div>${originTag(r.origin)}<h3 class="mt8">${e(r.asset_name)}</h3><p class="muted">${e(scenarioById(r.scenario)?.name)} · <code>${e(r.id)}</code></p></div><div class="axes">${tag('applic', r.axes?.applicability_assessment)}${tag('workflow', r.axes?.workflow_state)}${tag('priority', r.axes?.priority.level, r.axes?.priority.justification.join(' · '))}</div></div>
    <p class="next"><span>Próxima ação</span>${e(r.axes?.next_action)}</p>
    <form id="assign-form" class="inline-form"><label class="field"><span>Atribuir à função</span><select id="as-fn">${Object.entries(FUNCTIONS).map(([k, v]) => `<option value="${k}" ${(r.assigned_function || r.axes?.suggested_function) === k ? 'selected' : ''}>${e(v)}</option>`).join('')}</select></label><button class="btn" ${can('review.transition') ? '' : 'disabled'}>Atribuir</button></form>
    ${NEXT[r.state].length ? `<form id="tr-form" class="inline-form"><label class="field"><span>Mover para</span><select id="tr-to">${NEXT[r.state].map((s) => `<option value="${s}">${e(REVIEW_STATE[s])}</option>`).join('')}</select></label><label class="field grow"><span>Fundamentação (obrigatória)</span><input id="tr-reason" required maxlength="500" placeholder="Ex.: dispositivos conferidos no texto oficial; enquadramento confirmado"></label><button class="btn primary" ${can('review.transition') ? '' : 'disabled'}>Registrar decisão</button></form>` : '<p class="muted">Fluxo encerrado.</p>'}
    ${loginHint('review.transition')}
    <p class="hint">Versão das fontes registrada na decisão: <code>${e(versionOf(r))}</code>. Confirmar/rejeitar exige papel jurídico, compliance ou especialista. A decisão nunca é “IA aprovou”.</p>
    <div class="row gap wrap"><a class="btn" href="/api/export/decision-pack?finding=${encodeURIComponent(r.id)}&as_of=${state.asOf}" target="_blank" rel="noopener">Exportar dossiê de decisão</a><button class="btn" data-tab-go="decision:evidence">Registrar evidência</button><button class="btn" data-tab-go="decision:lab">Comparar opções (Decision Lab)</button></div>
    <h4 class="mt16">Histórico</h4><ol class="history">${r.transitions.map((t) => `<li><strong>${e(REVIEW_STATE[t.from_state])} → ${e(REVIEW_STATE[t.to_state])}</strong><small>${e(t.actor)} (${e(t.role)}) · ${fmtDateTime(t.at)}</small><small>${e(t.reason)} · fonte ${e(t.source_version)}</small></li>`).join('') || '<li class="muted">Criada como rascunho pela triagem determinística. Nenhuma decisão humana ainda.</li>'}</ol>`
    : empty('Selecione um cartão para atribuir função, decidir e exportar o dossiê.');
  return `<div class="kanban">${cols}</div>${card('Revisão selecionada', detail, {icon:'doc',cls:'review-detail'})}`;
}

function evidenceTab() {
  let total = 0, done = 0;
  const rows = data.reviews.map((r) => { const items = data.templates[r.scenario] || []; const have = new Set(r.evidence.map((x) => x.item)); total += items.length; done += items.filter((i) => have.has(i)).length;
    return `<tr class="${state.openReview === r.id ? 'sel' : ''}"><td><button class="link" data-review="${e(r.id)}">${e(r.asset_name)}</button><div class="sub">${originTag(r.origin)} ${e(scenarioById(r.scenario)?.name)}</div></td><td><div class="evcells">${items.map((i) => `<span class="evc ${have.has(i) ? 'ok' : ''}">${have.has(i) ? '✓' : '○'} ${e(i)}</span>`).join('')}</div></td></tr>`; }).join('');
  const r = data.reviews.find((x) => x.id === state.openReview) || data.reviews[0];
  const items = r ? (data.templates[r.scenario] || []) : [];
  return `<p class="muted">${done} de ${total} evidências exigidas registradas. Evidência é registro de que um documento existe e foi vinculado — não declara conformidade.</p>
  <div class="grid-8-4">${card('Matriz de lacunas', `<div class="table-wrap"><table class="table"><thead><tr><th>Análise</th><th>Evidências exigidas pelo cenário</th></tr></thead><tbody>${rows || `<tr><td colspan="2">${empty('Nenhuma revisão aberta.')}</td></tr>`}</tbody></table></div>`)}
  ${card('Registrar evidência', r ? `<p><strong>${e(r.asset_name)}</strong></p><form id="ev-form"><label class="field"><span>Item exigido</span><select id="ev-item">${items.map((i) => `<option>${e(i)}</option>`).join('')}</select></label><label class="field"><span>Descrição / local no GED (sem dados pessoais)</span><textarea id="ev-desc" rows="3" maxlength="2000"></textarea></label><button class="btn primary" ${can('evidence.add') ? '' : 'disabled'}>Registrar com SHA-256</button></form>${loginHint('evidence.add')}
    <ul class="history mt12">${r.evidence.map((x) => `<li><strong>${e(x.item)}</strong><small>${e(x.description)}</small><small>${e(x.actor)} · ${fmtDateTime(x.at)} · <code>${e(x.sha256.slice(0, 16))}…</code></small></li>`).join('')}</ul><p class="hint">O hash comprova integridade pontual do registro; não é certificação de inviolabilidade.</p>` : empty('Sem revisões.'))}</div>`;
}

const DEFAULT_OPTS = [
  { name: 'Agir agora', horas_internas: [80, 120, 200], custo_hora: [120, 150, 190], custo_externo: [20000, 45000, 90000], duracao_meses: [2, 3, 5] },
  { name: 'Agir em fases', horas_internas: [100, 160, 260], custo_hora: [120, 150, 190], custo_externo: [15000, 35000, 70000], duracao_meses: [4, 6, 9] },
  { name: 'Postergar para análise', horas_internas: [20, 40, 60], custo_hora: [120, 150, 190], custo_externo: [0, 5000, 15000], duracao_meses: [1, 1, 2] },
];
state.labOpts = state.labOpts || JSON.parse(JSON.stringify(DEFAULT_OPTS));
const VARS = [['horas_internas', 'Horas internas (h)'], ['custo_hora', 'Custo/hora (R$)'], ['custo_externo', 'Custo externo (R$)'], ['duracao_meses', 'Duração (meses)']];

function labTab() {
  const res = state.labResult;
  const form = state.labOpts.map((o, i) => `<fieldset class="opt"><legend><input data-opt="${i}" data-k="name" value="${e(o.name)}" aria-label="Nome da opção ${i + 1}"></legend>${VARS.map(([k, l]) => `<div class="triplet"><span>${l}</span>${['mín', 'base', 'máx'].map((t, j) => `<input type="number" min="0" step="any" data-opt="${i}" data-k="${k}" data-j="${j}" value="${o[k][j]}" aria-label="${l} ${t}">`).join('')}</div>`).join('')}</fieldset>`).join('');
  const out = res ? `<div class="table-wrap"><table class="table"><thead><tr><th>Opção</th><th>Mínimo</th><th>Base</th><th>Máximo</th><th>Duração (base)</th><th>Variável mais sensível</th></tr></thead><tbody>${res.options.map((o) => `<tr><td><strong>${e(o.name)}</strong></td><td>${fmtMoney(o.total.low)}</td><td><b>${fmtMoney(o.total.base)}</b></td><td>${fmtMoney(o.total.high)}</td><td>${o.duration_months.base} mês(es)</td><td>${e(o.sensitivity[0].label)} (±${fmtMoney(o.sensitivity[0].swing / 2)})</td></tr>`).join('')}</tbody></table></div>
    <details><summary>Memória de cálculo e sensibilidade</summary>${res.options.map((o) => `<h4>${e(o.name)}</h4><ul class="list mono">${o.memory.map((m) => `<li>${e(m)}</li>`).join('')}</ul>${o.sensitivity.map((s) => `<div class="sens"><span>${e(s.label)}</span><div class="bar"><i style="width:${res.options[0] && Math.max(...res.options.flatMap((x) => x.sensitivity.map((y) => y.swing))) ? s.swing / Math.max(...res.options.flatMap((x) => x.sensitivity.map((y) => y.swing))) * 100 : 0}%"></i></div><span>${fmtMoney(s.low_total)} – ${fmtMoney(s.high_total)}</span></div>`).join('')}`).join('')}</details>
    <ul class="hint">${res.caveats.map((c) => `<li>${e(c)}</li>`).join('')}</ul>
    <div class="row gap"><label class="field"><span>Vincular à revisão</span><select id="lab-r"><option value="">— nenhuma —</option>${data.reviews.map((r) => `<option value="${e(r.id)}" ${state.openReview === r.id ? 'selected' : ''}>${e(r.asset_name)} · ${e(r.scenario)}</option>`).join('')}</select></label><button class="btn" id="lab-save" ${can('finance.save') ? '' : 'disabled'}>Salvar cenário (${e(res.estimator_version)})</button></div>${loginHint('finance.save')}` : empty('Ajuste as premissas e calcule. Os valores iniciais são EXEMPLOS editáveis, não dados de empresa.');
  return `<p class="muted">Compare opções de execução com premissas suas (mínimo/base/máximo). O cálculo é reproduzível e não inclui multas, sanções ou perdas.</p>
    <div class="grid-6-6">${card('Premissas (exemplos editáveis)', `<div class="opts">${form}</div><div class="row gap mt12"><button class="btn primary" id="lab-calc">Calcular</button><button class="btn ghost" id="lab-reset">Restaurar exemplos</button></div>`)}${card('Resultado', out)}</div>`;
}

function packsTab() {
  return card('Dossiês de decisão', `<p class="muted">Relatório imprimível (salve em PDF pelo navegador) com fonte, snapshot, data-base, quatro eixos, explicação, decisões, evidências e premissas. Sempre rotulado como avaliação preliminar.</p>
    <div class="table-wrap"><table class="table"><thead><tr><th>Análise</th><th>Origem</th><th>Fluxo</th><th>Decisões</th><th></th></tr></thead><tbody>${data.reviews.map((r) => `<tr><td><strong>${e(r.asset_name)}</strong><div class="sub">${e(scenarioById(r.scenario)?.name)}</div></td><td>${originTag(r.origin)}</td><td>${tag('workflow', r.axes?.workflow_state)}</td><td>${r.transitions.length}</td><td><a class="btn sm" href="/api/export/decision-pack?finding=${encodeURIComponent(r.id)}&as_of=${state.asOf}" target="_blank" rel="noopener">Exportar</a></td></tr>`).join('')}</tbody></table></div>`);
}

function calendarTab() {
  const ms = data.timeline;
  return `<div class="grid-8-4">${card('Calendário de marcos normativos (por dispositivo)', `<ul class="timeline-list">${ms.map((m) => `<li class="${m.date <= state.asOf ? 'past' : ''}"><time>${fmtDate(m.date)}</time><span><strong>${e(m.document)}</strong><small>${e(m.provision)} · ${e(m.event)}</small></span></li>`).join('')}</ul>`)}
    ${card('Licenças e condicionantes', `<p>Nenhuma fonte de licenças está conectada. O adaptador Ibama (licenciamento federal) está declarado como <b>não conectado</b>.</p><p class="muted">A LexIA não infere licenças, prazos de renovação ou condicionantes que não estejam em fonte pública ou autorizada.</p>`)}</div>`;
}

export const decision = {
  title: 'Decisão & Execução', crumb: 'Revisão humana, evidências e opções',
  async render() {
    await refreshReviews();
    const t = curTab('decision', 'reviews');
    const body = t==='workbench' ? await workbenchHtml() : { reviews: reviewsTab, evidence: evidenceTab, lab: labTab, packs: packsTab, calendar: calendarTab }[t]();
    return `<div class="page-head"><div><span class="eyebrow">Decisão & Execução</span><h2>Decisão & Execução</h2><p class="muted">A triagem cria rascunhos; pessoas com o papel certo decidem, registram evidências e exportam o dossiê.</p></div></div>
      ${tabs('decision', [['reviews', `Revisões (${data.reviews.length})`], ['evidence', 'Evidências'], ['lab', 'Decision Lab'], ['packs', 'Dossiês de decisão'], ['calendar', 'Calendário de marcos'], ['workbench','Projetos & acompanhamento']])}${body}`;
  },
  mount(root, ctx) {
    mountWorkbench(root,ctx);
    root.querySelectorAll('[data-review]').forEach((b) => b.addEventListener('click', () => { state.openReview = b.dataset.review; ctx.rerender(); }));
    root.querySelector('#assign-form')?.addEventListener('submit', async (ev) => { ev.preventDefault(); try { await api('/api/reviews/assign', { review_id: state.openReview, function: root.querySelector('#as-fn').value }); toast('Função atribuída e registrada na trilha.'); ctx.rerender(); } catch (err) { toast(err.message, 'err'); } });
    root.querySelector('#tr-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault(); const r = data.reviews.find((x) => x.id === state.openReview);
      try { await api('/api/reviews/transition', { review_id: r.id, to_state: root.querySelector('#tr-to').value, reason: root.querySelector('#tr-reason').value, source_version: versionOf(r), as_of: state.asOf }); toast('Decisão registrada na trilha de auditoria.'); ctx.rerender(); } catch (err) { toast(err.message, 'err'); }
    });
    root.querySelector('#ev-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault(); const rid = state.openReview || data.reviews[0]?.id;
      try { await api('/api/reviews/evidence', { review_id: rid, item: root.querySelector('#ev-item').value, description: root.querySelector('#ev-desc').value }); state.openReview = rid; toast('Evidência registrada com hash.'); ctx.rerender(); } catch (err) { toast(err.message, 'err'); }
    });
    root.querySelectorAll('[data-opt]').forEach((inp) => inp.addEventListener('change', () => { const o = state.labOpts[+inp.dataset.opt]; if (inp.dataset.k === 'name') o.name = inp.value; else o[inp.dataset.k][+inp.dataset.j] = Number(inp.value); }));
    root.querySelector('#lab-calc')?.addEventListener('click', async () => { try { state.labResult = await api('/api/finance/evaluate', { options: state.labOpts }); ctx.rerender(); } catch (err) { toast(err.message, 'err'); } });
    root.querySelector('#lab-reset')?.addEventListener('click', () => { state.labOpts = JSON.parse(JSON.stringify(DEFAULT_OPTS)); state.labResult = null; ctx.rerender(); });
    root.querySelector('#lab-save')?.addEventListener('click', async () => { try { await api('/api/finance/save', { review_id: root.querySelector('#lab-r').value || null, options: state.labOpts }); toast('Cenário salvo com a versão do estimador e registrado na trilha.'); } catch (err) { toast(err.message, 'err'); } });
  },
};
