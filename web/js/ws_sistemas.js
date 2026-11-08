// Impacto em sistemas (regra sistemas-v1): mudança normativa → aplicações afetadas no portfólio → arquivo, linha e alteração sugerida.
// Detectores versionados apontam o código; a IA pode sugerir onde o detector não alcança (verificada); uma pessoa aprova e vira tarefa.
import { state, api, e, icon, toast, fmtDate } from './core.js';
import { repasseHtml, bindRepasse, carregarRepasses } from './triagem.js';

const S = () => (state.si = state.si || { mud: null, R: null, sel: null, todos: false, ia: {} });
const CRIT = { A: ['Crítico', 'crit'], B: ['Alto', 'alta'], C: ['Normal', 'baixa'] };
const n = (x) => Number(x || 0).toLocaleString('pt-BR');
const diffHtml = (d) => `<pre class="si-diff">${d.split('\n').filter((l) => !l.startsWith('---') && !l.startsWith('+++')).map((l) =>
  `<span class="${l.startsWith('+') ? 'add' : l.startsWith('-') ? 'del' : l.startsWith('@@') ? 'hunk' : ''}">${e(l)}</span>`).join('\n')}</pre>`;

function painel(st, R) {
  const a = R.afetados.find((x) => x.id === st.sel);
  if (!a) return '<div class="eq-vazio"><p>Escolha um sistema da lista para ver onde mudar.</p></div>';
  const T = state.siData?.tarefas || [];
  const feito = (k) => st.dec?.[a.id + ':' + k] || T.find((t) => t.sistema === a.nome && t.mudanca === R.mudanca.id && (k === 'meta' ? !t.arquivo : t.arquivo === a.achados[+k]?.arquivo && t.linha === a.achados[+k]?.linha))?.state;
  const sug = st.ia[a.id];
  return `<div class="si-head"><span class="lx-chip ${CRIT[a.criticidade][1]}">${CRIT[a.criticidade][0]}</span><h3>${e(a.nome)}</h3>
      <p class="muted sm">${e(a.area)} · ${e(a.stack)} · equipe dona: <b>${e(a.equipe)}</b> · domínio afetado: <code>${e(a.motivo)}</code></p>${repasseHtml('sistema', R.mudanca.id + ':' + a.id, a.nome + ' · ' + R.mudanca.titulo)}</div>
    ${a.achados.length ? a.achados.map((x, k) => `<article class="si-achado">
        <div class="row between wrap"><b class="si-file">${icon('doc')} ${e(x.arquivo)} <span class="muted">· linha ${x.linha}</span></b>
          <span class="lx-chip ${x.tipo === 'alteracao' ? 'ok' : 'mod'}">${x.tipo === 'alteracao' ? 'Alteração sugerida' : 'Revisar com o texto oficial'}</span></div>
        <p class="sm">${e(x.explica)}</p>
        ${x.diff ? diffHtml(x.diff) : `<pre class="si-diff"><span class="hunk">linha ${x.linha}</span>\n<span class="rev">${e(x.atual)}</span></pre>`}
        ${feito(k) ? `<p class="cp-act">✓ ${feito(k) === 'APROVADA' ? `Aprovada: virou tarefa para <b>${e(a.equipe)}</b>.` : 'Descartada com motivo registrado.'}</p>`
          : `<div class="row gap wrap"><button class="btn sm primary" data-ok="${k}">${icon('check')} Aprovar e abrir tarefa</button><button class="btn sm" data-no="${k}">Descartar</button></div>`}
      </article>`).join('')
    : `<p class="warn-note">${a.repo ? 'Os detectores não acharam dependência desta regra no código conectado.' : `Repositório não conectado: a LexIA sabe pelo cadastro que este sistema toca <b>${e(a.motivo)}</b>. A equipe <b>${e(a.equipe)}</b> recebe a tarefa de verificar.`}</p>
       ${feito('meta') ? `<p class="cp-act">✓ Tarefa de verificação aberta para <b>${e(a.equipe)}</b>.</p>` : `<button class="btn sm primary" data-meta="1">${icon('check')} Abrir tarefa de verificação</button>`}`}
    ${a.repo && R.ia ? `<div class="mt12">${sug ? `<h4>Sugestões da IA (conferidas)</h4>${sug.aceitas.map((s) => `<p class="sm"><b>${e(s.arquivo)}:${s.linha}</b> — ${e(s.o_que_mudar)}</p>`).join('') || '<p class="muted sm">A IA não achou outro ponto.</p>'}${sug.recusadas.length ? `<p class="hint">${sug.recusadas.length} sugestão(ões) recusada(s): o trecho citado não existe no arquivo.</p>` : ''}`
      : `<button class="btn sm ghost" data-ia="1">${icon('spark')} Pedir à IA outros pontos neste repositório</button>`}</div>` : ''}`;
}

