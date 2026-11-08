// Radares por setor: fechamento de minas (mineração), usinas e outorgas (energia), barragens de abastecimento (saneamento).
// Mesmo método do radar de barragens: sinais de campos oficiais, consequência, nível de atenção; sinal não é acusação.
import { state, data, api, e, card, icon } from './core.js';
import { project } from './map.js';
import { satView } from './geoview.js';

const ATT = { 'Crítica': ['#C83037', 'crit'], 'Alta': ['#D9762D', 'alta'], 'Moderada': ['#D4A12E', 'mod'], 'Baixa': ['#63768A', 'baixa'] };
const CONF = {
  fechamento: { eyebrow: 'Mineração · ANM/SIGMINE + SIGBM', titulo: 'Fechamento e paralisação de minas',
    sub: 'Minas com plano de fechamento, suspensão, renúncia ou caducidade, e as barragens que ficam a até 5 km delas: o risco de “a mina fecha e a barragem fica”.',
    tipos: [['fechamento', 'Minas em fechamento']], unidade: 'título(s)' },
  outorgas: { eyebrow: 'Energia · ANEEL/SIGA + ANA/SNISB', titulo: 'Usinas, outorgas e barragens de usinas',
    sub: 'Outorgas vencidas ou vencendo, outorgas antigas sem obra, e barragens de usinas fiscalizadas pela ANEEL sem plano de segurança ou sem PAE.',
    tipos: [['outorgas', 'Outorgas de usinas'], ['barragens_usinas', 'Barragens de usinas (ANEEL)']], unidade: 'registro(s)' },
  radiologico: { eyebrow: 'Nuclear · ANM/SIGMINE + SIGBM · autoridade nuclear (ANSN/CNEN)', titulo: 'Instalações e locais radiológicos',
    sub: 'Títulos de lavra com urânio, tório ou radioatividade natural e barragens com minério de urânio — com os sinais de fechamento, paralisação e abandono que pedem atenção da proteção radiológica.',
    tipos: [['radiologico', 'Locais radiológicos (dados oficiais)']], unidade: 'local(is)' },
  abastecimento: { eyebrow: 'Saneamento · ANA/SNISB', titulo: 'Barragens de abastecimento humano',
    sub: 'Barragens que abastecem cidades: sem empreendedor, sem plano de segurança, sem inspeção, ou com dano potencial alto e sem plano de emergência.',
    tipos: [['abastecimento', 'Barragens de abastecimento']], unidade: 'barragem(ns)' },
};
const RS = (k) => (state['rs_' + k] = state['rs_' + k] || { tipo: CONF[k].tipos[0][0], nivel: '', uf: '', q: '', sel: null, page: 0 });

function mapa(pts, sel) {
  const ufs = data.states.features.map((f) => `<path class="rd-uf" d="${f.path}" fill="#E8E2CA"><title>${e(f.uf)}</title></path>`).join('');
  const lbl = data.states.features.map((f) => (f.cx ? `<text class="rd-lbl" x="${f.cx}" y="${+f.cy + 3}">${f.uf}</text>` : '')).join('');
  const order = { 'Baixa': -1, 'Moderada': 0, 'Alta': 1, 'Crítica': 2 };
  const P = [...pts].sort((a, b) => order[a.a] - order[b.a]).map((p) => { const [x, y] = project(p.lat, p.lon); const on = p.id === sel;
    return `<circle class="rd-pt ${on ? 'on' : ''}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${on ? 5 : p.a === 'Crítica' ? 3.6 : p.a === 'Alta' ? 3 : p.a === 'Baixa' ? 1.8 : 2.2}" fill="${ATT[p.a][0]}" data-rid="${e(p.id)}"/>`; }).join('');
  return `<svg viewBox="100 100 545 425" class="rd-svg" role="img" aria-label="Mapa do radar">${ufs}${lbl}<g>${P}</g></svg>`;
}

