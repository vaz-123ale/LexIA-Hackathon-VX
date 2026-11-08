// Radar de abandono e barragens órfãs — sinais explicáveis (SIGBM/ANM + SNISB/ANA), responsáveis, plano de contingência e representação.
import { state, data, api, e, fmtDate, fmtDateTime, card, toast, icon, can, currentUser } from './core.js';
import { project } from './map.js';
import { satView } from './geoview.js';

export const ATT = { 'Crítica': ['#C83037', '▲▲'], 'Alta': ['#D9762D', '▲'], 'Moderada': ['#D4A12E', '■'], 'Baixa': ['#63768A', '▼'], 'Sem sinal': ['#9EABAE', '·'] };
export const attTag = (a) => `<span class="tag att" style="--c:${ATT[a]?.[0] || '#94A3B8'}"><i aria-hidden="true">${ATT[a]?.[1] || ''}</i>${e(a)}</span>`;
const VB = [100, 100, 545, 425];
const UF_NAME = { AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul', MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco', PI: 'Piauí', PR: 'Paraná', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte', RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina', SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins' };
const STEP_ST = { pendente: 'Pendente', em_andamento: 'Em andamento', feito: 'Feito', nao_aplicavel: 'Não se aplica' };
const RS = () => (state.radar = state.radar || { dataset: 'mineracao', filters: {}, chips: [], engine: null, sel: null, ftab: 'sinais', page: 0, q: '', ptab: 'radar' });

function qsOf(r) {
  const f = r.filters, p = new URLSearchParams({ dataset: r.dataset, limit: 3000 });
  for (const k of ['uf', 'attention', 'owner_kind', 'operational_status', 'signals']) if (f[k]?.length) p.set(k, f[k].join(','));
  for (const k of ['dpa_high', 'population', 'emergency', 'small_owner', 'hidden_risk']) if (f[k]) p.set(k, '1');
  if (f.text) p.set('q', f.text);
  return p.toString();
}

const kpi = (k, v, label, ic, filt) => `<button class="kpi kpi-btn" style="--k:${k}" data-kfilter='${e(JSON.stringify(filt))}'><span class="kpi-ic">${icon(ic)}</span><span><span class="kpi-v">${v}</span><span class="kpi-l">${label}</span></span></button>`;

function mapSvg(items, sel) {
  const byUf = {};
  items.forEach((x) => { if (x.attention === 'Crítica' || x.attention === 'Alta') byUf[x.uf] = (byUf[x.uf] || 0) + 1; });
  const max = Math.max(1, ...Object.values(byUf));
  const SH = ['#E8E2CA', '#EFDDBF', '#ECCBA4', '#E4B58A', '#D99B72', '#C9805E'];  // terra: quanto mais escuro, mais barragens em crítica/alta no estado
  const sh = (n) => (n ? SH[Math.min(5, 1 + Math.floor((n / max) * 4.999))] : SH[0]);
  const ufs = data.states.features.map((f) => `<path class="rd-uf" d="${f.path}" fill="${sh(byUf[f.uf] || 0)}" data-uf="${f.uf}" role="button" tabindex="0" aria-label="Filtrar ${e(UF_NAME[f.uf])}"><title>${e(UF_NAME[f.uf])}: ${byUf[f.uf] || 0} em atenção crítica/alta</title></path>`).join('');
  const lbl = data.states.features.map((f) => `<text class="rd-lbl" x="${f.cx}" y="${+f.cy + 3}">${f.uf}</text>`).join('');
  const order = { 'Sem sinal': 0, Baixa: 1, Moderada: 2, Alta: 3, 'Crítica': 4 };
  const pts = [...items].filter((x) => x.lat != null).sort((a, b) => order[a.attention] - order[b.attention]).map((x) => {
    const [cx, cy] = project(x.lat, x.lon), on = sel === x.id, r = on ? 6 : (x.attention === 'Crítica' ? 3.4 : x.attention === 'Alta' ? 2.8 : 2);
    return `<circle class="rd-pt ${on ? 'on' : ''}" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${r}" fill="${ATT[x.attention][0]}" data-id="${e(x.id)}"><title>${e(x.name)} · ${e(x.municipio || '')}/${e(x.uf || '')} · ${e(x.attention)}</title></circle>`;
  }).join('');
  return `<svg viewBox="${VB.join(' ')}" class="rd-svg" role="img" aria-label="Mapa do Brasil: estados sombreados pela quantidade de barragens em atenção crítica ou alta; pontos por barragem">${ufs}${lbl}<g>${pts}</g></svg>`;
}

const legend = () => `<div class="rd-legend">${Object.entries(ATT).map(([k, [c, s]]) => `<span><i style="background:${c}"></i>${s} ${k}</span>`).join('')}<span class="muted">· sombreado = nº de críticas/altas por UF</span></div>`;

function listRow(x, sel) {
  return `<button class="rd-row ${sel === x.id ? 'on' : ''}" data-id="${e(x.id)}"><span class="rd-bar" style="background:${ATT[x.attention][0]}"></span>
    <span class="rd-main"><strong>${e(x.name)}</strong><small>${e(x.municipio || '—')}/${e(x.uf || '—')} · ${x.kind === 'orfa' ? 'Órfã · SNISB' : `${e(x.owner_kind)} · SIGBM`}</small>
    <small class="rd-sig">${x.signals.slice(0, 2).map((s) => e(s)).join(' · ') || 'Sem sinais'}</small>${x.hidden_risk ? '<small class="ml-badge">IA · perfil de emergência</small>' : ''}</span>${attTag(x.attention)}</button>`;
}

function modelBox(x) {
  const one = (m, name, posTxt, hiTxt) => {
    if (!m) return '';
    const hi = m.hidden_risk;
    return `<div class="ml-row ${hi ? 'hi' : ''}"><b>${e(name)}</b><span class="pbar risk"><i style="width:${Math.round(m.p * 100)}%"></i></span><small>${Math.round(m.p * 100)}% · percentil ${m.percentile} · ${m.positive ? e(posTxt) : hi ? e(hiTxt) : 'sem destaque'}</small>${m.why?.length ? `<small class="muted">Motivos: ${m.why.map((w) => e(w.feature)).join('; ')}</small>` : ''}</div>`;
  };
  if (!x.model && !x.model_dce) return '';
  const fb = x.model_feedback || [];
  return `<div class="ml-box ${(x.model?.hidden_risk || x.model_dce?.hidden_risk) ? 'hi' : ''}"><span class="ml-ic">${icon('target')}</span><div class="grow">
    <b>Predição por IA (modelos campeões, treinados no SIGBM)</b>
    ${one(x.model, 'Emergência não declarada', 'já declarada em emergência', 'perfil de emergência, declarada sem emergência')}
    ${one(x.model_dce, 'Falha na próxima DCE', 'DCE já não atestada/não enviada', 'atestada hoje, perfil de quem falha')}
    ${can('model.feedback') ? `<form class="ml-fb"><select aria-label="Modelo"><option value="emergencia">Emergência não declarada</option><option value="dce">Falha na próxima DCE</option></select><input placeholder="O que você conferiu? (evidência)" aria-label="Evidência"><button class="btn sm primary" data-l="1">Confirmo o problema</button><button class="btn sm" data-l="0">Não procede</button></form>` : ''}
    ${fb.length ? `<small class="muted">Conferências: ${fb.map((f) => `${f.label ? '✓' : '✕'} ${e(f.target)} por ${e(f.actor)}`).join(' · ')}</small>` : ''}
    <small><a href="#/ia" data-ia-risk>Ver validação, agente e ciclo de evolução</a> · pedido de conferência, não diagnóstico · seu retorno entra no próximo treino</small></div></div>`;
}

function signalsTab(x) {
  return `<div class="brief" id="brief"><button class="btn sm ai" id="brief-btn">${icon('spark')} Resumir esta barragem com IA</button><small class="muted">Escrito só com os dados desta ficha; um verificador recusa números sem fonte e afirmações proibidas.</small></div>${modelBox(x)}<div class="rd-cq ${x.consequence.high ? 'hi' : ''}"><b>${icon('alert')} Consequência declarada</b><span>${x.consequence.items.map(e).join(' · ')}</span></div>
  <ol class="rd-sigs">${x.signals.map((s) => `<li class="${s.code === 'CONTEXTO_PORTE' ? 'ctx' : ''}"><div class="row between"><strong>${e(s.label)}</strong><span class="w" title="Peso na regra ${e(x.rule_version)}">+${s.weight}</span></div>
    <div class="ev">${icon('database')} <span>Campo <code>${e(s.evidence.field)}</code> = <b>${e(s.evidence.value)}</b></span><span class="src">${s.evidence.source === 'ANA_SNISB' ? 'SNISB/ANA' : 'SIGBM/ANM'}</span></div>
    <div class="basis">${s.basis.map((b) => `<a class="law" href="${e(b.url)}" target="_blank" rel="noopener noreferrer" title="${e(b.text)}">${e(b.ref)}</a>`).join('')}</div></li>`).join('')}</ol>
  <p class="hint">Pontuação ${x.score} · regra <code>${e(x.rule_version)}</code>. Crítica/Alta exigem pelo menos um sinal central (inatividade sem projeto, DCE não enviada/não atestada, problema sem correção, sem equipe ou sem empreendedor). Sinal não é conclusão: confirme na fonte.</p>`;
}

function respTab(x) {
  const ST = { identificado: ['Identificado', '#46774E'], faltando: ['Faltando', '#C83037'], 'a verificar': ['A verificar', '#D4A12E'], condicional: ['Condicional', '#63768A'] };
  return `<div class="rd-chain">${x.responsibles.map((r, i) => `<div class="rd-resp"><span class="n">${i + 1}</span><div><div class="row between wrap"><strong>${e(r.role)}</strong><span class="tag" style="--c:${ST[r.status]?.[1]}">${e(ST[r.status]?.[0] || r.status)}</span></div>
    <p class="who">${e(r.who)}</p><p class="muted sm">${e(r.how)}</p><div class="basis">${r.basis.map((b) => `<a class="law" href="${e(b.url)}" target="_blank" rel="noopener noreferrer" title="${e(b.text)}">${e(b.ref)}</a>`).join('')}</div></div></div>`).join('')}</div>
  <p class="hint">Nomes de pessoas físicas não são exibidos nem buscados. A LexIA não entra em contato com ninguém: indica o caminho e prepara o texto para envio humano.</p>`;
}

function planTab(x) {
  const p = x.plan, ed = can('contingency.edit');
  const pct = p.progress.total ? Math.round((100 * p.progress.done) / p.progress.total) : 0;
  return `<div class="rd-via"><div><span class="eyebrow">Viabilidade</span><b>${e(p.viability)}</b><p class="muted sm">${icon('arrow')} Caminho mais rápido: ${e(p.fastest_path)}</p></div>
    <div class="rd-prog"><b>${p.progress.done}/${p.progress.total}</b><small>etapas</small><span class="pbar"><i style="width:${pct}%"></i></span></div></div>
  <ol class="rd-steps">${p.steps.map((s, i) => `<li class="st-${s.status} ${s.blocked ? 'blocked' : ''}" data-step="${s.id}"><span class="n">${s.status === 'feito' ? '✓' : i + 1}</span><div class="body">
    <div class="row between wrap"><strong>${e(s.title)}</strong><span class="row gap wrap"><span class="mini-t">Complexidade ${e(s.complexity)}</span><span class="mini-t">Custo ${e(s.relative_cost)}</span>${s.blocked ? '<span class="mini-t warn" title="Depende de etapas anteriores">Aguardando dependência</span>' : ''}</span></div>
    <p class="muted sm">${icon('user')} ${e(s.role)}${s.depends_on.length ? ` · depende de: ${s.depends_on.map((d) => e(p.steps.find((q) => q.id === d)?.title || d)).join('; ')}` : ''}</p>
    <div class="basis">${s.basis.map((b) => `<a class="law" href="${e(b.url)}" target="_blank" rel="noopener noreferrer" title="${e(b.text)}">${e(b.ref)}</a>`).join('')}</div>
    ${s.note ? `<p class="note-l">${icon('doc')} ${e(s.note)} <small>— ${e(s.by || '')}, ${fmtDateTime(s.at)}</small></p>` : ''}
    ${ed ? `<form class="rd-stepf"><select aria-label="Situação da etapa">${Object.entries(STEP_ST).map(([k, v]) => `<option value="${k}" ${k === s.status ? 'selected' : ''}>${v}</option>`).join('')}</select><input placeholder="Evidência ou observação (obrigatória para “Feito”)" aria-label="Observação" value=""><button class="btn sm">Salvar</button></form>` : ''}
  </div></li>`).join('')}</ol>
  <p class="hint">${e(p.disclaimer)} ${ed ? 'Cada mudança entra na trilha de auditoria.' : 'Entre com um papel operacional para registrar o andamento.'}</p>`;
}

function draftTab(x, preview) {
  const u = currentUser(), emp = u?.kind === 'empresa';
  const ST = { RASCUNHO: ['Rascunho', '#D4A12E'], APROVADO_PARA_ENVIO: ['Aprovado para envio', '#46774E'], DESCARTADO: ['Descartado', '#63768A'] };
  return `<div class="warn-note">${icon('shield')} Rascunho gerado a partir dos campos da fonte. <b>Nada é enviado automaticamente.</b> ${emp ? 'Quem gera não pode aprovar (quatro olhos).' : 'Você pode baixar o texto e protocolar no órgão fiscalizador (Lei 12.334/2010, art. 17-A, §2º).'}</div>
  <textarea class="rd-draft" id="draft-body" rows="16" aria-label="Texto da representação">${e(preview || 'Carregando…')}</textarea>
  <div class="row gap wrap mt8"><button class="btn" id="draft-copy">${icon('copy')} Copiar</button><button class="btn" id="draft-dl">${icon('doc')} Baixar .txt</button>
    ${emp && can('draft.create') ? `<button class="btn primary" id="draft-save">${icon('check')} Salvar rascunho para revisão</button>` : ''}</div>
  ${emp && x.drafts.length ? `<h4 class="mt16">Rascunhos desta barragem</h4><div class="rd-drafts">${x.drafts.map((d) => `<div class="rd-dr"><div class="row between wrap"><b>#${d.id} · ${fmtDateTime(d.created_at)}</b><span class="tag" style="--c:${ST[d.state][1]}">${ST[d.state][0]}</span></div>
    <small class="muted">Gerado por ${e(d.created_by)} · SHA-256 <code>${e(d.sha256.slice(0, 12))}…</code>${d.decided_by ? ` · decidido por ${e(d.decided_by)}: “${e(d.reason)}”` : ''}</small>
    ${d.state === 'RASCUNHO' && can('draft.decide') ? `<form class="rd-dec" data-draft="${d.id}"><input placeholder="Justificativa (obrigatória)" required aria-label="Justificativa"><button class="btn sm primary" data-d="APROVADO_PARA_ENVIO">Aprovar para envio</button><button class="btn sm" data-d="DESCARTADO">Descartar</button></form>` : ''}</div>`).join('')}</div>` : ''}`;
}

function anomTab(x) {
  return x.anomalies.length ? `<ul class="rd-anom">${x.anomalies.map((a) => `<li><strong>${e(a.label)}</strong><span>${e(a.detail)}</span><small>${e(a.method)}${a.basis ? ' · ' + e(a.basis) : ''}</small></li>`).join('')}</ul><p class="hint">Inconsistência é pedido de conferência na fonte, não irregularidade.</p>`
    : '<div class="empty"><p>Nenhuma inconsistência detectada nos campos desta barragem.</p></div>';
}

function ficha(x, preview) {
  const r = RS(), watched = (data.me?.watchlist || []).includes(x.id);
  const facts = x.kind === 'mineracao'
    ? [['Empreendedor', x.owner_label], ['Tipo de dono', `${x.owner.kind} · ${x.owner.dams_in_sigbm} barragem(ns) no SIGBM`], ['Situação', x.operational_status], ['CRI / DPA (oficial)', `${x.cri || '—'} / ${x.dpa || '—'}`], ['Nível de emergência', x.emergency_level], ['Contenção', x.containment], ['Unidade gestora ANM', x.managing_unit], ['Última inspeção (SNISB)', x.snisb?.last_inspection ? fmtDate(x.snisb.last_inspection) : 'sem registro']]
    : [['Empreendedor', 'Não identificado no cadastro'], ['Uso principal', x.use], ['Fase de vida', x.phase], ['DPA / risco (SNISB)', `${x.damage_potential || 'não classificado'} / ${x.risk_category || 'não classificado'}`], ['Fiscalizador', x.regulator], ['Regulada pela PNSB', x.pnsb || 'não informado'], ['Capacidade', x.capacity_hm3 ? `${x.capacity_hm3} hm³` : '—'], ['Última inspeção', x.last_inspection ? fmtDate(x.last_inspection) : 'sem registro']];
  const T = [['sinais', `Sinais (${x.signals.length})`, 'alert'], ['resp', 'Responsáveis', 'users'], ['plano', `Plano de contingência (${x.plan.progress.done}/${x.plan.progress.total})`, 'check'], ['repr', 'Representação', 'doc'], ['anom', `Inconsistências (${x.anomalies.length})`, 'filter']];
  const body = { sinais: signalsTab, resp: respTab, plano: planTab, repr: (y) => draftTab(y, preview), anom: anomTab }[r.ftab](x);
  return `<section class="card rd-ficha" id="ficha" tabindex="-1"><header class="rd-fh"><button class="btn ghost sm" id="ficha-close">${icon('arrow', 'flip')} Voltar à lista</button>
    <div class="rd-ft"><span class="eyebrow">${x.kind === 'orfa' ? 'Barragem órfã · SNISB/ANA' : 'Barragem de mineração · SIGBM/ANM'}</span><h3>${e(x.name)}</h3><p class="muted">${e(x.municipio || '—')}/${e(x.uf || '—')} · <code>${e(x.id)}</code> · <span class="origin off">DADO OFICIAL</span></p></div>
    <div class="rd-fa">${attTag(x.attention)}<a class="btn sm" href="#/denuncia?dam=${encodeURIComponent(x.id)}">${icon('doc')} Fazer denúncia</a>${can('watch') ? `<button class="btn sm ${watched ? 'primary' : ''}" id="watch">${icon('star')} ${watched ? 'Acompanhando' : 'Acompanhar'}</button>` : ''}</div></header>
    <div class="rd-top"><dl class="kv rd-kv">${facts.map(([k, v]) => `<dt>${e(k)}</dt><dd>${e(v || '—')}</dd>`).join('')}</dl>
    <div class="rd-sat">${satView(x.lat, x.lon, { height: 210, label: `${x.name} · coordenada oficial ${x.kind === 'orfa' ? 'SNISB' : 'SIGBM'}` })}</div></div>
    <div class="tabs" role="tablist">${T.map(([id, l, ic]) => `<button role="tab" class="tab ${r.ftab === id ? 'on' : ''}" aria-selected="${r.ftab === id}" data-ftab="${id}">${icon(ic)}${e(l)}</button>`).join('')}</div>
    <div class="rd-fb">${body}</div></section>`;
}

function panorama(p) {
  const bars = (rows, max, color) => rows.map(([k, n]) => `<div class="hb"><span>${e(k)}</span><i style="--w:${(100 * n) / max}%;--c:${color}"></i><b>${n}</b></div>`).join('');
  const SIGL = { CONTEXTO_PORTE: 'Contexto: dono pequeno', AUTUADA: 'Autuada (SNISB)', INSPECAO_ANTIGA: 'Inspeção > 3 anos', INSTRUMENTACAO: 'Instrumentação sem adequação', PAE_AUSENTE: 'PAE exigido ausente', INATIVA_SEM_PROJETO: 'Inativa sem projeto', SEM_CORRECAO_SLOPE_DETERIORATION: 'Taludes sem correção', SEM_CORRECAO_SPILLWAY: 'Extravasor sem correção', SEM_INSPECAO: 'Sem inspeção registrada', DCE_NAO_ATESTADA: 'DCE não atestada', DCE_NAO_ENVIADA: 'DCE não enviada', SEM_CORRECAO_PERCOLATION: 'Percolação sem correção', SEM_CORRECAO_DEFORMATION: 'Deformação sem correção', NAO_VOLTA_SEM_OBRA: 'Não volta, sem obra', SEM_EQUIPE: 'Sem equipe técnica' };
  const ts = p.mining.top_signals.map(([k, n]) => [SIGL[k] || k, n]);
  return `<div class="grid-6-6">
    ${card('Quem tem barragem de mineração no Brasil', `<div class="pan-big"><div><b>92%</b><span>dos 301 empreendedores são pequenos (até 5 barragens, cooperativa ou pessoa física)</span></div><div><b>73%</b><span>das 77 barragens com emergência declarada são desses pequenos</span></div><div><b>11% × 5%</b><span>taxa de emergência entre pequenos e grandes</span></div><div><b>102</b><span>barragens no CPF de 67 pessoas (99 em MT)</span></div></div>
      <p class="hint">Análise da equipe sobre dados públicos do SIGBM/ANM (versão de 06/11/2026). Mostra concentração, não culpa. Método: <code>scripts/analise_porte_sigbm.py</code>.</p>`, { icon: 'users' })}
    ${card('Sinais mais frequentes · mineração', `<div class="hbars">${bars(ts, Math.max(...ts.map((t) => t[1])), '#F97316')}</div><p class="hint">${p.mining.flagged} barragens em atenção crítica/alta; ${p.mining.flagged_small_owner} delas de donos pequenos.</p>`, { icon: 'chart' })}
  </div>
  <div class="grid-6-6">
    ${card('Barragens órfãs (sem empreendedor) · SNISB', `<div class="pan-big three"><div><b>${p.orphans.total.toLocaleString('pt-BR')}</b><span>sem empreendedor identificado no cadastro nacional</span></div><div><b>${p.orphans.dpa_alto}</b><span>com dano potencial alto</span></div><div><b>${p.orphans.without_inspection.toLocaleString('pt-BR')}</b><span>sem data de inspeção registrada</span></div></div>
      <h4>Críticas + altas por UF</h4><div class="hbars">${bars(p.orphans.top_uf, Math.max(1, ...p.orphans.top_uf.map((t) => t[1])), '#C83037')}</div>
      <p class="hint">Nenhuma órfã é fiscalizada pela ANM (${p.orphans.mining_orphans}): na mineração o risco é o abandono de fato, com dono ainda registrado. Órfãs são sobretudo açudes de irrigação e dessedentação animal.</p>`, { icon: 'dam' })}
    ${card('Fontes desta análise', `<dl class="kv"><dt>SIGBM/ANM</dt><dd><code>${e(p.sources.sigbm?.snapshot_id || '—')}</code> · ${fmtDateTime(p.sources.sigbm?.fetched_at)}<br><a href="https://dadosabertos.anm.gov.br/SIGBM/" target="_blank" rel="noopener noreferrer">dadosabertos.anm.gov.br/SIGBM ↗</a></dd>
      <dt>SNISB/ANA</dt><dd><code>${e(p.sources.snisb?.snapshot_id || '—')}</code> · ${fmtDateTime(p.sources.snisb?.fetched_at)}<br>${p.sources.snisb ? `${p.sources.snisb.orphans.accepted} órfãs · ${p.sources.snisb.mining.indexed} complementos de mineração` : ''}<br><a href="https://www.snisb.gov.br/" target="_blank" rel="noopener noreferrer">snisb.gov.br ↗</a></dd>
      <dt>Base legal</dt><dd><a href="${e(p.law_url)}" target="_blank" rel="noopener noreferrer">Lei 12.334/2010, texto compilado (Planalto) ↗</a></dd><dt>Regra</dt><dd><code>${e(p.rule_version)}</code></dd></dl>
      <p class="hint">${e(p.reading)}</p><div class="row gap wrap"><a class="btn sm" href="/api/export/radar.csv?dataset=mineracao" download>${icon('doc')} CSV mineração</a><a class="btn sm" href="/api/export/radar.csv?dataset=orfas" download>${icon('doc')} CSV órfãs</a><a class="btn sm" href="/api/export/anomalias.csv" download>${icon('doc')} CSV inconsistências</a></div>`, { icon: 'database' })}
  </div>`;
}

function how() {
  const steps = [['database', 'Coleta oficial', 'SIGBM/ANM (CSV diário) e SNISB/ANA (serviço público). Snapshot imutável com SHA-256; nomes de pessoas físicas não são exibidos.'],
    ['alert', 'Sinais explicáveis', 'Regras versionadas leem campos declarados: inativa sem projeto, DCE não enviada, problema sem correção, sem PAE, sem empreendedor…'],
    ['target', 'Nível de atenção', 'Sinais + consequência declarada (DPA, população a jusante, emergência). Não substitui CRI/DPA nem a decisão do fiscalizador.'],
    ['users', 'Responsáveis', 'Cadeia da Lei 12.334/2010: empreendedor, sucessor, proprietário do terreno (subsidiário), fiscalizador, Defesa Civil e MP.'],
    ['check', 'Plano de contingência', 'Etapas com base legal, dependências, complexidade e custo relativo. Progresso registrado com evidência e auditoria.'],
    ['doc', 'Representação', 'Rascunho com os campos da fonte (art. 17-A, §2º). Humano revisa, outro humano aprova, e só então alguém envia.']];
  return `<div class="how-grid">${steps.map(([ic, t, d], i) => `<div class="how"><span class="how-n">${i + 1}</span>${icon(ic)}<b>${t}</b><p>${d}</p></div>`).join('')}</div>
  <div class="warn-note mt16">${icon('shield')} A LexIA não declara uma barragem “abandonada”. Ela mostra sinais nos dados públicos, quem responde pela lei e o próximo passo. A conclusão é do órgão fiscalizador.</div>`;
}

let cache = { key: null, list: null, pan: null };

export const radar = {
  citizen: true, both: true,
  async render() {
    const r = RS();
    const hashId = new URLSearchParams(location.hash.split('?')[1] || '').get('id');
    if (hashId) { r.sel = hashId; r.dataset = hashId.startsWith('SNISB') ? 'orfas' : 'mineracao'; history.replaceState(null, '', '#/radar'); }
    const key = qsOf(r);
    if (!cache.pan) cache.pan = await api('/api/radar/panorama');
    if (cache.key !== key) { cache.list = await api('/api/radar/list?' + key); cache.key = key; }
    const p = cache.pan, L = cache.list, m = p.mining.levels, o = p.orphans.levels;
    let x = null, preview = null;
    if (r.sel) { try { x = await api('/api/radar/item?id=' + encodeURIComponent(r.sel)); if (r.ftab === 'repr') preview = (await api('/api/radar/draft-preview?id=' + encodeURIComponent(r.sel))).body; } catch { r.sel = null; } }
    const per = 40, items = L.items, pages = Math.max(1, Math.ceil(items.length / per)); r.page = Math.min(r.page, pages - 1);
    const lv = L.levels || {};
    const head = `<header class="page-head"><div><span class="eyebrow">Barragens sem manutenção</span><h2>Radar de abandono</h2><p class="muted">Barragens com sinais de abandono ou sem dono identificado, quem responde pela lei e um plano para ninguém ficar sem manutenção. Dados oficiais da ANM e da ANA.</p></div>
      <div class="seg" role="group" aria-label="Página">${[['radar', 'Radar'], ['panorama', 'Panorama do setor'], ['como', 'Como funciona']].map(([k, l]) => `<button class="${r.ptab === k ? 'on' : ''}" data-ptab="${k}">${l}</button>`).join('')}</div></header>`;
    if (r.ptab === 'panorama') return head + panorama(p);
    if (r.ptab === 'como') return head + card('Do dado público ao plano de contingência', how(), { icon: 'spark' });
    return `${head}
    <div class="kpis4">${kpi('#C83037', m['Crítica'] || 0, 'Mineração em atenção crítica', 'alert', { dataset: 'mineracao', attention: ['Crítica'] })}
      ${kpi('#F97316', p.mining.inactive, 'Mineração inativa (SIGBM)', 'dam', { dataset: 'mineracao', operational_status: ['Inativa'] })}
      ${kpi('#68487A', (o['Crítica'] || 0) + (o['Alta'] || 0), 'Órfãs em atenção crítica ou alta', 'pin', { dataset: 'orfas', attention: ['Crítica', 'Alta'] })}
      ${kpi('#1570EF', p.started_plans.length, 'Planos de contingência iniciados', 'check', { dataset: 'mineracao', started: true })}</div>
    <form class="ai-bar mt16" id="ai-bar" role="search"><span class="ai-badge">${icon('spark')} IA</span><input id="ai-q" value="${e(r.q)}" placeholder="Filtre em português: “inativas sem projeto em MG”, “órfãs críticas no RN”, “pessoa física com emergência”…" aria-label="Filtrar em português"><button class="btn primary">Filtrar</button></form>
    <div class="ai-chips">${r.chips.length ? `<span class="muted sm">${e(r.engine || '')}:</span>${r.chips.map((c) => `<span class="chip-f">${e(c)}</span>`).join('')}<button class="link" id="clear-f">Limpar filtros</button>` : '<span class="muted sm">Sem filtro de texto. Use a caixa acima ou os botões.</span>'}</div>
    <div class="rd-tools"><div class="seg" role="group" aria-label="Base">${[['mineracao', 'Mineração · SIGBM'], ['orfas', 'Órfãs · SNISB'], ['ambos', 'Ambas']].map(([k, l]) => `<button class="${r.dataset === k ? 'on' : ''}" data-ds="${k}">${l}</button>`).join('')}</div>
      <div class="rd-att">${Object.keys(ATT).map((a) => `<button class="chip-btn ${(r.filters.attention || []).includes(a) ? 'on' : ''}" data-att="${a}" style="--c:${ATT[a][0]}"><i></i>${a} <b>${lv[a] || 0}</b></button>`).join('')}</div>
      <button class="chip-btn ml ${r.filters.hidden_risk ? 'on' : ''}" id="ml-toggle" title="Barragens com perfil técnico parecido com o das que estão em emergência (modelo treinado no SIGBM)">${icon('target')} Risco oculto (IA)</button>
      <a class="btn sm" href="/api/export/radar.csv?${qsOf(r)}" download>${icon('doc')} Exportar CSV</a></div>
    ${x ? ficha(x, preview) : ''}
    <div class="rd-grid ${x ? 'mt16' : ''}"><section class="card flush rd-mapc"><div class="rd-maph"><b>${L.total.toLocaleString('pt-BR')} barragem(ns)</b>${legend()}</div>${mapSvg(items, r.sel)}</section>
      <section class="card flush rd-listc"><div class="rd-listh"><b>Ordenado por atenção</b><small class="muted">clique para abrir a ficha</small></div><div class="rd-list">${items.slice(r.page * per, r.page * per + per).map((y) => listRow(y, r.sel)).join('') || '<div class="empty"><p>Nenhuma barragem com esses filtros.</p></div>'}</div>
      ${pages > 1 ? `<div class="pager"><button class="btn sm" data-pg="-1" ${r.page ? '' : 'disabled'}>‹</button><span>${r.page + 1} / ${pages}</span><button class="btn sm" data-pg="1" ${r.page < pages - 1 ? '' : 'disabled'}>›</button></div>` : ''}</section></div>
    <p class="hint">Fontes: SIGBM/ANM <code>${e(p.sources.sigbm?.snapshot_id || '—')}</code> e SNISB/ANA <code>${e(p.sources.snisb?.snapshot_id || '—')}</code>. Sinal de atenção não é conclusão nem acusação.</p>`;
  },
  mount(root, ctx) {
    const r = RS();
    const refresh = () => ctx.rerender();
    root.querySelectorAll('[data-ptab]').forEach((b) => b.addEventListener('click', () => { r.ptab = b.dataset.ptab; refresh(); }));
    root.querySelectorAll('[data-ds]').forEach((b) => b.addEventListener('click', () => { r.dataset = b.dataset.ds; r.page = 0; refresh(); }));
    root.querySelectorAll('[data-att]').forEach((b) => b.addEventListener('click', () => { const a = b.dataset.att, cur = new Set(r.filters.attention || []); cur.has(a) ? cur.delete(a) : cur.add(a); r.filters = { ...r.filters, attention: [...cur] }; r.page = 0; refresh(); }));
    root.querySelectorAll('[data-kfilter]').forEach((b) => b.addEventListener('click', () => { const f = JSON.parse(b.dataset.kfilter); if (f.started) { const id = cache.pan.started_plans[0]?.dam_id; if (id) { r.sel = id; r.ftab = 'plano'; refresh(); } else toast('Nenhum plano iniciado ainda. Abra uma barragem e registre a primeira etapa.'); return; } r.dataset = f.dataset; delete f.dataset; r.filters = f; r.chips = []; r.q = ''; r.page = 0; refresh(); }));
    root.querySelector('#ml-toggle')?.addEventListener('click', () => { const on = !r.filters.hidden_risk; r.filters = { ...r.filters, hidden_risk: on || undefined }; if (on) r.dataset = 'mineracao'; r.chips = on ? [...r.chips.filter((c) => !c.startsWith('Risco')), 'Risco oculto (modelo): sim'] : r.chips.filter((c) => !c.startsWith('Risco')); r.page = 0; refresh(); });
    root.querySelector('[data-ia-risk]')?.addEventListener('click', () => { state.ia = { ...(state.ia || {}), tab: 'risco' }; });
    root.querySelectorAll('.ml-fb [data-l]').forEach((b) => b.addEventListener('click', async (ev) => {
      ev.preventDefault(); const f = b.closest('form'), reason = f.querySelector('input').value.trim();
      if (!reason) return toast('Descreva o que foi conferido.', 'err');
      try { await api('/api/ml/feedback', { target: f.querySelector('select').value, dam_id: r.sel, label: +b.dataset.l, reason }); toast('Obrigado! Seu retorno entra no próximo treino do modelo.'); refresh(); } catch (err) { toast(err.message, 'err'); }
    }));
    root.querySelector('#clear-f')?.addEventListener('click', () => { r.filters = {}; r.chips = []; r.q = ''; r.page = 0; refresh(); });
    root.querySelectorAll('[data-pg]').forEach((b) => b.addEventListener('click', () => { r.page += +b.dataset.pg; refresh(); }));
    root.querySelector('#ai-bar')?.addEventListener('submit', async (ev) => {
      ev.preventDefault(); const q = root.querySelector('#ai-q').value.trim(); r.q = q;
      if (!q) { r.filters = {}; r.chips = []; return refresh(); }
      const btn = root.querySelector('#ai-bar button'); btn.disabled = true; btn.textContent = 'Interpretando com IA…';
      const it = await api('/api/ai/interpret?q=' + encodeURIComponent(q)).finally(() => { btn.disabled = false; btn.textContent = 'Filtrar'; });
      if (!it.chips.length) { toast('Não reconheci filtros nesse pedido. Tente “inativas em MG” ou “órfãs críticas”.', 'err'); return; }
      const f = it.filters; r.dataset = f.dataset; r.filters = f; r.chips = it.chips_text; r.engine = it.engine === 'ia' ? 'IA propôs, verificador conferiu' : 'Interpretado por regras'; r.page = 0; refresh();
    });
    const open = (id) => { r.sel = id; r.ftab = r.ftab || 'sinais'; refresh().then?.(() => document.getElementById('ficha')?.scrollIntoView({ behavior: 'smooth', block: 'start' })); };
    root.querySelectorAll('.rd-row, .rd-pt').forEach((b) => b.addEventListener('click', () => open(b.dataset.id)));
    root.querySelectorAll('.rd-uf').forEach((u) => u.addEventListener('click', () => {
      const uf = u.dataset.uf, cur = r.filters.uf || [];
      r.filters = { ...r.filters, uf: cur.length === 1 && cur[0] === uf ? [] : [uf] }; r.chips = r.filters.uf.length ? [`UF: ${uf}`] : []; r.engine = 'Clique no mapa'; r.page = 0; refresh();
      toast(r.filters.uf.length ? `Mostrando só ${UF_NAME[uf]}. Clique de novo no estado para voltar.` : 'Filtro de estado removido.');
    }));
    root.querySelector('#brief-btn')?.addEventListener('click', async (ev) => {
      ev.target.disabled = true; ev.target.textContent = 'Resumindo…';
      try {
        const b = await api('/api/radar/brief?id=' + encodeURIComponent(r.sel));
        root.querySelector('#brief').innerHTML = `<div class="brief-box"><div class="row between wrap"><b>${icon('spark')} Resumo</b><span class="tag" style="--c:${b.engine === 'ia' ? '#68487A' : '#63768A'}">${e(b.engine_label)}</span></div>
          <p><b>Em linguagem simples:</b> ${e(b.simple)}</p><p><b>Técnico:</b> ${e(b.technical)}</p>${b.rejected.length ? `<p class="warn-note">Verificador recusou a versão da IA: ${e(b.rejected.join('; '))}</p>` : ''}</div>`;
      } catch (err) { toast(err.message, 'err'); ev.target.disabled = false; }
    });
    root.querySelector('#ficha-close')?.addEventListener('click', () => { r.sel = null; refresh(); });
    root.querySelectorAll('[data-ftab]').forEach((b) => b.addEventListener('click', () => { r.ftab = b.dataset.ftab; refresh(); }));
    root.querySelector('#watch')?.addEventListener('click', async () => {
      if (!currentUser()?.id) return toast('Entre com uma conta para acompanhar.', 'err');
      const on = (data.me?.watchlist || []).includes(r.sel);
      try { const res = await api('/api/watchlist', { asset_id: r.sel, action: on ? 'remove' : 'add' }); data.me.watchlist = res.items; toast(on ? 'Removida da carteira.' : 'Adicionada à carteira: você será avisado de mudanças.'); refresh(); } catch (err) { toast(err.message, 'err'); }
    });
    root.querySelectorAll('.rd-stepf').forEach((f) => f.addEventListener('submit', async (ev) => {
      ev.preventDefault(); const li = f.closest('[data-step]');
      try { await api('/api/radar/plan-step', { dam_id: r.sel, step_id: li.dataset.step, status: f.querySelector('select').value, note: f.querySelector('input').value }); cache.pan = null; toast('Etapa registrada na trilha de auditoria.'); refresh(); } catch (err) { toast(err.message, 'err'); }
    }));
    const body = () => root.querySelector('#draft-body')?.value || '';
    root.querySelector('#draft-copy')?.addEventListener('click', async () => { await navigator.clipboard?.writeText(body()); toast('Texto copiado.'); });
    root.querySelector('#draft-dl')?.addEventListener('click', () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([body()], { type: 'text/plain;charset=utf-8' })); a.download = `representacao_${r.sel}.txt`; a.click(); URL.revokeObjectURL(a.href); });
    root.querySelector('#draft-save')?.addEventListener('click', async () => { try { await api('/api/radar/draft', { dam_id: r.sel, body: body() }); toast('Rascunho salvo. Outra pessoa (jurídico/compliance) precisa aprovar.'); refresh(); } catch (err) { toast(err.message, 'err'); } });
    root.querySelectorAll('.rd-dec').forEach((f) => f.querySelectorAll('[data-d]').forEach((b) => b.addEventListener('click', async (ev) => {
      ev.preventDefault(); const reason = f.querySelector('input').value.trim(); if (!reason) return toast('Escreva a justificativa.', 'err');
      try { await api('/api/radar/draft/decide', { id: +f.dataset.draft, decision: b.dataset.d, reason }); toast('Decisão registrada.'); refresh(); } catch (err) { toast(err.message, 'err'); }
    })));
  },
};
