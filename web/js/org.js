// Contexto de organização: deixa sempre claro DE QUEM é a informação na tela.
import { state, data, api, e, icon, refs } from './core.js';

export const NATURE = {
  FICTICIA: ['Empresa fictícia', 'nat-fic', 'Carteira de demonstração. Nenhum ativo representa instalação real.'],
  DADOS_PUBLICOS: ['Dados públicos ANM', 'nat-pub', 'Estruturas reais publicadas pela ANM (SIGBM), identificadas pelo CNPJ.'],
  PESQUISADA: ['Pesquisada · sem ativos', 'nat-res', 'Organização pesquisada em fontes públicas. Nenhum ativo conectado; nada é inventado.'],
  REGULADOR: ['Órgão regulador', 'nat-reg', 'Instituição pública que regula o setor (não é empresa).'],
};
export const currentOrg = () => data.orgs.find((o) => o.id === state.org) || data.orgs[0];
export const natTag = (n) => `<span class="nat ${NATURE[n][1]}" title="${e(NATURE[n][2])}">${e(NATURE[n][0])}</span>`;
const initials = (s) => s.replace(/[^A-Za-zÀ-ú ]/g, ' ').split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();

export async function loadOrgs() { const r = await api('/api/organizations'); data.orgs = r.items; data.orgNotice = r.notice; }

export function orgBar(subtitle = '') {
  const o = currentOrg();
  return `<section class="orgbar" aria-label="Organização em análise">
    <div class="org-id"><span class="org-av ${NATURE[o.nature][1]}">${e(initials(o.short))}</span>
      <div><div class="org-name">${e(o.name)} ${natTag(o.nature)}</div>
      <small>${e(o.sector)} · ${o.asset_count ? `<b>${o.asset_count}</b> ativo(s) ${o.nature === 'FICTICIA' ? 'na carteira de demonstração' : 'conectados (SIGBM/ANM)'}` : 'nenhum ativo conectado'}${subtitle ? ' · ' + subtitle : ''}</small></div>
      <button class="btn sm ghost" data-org-profile>${icon('book')} Sobre esta organização</button></div>
    <div class="org-switch" role="tablist" aria-label="Trocar organização">${data.orgs.map((x) => `<button role="tab" aria-selected="${x.id === o.id}" class="org-chip ${x.id === o.id ? 'on' : ''}" data-org="${x.id}" title="${e(NATURE[x.nature][2])}"><span class="dot ${NATURE[x.nature][1]}"></span>${e(x.short)}${x.asset_count ? ` <b>${x.asset_count}</b>` : ''}</button>`).join('')}</div>
  </section>`;
}

export function openOrgProfile() {
  const o = currentOrg();
  let m = document.getElementById('org-modal');
  if (!m) { m = document.createElement('div'); m.id = 'org-modal'; m.className = 'modal'; document.body.appendChild(m); }
  const scen = data.scenarios.filter((s) => o.scenarios.includes(s.id));
  m.innerHTML = `<div class="modal-box" role="dialog" aria-modal="true" aria-label="Perfil de ${e(o.name)}">
    <header class="modal-h"><div><h3>${e(o.name)}</h3><div class="row gap mt8">${natTag(o.nature)}<span class="muted sm">${e(o.kind)}</span></div></div><button class="icon-btn" data-close aria-label="Fechar">×</button></header>
    <p>${e(o.about)}</p>
    <dl class="kv"><dt>Setor</dt><dd>${e(o.sector)}</dd><dt>Dados conectados</dt><dd>${e(o.data)}</dd>${o.cnpj_root ? `<dt>Raiz do CNPJ</dt><dd><code>${e(o.cnpj_root)}</code> (identificação no SIGBM)</dd>` : ''}
      <dt>Normas monitoradas</dt><dd>${scen.length ? scen.map((s) => `${e(s.name)} <span class="muted">(${e(s.subtitle)})</span>`).join('<br>') : '—'}</dd>
      <dt>Fontes públicas</dt><dd>${refs(o.sources) || '—'}</dd></dl>
    <p class="hint">${e(data.orgNotice)}</p></div>`;
  m.hidden = false;
  const close = () => { m.hidden = true; };
  m.querySelector('[data-close]').onclick = close; m.onclick = (ev) => { if (ev.target === m) close(); };
  document.addEventListener('keydown', function esc(ev) { if (ev.key === 'Escape') { close(); document.removeEventListener('keydown', esc); } });
}
