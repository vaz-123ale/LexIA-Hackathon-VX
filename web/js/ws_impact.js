// Área 3: Laboratório de Impacto — norma/versão/data → diff por dispositivo → carteira → cascata → "e se" → dependências.
import { state, data, api, e, fmtDate, tag, originTag, refs, card, empty, AXES, LIFE_FROM_TEMPORAL, finding, assetById, scenarioById, cenarioDoSetor } from './core.js';
import { repasseHtml, bindRepasse, carregarRepasses } from './triagem.js';
import { explainTable } from './ws_exec_atlas.js';
import { projectForm, mountProject } from './project_screen.js';

state.lab = state.lab || { sel: null, portfolio: 'official' };
const QUICK = { eir: [['2026-04-10', 'Antes do aviso'], ['2026-04-17', 'Depois do aviso'], ['2026-11-06', 'Hoje']], anm: [['2026-11-06', 'Hoje'], ['2027-04-22', 'Arts. 76–77'], ['2027-08-02', 'Regra geral'], ['2029-12-26', '§1º art. 7º']],
  nr20: [['2024-12-01', 'Antes da Portaria 60/2025'], ['2026-11-06', 'Hoje']], anp_cp21: [['2026-11-06', 'Consulta aberta'], ['2027-01-10', 'Após a consulta']], ansn: [['2026-11-06', 'Hoje']] };
const FIELD_FMT = (k, v) => v == null || (Array.isArray(v) && !v.length) ? '—' : Array.isArray(v) ? v.join('; ') : (k.startsWith('valid') ? fmtDate(v) : v);
const FACTS = {
  building: ['Em edificação', [[true, 'Sim'], [false, 'Não'], [null, 'Não informado']]], generator: ['Grupo gerador', [[true, 'Sim'], [false, 'Não'], [null, 'Não informado']]],
  fuel: ['Combustível', [['diesel', 'Diesel'], ['biodiesel', 'Biodiesel'], ['gas', 'Gás'], [null, 'Não informado']]], tank_config: ['Tanque de consumo', [['separate', 'Separado'], ['integrated', 'Integrado'], ['none', 'Sem tanque'], [null, 'Não informado']]],
  dam: ['Cadastrado como barragem', [[true, 'Sim'], [false, 'Não'], [null, 'Não informado']]], anp_regulated: ['Atividade regulada ANP', [[true, 'Sim'], [false, 'Não'], [null, 'Não informado']]],
  radiative: ['Instalação radiativa', [[true, 'Sim'], [false, 'Não'], [null, 'Não informado']]], offshore_excluded: ['Plataforma marítima (20.2.2a)', [[true, 'Sim'], [false, 'Não'], [null, 'Não informado']]],
};

function portfolio() {
  const sc = state.scenario;
  if (state.lab.portfolio === 'official' && sc === 'anm' && data.official?.available) {
    return data.official.records.map((r) => ({ fid: `anm:${r.id}`, name: r.name, owner: r.owner_name, where: `${r.municipio}/${r.uf}`, origin: 'DADO_OFICIAL', applic: r.applicability, priority: r.priority, next: r.next_action }));
  }
  return data.assets.map((a) => { const f = finding(sc, a.id); return { fid: `${sc}:${a.id}`, name: a.name, owner: 'Cenário sintético', where: a.region, origin: 'CENARIO_HIPOTETICO', applic: f.axes.applicability_assessment, priority: f.axes.priority.level, next: f.axes.next_action, score: f.axes.priority.score }; });
}

