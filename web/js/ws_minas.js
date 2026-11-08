// Minas & substâncias (ANM/SIGMINE): além das barragens — tipo de mineração, substância e sinal radiológico (CNEN/ANSN).
import { state, data, api, e, card, icon } from './core.js';
import { project } from './map.js';
import { satView } from './geoview.js';

const CAT = { nuclear: ['Nuclear', '#DB2777'], norm: ['Radioatividade natural', '#68487A'], metalico: ['Metálico', '#B45309'], construcao: ['Construção civil', '#63768A'],
  agua: ['Água mineral', '#0EA5E9'], industrial: ['Mineral industrial', '#46774E'], gemas: ['Gemas e diamante', '#14B8A6'], energetico: ['Energético', '#111827'], outros: ['Outros', '#94A3B8'] };
const MS = () => (state.min = state.min || { cat: '', uf: '', rad: true, q: '', sel: null, page: 0 });

export const minasPage = {
  async render() {
    const st = MS();
    const p = new URLSearchParams({ limit: 3000 });
    if (st.cat) p.set('cat', st.cat); if (st.uf) p.set('uf', st.uf); if (st.rad) p.set('rad', '1'); if (st.q) p.set('q', st.q);
    const D = await api('/api/minas?' + p);
    const sel = D.items.find((m) => m.id === st.sel);
    const per = 40, pages = Math.max(1, Math.ceil(D.items.length / per)); st.page = Math.min(st.page, pages - 1);
    const ufs = data.states.features.map((f) => `<path class="rd-uf" d="${f.path}" fill="#E8E2CA"><title>${e(f.uf)}</title></path>`).join('');
    const pts = D.items.map((m) => { const [x, y] = project(m.lat, m.lon); return `<circle class="rd-pt ${st.sel === m.id ? 'on' : ''}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${m.radiologico ? 3.4 : 2}" fill="${CAT[m.categoria][1]}" data-mid="${e(m.id)}"><title>${e(m.substancia)} · ${e(m.uf)} · ${e(m.fase)}</title></circle>`; }).join('');
    const regs = (m) => ['ANM (título, Relatório Anual de Lavra, CFEM)', 'Órgão ambiental (licença)', 'MTE (NR-22)', ...(m.categoria === 'agua' ? ['Vigilância sanitária (água mineral)'] : []), ...(m.radiologico ? ['CNEN/ANSN (autoridade nuclear)'] : [])];
    return `<header class="page-head"><div><span class="eyebrow">Além das barragens · ANM/SIGMINE</span><h2>Minas & substâncias</h2><p class="muted">${D.total.toLocaleString('pt-BR')} minas com título de lavra no país, por tipo de mineração e substância. Locais com material nuclear ou radioatividade natural chamam também a autoridade nuclear.</p></div></header>
    <div class="min-cats">${D.by_cat.map(([l, n]) => { const k = Object.keys(CAT).find((c) => CAT[c][0] === l || (c === 'norm' && l.startsWith('Radioatividade')) || (c === 'energetico' && l.startsWith('Energético'))) || 'outros';
      return `<button class="min-cat ${st.cat === k ? 'on' : ''}" data-cat="${k}" style="--c:${CAT[k][1]}"><b>${n.toLocaleString('pt-BR')}</b><span>${e(l)}</span></button>`; }).join('')}</div>
    <div class="row gap wrap mt12"><label class="chip-btn ${st.rad ? 'on' : ''}" style="--c:#DB2777"><input type="checkbox" id="mn-rad" ${st.rad ? 'checked' : ''}> ☢ só nuclear / radioatividade natural (${D.radiologico})</label>
      <select id="mn-uf" aria-label="UF"><option value="">Todas as UFs</option>${data.states.features.map((f) => f.uf).sort().map((u) => `<option ${st.uf === u ? 'selected' : ''}>${u}</option>`).join('')}</select>
      <input class="search" id="mn-q" value="${e(st.q)}" placeholder="Substância, processo ou titular" style="max-width:300px">${st.cat ? `<button class="link" data-cat="">limpar tipo</button>` : ''}<span class="muted sm">${D.filtered.toLocaleString('pt-BR')} mina(s)</span></div>
    <div class="rd-grid mt12"><section class="card flush"><div class="rd-maph"><b>Mapa</b><div class="rd-legend">${Object.values(CAT).map(([l, c]) => `<span><i style="background:${c}"></i>${e(l)}</span>`).join('')}</div></div><svg viewBox="100 100 545 425" class="rd-svg" role="img" aria-label="Mapa das minas">${ufs}<g>${pts}</g></svg></section>
      <section>${sel ? card(e(sel.substancia), `<span class="tag" style="--c:${CAT[sel.categoria][1]}">${e(sel.categoria_label)}</span>
          ${sel.categoria === 'nuclear' ? `<p class="warn-note">☢ ${e(D.regras.nuclear)}</p>` : sel.categoria === 'norm' ? `<p class="warn-note">☢ ${e(D.regras.norm)}</p>` : ''}
          <dl class="kv"><dt>Processo ANM</dt><dd><code>${e(sel.processo)}</code></dd><dt>Fase</dt><dd>${e(sel.fase)}</dd><dt>Uso</dt><dd>${e(sel.uso || '—')}</dd><dt>Área</dt><dd>${Number(sel.area_ha || 0).toLocaleString('pt-BR')} ha</dd>
            <dt>Titular</dt><dd>${e(sel.titular)}</dd><dt>UF</dt><dd>${e(sel.uf)}</dd><dt>Último evento</dt><dd><small>${e(sel.ultimo_evento)}</small></dd></dl>
          <h4>Quem regula (típico do tipo de atividade)</h4><ul class="ticks">${regs(sel).map((r) => `<li>${e(r)}</li>`).join('')}</ul><p class="hint">${e(D.regras.todas)} Confirmar aplicabilidade caso a caso.</p>
          ${satView(sel.lat, sel.lon, { zoom: 14, height: 180, area: true, label: 'Centro aproximado da área do processo (ANM)' })}
          <button class="btn sm mt8" id="mn-close">${icon('arrow', 'flip')} Voltar à lista</button>`, { icon: 'mine' })
        : `<div class="rd-list card flush">${D.items.slice(st.page * per, st.page * per + per).map((m) => `<button class="rd-row" data-mid="${e(m.id)}"><span class="rd-bar" style="background:${CAT[m.categoria][1]}"></span><span class="rd-main"><strong>${e(m.substancia)}</strong><small>${e(m.uf)} · ${e(m.fase)} · ${e(m.titular)}</small></span>${m.radiologico ? '<span class="tag" style="--c:#DB2777">☢</span>' : ''}</button>`).join('') || '<div class="empty"><p>Nenhuma mina com esses filtros.</p></div>'}
          ${pages > 1 ? `<div class="pager"><button class="btn sm" data-pg="-1" ${st.page ? '' : 'disabled'}>‹</button><span>${st.page + 1} / ${pages}</span><button class="btn sm" data-pg="1" ${st.page < pages - 1 ? '' : 'disabled'}>›</button></div>` : ''}</div>`}</section></div>
    <p class="hint">Fonte: ANM/SIGMINE (serviço público), snapshot <code>${e(D.manifest?.snapshot_id || '—')}</code>. Só o centro aproximado da área é guardado; nome de pessoa física não é exibido.</p>`;
  },
  mount(root, ctx) {
    const st = MS();
    root.querySelectorAll('[data-cat]').forEach((b) => b.addEventListener('click', () => { st.cat = st.cat === b.dataset.cat ? '' : b.dataset.cat; if (st.cat && !['nuclear', 'norm'].includes(st.cat)) st.rad = false; st.page = 0; st.sel = null; ctx.rerender(); }));
    root.querySelector('#mn-rad')?.addEventListener('change', (ev) => { st.rad = ev.target.checked; st.page = 0; st.sel = null; ctx.rerender(); });
    root.querySelector('#mn-uf')?.addEventListener('change', (ev) => { st.uf = ev.target.value; st.page = 0; st.sel = null; ctx.rerender(); });
    let t; root.querySelector('#mn-q')?.addEventListener('input', (ev) => { clearTimeout(t); t = setTimeout(async () => { st.q = ev.target.value; st.page = 0; await ctx.rerender(); const q = document.querySelector('#mn-q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }, 350); });
    root.querySelectorAll('[data-mid]').forEach((b) => b.addEventListener('click', () => { st.sel = b.dataset.mid; ctx.rerender(); }));
    root.querySelector('#mn-close')?.addEventListener('click', () => { st.sel = null; ctx.rerender(); });
    root.querySelectorAll('[data-pg]').forEach((b) => b.addEventListener('click', () => { st.page += +b.dataset.pg; ctx.rerender(); }));
  },
};
