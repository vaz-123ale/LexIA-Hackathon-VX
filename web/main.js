// LexIA — roteador com três experiências: site público, portal do cidadão e painel da empresa.
import { state, data, api, e, fmtDate, fmtDateTime, toast, icon, refreshFindings, refreshReviews, refreshOfficial, refreshMe, currentUser, can, AS_OF_DEFAULT } from './js/core.js';
import { exec, atlas } from './js/ws_exec_atlas.js';
import { impact } from './js/ws_impact.js?v=72';
import { decision } from './js/ws_decision.js';
import { gov } from './js/ws_gov.js';
import { inicio, sobre, entrar, cadastro, cidadao } from './js/site.js?v=visual40';
import { openDrawer, closeDrawer } from './js/drawer.js';
import { radar } from './js/ws_radar.js';
import { ia } from './js/ws_ia.js?v=65';
import { negocio } from './js/ws_business.js';
import { compliancePage } from './js/ws_compliance.js?v=73';
import { denunciaPage, denunciaAnonimaPage } from './js/ws_denuncia.js?v=72';
import { hidroPage } from './js/ws_hidro.js';
import { ativosPage } from './js/ws_ativos.js';
import { minasPage } from './js/ws_minas.js';
import { fechamentoPage, outorgasPage, abastecimentoPage, radiologicoPage } from './js/ws_radar_setor.js';
import { contasPage } from './js/ws_contas.js';
import { perfilPage } from './js/ws_perfil.js';
import { equipePage, convitePage } from './js/ws_equipe.js?v=67';
import { extratorPage } from './js/ws_extrator.js';
import { relatorioPage } from './js/ws_relatorio.js?v=67';
import { sistemasPage } from './js/ws_sistemas.js?v=72';
import { transparencia } from './js/ws_transparencia.js?v=63';
import { mountBubble } from './js/bubble.js';

const ROUTES = { inicio, sobre, entrar, cadastro, cidadao, exec, atlas, radar, impact, decision, gov, ia, negocio, compliance: compliancePage, denuncia: denunciaPage, 'denuncia-anonima': denunciaAnonimaPage, hidro: hidroPage, ativos: ativosPage, minas: minasPage, fechamento: fechamentoPage, outorgas: outorgasPage, abastecimento: abastecimentoPage, radiologico: radiologicoPage, contas: contasPage, perfil: perfilPage, equipe: equipePage, convite: convitePage, extrator: extratorPage, sistemas: sistemasPage, relatorio: relatorioPage, transparencia };
// Menu da empresa em GRUPOS; dentro de cada grupo, abas. O perfil da empresa decide quais abas aparecem.
const GROUPS = [['exec', 'Visão Executiva', 'home', ['exec']],
  ['operacao', 'Operação & Ativos', 'pin', ['ativos', 'radiologico', 'minas', 'fechamento', 'radar', 'atlas', 'outorgas', 'hidro', 'abastecimento']],
  ['conformidade', 'Conformidade', 'shield', ['compliance', 'impact', 'extrator', 'sistemas', 'decision', 'denuncia', 'gov']],
  ['ia', 'Central de IA', 'spark', ['ia']],
  ['relatorio', 'Relatório da empresa', 'doc', ['relatorio']],
  ['equipe', 'Equipe e acessos', 'users', ['equipe']]];
// Acesso por módulo (regra acessos-v1): a gestão marca o que cada pessoa vê; o servidor também fecha a API.
const ROUTE_MOD = { exec: 'visao', ativos: 'operacao', radiologico: 'operacao', minas: 'operacao', fechamento: 'operacao', radar: 'operacao', atlas: 'operacao', outorgas: 'operacao',
  hidro: 'operacao', abastecimento: 'operacao', compliance: 'conformidade-tela', impact: 'conformidade', decision: 'conformidade', gov: 'conformidade', extrator: 'obrigacoes', sistemas: 'sistemas',
  denuncia: 'denuncias', ia: 'ia', relatorio: 'relatorio' };
const ADMIN = ['gestor', 'compliance', 'juridico'];
export const podeModulo = (m) => { const u = currentUser(); if (!u || u.kind !== 'empresa' || !Array.isArray(u.modulos)) return true;
  return m === 'conformidade-tela' ? ['conformidade', 'denuncias', 'documentos'].some((x) => u.modulos.includes(x)) : u.modulos.includes(m); };