export const impact = {
  title: 'Laboratório de Impacto', crumb: 'Da mudança normativa ao ativo afetado',
  async render() {
    await carregarRepasses();
    if (!cenarioDoSetor(scenarioById(state.scenario))) { const f = data.scenarios.find(cenarioDoSetor); if (f) { state.scenario = f.id; if (state.lab) state.lab.sel = null; } }
    const sc = scenarioById(state.scenario);
    const diffs = await api(`/api/diff?scenario=${sc.id}`);
    const life = (pid) => { const p = data.provisions.find((x) => x.id === pid); return p ? tag('lifecycle', LIFE_FROM_TEMPORAL[p.status]) : ''; };
    const foot = (d) => `<p class="hint">${e(d.basis)} Origem: ${e(d.origin)}. ${data.health.llm.enabled ? 'Proposta de IA disponível em “Perguntar sobre esta análise” (rotulada como proposta até revisão).' : 'IA generativa desligada: nenhuma proposta de IA exibida.'} ${d.after.official_text_url ? `<a href="${e(d.after.official_text_url)}" target="_blank" rel="noopener noreferrer">Texto oficial ↗</a>` : ''} ${refs(d.after.sources)}</p>`;
    const paired = diffs.filter((d) => d.before), single = diffs.filter((d) => !d.before);
    const diffHtml = paired.map((d) => `<div class="diff"><div class="diff-h"><strong>${e(d.after.provision)}</strong>${life(d.after_id)}<span class="muted sm">${e(d.after.document)}</span></div>
      <div class="diff-cols"><div class="col before"><div class="col-h">Antes · <code>${e(d.before_id)}</code> ${life(d.before_id)}</div><dl class="kv">${d.changes.map((c) => `<dt>${e(c.label)}</dt><dd>${e(FIELD_FMT(c.field, c.before))}</dd>`).join('')}</dl></div>
      <div class="col after"><div class="col-h">Depois · <code>${e(d.after_id)}</code> ${life(d.after_id)}</div><dl class="kv">${d.changes.map((c) => `<dt>${e(c.label)} <span class="chg">${e(c.type)}</span></dt><dd>${e(FIELD_FMT(c.field, c.after))}</dd>`).join('')}</dl></div></div>${foot(d)}</div>`).join('')
      + (single.length ? `<div class="table-wrap"><table class="table compact"><thead><tr><th>Dispositivo</th><th>Versão</th><th>Início de vigência</th><th>Status na data</th><th>Resumo curado</th><th>Fontes</th></tr></thead><tbody>${single.map((d) => `<tr><td><strong>${e(d.after.provision)}</strong><div class="sub"><code>${e(d.after_id)}</code></div></td><td>${e(d.after.version)}</td><td>${e(FIELD_FMT('valid_from', d.after.valid_from || d.after.consultation_from))}</td><td>${life(d.after_id)}</td><td class="sm">${e(d.after.summary)}</td><td>${refs(d.after.sources)}${d.after.official_text_url ? ` <a href="${e(d.after.official_text_url)}" target="_blank" rel="noopener noreferrer">texto oficial ↗</a>` : ''}</td></tr>`).join('')}</tbody></table></div>
        <p class="hint">Sem versão anterior no corpus curado para estes dispositivos: comparação limitada a vigência e metadados. ${e(single[0].basis)} ${data.health.llm.enabled ? '' : 'IA generativa desligada: nenhuma proposta de IA exibida.'}</p>` : '');

    const pf = portfolio();
    const counts = Object.keys(AXES.applic).map((k) => [k, pf.filter((x) => x.applic === k).length]).filter(([, n]) => n);
    const order = { urgent: 0, high: 1, medium: 2, low: 3, not_assessed: 4 };
    const top = pf.filter((x) => ['candidate_review', 'missing_attributes', 'confirmed_applicable_by_human'].includes(x.applic)).sort((a, b) => order[a.priority] - order[b.priority]).slice(0, 12);
    if (!state.lab.sel || !pf.some((x) => x.fid === state.lab.sel)) state.lab.sel = top[0]?.fid || pf[0]?.fid;

    const [scId, aid] = state.lab.sel.split(':');
    const c = await api(`/api/chain?asset=${encodeURIComponent(aid)}&scenario=${scId}&as_of=${state.asOf}`);
    const cascade = [
      ['Norma', `${sc.subtitle}`, 'fonte catalogada', refs(sc.sources)], ['Dispositivo', Object.entries(c.axes.normative_lifecycle).map(([k, v]) => `${k} · ${AXES.lifecycle[v][0]}`).join('; ') || '—', 'regra temporal', ''],
      ['Obrigação candidata', c.finding.headline, 'derivada (regra ' + c.finding.rule_id + ')', ''], ['Ativo', `${c.finding.asset_id}`, c.origin === 'DADO_OFICIAL' ? 'dado oficial' : 'cenário hipotético', ''],
      ['Processo', 'Sem dado autorizado', 'roadmap (P2)', ''], ['Controle', 'Sem dado autorizado', 'roadmap (P2)', ''],
      ['Evidência', `${(c.stages.find((s) => s.key === 'evidencia')?.summary) || '—'}`, 'registro humano', ''], ['Contrato / projeto', 'Sem dado autorizado', 'roadmap (P2)', ''],
      ['Decisão', c.axes.workflow_state ? AXES.workflow[c.axes.workflow_state][0] : '—', 'humano', ''],
    ];
    const isSyn = c.origin !== 'DADO_OFICIAL';
    const a = isSyn ? assetById(aid) : null, ov = isSyn ? (state.overrides[aid] || {}) : {};
    let sim = null;
    if (isSyn && Object.keys(ov).length) sim = await api('/api/analyze', { asset_id: aid, scenario_id: scId, as_of: state.asOf, facts_override: ov });
    return `
    <div class="page-head"><div><h2>Laboratório de Impacto</h2><p class="muted">Escolha a norma e a data. A vigência é calculada por dispositivo; as regras só se aplicam quando os atributos necessários existem.</p></div></div>
    ${repasseHtml('mudanca', sc.id, sc.title || sc.name || sc.id)}

    <div class="filters">
      <label class="field"><span>Norma / mudança</span><select data-bind="scenario">${data.scenarios.filter((s) => cenarioDoSetor(s) || s.id === sc.id).map((s) => `<option value="${s.id}" ${s.id === sc.id ? 'selected' : ''}>${e(s.name)}</option>`).join('')}</select></label>
      <label class="field"><span>Data-base</span><input type="date" data-bind-date value="${state.asOf}" min="2020-01-01" max="2035-12-31"></label>
      <div class="quick">${(QUICK[sc.id] || []).map(([d, l]) => `<button class="btn sm ${state.asOf === d ? 'primary' : ''}" data-date="${d}">${e(l)} · ${fmtDate(d)}</button>`).join('')}</div>
    </div>
    <ol class="steps">
      <li><span>1</span>Mudança por dispositivo</li><li><span>2</span>Carteira impactada</li><li><span>3</span>Cascata do ativo</li><li><span>4</span>E se</li>
    </ol>
    ${card('1 · Mudança por dispositivo <span class="muted">— diff lado a lado</span>', diffHtml, { right: `<span class="hint">${e(sc.notes)}</span>` })}
    <div class="grid-6-6">
      ${card('2 · Carteira impactada', `<div class="row between wrap"><div class="seg">${sc.id === 'anm' ? `<button data-pf="official" class="${state.lab.portfolio === 'official' ? 'on' : ''}">Dados oficiais · SIGBM</button>` : ''}<button data-pf="synthetic" class="${state.lab.portfolio !== 'official' || sc.id !== 'anm' ? 'on' : ''}">Cenário hipotético</button></div>${sc.id !== 'anm' ? '<span class="hint">Sem fonte oficial conectada para este setor: só o cenário hipotético.</span>' : ''}</div>
        <div class="counts">${counts.map(([k, n]) => `<div>${tag('applic', k)}<b>${n}</b></div>`).join('')}</div>
        <div class="table-wrap short"><table class="table compact"><thead><tr><th>Estrutura</th><th>Enquadramento</th><th>Prioridade</th><th>Próxima ação</th></tr></thead><tbody>${top.map((x) => `<tr class="${x.fid === state.lab.sel ? 'sel' : ''}" tabindex="0" data-pick="${e(x.fid)}"><td><strong>${e(x.name)}</strong><div class="sub">${e(x.owner)} · ${e(x.where)}</div></td><td>${tag('applic', x.applic)}</td><td>${tag('priority', x.priority)}</td><td class="sm">${e(x.next)}</td></tr>`).join('') || `<tr><td colspan="4">${empty('Nenhum candidato nesta data.')}</td></tr>`}</tbody></table></div>
        <p class="hint">Mostrando até 12 candidatos ordenados pela prioridade LexIA. A lista completa está no Atlas.</p>`)}
      ${card(`3 · Cascata · ${originTag(c.origin)}`, `<ol class="cascade">${cascade.map(([k, v, how, extra]) => `<li class="${how.startsWith('roadmap') ? 'gap' : ''}"><span class="k">${e(k)}</span><span class="v">${e(v)} ${extra}</span><span class="how">${e(how)}</span></li>`).join('')}</ol>
        ${c.finding.temporal_note ? `<p class="warn-note">${e(c.finding.temporal_note)}</p>` : ''}
        <details><summary>Explicação da triagem</summary>${explainTable(c.explanation, c.finding)}</details>
        <div class="row gap wrap mt12"><button class="btn" data-toggle-graph>${state.showGraph ? 'Ocultar dependências' : 'Ver dependências'}</button><a class="btn" href="/api/export/decision-pack?finding=${encodeURIComponent(state.lab.sel)}&as_of=${state.asOf}" target="_blank" rel="noopener">Dossiê de decisão</a><button class="btn ghost" data-ask>Perguntar sobre esta análise</button></div>`)}
    </div>
    ${state.showGraph ? `<section class="card"><header class="card-h"><h3>Dependências (cenário hipotético)</h3><span class="hint">Grafo derivado das regras; cada aresta tem source_id e review_status.</span></header><div id="graph-slot" class="graph-wrap"><div class="loading">Carregando grafo…</div></div></section>` : ''}
    ${card('4 · E se <span class="muted">— apenas ativos hipotéticos</span>', isSyn ? `<p class="muted sm">Altere atributos hipotéticos de <b>${e(aid)}</b>. Nada é salvo no cadastro.</p><div class="facts">${Object.entries(FACTS).map(([k, [label, opts]]) => { const cur = k in ov ? ov[k] : a.facts[k] ?? null; return `<label class="field"><span>${e(label)}${k in ov ? ' <b class="mod">alterado</b>' : ''}</span><select data-fact="${k}">${opts.map(([v, l]) => `<option value='${JSON.stringify(v)}' ${JSON.stringify(cur) === JSON.stringify(v) ? 'selected' : ''}>${e(l)}</option>`).join('')}</select></label>`; }).join('')}</div>
      ${sim ? `<div class="compare"><div>Cadastro: <b>${e(c.finding.headline)}</b></div><div>→</div><div>Simulação: <b>${e(sim.headline)}</b> <span class="muted">(regra ${e(sim.rule_id)})</span></div></div><button class="btn sm" id="sim-reset">Restaurar cadastro</button>` : ''}`
      : '<p class="muted">Dados oficiais não são editáveis aqui: o “e se” só vale para cenários hipotéticos, para não sugerir que a estrutura real mudou.</p>')}    <details class="project-intake" ${state.projectOpen ? 'open' : ''}><summary>Triagem de novo projeto · enviar PDF ou descrição</summary>${projectForm()}</details>`;
  },
  async mount(root, ctx) {
    bindRepasse(root, ctx);
    mountProject(root, ctx);
    if(state.projectScroll){root.querySelector('.project-intake')?.scrollIntoView({block:'start'});state.projectScroll=false;}
    root.querySelectorAll('[data-date]').forEach((b) => b.addEventListener('click', () => ctx.setDate(b.dataset.date)));
    root.querySelectorAll('[data-pf]').forEach((b) => b.addEventListener('click', () => { state.lab.portfolio = b.dataset.pf; state.lab.sel = null; ctx.rerender(); }));
    root.querySelectorAll('[data-pick]').forEach((tr) => { const go = () => { state.lab.sel = tr.dataset.pick; ctx.rerender(); }; tr.addEventListener('click', go); tr.addEventListener('keydown', (ev) => ev.key === 'Enter' && go()); });
    root.querySelector('[data-toggle-graph]')?.addEventListener('click', () => { state.showGraph = !state.showGraph; ctx.rerender(); });
    root.querySelectorAll('[data-fact]').forEach((s) => s.addEventListener('change', () => {
      const aid = state.lab.sel.split(':')[1], k = s.dataset.fact, v = JSON.parse(s.value), ov = { ...(state.overrides[aid] || {}) };
      if (JSON.stringify(assetById(aid).facts[k] ?? null) === JSON.stringify(v)) delete ov[k]; else ov[k] = v;
      state.overrides[aid] = ov; ctx.rerender();
    }));
    root.querySelector('#sim-reset')?.addEventListener('click', () => { delete state.overrides[state.lab.sel.split(':')[1]]; ctx.rerender(); });
    const slot = root.querySelector('#graph-slot');
    if (slot) {
      const [{ graphSvg }, g] = await Promise.all([import('./graph.js'), api(`/api/graph?as_of=${state.asOf}`)]);
      slot.innerHTML = graphSvg(g, null);
    }
  },
};
