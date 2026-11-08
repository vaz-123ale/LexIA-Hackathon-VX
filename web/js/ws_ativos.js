import { assetSymbol as shape } from './asset_symbols.js';
// Ativos & Mapa — plataforma multissetorial: a mesma tela atende mineração, energia e saneamento só com configuração.
import { state, data, api, e, fmtDate, card, toast, icon } from './core.js';
import { project } from './map.js';
import { satView } from './geoview.js';

const ST = { critico: ['Crítico', '#C83037'], pendencia: ['Pendência', '#D4A12E'], normal: ['Normal', '#46774E'] };
const LV = { 'Crítico': '#C83037', 'Alto': '#F97316', 'Médio': '#EAB308', 'Baixo': '#63768A' };
const AS = () => (state.atv = state.atv || { empresa: null, aba: null, sel: null });
const VB = [100, 100, 545, 425];

const glyph = (sym, color) => `<svg viewBox="-16 -16 32 32" class="glyph">${shape(sym, 0, 0, 12, color)}</svg>`;

const UFC = {};
function ufCenter(f) {
  if (UFC[f.uf]) return UFC[f.uf];
  const nums = f.path.match(/-?\d+(\.\d+)?/g).map(Number); let sx = 0, sy = 0, k = 0;
  for (let i = 0; i + 1 < nums.length; i += 2) { sx += nums[i]; sy += nums[i + 1]; k++; }
  return (UFC[f.uf] = [sx / k, sy / k]);
}
// pontos: [{id, lat, lon, simbolo, cor, nome, sub}]
export function regionMap(points, sel, { label = true, aria = 'Mapa dos ativos' } = {}) {
  const P = points.filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon)).map((p) => ({ ...p, xy: project(p.lat, p.lon) }));
  if (!P.length) return '<div class="empty"><p>Sem coordenadas para mostrar.</p></div>';
  let [x0, y0, x1, y1] = [Math.min(...P.map((p) => p.xy[0])), Math.min(...P.map((p) => p.xy[1])), Math.max(...P.map((p) => p.xy[0])), Math.max(...P.map((p) => p.xy[1]))];
  let w = Math.max((x1 - x0) * 1.5, 90), h = Math.max((y1 - y0) * 1.5, 62);   // zoom mínimo: sempre mostra o entorno (estados vizinhos)
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2; if (w / h > 1.45) h = w / 1.45; else w = h * 1.45;
  const vb = [cx - w * .60, cy - h * .54, w * 1.22, h * 1.12], r = w / 58, fs = w / 72;
  // ativos no mesmo lugar: espalha em círculo para todos ficarem visíveis e clicáveis
  const groups = [];
  for (const p of P) { const g = groups.find((q) => Math.hypot(q.x - p.xy[0], q.y - p.xy[1]) < r * 1.6); if (g) g.items.push(p); else groups.push({ x: p.xy[0], y: p.xy[1], items: [p] }); }
  for (const g of groups) if (g.items.length > 1) g.items.forEach((p, i) => { const a = (2 * Math.PI * i) / g.items.length - Math.PI / 2; p.xy = [g.x + Math.cos(a) * r * 2.1, g.y + Math.sin(a) * r * 2.1]; });
  // rótulos: à direita do ponto; se colidir com outro rótulo, desce e ganha linha-guia
  const placed = [];
  for (const p of [...P].sort((a, b) => a.xy[1] - b.xy[1])) {
    let ly = p.xy[1] + fs * 0.35; const lx = Math.min(p.xy[0] + r * 2, vb[0] + vb[2] - fs * 19);
    while (placed.some((q) => Math.abs(q.y - ly) < fs * 2.1 && Math.abs(q.x - lx) < w * 0.28)) ly += fs * 2.2;
    placed.push({ x: lx, y: ly }); p.lbl = [lx, ly];
  }
  const ufs = data.states.features.map((f) => `<path class="rd-uf" d="${f.path}" fill="#E8E2CA" stroke="#FFFDF5" stroke-width="1.2" vector-effect="non-scaling-stroke"/>`).join('');
  const ufl = data.states.features.map((f) => { const [ux, uy] = ufCenter(f); return ux > vb[0] && ux < vb[0] + w && uy > vb[1] && uy < vb[1] + h ? `<text x="${ux.toFixed(1)}" y="${uy.toFixed(1)}" class="atv-ufl" font-size="${(fs * 1.5).toFixed(2)}">${e(f.uf)}</text>` : ''; }).join('');
  const halo = groups.filter((g) => g.items.length > 1).map((g) => `<circle cx="${g.x}" cy="${g.y}" r="${(r * 3.3).toFixed(2)}" class="atv-halo"/>`).join('');
  const pts = P.map((p) => { const [x, y] = p.xy, on = sel === p.id, [lx, ly] = p.lbl, moved = Math.abs(ly - (y + fs * 0.35)) > fs * 0.5;
    return `<g class="atv-pt ${on ? 'on' : ''}" data-aid="${e(p.id)}" role="button" tabindex="0" aria-label="${e(p.nome)}">${label && moved ? `<path d="M${(x + r).toFixed(2)},${y.toFixed(2)} L${(lx - fs * 0.3).toFixed(2)},${(ly - fs * 0.35).toFixed(2)}" class="atv-lead" vector-effect="non-scaling-stroke"/>` : ''}${shape(p.simbolo, x, y, on ? r * 1.35 : r, p.cor)}
      ${label ? `<text x="${lx.toFixed(2)}" y="${ly.toFixed(2)}" class="atv-lbl" font-size="${fs.toFixed(2)}">${e(p.nome.length > 30 ? p.nome.slice(0, 29) + '…' : p.nome)}</text>` : ''}<title>${e(p.nome)}${p.sub ? ' · ' + e(p.sub) : ''}</title></g>`; }).join('');
  const km = Math.round((w / (data.map.width || 690)) * 4300 / 5 / 10) * 10 || 10;
  return `<svg viewBox="${vb.map((v) => v.toFixed(2)).join(' ')}" class="rd-svg atv-svg" role="img" aria-label="${e(aria)}"><defs><linearGradient id="atv-sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#D6E7F2"/><stop offset="1" stop-color="#B7D2E6"/></linearGradient></defs><rect x="${vb[0]}" y="${vb[1]}" width="${vb[2]}" height="${vb[3]}" fill="url(#atv-sea)"/>${ufs}${ufl}${halo}${pts}</svg>
    <div class="atv-scale">Região ampliada nos ativos · ${P.length} ponto(s)${groups.some((g) => g.items.length > 1) ? ' · ativos no mesmo local aparecem lado a lado dentro do círculo' : ''}</div>`;
}
function map(R, sel) {
  return regionMap(R.assets.map((a) => ({ id: a.id, lat: a.lat, lon: a.lon, simbolo: a.simbolo, cor: ST[a.status][1], nome: a.nome, sub: `${a.tipo_rotulo} · ${ST[a.status][0]}` })), sel, { aria: 'Mapa dos ativos da empresa' });
}

