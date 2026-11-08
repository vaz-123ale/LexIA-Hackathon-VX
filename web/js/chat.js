// Conversa compartilhada entre a bolinha (mini-chat) e a página Central de IA.
import { api, e, icon, perfilSetor } from './core.js';
import { attTag } from './ws_radar.js';

export const chat = { msgs: [], busy: false, listeners: new Set() };
const emit = () => chat.listeners.forEach((f) => f());

export const SUGGEST = ['Risco oculto em MT', 'Órfãs críticas no RN', 'Inativas sem projeto em MG', 'Pessoa física com emergência', 'Quem é responsável por barragem abandonada?', 'Cooperativas sem DCE', 'O que muda na Resolução ANM 245/2026?'];

export async function send(q, profile = 'simples') {
  q = (q || '').trim();
  if (!q || chat.busy) return;
  chat.msgs.push({ who: 'me', text: q }); chat.busy = true; emit();
  try { chat.msgs.push({ who: 'ia', ...(await api('/api/ai/quick', { q, profile, setor: perfilSetor() })) }); }
  catch (err) { chat.msgs.push({ who: 'ia', kind: 'error', answer: 'Não consegui consultar agora. ' + err.message }); }
  finally { chat.busy = false; emit(); }
}

const pbox = (p) => (p ? `<div class="persp"><b>Para você · ${e(p.rotulo)}</b><small>${e(p.foco)}</small>${(p.pontos || []).map((x) => `<span>• ${e(x)}</span>`).join('')}<span class="persp-next">→ ${e(p.proximo_passo)}</span><small class="muted">${e(p.nota)}</small></div>` : '');
const ENGINE = { regras: 'Regras', ia: 'IA + verificador', controlado: 'Resposta controlada', ia_conectada: 'IA + verificador de citações' };

export function msgHtml(m, compact = false) {
  if (m.who === 'me') return `<div class="cm me"><p>${e(m.text)}</p></div>`;
  const res = (m.results || []).slice(0, compact ? 3 : 6);
  return `<div class="cm ia"><span class="cm-av">${icon('spark')}</span><div class="cm-b">
    <p>${e(m.answer)}</p>${pbox(m.perspectiva)}
    ${m.chips?.length ? `<div class="cm-chips">${m.chips.map((c) => `<span class="chip-f">${e(c)}</span>`).join('')}</div>` : ''}
    ${res.length ? `<div class="cm-res">${res.map((r) => `<a href="#/radar?id=${encodeURIComponent(r.id)}" class="cm-r"><span><b>${e(r.name)}</b><small>${e(r.municipio || '')}/${e(r.uf || '')} · ${r.kind === 'orfa' ? 'órfã' : 'mineração'}</small></span>${attTag(r.attention)}</a>`).join('')}${m.total > res.length ? `<small class="muted">+${m.total - res.length} no Radar</small>` : ''}</div>` : ''}
    ${m.sources?.length ? `<div class="cm-src">${m.sources.map((s) => (s.startsWith('http') ? `<a href="${e(s)}" target="_blank" rel="noopener noreferrer">Fonte oficial ↗</a>` : `<span>${e(s)}</span>`)).join('')}</div>` : ''}
    <small class="cm-meta">${e(ENGINE[m.engine] || m.engine || '')}${m.note ? ' · ' + e(m.note) : ''}${m.state === 'ABSTAIN' ? ' · abstenção: sem base verificada' : ''}</small>
  </div></div>`;
}
