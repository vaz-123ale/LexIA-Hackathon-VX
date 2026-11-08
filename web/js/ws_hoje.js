// "Hoje" e "Aprovar": as duas telas de entrada do app no celular (servem também no computador).
// Só reúnem o que já existe: alertas por regra (compliance-v1), avaliações normativas, denúncias recebidas,
// obrigações propostas e impacto em sistemas. Nenhuma decisão é tomada aqui: cada item abre a tela completa,
// onde a pessoa lê a fonte e registra a decisão (a IA propõe, regras verificam, humano confirma).
import { state, data, api, e, icon, fmtDate, currentUser } from './core.js';

const PEND_REV = ['not_assigned', 'pending_review', 'reviewing'];
const DST = { RECEBIDA: 'Recebida', EM_APURACAO: 'Em apuração', RESPONDIDA: 'Respondida' };
const pode = (m) => { const u = currentUser(); if (!u || u.kind !== 'empresa' || !Array.isArray(u.modulos)) return true; return u.modulos.includes(m); };
const perfil = () => (data.empresas || []).find((c) => c.id === state.perfil) || (data.empresas || [])[0];
const qEmp = () => (state.perfil ? '?empresa=' + encodeURIComponent(state.perfil) : '');
const ok = (p) => p.catch(() => null);

async function carregar() {
  const [comp, den, obr, sis] = await Promise.all([
    pode('conformidade') ? ok(api('/api/compliance' + (state.perfil ? '?org=' + encodeURIComponent(state.perfil) : ''))) : null,
    pode('denuncias') ? ok(api('/api/denuncias/recebidas' + qEmp())) : null,
    pode('obrigacoes') ? ok(api('/api/obrigacoes' + qEmp())) : null,
    pode('sistemas') && perfil()?.rotas?.includes('sistemas') ? ok(api('/api/sistemas' + qEmp())) : null]);
  const alertas = (comp?.items || []).filter((a) => a.status !== 'RESOLVIDO');
  const critico = alertas.filter((a) => ['Crítico', 'Alto'].includes(a.level) && (a.urgency === 'Agora' || a.safety));
  const prazos = alertas.filter((a) => a.urgency === 'Vencido' || (a.days_to_due != null && a.days_to_due <= 7));
  const denAbertas = (den?.items || []).filter((d) => d.dest_state !== 'RESPONDIDA');
  const revisoes = pode('conformidade') ? (data.reviews || []).filter((r) => PEND_REV.includes(r.axes?.workflow_state)) : [];
  const obrigacoes = (obr?.items || []).filter((o) => !['CONFIRMADA', 'REJEITADA'].includes(o.state));
  const mudancas = sis?.mudancas || [];
  return { comp, alertas, critico, prazos, denAbertas, revisoes, obrigacoes, mudancas, sis };
}

const chip = (txt, cls) => `<span class="mb-chip ${cls}">${e(txt)}</span>`;
const linha = (attrs, c, titulo, sub) => `<button class="mb-row" type="button" ${attrs}>${c}<span class="mb-row-t"><b>${e(titulo)}</b><small>${e(sub)}</small></span>${icon('chevron', 'mb-go')}</button>`;
const secao = (n, titulo, corpo, extra = '') => `<section class="mb-sec"><h3><i>${n}</i>${e(titulo)}${extra}</h3>${corpo}</section>`;
const vazio = (txt) => `<p class="mb-empty">${icon('check')} ${e(txt)}</p>`;
const NIV = { 'Crítico': 'crit', 'Alto': 'alta', 'Médio': 'med', 'Baixo': 'baixa' };

function abrirAlerta(id) { state.comp = { ...(state.comp || {}), tab: 'alertas', sel: id, org: state.perfil }; state.scrollSel = 'article.cp-alert'; location.hash = '#/compliance'; }
function abrirDenuncias() { state.comp = { ...(state.comp || {}), tab: 'denuncias', org: state.perfil }; location.hash = '#/compliance'; }
function ligar(root) {
  root.querySelectorAll('[data-mb-alerta]').forEach((b) => b.addEventListener('click', () => abrirAlerta(b.dataset.mbAlerta)));
  root.querySelectorAll('[data-mb-den]').forEach((b) => b.addEventListener('click', abrirDenuncias));
  root.querySelectorAll('[data-mb-href]').forEach((b) => b.addEventListener('click', () => { location.hash = b.dataset.mbHref; }));
}

function saudacao() { const h = new Date().getHours(); return h < 12 ? 'Bom dia' : h < 18 ? 'Boa tarde' : 'Boa noite'; }