// Negócio & impacto e Contas-alvo são material da equipe para a banca: saem do menu (continuam em #/negocio e #/contas).
const SUB = { ativos: 'Mapa de ativos', minas: 'Minas', fechamento: 'Fechamento de minas', radar: 'Barragens de mineração', atlas: 'Atlas ANM',
  outorgas: 'Usinas e outorgas', hidro: 'Reservatórios (ONS)', abastecimento: 'Barragens de abastecimento', radiologico: 'Instalações radiológicas', compliance: 'Alertas', extrator: 'Norma → obrigação', sistemas: 'Impacto em sistemas', impact: 'Mudanças normativas',
  decision: 'Decisão & execução', denuncia: 'Denúncias', negocio: 'Negócio & impacto', contas: 'Contas-alvo', gov: 'Fontes & governança' };
const ALWAYS = ['exec', 'ia', 'negocio', 'contas', 'gov', 'perfil', 'equipe'];
const perfilAtual = () => (data.empresas || []).find((c) => c.id === state.perfil) || (data.empresas || [])[0];
const ocultos = () => { try { return JSON.parse(localStorage.getItem('lexia.ocultos.' + state.perfil) || '[]'); } catch { return []; } };
function visible(id) {
  const u = currentUser();
  if (id === 'equipe') return !!u && ADMIN.includes(u.role);
  if (ROUTE_MOD[id] && !podeModulo(ROUTE_MOD[id])) return false;
  if (id === 'relatorio') return true;
  if (ALWAYS.includes(id)) return true;
  const p = perfilAtual();
  if (!p) return true;
  return p.rotas.includes(id) && !ocultos().includes(id);
}
const groupOf = (id) => GROUPS.find((g) => g[3].includes(id));
const groupRoutes = (g) => g[3].filter(visible);
const COMPANY = [['exec', 'Visão Executiva', 'home'], ['ativos', 'Ativos & Mapa', 'pin'], ['compliance', 'Compliance & Alertas', 'shield'], ['impact', 'Mudanças normativas', 'flask'], ['decision', 'Decisão & Execução', 'check'], ['minas', 'Minas & substâncias', 'mine'], ['radar', 'Barragens (radar)', 'alert'], ['hidro', 'Monitoramento ONS', 'chart'], ['atlas', 'Atlas oficial ANM', 'layers'], ['denuncia', 'Denúncia assistida', 'doc'], ['gov', 'Fontes & Governança', 'refresh'], ['ia', 'Central de IA', 'spark'], ['negocio', 'Negócio & Impacto', 'star']];
const CITIZEN = [['cidadao', 'Minha região', 'pin'], ['denuncia', 'Fazer denúncia', 'doc'], ['transparencia', 'Transparência', 'chart'], ['radar', 'Barragens sem manutenção', 'alert'], ['ia', 'Central de IA', 'spark']];
const SHORT = { exec: 'Visão', atlas: 'Atlas', impact: 'Impacto', decision: 'Decisão', gov: 'Fontes', cidadao: 'Região', inicio: 'Início', sobre: 'Sobre', radar: 'Radar', ia: 'IA', negocio: 'Negócio', compliance: 'Alertas', denuncia: 'Denúncia', hidro: 'ONS', ativos: 'Ativos', minas: 'Minas', transparencia: 'Transparência', contas: 'Contas' };
const LEGACY = { command: 'exec', map: 'atlas', globe: 'atlas', time: 'impact', simulator: 'impact', chain: 'impact', graph: 'impact', assistant: 'ia', abandono: 'radar', orfas: 'radar', reviews: 'decision', evidence: 'decision', sources: 'gov', integrations: 'gov', checklist: 'gov', login: 'entrar', home: 'inicio' };

const content = document.getElementById('content');
let rendering = 0, leaveHooks = [], installPrompt = null, notes = { items: [], unread: 0 };
const ctx = { rerender, go, setDate, onLeave: (fn) => leaveHooks.push(fn) };
window.addEventListener('beforeinstallprompt', (ev) => { ev.preventDefault(); installPrompt = ev; });
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));

const navFor = () => (currentUser()?.kind === 'cidadao' ? CITIZEN : COMPANY);

