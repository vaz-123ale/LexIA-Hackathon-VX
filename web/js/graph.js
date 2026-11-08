// RegulaGraph: layout em camadas (fonte → documento → dispositivo → achado → ativo/revisão → evidência)
// com ordenação baricêntrica para reduzir cruzamentos.
import { e } from './core.js';
const STATE_COLORS = { REVIEW: '#39A994', FUTURE_REVIEW: '#8FB3C9', MONITOR: '#8FB3C9', INSUFFICIENT: '#D6A95D', VIGENTE: '#39A994', FUTURA: '#8FB3C9', HISTORICA: '#7E9097', EM_CONSULTA: '#8FB3C9', A_CONFERIR: '#D6A95D', CONFIRMED: '#7CC6B4', REJECTED: '#CF6E70' };
const colorOf = (s) => STATE_COLORS[s] || '#6F8389';

export const KINDS = {
  fonte: { col: 0, label: 'Fonte oficial', color: '#9fd0ff' },
  documento: { col: 1, label: 'Documento', color: '#6cb6ff' },
  dispositivo: { col: 2, label: 'Dispositivo + vigência', color: '#4fd8c4' },
  achado: { col: 3, label: 'Achado (regra)', color: '#ffc86b' },
  ativo: { col: 4, label: 'Ativo sintético', color: '#f6a5ff' },
  revisao: { col: 4, label: 'Revisão humana', color: '#ffb36b' },
  evidencia: { col: 5, label: 'Evidência', color: '#76dab3' },
};

export function layout(graph, W = 1400) {
  const cols = Array.from({ length: 6 }, () => []);
  graph.nodes.forEach((n) => cols[KINDS[n.kind]?.col ?? 0].push(n));
  const nb = new Map(graph.nodes.map((n) => [n.id, []]));
  graph.edges.forEach((ed) => { nb.get(ed.from)?.push(ed.to); nb.get(ed.to)?.push(ed.from); });
  const pos = new Map();
  cols.forEach((c) => c.forEach((n, i) => pos.set(n.id, i)));
  for (let pass = 0; pass < 6; pass++) {
    cols.forEach((c) => {
      c.forEach((n) => { const ns = nb.get(n.id).filter((x) => pos.has(x)); n._b = ns.length ? ns.reduce((s, x) => s + pos.get(x) / Math.max(1, cols[KINDS[graph.nodes.find((k) => k.id === x).kind].col].length), 0) / ns.length : 0.5; });
      c.sort((a, b) => a._b - b._b || (a.kind > b.kind ? 1 : -1)).forEach((n, i) => pos.set(n.id, i));
    });
  }
  const rowH = 46, H = Math.max(...cols.map((c) => c.length)) * rowH + 80, colW = (W - 260) / 5;
  cols.forEach((c, ci) => { const off = (H - c.length * rowH) / 2; c.forEach((n, i) => { n.x = 130 + ci * colW; n.y = off + i * rowH + rowH / 2; }); });
  return { W, H, cols };
}

export function graphSvg(graph, selected) {
  const { W, H } = layout(graph);
  const by = new Map(graph.nodes.map((n) => [n.id, n]));
  const sel = selected && by.get(selected);
  const near = new Set(sel ? [sel.id] : []);
  if (sel) graph.edges.forEach((ed) => { if (ed.from === sel.id) near.add(ed.to); if (ed.to === sel.id) near.add(ed.from); });
  const edges = graph.edges.map((ed) => {
    const a = by.get(ed.from), b = by.get(ed.to); if (!a || !b) return '';
    const [s, t] = a.x <= b.x ? [a, b] : [b, a], mx = (s.x + t.x) / 2;
    const on = sel && (ed.from === sel.id || ed.to === sel.id);
    return `<path class="g-edge ${on ? 'on' : ''} ${sel && !on ? 'dim' : ''}" d="M${s.x},${s.y} C${mx},${s.y} ${mx},${t.y} ${t.x},${t.y}"><title>${e(ed.rel)} · fonte: ${e(ed.source_id || '—')} · status: ${e(ed.review_status)}</title></path>`;
  }).join('');
  const nodes = graph.nodes.map((n) => {
    const k = KINDS[n.kind], c = n.state ? colorOf(n.state) : n.status ? colorOf(n.status) : k.color;
    const label = n.label.length > 34 ? n.label.slice(0, 33) + '…' : n.label;
    const dim = sel && !near.has(n.id);
    return `<g class="g-node ${n.id === selected ? 'sel' : ''} ${dim ? 'dim' : ''}" data-node="${e(n.id)}" tabindex="0" role="button" aria-label="${e(k.label)}: ${e(n.label)}" transform="translate(${n.x},${n.y})">
      <rect x="-104" y="-16" width="208" height="32" rx="8" style="--c:${c}"/><circle cx="-90" cy="0" r="5" fill="${c}"/>
      <text x="-78" y="4">${e(label)}</text><title>${e(n.label)}</title></g>`;
  }).join('');
  const heads = Object.entries(KINDS).filter(([k]) => k !== 'revisao').map(([, v]) => { const x = 130 + v.col * (W - 260) / 5; return `<text class="g-head" x="${x}" y="22" text-anchor="middle">${e(v.col === 4 ? 'Ativo · Revisão' : v.label)}</text>`; }).join('');
  return `<svg class="graph-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Grafo regulatório">${heads}${edges}${nodes}</svg>`;
}
