// Equipe e acessos: a gestão cadastra pessoas (uma a uma, só com o e-mail ou importando CSV/Excel/PDF), escolhe a frente (empresa)
// e marca num checklist o que cada uma acessa. Desmarcar ou revogar vale na hora (o servidor fecha a API). Tudo fica na trilha.
import { state, api, e, icon, toast, currentUser, refreshMe } from './core.js';

const QS = () => new URLSearchParams(location.hash.split('?')[1] || '');
const ES = () => (state.eq = state.eq || { sel: null, prev: null, links: [], funcao: 'operacao', loteFuncao: 'operacao', texto: '' });
const iniciais = (n) => (n || '?').split(' ').map((p) => p[0]).filter((c) => /[A-ZÁ-Ú]/i.test(c)).slice(0, 2).join('').toUpperCase();

function painel(D, sel) {
  if (!sel) return '<div class="eq-vazio"><p>Escolha uma pessoa na lista para ver e marcar o que ela acessa.</p></div>';
  const conv = sel.alvo === 'convite';
  const x = conv ? D.convites.find((c) => c.id === sel.id) : D.membros.find((m) => m.id === sel.id);
  if (!x) return '<div class="eq-vazio"><p>Pessoa não encontrada.</p></div>';
  const fixo = !conv && (x.is_demo || x.modulos == null), eu = !conv && x.id === D.eu, susp = x.status === 'suspenso';
  const mods = fixo ? Object.keys(D.modulos) : (x.modulos || []);
  const frente = D.frentes.find((f) => f.id === x.empresa_id);
  return `<div class="eq-pessoa"><span class="eq-av">${e(iniciais(x.name))}</span><div><h3>${e(x.name)}</h3><p class="muted sm">${e(x.cargo || D.funcoes[x.function]?.rotulo || x.function || '')} · ${e(x.email)}</p>
      <div class="row gap wrap mt8"><span class="lx-chip ${conv ? 'mod' : susp ? 'crit' : 'ok'}">${conv ? 'Convite pendente' : susp ? 'Acesso revogado' : 'Ativo'}</span><span class="lx-chip oficial">${frente ? 'Frente: ' + e(frente.nome) : 'Todas as frentes da organização'}</span></div></div></div>
    <h4>O que esta pessoa acessa</h4>
    ${fixo ? `<p class="hint">${x.is_demo ? 'Conta de demonstração compartilhada: acesso completo do papel, fixo.' : eu ? 'Este é você.' : 'Acesso completo do papel.'}</p>` : '<p class="hint">Marque ou desmarque: vale na hora, a pessoa já não abre o que foi desmarcado.</p>'}
    <ul class="eq-check">${Object.entries(D.modulos).map(([k, l]) => `<li><label class="${fixo || susp || !D.sou_admin ? 'off' : ''}"><input type="checkbox" data-mod="${k}" ${mods.includes(k) ? 'checked' : ''} ${fixo || susp || !D.sou_admin ? 'disabled' : ''}><span>${e(l)}</span></label></li>`).join('')}</ul>
    ${D.sou_admin && !eu && !x.is_demo ? `<div class="row gap wrap mt12">${conv ? '<button class="btn" id="eq-cancel" type="button">Cancelar convite</button>'
      : susp ? '<button class="btn primary" id="eq-react" type="button">Devolver o acesso</button>' : '<button class="btn danger" id="eq-revoke" type="button">Revogar todo o acesso</button>'}</div>` : ''}
    <p class="hint mt8">Toda mudança fica registrada na trilha de auditoria (quem mudou, quando e o quê).</p>`;
}