function renderPublicChrome() {
  closeDrawer();
  document.getElementById('assistant-rail')?.remove();
  document.body.className = 'mode-public';
  const u = currentUser();
  document.querySelectorAll('.site-nav a').forEach((a) => a.classList.toggle('on', a.dataset.r === state.route));
  document.getElementById('site-actions').innerHTML = u
    ? `<a class="btn primary" href="${u.kind === 'cidadao' ? '#/cidadao' : '#/exec'}">Meu painel ${icon('arrow')}</a><button class="btn ghost" id="logout-pub">Sair</button>`
    : `<a class="btn ghost" href="#/entrar">Entrar</a><a class="btn primary hide-sm" href="#/cadastro">Criar conta</a>`;
  document.getElementById('logout-pub')?.addEventListener('click', logout);
}

function renderAppChrome() {
  const u = currentUser(), cid = u.kind === 'cidadao';
  document.body.className = 'mode-app ' + (cid ? 'is-citizen' : 'is-company');
  // Contexto exclusivamente decorativo: páginas de assunto fixo prevalecem
  // sobre o perfil. Não participa de consultas, regras ou filtros de dados.
  const visualTopic = { minas: 'mineracao', hidro: 'energia', radar: 'barragens', atlas: 'barragens', negocio: 'mineracao' };
  // empresa: a imagem segue SEMPRE o perfil escolhido (todas as abas); cidadão/público: o tema da página
  document.body.dataset.visualSector = cid ? (visualTopic[state.route] || '') : (perfilAtual()?.setor || visualTopic[state.route] || '');
  const pending = data.reviews.filter((r) => ['not_assigned', 'pending_review', 'reviewing'].includes(r.axes?.workflow_state)).length;
  const items = navFor();
  if (!cid) {
    const cur = groupOf(state.route)?.[0];
    const gs = GROUPS.filter((g) => groupRoutes(g).length);
    const first = (g) => { const r = groupRoutes(g); return r.includes(state.last?.[g[0]]) ? state.last[g[0]] : r[0]; };
    document.getElementById('nav').innerHTML = gs.map((g) => { const n = groupRoutes(g).length, on = cur === g[0];
      return `<a class="nav-item ${on ? 'active' : ''}" href="#/${first(g)}" ${on ? 'aria-current="page"' : ''}>${icon(g[2])}<span>${g[1]}</span>${g[0] === 'conformidade' && pending ? `<b class="badge" title="Avaliações pendentes">${pending}</b>` : n > 1 ? `<span class="nav-n">${n}</span>` : ''}</a>`; }).join('');
    document.getElementById('bottom-nav').innerHTML = gs.map((g) => `<a href="#/${first(g)}" class="${cur === g[0] ? 'active' : ''}" aria-label="${g[1]}">${icon(g[2])}${g[1].split(' ')[0]}</a>`).join('');
  } else {
  document.getElementById('nav').innerHTML = items.map(([id, label, ic]) => `<a class="nav-item ${state.route === id ? 'active' : ''}" href="#/${id}" ${state.route === id ? 'aria-current="page"' : ''}>${icon(ic)}<span>${label}</span>${id === 'decision' && pending ? `<b class="badge" title="Avaliações pendentes">${pending}</b>` : ''}</a>`).join('');
  document.getElementById('bottom-nav').innerHTML = items.map(([id, label, ic]) => `<a href="#/${id}" class="${state.route === id ? 'active' : ''}" aria-label="${label}">${icon(ic)}${SHORT[id]}</a>`).join('');
  }
  document.getElementById('side-mode-t').textContent = cid ? 'LexIA Cidadão' : 'Modo: Demonstração';
  document.getElementById('side-mode-s').textContent = cid ? 'Informação pública da ANM' : 'Dados oficiais + cenários controlados';
  document.getElementById('reset-demo').hidden = !can('demo.reset');
  const h = data.health, llm = h.llm;
  document.getElementById('assistant-rail')?.remove(); // substituído pela bolinha (mini-chat) e pela página Central de IA
  const initials = u.name.split(' ').map((p) => p[0]).filter((c) => /[A-ZÁ-Ú]/i.test(c)).slice(0, 2).join('').toUpperCase();
  document.getElementById('topbar-ctx').innerHTML = `
    <form id="gsearch" class="gsearch" role="search">${icon('search')}<input id="gq" placeholder="Buscar estrutura, norma, empresa, CNPJ ou município…" aria-label="Busca global"><kbd>Ctrl + K</kbd></form>
    <span class="tb-div"></span>
    <label class="tb-pill tb-date" title="Data-base da análise (vigência por dispositivo)">${icon('cal')}<span class="tb-2"><small>Data-base</small><input type="date" id="asof" value="${state.asOf}" min="2020-01-01" max="2035-12-31" aria-label="Data-base"></span>${icon('chevron','chev')}</label>
    ${state.asOf !== AS_OF_DEFAULT ? `<button class="tb-pill warn" id="asof-reset" title="Voltar para ${fmtDate(AS_OF_DEFAULT)}">Simulando · voltar ×</button>` : ''}
    ${cid || !data.empresas?.length ? '' : `<div class="dd"><button class="tb-perfil" id="perfil-btn" aria-expanded="false" title="O perfil escolhe os módulos, os dados e os alertas mostrados">${icon('building')}<span><small>Perfil da empresa</small><b>${e(perfilAtual().setor_nome)}</b></span>${icon('chevron', 'chev')}</button><div class="dd-panel perfil-panel" id="perfil-panel" hidden></div></div>`}
    ${cid ? '' : `<button class="tb-pill tb-opt" data-go-tab="gov:connectors" title="Fontes oficiais conectadas">${icon('layers')}<span class="tb-2"><small>Fontes oficiais</small><b>SIGBM · ANM · +${h.sources - 2}</b></span>${icon('chevron', 'chev')}</button>`}
    <a class="tb-ia ${state.route === 'ia' ? 'on' : ''}" href="#/ia" title="${llm.enabled ? 'IA generativa conectada, com verificador' : 'IA em modo controlado (regras e respostas pré-validadas)'}" aria-label="Abrir Central de IA">${icon('spark')}<span>IA</span><i class="${llm.enabled ? 'on' : ''}"></i></a>
    <div class="dd"><button class="icon-btn bell" id="bell" aria-label="Notificações (${notes.unread} não lidas)" aria-expanded="false">${icon('bell')}${notes.unread ? '<i class="dot"></i>' : ''}</button><div class="dd-panel" id="bell-panel" hidden></div></div>
    <div class="dd"><button class="avatar ${u.avatar ? 'has-photo' : ''}" id="avatar" aria-label="Conta de ${e(u.name)}" aria-expanded="false">${u.avatar ? `<img src="${e(u.avatar)}" alt="">` : e(initials || '?')}</button><div class="dd-panel" id="avatar-panel" hidden>
      <div class="me"><b>${e(u.name)}</b><small>${e(u.email || '')}</small><small>${cid ? 'Conta de cidadão' : `${e(u.org_name || '')} · papel: ${e(u.role)}`}</small></div>
      ${cid ? '' : '<button class="dd-item" data-ask>Perguntar sobre esta análise</button>'}
      ${installPrompt ? '<button class="dd-item" id="install-app">Instalar como aplicativo</button>' : ''}
      <a class="dd-item" href="#/perfil">${icon('user')} Meu perfil</a>
      ${cid ? '' : `<a class="dd-item" href="#/equipe">${icon('users')} Equipe e permissões</a>`}
      <a class="dd-item" href="#/sobre">Sobre e privacidade</a><button class="dd-item danger" id="logout">${icon('logout')} Sair</button></div></div>`;
  const q = (id) => document.getElementById(id);
  q('asof').addEventListener('change', (ev) => ev.target.value && setDate(ev.target.value));
  q('asof-reset')?.addEventListener('click', () => setDate(AS_OF_DEFAULT));
  q('gsearch').addEventListener('submit', (ev) => { ev.preventDefault(); if (cid) { go('cidadao'); return; } state.atlas.q = q('gq').value; state.atlas.page = 0; go('atlas'); });
  q('logout').addEventListener('click', logout);
  q('install-app')?.addEventListener('click', async () => { installPrompt.prompt(); await installPrompt.userChoice; installPrompt = null; renderAppChrome(); });
  const toggle = (btn, panel, fill) => { q(btn).addEventListener('click', (ev) => { ev.stopPropagation(); const p = q(panel), open = p.hidden; document.querySelectorAll('.dd-panel').forEach((x) => { x.hidden = true; }); p.hidden = !open; q(btn).setAttribute('aria-expanded', String(open)); if (open && fill) fill(p); }); };
  toggle('avatar', 'avatar-panel');
  if (q('perfil-btn')) toggle('perfil-btn', 'perfil-panel', (p) => {
    const P = perfilAtual(), oc = ocultos(), ops = P.rotas.filter((r) => groupOf(r)?.[0] === 'operacao');
    p.innerHTML = `<div class="dd-h"><b>Perfil da empresa</b></div>${data.empresas.map((c) => `<button class="perfil-opt ${c.id === P.id ? 'on' : ''}" data-perfil="${e(c.id)}">${icon(c.setor === 'mineracao' ? 'mine' : c.setor === 'energia' ? 'generator' : c.setor === 'nuclear' ? 'alert' : 'pipe')}<span><b>${e(c.setor_nome)}</b><small>${e(c.nome)}</small></span></button>`).join('')}
      <div class="perfil-mods"><h5>Módulos de operação deste perfil</h5>${ops.map((r) => `<label><input type="checkbox" data-mod="${r}" ${oc.includes(r) ? '' : 'checked'}> ${e(SUB[r])}</label>`).join('')}<p class="hint">A empresa liga só o que usa. Mesmo núcleo, interface diferente.</p></div>`;
    p.querySelectorAll('[data-perfil]').forEach((b) => b.addEventListener('click', () => setPerfil(b.dataset.perfil)));
    p.querySelectorAll('[data-mod]').forEach((c) => c.addEventListener('change', () => {
      const o = new Set(ocultos());
      if (c.checked) o.delete(c.dataset.mod); else o.add(c.dataset.mod);
      if (!P.rotas.some((r) => groupOf(r)?.[0] === 'operacao' && !o.has(r))) { c.checked = true; toast('Deixe pelo menos um módulo de operação.', 'err'); return; }
      localStorage.setItem('lexia.ocultos.' + state.perfil, JSON.stringify([...o]));
      if (!visible(state.route)) go(groupRoutes(groupOf(state.route))[0]); else rerender();
    }));
  });
  toggle('bell', 'bell-panel', async (p) => {
    p.innerHTML = `<div class="dd-h"><b>Notificações</b>${notes.unread ? '<button class="link" id="read-all">Marcar como lidas</button>' : ''}</div>` + (notes.items.length ? notes.items.slice(0, 8).map((n) => `<a class="note ${n.read ? '' : 'unread'}" href="${e(n.link || '#')}"><span class="note-k k-${e(n.kind)}">${e({ norma: 'Fonte', dados: 'Dados', alerta: 'Alerta' }[n.kind] || n.kind)}</span><strong>${e(n.title)}</strong><small>${e(n.body)}</small><small>${fmtDateTime(n.created_at)}</small></a>`).join('') : '<p class="muted sm pad">Sem notificações. O monitor de fontes avisa aqui quando um canal oficial muda.</p>');
    p.querySelector('#read-all')?.addEventListener('click', async () => { await api('/api/notifications/read', { ids: notes.items.map((n) => n.id) }); await loadNotes(); renderAppChrome(); });
  });
}

