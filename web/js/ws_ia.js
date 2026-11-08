// Central de IA — página completa: conversa, consulta em português → filtros, inconsistências, rascunhos e transparência.
import { state, api, e, fmtDateTime, card, toast, icon, currentUser, can } from './core.js';
import { chat, send, msgHtml, SUGGEST } from './chat.js';
import { attTag } from './ws_radar.js';

const IS = () => (state.ia = state.ia || { tab: 'chat', interp: null, iq: '', acode: '', profile: 'simples', target: 'emergencia' });
const KIND = { nlp: ['Linguagem natural', '#1570EF'], rag: ['Recuperação + geração', '#68487A'], stats: ['Estatística', '#0EA5E9'], rules: ['Regras versionadas', '#46774E'], ml: ['Aprendizado de máquina', '#DB2777'], draft: ['Redação assistida', '#D4A12E'], match: ['Correspondência', '#63768A'] };
const ACODE = { INATIVA_EM_EMERGENCIA: 'Inativa com emergência declarada', VOLUME_ACIMA_LICENCIADO: 'Volume acima do licenciado', ALTURA_ACIMA_LICENCIADA: 'Altura acima da licenciada', EMERGENCIA_SEM_PAE: 'Emergência sem PAE', DESCARACT_SEM_FASE: 'Descaracterização sem fase', CAPACIDADE_INCOERENTE: 'Capacidade incoerente', ATIPICO_VOLUME_ALTURA: 'Volume/altura atípico', DPA_FORA_PNSB: 'DPA média/alta fora da PNSB', DATA_IMPROVAVEL: 'Data improvável' };

function chatTab(st) {
  return `<div class="ia-chat card flush"><div class="ia-msgs" id="ia-msgs" aria-live="polite">${chat.msgs.length ? chat.msgs.map((m) => msgHtml(m)).join('') : `<div class="ia-welcome">${icon('spark', 'big')}<h3>Pergunte sobre barragens, responsáveis e normas</h3><p class="muted">Eu filtro os dados oficiais, explico a base legal e abro o plano de contingência. Normas são respondidas só com citação verificada.</p><div class="bub-sug">${SUGGEST.map((s) => `<button class="chip-btn" data-s="${e(s)}">${e(s)}</button>`).join('')}</div></div>`}
    ${chat.busy ? '<div class="cm ia typing"><span></span><span></span><span></span></div>' : ''}</div>
    <form class="ia-f" id="ia-f"><div class="seg sm" role="group" aria-label="Linguagem" ${currentUser()?.kind === 'cidadao' ? 'hidden' : ''}>${[['simples', 'Simples'], ['tecnico', 'Técnica']].map(([k, l]) => `<button type="button" class="${st.profile === k ? 'on' : ''}" data-prof="${k}">${l}</button>`).join('')}</div>
      <input id="ia-q" placeholder="Escreva sua pergunta…" aria-label="Pergunta" ${chat.busy ? 'disabled' : ''}><button class="btn primary">${icon('arrow')} Enviar</button></form></div>
    <p class="hint">A linguagem muda o texto, nunca as fontes, condições ou a certeza. ${currentUser()?.kind === 'empresa' ? '<button class="link" data-assistant-tab="agenda">Abrir a agenda do assistente (pendências da sua carteira)</button>' : ''}</p>`;
}

function interpTab(st) {
  const it = st.interp;
  const FL = { dataset: 'Base', uf: 'UF', attention: 'Atenção', owner_kind: 'Tipo de dono', operational_status: 'Situação', signals: 'Sinais', dpa_high: 'DPA alto', population: 'População a jusante', emergency: 'Emergência', small_owner: 'Dono pequeno', text: 'Texto' };
  return `<div class="grid-6-6">${card('Consulta em português → filtros', `<p class="muted">A IA converte seu pedido em filtros estruturados. Um verificador descarta valores fora do vocabulário (UF, sinais, níveis), então a IA não consegue inventar categorias.</p>
    <form id="interp-f" class="row gap mt8"><input class="search" id="interp-q" value="${e(st.iq)}" placeholder="Ex.: cooperativas no Pará com barragem inativa e gente abaixo"><button class="btn primary">Interpretar</button></form>
    <div class="bub-sug mt8">${['barragens largadas em Minas com população abaixo', 'órfãs com dano alto no Rio Grande do Norte', 'pessoa física em MT sem DCE', 'em descaracterização com emergência'].map((s) => `<button class="chip-btn" data-iq="${e(s)}">${e(s)}</button>`).join('')}</div>`, { icon: 'spark' })}
    ${card('Resultado da interpretação', it ? `<div class="row between wrap"><span class="tag" style="--c:${it.engine === 'ia' ? '#68487A' : '#46774E'}">${e(it.engine_label)}</span>${it.note ? `<small class="muted">${e(it.note)}</small>` : ''}</div>
      <table class="table compact mt8"><thead><tr><th>Filtro</th><th>Valor</th></tr></thead><tbody>${Object.entries(it.filters).filter(([, v]) => (Array.isArray(v) ? v.length : v && v !== 'ambos')).map(([k, v]) => `<tr><td>${e(FL[k] || k)}</td><td>${e(Array.isArray(v) ? v.join(', ') : v === true ? 'sim' : v)}</td></tr>`).join('') || '<tr><td colspan="2" class="muted">Nenhum filtro reconhecido.</td></tr>'}</tbody></table>
      <h4>De onde veio cada filtro</h4><div class="cm-chips">${it.chips.map((c, i) => `<span class="chip-f" title="origem: ${e(c.from)}">${e(it.chips_text[i])} <small>← “${e(c.from)}”</small></span>`).join('')}</div>
      ${it.dropped?.length ? `<p class="warn-note">Descartado pelo verificador: ${e(it.dropped.join(', '))}</p>` : ''}
      <button class="btn primary mt12" id="interp-go">${icon('pin')} Ver no Radar</button>` : '<div class="empty"><p>Escreva um pedido para ver os filtros gerados.</p></div>', { icon: 'filter' })}</div>`;
}