function ficha(x, k) {
  const near = x.barragens_proximas || [];
  return `<div class="atv-panel"><span class="eyebrow">${e(x.categoria || '')}</span><h3>${e(x.nome)}</h3>
    <p class="muted sm">${e(x.municipio || x.municipios || '')}${x.uf ? ' · ' + e(x.uf) : ''} · ${e(x.empresa)}</p>
    <span class="lx-chip ${ATT[x.atencao][1]}">Atenção ${e(x.atencao)} · ${x.pontos} ponto(s)</span>
    <h4>Sinais nos dados oficiais</h4><ul class="rs-sig">${x.sinais.map((s) => `<li><b>${e(s.label)}</b> <span class="lx-chip baixa">+${s.weight}</span><small>Campo <code>${e(s.evidence.field)}</code> = “${e(s.evidence.value)}” · ${e(s.evidence.source)}</small></li>`).join('')}</ul>
    <h4>Consequência</h4><ul class="ticks">${x.consequencia.map((c) => `<li>${e(c)}</li>`).join('')}</ul>
    ${near.length ? `<h4>Barragens do SIGBM a até 5 km</h4><table class="table compact"><tbody>${near.map((b) => `<tr><td>${e(b.nome)}</td><td>DPA ${e(b.dpa || '—')}</td><td>${e(b.situacao || '')}</td><td>${b.km} km</td></tr>`).join('')}</tbody></table>` : ''}
    <dl class="kv mt8">${[['Fase', x.fase], ['Fiscalizador', x.fiscalizador], ['Dano potencial', x.dpa], ['Categoria de risco', x.cri], ['Potência', x.potencia_mw != null ? x.potencia_mw.toLocaleString('pt-BR') + ' MW' : null],
      ['Fim da outorga', x.fim_vigencia], ['Capacidade', x.capacidade_hm3 != null ? x.capacidade_hm3 + ' hm³' : null], ['Última inspeção', x.ultima_inspecao], ['Último evento', x.evento]]
      .filter(([, v]) => v).map(([a, v]) => `<dt>${a}</dt><dd>${e(v)}</dd>`).join('')}</dl>
    ${x.lat != null ? satView(x.lat, x.lon, { zoom: 14, height: 170, label: 'Coordenada declarada na fonte oficial' }) : ''}
    <div class="row gap wrap mt8"><button class="btn sm" id="rs-close">${icon('arrow', 'flip')} Voltar à lista</button>${k !== 'outorgas' || x.id.startsWith('SNISB') ? `<a class="btn sm" href="#/denuncia?dam=${encodeURIComponent(x.id)}">${icon('doc')} Registrar denúncia</a>` : ''}</div></div>`;
}