async function setPerfil(id) {
  state.perfil = id; localStorage.setItem('lexia.perfil', id);
  await loadNotes();
  state.atv = { ...(state.atv || {}), empresa: id, aba: null, sel: null }; state.comp = { ...(state.comp || {}), org: id, sel: null };
  toast(`Perfil: ${perfilAtual().setor_nome}. Mesmo sistema, módulos e dados desta empresa.`);
  if (!visible(state.route)) go(groupRoutes(groupOf(state.route) || GROUPS[0])[0] || 'exec'); else rerender();
}
function subtabs() {
  const u = currentUser();
  if (!u || u.kind === 'cidadao') return '';
  const g = groupOf(state.route); if (!g) return '';
  const rs = groupRoutes(g); if (rs.length < 2 && rs[0] === state.route) return '';
  state.last = { ...(state.last || {}), [g[0]]: state.route };
  const P = perfilAtual();
  return `<nav class="subtabs" aria-label="${e(g[1])}"><span class="sg">${e(g[1])}</span>${rs.map((r) => `<a href="#/${r}" class="${r === state.route ? 'on' : ''}" ${r === state.route ? 'aria-current="page"' : ''}>${e(SUB[r] || r)}</a>`).join('')}${g[0] === 'operacao' && P ? `<span class="perfil-tag">Perfil: ${e(P.nome)}</span>` : ''}</nav>`;
}
async function loadNotes() { try { notes = await api('/api/notifications' + (state.perfil && currentUser()?.kind === 'empresa' ? '?empresa=' + encodeURIComponent(state.perfil) : '')); } catch { notes = { items: [], unread: 0 }; } }
async function logout() { data.empresas = null; await api('/api/auth/logout', { x: 1 }).catch(() => {}); await refreshMe(); toast('Você saiu.'); go('inicio'); }

