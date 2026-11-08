// Mapa do Brasil por UF (malha IBGE): coroplético pela quantidade de ativos + pontos + painel lateral clicável.
import { data, e, icon, TRIAGE, tag, originTag, ASSET_ICON } from './core.js';
import { project } from './map.js';

const VB = [100, 100, 545, 425];
const UF_NAME = { AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul', MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina', SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins' };
const SHADES = ['#EEF2F7', '#DCE9FB', '#B9D3F7', '#8CB6F0', '#5B95E6', '#28518A'];

/**
 * @param root elemento container
 * @param items ativos [{id,name,uf,lat,lon,state,organization,origin,priority,next_action,finding_id,region,kind,details}]
 * @param opts {stateOf(item)->estado, actions(item)->html}
 */
export function createBrMap(root, items, opts = {}) {
  const stateOf = opts.stateOf || ((a) => a.state);
  let filter = null, sel = null; // filter: estado de triagem; sel: {type:'uf'|'asset', id}
  const visible = () => items.filter((a) => stateOf(a) && (!filter || stateOf(a) === filter));
  root.innerHTML = `<div class="brm"><div class="brm-map"><svg viewBox="${VB.join(' ')}" role="img" aria-label="Mapa do Brasil por estado com ativos"></svg><div class="brm-tip" hidden></div>
      <div class="brm-scale"><span>Ativos por estado</span>${SHADES.slice(1).map((c) => `<i style="background:${c}"></i>`).join('')}<span>mais</span></div></div>
    <aside class="brm-panel" aria-live="polite"></aside></div>`;
  const svg = root.querySelector('svg'), tip = root.querySelector('.brm-tip'), panel = root.querySelector('.brm-panel');

  function draw() {
    const vis = visible();
    const byUf = {};
    vis.forEach((a) => { (byUf[a.uf] = byUf[a.uf] || []).push(a); });
    const max = Math.max(1, ...Object.values(byUf).map((l) => l.length));
    const shade = (n) => (n ? SHADES[Math.min(5, 1 + Math.floor((n / max) * 4.999))] : SHADES[0]);
    const many = vis.length > 40;
    const ufs = data.states.features.map((f) => {
      const n = (byUf[f.uf] || []).length, on = sel?.type === 'uf' && sel.id === f.uf;
      return `<path class="brm-uf ${on ? 'on' : ''} ${n ? 'has' : ''}" d="${f.path}" fill="${shade(n)}" data-uf="${f.uf}" tabindex="${n ? 0 : -1}" role="button" aria-label="${e(UF_NAME[f.uf])}: ${n} ativo(s)"/>`;
    }).join('');
    const labels = data.states.features.map((f) => {
      const n = (byUf[f.uf] || []).length;
      return n ? `<g class="brm-badge" data-uf="${f.uf}"><circle cx="${f.cx}" cy="${f.cy}" r="${n > 9 ? 9.5 : 8}"/><text x="${f.cx}" y="${f.cy + 3.2}">${n}</text><text class="brm-sig" x="${f.cx}" y="${f.cy - 11}">${f.uf}</text></g>` : `<text class="brm-sig dim" x="${f.cx}" y="${f.cy + 3}">${f.uf}</text>`;
    }).join('');
    const pts = many ? '' : vis.map((a) => { const [x, y] = project(a.lat, a.lon); const on = sel?.type === 'asset' && sel.id === a.id;
      return `<g class="brm-pt ${on ? 'on' : ''}" data-asset="${e(a.id)}" tabindex="0" role="button" aria-label="${e(a.name)}"><circle cx="${x}" cy="${y}" r="${on ? 6.5 : 4.8}" fill="${TRIAGE[stateOf(a)][1]}"/></g>`; }).join('');
    svg.innerHTML = ufs + labels + pts;
    renderPanel(vis, byUf, many);
  }

  function legend(vis) {
    const counts = Object.keys(TRIAGE).map((k) => [k, items.filter((a) => stateOf(a) === k).length]);
    return `<div class="lp-h">Resultado da triagem <span class="info-dot" title="Resultado do motor de regras para cada ativo. Clique para filtrar o mapa. Não é conclusão de conformidade.">i</span></div>
      <ul class="lp-list click">${counts.map(([k, n]) => `<li><button class="${filter === k ? 'on' : ''} ${n ? '' : 'zero'}" data-filter="${k}" ${n ? '' : 'disabled'}><i style="background:${TRIAGE[k][1]}"></i><span>${TRIAGE[k][0]}</span><b>${n}</b></button></li>`).join('')}</ul>
      ${filter ? `<button class="link" data-filter="">Mostrar todos os resultados</button>` : `<p class="hint">Clique num estado, num ponto ou num resultado.</p>`}`;
  }
  const row = (a) => `<button class="brm-item" data-asset="${e(a.id)}"><span class="brm-ic">${icon(ASSET_ICON[a.kind] || 'building')}</span><span class="brm-it"><strong>${e(a.name)}</strong><small>${e(a.organization)} · ${e(a.region)}</small></span><i class="brm-dot" style="background:${TRIAGE[stateOf(a)][1]}" title="${e(TRIAGE[stateOf(a)][0])}"></i></button>`;

  function renderPanel(vis, byUf, many) {
    if (sel?.type === 'asset') {
      const a = items.find((x) => x.id === sel.id);
      if (!a) { sel = null; return renderPanel(vis, byUf, many); }
      const st = stateOf(a);
      panel.innerHTML = `<button class="link back" data-back>${icon('arrow', 'flip')} Voltar</button>
        <div class="brm-head"><span class="brm-ic lg">${icon(ASSET_ICON[a.kind] || 'building')}</span><div><h4>${e(a.name)}</h4><small>${e(a.organization)}</small></div></div>
        <div class="axes">${originTag(a.origin)}<span class="tag" style="--c:${TRIAGE[st][1]}"><i>●</i>${e(TRIAGE[st][0])}</span>${a.priority ? tag('priority', a.priority.level, a.priority.justification.join(' · ')) : ''}</div>
        <dl class="kv"><dt>Local</dt><dd>${e(a.region)}</dd>${Object.entries(a.details || {}).filter(([, v]) => v).slice(0, 4).map(([k, v]) => `<dt>${e(k)}</dt><dd>${e(v)}</dd>`).join('')}</dl>
        <p class="next"><span>Próxima ação</span>${e(a.next_action || a.headline)}</p>
        <div class="actions">${opts.actions ? opts.actions(a) : ''}</div>`;
    } else if (sel?.type === 'uf') {
      const list = byUf[sel.id] || [];
      panel.innerHTML = `<button class="link back" data-back>${icon('arrow', 'flip')} Voltar à legenda</button><h4 class="mt8">${e(UF_NAME[sel.id])} <span class="muted">· ${list.length} ativo(s)</span></h4>
        <div class="brm-list">${list.map(row).join('') || '<p class="muted">Nenhum ativo neste estado com o filtro atual.</p>'}</div>`;
    } else {
      const top = Object.entries(byUf).sort((a, b) => b[1].length - a[1].length).slice(0, 4);
      panel.innerHTML = `<div class="brm-sum"><b>${vis.length}</b> ativo(s) em <b>${Object.keys(byUf).length}</b> estado(s)${many ? '<small>Muitos pontos: mostrando a concentração por estado.</small>' : ''}</div>${legend(vis)}
        ${top.length ? `<div class="brm-top"><span>Maior concentração</span>${top.map(([uf, l]) => `<button class="chip-btn" data-uf="${uf}">${uf} · ${l.length}</button>`).join('')}</div>` : ''}`;
    }
  }

  function showTip(ev, html) { const r = root.querySelector('.brm-map').getBoundingClientRect(); tip.hidden = false; tip.innerHTML = html; tip.style.left = `${Math.min(ev.clientX - r.left + 14, r.width - 220)}px`; tip.style.top = `${ev.clientY - r.top + 14}px`; }
  root.addEventListener('mousemove', (ev) => {
    const p = ev.target.closest('[data-asset]'), u = ev.target.closest('[data-uf]');
    if (p && p.closest('svg')) { const a = items.find((x) => x.id === p.dataset.asset); showTip(ev, `<b>${e(a.name)}</b><br>${e(a.organization)}<br>${e(TRIAGE[stateOf(a)][0])}`); }
    else if (u && u.closest('svg')) { const l = visible().filter((a) => a.uf === u.dataset.uf); showTip(ev, `<b>${e(UF_NAME[u.dataset.uf])}</b><br>${l.length} ativo(s)${l.length ? '<br>' + Object.keys(TRIAGE).map((k) => [k, l.filter((a) => stateOf(a) === k).length]).filter(([, n]) => n).map(([k, n]) => `${n} ${TRIAGE[k][0].toLowerCase()}`).join(' · ') : ''}`); }
    else tip.hidden = true;
  });
  root.addEventListener('mouseleave', () => { tip.hidden = true; });
  root.addEventListener('click', (ev) => {
    const f = ev.target.closest('[data-filter]'); if (f) { filter = f.dataset.filter || null; sel = null; draw(); return; }
    if (ev.target.closest('[data-back]')) { sel = sel?.type === 'asset' && sel.from ? { type: 'uf', id: sel.from } : null; draw(); return; }
    const a = ev.target.closest('[data-asset]'); if (a) { const it = items.find((x) => x.id === a.dataset.asset); sel = { type: 'asset', id: a.dataset.asset, from: sel?.type === 'uf' ? sel.id : it?.uf }; draw(); return; }
    const u = ev.target.closest('[data-uf]'); if (u && (visible().some((x) => x.uf === u.dataset.uf))) { sel = { type: 'uf', id: u.dataset.uf }; draw(); }
  });
  root.addEventListener('keydown', (ev) => { if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.closest('svg')) { ev.preventDefault(); ev.target.dispatchEvent(new MouseEvent('click', { bubbles: true })); } });
  draw();
  return { select(id) { sel = { type: 'asset', id }; draw(); } };
}