function spark(vals, lim, crit, color) {
  const W = 220, H = 46, mn = Math.min(...vals, lim ?? Infinity, crit ?? Infinity), mx = Math.max(...vals, lim ?? -Infinity, crit ?? -Infinity);
  const Y = (v) => H - 4 - ((v - mn) / (mx - mn || 1)) * (H - 8), X = (i) => (i / (vals.length - 1)) * W;
  const line = (v, c) => (v == null ? '' : `<line x1="0" x2="${W}" y1="${Y(v)}" y2="${Y(v)}" stroke="${c}" stroke-dasharray="3 3"/>`);
  return `<svg viewBox="0 0 ${W} ${H}" class="atv-spark">${line(lim, '#D4A12E')}${line(crit, '#C83037')}<path d="${vals.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join('')}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
}

function assetPanel(a, R) {
  const al = R.alerts.filter((x) => x.asset_id === a.id);
  return `<div class="atv-panel"><div class="row between wrap"><div><span class="eyebrow">${e(a.tipo_rotulo)}${a.radiologico ? ' · material radioativo' : ''}</span><h3>${e(a.nome)}</h3><p class="muted sm">${e(a.municipio || '')}${a.substancia ? ' · ' + e(a.substancia) : ''} · coordenada ilustrativa</p></div><span class="tag" style="--c:${ST[a.status][1]}">${ST[a.status][0]}</span></div>
    ${a.radiologico ? '<p class="warn-note">☢ Ativo com material radioativo: além da ANM, entram a autoridade nuclear (CNEN/ANSN, Lei 14.222/2021) e a proteção radiológica (norma CNEN NN 4.01).</p>' : ''}
    <h4>Documentos e licenças</h4><table class="table compact"><tbody>${a.documentos.map((d) => `<tr><td>${e(d.nome)}<br><small class="muted">${e(d.base)}</small></td><td>${d.vence ? fmtDate(d.vence) : '—'}</td><td><span class="tag" style="--c:${d.nivel ? LV[d.nivel] : '#46774E'}">${e(d.status)}</span></td></tr>`).join('')}</tbody></table>
    ${a.indicadores.length ? `<h4>Indicadores (leituras sintéticas)</h4><div class="atv-inds">${a.indicadores.map((i) => `<div><b>${e(i.nome)}</b><span>${e(i.atual)} ${e(i.unidade)}${i.z != null ? ` · z ${i.z}` : ''}</span>${spark(i.serie, i.limite_alerta, i.limite_critico, i.nivel ? LV[i.nivel] : '#1570EF')}${i.motivo ? `<small class="err">${e(i.motivo)}</small>` : '<small class="muted">dentro do padrão</small>'}</div>`).join('')}</div>` : ''}
    <h4>Alertas e quem recebe</h4>${al.map((x) => `<div class="atv-al"><span class="tag" style="--c:${LV[x.level]}">${e(x.level)}</span> <b>${e(x.title)}</b><small>→ ${x.recipients.map((r) => r.sem_pessoa ? `<s title="papel sem pessoa cadastrada">${e(r.rotulo)}</s>` : e(r.rotulo)).join(', ')} · ${e(x.action)}</small></div>`).join('') || '<p class="muted sm">Sem alertas.</p>'}
    <h4>Reguladores do setor</h4><p class="sm">${a.reguladores.map(e).join(' · ')}</p>
    ${satView(a.lat, a.lon, { synthetic: true })}
    <div class="row gap wrap mt8"><a class="btn sm" href="#/compliance">${icon('shield')} Tratar em Compliance</a><a class="btn sm" href="#/denuncia?dam=${encodeURIComponent('ATIVO:' + R.empresa.id + ':' + a.id)}">${icon('doc')} Registrar denúncia sobre este ativo</a></div></div>`;
}

const ATT = { 'Crítica': '#C83037', 'Alta': '#D9762D', 'Moderada': '#D4A12E', 'Baixa': '#63768A', 'Sem sinal': '#9EA8AE' };
async function realView(st) {
  const T = await api('/api/transparencia');
  const opts = T.empresas.filter((o) => o.barragens >= 3).slice(0, 30);
  if (!st.real || !opts.some((o) => o.cnpj_root === st.real)) st.real = opts[0]?.cnpj_root;
  const D = await api('/api/empresa-publica?root=' + st.real);
  const sel = D.barragens.find((b) => b.id === st.sel) || D.minas.find((m) => m.id === st.sel);
  const cnt = (a) => D.barragens.filter((b) => b.atencao === a).length;
  const pts = [...D.barragens.map((b) => ({ id: b.id, lat: b.lat, lon: b.lon, simbolo: 'triangulo', cor: ATT[b.atencao] || '#9EA8AE', nome: b.nome, sub: `Barragem · ${b.atencao}` })),
    ...D.minas.map((m) => ({ id: m.id, lat: m.lat, lon: m.lon, simbolo: m.radiologico ? 'radiacao' : 'quadrado', cor: '#28518A', nome: `Lavra · ${m.substancia}`, sub: m.fase }))];
  const panel = !sel ? '' : sel.processo ? `<div class="atv-panel"><span class="eyebrow">Título de lavra · ANM/SIGMINE</span><h3>${e(sel.substancia)}</h3><dl class="kv"><dt>Processo</dt><dd><code>${e(sel.processo)}</code></dd><dt>Tipo</dt><dd>${e(sel.categoria_label)}</dd><dt>Fase</dt><dd>${e(sel.fase)}</dd><dt>Área</dt><dd>${Number(sel.area_ha || 0).toLocaleString('pt-BR')} ha</dd><dt>UF</dt><dd>${e(sel.uf)}</dd></dl>${sel.radiologico ? '<p class="warn-note">☢ Substância com radioatividade natural ou nuclear: entra também a autoridade nuclear (CNEN/ANSN).</p>' : ''}${satView(sel.lat, sel.lon, { zoom: 14, height: 170, area: true, label: 'Centro aproximado da área (ANM)' })}<button class="btn sm mt8" id="atv-close">Voltar</button></div>`
    : `<div class="atv-panel"><span class="eyebrow">Barragem · ANM/SIGBM (dado oficial)</span><h3>${e(sel.nome)}</h3><p class="muted sm">${e(sel.municipio)}/${e(sel.uf)}${sel.mina ? ' · mina ' + e(sel.mina) : ''}</p>
      <span class="lx-chip ${{ 'Crítica': 'crit', 'Alta': 'alta', 'Moderada': 'mod', 'Baixa': 'baixa' }[sel.atencao] || 'baixa'}">Atenção ${e(sel.atencao)}</span>
      <dl class="kv mt8"><dt>Minério</dt><dd>${e(sel.minerio || '—')}</dd><dt>Tipo</dt><dd>${e(sel.tipo || '—')}</dd><dt>Situação</dt><dd>${e(sel.situacao || '—')}</dd><dt>Dano potencial</dt><dd>${e(sel.dpa || '—')}</dd><dt>Categoria de risco</dt><dd>${e(sel.cri || '—')}</dd><dt>Emergência</dt><dd>${e(sel.emergencia || '—')}</dd><dt>Declaração de estabilidade</dt><dd>${e(sel.dce || '—')}</dd></dl>
      ${sel.sinais.length ? `<h4>Por que a atenção</h4><ul class="ticks">${sel.sinais.map((x) => `<li>${e(x)}</li>`).join('')}</ul>` : '<p class="muted sm">Nenhum sinal nos campos públicos.</p>'}
      ${satView(sel.lat, sel.lon, { zoom: 15, height: 170, label: 'Coordenada declarada no SIGBM' })}<div class="row gap wrap mt8"><button class="btn sm" id="atv-close">Voltar</button><a class="btn sm" href="#/radar">Abrir no radar de barragens</a></div></div>`;
  return `<div class="row gap wrap mt12 atv-real-h"><label class="field" style="min-width:320px;margin:0"><span>Empresa real (pessoa jurídica, dados públicos)</span><select id="atv-real">${opts.map((o) => `<option value="${o.cnpj_root}" ${o.cnpj_root === st.real ? 'selected' : ''}>${e(o.empresa)} · ${o.barragens} barragens</option>`).join('')}</select></label>
      <p class="warn-note" style="flex:1;margin:0">${icon('shield')} ${e(D.aviso)}</p></div>
    <div class="kpis4 mt12"><div class="kpi"><span class="kpi-ic">${icon('dam')}</span><div><div class="kpi-v">${D.barragens.length}</div><div class="kpi-l">barragens no SIGBM</div></div></div>
      <div class="kpi"><span class="kpi-ic">${icon('alert')}</span><div><div class="kpi-v">${cnt('Crítica') + cnt('Alta')}</div><div class="kpi-l">com atenção crítica ou alta</div></div></div>
      <div class="kpi"><span class="kpi-ic">${icon('target')}</span><div><div class="kpi-v">${D.barragens.filter((b) => (b.dpa || '').toLowerCase() === 'alta').length}</div><div class="kpi-l">com dano potencial alto</div></div></div>
      <div class="kpi"><span class="kpi-ic">${icon('mine')}</span><div><div class="kpi-v">${D.minas.length}</div><div class="kpi-l">títulos de lavra (mesmo nome)</div></div></div></div>
    <div class="atv-grid mt12"><section class="card flush"><div class="rd-maph"><b>${e(D.empresa)}</b><div class="atv-leg">${glyph('triangulo', '#475569')} Barragem ${glyph('quadrado', '#28518A')} Mina ${glyph('radiacao', '#28518A')} Radiológica <span class="muted">· cor da barragem = atenção:</span>${Object.entries(ATT).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join('')}</div></div>${regionMap(pts, st.sel, { label: pts.length <= 25, aria: 'Mapa da empresa com dados públicos' })}</section>
      <section>${panel || `<div class="rd-list card flush">${D.barragens.sort((a, b) => (b.pontos || 0) - (a.pontos || 0)).map((b) => `<button class="rd-row" data-aid="${e(b.id)}">${glyph('triangulo', ATT[b.atencao] || '#9EA8AE')}<span class="rd-main"><strong>${e(b.nome)}</strong><small>${e(b.municipio)}/${e(b.uf)} · DPA ${e(b.dpa || '—')} · ${e(b.situacao || '')}</small></span><span class="lx-chip ${{ 'Crítica': 'crit', 'Alta': 'alta', 'Moderada': 'mod', 'Baixa': 'baixa' }[b.atencao] || 'baixa'}">${e(b.atencao)}</span></button>`).join('')}
        ${D.minas.slice(0, 20).map((m) => `<button class="rd-row" data-aid="${e(m.id)}">${glyph(m.radiologico ? 'radiacao' : 'quadrado', '#28518A')}<span class="rd-main"><strong>${e(m.substancia)}</strong><small>Lavra · ${e(m.fase)} · ${e(m.uf)}</small></span></button>`).join('')}</div>`}</section></div>
    <p class="hint">Fonte: ANM/SIGBM (snapshot ${e(D.snapshot || '—')}) e ANM/SIGMINE. Atenção = sinal da LexIA a partir de campos públicos, não declaração de irregularidade.</p>`;
}

export const ativosPage = {
  async render() {
    const st = AS();
    const E = await api('/api/ativos/empresas');
    const hashE = new URLSearchParams(location.hash.split('?')[1] || '').get('empresa');
    if (hashE) { st.empresa = hashE; history.replaceState(null, '', '#/ativos'); }
    if (state.perfil && E.items.some((x) => x.id === state.perfil)) st.empresa = state.perfil;
    if (!st.empresa || !E.items.some((x) => x.id === st.empresa)) st.empresa = E.items[0]?.id;
    if (!st.empresa) return '<div class="empty"><p>Nenhuma empresa configurada para esta conta.</p></div>';
    const cur = E.items.find((x) => x.id === st.empresa);
    const modeBar = cur?.setor === 'mineracao' ? `<div class="seg atv-mode mt12" role="group" aria-label="Fonte dos dados"><button class="${st.modo !== 'real' ? 'on' : ''}" data-modo="demo">Empresa da demonstração · com sensores (fictícia)</button><button class="${st.modo === 'real' ? 'on' : ''}" data-modo="real">Empresa real · dados públicos da ANM</button></div>` : '';
    const head = `<header class="page-head"><div><span class="eyebrow">Operação & Ativos · ${e(cur?.setor_nome || '')}</span><h2>Mapa de ativos</h2><p class="muted">Cada ativo no mapa com a situação dele: documentos, sensores e alertas. A forma diz o tipo de ativo; a cor diz se está tudo certo (verde), com pendência (amarelo) ou crítico (vermelho).</p></div></header>`;
    if (cur?.setor === 'mineracao' && st.modo === 'real') return head + modeBar + await realView(st);
    const R = await api('/api/ativos?empresa=' + encodeURIComponent(st.empresa));
    const tabs = [...R.abas_ativas, 'config'];
    if (!st.aba || !tabs.includes(st.aba)) st.aba = 'todos';
    const lst = R.assets.filter((a) => st.aba === 'todos' || a.aba === st.aba);
    const sel = R.assets.find((a) => a.id === st.sel);
    const cnt = (s) => R.assets.filter((a) => a.status === s).length;
    const body = st.aba === 'config' ? configTab(R) : st.aba === 'documentos' ? docsTab(R) : st.aba === 'juridico' ? juridicoTab(R) : `
      <div class="atv-grid"><section class="card flush"><div class="rd-maph"><b>${lst.length} ativo(s)</b><div class="atv-leg">${Object.values(R.legenda).map((l) => `<span>${glyph(l.simbolo, '#475569')}${e(l.rotulo)}</span>`).join('')}<span class="muted">· cor = situação:</span>${Object.values(ST).map(([n, c]) => `<span><i style="background:${c}"></i>${n}</span>`).join('')}</div></div>${map({ ...R, assets: lst }, st.sel)}</section>
        <section>${sel ? assetPanel(sel, R) : `<div class="rd-list card flush">${lst.map((a) => `<button class="rd-row" data-aid="${e(a.id)}">${glyph(a.simbolo, ST[a.status][1])}<span class="rd-main"><strong>${e(a.nome)}</strong><small>${e(a.tipo_rotulo)} · ${e(a.municipio || '')}</small></span><span class="tag" style="--c:${ST[a.status][1]}">${ST[a.status][0]}${a.ocorrencias ? ' · ' + a.ocorrencias : ''}</span></button>`).join('')}</div>`}</section></div>`;
    return `${head}${modeBar}
    <div class="row between wrap"><p class="sm"><b>${e(R.empresa.nome)}</b> · setor ${e(R.setor.nome)} · reguladores: ${R.setor.reguladores.map(e).join(', ')}</p><small class="muted">${e(E.aviso)}</small></div>
    <div class="kpis4 mt8"><div class="kpi" style="--k:#1570EF"><span class="kpi-ic">${icon('layers')}</span><div><div class="kpi-v">${R.assets.length}</div><div class="kpi-l">ativos monitorados</div></div></div>
      <div class="kpi" style="--k:#C83037"><span class="kpi-ic">${icon('alert')}</span><div><div class="kpi-v">${cnt('critico')}</div><div class="kpi-l">em situação crítica</div></div></div>
      <div class="kpi" style="--k:#D4A12E"><span class="kpi-ic">${icon('doc')}</span><div><div class="kpi-v">${cnt('pendencia')}</div><div class="kpi-l">com pendência</div></div></div>
      <div class="kpi" style="--k:#68487A"><span class="kpi-ic">${icon('users')}</span><div><div class="kpi-v">${R.alerts.length}</div><div class="kpi-l">alertas roteados por papel${R.donos ? ` · <b style="color:${R.donos.alertas_sem_dono ? '#C83037' : '#46774E'}">${R.donos.alertas_sem_dono} sem dono</b>` : ''}</div></div></div></div>
    ${R.donos?.alertas_escalados ? `<p class="warn-note mt8">${icon('users')} ${R.donos.alertas_escalados} alerta(s) escalado(s): o papel responsável não tem pessoa cadastrada nesta empresa (${R.donos.papeis_sem_pessoa.map(e).join(', ')}). Cadastre alguém no papel ou ajuste a rota em Configuração. <a href="#/equipe">${icon('users')} Convidar pessoas</a></p>` : ''}
    <div class="atv-filtro mt16"><span>Mostrar</span><div class="tabs" role="tablist" style="margin:0">${[['todos', 'Todos'], ...tabs.map((t) => [t, t === 'config' ? 'Configuração' : (R.abas_rotulos[t] || t)])].map(([k, l]) => `<button role="tab" aria-selected="${st.aba === k}" class="tab ${st.aba === k ? 'on' : ''}" data-aba="${k}">${e(l)}</button>`).join('')}</div></div>
    ${body}`;
  },
  mount(root, ctx) {
    const st = AS();
    root.querySelectorAll('[data-emp]').forEach((b) => b.addEventListener('click', () => { st.empresa = b.dataset.emp; st.sel = null; st.aba = 'todos'; ctx.rerender(); }));
    root.querySelectorAll('[data-modo]').forEach((b) => b.addEventListener('click', () => { st.modo = b.dataset.modo; st.sel = null; ctx.rerender(); }));
    root.querySelector('#atv-real')?.addEventListener('change', (ev) => { st.real = ev.target.value; st.sel = null; ctx.rerender(); });
    root.querySelectorAll('[data-aba]').forEach((b) => b.addEventListener('click', () => { st.aba = b.dataset.aba; st.sel = null; ctx.rerender(); }));
    root.querySelectorAll('svg [data-aid]').forEach((b) => b.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); b.dispatchEvent(new MouseEvent('click', { bubbles: true })); } }));
    root.querySelectorAll('[data-aid]').forEach((b) => b.addEventListener('click', () => { st.sel = st.sel === b.dataset.aid ? null : b.dataset.aid; ctx.rerender(); }));
    root.querySelector('#atv-close')?.addEventListener('click', () => { st.sel = null; ctx.rerender(); });
  },
};

function docsTab(R) {
  const rows = R.assets.flatMap((a) => a.documentos.map((d) => ({ a, d }))).sort((x, y) => (x.d.dias ?? 99999) - (y.d.dias ?? 99999));
  return card('Documentos e licenças de todos os ativos', `<div class="table-wrap tall"><table class="table compact"><thead><tr><th>Ativo</th><th>Documento</th><th>Base</th><th>Vence</th><th>Situação</th></tr></thead><tbody>${rows.map(({ a, d }) => `<tr><td>${glyph(a.simbolo, ST[a.status][1])} ${e(a.nome)}</td><td>${e(d.nome)}</td><td><small>${e(d.base)}</small></td><td>${d.vence ? fmtDate(d.vence) : '—'}</td><td><span class="tag" style="--c:${d.nivel ? LV[d.nivel] : '#46774E'}">${e(d.status)}</span></td></tr>`).join('')}</tbody></table></div>
    <p class="hint">Verificação de datas e limites é regra simples (custo zero de IA). A IA só entra para interpretar texto.</p>`, { icon: 'doc' });
}

function juridicoTab(R) {
  return card('Jurídico e Compliance — alertas desta empresa', `<div class="table-wrap tall"><table class="table compact"><thead><tr><th>Nível</th><th>Alerta</th><th>Ativo</th><th>Vai para</th><th>Situação</th></tr></thead><tbody>${R.alerts.map((x) => `<tr><td><span class="tag" style="--c:${LV[x.level]}">${e(x.level)}</span></td><td>${e(x.title)}<br><small class="muted">${e(x.action)}</small></td><td>${e(x.asset_name)}</td><td>${x.recipients.map((r) => e(r.rotulo)).join(', ')}</td><td>${e(x.status)}</td></tr>`).join('')}</tbody></table></div>
    <a class="btn sm mt8" href="#/compliance">${icon('shield')} Abrir em Compliance & Alertas (prazo, evidência, histórico)</a>`, { icon: 'shield' });
}

function configTab(R) {
  const C = R.config;
  return `<div class="grid-6-6">${card('Parâmetros da empresa', `<dl class="kv"><dt>Setor</dt><dd>${e(R.setor.nome)}</dd><dt>UFs de operação</dt><dd>${(C.uf || []).map(e).join(', ')}</dd>
      <dt>Abas ativas</dt><dd>${C.abas_ativas.map((t) => e(R.abas_rotulos[t] || t)).join(' · ')}</dd><dt>Tipos de ativo</dt><dd>${Object.values(R.legenda).map((l) => `${l.caractere} ${e(l.rotulo)}`).join(' · ')}</dd>
      <dt>Reguladores</dt><dd>${R.setor.reguladores.map(e).join(' · ')}</dd><dt>Regra</dt><dd><code>${e(R.rule_version)}</code></dd></dl>
      <p class="hint">Trocar de setor não exige código: o módulo do setor define ativos, documentos, indicadores, limites e reguladores (data/setores.json).</p>`, { icon: 'layers' })}
    ${card('Quem recebe cada tipo de ocorrência', `<table class="table compact"><thead><tr><th>Ocorrência</th><th>Papéis</th></tr></thead><tbody>${Object.entries(C.roteamento).map(([k, v]) => `<tr><td>${e(k.replaceAll('_', ' '))}</td><td>${v.map((r) => e(C.papeis[r] || (r === 'dono_do_documento' ? 'Responsável pelo documento' : r))).join(', ')}</td></tr>`).join('')}</tbody></table>
      <p class="hint">Cada papel é ligado às pessoas da própria empresa: a notificação chega só a quem precisa, nunca a outra organização.</p>`, { icon: 'users' })}</div>`;
}
