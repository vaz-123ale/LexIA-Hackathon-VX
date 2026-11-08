// Áreas 1 (Visão Executiva) e 2 (Atlas Empresarial).
import { state, data, api, e, fmtDate, fmtDateTime, fmtCnpj, tag, originTag, refs, card, empty, toast, can, AXES, TRIAGE, ICON, icon, ASSET_ICON, finding, assetById, scenarioById, refreshReviews, refreshOfficial, refreshMe, cenarioDoSetor } from './core.js';
import { createMap } from './map.js';
import { satView } from './geoview.js';

const norm = (s) => String(s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
const SC_NAME = (id) => scenarioById(id)?.name || id;

// ======================= 1. VISÃO EXECUTIVA =======================
const KPI = { changes: ['doc', '#28518A'], pending: ['alert', '#D4A12E'], milestones: ['cal', '#3B82F6'], affected: ['layers', '#68487A'] };
const KPI_LABEL = { changes: 'Mudanças normativas em análise', pending: 'Avaliações pendentes de decisão', milestones: 'Marcos nos próximos 12 meses', affected: 'Ativos potencialmente afetados' };
export function changeFeed(portfolio) {
  const actionable=new Set(['REVIEW','FUTURE_REVIEW','INSUFFICIENT','MONITOR']);
  const entries=data.scenarios.filter(cenarioDoSetor).map(sc=>{
    const assets=portfolio.filter(a=>actionable.has(a.states?.[sc.id]));
    const provisions=data.provisions.filter(p=>sc.provisions.includes(p.id));
    return {sc,assets,provisions};
  }).sort((a,b)=>((b.sc.priority||0)-(a.sc.priority||0))||(b.assets.length-a.assets.length)); // prioridade: publicação com prazo (ex.: aviso EIR)
  return entries.slice(0,3).map(({sc,assets,provisions})=>{
    const gap=assets.filter(a=>a.states[sc.id]==='INSUFFICIENT').length;
    const first=assets[0];
    return `<article class="change-card"><div class="change-mark">${icon(sc.id==='anm'||sc.id==='eir'?'dam':'doc')}</div><div class="change-content"><div class="row between wrap"><h4>${e(sc.name)}</h4><span class="change-count">${assets.length} ativo(s) candidato(s)</span></div><p>${e(sc.subtitle)}</p><div class="provision-chips">${provisions.slice(0,2).map(p=>`<span title="${e(p.version)}">${e(p.provision)} · ${e(p.status_label || p.status)}</span>`).join('')}</div><p class="change-gap">${gap ? `${gap} ativo(s) com dados insuficientes; complete os atributos no laboratório.` : assets.length ? 'Confira condições, exceções e evidências antes de decidir.' : 'Sem impacto calculado neste recorte da carteira; não significa ausência de obrigação.'}</p><div class="row between wrap"><span class="sm">${refs(sc.sources)}</span><button class="link-arrow change-action" ${first ? `data-analyze="${e(sc.id+':'+first.id)}"` : `data-open-scenario="${e(sc.id)}"`}>${first?'Analisar impacto':'Consultar cenário'} ${icon('arrow')}</button></div></div></article>`;
  }).join('') || empty('Nenhuma mudança no corpus selecionado.');
}
export const exec = {
  title: 'Visão Executiva', crumb: 'Panorama regulatório',
  async render() {
    const [x, ins, EMP] = await Promise.all([api(`/api/executive?as_of=${state.asOf}`), api(`/api/insight?as_of=${state.asOf}`), api('/api/ativos/empresas').catch(() => ({ items: [] }))]);
    const OPS = await Promise.all(EMP.items.filter((c) => !state.perfil || c.id === state.perfil).map((c) => api('/api/ativos?empresa=' + encodeURIComponent(c.id)).catch(() => null)));
    const sectors = OPS.filter(Boolean).map((r) => { const crit = r.assets.filter((a) => a.status === 'critico').length, pend = r.assets.filter((a) => a.status === 'pendencia').length;
      return `<a class="sec-op" href="#/ativos" data-emp="${e(r.empresa.id)}"><span class="eyebrow">${e(r.setor.nome)}</span><b>${e(r.empresa.nome)}</b><span class="sec-n"><i style="--c:#C83037">${crit} crítico(s)</i><i style="--c:#D4A12E">${pend} pendência(s)</i><i style="--c:#46774E">${r.assets.length - crit - pend} normal</i></span><small>${r.alerts.length} alerta(s) roteados por papel · ${r.abas_ativas.length} módulos ativos</small></a>`; }).join('');
    data.execPortfolio = x.portfolio;
    const kpis = x.metrics.map((m) => `<article class="kpi" style="--k:${KPI[m.id][1]}" title="${e(m.definition)}"><span class="kpi-ic">${icon(KPI[m.id][0])}</span><div><div class="kpi-v">${m.value}</div><div class="kpi-l">${e(KPI_LABEL[m.id])}</div></div></article>`).join('');
    const queue = x.queue.filter((q) => { const sc = data.scenarios.find((c) => c.id === q.scenario); return !sc || cenarioDoSetor(sc); }).slice(0, 5).map((q) => {
      const aid = q.id.includes(':') ? q.id.split(':')[1] : q.id, a = assetById(aid), ic = a ? (ASSET_ICON[a.kind] || 'building') : 'dam';
      return `<button class="q-row" data-open-review="${e(q.finding_id || q.id)}"><span class="q-ic">${icon(ic)}</span><span class="q-txt"><strong>${e(q.name || q.asset_name)}</strong><small>${e(SC_NAME(q.scenario))}</small></span>${tag('priority', q.priority.level, q.priority.justification.join(' · '))}</button>`;
    }).join('');
    const ms = x.milestones.filter((m) => cenarioDoSetor({ regulator: (String(m.document).match(/(ANM|ANEEL|ANP|ANA|MTE|ANSN|CNEN)/) || [])[1] || '' })).slice(0, 4).map((m) => `<li><time>${fmtDate(m.date)}</time><span><strong>${e(m.document)}</strong><small>${e(m.provision)} · ${e(m.event)}</small></span></li>`).join('');
    return `
    <section class="hero">
      <div class="hero-txt"><div class="eyebrow">Visão executiva</div><h1>Panorama de Risco e Conformidade</h1><p>Mudanças normativas, alertas de ativos, documentos e manutenção em todos os setores da operação · data-base ${fmtDate(state.asOf)}.</p></div>
      <div class="hero-art" aria-hidden="true"></div>
    </section>
    <div class="kpis4">${kpis}</div>
    <div class="origem-dados" role="note"><b>Origem dos dados nesta tela:</b>
      <span class="lx-chip oficial">Normas e mudanças: textos oficiais (ANM, MTE, ANP, ANSN)</span>
      <span class="lx-chip mod">Indicadores, mudanças por ativo e fila: carteira de cenários fictícia</span>
      <span class="lx-chip mod">Operação da empresa: empresa fictícia de demonstração</span>
      <span class="lx-chip oficial">Radares, Transparência e Atlas: dados oficiais (SIGBM, SIGMINE, SNISB, ONS, ANEEL)</span></div>
    ${sectors ? `<section class="card mt16"><header class="card-h"><h3>${icon('layers', 'h-ic')}Operação da empresa · perfil ativo</h3><a class="link-arrow" href="#/ativos">Ativos & Mapa ${icon('arrow')}</a></header><div class="sec-ops">${sectors}</div><p class="hint">Empresa e ativos fictícios de demonstração. Troque o perfil no topo para ver outro setor na mesma plataforma.</p></section>` : ''}
    <div class="grid-exec">
      <section class="card">
        <header class="card-h"><h3>${icon('doc', 'h-ic')}Mudanças que exigem atenção</h3><a class="link-arrow" href="#/impact">Ver laboratório ${icon('arrow')}</a></header>
        <div class="change-feed">${changeFeed(x.portfolio)}</div>
      </section>
      <div class="stack">
        <section class="card"><header class="card-h"><h3>${icon('target', 'h-ic')}Fila prioritária</h3><a class="link-arrow" href="#/decision">Ver todas ${icon('arrow')}</a></header>
          <div class="q-list">${queue || empty('Nenhuma revisão aberta.')}</div></section>
        <section class="card"><header class="card-h"><h3>${icon('cal', 'h-ic')}Próximos marcos regulatórios</h3><a class="link-arrow" href="#/impact">Ver linha do tempo ${icon('arrow')}</a></header>
          ${ms ? `<ul class="timeline-list">${ms}</ul>` : empty('Nenhum marco nos próximos 12 meses.')}</section>
      </div>
    </div>
    <section class="insight"><span class="ins-ic">${icon('chart')}</span><strong>Insight da LexIA</strong><span class="ins-tag" title="${e(ins.note)}">${e(ins.generated_by)}</span>
      <p>${e(ins.text)}</p><button class="btn primary" data-open-scenario="${e(ins.scenario || state.scenario)}">Analisar mudança ${icon('arrow')}</button></section>`;
  },
  mount(root, ctx) {
    root.querySelectorAll('[data-emp]').forEach((a) => a.addEventListener('click', () => { state.atv = { ...(state.atv || {}), empresa: a.dataset.emp, aba: null, sel: null }; }));
    root.querySelectorAll('[data-open-scenario]').forEach(b=>b.addEventListener('click',()=>{state.scenario=b.dataset.openScenario;state.lab.sel=null;ctx.go('impact');}));
  },
};

// ======================= 2. ATLAS EMPRESARIAL =======================
let mapCtl = null, globeCtl = null, entityCache = { q: null, res: null };

function rows() {
  const A = state.atlas, q = norm(A.q);
  const off = A.showOfficial && data.official?.available ? data.official.records.map((r) => ({ ...r, origin: 'DADO_OFICIAL', kind: 'official' })) : [];
  const syn = A.showSynthetic ? data.assets.map((a) => { const f = finding(state.atlas.synScenario || 'nr20', a.id); return { id: a.id, official_id: a.id, name: a.name, owner_name: 'Cenário sintético', owner_cnpj: null, uf: a.region, municipio: '', lat: a.lat, lon: a.lon, operational_status: null, pnsb: null, cri: null, dpa: null, applicability: f?.axes.applicability_assessment, priority: f?.axes.priority.level, next_action: f?.axes.next_action, origin: 'CENARIO_HIPOTETICO', kind: 'synthetic' }; }) : [];
  return [...off, ...syn].filter((r) => (!q || norm(`${r.name} ${r.owner_name} ${r.owner_cnpj || ''} ${r.municipio} ${r.official_id}`).includes(q))
    && (!A.uf || r.uf === A.uf) && (!A.op || r.operational_status === A.op) && (!A.pnsb || r.pnsb === A.pnsb)
    && (!A.cri || r.cri === A.cri) && (!A.dpa || r.dpa === A.dpa) && (!A.applic || r.applicability === A.applic));
}
const colorOf = (r) => AXES.applic[r.applicability]?.[2] || '#5D7A94';
const points = (list) => list.map((r) => ({ id: r.id, lat: r.lat, lon: r.lon, uf: r.uf, kind: r.kind, color: colorOf(r), short: r.kind === 'synthetic' ? r.id : r.name, label: `${r.name} · ${r.owner_name}${r.kind === 'synthetic' ? ' (hipotético)' : ''}` }));

async function sidePanel() {
  const s = state.selection;
  if (!s) return `<div class="panel-empty"><h3>Selecione uma estrutura</h3><p class="muted">Clique no mapa ou na tabela. A ficha mostra a situação, por que foi selecionada, o que falta e as ações possíveis.</p></div>`;
  let head, situation, why, missing, actions, fid;
  if (s.kind === 'official') {
    const d = await api(`/api/official/sigbm/record?id=${encodeURIComponent(s.id)}&as_of=${state.asOf}`);
    const r = d.record, L = d.labels, ax = d.axes; fid = `anm:${r.id}`;
    head = `<div class="row between panel-origin"><span class="row gap"><span class="reference-icon database" aria-hidden="true">${icon('layers')}</span>${originTag('DADO_OFICIAL')}</span><span class="row gap muted sm">ID SIGBM ${e(r.official_id)}<button class="icon-btn copy-id" data-copy-id="${e(r.official_id)}" aria-label="Copiar ID SIGBM">${icon('copy')}</button></span></div><h3>${e(r.name)}</h3><p class="muted">${e(r.owner_name)} · CNPJ ${fmtCnpj(r.owner_cnpj)}<br>${e(r.municipio)}/${e(r.uf)}${r.mine_name ? ' · mina ' + e(r.mine_name) : ''}</p>`;
    const fields = ['operational_status', 'dam_type', 'pnsb', 'paebm_required', 'emergency_level', 'cri', 'dpa', 'dce_risr', 'dco', 'main_ore', 'managing_unit'];
    situation = `<div class="axes">${tag('lifecycle', ax.primary_lifecycle)}${tag('applic', ax.applicability_assessment)}${tag('workflow', ax.workflow_state)}${tag('priority', ax.priority.level, ax.priority.justification.join(' · '))}</div>
      <div class="next"><span class="reference-icon target" aria-hidden="true">${icon('target')}</span><div><span class="next-label">Próxima ação</span>${e(ax.next_action)}</div></div>
      <dl class="kv">${fields.slice(0,7).map((k) => `<dt title="${e(L[k] || k)}">${e(({cri:'Categoria de Risco (CRI)',dpa:'Dano Potencial Associado (DPA)'})[k] || L[k] || k)}</dt><dd>${e(r[k] ?? '— (não informado na fonte)')}</dd>`).join('')}</dl><details class="source-more"><summary>Campos adicionais da fonte</summary><dl class="kv">${fields.slice(7).map(k=>`<dt>${e(L[k] || k)}</dt><dd>${e(r[k] ?? 'Não informado')}</dd>`).join('')}</dl></details>
      <p class="hint">${e(d.categorical_note)} Dados como publicados pela ANM; a LexIA não avalia segurança nem estabilidade.</p>
      <p class="hint">Fonte: <a href="${e(d.snapshot.source_url)}" target="_blank" rel="noopener noreferrer">SIGBM/ANM ↗</a> · snapshot ${e(d.snapshot.snapshot_id)} · coletado ${fmtDateTime(d.snapshot.fetched_at)}</p>`;
    why = explainTable(d.explanation, d.finding);
    missing = d.finding.missing;
    var place = satView(r.lat, r.lon, { label: `${r.name} · ${r.municipio}/${r.uf} (coordenada oficial SIGBM)` });
  } else {
    const a = assetById(s.id), sc = state.atlas.synScenario || 'nr20';
    const c = await api(`/api/chain?asset=${a.id}&scenario=${sc}&as_of=${state.asOf}`);
    const ax = c.axes; fid = `${sc}:${a.id}`;
    head = `<div class="row between"><span>${originTag('CENARIO_HIPOTETICO')}</span><span class="muted sm">${e(a.id)}</span></div><h3>${e(a.name)}</h3><p class="muted">${e(a.sector)} · ${e(a.region)}<br>Norma em análise: ${e(SC_NAME(sc))}</p>`;
    situation = `<div class="axes">${tag('lifecycle', ax.primary_lifecycle)}${tag('applic', ax.applicability_assessment)}${tag('workflow', ax.workflow_state)}${tag('priority', ax.priority.level, ax.priority.justification.join(' · '))}</div><p class="next"><span>Próxima ação</span>${e(ax.next_action)}</p><p class="muted">${e(a.description)}</p>`;
    why = explainTable(c.explanation, c.finding);
    missing = c.finding.missing;
    var place = satView(a.lat, a.lon, { synthetic: true });
  }
  actions = `<div class="actions">
    <button class="btn primary" data-analyze="${e(fid)}">Analisar mudança</button>
    ${can('review.open') ? `<button class="btn" data-open-new-review="${e(fid)}">Abrir revisão</button>` : '<span class="hint">Entre como jurídico, operação ou engenharia para abrir revisão.</span>'}
    ${can('watch') ? (data.me.watchlist || []).includes(state.selection.id) ? `<button class="btn" data-watch="${e(state.selection.id)}" data-action="remove">${icon('star')} Na carteira · remover</button>` : `<button class="btn" data-watch="${e(state.selection.id)}" data-action="add">${icon('star')} Adicionar à carteira</button>` : ''}
    <a class="btn" href="/api/export/decision-pack?finding=${encodeURIComponent(fid)}&as_of=${state.asOf}" target="_blank" rel="noopener">Dossiê de decisão</a>
    <button class="btn ghost" data-ask>Perguntar sobre esta análise</button></div>`;
  return `<div class="panel">${head}
    <details open><summary>Local e imagem de satélite</summary>${place}</details>
    <details open><summary>Situação</summary>${situation}</details>
    <details><summary>Por que foi selecionado</summary>${why}</details>
    <details><summary>O que está faltando</summary><ul class="list">${missing.map((m) => `<li>${e(m)}</li>`).join('')}</ul></details>
    <details><summary>Ações possíveis</summary>${actions}</details></div>`;
}

export function explainTable(ex, f) {
  return `<table class="table compact"><thead><tr><th>Atributo</th><th>Operador</th><th>Valor</th><th>Resultado</th></tr></thead><tbody>${ex.map((x) => `<tr><td>${e(x.attribute)}</td><td><code>${e(x.operator)}</code></td><td>${e(x.value ?? '— ausente')}</td><td>${e({ MET: 'atendida', NOT_MET: 'não atendida', MISSING: 'dado ausente' }[x.result] || x.result)}</td></tr>`).join('')}</tbody></table>
    <p class="sm">Regra <code>${e(f.rule_id)}</code> · dispositivo ${e(ex[0]?.provision || '—')} · ${e(ex[0]?.version || '')} · data ${fmtDate(f.as_of)}</p>
    <p>${e(f.rationale)}</p>${f.temporal_note ? `<p class="warn-note">${e(f.temporal_note)}</p>` : ''}<p class="sm">Fontes: ${refs(f.source_ids)}</p>`;
}

export const atlas = {
  title: 'Atlas Empresarial', crumb: 'Estruturas oficiais e cenários no território',
  async render() {
    if (!data.official) await refreshOfficial();
    const O = data.official, A = state.atlas, list = rows();
    if (!list.some(r=>r.id===state.selection?.id)) {
      const initial=list.find(r=>r.id==='SIGBM-9149') || list[0];
      state.selection=initial ? {id:initial.id,kind:initial.kind==='official'?'official':'synthetic'} : null;
    }
    const uniq = (k) => [...new Set((O?.records || []).map((r) => r[k]).filter(Boolean))].sort();
    const per = 25, pages = Math.max(1, Math.ceil(list.length / per)); A.page = Math.min(A.page, pages - 1);
    const pageRows = list.slice(A.page * per, A.page * per + per);
    const sel = (bind, label, values, cur) => `<label class="field"><span>${label}</span><select data-atlas="${bind}"><option value="">Todos</option>${values.map((v) => `<option ${cur === v ? 'selected' : ''}>${e(v)}</option>`).join('')}</select></label>`;
    const ent = A.q.length >= 3 ? `<div id="entity-box" class="entity-box" aria-live="polite"></div>` : '';
    return `
    <div class="page-head"><div><h2>Atlas Empresarial</h2><p class="muted" title="${O?.available ? `${O.quality.rejected} linhas rejeitadas pela validação; consulte Fontes & Governança para a qualidade completa.` : ''}">${O?.available ? `${O.records.length} estruturas oficiais do SIGBM/ANM · snapshot de ${fmtDateTime(O.snapshot.fetched_at).replace(' ', ' às ')}` : 'Sem snapshot oficial disponível.'}</p></div>
    </div>
    <div class="filters atlas-filters">
      <h3 class="filter-title">${icon('filter')} Filtros de consulta</h3>
      <label class="field grow"><span>Buscar estrutura, empreendimento,<br>CNPJ, município ou ID</span><span class="input-search">${icon('search')}<input id="atlas-q" class="search" value="${e(A.q)}" placeholder="Ex.: Vale, 33.592.510/0001-54, Itabirito…" autocomplete="off"></span></label>
      ${sel('uf', 'UF', uniq('uf'), A.uf)}${sel('op', 'Situação operacional', uniq('operational_status'), A.op)}${sel('pnsb', 'Inserida na PNSB', uniq('pnsb'), A.pnsb)}
      ${sel('cri', 'CRI (categoria oficial)', ['Baixa', 'Média', 'Alta'], A.cri)}${sel('dpa', 'DPA (categoria oficial)', ['Baixa', 'Média', 'Alta'], A.dpa)}
      <label class="field"><span>Enquadramento LexIA</span><select data-atlas="applic"><option value="">Todos</option>${Object.entries(AXES.applic).map(([k, v]) => `<option value="${k}" ${A.applic === k ? 'selected' : ''}>${v[0]}</option>`).join('')}</select></label>
      ${A.showSynthetic ? `<label class="field"><span>Norma (camada hipotética)</span><select data-atlas="synScenario">${data.scenarios.map((x) => `<option value="${x.id}" ${(A.synScenario || 'nr20') === x.id ? 'selected' : ''}>${e(x.name)}</option>`).join('')}</select></label>` : ''}
      <fieldset class="layers"><legend>Camadas</legend><label><input type="checkbox" data-layer="showOfficial" ${A.showOfficial ? 'checked' : ''}> Dado oficial</label><label><input type="checkbox" data-layer="showSynthetic" ${A.showSynthetic ? 'checked' : ''}> Cenário hipotético</label></fieldset>
      ${A.q || A.uf || A.op || A.pnsb || A.cri || A.dpa || A.applic ? '<button class="btn ghost sm" id="atlas-clear">Limpar filtros</button>' : ''}
    </div>
    ${ent}
    <div class="grid-8-4">
      <section class="card flush atlas-map-card"><header class="card-h"><h3>${icon('pin', 'h-ic')}Mapa de estruturas e empreendimentos</h3><div class="seg" role="group" aria-label="Modo de visualização"><button data-view="map" class="${A.view === 'map' ? 'on' : ''}">Mapa</button><button data-view="globe" class="${A.view === 'globe' ? 'on' : ''}">Globo (opcional)</button></div></header><div id="atlas-map" class="map-frame"></div><div class="map-foot"><span>${list.length} estrutura(s) no filtro · cor = enquadramento LexIA (${Object.entries(AXES.applic).slice(0, 4).map(([, v]) => `<i style="color:${v[2]}">${v[1]}</i> ${v[0]}`).join(' · ')})</span><span>Natural Earth (domínio público) · coordenadas oficiais do SIGBM · pontos hipotéticos são ilustrativos</span></div></section>
      <aside class="card side" id="side-panel" aria-live="polite"><div class="loading">Carregando ficha…</div></aside>
    </div>
    ${card(`Tabela sincronizada <span class="muted">· ${list.length} resultado(s)</span>`, `<div class="table-wrap"><table class="table"><thead><tr><th>Origem</th><th>ID</th><th>Estrutura</th><th>Empreendedor</th><th>Local</th><th>Situação</th><th>PNSB</th><th>Enquadramento</th><th>Prioridade</th></tr></thead><tbody>
      ${pageRows.map((r) => `<tr class="${state.selection?.id === r.id ? 'sel' : ''}" tabindex="0" data-row="${e(r.id)}" data-kind="${r.kind}"><td>${originTag(r.origin)}</td><td><code>${e(r.official_id)}</code></td><td>${e(r.name)}</td><td>${e(r.owner_name)}</td><td>${e(r.municipio)}${r.municipio ? '/' : ''}${e(r.uf)}</td><td>${e(r.operational_status || '—')}</td><td>${e(r.pnsb || '—')}</td><td>${tag('applic', r.applicability)}</td><td>${tag('priority', r.priority)}</td></tr>`).join('') || `<tr><td colspan="9">${empty('Nenhuma estrutura com estes filtros.')}</td></tr>`}</tbody></table></div>
      <div class="pager"><button class="btn sm" data-page="-1" ${A.page === 0 ? 'disabled' : ''}>← Anterior</button><span>Página ${A.page + 1} de ${pages}</span><button class="btn sm" data-page="1" ${A.page >= pages - 1 ? 'disabled' : ''}>Próxima →</button></div>`)}`;
  },
  async mount(root, ctx) {
    const list = rows();
    const frame = root.querySelector('#atlas-map');
    const select = async (id, kind) => { state.selection = { id, kind: kind || (id.startsWith('SIGBM-') ? 'official' : 'synthetic') }; mapCtl?.update(points(rows()), id); root.querySelectorAll('[data-row]').forEach((tr) => tr.classList.toggle('sel', tr.dataset.row === id)); await fillPanel(root, ctx); };
    if (state.atlas.view === 'globe') {
      const { createGlobe } = await import('./globe.js');
      frame.classList.add('globe-frame'); frame.style.height = '600px';
      frame.innerHTML = '<canvas aria-label="Globo interativo com as mesmas estruturas. Clique em um ponto para ver a ficha." role="img"></canvas><div class="globe-hud"><span>Arraste para girar · role para aproximar · clique num ponto</span><div class="row gap"><button class="btn sm" data-g="br">Brasil</button><button class="btn sm" data-g="world">Mundo</button><button class="btn sm" data-g="spin">Girar</button></div></div><div class="globe-card" id="globe-card" hidden></div><div class="globe-tip" id="globe-tip" hidden></div>';
      const card = frame.querySelector('#globe-card'), tip = frame.querySelector('#globe-tip');
      const showCard = (id) => {
        const r = list.find((x) => x.id === id); if (!r) { card.hidden = true; return; }
        card.hidden = false;
        card.innerHTML = `<button class="icon-btn gc-x" aria-label="Fechar">×</button>${originTag(r.origin)}<h4>${e(r.name)}</h4><p>${e(r.owner_name)}${r.municipio ? ' · ' + e(r.municipio) + '/' + e(r.uf) : ''}</p>
          <div class="axes">${tag('applic', r.applicability)}${tag('priority', r.priority)}</div>${r.operational_status ? `<p class="sm">Situação: <b>${e(r.operational_status)}</b> · PNSB: <b>${e(r.pnsb || '—')}</b></p>` : ''}
          <p class="sm next-mini">${e(r.next_action || '')}</p><div class="row gap wrap"><button class="btn sm primary" data-gc="open">Ver ficha completa</button><button class="btn sm" data-analyze="${r.kind === 'official' ? 'anm:' + r.id : (state.atlas.synScenario || 'nr20') + ':' + r.id}">Analisar mudança</button></div>`;
        card.querySelector('.gc-x').onclick = () => { card.hidden = true; };
        card.querySelector('[data-gc="open"]').onclick = () => { root.querySelector('#side-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
      };
      globeCtl = createGlobe(frame.querySelector('canvas'), { world: data.world, points: points(list), labels: false, start: [-52, -15], zoom: 0.95, autoRotate: false, selected: () => state.selection?.id,
        onPick: (p) => { select(p.id); showCard(p.id); },
        onHover: (p, ev) => { if (!p) { tip.hidden = true; return; } const rc = frame.getBoundingClientRect(); tip.hidden = false; tip.style.left = `${ev.clientX - rc.left + 12}px`; tip.style.top = `${ev.clientY - rc.top + 12}px`; tip.textContent = p.label; } });
      frame.querySelector('[data-g="br"]').onclick = () => globeCtl.focus(-52, -15, 1.25);
      frame.querySelector('[data-g="world"]').onclick = () => globeCtl.focus(-30, 5, 0.8);
      frame.querySelector('[data-g="spin"]').onclick = () => globeCtl.setAuto(!globeCtl.isAuto());
      if (state.selection) showCard(state.selection.id);
      ctx.onLeave(() => globeCtl?.destroy());
    } else {
      mapCtl = createMap(frame, { points: points(list), selected: state.selection?.id, onSelect: (id) => select(id), height: 506 });
      const s = list.find((r) => r.id === state.selection?.id);
      const A = state.atlas, filtered = A.q || A.uf || A.op || A.pnsb || A.cri || A.dpa || A.applic;
      if (s && state.atlas.focus) { mapCtl.focus(s.lat, s.lon); state.atlas.focus = false; } else if (filtered && list.length && list.length < 900) mapCtl.fit(list);
    }
    await fillPanel(root, ctx);
    const q = root.querySelector('#atlas-q'); let t;
    q.addEventListener('input', () => { clearTimeout(t); t = setTimeout(async () => { state.atlas.q = q.value; state.atlas.page = 0; await ctx.rerender(); const n = document.querySelector('#atlas-q'); n.focus(); n.setSelectionRange(n.value.length, n.value.length); }, 300); });
    root.querySelectorAll('[data-atlas]').forEach((s) => s.addEventListener('change', () => { state.atlas[s.dataset.atlas] = s.value; state.atlas.page = 0; ctx.rerender(); }));
    root.querySelectorAll('[data-layer]').forEach((c) => c.addEventListener('change', () => { state.atlas[c.dataset.layer] = c.checked; ctx.rerender(); }));
    root.querySelector('#atlas-clear')?.addEventListener('click', () => { Object.assign(state.atlas, { q: '', uf: '', op: '', pnsb: '', cri: '', dpa: '', applic: '', page: 0 }); ctx.rerender(); });
    root.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => { state.atlas.view = b.dataset.view; ctx.rerender(); }));
    root.querySelectorAll('[data-page]').forEach((b) => b.addEventListener('click', () => { state.atlas.page += Number(b.dataset.page); ctx.rerender(); }));
    root.querySelectorAll('[data-row]').forEach((tr) => { const go = () => { state.atlas.focus = true; select(tr.dataset.row, tr.dataset.kind); mapCtl?.focus(...(() => { const r = list.find((x) => x.id === tr.dataset.row); return [r.lat, r.lon]; })()); }; tr.addEventListener('click', go); tr.addEventListener('keydown', (ev) => ev.key === 'Enter' && go()); });
    const box = root.querySelector('#entity-box');
    if (box) {
      if (entityCache.q !== state.atlas.q) entityCache = { q: state.atlas.q, res: await api(`/api/entities/search?q=${encodeURIComponent(state.atlas.q)}`) };
      const R = entityCache.res.results;
      box.innerHTML = R.length ? `<div class="row between"><strong>Organizações correspondentes no SIGBM</strong><span class="hint">${e(entityCache.res.note)}</span></div><div class="ents">${R.slice(0, 6).map((o) => `<div class="ent"><div><strong>${e(o.legal_name)}</strong><small>CNPJ ${fmtCnpj(o.cnpj)} · ${o.asset_count} estrutura(s)</small><small>${e(o.explanation)}</small></div><div class="ent-r"><span class="conf" title="Confiança do vínculo cadastral, não certeza jurídica">${Math.round(o.entity_match_confidence * 100)}%</span><span class="tag" style="--c:#FFB547">vínculo a confirmar</span>${o.cnpj ? `<button class="btn sm" data-ent-filter="${e(o.cnpj)}">Filtrar por CNPJ</button>` : ''}</div></div>`).join('')}</div>` : '';
      box.querySelectorAll('[data-ent-filter]').forEach((b) => b.addEventListener('click', () => { state.atlas.q = b.dataset.entFilter; state.atlas.page = 0; ctx.rerender(); }));
    }
  },
};

async function fillPanel(root, ctx) {
  const panel = root.querySelector('#side-panel');
  if (!panel) return;
  try { panel.innerHTML = await sidePanel(); } catch (err) { panel.innerHTML = `<p class="err">${e(err.message)}</p>`; return; }
  panel.querySelector('[data-copy-id]')?.addEventListener('click', async ev => {try {await navigator.clipboard.writeText(ev.currentTarget.dataset.copyId);toast('ID SIGBM copiado.');} catch {toast('Não foi possível copiar. O ID está visível na ficha.','err');}});
  panel.querySelector('[data-watch]')?.addEventListener('click', async (ev) => {
    const b = ev.currentTarget;
    try { await api('/api/watchlist', { asset_id: b.dataset.watch, action: b.dataset.action }); await refreshMe(); toast(b.dataset.action === 'add' ? 'Adicionado à carteira: entra nos indicadores da Visão Executiva.' : 'Removido da carteira.'); await fillPanel(root, ctx); } catch (err) { toast(err.message, 'err'); }
  });
  panel.querySelector('[data-open-new-review]')?.addEventListener('click', async (ev) => {
    try { await api('/api/reviews/open', { finding_id: ev.target.dataset.openNewReview, as_of: state.asOf }); await refreshReviews(); toast('Revisão aberta como rascunho. Siga em Decisão & Execução.'); await fillPanel(root, ctx); } catch (err) { toast(err.message, 'err'); }
  });
}