function anomTab(st, A) {
  const counts = A.counts;
  return `${card('Inconsistências nos dados oficiais declarados', `<p class="muted">Duas técnicas, nenhuma generativa: <b>regras de coerência</b> (ex.: altura atual maior que a licenciada) e <b>estatística robusta</b> (mediana e desvio absoluto mediano em escala log) para valores atípicos que sugerem erro de digitação ou de unidade. ${A.total_records} estruturas analisadas.</p>
    <div class="an-grid">${counts.map(([c, n]) => `<button class="an-c ${st.acode === c ? 'on' : ''}" data-acode="${c}"><b>${n}</b><span>${e(ACODE[c] || c)}</span></button>`).join('')}</div>
    <div class="row between wrap mt12"><small class="muted">${st.acode ? `Filtrando: ${e(ACODE[st.acode])} · <button class="link" data-acode="">mostrar todas</button>` : 'Clique num tipo para filtrar.'}</small><a class="btn sm" href="/api/export/anomalias.csv" download>${icon('doc')} Exportar CSV</a></div>
    <div class="table-wrap tall mt8"><table class="table compact"><thead><tr><th>Estrutura</th><th>Inconsistência</th><th>Detalhe</th><th>Método</th></tr></thead><tbody>${A.items.map((a) => `<tr><td><a href="#/radar?id=${encodeURIComponent(a.id)}">${e(a.name)}</a><br><small class="muted">${e(a.municipio)}/${e(a.uf)}</small></td><td>${e(a.label)}${a.basis ? `<br><small class="muted">${e(a.basis)}</small>` : ''}</td><td>${e(a.detail)}</td><td><small>${e(a.method)}</small></td></tr>`).join('')}</tbody></table></div>
    <p class="hint">${e(A.reading)}</p>`, { icon: 'filter' })}`;
}