async function rerender() {
  const my = ++rendering;
  leaveHooks.forEach((f) => f()); leaveHooks = [];
  const page = ROUTES[state.route];
  const pub = page.public && !(page.inApp && currentUser());   // logado: páginas públicas "de dentro" abrem sem sair da conta
  if (pub) renderPublicChrome(); else renderAppChrome();
  try {
    const html = await page.render();
    if (my !== rendering) return;
    content.dataset.page = state.route;
    content.innerHTML = subtabs() + html;
    await page.mount?.(content, ctx);
    mountBubble(!pub && podeModulo('ia'));
  } catch (err) {
    console.error(err);
    content.innerHTML = `<div class="card"><h3>Não foi possível carregar esta página</h3><p class="muted">${e(err.message)}</p><button class="btn" data-reload>Tentar novamente</button></div>`;
    content.querySelector('[data-reload]')?.addEventListener('click', () => location.reload());
  }
}
async function setDate(iso) {
  closeDrawer();
  state.asOf = iso;
  try { await Promise.all([refreshFindings(), refreshReviews(), refreshOfficial()]); } catch (err) { toast(err.message, 'err'); state.asOf = AS_OF_DEFAULT; await refreshFindings(); }
  await rerender();
}
function go(r) { if (location.hash !== `#/${r}`) location.hash = `#/${r}`; else rerender(); }