function page(k) {
  return {
    async render() {
      const C = CONF[k], st = RS(k);
      const p = new URLSearchParams({ tipo: st.tipo, limit: 400 });
      if (st.nivel) p.set('nivel', st.nivel); if (st.uf) p.set('uf', st.uf); if (st.q) p.set('q', st.q);
      const D = await api('/api/radar-setor?' + p).catch((err) => ({ error: err.message }));
      if (D.error) return `<div class="empty"><p>${e(D.error)}</p></div>`;
      const sel = D.items.find((x) => x.id === st.sel);
      const per = 30, pages = Math.max(1, Math.ceil(D.items.length / per)); st.page = Math.min(st.page, pages - 1);
      const extra = k === 'fechamento' ? `<div class="kpi" style="--k:#C83037"><span class="kpi-ic">${icon('dam')}</span><div><div class="kpi-v">${D.barragens_afetadas}</div><div class="kpi-l">barragens a até 5 km dessas minas (${D.barragens_afetadas_dpa_alta} com dano potencial alto)</div></div></div>` : '';
      return `<header class="page-head"><div><span class="eyebrow">${e(C.eyebrow)} · regra ${e(D.rule_version)}</span><h2>${e(C.titulo)}</h2><p class="muted">${e(C.sub)}</p></div></header>
      ${C.tipos.length > 1 ? `<div class="seg mt8" role="group">${C.tipos.map(([t, l]) => `<button class="${st.tipo === t ? 'on' : ''}" data-rtipo="${t}">${e(l)}</button>`).join('')}</div>` : ''}
      <div class="kpis4 mt12">${['Crítica', 'Alta', 'Moderada'].map((n) => `<button class="kpi kpi-btn ${st.nivel === n ? 'on' : ''}" style="--k:${ATT[n][0]}" data-rnivel="${n}"><span class="kpi-ic">${icon('alert')}</span><span><span class="kpi-v">${D.niveis[n].toLocaleString('pt-BR')}</span><span class="kpi-l">atenção ${n.toLowerCase()}</span></span></button>`).join('')}
        ${extra || `<div class="kpi"><span class="kpi-ic">${icon('layers')}</span><div><div class="kpi-v">${D.total.toLocaleString('pt-BR')}</div><div class="kpi-l">${C.unidade} com algum sinal</div></div></div>`}</div>
      <details class="rs-crit mt12"><summary>${icon('book')} Como este radar decide (critérios ${e(D.rule_version)})</summary><ul>${D.criterios.map((c) => `<li>${e(c)}</li>`).join('')}</ul><p class="hint">Fonte: ${e(D.fonte)} · snapshot <code>${e(D.snapshot || '—')}</code>. Sinal é para alguém conferir, não é conclusão nem acusação.</p></details>
      <div class="row gap wrap mt12"><select id="rs-uf" aria-label="UF"><option value="">Todas as UFs</option>${data.states.features.map((f) => f.uf).sort().map((u) => `<option ${st.uf === u ? 'selected' : ''}>${u}</option>`).join('')}</select>
        <input class="search" id="rs-q" value="${e(st.q)}" placeholder="Nome, empresa ou município" style="max-width:300px">${st.nivel ? `<button class="link" data-rnivel="">limpar nível</button>` : ''}<span class="muted sm">${D.filtrados.toLocaleString('pt-BR')} resultado(s)</span></div>
      <div class="rd-grid mt12"><section class="card flush"><div class="rd-maph"><b>Mapa</b><div class="rd-legend">${['Crítica', 'Alta', 'Moderada', ...(k === 'radiologico' ? ['Baixa'] : [])].map((n) => `<span><i style="background:${ATT[n][0]}"></i>${n === 'Baixa' ? 'Baixa (monitorar)' : n}</span>`).join('')}</div></div>${mapa(D.pontos, st.sel)}</section>
        <section>${sel ? ficha(sel, k) : `<div class="rd-list card flush">${D.items.slice(st.page * per, st.page * per + per).map((x) => `<button class="rd-row" data-rid="${e(x.id)}"><span class="rd-bar" style="background:${ATT[x.atencao][0]}"></span><span class="rd-main"><strong>${e(x.nome)}</strong><small>${e(x.uf || '')}${x.municipio ? ' · ' + e(x.municipio) : ''} · ${e(x.empresa).slice(0, 70)}</small><small class="rd-sig">${x.sinais.map((s) => e(s.label)).join(' · ').slice(0, 160)}</small></span><span class="lx-chip ${ATT[x.atencao][1]}">${e(x.atencao)}</span></button>`).join('') || '<div class="empty"><p>Nada com esses filtros.</p></div>'}
          ${pages > 1 ? `<div class="pager"><button class="btn sm" data-rpg="-1" ${st.page ? '' : 'disabled'}>‹</button><span>${st.page + 1} / ${pages}</span><button class="btn sm" data-rpg="1" ${st.page < pages - 1 ? '' : 'disabled'}>›</button></div>` : ''}</div>`}</section></div>`;
    },
    mount(root, ctx) {
      const st = RS(k), re_ = () => { st.page = 0; st.sel = null; ctx.rerender(); };
      root.querySelectorAll('[data-rtipo]').forEach((b) => b.addEventListener('click', () => { st.tipo = b.dataset.rtipo; st.nivel = ''; re_(); }));
      root.querySelectorAll('[data-rnivel]').forEach((b) => b.addEventListener('click', () => { st.nivel = st.nivel === b.dataset.rnivel ? '' : b.dataset.rnivel; re_(); }));
      root.querySelector('#rs-uf')?.addEventListener('change', (ev) => { st.uf = ev.target.value; re_(); });
      let t; root.querySelector('#rs-q')?.addEventListener('input', (ev) => { clearTimeout(t); t = setTimeout(async () => { st.q = ev.target.value; st.page = 0; st.sel = null; await ctx.rerender(); const q = document.querySelector('#rs-q'); q?.focus(); q?.setSelectionRange(q.value.length, q.value.length); }, 350); });
      root.querySelectorAll('[data-rid]').forEach((b) => b.addEventListener('click', () => { st.sel = b.dataset.rid; ctx.rerender(); }));
      root.querySelector('#rs-close')?.addEventListener('click', () => { st.sel = null; ctx.rerender(); });
      root.querySelectorAll('[data-rpg]').forEach((b) => b.addEventListener('click', () => { st.page += +b.dataset.rpg; ctx.rerender(); }));
    },
  };
}
export const fechamentoPage = page('fechamento');
export const outorgasPage = page('outorgas');
export const abastecimentoPage = page('abastecimento');
export const radiologicoPage = page('radiologico');
