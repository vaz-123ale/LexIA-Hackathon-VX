// Compliance & Alertas — agente de alertas jurídicos (regras) + documentos da organização no cofre (S3 por Customer ID).
import { state, api, e, fmtDate, fmtDateTime, card, toast, icon, can, currentUser } from './core.js';
import { relatoFormal, normasDz, implicDz, caminhosDz } from './ws_denuncia.js?v=72';
import { repasseHtml, bindRepasse, carregarRepasses } from './triagem.js';

const LV = { 'Crítico': '#C83037', 'Alto': '#F97316', 'Médio': '#EAB308', 'Baixo': '#63768A' };
const ST = { ABERTO: ['Aberto', '#C83037'], EM_REGULARIZACAO: ['Aguardando regularização', '#D4A12E'], RESOLVIDO: ['Resolvido', '#46774E'], DESCARTADO: ['Descartado', '#94A3B8'] };
const CS = () => (state.comp = state.comp || { tab: 'alertas', sel: null, lvl: '', org: '' });
const DST = { RECEBIDA: ['Recebida', '#C83037'], EM_APURACAO: ['Em apuração', '#D4A12E'], RESPONDIDA: ['Respondida', '#46774E'] };
const lvTag = (l) => `<span class="tag" style="--c:${LV[l]}">${e(l)}</span>`;
const stTag = (s) => `<span class="tag" style="--c:${ST[s][1]}">${ST[s][0]}</span>`;

function alertBox(a, hist) {
  const role = currentUser()?.role;
  const next = { ABERTO: [['EM_REGULARIZACAO', 'Iniciar regularização'], ...(['juridico', 'compliance'].includes(role) ? [['DESCARTADO', 'Descartar (justificar)']] : [])], EM_REGULARIZACAO: [['RESOLVIDO', 'Marcar como resolvido'], ['ABERTO', 'Reabrir']], RESOLVIDO: [['ABERTO', 'Reabrir']], DESCARTADO: [['ABERTO', 'Reabrir']] }[a.status] || [];
  return `<article class="cp-alert lv-${e(a.level)}">
    <header><span class="cp-ic">${icon(a.safety ? 'alert' : 'doc')}</span><div><b>${a.safety ? 'Atenção: possível risco de não conformidade com impacto em segurança' : 'Atenção: possível risco de não conformidade'}</b><small>${e(a.asset_name)} · ${e(a.title)}</small></div>${lvTag(a.level)}</header>
    <p>${e(a.detail)}</p>
    <p>${e(a.consequences)}</p>
    <p class="cp-act"><b>Ação recomendada:</b> ${e(a.action)}</p>
    ${repasseHtml('alerta', a.id, a.title)}
    <dl class="kv"><dt>Status</dt><dd>${stTag(a.status)}${a.regularize_by ? ` · prazo de regularização ${fmtDate(a.regularize_by)}` : ''}</dd>
      <dt>Urgência</dt><dd>${e(a.urgency)}${a.due ? ` · vence ${fmtDate(a.due)}` : ''}</dd>
      <dt>Responsáveis</dt><dd>${a.responsibles.map(e).join(' · ')}</dd><dt>Origem</dt><dd>${e(a.origin)}</dd>
      ${a.evidence ? `<dt>Evidência</dt><dd>${e(a.evidence)}</dd>` : ''}</dl>
    <div class="basis">${a.basis.map((b) => (b.url ? `<a class="law" href="${e(b.url)}" target="_blank" rel="noopener noreferrer" title="${e(b.text)}">${e(b.ref)}</a>` : `<span class="law" title="${e(b.text)}">${e(b.ref)}</span>`)).join('')}</div>
    ${a.safety && a.status === 'ABERTO' ? '<p class="warn-note">Situação de segurança: tratar imediatamente, além do trâmite documental.</p>' : ''}
    ${next.length ? `<form class="cp-tr" data-id="${e(a.id)}"><input type="date" name="regularize_by" aria-label="Prazo de regularização"><input name="note" placeholder="Evidência, protocolo ou justificativa" aria-label="Observação">${next.map(([to, l]) => `<button class="btn sm ${to === 'RESOLVIDO' || to === 'EM_REGULARIZACAO' ? 'primary' : ''}" data-to="${to}">${l}</button>`).join('')}</form>` : ''}
    <details class="mt8"><summary>Histórico (${hist.length})</summary><ul class="history">${hist.map((h) => `<li><strong>${e(h.action)}</strong><small>${e(h.actor)} · ${fmtDateTime(h.at)}${h.note ? ' · ' + e(h.note) : ''}</small></li>`).join('')}</ul></details>
  </article>`;
}

