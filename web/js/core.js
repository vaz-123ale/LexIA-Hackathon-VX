// Núcleo v4: estado, API (sessão por cookie), rótulos dos eixos e utilitários.
export const AS_OF_DEFAULT = '2026-11-06';

export const state = {
  route: 'inicio', ws: 'exec', tab: {}, asOf: AS_OF_DEFAULT, scenario: 'anm', profile: 'simples',
  atlas: { q: '', uf: '', op: '', pnsb: '', cri: '', dpa: '', applic: '', showOfficial: true, showSynthetic: false, page: 0, view: 'map' },
  selection: null, overrides: {}, openReview: null, showGraph: false, execLayer: 'all', authTab: 'empresa',
};

export const data = { assets: [], sources: [], scenarios: [], provisions: [], findings: [], map: null, states: null, world: null, health: null,
  reviews: [], templates: {}, connectors: [], checklist: null, timeline: [], official: null, users: [], permissions: {}, me: { authenticated: false } };

export async function api(path, body) {
  const opts = { headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' };
  if (body !== undefined) { opts.method = 'POST'; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  const json = await res.json().catch(() => ({ error: 'Resposta inválida do servidor.' }));
  if (!res.ok) throw new Error(json.error || `Erro ${res.status}`);
  return json;
}

export const e = (s) => String(s ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
export const fmtDate = (iso) => { if (!iso) return '—'; const [y, m, d] = iso.slice(0, 10).split('-'); return `${d}/${m}/${y}`; };
export const fmtDateTime = (iso) => iso ? `${fmtDate(iso)} ${iso.slice(11, 16)} UTC` : '—';
export const fmtMoney = (v) => 'R$ ' + Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtCnpj = (c) => c ? String(c).replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5') : '—';

// Resultado da triagem (motor de regras) — mesma paleta da legenda do mapa
export const TRIAGE = {
  REVIEW: ['Candidato à revisão', '#F5B301'], INSUFFICIENT: ['Dados insuficientes', '#8B5CF6'], FUTURE_REVIEW: ['Transição futura', '#3B82F6'],
  MONITOR: ['Monitorar (consulta)', '#10B981'], OUT_OF_SCOPE: ['Fora do escopo', '#CBD5E1'], NO_LINK: ['Sem vínculo', '#63768A'],
};
// Quatro eixos independentes (texto + ícone; a cor nunca é o único indicador)
export const AXES = {
  lifecycle: {
    proposed: ['Proposto / em consulta', '◌', '#10B981'], published_not_effective: ['Publicado, sem efeito', '◔', '#3B82F6'],
    effective: ['Vigente', '●', '#2563EB'], historical: ['Histórico', '◍', '#94A3B8'], revoked: ['Revogado', '⊘', '#EF4444'], unknown: ['Data a conferir', '?', '#D4A12E'],
  },
  applic: {
    candidate_review: ['Candidato à revisão', '◆', '#F5B301'], missing_attributes: ['Dados insuficientes', '◇', '#8B5CF6'],
    excluded_by_scope: ['Excluído pelo escopo', '⊘', '#94A3B8'], no_supported_link: ['Sem vínculo suportado', '–', '#63768A'],
    confirmed_applicable_by_human: ['Aplicável · confirmado', '✓', '#46774E'], rejected_by_human: ['Rejeitado · humano', '✕', '#EF4444'],
  },
  workflow: {
    not_assigned: ['Sem responsável', '○', '#94A3B8'], pending_review: ['Aguardando revisão', '◐', '#D4A12E'], reviewing: ['Em revisão', '◑', '#3B82F6'],
    approved_for_action: ['Aprovado p/ ação', '✓', '#46774E'], action_in_progress: ['Ação em andamento', '▶', '#8B5CF6'], closed: ['Encerrado', '■', '#63768A'],
  },
  priority: {
    urgent: ['Urgente', '▲', '#C83037'], high: ['Alta', '▲', '#E5484D'], medium: ['Média', '■', '#D4A12E'], low: ['Baixa', '▼', '#63768A'], not_assessed: ['Não avaliada', '·', '#94A3B8'],
  },
};
export const tag = (axis, v, title = '') => {
  const m = AXES[axis]?.[v]; if (!m) return '';
  return `<span class="tag ${axis === 'priority' ? 'prio-' + v : ''}" style="--c:${m[2]}" title="${e(title || m[0])}"><i aria-hidden="true">${m[1]}</i>${e(m[0])}</span>`;
};
export const originTag = (o) => o === 'DADO_OFICIAL' ? '<span class="origin off" title="Dado de fonte oficial (snapshot identificado)">DADO OFICIAL</span>'
  : '<span class="origin hyp" title="Cenário hipotético com dados sintéticos">CENÁRIO HIPOTÉTICO</span>';
export const LIFE_FROM_TEMPORAL = { EM_CONSULTA: 'proposed', CONSULTA_ENCERRADA: 'proposed', FUTURA: 'published_not_effective', VIGENTE: 'effective', HISTORICA: 'historical', REVOGADA: 'revoked', A_CONFERIR: 'unknown' };
export const REVIEW_STATE = { DRAFT: 'Rascunho', REVIEW_PENDING: 'Aguardando revisão', CONFIRMED: 'Confirmado', REJECTED: 'Rejeitado', ACTION_TRACKING: 'Em acompanhamento', CLOSED: 'Encerrado' };
export const FUNCTIONS = { juridico: 'Jurídico', compliance: 'Compliance', engenharia: 'Engenharia / geotecnia', operacao: 'Operação', financas: 'Finanças', regulatorio: 'Assuntos regulatórios', protecao_radiologica: 'Proteção radiológica', meio_ambiente: 'Meio ambiente', auditoria: 'Auditoria' };

// Ícones de traço (24×24) — mesma linguagem da referência
export const ICON = {
  home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>', pin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  flask: '<path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3"/>', check: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 12l3 3 5-6"/>',
  refresh: '<path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/>', doc: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
  alert: '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/>', cal: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4M8 14h2M14 14h2M8 17h2"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  bell: '<path d="M6 16V11a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>', user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>', chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>', chevron: '<path d="M6 9l6 6 6-6"/>', shield: '<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/>',
  filter: '<path d="M3 4h18l-7 8v8l-4-2v-6z"/>', copy: '<rect x="8" y="3" width="12" height="14" rx="2"/><path d="M16 17v4H4V7h4"/>', crosshair: '<circle cx="12" cy="12" r="7"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
  link: '<path d="M10 14l4-4M8 16l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 8l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0"/>', monitor:'<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>', database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>', users:'<circle cx="9" cy="7" r="3"/><path d="M2 20v-3c0-5 14-5 14 0v3zM16 4c5 0 5 7 0 7M18 13c4 0 4 3 4 7h-3"/>',
  logout: '<path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10"/>', star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
  book: '<path d="M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-7a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h8z"/>', phone: '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
  building: '<path d="M4 21V5l8-2v18M12 7l8 3v11M8 8v.01M8 12v.01M8 16v.01M16 13v.01M16 17v.01M2 21h20"/>',
  generator: '<rect x="3" y="7" width="15" height="10" rx="1.5"/><path d="M18 10h3v4h-3M6 11h5M6 14h7M7 7V5M14 7V5"/>',
  dam: '<path d="M2 18h20M4 18V9l3-2v11M9 18V8M13 18V8M17 18V7l3 2v9M9 12h4"/><path d="M2 21c2 0 2-1.5 4-1.5s2 1.5 4 1.5 2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5"/>',
  platform: '<path d="M3 13h18M6 13V8h12v5M9 8V4h6v4M6 13l-2 8M18 13l2 8M10 17h4"/>', pipe: '<path d="M2 9h20v6H2zM6 9v6M18 9v6M12 3v6M12 15v6"/>',
  lab: '<path d="M9 3h6M10 3v6L5 19a1.5 1.5 0 0 0 1.4 2h11.2a1.5 1.5 0 0 0 1.4-2L14 9V3"/><path d="M7.5 15h9"/>', mine: '<path d="M3 20l6-10 4 6 3-4 5 8z"/><circle cx="16" cy="6" r="2"/>',
};
export const icon = (name, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICON[name] || ''}</svg>`;
export const ASSET_ICON = { terrestrial_building: 'generator', administrative: 'building', offshore_platform: 'platform', dam: 'dam', mining_pile: 'mine', outdoor_station: 'pipe', pipeline: 'pipe', radiative_facility: 'lab' };

export const lookupSource = (id) => data.sources.find((s) => s.id === id);
export const refLink = (id) => { const s = lookupSource(id); return s ? `<a class="ref" href="${e(s.url)}" target="_blank" rel="noopener noreferrer" title="${e(s.title)} · nível ${e(s.verification)}">${e(id)} ↗</a>` : e(id); };
export const refs = (ids) => (ids || []).map(refLink).join(' ');
export const assetById = (id) => data.assets.find((a) => a.id === id);
export const scenarioById = (id) => data.scenarios.find((s) => s.id === id);
export const finding = (scenario, asset) => data.findings.find((f) => f.scenario === scenario && f.asset_id === asset);
export const currentUser = () => data.me?.authenticated ? data.me.user : null;
export const can = (perm) => !!data.me?.authenticated && (data.me.permissions || []).includes(perm);

export const card = (title, body, opts = {}) => `<section class="card ${opts.cls || ''}">${title ? `<header class="card-h"><h3>${opts.icon ? icon(opts.icon, 'h-ic') : ''}${title}</h3>${opts.right || ''}</header>` : ''}${body}</section>`;
export const tabs = (ws, items) => { const cur = state.tab[ws] || items[0][0]; return `<div class="tabs" role="tablist">${items.map(([id, label, ic]) => `<button role="tab" class="tab ${cur === id ? 'on' : ''}" aria-selected="${cur === id}" data-tab="${ws}:${id}">${ic ? icon(ic) : ''}${e(label)}</button>`).join('')}</div>`; };
export const curTab = (ws, def) => state.tab[ws] || def;
export const empty = (msg, action = '') => `<div class="empty"><p>${msg}</p>${action}</div>`;

export function toast(msg, kind = 'ok') {
  const t = document.createElement('div');
  t.className = `toast ${kind}`; t.setAttribute('role', 'status'); t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add('out'), 3400); setTimeout(() => t.remove(), 3900);
}

export async function refreshMe() { data.me = await api('/api/auth/me'); return data.me; }
export async function refreshFindings() {
  [data.findings, data.provisions] = await Promise.all([api(`/api/findings?as_of=${state.asOf}`), api(`/api/provisions?as_of=${state.asOf}`)]);
}
export async function refreshReviews() {
  const r = await api(`/api/reviews?as_of=${state.asOf}`); data.reviews = r.reviews; data.templates = r.evidence_templates;
}
export async function refreshOfficial() { data.official = await api(`/api/official/sigbm?as_of=${state.asOf}`); }

// setor do perfil de empresa escolhido no topo (filtra normas na Central de IA)
export const perfilSetor = () => (currentUser()?.kind === 'empresa' ? (data.empresas || []).find((c) => c.id === state.perfil)?.setor || null : null);

// mudança normativa (cenário) ↔ setor do perfil: ANM só mineração; ANP energia/indústria; MTE e ANSN valem para todos
const CEN_SETOR = { ANM: ['mineracao', 'nuclear'], ANEEL: ['energia'], ANP: ['energia', 'industria'], ANA: ['saneamento'], MTE: null, ANSN: null, CNEN: null };
export const cenarioDoSetor = (sc) => { const s = perfilSetor(); if (!s) return true; const list = CEN_SETOR[(sc.regulator || '').toUpperCase()]; return !list || list.includes(s); };