async function route() {
  closeDrawer();
  let id = location.hash.replace('#/', '').split('?')[0] || 'inicio';
  id = ROUTES[id] ? id : (LEGACY[id] || 'inicio');
  const u0 = currentUser();
  if (u0 && id === 'inicio') { id = u0.kind === 'cidadao' ? 'cidadao' : 'exec'; history.replaceState(null, '', '#/' + id); }   // logado: o logo leva ao início da conta, não ao site
  const u = u0, page = ROUTES[id];
  if (!page.public && !u) { state.authTab = 'empresa'; toast('Entre para acessar o painel.'); id = 'entrar'; history.replaceState(null, '', '#/entrar'); }
  else if (u && u.kind === 'cidadao' && !page.public && !page.citizen) { id = 'cidadao'; history.replaceState(null, '', '#/cidadao'); }
  else if (u && u.kind === 'empresa' && page.citizen && !page.both) { id = 'exec'; history.replaceState(null, '', '#/exec'); }
  else if (u && u.kind === 'empresa' && !ROUTES[id].public && ((ROUTE_MOD[id] && !podeModulo(ROUTE_MOD[id])) || (id === 'equipe' && !ADMIN.includes(u.role)))) {   // módulo não liberado
    const alvo = GROUPS.flatMap((g) => g[3]).find((r) => ROUTE_MOD[r] && podeModulo(ROUTE_MOD[r])) || 'perfil'; toast('Esta área não foi liberada para você pela gestão da empresa.'); id = alvo; history.replaceState(null, '', '#/' + id); }
  else if (u && ['negocio', 'contas'].includes(id) && u.role !== 'curador') { id = u.kind === 'cidadao' ? 'cidadao' : 'exec'; history.replaceState(null, '', '#/' + id); }   // área interna da equipe LexIA
  state.route = id; state.ws = id;
  if (u && (!page.public || page.inApp)) { await Promise.all([refreshReviews().catch(() => {}), loadNotes()]); }
  if (u && u.kind === 'empresa' && !data.empresas) {
    data.empresas = (await api('/api/ativos/empresas').catch(() => ({ items: [] }))).items;
    const saved = localStorage.getItem('lexia.perfil');
    state.perfil = data.empresas.some((c) => c.id === saved) ? saved : data.empresas[0]?.id;
    if (state.perfil) { state.atv = { ...(state.atv || {}), empresa: state.perfil }; state.comp = { ...(state.comp || {}), org: state.perfil }; }
  }
  await rerender(); content.focus({ preventScroll: true }); window.scrollTo(0, 0);
}

