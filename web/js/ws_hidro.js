// Monitoramento hidrológico (ONS) — anomalias por z-score sazonal, tendência, padrões parecidos (KNN) e recomendações de manutenção.
import { state, api, e, fmtDate, fmtDateTime, card, icon } from './core.js';

const LV = { 'Crítica': '#C83037', 'Alta': '#F97316', 'Moderada': '#EAB308', 'Normal': '#46774E' };
const HS = () => (state.hid = state.hid || { sel: null, lvl: '', q: '' });
const num = (v, d = 1) => (v == null ? '—' : Number(v).toLocaleString('pt-BR', { maximumFractionDigits: d }));

function spark(vals, color, h = 90, marks = null) {
  const pts = vals.map((v, i) => [i, v]).filter(([, v]) => v != null);
  if (pts.length < 2) return '<p class="muted sm">Sem dados suficientes.</p>';
  const ys = pts.map(([, v]) => v), mn = Math.min(...ys), mx = Math.max(...ys), W = 600, n = vals.length - 1 || 1;
  const X = (i) => (i / n) * W, Y = (v) => h - 6 - ((v - mn) / (mx - mn || 1)) * (h - 12);
  const d = pts.map(([i, v], k) => `${k ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join('');
  const ref = marks ? marks.filter((m) => m.v != null && m.v >= mn - (mx - mn) * 0.2 && m.v <= mx + (mx - mn) * 0.2).map((m) => `<line x1="0" x2="${W}" y1="${Y(m.v)}" y2="${Y(m.v)}" stroke="${m.c}" stroke-dasharray="4 4"/><text x="4" y="${Y(m.v) - 3}" font-size="10" fill="${m.c}">${e(m.l)}</text>`).join('') : '';
  return `<svg viewBox="0 0 ${W} ${h}" class="hd-spark" preserveAspectRatio="none" role="img"><path d="${d}" fill="none" stroke="${color}" stroke-width="2"/>${ref}</svg>
    <div class="row between sm muted"><span>mín ${num(mn)}</span><span>máx ${num(mx)}</span></div>`;
}

export const hidroPage = {
  async render() {
    const st = HS();
    const d = await api('/api/hidro');
    let x = null;
    if (st.sel) x = await api('/api/hidro?id=' + encodeURIComponent(st.sel)).catch(() => null);
    const items = d.items.filter((r) => (!st.lvl || r.attention === st.lvl) && (!st.q || `${r.nome} ${r.rio || ''} ${r.bacia}`.toLowerCase().includes(st.q.toLowerCase())));
    const files = d.meta?.files || [];
    return `<header class="page-head"><div><span class="eyebrow">Manutenção preventiva · dados abertos do ONS</span><h2>Monitoramento hidrológico</h2><p class="muted">Nível, volume útil e vazões diárias de ${d.total} reservatórios do Sistema Interligado Nacional. A LexIA detecta picos, tendências e comportamentos fora do padrão e sugere inspeções antes do problema.</p></div></header>
    <div class="kpis4">${['Crítica', 'Alta', 'Moderada', 'Normal'].map((l) => `<button class="kpi kpi-btn" style="--k:${LV[l]}" data-hl="${l}"><span class="kpi-ic">${icon('chart')}</span><span><span class="kpi-v">${d.levels[l] || 0}</span><span class="kpi-l">atenção ${l.toLowerCase()}</span></span></button>`).join('')}</div>
    <div class="row gap wrap mt16"><input class="search" id="hd-q" value="${e(st.q)}" placeholder="Buscar reservatório, rio ou bacia" style="max-width:360px">${st.lvl ? `<button class="chip-btn" data-hl="">${e(st.lvl)} ×</button>` : ''}<span class="muted sm">${items.length} reservatório(s)</span></div>
    <div class="cp-grid mt12"><section class="card flush"><div class="rd-list">${items.map((r) => `<button class="rd-row ${st.sel === r.id ? 'on' : ''}" data-hid="${e(r.id)}"><span class="rd-bar" style="background:${LV[r.attention]}"></span><span class="rd-main"><strong>${e(r.nome)}</strong><small>${e(r.bacia)} · ${e(r.rio || r.tipo)} · volume útil ${num(r.volume_util)}%</small><small class="rd-sig">${r.signals.map(e).join(' · ') || 'Sem sinal'}</small></span><span class="tag" style="--c:${LV[r.attention]}">${e(r.attention)}</span></button>`).join('')}</div></section>
      <section>${x ? card(e(x.nome), `<p class="muted sm">${e(x.subsistema)} · bacia ${e(x.bacia)} · ${e(x.rio || '')} · dado de ${fmtDate(x.last_date)}</p>
          <div class="eff-grid"><div><b>${num(x.nivel, 2)} m</b><span>nível montante</span></div><div><b>${num(x.volume_util)}%</b><span>volume útil</span></div><div><b>${num(x.vazao_afluente, 0)} m³/s</b><span>vazão afluente</span></div><div><b>${num(x.vazao_vertida, 0)} m³/s</b><span>vazão vertida</span></div></div>
          <h4>Nível (120 dias)</h4>${spark(x.series.nivel, '#1570EF', 90, [{ v: x.cota_max, c: '#C83037', l: 'cota máx.' }, { v: x.cota_min, c: '#D4A12E', l: 'cota mín.' }])}
          <h4>Vazão afluente (120 dias)</h4>${spark(x.series.afluente, '#68487A')}
          <h4>Vazão vertida (120 dias)</h4>${spark(x.series.vertida, '#DB2777', 60)}
          <h4>Sinais (${e(x.rule_version)})</h4><ul class="ticks no">${x.signals.map((s) => `<li>${e(s.label)}</li>`).join('') || '<li>Nenhum sinal.</li>'}</ul>
          <dl class="kv"><dt>Z-score afluência (mesma época do ano anterior)</dt><dd>${num(x.z_afluencia, 2)}</dd><dt>Tendência do nível</dt><dd>${x.tendencia_m_dia == null ? '—' : num(x.tendencia_m_dia * 100, 1) + ' cm/dia'}</dd>
            <dt>Padrões parecidos (KNN)</dt><dd>${x.knn ? `${x.knn.k} janelas de ${x.knn.window_days} dias mais parecidas: afluência mudou ${num(x.knn.expected_change_pct)}% nos ${x.knn.ahead_days} dias seguintes (concordância ${Math.round(x.knn.agreement * 100)}%)` : 'histórico insuficiente'}</dd></dl>
          <h4>Recomendações de inspeção e manutenção</h4><ul class="ticks">${x.recommendations.map((r) => `<li>${e(r)}</li>`).join('') || '<li>Manter rotina de inspeção.</li>'}</ul>
          <p class="hint">${e(d.reading)}</p>`, { icon: 'chart' }) : '<div class="empty"><p>Selecione um reservatório para ver a série, os sinais e as recomendações.</p></div>'}</section></div>
    <p class="hint">Fonte: ONS — Dados Abertos (arquivos públicos no Amazon S3 do ONS; a API do portal é bloqueada no robots.txt e não é usada). Coleta: ${fmtDateTime(d.meta?.collected_at)} · ${files.length} arquivo(s) com SHA-256.</p>`;
  },
  mount(root, ctx) {
    const st = HS();
    root.querySelectorAll('[data-hl]').forEach((b) => b.addEventListener('click', () => { st.lvl = b.dataset.hl === st.lvl ? '' : b.dataset.hl; ctx.rerender(); }));
    root.querySelectorAll('[data-hid]').forEach((b) => b.addEventListener('click', () => { st.sel = b.dataset.hid; ctx.rerender(); }));
    let t; root.querySelector('#hd-q')?.addEventListener('input', (ev) => { clearTimeout(t); t = setTimeout(async () => { st.q = ev.target.value; await ctx.rerender(); const q = document.querySelector('#hd-q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }, 300); });
  },
};