async function inboxTab() {
  const d = await api('/api/denuncias/recebidas' + (state.perfil ? '?empresa=' + encodeURIComponent(state.perfil) : ''));
  const CAT = { barragem: 'Barragem', energia: 'Energia elétrica', saneamento: 'Água e esgoto', mineracao: 'Mineração', trabalho: 'Segurança do trabalho', radiacao: 'Radiação', outro: 'Outro' };
  const res = (r) => !r || !r.fatos ? '' : `<dl class="kv dn-kv mt8">${r.quando ? `<dt>Quando</dt><dd>${e(r.quando.texto)} <small class="muted">(“${e(r.quando.trecho)}”)</small></dd>` : '<dt>Quando</dt><dd>não informado</dd>'}
      ${r.desde ? `<dt>Desde quando</dt><dd>${e(r.desde.texto)}</dd>` : ''}${r.periodo ? `<dt>Período</dt><dd>${e(r.periodo)}</dd>` : ''}<dt>Onde</dt><dd>${e(r.onde || 'conforme o relato')}</dd>
      ${r.afetados?.length ? `<dt>Pode afetar</dt><dd>${e(r.afetados.join(', '))}</dd>` : ''}${r.recorrente ? '<dt>Repetição</dt><dd>a situação se repete ou continua</dd>' : ''}</dl>
      <ol class="sm">${r.fatos.map((f) => `<li>${e(f)}</li>`).join('')}</ol>`;
  return `<div class="grid-8-4">${card('Denúncias recebidas sobre ativos da empresa', d.items.length ? d.items.map((x) => `<article class="cp-alert"><header><span class="cp-ic">${icon('doc')}</span><div><b>${e(x.ativo)}</b><small>Denúncia #${x.id}${x.categoria ? ' · ' + e(CAT[x.categoria] || x.categoria) : ''} · confirmada em ${fmtDateTime(x.confirmed_at)} · ${x.identificado ? 'denunciante identificado' : 'anônima para a empresa'}</small></div><span class="tag" style="--c:${DST[x.dest_state][1]}">${DST[x.dest_state][0]}</span></header>
      ${x.dossie?.relato_formal ? `<div class="dz-box">${relatoFormal(x.dossie)}
        <div class="grid-6-6 mt8"><div><h4>Normas possivelmente descumpridas</h4>${normasDz(x.dossie)}<h4>Implicações</h4>${implicDz(x.dossie)}</div>
        <div><h4>Dossiê · caminhos para resolver</h4>${caminhosDz(x.dossie, x.passos || {}, ['compliance', 'juridico', 'gestor', 'operacao', 'especialista'].includes(currentUser()?.role))}
          <p class="hint">${e(x.dossie.aviso)}</p></div></div></div>` : res(x.resumo)}
      <details><summary>Ler a denúncia completa (com as normas)</summary><textarea class="rd-draft" rows="14" readonly>${e(x.body)}</textarea></details>
      ${repasseHtml('denuncia', x.id, 'Denúncia #' + x.id + ' · ' + x.ativo)}
      ${x.resposta ? `<p class="cp-act"><b>Resposta registrada:</b> ${e(x.resposta)}</p>` : ''}
      <form class="dn-resp row gap wrap mt8" data-id="${x.id}"><input name="resposta" placeholder="Providência adotada / resposta" style="flex:1;min-width:220px"><button class="btn sm" data-st="EM_APURACAO">Em apuração</button><button class="btn sm primary" data-st="RESPONDIDA">Registrar resposta</button></form></article>`).join('')
    : '<div class="empty"><p>Nenhuma denúncia recebida. Quando alguém confirmar uma denúncia sobre um ativo desta empresa, ela aparece aqui e um e-mail vai para compliance e jurídico.</p></div>', { icon: 'doc' })}
    ${card('E-mails enviados à empresa', `<p class="sm">${d.ses ? 'Envio por e-mail ativo.' : 'Nesta demonstração o e-mail não sai da plataforma: cada mensagem fica registrada aqui, com destinatário e data.'}</p>
      <ul class="history">${d.emails.map((m) => `<li><strong>${e(m.subject)}</strong><small>para ${e(m.to_email)} · ${e(m.state)} · ${fmtDateTime(m.created_at)}</small></li>`).join('') || '<li class="muted">Nenhum e-mail.</li>'}</ul>`, { icon: 'bell' })}</div>`;
}