document.addEventListener('click', (ev) => {
  if (ev.target.closest('[data-project-open]')) { closeDrawer();state.projectOpen = true; state.projectScroll=true; go('impact'); return; }
  if (!ev.target.closest('.dd')) document.querySelectorAll('.dd-panel').forEach((x) => { x.hidden = true; });
  const assistant = ev.target.closest('[data-assistant-tab]'); if (assistant) { openDrawer(assistant.dataset.assistantTab); return; }
  const at = ev.target.closest('[data-auth-tab]'); if (at) state.authTab = at.dataset.authTab;
  const gt = ev.target.closest('[data-go-tab], [data-tab-go]');
  if (gt) { closeDrawer();const [ws, t] = (gt.dataset.goTab || gt.dataset.tabGo).split(':'); state.tab[ws] = t; ev.preventDefault(); go(ws); return; }
  const g = ev.target.closest('[data-go]'); if (g) { ev.preventDefault(); go(g.dataset.go); return; }
  const t = ev.target.closest('[data-tab]'); if (t) { const [ws, id] = t.dataset.tab.split(':'); state.tab[ws] = id; rerender(); return; }
  const r = ev.target.closest('[data-open-review]'); if (r) { state.openReview = r.dataset.openReview; state.tab.decision = 'reviews'; go('decision'); return; }
  const a = ev.target.closest('[data-analyze]'); if (a) { const [sc] = a.dataset.analyze.split(':'); state.scenario = sc; state.lab = { ...(state.lab || {}), sel: a.dataset.analyze, portfolio: a.dataset.analyze.includes('SIGBM-') ? 'official' : 'synthetic' }; go('impact'); return; }
  if (ev.target.closest('[data-ask]')) openDrawer();
});
document.addEventListener('change', (ev) => {
  const b = ev.target.closest('[data-bind]');
  if (b) { state[b.dataset.bind] = b.value; if (b.dataset.bind === 'scenario' && state.lab) state.lab.sel = null; rerender(); return; }
  if (ev.target.matches('[data-bind-date]') && ev.target.value) setDate(ev.target.value);
});
document.addEventListener('keydown', (ev) => { if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') { const q = document.getElementById('gq'); if (q) { ev.preventDefault(); q.focus(); } } });
document.getElementById('reset-demo').addEventListener('click', async () => {
  if (!confirm('Reiniciar o estado DEMO (revisões, evidências, cenários financeiros e trilha)? Contas, fontes, snapshots e originais são preservados.')) return;
  try { await api('/api/admin/reset', { confirm: true }); await refreshReviews(); state.openReview = null; toast('Estado DEMO reiniciado.'); rerender(); } catch (err) { toast(err.message, 'err'); }
});
document.getElementById('menu-btn').addEventListener('click', () => document.body.classList.toggle('nav-open'));
window.addEventListener('hashchange', () => { document.body.classList.remove('nav-open'); route(); });

async function boot() {
  try {
    const [health, assets, sources, scenarios, map, states, world, connectors, checklist, timeline, users, rivers] = await Promise.all([
      api('/api/health'), api('/api/assets'), api('/api/sources'), api('/api/scenarios'), fetch('/map.json').then((r) => r.json()), fetch('/br_uf.json').then((r) => r.json()).catch(() => null),
      fetch('/world.json').then((r) => r.json()).catch(() => null), api('/api/connectors'), api('/api/checklist'), api('/api/timeline'), api('/api/demo/users'),fetch('/rivers.json').then(r=>r.json()).catch(()=>null)]);
    Object.assign(data, { health, assets, sources, scenarios, map, states, world, connectors, checklist, timeline, rivers, users: users.users, permissions: users.permissions });
    await Promise.all([refreshMe(), refreshFindings()]);
    await route();
  } catch (err) {
    content.innerHTML = `<div class="card"><h3>Servidor não encontrado</h3><p>Inicie com <code>python -m app.server</code> na raiz do projeto e abra <code>http://localhost:8765</code>.</p><p class="muted">${e(err.message)}</p></div>`;
  }
}
boot();