export const equipePage = {
  title: 'Equipe e acessos',
  async render() {
    const st = ES();
    const pre = QS().get('funcao'); if (pre) st.funcao = pre;
    const D = await api('/api/equipe' + (state.perfil ? '?empresa=' + encodeURIComponent(state.perfil) : ''));
    state.eqData = D;
    const frenteAtual = D.frentes.find((f) => f.id === state.perfil) || D.frentes[0];
    const daFrente = (x) => !x.empresa_id || x.empresa_id === frenteAtual?.id;
    const membros = D.membros.filter(daFrente), convites = D.convites.filter(daFrente);
    const F = D.funcoes, fsel = (sel, attr) => `<select ${attr}>${Object.entries(F).map(([k, v]) => `<option value="${k}" ${k === sel ? 'selected' : ''}>${e(v.rotulo)}</option>`).join('')}</select>`;
    const item = (x, alvo) => { const on = st.sel && st.sel.alvo === alvo && st.sel.id === x.id;
      return `<button type="button" class="eq-item ${on ? 'on' : ''}" data-sel="${alvo}:${x.id}"><span class="eq-av sm">${e(iniciais(x.name))}</span><span class="eq-t"><b>${e(x.name)}</b><small>${e(x.cargo || F[x.function]?.rotulo || '')} · ${e(x.email)}</small></span>
        <span class="lx-chip ${alvo === 'convite' ? 'mod' : x.status === 'suspenso' ? 'crit' : 'ok'}">${alvo === 'convite' ? 'convite' : x.status === 'suspenso' ? 'revogado' : x.empresa_id ? (x.modulos?.length ?? 0) + ' áreas' : 'todas'}</span></button>`; };
    return `<header class="page-head"><div><span class="eyebrow">Equipe e acessos · ${e(frenteAtual?.nome || D.org || '')}</span><h2>Equipe e acessos</h2>
      <p class="muted">Cadastre quem trabalha nesta frente e marque o que cada pessoa acessa. Quem entra por aqui vê <b>só esta empresa</b> e só as áreas marcadas. Revogar vale na hora.</p></div></header>
    ${!D.sou_admin ? '<p class="warn-note">Você pode ver a equipe, mas só gestão, compliance ou jurídico podem cadastrar e mudar acessos.</p>' : ''}
    ${D.sou_admin ? `<div class="grid-6-6">
      <section class="card"><header class="card-h"><h3>${icon('user', 'h-ic')}Adicionar pessoa</h3></header>
        <form id="eq-inv" class="pf-form"><label class="field"><span>E-mail (obrigatório)</span><input id="eq-email" type="email" required maxlength="160" placeholder="nome@empresa.com.br"></label>
          <div class="row gap wrap"><label class="field" style="flex:1;min-width:160px"><span>Nome (opcional)</span><input id="eq-nome" maxlength="120"></label><label class="field" style="flex:1;min-width:160px"><span>Cargo (opcional)</span><input id="eq-cargo" maxlength="80" placeholder="Ex.: Técnico de segurança"></label></div>
          <label class="field"><span>Função (define o acesso inicial; você ajusta depois)</span>${fsel(st.funcao, 'id="eq-funcao"')}</label>
          <button class="btn primary">${icon('users')} Dar acesso</button></form></section>
      <section class="card"><header class="card-h"><h3>${icon('doc', 'h-ic')}Importar lista de funcionários</h3></header>
        <p class="sm">CSV, Excel (.xlsx) ou PDF com <b>nome, cargo e e-mail</b>, ou cole a lista abaixo. Você confere antes de enviar.</p>
        <label class="btn sm">${icon('doc')} Escolher arquivo<input type="file" id="eq-file" accept=".csv,.xlsx,.pdf,.txt" hidden></label>
        <label class="field mt8"><span>Ou cole aqui (uma pessoa por linha)</span><textarea id="eq-txt" rows="3" placeholder="Maria Souza; Técnica de segurança; maria@empresa.com.br">${e(st.texto)}</textarea></label>
        <button class="btn sm mt8" id="eq-ler" type="button">Ler lista</button>
        ${st.prev ? `<div class="eq-prev mt12"><p class="sm"><b>${st.prev.linhas.length}</b> pessoa(s) encontrada(s)${st.prev.ignoradas ? ` · ${st.prev.ignoradas} linha(s) sem e-mail ignorada(s)` : ''}.${st.prev.aviso ? ' ' + e(st.prev.aviso) : ''}</p>
          ${st.prev.linhas.length ? `<div class="table-wrap"><table class="table compact"><thead><tr><th></th><th>Nome</th><th>Cargo</th><th>E-mail</th></tr></thead><tbody>${st.prev.linhas.map((r, i) => `<tr><td><input type="checkbox" data-lin="${i}" ${r.ok === false ? '' : 'checked'}></td><td>${e(r.nome || '—')}</td><td>${e(r.cargo || '—')}</td><td>${e(r.email)}</td></tr>`).join('')}</tbody></table></div>
          <div class="row gap wrap mt8"><label class="field" style="flex:1"><span>Função de todos (acesso inicial)</span>${fsel(st.loteFuncao, 'id="eq-lfun"')}</label><button class="btn primary" id="eq-lote" type="button">${icon('users')} Dar acesso a ${st.prev.linhas.filter((r) => r.ok !== false).length}</button></div>` : ''}</div>` : ''}</section></div>` : ''}
    ${st.links.length ? `<div class="eq-links mt12"><b>${st.links.length} acesso(s) criado(s) em ${e(frenteAtual?.nome || '')}.</b> Nesta demonstração o e-mail não sai da plataforma: envie o link para a pessoa criar a senha (vale 7 dias).
      <ul>${st.links.map((l) => `<li><span>${e(l.nome || l.email)}</span><input readonly value="${e(l.link)}"><button class="btn sm" data-copy="${e(l.link)}" type="button">Copiar</button></li>`).join('')}</ul><button class="btn sm ghost" id="eq-fecha" type="button">Fechar</button></div>` : ''}
    ${D.papeis_sem_pessoa?.length ? `<div class="warn-note mt12">${icon('users')} <b>Papéis sem pessoa nesta frente:</b> ${D.papeis_sem_pessoa.map((p) => e(p.papel)).join(', ')}. Os alertas desses papéis estão sendo escalados até alguém ser cadastrado.</div>` : ''}
    <div class="eq-grid mt16">
      <section class="card"><header class="card-h"><h3>${icon('users', 'h-ic')}Pessoas · ${e(frenteAtual?.nome || '')}</h3><span class="muted sm">${membros.length} pessoa(s) · ${convites.length} convite(s)</span></header>
        <div class="eq-list">${membros.map((m) => item(m, 'pessoa')).join('')}${convites.map((c) => item(c, 'convite')).join('') || ''}</div></section>
      <section class="card eq-painel"><header class="card-h"><h3>${icon('shield', 'h-ic')}Acesso</h3></header>${painel(D, st.sel)}</section>
    </div>`;
  },
  mount(root, ctx) {
    const st = ES(), D = state.eqData;
    root.querySelectorAll('[data-sel]').forEach((b) => b.addEventListener('click', () => { const [alvo, id] = b.dataset.sel.split(':'); st.sel = { alvo, id: +id }; ctx.rerender(); }));
    root.querySelector('#eq-funcao')?.addEventListener('change', (ev) => { st.funcao = ev.target.value; });
    root.querySelector('#eq-lfun')?.addEventListener('change', (ev) => { st.loteFuncao = ev.target.value; });
    root.querySelector('#eq-inv')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const v = (id) => root.querySelector(id).value;
      try { const r = await api('/api/equipe/convidar', { email: v('#eq-email'), nome: v('#eq-nome'), cargo: v('#eq-cargo'), funcao: v('#eq-funcao'), empresa: state.perfil });
        st.links = [{ nome: v('#eq-nome') || r.email, email: r.email, link: r.link }]; st.sel = { alvo: 'convite', id: r.id }; toast('Acesso criado. Ajuste o checklist à direita.'); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    });
    const ler = async (body) => { try { st.prev = await api('/api/equipe/importar', body); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); };
    root.querySelector('#eq-file')?.addEventListener('change', async (ev) => {
      const f = ev.target.files[0]; if (!f) return;
      if (f.size > 4 * 1024 * 1024) return toast('Arquivo acima de 4 MB.', 'err');
      const b64 = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.readAsDataURL(f); });
      ler({ nome_arquivo: f.name, conteudo: b64 });
    });
    root.querySelector('#eq-ler')?.addEventListener('click', () => { st.texto = root.querySelector('#eq-txt').value; if (st.texto.trim()) ler({ nome_arquivo: 'lista.txt', texto: st.texto }); });
    root.querySelectorAll('[data-lin]').forEach((c) => c.addEventListener('change', () => { st.prev.linhas[+c.dataset.lin].ok = c.checked; ctx.rerender(); }));
    root.querySelector('#eq-lote')?.addEventListener('click', async (ev) => {
      ev.target.disabled = true;
      const linhas = st.prev.linhas.filter((r) => r.ok !== false);
      try { const r = await api('/api/equipe/convidar-lote', { linhas, funcao: st.loteFuncao, empresa: state.perfil });
        st.links = r.convidados; st.prev = null; st.texto = '';
        toast(`${r.convidados.length} acesso(s) criado(s)${r.erros.length ? ` · ${r.erros.length} com problema: ${r.erros.map((x) => x.email + ' (' + x.erro + ')').join('; ')}` : ''}.`, r.erros.length ? 'err' : undefined); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    });
    root.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', async () => { try { await navigator.clipboard.writeText(b.dataset.copy); toast('Link copiado.'); } catch { b.previousElementSibling.select(); } }));
    root.querySelector('#eq-fecha')?.addEventListener('click', () => { st.links = []; ctx.rerender(); });
    root.querySelectorAll('[data-mod]').forEach((c) => c.addEventListener('change', async () => {
      const mods = [...root.querySelectorAll('[data-mod]:checked')].map((x) => x.dataset.mod);
      try { await api('/api/equipe/acesso', { alvo: st.sel.alvo, id: st.sel.id, modulos: mods }); toast(c.checked ? 'Acesso liberado.' : 'Acesso retirado. Já vale.'); } catch (err) { toast(err.message, 'err'); c.checked = !c.checked; return; }
      ctx.rerender();
    }));
    const status = async (to) => { try { await api('/api/equipe/alterar', { id: st.sel.id, status: to, motivo: to === 'suspenso' ? 'Acesso revogado pela gestão (Equipe e acessos)' : 'Acesso devolvido pela gestão (Equipe e acessos)' }); toast(to === 'suspenso' ? 'Acesso revogado. A pessoa saiu da plataforma.' : 'Acesso devolvido.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); };
    root.querySelector('#eq-revoke')?.addEventListener('click', () => { if (confirm('Revogar todo o acesso desta pessoa agora?')) status('suspenso'); });
    root.querySelector('#eq-react')?.addEventListener('click', () => status('ativo'));
    root.querySelector('#eq-cancel')?.addEventListener('click', async () => { try { await api('/api/equipe/revogar-convite', { id: st.sel.id }); st.sel = null; toast('Convite cancelado.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); });
    void D;
  },
};

export const convitePage = {
  public: true, title: 'Convite',
  async render() {
    const t = QS().get('t') || '';
    const I = await api('/api/convite?t=' + encodeURIComponent(t)).catch((err) => ({ error: err.message }));
    if (I.error) return `<section class="tp-wrap"><div class="card"><h2>Convite</h2><p class="warn-note">${e(I.error)}</p><a class="btn" href="#/entrar">Ir para o login</a></div></section>`;
    return `<section class="tp-wrap"><div class="card cv-card"><span class="eyebrow">Acesso à LexIA</span><h2>${e(I.org_name)}</h2>
      <p>Olá, <b>${e(I.name)}</b>. A gestão da empresa liberou seu acesso como <b>${e(I.funcao)}</b>. Você verá só as áreas que ela marcou.</p>
      <form id="cv-form" class="pf-form"><label class="field"><span>E-mail</span><input value="${e(I.email)}" readonly></label>
        <label class="field"><span>Crie sua senha (8+ caracteres, letras e números)</span><input id="cv-pw" type="password" required minlength="8"></label>
        <label class="chip-btn"><input type="checkbox" id="cv-ok"> Concordo com o uso dos meus dados conforme a LGPD (ver Sobre e privacidade).</label>
        <button class="btn primary lg">Criar senha e entrar</button></form></div></section>`;
  },
  mount(root, ctx) {
    root.querySelector('#cv-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      try { await api('/api/convite/aceitar', { t: QS().get('t'), senha: root.querySelector('#cv-pw').value, consent: root.querySelector('#cv-ok').checked }); await refreshMe(); toast('Bem-vindo(a).'); ctx.go('exec'); }
      catch (err) { toast(err.message, 'err'); }
    });
  },
};
void currentUser;