async function docsTab() {
  const d = await api('/api/docs');
  return `<div class="grid-8-4">${card('Documentos da organização', `<p class="sm">Guardados no cofre em <code>clientes/${e(d.customer_id)}/…</code> — o nome da empresa não aparece no caminho. Cada arquivo tem SHA-256 conferido na leitura.</p>
      ${d.allowed ? `<form id="up" class="row gap wrap"><input type="file" id="up-f" accept=".pdf,.png,.jpg,.jpeg,.txt" aria-label="Arquivo"><select id="up-k" aria-label="Tipo"><option value="documento">Documento</option><option value="evidencia">Evidência</option><option value="protocolo">Protocolo</option></select><button class="btn primary">${icon('shield')} Enviar ao cofre</button></form>` : '<p class="warn-note">Seu acesso aos documentos desta organização foi revogado.</p>'}
      <div class="table-wrap mt12"><table class="table compact"><thead><tr><th>#</th><th>Arquivo</th><th>Tipo</th><th>Tamanho</th><th>SHA-256</th><th>Onde</th><th></th></tr></thead><tbody>${d.docs.map((x) => `<tr><td>${x.id}</td><td>${e(x.name)}</td><td>${e(x.kind)}</td><td>${Math.ceil(x.bytes / 1024)} KB</td><td><code>${e(x.sha256.slice(0, 12))}…</code></td><td>${e(x.vault_mode)}</td><td><a class="btn sm" href="/api/docs/file?id=${x.id}">Baixar</a></td></tr>`).join('') || '<tr><td colspan="7" class="muted">Nenhum documento ainda.</td></tr>'}</tbody></table></div>`, { icon: 'database' })}
    ${card('Acesso e segurança', `<dl class="kv"><dt>Customer ID</dt><dd><code>${e(d.customer_id)}</code></dd><dt>Armazenamento</dt><dd>${d.mode === 's3' ? 'Amazon S3 privado + KMS' : 'Local (mesmo formato do S3)'}</dd><dt>Cadastro</dt><dd>Separado dos documentos, no banco da aplicação</dd></dl>
      ${['gestor', 'compliance', 'juridico'].includes(currentUser()?.role) ? `<form id="rv" class="row gap wrap"><input id="rv-u" placeholder="ID do usuário" aria-label="Usuário"><button class="btn sm" data-r="1">Revogar acesso</button><button class="btn sm" data-r="0">Restaurar</button></form>` : '<p class="hint">Gestor, compliance ou jurídico podem revogar o acesso de um usuário.</p>'}
      <ul class="history">${d.access.map((a) => `<li><strong>Usuário ${e(a.user_id)}</strong><small>${a.revoked_at ? 'revogado em ' + fmtDateTime(a.revoked_at) : 'acesso ativo'}</small></li>`).join('')}</ul>`, { icon: 'shield' })}</div>`;
}

export const compliancePage = {
  async render() {
    await carregarRepasses();
    const st = CS();
    const um = currentUser()?.modulos, okm = (m) => !Array.isArray(um) || um.includes(m);
    const TABS = [['alertas', 'Alertas', 'alert', 'conformidade'], ['denuncias', 'Denúncias recebidas', 'doc', 'denuncias'], ['docs', 'Documentos', 'database', 'documentos']].filter((t) => okm(t[3]));
    if (!TABS.some((t) => t[0] === st.tab)) st.tab = TABS[0]?.[0] || 'alertas';
    const tabs = `<div class="tabs" role="tablist">${TABS.map(([k, l, ic]) => `<button role="tab" class="tab ${st.tab === k ? 'on' : ''}" data-ctab="${k}">${icon(ic)}${l}</button>`).join('')}</div>`;
    const head = `<header class="page-head"><div><span class="eyebrow">Agente de alertas jurídicos</span><h2>Compliance & Alertas</h2><p class="muted">Documentos vencidos, licenças perto do fim, informações desatualizadas e situações das barragens acompanhadas — com base legal, ação recomendada e prazo de regularização.</p></div></header>`;
    if (st.tab === 'docs') return head + tabs + await docsTab();
    if (st.tab === 'denuncias') return head + tabs + await inboxTab();
    const emps = await api('/api/ativos/empresas').catch(() => ({ items: [] }));
    const perfil = state.perfil && emps.items.find((x) => x.id === state.perfil);
    if (perfil && st.org !== '' && st.org !== perfil.id) st.org = perfil.id;
    if (perfil && perfil.setor !== 'mineracao') st.org = perfil.id;
    const d = await api('/api/compliance' + (st.org ? '?org=' + encodeURIComponent(st.org) : ''));
    const orgSel = perfil && perfil.setor === 'mineracao' ? `<div class="seg mt8" role="group" aria-label="Recorte">${[[perfil.id, 'Ativos e sensores'], ['', 'Obrigações das barragens']].map(([k, l]) => `<button class="${st.org === k ? 'on' : ''}" data-org="${k}">${e(l)}</button>`).join('')}</div>` : '';
    const open = d.items.filter((a) => ['ABERTO', 'EM_REGULARIZACAO'].includes(a.status));
    const list = d.items.filter((a) => !st.lvl || a.level === st.lvl);
    let detail = '';
    if (st.sel) { try { const a = await api('/api/compliance?id=' + encodeURIComponent(st.sel) + (st.org ? '&org=' + encodeURIComponent(st.org) : '')); detail = alertBox(a, a.history); } catch { st.sel = null; } }
    return head + tabs + orgSel + `
    <div class="kpis4 mt12">${['Crítico', 'Alto', 'Médio', 'Baixo'].map((l) => `<button class="kpi kpi-btn" style="--k:${LV[l]}" data-lvl="${l}"><span class="kpi-ic">${icon('alert')}</span><span><span class="kpi-v">${d.by_level[l] || 0}</span><span class="kpi-l">${l === 'Crítico' ? 'críticos em aberto' : `nível ${l.toLowerCase()} em aberto`}</span></span></button>`).join('')}</div>
    <div class="row between wrap mt16"><span class="muted sm">${open.length} em aberto · ${d.by_status.RESOLVIDO || 0} resolvidos · regra <code>${e(d.rule_version)}</code>${st.lvl ? ` · filtrando ${e(st.lvl)} <button class="link" data-lvl="">limpar</button>` : ''}</span>
      <button class="btn" id="cp-scan">${icon('refresh')} Rodar agente de compliance</button></div>
    <div class="cp-grid mt12"><section class="card flush"><div class="rd-list">${list.map((a) => `<button class="rd-row ${st.sel === a.id ? 'on' : ''}" data-aid="${e(a.id)}"><span class="rd-bar" style="background:${LV[a.level]}"></span><span class="rd-main"><strong>${e(a.title)}</strong><small>${e(a.asset_name)} · ${e(a.urgency)}${a.safety ? ' · segurança' : ''}</small></span>${stTag(a.status)}</button>`).join('') || '<div class="empty"><p>Nenhum alerta.</p></div>'}</div></section>
      <section>${detail || '<div class="empty"><p>Selecione um alerta para ver a base legal, as consequências possíveis e registrar a regularização.</p></div>'}</section></div>
    <p class="hint">${e(d.note)}</p>`;
  },
  mount(root, ctx) {
    bindRepasse(root, ctx);
    const st = CS();
    root.querySelectorAll('[data-ctab]').forEach((b) => b.addEventListener('click', () => { st.tab = b.dataset.ctab; ctx.rerender(); }));
    root.querySelectorAll('[data-org]').forEach((b) => b.addEventListener('click', () => { st.org = b.dataset.org; st.sel = null; ctx.rerender(); }));
    root.querySelectorAll('[data-passo]').forEach((c) => c.addEventListener('change', async () => {
      const did = +c.closest('article').querySelector('.dn-resp').dataset.id;
      try { await api('/api/denuncias/passo', { id: did, passo: +c.dataset.passo, feito: c.checked, empresa: state.perfil }); toast(c.checked ? 'Passo marcado como feito (fica na trilha).' : 'Passo reaberto.'); } catch (err) { toast(err.message, 'err'); c.checked = !c.checked; return; }
      ctx.rerender();
    }));
    root.querySelectorAll('.dn-resp [data-st]').forEach((b) => b.addEventListener('click', async (ev) => {
      ev.preventDefault(); const f = b.closest('form');
      try { await api('/api/denuncias/responder', { id: +f.dataset.id, state: b.dataset.st, resposta: f.resposta.value }); toast('Registrado.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender();
    }));
    root.querySelectorAll('[data-lvl]').forEach((b) => b.addEventListener('click', () => { st.lvl = b.dataset.lvl === st.lvl ? '' : b.dataset.lvl; ctx.rerender(); }));
    root.querySelectorAll('[data-aid]').forEach((b) => b.addEventListener('click', () => { st.sel = b.dataset.aid; ctx.rerender(); }));
    root.querySelector('#cp-scan')?.addEventListener('click', async () => { try { const r = await api('/api/compliance/scan', { go: 1 }); toast(`Agente de compliance: ${r.novos} novo(s), ${r.escalados} escalado(s).`); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); });
    root.querySelectorAll('.cp-tr [data-to]').forEach((b) => b.addEventListener('click', async (ev) => {
      ev.preventDefault(); const f = b.closest('form');
      try { await api('/api/compliance/transition', { id: f.dataset.id, to: b.dataset.to, note: f.note.value, regularize_by: f.regularize_by.value || null }); toast('Registrado no histórico.'); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    }));
    root.querySelector('#up')?.addEventListener('submit', async (ev) => {
      ev.preventDefault(); const file = root.querySelector('#up-f').files[0];
      if (!file) return toast('Escolha um arquivo.', 'err');
      if (file.size > 5 * 1024 * 1024) return toast('Máximo de 5 MB.', 'err');
      const b64 = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.readAsDataURL(file); });
      try { const r = await api('/api/docs/upload', { name: file.name, mime: file.type || 'application/octet-stream', data: b64, kind: root.querySelector('#up-k').value }); toast(`Guardado no cofre (SHA-256 ${r.sha256.slice(0, 10)}…).`); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    });
    root.querySelectorAll('#rv [data-r]').forEach((b) => b.addEventListener('click', async (ev) => {
      ev.preventDefault(); try { await api('/api/docs/access', { user_id: root.querySelector('#rv-u').value, revoke: b.dataset.r === '1' }); toast('Acesso atualizado.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender();
    }));
  },
};