function draftsTab(D) {
  const ST = { RASCUNHO: ['Rascunho', '#D4A12E'], APROVADO_PARA_ENVIO: ['Aprovado para envio', '#46774E'], DESCARTADO: ['Descartado', '#63768A'] };
  return card('Rascunhos de representação', D ? (D.items.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>Barragem</th><th>Atenção</th><th>Situação</th><th>Gerado</th><th>Decisão</th></tr></thead><tbody>${D.items.map((d) => `<tr><td>${d.id}</td><td><a href="#/radar?id=${encodeURIComponent(d.dam_id)}">${e(d.dam_name || d.dam_id)}</a> <small class="muted">${e(d.uf || '')}</small></td><td>${d.attention ? attTag(d.attention) : ''}</td><td><span class="tag" style="--c:${ST[d.state][1]}">${ST[d.state][0]}</span></td><td>${e(d.created_by)}<br><small class="muted">${fmtDateTime(d.created_at)}</small></td><td>${d.decided_by ? `${e(d.decided_by)}<br><small class="muted">${e(d.reason)}</small>` : '—'}</td></tr>`).join('')}</tbody></table></div>`
    : '<div class="empty"><p>Nenhum rascunho ainda. Abra uma barragem no Radar, aba <b>Representação</b>.</p><a class="btn primary mt8" href="#/radar">Abrir o Radar</a></div>')
    : '<div class="empty"><p>Rascunhos ficam na área empresarial.</p></div>', { icon: 'doc', right: '<small class="muted">Quem gera não aprova · tudo na trilha de auditoria</small>' });
}

function riskTab(M) {
  if (!M.available) return `<div class="empty"><p>${e(M.reason)}</p></div>`;
  const m = M.metrics, maxc = Math.max(...M.top_features.map((f) => Math.abs(f.coef)));
  const TT = TARGET_TXT[M.target || 'emergencia'];
  return `<section class="risk-hero"><div><span class="eyebrow">Predição · aprendizado de máquina sobre dados oficiais · versão #${M.version_id ?? ''}</span><h3>${TT[0]}</h3>
      <p>${e(M.question)} O modelo aprendeu com as ${M.positives} barragens ${e(M.positive_label)} e procurou o mesmo perfil nas demais.${M.feedback_used ? ` Esta versão já usa ${M.feedback_used} conferência(s) humana(s).` : ''}</p></div>
      <div class="risk-big"><b>${M.flagged_total}</b><span>${TT[1]}</span></div></section>
    <div class="risk-metrics">
      <div><b>${m.cv_auc.toFixed(2).replace('.', ',')}</b><span>AUC na validação cruzada (${m.folds} dobras)</span><small>1 = perfeito · 0,5 = sorteio</small></div>
      <div><b>${Math.round(m.precision_top50 * 100)}%</b><span>das 50 mais suspeitas eram de fato positivas</span><small>na validação, sem ver a resposta</small></div>
      <div><b>${String(m.lift_top50).replace('.', ',')}×</b><span>melhor que escolher ao acaso</span><small>taxa-base ${Math.round(m.base_rate * 100)}%</small></div>
      <div><b>${M.trained_on}</b><span>barragens na PNSB usadas no treino</span><small>${M.features} variáveis técnicas</small></div></div>
    <div class="grid-8-4 mt16">${card('Barragens para conferir', `<div class="table-wrap tall"><table class="table"><thead><tr><th>Barragem</th><th>Parecença</th><th>Por que o modelo apontou</th><th>Radar</th></tr></thead><tbody>${M.items.map((x) => `<tr><td><a href="#/radar?id=${encodeURIComponent(x.id)}"><b>${e(x.name)}</b></a><br><small class="muted">${e(x.municipio)}/${e(x.uf)} · ${e(x.owner_kind)} · ${e(x.status || '')}</small></td>
        <td><span class="pbar risk"><i style="width:${Math.round(x.p * 100)}%"></i></span><small>${Math.round(x.p * 100)}% · percentil ${x.percentile}</small></td>
        <td><ul class="why">${x.why.map((w) => `<li>${e(w.feature)}</li>`).join('')}</ul></td><td>${attTag(x.attention)}</td></tr>`).join('')}</tbody></table></div>`, { icon: 'target', right: `<small class="muted">limiar: 1º quartil das barragens em emergência (${Math.round(M.threshold * 100)}%)</small>` })}
      ${card('O que mais pesa', `<div class="hbars">${M.top_features.slice(0, 10).map((f) => `<div class="hb coef"><span title="${e(f.feature)}">${e(f.feature)}</span><i style="--w:${(100 * Math.abs(f.coef)) / maxc}%;--c:${f.coef > 0 ? '#DB2777' : '#46774E'}"></i><b>${f.coef > 0 ? '+' : ''}${String(f.coef).replace('.', ',')}</b></div>`).join('')}</div><p class="hint">Rosa aumenta a parecença com emergência; verde reduz.</p>`, { icon: 'chart' })}</div>
    ${card('Ficha do modelo', `<dl class="kv"><dt>Versão</dt><dd><code>${e(M.version)}</code></dd><dt>Método</dt><dd>${e(M.method)}</dd><dt>Leitura</dt><dd>${e(M.reading)}</dd></dl><h4>Limites</h4><ul class="ticks no">${M.limits.map((l) => `<li>${e(l)}</li>`).join('')}</ul>`, { icon: 'shield' })}`;
}

const TARGET_TXT = {
  emergencia: ['Barragens que parecem estar em emergência, mas declaram que não estão', 'barragens com perfil de emergência<br>declaradas “sem emergência”'],
  dce: ['Quem deve falhar na próxima declaração de estabilidade (campanha de março/2027)', 'barragens atestadas hoje<br>com perfil de quem falha'],
};

function predTab(st, M) {
  const seg = `<div class="seg pred-seg" role="group" aria-label="Modelo">${[['emergencia', 'Emergência não declarada'], ['dce', 'Falha na próxima DCE']].map(([k, l]) => `<button class="${st.target === k ? 'on' : ''}" data-target="${k}">${l}</button>`).join('')}</div>`;
  return seg + riskTab(M);
}

const fmtPct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
const TOOL_LABEL = { verificar_fontes: ['Perceber', 'database'], monitorar_modelos: ['Avaliar', 'chart'], retreinar: ['Aprender', 'refresh'], comparar: ['Decidir', 'filter'], priorizar: ['Priorizar', 'target'], propor_acoes: ['Agir (propor)', 'check'], planejador_ia: ['Planejador IA', 'spark'] };

function agentTab(A) {
  const L = A.last, canRun = can('agent.run'), canDec = can('agent.decide');
  const step = (s) => { const [t, ic] = TOOL_LABEL[s.tool] || [s.tool, 'spark']; return `<li class="ag-step ${s.error ? 'err' : ''} ${s.skipped ? 'skip' : ''}"><span class="ag-ic">${icon(ic)}</span><div><b>${e(t)}</b> <code>${e(s.tool)}</code>${s.skipped ? ' <span class="mini-t">pulado</span>' : ''}<pre>${e(JSON.stringify(s.output, null, 1).slice(0, 700))}</pre></div></li>`; };
  const act = (a) => `<article class="ag-act k-${e(a.kind)}"><div class="row between wrap"><b>${e(a.title)}</b><span class="tag" style="--c:${a.kind === 'promover_modelo' ? '#68487A' : '#DB2777'}">${a.kind === 'promover_modelo' ? 'Promoção de modelo' : `Valor ${String(a.value).replace('.', ',')}`}</span></div>
    <p class="muted sm">${e(a.rationale)}</p>
    <div class="row gap wrap">${a.kind === 'conferir' ? `<a class="btn sm" href="#/radar?id=${encodeURIComponent(a.dam_id)}">Abrir ficha</a>` : ''}
    ${canDec ? `<form class="ag-dec" data-aid="${a.id}"><input placeholder="Justificativa (obrigatória)" aria-label="Justificativa"><button class="btn sm primary" data-ok="1">Aprovar</button><button class="btn sm" data-ok="0">${a.kind === 'conferir' ? 'Não procede' : 'Rejeitar'}</button></form>` : '<small class="muted">Entre com papel que pode decidir.</small>'}</div></article>`;
  return `<section class="ag-hero"><div><span class="eyebrow">Agente autônomo · aprovação humana</span><h3>O agente vigia as fontes, aprende com as conferências e propõe o que fazer</h3>
      <p>Roda sozinho ao iniciar e a cada novo snapshot oficial. Percebe → avalia → aprende → decide → prioriza → propõe. Nada sai do sistema e nenhum modelo muda sem um humano aprovar.</p>
      <div class="row gap wrap mt8"><span class="tag" style="--c:${A.planner === 'ia' ? '#68487A' : '#46774E'}">Planejador: ${A.planner === 'ia' ? 'Claude (uso de ferramentas)' : 'regras (mesmas ferramentas)'}</span>${canRun ? `<button class="btn primary" id="ag-run" ${A.running ? 'disabled' : ''}>${icon('spark')} ${A.running ? 'Executando…' : 'Executar agente agora'}</button>` : ''}</div></div>
      <div class="risk-big"><b>${A.pending.length}</b><span>propostas aguardando<br>aprovação humana</span></div></section>
    ${L ? `<div class="grid-6-6 mt16">${card(`Última execução · #${L.id}`, `<p><b>${e(L.summary?.text || '')}</b></p><p class="muted sm">Gatilho: ${e(L.trigger)} · ${fmtDateTime(L.finished_at)}</p><ol class="ag-steps">${L.steps.map(step).join('')}</ol>`, { icon: 'monitor' })}
      ${card('Propostas para aprovar', A.pending.length ? A.pending.map(act).join('') : '<div class="empty"><p>Nenhuma proposta pendente. Execute o agente ou aguarde o próximo snapshot.</p></div>', { icon: 'check', right: '<small class="muted">“Não procede” vira rótulo negativo no próximo treino</small>' })}</div>` : '<div class="empty mt16"><p>O agente ainda não rodou.</p></div>'}
    ${A.decided.length ? card('Decisões recentes', `<div class="table-wrap"><table class="table compact"><thead><tr><th>Proposta</th><th>Decisão</th><th>Quem</th><th>Justificativa</th></tr></thead><tbody>${A.decided.map((a) => `<tr><td>${e(a.title)}</td><td>${a.state === 'APROVADA' ? '✓ Aprovada' : '✕ Rejeitada'}</td><td>${e(a.decided_by)}<br><small class="muted">${fmtDateTime(a.decided_at)}</small></td><td>${e(a.reason)}</td></tr>`).join('')}</tbody></table></div>`, { icon: 'users' }) : ''}
    ${card('Execuções', `<div class="table-wrap short"><table class="table compact"><thead><tr><th>#</th><th>Gatilho</th><th>Planejador</th><th>Fim</th><th>Propostas</th></tr></thead><tbody>${A.runs.map((r) => `<tr><td>${r.id}</td><td>${e(r.trigger)}</td><td>${e(r.planner)}</td><td>${fmtDateTime(r.finished_at)}</td><td>${r.actions_created ?? '—'}</td></tr>`).join('')}</tbody></table></div>`, { icon: 'refresh' })}`;
}

function cycleTab(MM) {
  const stage = (n, t, d, ic) => `<li><span class="cy-n">${n}</span>${icon(ic)}<b>${t}</b><small>${d}</small></li>`;
  const block = (t, m) => {
    const ch = m.champion, cd = m.challenger, mo = m.monitor;
    const mrow = (v, lab) => v ? `<tr><td>${lab} #${v.id}<br><small class="muted">${e(v.version)} · ${fmtDateTime(v.created_at)}</small></td><td>${String(v.metrics.cv_auc).replace('.', ',')}</td><td>${fmtPct(v.metrics.precision_top10)}</td><td>${fmtPct(v.metrics.precision_top50)}</td><td>${v.feedback_used}</td><td>${v.flagged_total}</td></tr>` : '';
    return card(m.name, `<p class="muted sm">${e(m.question)}</p>
      <div class="cy-mon"><div><b>${mo.drift_status || '—'}</b><span>Deriva dos dados (PSI máx. ${String(mo.drift_psi_max ?? '—').replace('.', ',')})</span></div>
        <div><b>${fmtPct(mo.field_precision)}</b><span>Acerto nas conferências humanas (${mo.feedback_on_flagged || 0})</span></div>
        <div><b>${mo.new_feedback_since_champion || 0}</b><span>retornos novos desde o campeão</span></div>
        <div><b>${mo.retrain_recommended ? 'Sim' : 'Não'}</b><span>retreino recomendado</span></div></div>
      <div class="table-wrap mt8"><table class="table compact"><thead><tr><th>Versão</th><th>AUC</th><th>Precisão top 10</th><th>Precisão top 50</th><th>Retornos usados</th><th>Alertas</th></tr></thead><tbody>${mrow(ch, '🏆 Campeão')}${mrow(cd, '⚔ Desafiante')}</tbody></table></div>
      ${m.compare ? `<div class="cy-cmp"><b>Comparação:</b> ΔAUC ${m.compare.delta_auc >= 0 ? '+' : ''}${String(m.compare.delta_auc).replace('.', ',')} · Δprecisão top 50 ${m.compare.delta_prec50 >= 0 ? '+' : ''}${String(m.compare.delta_prec50).replace('.', ',')} → <b>${e(m.compare.recommendation)}</b><br><small class="muted">${e(m.compare.rule)}</small>
        ${can('model.promote') ? `<form class="cy-prom" data-vid="${cd.id}"><input placeholder="Justificativa" aria-label="Justificativa"><button class="btn sm primary" data-act="promote">Promover</button><button class="btn sm" data-act="discard">Descartar</button></form>` : ''}</div>`
        : (can('model.train') ? `<button class="btn sm mt8" data-train="${t}">${icon('refresh')} Treinar desafiante com o retorno atual</button>` : '')}
      <details class="mt8"><summary>Histórico de versões (${m.versions.length}) e retornos humanos (${m.feedback.length})</summary>
        <ul class="history">${m.versions.map((v) => `<li><strong>#${v.id} · ${e(v.status)}</strong><small>AUC ${v.metrics.cv_auc} · ${v.feedback_used} retorno(s) · por ${e(v.created_by)}${v.promoted_by ? ` · promovido por ${e(v.promoted_by)}: “${e(v.promote_reason || '')}”` : ''}</small></li>`).join('')}</ul>
        <ul class="history">${m.feedback.map((f) => `<li><strong>${f.label ? '✓ Confirmado' : '✕ Não procede'} · <a href="#/radar?id=${encodeURIComponent(f.dam_id)}">${e(f.dam_id)}</a></strong><small>${e(f.actor)} · ${fmtDateTime(f.at)} · ${e(f.reason)}</small></li>`).join('') || '<li class="muted">Sem retorno humano ainda.</li>'}</ul></details>`, { icon: 'refresh' });
  };
  return `<ol class="cycle">${stage(1, 'Dados oficiais', 'snapshot SIGBM com SHA-256', 'database')}${stage(2, 'Treino', 'regressão logística, 52 variáveis', 'lab')}${stage(3, 'Validação', 'validação cruzada em 5 dobras', 'filter')}${stage(4, 'Implantação', 'campeão versionado', 'check')}${stage(5, 'Monitoramento', 'deriva + acerto de campo', 'chart')}${stage(6, 'Retorno humano', 'confirmo / não procede', 'users')}${stage(7, 'Retreino', 'desafiante com o retorno', 'refresh')}${stage(8, 'Promoção', 'só com aprovação humana', 'shield')}</ol>
    <div class="grid-6-6 mt16">${Object.entries(MM).map(([t, m]) => block(t, m)).join('')}</div>`;
}

function costCard(U) {
  if (!U) return '';
  const pm = Object.entries(U.por_modelo || {});
  return card('Custo da IA generativa: determinístico primeiro', `<div class="eff-grid"><div><b>${U.resolvido_sem_ia_pct == null ? '—' : U.resolvido_sem_ia_pct + '%'}</b><span>dos pedidos de hoje resolvidos sem IA (regra ou cache)</span></div>
      <div><b>${U.deterministico}</b><span>resolvidos por regras/respostas controladas</span></div><div><b>${U.cache}</b><span>respostas reaproveitadas do cache</span></div><div><b>${U.chamadas} / ${U.teto_diario}</b><span>chamadas pagas hoje / teto diário</span></div></div>
    <p class="sm mt8"><b>Política ${e(U.politica)}:</b> regras e respostas conferidas resolvem primeiro; a IA só entra quando elas não dão conta, usando o modelo mais barato para a tarefa (filtros e resumos → modelo leve; perguntas e denúncias → modelo padrão). Agente, predição, radar, compliance e monitoramento ONS rodam localmente, sem custo de IA.</p>
    ${pm.length ? `<p class="hint">Hoje por modelo: ${pm.map(([m, n]) => `${e(m)} × ${n}`).join(' · ')}</p>` : ''}
    ${U.interno ? costTable('Por cliente (Customer/organização)', U.por_cliente, U.preco_configurado) + costTable('Por funcionalidade', U.por_funcionalidade, U.preco_configurado) : costTable('Uso da sua organização', U.por_cliente, U.preco_configurado)}
    <p class="hint">Tokens são estimados (~4 caracteres por token); custo em dinheiro só aparece com preço configurado. Documento idêntico enviado de novo (mesmo SHA-256) não é regravado nem reprocessado.</p>`, { icon: 'chart' });
}

function costTable(title, M, priced) {
  const rows = Object.entries(M || {}).sort((a, b) => b[1].requisicoes - a[1].requisicoes).slice(0, 10);
  if (!rows.length) return '';
  return `<h4 class="mt12">${e(title)}</h4><table class="table compact"><thead><tr><th>${title.startsWith('Por cliente') ? 'Cliente' : 'Funcionalidade'}</th><th>Requisições</th><th>Regras</th><th>Cache</th><th>IA paga</th><th>Tokens (est.)</th>${priced ? '<th>US$ (est.)</th>' : ''}</tr></thead>
    <tbody>${rows.map(([k, b]) => `<tr><td>${e(k)}</td><td>${b.requisicoes}</td><td>${b.deterministico}</td><td>${b.cache}</td><td>${b.ia}</td><td>${b.tokens_est.toLocaleString('pt-BR')}</td>${priced ? `<td>${b.custo_usd_est ?? '—'}</td>` : ''}</tr>`).join('')}</tbody></table>`;
}

const CATN = { relevancia_filtros: 'Relevância (pergunta → filtros)', normas_denuncia: 'Normas corretas (denúncia)', versao_vigente: 'Versão vigente por dispositivo', roteamento: 'Roteamento para a pessoa certa',
  perguntas: 'Resposta com fonte ou abstenção', alucinacao: 'Sem alucinação (verificadores)', isolamento: 'Isolamento entre empresas',
  setor_normas: 'Normas do setor certo (e recusa das outras)', donos: 'Nenhum alerta sem dono', extracao: 'Norma → obrigação (trecho literal)' };
const AREA_N = { juridico: 'Jurídico', operacional: 'Operacional', seguranca: 'Segurança', ambiental: 'Ambiental', trabalhista: 'Trabalhista', radiologico: 'Radiológico', documental: 'Documental' };
const SET_N = { mineracao: 'Mineração', energia: 'Energia', saneamento: 'Saneamento', industria: 'Indústria' };
function coverageCard(C) {
  if (!C || C.error) return '';
  return card('Matriz de cobertura: setor × área', `<p class="sm">Cada célula mostra quantas normas do catálogo cobrem aquela área naquele setor (passe o mouse para ver quais). Célula vazia é <b>lacuna visível</b>: vai para a curadoria completar, não é tratada como "não se aplica".</p>
    <div class="table-wrap"><table class="table compact cov"><thead><tr><th>Setor</th>${C.areas.map((a) => `<th>${e(AREA_N[a] || a)}</th>`).join('')}</tr></thead>
    <tbody>${C.setores.map((s) => `<tr><td><b>${e(SET_N[s] || s)}</b></td>${C.areas.map((a) => { const L = C.matriz[s][a]; return `<td class="${L.length ? '' : 'gap'}" title="${e(L.map((x) => x.ref).join(' · ') || 'Lacuna: sem norma no catálogo')}">${L.length || '—'}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>
    <div class="row gap wrap mt8"><span class="lx-chip ${C.lacunas.length ? 'alta' : 'ok'}">${C.lacunas.length} lacuna(s) na matriz</span><span class="lx-chip ${C.sem_classificacao.length ? 'crit' : 'ok'}">${C.sem_classificacao.length} norma(s) sem classificação</span><span class="muted sm">${C.total_normas} normas no catálogo · regra ${e(C.rule_version)}</span></div>
    ${C.lacunas.length ? `<p class="hint">Lacunas: ${C.lacunas.map((l) => `${SET_N[l.setor]} × ${AREA_N[l.area]}`).join(' · ')}.</p>` : ''}`, { icon: 'layers' });
}
function evalTab(R) {
  if (!R || R.error) return '<div class="empty"><p>Avaliação indisponível.</p></div>';
  const pct = (x) => Math.round(x * 100) + '%';
  return card(`Avaliação da IA · ${e(R.versao)} · ${R.aprovados}/${R.total} casos`, `<div class="eff-grid">${Object.entries(R.por_categoria).map(([k, v]) => `<div><b style="color:${v.taxa === 1 ? '#46774E' : '#C83037'}">${pct(v.taxa)}</b><span>${e(CATN[k] || k)} (${v.ok}/${v.total})</span></div>`).join('')}
      <div><b>${R.normas.precisao == null ? '—' : pct(R.normas.precisao)} / ${R.normas.recall == null ? '—' : pct(R.normas.recall)}</b><span>precisão / recall das normas contra o gabarito</span></div></div>
    <p class="warn-note mt8">${e(R.aviso)}</p>
    <div class="row gap wrap mt8"><button class="btn sm" id="ev-run">${icon('refresh')} Rodar de novo</button><span class="muted sm">Executada em ${e(R.executado_em)} · custo de IA: ${e(R.custo_ia)}</span></div>
    <table class="table compact mt12"><thead><tr><th></th><th>Categoria</th><th>Caso</th><th>Resultado</th></tr></thead><tbody>${R.casos.map((c) => `<tr><td>${c.ok ? '✓' : '✗'}</td><td>${e(CATN[c.categoria] || c.categoria)}</td><td>${e(c.caso)}</td><td><small>${e(c.detalhe)}</small></td></tr>`).join('')}</tbody></table>`, { icon: 'check' });
}

function transpTab(S) {
  const g = S.llm.enabled;
  return `<div class="ia-trans">${S.capabilities.map((c) => `<div class="cap"><span class="tag" style="--c:${KIND[c.kind][1]}">${KIND[c.kind][0]}</span><b>${e(c.name)}</b><p>${e(c.engine)}</p></div>`).join('')}</div>
  <div class="grid-6-6 mt16">${card('O que a IA faz', `<ul class="ticks"><li>Converte pedidos em português em filtros conferidos.</li><li>Redige respostas a partir de trechos recuperados, com citação literal conferida.</li><li>Aponta inconsistências estatísticas e de coerência nos dados oficiais.</li><li>Prepara rascunhos com os campos da fonte, para revisão humana.</li></ul>`, { icon: 'check' })}
    ${card('O que a IA nunca faz', `<ul class="ticks no"><li>Declarar conformidade, aplicabilidade ou “barragem abandonada”.</li><li>Enviar ofício, e-mail ou representação sozinha.</li><li>Alterar fontes, vigência, condições ou certeza ao trocar a linguagem.</li><li>Exibir ou buscar dados de pessoas físicas.</li></ul>`, { icon: 'shield' })}</div>
  ${currentUser()?.role !== 'curador' ? card('Modelo e modo atual', `<dl class="kv"><dt>IA generativa</dt><dd>${g ? `Conectada · <code>${e(S.llm.model)}</code>` : 'Desligada: o sistema usa regras e respostas controladas'}</dd><dt>Princípio</dt><dd>A IA propõe; regras versionadas verificam; humano competente confirma.</dd></dl>`, { icon: 'monitor' }) : card('Modelo e modo atual (equipe LexIA)', `<dl class="kv"><dt>IA generativa</dt><dd>${g ? `Conectada · <code>${e(S.llm.model)}</code>` : 'Desligada: o sistema usa regras e respostas controladas (nada é rotulado como IA generativa)'}</dd><dt>Provedor</dt><dd>${({ bedrock: 'Amazon Bedrock (na conta AWS do cliente)', gemini: 'Google Gemini', anthropic: 'Anthropic API (Claude)' })[S.llm.provider] || S.llm.provider} · alternável por <code>TORRE_LLM_PROVIDER</code></dd><dt>Pacote</dt><dd>${S.llm.package_installed ? 'anthropic instalado' : 'anthropic não instalado'}</dd><dt>Chave</dt><dd>${S.llm.api_key_present ? 'configurada no servidor' : 'ausente (defina ANTHROPIC_API_KEY)'}</dd><dt>Princípio</dt><dd>A IA propõe; regras versionadas verificam; humano competente confirma.</dd></dl>`, { icon: 'monitor' })}`;
}

export const ia = {
  citizen: true, both: true,
  async render() {
    const st = IS(), S = await api('/api/ai/status'), gen = S.llm.enabled;
    const emp = currentUser()?.kind === 'empresa';
    const T = [['chat', 'Conversa', 'spark'], ['agente', 'Agente', 'monitor'], ['risco', 'Predição', 'target'], ['ciclo', 'Ciclo de evolução', 'refresh'], ['interp', 'Consulta → filtros', 'filter'], ['anom', 'Inconsistências', 'alert'], ['eval', 'Avaliação', 'check'], ...(emp ? [['drafts', 'Rascunhos', 'doc']] : []), ['transp', 'Como a IA funciona', 'shield']];
    if (!emp) T.splice(0, T.length, ...T.filter(([k]) => ['chat', 'interp', 'transp'].includes(k)));   // cidadão: só o que é útil para ele
    if (!T.some(([k]) => k === st.tab)) st.tab = 'chat';
    let body = '';
    if (st.tab === 'chat') body = chatTab(st);
    else if (st.tab === 'interp') body = interpTab(st);
    else if (st.tab === 'risco') body = predTab(st, await api('/api/ml/predictions?target=' + st.target));
    else if (st.tab === 'agente') body = agentTab(await api('/api/agent'));
    else if (st.tab === 'ciclo') body = cycleTab(await api('/api/ml/models'));
    else if (st.tab === 'anom') body = anomTab(st, await api('/api/ai/anomalies?limit=400' + (st.acode ? '&code=' + st.acode : '')));
    else if (st.tab === 'eval') body = evalTab(await api('/api/ai/eval' + (st.evRefresh ? '?refresh=1' : '')).catch(() => null)) + coverageCard(await api('/api/cobertura').catch(() => null)), st.evRefresh = false;
    else if (st.tab === 'drafts') body = draftsTab(await api('/api/radar/drafts').catch(() => null));
    else body = (emp ? costCard(await api('/api/ai/usage').catch(() => null)) : '') + transpTab(S);
    return `<section class="ia-hero"><div class="ia-hero-t"><span class="ia-orb">${icon('spark')}</span><div><span class="eyebrow light">Assistente da LexIA</span><h2>Central de IA</h2><p>Filtra os dados oficiais em português, explica a base legal e aponta inconsistências. Toda conclusão passa por um humano.</p></div></div>
      <div class="ia-status"><span class="ia-dot ${gen ? 'on' : ''}"></span><div><b>${gen ? 'IA generativa conectada' : 'Modo controlado'}</b><small>${gen ? e(S.llm.model) + ' · com verificador' : 'Regras, estatística e respostas pré-validadas'}</small></div></div>
      <ol class="ia-flow"><li>${icon('spark')}<b>IA propõe</b></li><li>${icon('filter')}<b>Regras verificam</b></li><li>${icon('user')}<b>Humano confirma</b></li></ol></section>
    <div class="tabs ia-tabs" role="tablist">${T.map(([k, l, ic]) => `<button role="tab" class="tab ${st.tab === k ? 'on' : ''}" aria-selected="${st.tab === k}" data-iatab="${k}">${icon(ic)}${l}</button>`).join('')}</div>${body}`;
  },
  mount(root, ctx) {
    const st = IS();
    root.querySelectorAll('[data-target]').forEach((b) => b.addEventListener('click', () => { st.target = b.dataset.target; ctx.rerender(); }));
    root.querySelector('#ag-run')?.addEventListener('click', async (ev) => { ev.target.disabled = true; ev.target.textContent = 'Executando…'; try { const r = await api('/api/agent/run', { go: true }); toast(r.summary?.text || 'Agente executado.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); });
    root.querySelectorAll('.ag-dec').forEach((f) => f.querySelectorAll('[data-ok]').forEach((b) => b.addEventListener('click', async (ev) => {
      ev.preventDefault(); const reason = f.querySelector('input').value.trim(); if (!reason) return toast('Escreva a justificativa.', 'err');
      try { const r = await api('/api/agent/decide', { id: +f.dataset.aid, approve: b.dataset.ok === '1', reason }); toast(r.effect || 'Decisão registrada.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender();
    })));
    root.querySelectorAll('[data-train]').forEach((b) => b.addEventListener('click', async () => { b.disabled = true; b.textContent = 'Treinando…'; try { const v = await api('/api/ml/train', { target: b.dataset.train }); toast(`Desafiante #${v.id} treinado (AUC ${v.metrics.cv_auc}).`); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); }));
    root.querySelectorAll('.cy-prom').forEach((f) => f.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', async (ev) => {
      ev.preventDefault(); const reason = f.querySelector('input').value.trim(); if (!reason) return toast('Escreva a justificativa.', 'err');
      try { await api('/api/ml/' + b.dataset.act, { id: +f.dataset.vid, reason }); toast(b.dataset.act === 'promote' ? 'Desafiante promovido a campeão.' : 'Desafiante descartado.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender();
    })));
    root.querySelector('#ev-run')?.addEventListener('click', () => { st.evRefresh = true; ctx.rerender(); });
    root.querySelectorAll('[data-iatab]').forEach((b) => b.addEventListener('click', () => { st.tab = b.dataset.iatab; ctx.rerender(); }));
    root.querySelectorAll('[data-prof]').forEach((b) => b.addEventListener('click', () => { st.profile = b.dataset.prof; ctx.rerender(); }));
    const m = root.querySelector('#ia-msgs'); if (m) m.scrollTop = m.scrollHeight;
    root.querySelector('#ia-f')?.addEventListener('submit', (ev) => { ev.preventDefault(); send(root.querySelector('#ia-q').value, st.profile); });
    root.querySelectorAll('[data-s]').forEach((b) => b.addEventListener('click', () => send(b.dataset.s, st.profile)));
    if (st.tab === 'chat') { const fn = () => { if (location.hash.startsWith('#/ia') && st.tab === 'chat') ctx.rerender(); }; chat.listeners.add(fn); ctx.onLeave(() => chat.listeners.delete(fn)); root.querySelector('#ia-q')?.focus(); }
    const interp = async (q) => { st.iq = q; try { st.interp = await api('/api/ai/interpret?q=' + encodeURIComponent(q)); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); };
    root.querySelector('#interp-f')?.addEventListener('submit', (ev) => { ev.preventDefault(); interp(root.querySelector('#interp-q').value); });
    root.querySelectorAll('[data-iq]').forEach((b) => b.addEventListener('click', () => interp(b.dataset.iq)));
    root.querySelector('#interp-go')?.addEventListener('click', () => {
      const it = st.interp; state.radar = { ...(state.radar || {}), dataset: it.filters.dataset, filters: it.filters, chips: it.chips_text, engine: it.engine === 'ia' ? 'IA propôs, verificador conferiu' : 'Interpretado por regras', q: st.iq, sel: null, page: 0, ptab: 'radar', ftab: 'sinais' };
      ctx.go('radar');
    });
    root.querySelectorAll('[data-acode]').forEach((b) => b.addEventListener('click', () => { st.acode = b.dataset.acode; ctx.rerender(); }));
  },
};