export const sistemasPage = {
  title: 'Impacto em sistemas',
  async render() {
    const st = S();
    const D = await api('/api/sistemas'); await carregarRepasses();
    if (!st.mud) st.mud = D.mudancas[0].id;
    state.siData = D;
    if (!st.R || st.R.mudanca.id !== st.mud) { st.R = await api('/api/sistemas/mapear?mudanca=' + encodeURIComponent(st.mud)); st.sel = st.R.afetados[0]?.id; st.todos = false; }
    state.siData = D;
    const R = st.R, rs = R.resumo, lista = st.todos ? R.afetados : R.afetados.slice(0, 12);
    const vig = (d) => (d <= (state.asOf || '2026-11-06') ? ['Vigente', 'ok'] : ['Futura', 'mod']);
    return `<header class="page-head"><div><span class="eyebrow">Conformidade · regra ${e(D.rule_version)}</span><h2>Impacto em sistemas</h2>
      <p class="muted">Quando uma norma muda, a LexIA cruza o portfólio de aplicações, lê o código conectado e aponta <b>o arquivo, a linha e a alteração</b>. Uma pessoa aprova; vira tarefa para a equipe dona do sistema.</p></div></header>
    <div class="si-kpis"><div><b>${n(D.portfolio)}</b><span>aplicações no portfólio</span></div><div><b>${D.repos}</b><span>repositórios conectados</span></div>
      <div><b>${D.mudancas.length}</b><span>mudanças normativas monitoradas</span></div><div><b>${D.tarefas.filter((t) => t.state === 'APROVADA').length}</b><span>alterações aprovadas viraram tarefa</span></div></div>
    <p class="hint">${e(D.aviso)}</p>
    <h3 class="si-h">${icon('book')} 1 · Mudança normativa</h3>
    <div class="si-muds">${D.mudancas.map((m) => { const [vl, vc] = vig(m.vigencia); return `<button type="button" class="si-mud ${m.id === st.mud ? 'on' : ''}" data-mud="${e(m.id)}">
      <span class="row between"><b>${e(m.titulo)}</b><span class="lx-chip ${vc}">${vl} · ${e(fmtDate(m.vigencia))}</span></span><small class="muted">${e(m.norma)}</small><small>${e(m.mudanca)}</small></button>`; }).join('')}</div>
    <h3 class="si-h">${icon('layers')} 2 · Onde isso bate nos sistemas</h3>
    <div class="si-res"><div><b>${n(rs.afetados)}</b><span>de ${n(R.portfolio)} aplicações afetadas</span></div><div class="c"><b>${rs.criticos}</b><span>de criticidade alta (A)</span></div>
      <div><b>${rs.com_codigo}</b><span>com código analisado</span></div><div class="g"><b>${rs.alteracoes}</b><span>pontos de código apontados</span></div><div><b>${R.ms} ms</b><span>para cruzar o portfólio</span></div></div>
    <div class="si-grid mt12">
      <section class="card"><header class="card-h"><h3>Sistemas afetados</h3><span class="muted sm">críticos e com código primeiro</span></header>
        <div class="si-list">${lista.map((a) => `<button type="button" class="si-item ${a.id === st.sel ? 'on' : ''}" data-sel="${e(a.id)}"><span class="lx-chip ${CRIT[a.criticidade][1]}">${a.criticidade}</span>
          <span class="si-t"><b>${e(a.nome)}</b><small>${e(a.area)} · ${e(a.motivo)}</small></span>
          <span class="si-n ${a.achados.length ? 'g' : ''}">${a.repo ? `${a.achados.length} ponto(s)` : 'metadados'}</span></button>`).join('')}</div>
        ${R.afetados.length > 12 ? `<button class="btn sm ghost mt8" id="si-todos" type="button">${st.todos ? 'Mostrar menos' : `Ver todos os ${R.afetados.length}`}</button>` : ''}</section>
      <section class="card si-painel">${painel(st, R)}</section>
    </div>
    ${D.tarefas.length ? `<section class="card mt16"><header class="card-h"><h3>${icon('check', 'h-ic')}3 · Tarefas geradas</h3><button class="btn sm" id="si-csv" type="button">Exportar CSV</button></header>
      <div class="table-wrap"><table class="table compact"><thead><tr><th>Sistema</th><th>Arquivo</th><th>Mudança</th><th>Equipe</th><th>Decisão</th><th>Por</th></tr></thead>
      <tbody>${D.tarefas.map((t) => `<tr><td>${e(t.sistema)}</td><td><code>${e(t.arquivo || '—')}${t.linha ? ':' + t.linha : ''}</code></td><td>${e(D.mudancas.find((m) => m.id === t.mudanca)?.titulo || t.mudanca)}</td><td>${e(t.equipe)}</td><td><span class="lx-chip ${t.state === 'APROVADA' ? 'ok' : 'baixa'}">${e(t.state)}</span>${t.motivo ? `<small class="muted"> ${e(t.motivo)}</small>` : ''}</td><td>${e(t.actor)}</td></tr>`).join('')}</tbody></table></div></section>` : ''}`;
  },
  mount(root, ctx) {
    bindRepasse(root, ctx);
    const st = S(), R = st.R;
    root.querySelectorAll('[data-mud]').forEach((b) => b.addEventListener('click', () => { st.mud = b.dataset.mud; st.R = null; st.dec = {}; ctx.rerender(); }));
    root.querySelectorAll('[data-sel]').forEach((b) => b.addEventListener('click', () => { st.sel = b.dataset.sel; ctx.rerender(); }));
    root.querySelector('#si-todos')?.addEventListener('click', () => { st.todos = !st.todos; ctx.rerender(); });
    const a = R?.afetados.find((x) => x.id === st.sel);
    const decide = async (k, decisao, motivo = '') => {
      const x = k === 'meta' ? { arquivo: '', linha: 0, explica: 'Verificar o sistema (repositório não conectado)' } : a.achados[+k];
      try { await api('/api/sistemas/decidir', { item: { mudanca: R.mudanca.id, sistema: a.nome, equipe: a.equipe, ...x }, decisao, motivo });
        st.dec = { ...(st.dec || {}), [a.id + ':' + k]: decisao }; toast(decisao === 'APROVADA' ? `Tarefa aberta para ${a.equipe}.` : 'Descartada.'); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    };
    root.querySelectorAll('[data-ok]').forEach((b) => b.addEventListener('click', () => decide(b.dataset.ok, 'APROVADA')));
    root.querySelectorAll('[data-no]').forEach((b) => b.addEventListener('click', () => { const m = prompt('Por que descartar? (fica na trilha)'); if (m) decide(b.dataset.no, 'DESCARTADA', m); }));
    root.querySelector('[data-meta]')?.addEventListener('click', () => decide('meta', 'APROVADA'));
    root.querySelector('[data-ia]')?.addEventListener('click', async (ev) => {
      ev.target.disabled = true; ev.target.textContent = 'Lendo o código com IA…';
      try { st.ia[a.id] = await api('/api/sistemas/sugerir', { repo: a.repo, mudanca: R.mudanca.id }); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    });
    root.querySelector('#si-csv')?.addEventListener('click', () => {
      const T = state.siData.tarefas, esc = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`;
      const csv = '﻿' + ['sistema;arquivo;linha;mudanca;equipe;decisao;motivo;por;quando', ...T.map((t) => [t.sistema, t.arquivo, t.linha, t.mudanca, t.equipe, t.state, t.motivo, t.actor, t.created_at].map(esc).join(';'))].join('\n');
      const l = document.createElement('a'); l.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' })); l.download = 'lexia_tarefas_sistemas.csv'; l.click(); URL.revokeObjectURL(l.href);
    });
  },
};
