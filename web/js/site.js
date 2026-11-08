// Site público (início, sobre, entrar, cadastro) e Portal do Cidadão.
import { state, data, api, e, fmtDate, fmtDateTime, icon, refs, toast, refreshMe, refreshOfficial, TRIAGE, can } from './core.js';
import { createMap } from './map.js';
import { satView } from './geoview.js';
import { openDrawer } from './drawer.js';
import { streetMap } from './ws_denuncia.js?v=72';

const norm = (s) => String(s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
let heroGlobe = null;

// ------------------------------------------------------------------ INÍCIO
export const inicio = {
  public: true, title: 'Início',
  async render() {
    if (!data.official) await refreshOfficial().catch(() => null);
    const n = data.official?.records?.length || 0, h = data.health;
    const M = await api('/api/minas?limit=1').catch(() => null);
    const logged = data.me.authenticated, home = logged ? (data.me.user.kind === 'cidadao' ? '#/cidadao' : '#/exec') : null;
    return `
    <section class="l-hero">
      <div class="l-hero-txt">
        <span class="pill-soft">${icon('shield')} Risco, conformidade e manutenção · multissetorial</span>
        <h1>Da mudança regulatória à <span class="grad-txt">decisão executável</span>.</h1>
        <p>A LexIA é uma plataforma de <b>gestão de riscos, conformidade e manutenção preventiva</b>: conecta fontes oficiais, vigência por artigo, sensores e os ativos da operação (minas, barragens, usinas, estações, equipamentos) para mostrar <b>o que muda, onde, a partir de quando e quem decide</b>, com prova de cada passo. Mineração, energia, saneamento e nuclear usam o mesmo núcleo: o que muda de uma empresa para outra é a configuração.</p>
        <div class="row gap wrap">${logged ? `<a class="btn primary lg" href="${home}">Ir para o meu painel ${icon('arrow')}</a>` : `<a class="btn primary lg" href="#/entrar" data-auth-tab="empresa">Entrar como empresa ${icon('arrow')}</a><a class="btn lg ghost-light" href="#/entrar" data-auth-tab="cidadao">Sou cidadão</a>`}</div>
        <ul class="l-stats">
          <li><b>${n}</b><span>barragens oficiais do SIGBM/ANM no snapshot de ${fmtDate(data.official?.snapshot?.fetched_at)}</span></li>
          ${M ? `<li><b>${M.total.toLocaleString('pt-BR')}</b><span>minas com título de lavra (ANM/SIGMINE), ${M.radiologico} com sinal radiológico</span></li>` : ''}
          <li><b>${h.sources}</b><span>fontes oficiais catalogadas e monitoradas</span></li>
          <li><b>4 frentes</b><span>mineração, energia, saneamento e nuclear na mesma plataforma</span></li>
        </ul>
      </div>
      <div class="l-hero-frentes" aria-label="As frentes atendidas pela LexIA">${[['sector-mining.jpg', 'Mineração', 'minas, barragens de rejeito, fechamento'], ['sector-energy.jpg', 'Energia', 'usinas, outorgas, subestações'], ['sector-sanitation.jpg', 'Saneamento', 'estações, abastecimento, água'], ['sector-nuclear.jpg?v=nuclear2', 'Nuclear', 'fontes, rejeitos, proteção radiológica']].map(([img, t, d]) => `<figure><img src="/img/brand/${img}" alt=""><figcaption><b>${t}</b><small>${d}</small></figcaption></figure>`).join('')}</div>
    </section>

    <section class="l-sec">
      <div class="l-head"><span class="eyebrow">O problema</span><h2>Normas mudam por partes. As empresas descobrem tarde — e sem rastro.</h2></div>
      <div class="l-grid3">
        <article class="l-card">${icon('doc')}<h3>Fontes espalhadas</h3><p>Diários oficiais, portais de agências e versões históricas em lugares diferentes, com datas que mudam por artigo.</p></article>
        <article class="l-card">${icon('pin')}<h3>Impacto difícil de localizar</h3><p>Saber o que diz a norma não basta: é preciso saber <b>quais unidades</b> são afetadas e o que falta verificar em cada uma.</p></article>
        <article class="l-card">${icon('check')}<h3>Decisão sem prova</h3><p>Quem decidiu, quando, com base em qual versão? Planilhas e e-mails não respondem a um auditor.</p></article>
      </div>
    </section>

    <section class="l-sec">
      <div class="l-head"><span class="eyebrow">Uma plataforma, vários setores</span><h2>O núcleo é o mesmo; o que muda é a configuração</h2></div>
      <div class="l-grid2 sectors">${[['mine', 'Mineração', 'Minas por substância e tipo de lavra, barragens de rejeito, britadores e locais com material radioativo (CNEN/ANSN). Primeiro caso de uso.'],
        ['spark', 'Energia', 'Usinas, barragens de UHE, subestações e transformadores; vazões e níveis do ONS com z-score sazonal e casos análogos (KNN).'],
        ['pipe', 'Saneamento', 'Estações de tratamento, reservatórios e elevatórias; outorgas, licenças e qualidade da água.'],
        ['shield', 'Nuclear e radioativos', 'Minas de urânio, instalações e fontes radioativas, rejeitos e proteção radiológica (CNEN/ANSN). Indústria entra com o mesmo fluxo (NR-13, NR-20).']].map(([ic, t, d], i) => `<article class="l-card l-sector"><img src="/img/brand/${['sector-mining.jpg', 'sector-energy.jpg', 'sector-sanitation.jpg', 'sector-nuclear.jpg?v=nuclear2'][i]}" alt="">${icon(ic)}<h3>${t}</h3><p>${d}</p></article>`).join('')}</div>
      <p class="l-note">${icon('filter')} Cada empresa liga ou desliga módulos (minas, barragens, equipamentos, documentos e licenças, jurídico e compliance), define limites dos sensores e quem recebe cada alerta: <b>a informação certa para a pessoa certa</b>.</p>
    </section>

    <section class="l-sec alt">
      <div class="l-head"><span class="eyebrow">Como funciona</span><h2>Uma cadeia auditável, do Diário Oficial ao dossiê de decisão</h2></div>
      <ol class="l-chain">${[['refresh', 'Monitorar', 'Fontes oficiais verificadas periodicamente, respeitando as regras de cada site.'], ['doc', 'Versionar', 'Cada dispositivo com início e fim de vigência.'], ['pin', 'Cruzar', 'Regras explícitas cruzam o artigo com os atributos de cada ativo.'], ['check', 'Decidir', 'O sistema cria rascunhos; quem decide é uma pessoa com o papel certo.'], ['shield', 'Provar', 'Evidências com hash, trilha encadeada e dossiê exportável.']].map(([ic, t, d], i) => `<li><span class="step-n">${i + 1}</span>${icon(ic)}<h3>${t}</h3><p>${d}</p></li>`).join('')}</ol>
      <p class="l-note">${icon('spark')} <b>A IA propõe, regras verificam, humano decide.</b> A LexIA não emite parecer jurídico nem declara conformidade.</p>
    </section>

    <section class="l-sec">
      <div class="l-head"><span class="eyebrow">IA que gera valor, não só texto</span><h2>Prever onde o próximo problema vai aparecer — e provar o que foi feito</h2></div>
      <div class="l-grid3">
        <article class="l-card">${icon('target')}<h3>Predição validada</h3><p>Modelos treinados nos dados públicos (começando pela ANM) indicam quais barragens tendem a <b>falhar na próxima declaração de estabilidade</b> ou têm perfil de emergência não declarada — 4× mais certeiros que conferir ao acaso.</p></article>
        <article class="l-card">${icon('monitor')}<h3>Agente autônomo</h3><p>A cada dado novo da ANM, o agente verifica fontes, retreina, prioriza e <b>propõe</b> ações. Nada é enviado nem decidido sem uma pessoa aprovar.</p></article>
        <article class="l-card">${icon('shield')}<h3>Prova imutável</h3><p>Fontes, versões, decisões e modelos ficam num cofre com hash (na implantação, AWS S3 Object Lock): o que a empresa sabia e decidiu, e quando.</p></article>
      </div>
    </section>

    <section class="l-sec">
      <div class="l-head"><span class="eyebrow">Para quem</span><h2>Duas experiências, separadas</h2></div>
      <div class="l-grid2">
        <article class="aud aud-emp"><span class="aud-tag">${icon('building')} Empresas</span><h3>Operação regulatória com decisão auditável</h3>
          <ul><li>Ativos & mapa por setor: minas, barragens, usinas, estações e equipamentos, com status e alertas roteados por papel</li><li>Fila de mudanças: publicação oficial → unidade afetada → obrigação com prazo, dono e prova</li><li>Compliance & alertas, denúncias recebidas e documentos isolados por cliente</li><li>Predição por IA e agente que prioriza a conferência</li><li>Atlas com estruturas oficiais e a sua carteira de ativos</li><li>Laboratório de impacto com vigência por artigo</li><li>Revisão por função (jurídico, engenharia, compliance…)</li><li>Dossiê de decisão e trilha de auditoria</li><li>Alertas quando uma fonte oficial muda</li></ul>
          <a class="btn primary" href="#/cadastro" data-auth-tab="empresa">Criar conta empresarial</a></article>
        <article class="aud aud-cid"><span class="aud-tag">${icon('user')} Cidadãos</span><h3>Informação pública em linguagem simples</h3>
          <ul><li>Barragens e minas perto de você (dados oficiais da ANM)</li><li>Denúncia assistida: a LexIA organiza as normas e a empresa responsável recebe</li><li>O que cada classificação significa, sem jargão</li><li>Acompanhar estruturas e receber avisos</li><li>Canais oficiais e telefones de emergência</li></ul>
          <a class="btn" href="#/cadastro" data-auth-tab="cidadao">Criar conta de cidadão</a></article>
      </div>
    </section>

    <section class="l-sec alt">
      <div class="l-head"><span class="eyebrow">Canais oficiais</span><h2>Conectados de verdade — e honestos sobre o que não está</h2></div>
      <div class="l-sources">
        <div class="src ok"><b>ANM · SIGBM</b><span>Conectado · coleta automática quando a ANM publica nova versão</span></div>
        <div class="src ok"><b>ANM · SIGMINE</b><span>Conectado · minas por substância e fase (serviço público)</span></div>
        <div class="src ok"><b>ONS · dados abertos</b><span>Conectado · vazões e níveis dos reservatórios</span></div>
        <div class="src ok"><b>ANA · SNISB</b><span>Conectado · barragens sem empreendedor identificado</span></div>
        <div class="src ok"><b>gov.br (MTE, ANM, ANP, ANSN…)</b><span>Monitorado · alerta quando a página oficial muda</span></div>
        <div class="src ok"><b>ANM Legis</b><span>Monitorado · texto oficial da Res. ANM 245/2026</span></div>
        <div class="src wait"><b>Diário Oficial da União</b><span>A conectar via INLABS (exige credencial). O site bloqueia robôs.</span></div>
        <div class="src wait"><b>LexML</b><span>Bloqueado por verificação anti-robô; requer acordo de acesso.</span></div>
      </div>
    </section>

    <section class="l-cta"><h2>Pronto para ver na prática?</h2><p>Use uma conta de demonstração — empresa ou cidadão — e percorra o fluxo completo.</p>
      <div class="row gap wrap center"><a class="btn primary lg" href="#/entrar" data-auth-tab="empresa">Entrar</a><a class="btn lg ghost-light" href="#/sobre">Sobre o projeto</a></div></section>`;
  },
  mount(root, ctx) {
    const c = root.querySelector('#hero-globe');
    if (c && data.world) {
      import('./globe.js').then(({ createGlobe }) => {
        const pts = (data.official?.records || []).map((r) => ({ id: r.id, lat: r.lat, lon: r.lon, color: '#14315C', label: r.name }));
        heroGlobe = createGlobe(c, { world: data.world, points: pts, labels: false, start: [-50, -12], zoom: 0.92, autoRotate: true, pointSize: 2.2, theme: 'claro' });
        ctx.onLeave(() => heroGlobe?.destroy());
      });
    }
  },
};

// ------------------------------------------------------------------ SOBRE
export const sobre = {
  public: true, inApp: true, title: 'Sobre',
  async render() {
    return `<section class="page-narrow">
      <div class="sobre-banner" aria-hidden="true"></div>
      <span class="eyebrow">Sobre</span><h1>LexIA</h1>
      <p class="lead">Projeto desenvolvido para o Hackathon VX (Desafio 02 · IA para problemas de negócio). Nosso objetivo: transformar mudança regulatória em decisão executável e auditável.</p>
      <div class="about-grid">
        <article class="card"><h3>${icon('target', 'h-ic')}Missão</h3><p>Ligar <b>fonte oficial → artigo → vigência → ativo → decisão humana → evidência</b>, sem esconder incertezas.</p></article>
        <article class="card"><h3>${icon('shield', 'h-ic')}Princípios</h3><ul class="list"><li>A IA propõe; regras versionadas verificam; humano competente decide.</li><li>Dado oficial e cenário hipotético nunca se misturam.</li><li>Sem número inventado: métricas calculadas ou ausentes.</li><li>Na dúvida, abster-se e dizer o que falta.</li></ul></article>
        <article class="card"><h3>${icon('doc', 'h-ic')}O que a LexIA não é</h3><p>Não é parecer jurídico, licença, laudo de engenharia, certificação de segurança nem declaração de conformidade. Empresas citadas aparecem apenas porque constam em cadastros públicos — não são clientes nem parceiras.</p></article>
        <article class="card"><h3>${icon('user', 'h-ic')}Privacidade (LGPD)</h3><p>No cadastro guardamos nome, e-mail, tipo de conta e, para empresas, razão social, CNPJ e função. Senhas são armazenadas com hash (PBKDF2). CPFs presentes em dados públicos são ocultados. Os dados ficam no servidor local desta demonstração.</p></article>
        <article class="card"><h3>${icon('refresh', 'h-ic')}Fontes</h3><p>${data.health.sources} fontes oficiais catalogadas (dossiê de 05/11/2026), SIGBM/ANM e malha de UFs do IBGE. Veja a página <a href="#/gov">Fontes & Governança</a> (empresas) para proveniência e qualidade.</p></article>
        <article class="card"><h3>${icon('alert', 'h-ic')}Limitações atuais</h3><ul class="list"><li>Extração de obrigações: a IA só propõe; uma pessoa confirma cada uma.</li><li>Diário Oficial depende de credencial INLABS.</li><li>Contas de demonstração usam senha pública.</li></ul></article>
      </div></section>`;
  },
};

// ------------------------------------------------------------------ ENTRAR / CADASTRO
const DEMO = { empresa: [['ana@demo.lexia.app', 'Ana · Jurídico'], ['diego@demo.lexia.app', 'Diego · Operação'], ['carla@demo.lexia.app', 'Carla · Engenharia'], ['gabi@demo.lexia.app', 'Gabi · Curadoria']], cidadao: [['joana@demo.lexia.app', 'Joana · Itabirito/MG']] };
const authTabs = (mode) => `<div class="seg big" role="tablist"><button role="tab" data-at="cidadao" class="${state.authTab === 'cidadao' ? 'on' : ''}">${icon('user')} Sou cidadão</button><button role="tab" data-at="empresa" class="${state.authTab === 'empresa' ? 'on' : ''}">${icon('building')} Sou empresa</button></div>`;
const authAside = (login = false) => `<aside class="auth-aside"><img class="auth-logo" src="/img/brand/logo-lexia-v6.png" alt="LexIA">
  ${state.authTab === 'empresa' ? `<h2>Risco, conformidade e manutenção com prova.</h2><ul><li>Módulos do seu setor: minas, barragens, usinas, estações</li><li>Alertas para a pessoa certa, com base legal</li><li>Decisão humana registrada e evidência com hash</li></ul>` : `<h2>Informação pública, sem jargão.</h2><ul><li>Barragens perto de você, com dados da ANM</li><li>O que cada classificação significa</li><li>Avisos e canais oficiais</li></ul>`}
  ${login ? '<div class="auth-art auth-reference-art" aria-hidden="true"><img src="/img/brand/login-reference.jpeg" alt=""></div>' : '<img src="/img/brand/landscape-identity.jpg" alt="" class="auth-art">'}</aside>`;
const quickDemo = () => `<div class="demo-corner" role="region" aria-label="Acesso rápido à demonstração"><b>Acesso rápido · demonstração</b>
        ${[['cidadao', 'Cidadão', 'joana@demo.lexia.app'], ['empresa', 'Empresa', 'ana@demo.lexia.app']].map(([k, l, m]) => `<button type="button" data-quick="${k}" data-mail="${m}"><span class="dc-k">${l}</span><span class="dc-c">${m}<br>senha: LexIA2026demo</span><span class="dc-go">Entrar →</span></button>`).join('')}</div>`;
function bindAuthTabs(root, ctx) { root.querySelectorAll('[data-at]').forEach((b) => b.addEventListener('click', () => { state.authTab = b.dataset.at; ctx.rerender(); })); }
async function afterAuth(ctx, user) { await refreshMe(); toast(`Bem-vindo(a), ${user.name}.`); ctx.go(user.kind === 'cidadao' ? 'cidadao' : 'exec'); }

export const entrar = {
  public: true, title: 'Entrar',
  async render() {
    return `<section class="auth">${authAside(true)}<div class="auth-right">${quickDemo()}<div class="auth-card"><h1>Entrar</h1><p class="muted">Escolha o tipo de conta. As experiências e as informações são separadas.</p>${authTabs()}
      <form id="login" class="form" autocomplete="on"><label class="field"><span>E-mail</span><input id="l-email" type="email" required autocomplete="username"></label>
      <label class="field"><span>Senha</span><input id="l-pw" type="password" required autocomplete="current-password"></label>
      <button class="btn primary block">Entrar como ${state.authTab === 'empresa' ? 'empresa' : 'cidadão'}</button></form>
      <p class="center sm">Não tem conta? <a href="#/cadastro">Cadastre-se</a></p>
      <div class="demo-box"><b>Contas de demonstração</b> <span class="muted sm">(senha pública: LexIA2026demo)</span><div class="chips">${DEMO[state.authTab].map(([m, l]) => `<button class="chip-btn" data-demo="${m}">${e(l)}</button>`).join('')}</div></div></div></div></section>`;
  },
  mount(root, ctx) {
    bindAuthTabs(root, ctx);
    const go = async (email, pw) => { try { const r = await api('/api/auth/login', { email, password: pw, kind: state.authTab }); await afterAuth(ctx, r.user); } catch (err) { toast(err.message, 'err'); } };
    root.querySelector('#login').addEventListener('submit', (ev) => { ev.preventDefault(); go(root.querySelector('#l-email').value, root.querySelector('#l-pw').value); });
    root.querySelectorAll('[data-demo]').forEach((b) => b.addEventListener('click', () => go(b.dataset.demo, 'LexIA2026demo')));
    root.querySelectorAll('[data-quick]').forEach((b) => b.addEventListener('click', () => {
      state.authTab = b.dataset.quick;
      root.querySelector('#l-email').value = b.dataset.mail; root.querySelector('#l-pw').value = 'LexIA2026demo';
      go(b.dataset.mail, 'LexIA2026demo');
    }));
  },
};

const UFS = 'AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split(' ');
export const cadastro = {
  public: true, title: 'Criar conta',
  async render() {
    const emp = state.authTab === 'empresa';
    return `<section class="auth">${authAside()}<div class="auth-card"><h1>Criar conta</h1><p class="muted">${emp ? 'Para equipes de jurídico, compliance, engenharia, operação e finanças.' : 'Para acompanhar informações públicas da sua região.'}</p>${authTabs()}
      <form id="reg" class="form">
        <label class="field"><span>Nome completo</span><input id="r-name" required maxlength="120" autocomplete="name"></label>
        <label class="field"><span>E-mail${emp ? ' corporativo' : ''}</span><input id="r-email" type="email" required autocomplete="email"></label>
        ${emp ? `<div class="form-2"><label class="field"><span>Razão social</span><input id="r-org" required maxlength="160"></label><label class="field"><span>CNPJ</span><input id="r-cnpj" required inputmode="numeric" placeholder="00.000.000/0000-00" maxlength="18"></label></div>
        <label class="field"><span>Sua função</span><select id="r-fn" required><option value="">Selecione</option>${[['juridico', 'Jurídico'], ['compliance', 'Compliance'], ['engenharia', 'Engenharia / geotecnia'], ['operacao', 'Operação'], ['financas', 'Finanças'], ['meio_ambiente', 'Meio ambiente'], ['regulatorio', 'Assuntos regulatórios'], ['auditoria', 'Auditoria']].map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
        <p class="hint">Demonstração: a função define suas permissões. Em produção, o administrador da organização atribui os papéis.</p>`
        : `<div class="form-2"><label class="field"><span>UF</span><select id="r-uf"><option value="">—</option>${UFS.map((u) => `<option>${u}</option>`).join('')}</select></label><label class="field"><span>Município (opcional)</span><input id="r-mun" maxlength="80"></label></div>`}
        <label class="field"><span>Senha</span><input id="r-pw" type="password" required minlength="8" autocomplete="new-password" placeholder="8+ caracteres, com letras e números"></label>
        <label class="check"><input type="checkbox" id="r-ok"> <span>Li e aceito o uso dos meus dados para criar e operar a conta, conforme a LGPD (ver <a href="#/sobre">Sobre › Privacidade</a>).</span></label>
        <button class="btn primary block">Criar conta ${emp ? 'empresarial' : 'de cidadão'}</button></form>
      <p class="center sm">Já tem conta? <a href="#/entrar">Entrar</a></p></div></section>`;
  },
  mount(root, ctx) {
    bindAuthTabs(root, ctx);
    const cnpj = root.querySelector('#r-cnpj');
    cnpj?.addEventListener('input', () => { const d = cnpj.value.replace(/\D/g, '').slice(0, 14); cnpj.value = d.replace(/^(\d{2})(\d)/, '$1.$2').replace(/^(\d{2})\.(\d{3})(\d)/, '$1.$2.$3').replace(/\.(\d{3})(\d)/, '.$1/$2').replace(/(\d{4})(\d)/, '$1-$2'); });
    root.querySelector('#reg').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const v = (id) => root.querySelector(id)?.value;
      const body = { kind: state.authTab, name: v('#r-name'), email: v('#r-email'), password: v('#r-pw'), consent: root.querySelector('#r-ok').checked,
        org_name: v('#r-org'), cnpj: v('#r-cnpj'), function: v('#r-fn'), uf: v('#r-uf'), municipio: v('#r-mun') };
      try { const r = await api('/api/auth/register', body); await afterAuth(ctx, r.user); } catch (err) { toast(err.message, 'err'); }
    });
  },
};