export const hojePage = {
  title: 'Hoje',
  async render() {
    const u = currentUser(), P = perfil(), D = await carregar();
    const nAprovar = D.revisoes.length + D.denAbertas.filter((d) => d.dest_state === 'RECEBIDA').length + D.obrigacoes.length;
    const ativosPrio = new Set([...D.critico, ...D.prazos].map((a) => a.asset_id)).size;
    const semPessoa = D.alertas.filter((a) => (a.recipients || []).some((r) => r.sem_pessoa)).length;
    const lista = (xs, max = 3) => xs.slice(0, max).map((a) => linha(`data-mb-alerta="${e(a.id)}"`, chip(a.urgency === 'Vencido' ? 'Vencido' : a.level, NIV[a.level] || 'med'), a.title, `${a.asset_name} · ${a.urgency}${a.safety ? ' · segurança' : ''}`)).join('');
    const mais = (xs, max = 3) => (xs.length > max ? `<a class="mb-more" href="#/compliance">Ver os ${xs.length} ${icon('arrow')}</a>` : '');
    return `<div class="mb-page">
      <header class="mb-hero"><span class="eyebrow">Panorama regulatório · ${e(P?.setor_nome || '')}</span>
        <h2>Hoje</h2><p>${saudacao()}, ${e((u.name || '').split(' ')[0])}. Prioridades, decisões e prazos de <b>${e(P?.nome || u.org_name || 'sua empresa')}</b> em ${e(fmtDate(state.asOf))}.</p></header>
      <div class="mb-stats">
        <a href="#/compliance" class="mb-stat s-crit"><b>${D.critico.length}</b><small>crítico agora</small></a>
        <a href="#/aprovar" class="mb-stat s-apr"><b>${nAprovar}</b><small>para aprovar</small></a>
        <a href="#/compliance" class="mb-stat s-prz"><b>${D.prazos.length}</b><small>prazo vencido ou na semana</small></a>
      </div>
      ${D.comp ? secao('01', 'Crítico agora', D.critico.length ? lista(D.critico) + mais(D.critico) : vazio('Nada crítico para agora neste perfil.')) : ''}
      ${secao('02', 'Para você aprovar', nAprovar ? linha('data-mb-href="#/aprovar"', chip('Decisão', 'dec'), `${nAprovar} ${nAprovar === 1 ? 'decisão pendente' : 'decisões pendentes'}`, 'Leia a fonte e o trecho antes de decidir.') : vazio('Nenhuma decisão esperando por você.'))}
      ${D.comp ? secao('03', 'Prazos vencidos ou da semana', D.prazos.length ? lista(D.prazos) + mais(D.prazos) : vazio('Nenhum prazo vencido ou na semana.')) : ''}
      ${pode('denuncias') ? secao('04', 'Denúncias sem resposta', D.denAbertas.length ? D.denAbertas.slice(0, 3).map((d) => linha('data-mb-den', chip(DST[d.dest_state] || d.dest_state, 'res'), d.ativo || 'Ativo da empresa', `Denúncia #${d.id} · ${d.identificado ? 'denunciante identificado' : 'anônima para a empresa'}`)).join('') : vazio('Todas as denúncias recebidas foram respondidas.')) : ''}
      <div class="mb-sum">
        <p><span>Ativos com alerta prioritário</span><b>${ativosPrio}</b></p>
        <p><span>Alertas sem pessoa no papel</span><b>${semPessoa}</b></p>
        <p><span>Alertas abertos no perfil</span><b>${D.alertas.length}</b></p>
      </div>
      <p class="mb-note">Alertas por regra versionada (${e(D.comp?.rule_version || 'compliance-v1')}), sem IA generativa. Empresa e ativos fictícios de demonstração; normas e fontes reais.</p>
    </div>`;
  },
  mount(root) { ligar(root); },
};

export const aprovarPage = {
  title: 'Aprovar',
  async render() {
    const D = await carregar(), P = perfil();
    const recebidas = D.denAbertas.filter((d) => d.dest_state === 'RECEBIDA');
    const blocos = [];
    if (pode('conformidade')) blocos.push(secao('01', 'Avaliações normativas do grupo', D.revisoes.length ? D.revisoes.slice(0, 6).map((r) => linha(`data-open-review="${e(r.id)}"`, chip('Avaliar', 'dec'), r.headline_now || r.headline, `${r.asset_name || r.asset_id} · ${r.scenario_name || r.scenario}`)).join('') + (D.revisoes.length > 6 ? `<a class="mb-more" href="#/decision">Ver as ${D.revisoes.length} ${icon('arrow')}</a>` : '') : vazio('Nenhuma avaliação esperando decisão.'), `<span class="mb-n">${D.revisoes.length}</span>`));
    if (pode('denuncias')) blocos.push(secao('02', 'Denúncias para triagem', recebidas.length ? recebidas.map((d) => linha('data-mb-den', chip('Recebida', 'res'), d.ativo || 'Ativo da empresa', `Denúncia #${d.id} · abrir o dossiê e o checklist de caminhos`)).join('') : vazio('Nenhuma denúncia nova para triar.'), `<span class="mb-n">${recebidas.length}</span>`));
    if (pode('obrigacoes') && P?.rotas?.includes('extrator')) blocos.push(secao('03', 'Obrigações propostas', D.obrigacoes.length ? D.obrigacoes.slice(0, 4).map((o) => linha('data-mb-href="#/extrator"', chip(o.origem === 'ia' ? 'IA propôs' : 'Regra', 'dec'), o.obrigacao, `${o.prazo || 'sem prazo explícito'} · papel: ${o.papel || '—'}`)).join('') : vazio('Nenhuma obrigação esperando confirmação.'), `<span class="mb-n">${D.obrigacoes.length}</span>`));
    if (D.sis) blocos.push(secao('04', 'Mudanças que afetam sistemas', D.mudancas.length ? D.mudancas.slice(0, 3).map((m) => linha('data-mb-href="#/sistemas"', chip('Código', 'cod'), m.titulo, `${m.norma} · vigência ${fmtDate(m.vigencia)}`)).join('') : vazio('Nenhuma mudança afetando sistemas.')));
    return `<div class="mb-page">
      <header class="mb-hero"><span class="eyebrow">Decisão humana · ${e(P?.setor_nome || '')}</span><h2>Aprovar</h2>
        <p>A IA e as regras propõem; você decide. Cada item abre a tela completa com a fonte, o trecho da norma e o campo do motivo. Nada é publicado ou encaminhado sem o seu aceite.</p></header>
      ${blocos.join('') || '<p class="mb-empty">A gestão da empresa não liberou áreas de decisão para você.</p>'}
      <p class="mb-note">Toda decisão fica registrada na trilha, com quem decidiu, quando e por quê.</p>
    </div>`;
  },
  mount(root) { ligar(root); },
};