// ------------------------------------------------------------------ PORTAL DO CIDADÃO
const GLOSS = [
  ['CRI — Categoria de Risco', 'Classificação da ANM conforme características da própria barragem que podem influenciar a possibilidade de acidente (projeto, estado de conservação, gestão). Alta, Média ou Baixa.'],
  ['DPA — Dano Potencial Associado', 'Classificação do dano que poderia ocorrer em caso de rompimento ou mau funcionamento, independentemente da probabilidade de acontecer. Não é uma previsão.'],
  ['PNSB', 'Política Nacional de Segurança de Barragens. Barragens “inseridas na PNSB” seguem as obrigações dessa política.'],
  ['PAEBM', 'Plano de Ação de Emergência para Barragens de Mineração: define alertas, rotas e responsabilidades em emergência.'],
  ['Nível de emergência', 'Situação declarada pelo empreendedor ao sistema da ANM. Em caso de alerta, siga sempre as orientações da Defesa Civil.'],
];
state.cid = state.cid || { uf: '', mun: '' };
export const cidadao = {
  title: 'Minha região', citizen: true,
  async render() {
    if (!data.official) await refreshOfficial();
    const u = data.me.user, C = state.cid;
    if (!C.uf && !C.mun) { C.uf = u.uf || 'MG'; C.mun = u.municipio || ''; }
    const recs = data.official.records;
    const local = recs.filter((r) => (!C.uf || r.uf === C.uf) && (!C.mun || norm(r.municipio) === norm(C.mun)));
    const muns = [...new Set(recs.filter((r) => r.uf === C.uf).map((r) => r.municipio))].sort();
    const watched = recs.filter((r) => (data.me.watchlist || []).includes(r.id));
    const notes = await api('/api/notifications');
    const emerg = local.filter((r) => r.emergency_level && r.emergency_level !== 'Sem emergência').length;
    const P = data.provisions.filter((p) => p.regulator === 'ANM');
    const dcard = (r) => `<article class="dam ${r.emergency_level && r.emergency_level !== 'Sem emergência' ? 'warn' : ''}"><div class="dam-h"><span class="dam-ic">${icon('dam')}</span><div><strong>${e(r.name)}</strong><small>${e(r.municipio)}/${e(r.uf)} · ${e(r.owner_name)}</small></div></div>
      <dl class="mini"><dt>Situação</dt><dd>${e(r.operational_status || '—')}</dd><dt>Emergência declarada</dt><dd>${e(r.emergency_level || '—')}</dd><dt>CRI / DPA</dt><dd>${e(r.cri || '—')} / ${e(r.dpa || '—')}</dd><dt>Na PNSB</dt><dd>${e(r.pnsb || '—')}</dd></dl>
      ${(data.me.watchlist || []).includes(r.id) ? `<button class="btn sm" data-cw="${r.id}" data-a="remove">${icon('star')} Acompanhando</button>` : `<button class="btn sm primary" data-cw="${r.id}" data-a="add">${icon('star')} Acompanhar</button>`}</article>`;
    return `
    <section class="cid-hero"><div><span class="eyebrow">Portal do cidadão</span><h1>Olá, ${e(u.name.split(' ')[0])}.</h1><p>Informações públicas da ANM sobre barragens de mineração na sua região, em linguagem simples. Dados do SIGBM de ${fmtDateTime(data.official.snapshot.fetched_at)}.</p></div>
      <form class="region" id="region"><label class="field"><span>UF</span><select id="c-uf">${UFS.map((x) => `<option ${x === C.uf ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
      <label class="field"><span>Município</span><select id="c-mun"><option value="">Todos</option>${muns.map((m) => `<option ${norm(m) === norm(C.mun) ? 'selected' : ''}>${e(m)}</option>`).join('')}</select></label></form></section>
    <div class="cid-stats"><div class="kpi" style="--k:#28518A"><span class="kpi-ic">${icon('dam')}</span><div><div class="kpi-v">${local.length}</div><div class="kpi-l">barragens de mineração ${C.mun ? 'no município' : 'na UF'}</div></div></div>
      <div class="kpi" style="--k:#E5484D"><span class="kpi-ic">${icon('alert')}</span><div><div class="kpi-v">${emerg}</div><div class="kpi-l">com nível de emergência declarado</div></div></div>
      <div class="kpi" style="--k:#68487A"><span class="kpi-ic">${icon('star')}</span><div><div class="kpi-v">${watched.length}</div><div class="kpi-l">que você acompanha</div></div></div></div>
    <div class="grid-exec">
      <section class="card"><header class="card-h"><h3>${icon('pin', 'h-ic')}Barragens ${C.mun ? 'em ' + e(C.mun) : 'em ' + e(C.uf)}</h3><span class="muted sm">fonte: ANM · SIGBM</span></header>
        <div id="cid-map" class="map-frame light-map"></div><div id="cid-pick" aria-live="polite"><p class="hint">Clique num ponto do mapa para ver a barragem, a imagem de satélite e o que fazer.</p></div>
        <div class="dams">${local.slice(0, 12).map(dcard).join('') || '<p class="muted">Nenhuma barragem de mineração cadastrada aqui no SIGBM.</p>'}</div>${local.length > 12 ? `<p class="hint">Mostrando 12 de ${local.length}. Escolha um município para ver menos.</p>` : ''}</section>
      <div class="stack">
        <section class="card emergency"><h3>${icon('phone', 'h-ic')}Em emergência</h3><p><b>Defesa Civil: 199</b> · Bombeiros: 193</p><p class="sm">Siga sempre as orientações da Defesa Civil e as rotas de fuga sinalizadas. Este portal não substitui alertas oficiais.</p></section>
        <section class="card"><h3>${icon('book', 'h-ic')}O que mudou nas regras</h3><p class="sm">As novas regras da ANM para barragens (Resolução 220/2025, ajustada pela 245/2026) entram <b>em etapas</b>:</p>
          <ul class="timeline-list">${P.filter((p) => p.valid_from).map((p) => `<li class="${p.valid_from <= state.asOf ? 'past' : ''}"><time>${fmtDate(p.valid_from)}</time><span><strong>${e(p.provision)}</strong><small>${p.valid_from <= state.asOf ? 'já vale' : 'ainda vai valer'}</small></span></li>`).join('')}</ul>
          <p class="hint">Fontes: ${refs(['F09', 'F10', 'F40'])}</p><button class="btn sm" data-ask>Perguntar em linguagem simples</button></section>
        <section class="card"><h3>${icon('bell', 'h-ic')}Avisos</h3>${notes.items.length ? `<ul class="history">${notes.items.slice(0, 5).map((n) => `<li><strong>${e(n.title)}</strong><small>${e(n.body)}</small><small>${fmtDateTime(n.created_at)}</small></li>`).join('')}</ul>` : '<p class="muted sm">Nenhum aviso por enquanto. Avisamos quando a ANM publicar novos dados.</p>'}</section>
      </div>
    </div>
    ${watched.length ? `<section class="card mt16"><h3>${icon('star', 'h-ic')}Estruturas que você acompanha</h3><div class="dams">${watched.map(dcard).join('')}</div></section>` : ''}
    <section class="card mt16"><h3>${icon('book', 'h-ic')}Entenda os termos</h3><div class="gloss">${GLOSS.map(([t, d]) => `<details><summary>${e(t)}</summary><p>${e(d)}</p></details>`).join('')}</div>
      <p class="hint">Definições em linguagem simples baseadas na legislação de segurança de barragens (Lei 12.334/2010) catalogada pela ANM ${refs(['F09'])}. Os dados são publicados pelos empreendedores e pela ANM; a LexIA não avalia a segurança de nenhuma estrutura.</p></section>`;
  },
  mount(root, ctx) {
    const C = state.cid, recs = data.official.records;
    const local = recs.filter((r) => (!C.uf || r.uf === C.uf) && (!C.mun || norm(r.municipio) === norm(C.mun)));
    const rua = C.mun && local.length && local.length <= 60;   // município escolhido: mapa de ruas com os números das barragens
    const pinsRua = local.map((r, i) => ({ id: r.id, n: i + 1, lat: r.lat, lon: r.lon, nome: r.name, numero: r.id, real: true }));
    const frame = root.querySelector('#cid-map');
    const desenhaRua = (sel) => { frame.classList.remove('map-frame', 'light-map'); frame.innerHTML = streetMap(pinsRua, null, sel); frame.querySelectorAll('[data-pick]').forEach((b) => b.addEventListener('click', () => pick(b.dataset.pick))); };
    const m = rua ? null : createMap(frame, { points: local.map((r) => ({ id: r.id, lat: r.lat, lon: r.lon, kind: 'official', color: r.emergency_level && r.emergency_level !== 'Sem emergência' ? '#E5484D' : '#28518A', label: `${r.name} · ${r.municipio}` })), selected: null, controls: true, legend: false, onlyBrazil: true, pinScale: 1.4, height: 300, onSelect: (id) => pick(id) });
    function pick(id) {
      const r = recs.find((x) => x.id === id); if (!r) return;
      if (rua) desenhaRua(id); else m.update(local.map((q) => ({ id: q.id, lat: q.lat, lon: q.lon, kind: 'official', color: q.emergency_level && q.emergency_level !== 'Sem emergência' ? '#E5484D' : '#28518A', label: `${q.name} · ${q.municipio}`, short: q.name })), id);
      const em = r.emergency_level && r.emergency_level !== 'Sem emergência';
      root.querySelector('#cid-pick').innerHTML = `<article class="cid-pick ${em ? 'warn' : ''}"><div class="cid-pick-t"><span class="eyebrow">Barragem selecionada · dado oficial ANM</span><h4>${e(r.name)}</h4><p class="muted sm">${e(r.municipio)}/${e(r.uf)} · ${e(r.owner_name)}</p>
        <dl class="mini"><dt>Situação</dt><dd>${e(r.operational_status || '—')}</dd><dt>Emergência declarada</dt><dd>${e(r.emergency_level || '—')}</dd><dt>Dano potencial (DPA)</dt><dd>${e(r.dpa || '—')}</dd></dl>
        ${em ? '<p class="warn-note">Há nível de emergência declarado. Siga a Defesa Civil (199).</p>' : ''}
        <div class="row gap wrap"><a class="btn sm primary" href="#/radar?id=${encodeURIComponent(r.id)}">Ver sinais e responsáveis</a><button class="btn sm" data-cw="${r.id}" data-a="${(data.me.watchlist || []).includes(r.id) ? 'remove' : 'add'}">${icon('star')} ${(data.me.watchlist || []).includes(r.id) ? 'Acompanhando' : 'Acompanhar'}</button></div></div>
        <div>${satView(r.lat, r.lon, { height: 190, label: `${r.name} (coordenada oficial)` })}</div></article>`;
      root.querySelector('#cid-pick [data-cw]').addEventListener('click', async (ev) => { const b = ev.currentTarget; try { await api('/api/watchlist', { asset_id: b.dataset.cw, action: b.dataset.a }); await refreshMe(); toast(b.dataset.a === 'add' ? 'Você vai receber avisos sobre esta estrutura.' : 'Deixou de acompanhar.'); ctx.rerender(); } catch (err) { toast(err.message, 'err'); } });
    }
    if (rua) desenhaRua(null); else if (local.length) m.fit(local);
    root.querySelector('#c-uf').addEventListener('change', (ev) => { C.uf = ev.target.value; C.mun = ''; ctx.rerender(); });
    root.querySelector('#c-mun').addEventListener('change', (ev) => { C.mun = ev.target.value; ctx.rerender(); });
    root.querySelectorAll('[data-cw]').forEach((b) => b.addEventListener('click', async () => { try { await api('/api/watchlist', { asset_id: b.dataset.cw, action: b.dataset.a }); await refreshMe(); toast(b.dataset.a === 'add' ? 'Você vai receber avisos sobre esta estrutura.' : 'Deixou de acompanhar.'); ctx.rerender(); } catch (err) { toast(err.message, 'err'); } }));
  },
};
