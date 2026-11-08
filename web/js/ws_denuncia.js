// Denúncia do cidadão — passo a passo simples: 1) sobre o quê  2) onde (mapa numerado perto de você)  3) o que aconteceu  4) denúncia organizada → revisar e enviar.
// Regras: a localização só serve para a busca (não é gravada); a pessoa confirma antes de qualquer envio; a análise (normas) só aparece depois de gerar.
import { state, api, e, fmtDateTime, toast, icon, currentUser } from './core.js';
import { satView } from './geoview.js';

const CATS = [
  ['barragem', 'Barragem', '🌊', 'Trinca, vazamento, água saindo, lama, sirene'],
  ['energia', 'Energia elétrica', '⚡', 'Fio solto, poste, subestação, usina'],
  ['saneamento', 'Água e esgoto', '💧', 'Água com cor ou cheiro, esgoto a céu aberto'],
  ['mineracao', 'Mina ou mineração', '⛏️', 'Poeira, explosão, caminhões, área abandonada'],
  ['trabalho', 'Segurança do trabalho', '🦺', 'Trabalhador sem proteção, acidente, altura'],
  ['radiacao', 'Radiação', '☢️', 'Símbolo de radiação, tambor, fonte abandonada'],
  ['outro', 'Outro assunto', '📝', 'Descreva com suas palavras'],
];
const EXEMPLO = { lat: -20.253, lon: -43.803, nome: 'Itabirito/MG (local de exemplo)' };
const QUANDO = [['', 'Quando foi?'], ['hoje', 'Hoje'], ['ontem', 'Ontem'], ['anteontem', 'Anteontem'], ['semana passada', 'Semana passada'], ['data', 'Escolher a data'], ['nao lembro', 'Não lembro']];
let ANON = false;
const DS = () => (ANON ? (state.denA = state.denA || { anon: true, cat: '', near: null, me: null, sel: null, relato: '', quando: '', data: '', ev: [], current: null, an: null, destino: null, editando: true }) : (state.den = state.den || { cat: '', near: null, me: null, sel: null, relato: '', quando: '', data: '', ev: [], current: null, an: null, destino: null, editando: true }));
const catInfo = (k) => CATS.find((c) => c[0] === k) || CATS[CATS.length - 1];
const kmTxt = (k) => (k < 1 ? Math.round(k * 1000) + ' m' : k.toLocaleString('pt-BR') + ' km');

// ------------------------------------------------------------ mapa de ruas com marcadores numerados (Esri World Street Map)
const TILE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile';
const W = 760, H = 380;
const merc = (lat, lon, z) => { const n = 256 * 2 ** z, r = (lat * Math.PI) / 180; return [((lon + 180) / 360) * n, ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n]; };
export function streetMap(items, me, selId) {
  const pts = items.filter((x) => !x.longe);
  const all = [...pts.map((x) => [x.lat, x.lon]), ...(me ? [[me.lat, me.lon]] : [])];
  let z = 15;
  for (; z > 4; z--) {
    const xy = all.map(([la, lo]) => merc(la, lo, z));
    const dx = Math.max(...xy.map((p) => p[0])) - Math.min(...xy.map((p) => p[0])), dy = Math.max(...xy.map((p) => p[1])) - Math.min(...xy.map((p) => p[1]));
    if (dx < W * 0.82 && dy < H * 0.78) break;
  }
  const xy = all.map(([la, lo]) => merc(la, lo, z));
  const cx = (Math.max(...xy.map((p) => p[0])) + Math.min(...xy.map((p) => p[0]))) / 2, cy = (Math.max(...xy.map((p) => p[1])) + Math.min(...xy.map((p) => p[1]))) / 2;
  const x0 = cx - W / 2, y0 = cy - H / 2;
  const pct = (x, y) => `left:${(((x - x0) / W) * 100).toFixed(3)}%;top:${(((y - y0) / H) * 100).toFixed(3)}%`;
  let tiles = '';
  for (let ty = Math.floor(y0 / 256); ty <= Math.floor((y0 + H) / 256); ty++) for (let tx = Math.floor(x0 / 256); tx <= Math.floor((x0 + W) / 256); tx++) {
    tiles += `<img alt="" loading="lazy" src="${TILE}/${z}/${ty}/${tx}" style="${pct(tx * 256, ty * 256)};width:${((256 / W) * 100).toFixed(3)}%">`;
  }
  const [mx, my] = me ? merc(me.lat, me.lon, z) : [0, 0];
  const marks = pts.map((x) => { const [px, py] = merc(x.lat, x.lon, z); return `<button type="button" class="dm-pin ${x.real ? 'real' : 'demo'} ${x.id === selId ? 'on' : ''}" data-pick="${e(x.id)}" style="${pct(px, py)}" aria-label="${x.n}: ${e(x.nome)}" title="${e(x.nome)} · ${e(x.numero)}">${x.n}</button>`; }).join('');
  return `<div class="dm-map" role="group" aria-label="Mapa: você e o que está perto">${tiles}${me ? `<span class="dm-me" style="${pct(mx, my)}" title="Você"><i></i><b>Você</b></span>` : ''}${marks}
    <small class="dm-attr">Mapa: Esri${me ? ' · ' + e(me.nome || 'sua localização') : ''}</small></div>`;
}

const detalhe = (x) => !x ? '' : `<article class="dm-det">
  <div class="dm-img">${x.real ? satView(x.lat, x.lon, { zoom: 16, height: 210, label: `Nº ${x.n} · ${x.numero} (coordenada oficial)` })
    : `<figure class="dm-ilu"><img src="${e(x.imagem || '/img/brand/landscape-identity.jpg')}" alt=""><figcaption>Imagem ilustrativa do setor · ativo fictício de demonstração</figcaption></figure>`}</div>
  <div class="dm-info"><span class="dm-num">${x.n}</span><h4>${e(x.nome)}</h4>
    <dl class="kv"><dt>Número oficial</dt><dd><code>${e(x.numero)}</code></dd><dt>Tipo</dt><dd>${e(x.tipo)}</dd><dt>Responsável</dt><dd>${e(x.empresa)}</dd>
      <dt>Local</dt><dd>${e(x.local || '—')} · ${kmTxt(x.km)} de você</dd><dt>Fonte</dt><dd>${e(x.fonte)}</dd></dl>
    <span class="lx-chip ${x.recebe_direto ? 'ok' : 'oficial'}">${x.recebe_direto ? 'A denúncia vai direto para a empresa na LexIA' : 'A denúncia vai para o órgão oficial'}</span></div></article>`;

function passo1(st) {
  return `<section class="card dn-step"><header class="card-h"><h3><span class="dn-sn">1</span> Sobre o que é a denúncia?</h3></header>
    <div class="dn-cats">${CATS.map(([k, l, ico, d]) => `<button type="button" class="dn-cat ${st.cat === k ? 'on' : ''}" data-cat="${k}"><span class="dn-ico" aria-hidden="true">${ico}</span><b>${l}</b><small>${d}</small></button>`).join('')}</div></section>`;
}

function passo2(st) {
  if (!st.cat) return '';
  const c = catInfo(st.cat), N = st.near;
  return `<section class="card dn-step" id="dn-passo2"><header class="card-h"><h3><span class="dn-sn">2</span> Onde? <small class="muted">${e(c[1])}</small></h3></header>
    <div class="row gap wrap"><button class="btn primary" id="dn-geo" type="button">${icon('pin')} Usar minha localização</button>
      <button class="btn" id="dn-ex" type="button">Usar local de exemplo (Itabirito/MG)</button>
      <button class="btn ghost" id="dn-skip" type="button">Não sei / vou descrever o local</button></div>
    <p class="hint">Sua localização serve só para esta busca: não é gravada nem enviada à empresa.</p>
    ${!N ? '' : !N.items.length ? `<p class="warn-note">${e(N.vazio || 'Nada encontrado perto.')}</p>` : `
    <div class="dn-mapwrap">${streetMap(N.items, st.me, st.sel?.id)}
      <ol class="dn-list">${N.items.map((x) => `<li><button type="button" class="dn-li ${st.sel?.id === x.id ? 'on' : ''}" data-pick="${e(x.id)}"><span class="dm-n ${x.real ? 'real' : 'demo'}">${x.n}</span>
        <span><b>${e(x.nome)}</b><small>${e(x.numero)} · ${e(x.tipo)} · ${kmTxt(x.km)}${x.longe ? ' (fora do mapa)' : ''}</small></span></button></li>`).join('')}</ol></div>
    <p class="hint">Toque no número para ver a estrutura. Números em azul: dado oficial público. Em dourado: empresa fictícia da demonstração que usa a LexIA.</p>
    ${detalhe(st.sel)}`}
    ${st.sel === false ? '<p class="sm"><b>Sem estrutura escolhida:</b> descreva o local no relato (rua, bairro, ponto de referência).</p>' : ''}</section>`;
}

function passo3(st) {
  if (!st.cat || st.sel === null) return '';
  return `<section class="card dn-step"><header class="card-h"><h3><span class="dn-sn">3</span> O que aconteceu?</h3></header>
    <label class="field"><span>Conte com suas palavras: o que viu, onde exatamente, desde quando. A LexIA organiza para você.</span>
      <textarea id="dn-rel" rows="5" placeholder="Ex.: Ontem à noite vi água barrenta saindo na base da barragem, perto da ponte. Desde março aparece de novo quando chove.">${e(st.relato)}</textarea></label>
    <div class="row gap wrap mt8"><label class="field" style="flex:0 0 200px"><span>Quando foi?</span><select id="dn-q">${QUANDO.map(([v, l]) => `<option value="${v}" ${st.quando === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
      ${st.quando === 'data' ? `<label class="field" style="flex:0 0 180px"><span>Data</span><input type="date" id="dn-d" value="${e(st.data)}"></label>` : ''}
      ${ANON ? '<p class="hint" style="flex:1;min-width:220px">Na denúncia anônima não há anexo: nada que identifique você é enviado.</p>' : ''}<label class="field" style="flex:1;min-width:220px;${ANON ? 'display:none' : ''}"><span>Fotos ou documentos (opcional)</span><input type="file" id="dn-files" multiple accept=".pdf,.png,.jpg,.jpeg,.txt"></label></div>
    ${st.ev.length ? `<ul class="history">${st.ev.map((x) => `<li><strong>${e(x.name)}</strong><small>guardado com SHA-256 ${e(x.sha256.slice(0, 12))}…</small></li>`).join('')}</ul>` : ''}
    <button class="btn primary lg mt12" id="dn-go">${icon('spark')} Gerar denúncia</button></section>`;
}


// Dossiê (regra dossie-v1): relato formal, normas possivelmente descumpridas, implicações e caminhos. Usado pelo cidadão e pela empresa.
export const relatoFormal = (D) => !D?.relato_formal ? '' : `<div class="dz-formal"><div class="row between wrap"><h4>Relato formal</h4><span class="lx-chip ${String(D.motor_redacao).startsWith('ia') ? 'ia' : 'ok'}">${String(D.motor_redacao).startsWith('ia') ? 'IA redigiu · verificador conferiu' : 'Redigido por regra'}</span></div><p>${e(D.relato_formal)}</p></div>`;
export const normasDz = (D) => !D?.normas_descumpridas?.length ? '<p class="muted sm">Nenhuma norma específica do catálogo para este relato.</p>'
  : `<ul class="dz-normas">${D.normas_descumpridas.map((n) => `<li><a class="law" href="${e(n.url || '#')}" target="_blank" rel="noopener noreferrer">${e(n.ref)}</a><small>${e(n.exige)}</small>${n.trecho ? `<q>${e(n.trecho)}</q>` : ''}</li>`).join('')}</ul>`;
export const implicDz = (D) => !D?.implicacoes?.length ? '' : `<div class="dz-impl">${D.implicacoes.map((i) => `<article><b>${e(i.orgao)}</b><span class="dz-faixa">${e(i.faixa)}</span><small>${e(i.sancao)}</small>
  <small class="muted">Base: <a href="${e(i.url)}" target="_blank" rel="noopener noreferrer">${e(i.base)}</a> · custos além da multa: ${e(i.custos)}</small></article>`).join('')}</div>`;
export const caminhosDz = (D, feitos = null, pode = false) => !D?.caminhos?.length ? '' : `<ol class="dz-passos">${D.caminhos.map((p, i) => { const f = feitos && feitos[String(i)];
  return `<li class="${f ? 'feito' : ''}">${feitos ? `<label><input type="checkbox" data-passo="${i}" ${f ? 'checked' : ''} ${pode ? '' : 'disabled'}>` : '<span>'}<b>${e(p.passo)}</b>${feitos ? '</label>' : '</span>'}
    <small><span class="lx-chip oficial">${e(p.papel)}</span> <span class="lx-chip ${p.prazo === 'imediato' ? 'crit' : 'mod'}">${e(p.prazo)}</span> evidência: ${e(p.evidencia)}${f ? ` · <b>feito</b> por ${e(f.por)}` : ''}</small></li>`; }).join('')}</ol>`;

const LINHA = (k, v) => (v ? `<dt>${k}</dt><dd>${v}</dd>` : '');
function passo4(st, cur) {
  if (!cur || !st.an) return '';
  const an = st.an, R = an.resumo || {}, q = R.quando, enviado = cur.state !== 'RASCUNHO';
  return `<section class="card dn-step dn-result"><header class="card-h"><h3><span class="dn-sn">4</span> Sua denúncia organizada</h3><span class="lx-chip ${an.engine === 'ia' ? 'ia' : 'ok'}">${an.engine === 'ia' ? 'IA organizou · normas conferidas' : 'Organizada por regras'}</span></header>
    ${an.aviso_risco ? `<p class="warn-note">${e(an.aviso_risco)}</p>` : ''}
    ${relatoFormal(an.dossie)}
    <div class="grid-6-6 mt12"><div><dl class="kv dn-kv">
      ${LINHA('Quando', q ? `${e(q.texto)} <small class="muted">(você escreveu “${e(q.trecho)}”)</small>` : '<span class="lx-chip alta">não informado</span>')}
      ${LINHA('Desde quando', R.desde && e(R.desde.texto))}${LINHA('Período', R.periodo && e(R.periodo))}
      ${LINHA('Onde', e(R.onde || 'conforme o relato'))}${LINHA('Pode afetar', R.afetados?.length && e(R.afetados.join(', ')))}
      ${LINHA('Repetição', R.recorrente ? 'a situação se repete ou continua' : '')}</dl>
      <details class="sm"><summary>Suas palavras (fatos)</summary><ol class="sm">${(R.fatos || []).map((f) => `<li>${e(f)}</li>`).join('')}</ol></details>
      <h4>O que se pede</h4><ul class="ticks">${(R.pedidos || []).map((p) => `<li>${e(p)}</li>`).join('')}</ul>
      ${R.faltando?.length ? `<p class="warn-note">Para ficar mais forte, falta: <b>${e(R.faltando.join('; '))}</b>.${q?.pergunta ? ' ' + e(q.pergunta) : ''} <button class="btn sm" id="dn-edit" type="button">Corrigir</button></p>` : ''}</div>
    <div><h4>Para onde vai</h4>${st.vaiEmpresa ? `<p class="cp-act">Vai direto para <b>${e(st.empresa)}</b> na LexIA (compliance e jurídico recebem na hora). Envie também ao órgão oficial.</p>` : `<p>${e(an.destinatario)}</p><p class="hint">Esta empresa não recebe denúncias pela LexIA: depois de confirmar, envie pelo canal oficial abaixo.</p>`}
      <h4>O que a LexIA encontrou</h4><div class="row gap wrap"><span class="tag" style="--c:${an.gravidade === 'alta' ? '#C83037' : an.gravidade === 'media' ? '#D4A12E' : '#63768A'}">Gravidade ${e(an.gravidade)}</span></div>
      <ul class="ticks">${an.temas.map((t) => `<li>${e(t)}</li>`).join('') || '<li>Relato genérico.</li>'}</ul>
      ${an.dossie ? `<h4>Normas que podem não estar sendo cumpridas</h4>${normasDz(an.dossie)}<h4>O que pode implicar para a empresa</h4>${implicDz(an.dossie)}
        <p class="hint">A empresa recebe também um dossiê com <b>${an.dossie.caminhos?.length || 0} caminhos para resolver</b>, cada um com responsável e prazo sugerido.</p>`
        : `<div class="basis">${an.normas.map((n) => `<a class="law" href="${e(n.url || '#')}" target="_blank" rel="noopener noreferrer" title="${e(n.text)}">${e(n.ref)}</a>`).join('')}</div>`}
      ${an.lacuna ? '<p class="hint">Este caso foi para a curadoria da LexIA completar o catálogo de normas.</p>' : ''}
      <details class="sm mt8"><summary>Possíveis consequências para o responsável</summary><ul>${an.consequencias.map((c) => `<li>${e(c)}</li>`).join('')}</ul></details></div></div>
    <details class="mt8"><summary>Ver o documento completo</summary><textarea class="rd-draft" rows="16" readonly>${e(cur.body)}</textarea><button class="btn sm mt8" id="dn-dl" type="button">${icon('doc')} Baixar .txt</button></details>
    ${!enviado ? `<div class="dn-confirm">${ANON ? '<p class="sm"><b>Denúncia anônima:</b> a empresa e o órgão não recebem nenhum dado seu. Depois de enviar, você recebe um código para acompanhar.</p>' : '<label class="chip-btn"><input type="checkbox" id="dn-id"> Mostrar meu nome e e-mail para a empresa (se não marcar, vai anônima)</label>'}
        <div class="row gap wrap"><button class="btn primary lg" id="dn-ok">${icon('check')} Revisei, enviar denúncia</button><button class="btn" id="dn-edit2" type="button">Corrigir relato</button></div>
        <p class="hint">Nada é enviado sem este clique. O documento fica guardado com hash (<code>${e(cur.sha256.slice(0, 12))}…</code>) na sua conta.</p></div>`
    : `${ANON && st.codigo ? `<div class="dn-codigo"><span>Seu código de acompanhamento</span><b>${e(st.codigo)}</b><small>Guarde este código: é a única forma de acompanhar a resposta, porque não guardamos quem você é.</small></div>` : ''}
      ${cur.empresa_resposta?.resposta ? `<p class="cp-act"><b>Resposta da empresa:</b> ${e(cur.empresa_resposta.resposta)}</p>` : ''}
      <p class="cp-act">✓ ${st.destino?.cadastrada_na_lexia ? `Enviada para <b>${e(st.destino.empresa)}</b> na LexIA${st.destino.emails ? ` e ${st.destino.emails} e-mail(s) para compliance e jurídico` : ''}. Você acompanha a resposta em “Minhas denúncias”.` : 'Confirmada. Agora envie pelo canal oficial abaixo.'}</p>
      <h4>Envie também pelo canal oficial</h4><div class="dn-ch">${(an.canais || []).map((c) => `<a class="crit-i" href="${e(c.url)}" target="_blank" rel="noopener noreferrer"><b>${e(c.nome)}</b><p>${e(c.quando)}</p><span>Abrir ${icon('arrow')}</span></a>`).join('')}</div>
      ${cur.state === 'CONFIRMADA' ? `<form id="dn-fw" class="row gap wrap mt8"><input id="dn-proto" placeholder="Número do protocolo recebido (opcional)" aria-label="Protocolo"><button class="btn">Registrar que enviei ao órgão</button></form>` : `<p class="hint">Registrado em ${fmtDateTime(cur.forwarded_at)}${cur.protocol ? ` · protocolo ${e(cur.protocol)}` : ''}.</p>`}
      <button class="btn mt8" id="dn-new" type="button">Fazer outra denúncia</button>`}</section>`;
}

async function renderDen() {
    const st = DS();
    const hashDam = new URLSearchParams(location.hash.split('?')[1] || '').get('dam');
    if (hashDam) { Object.assign(st, { cat: st.cat || 'barragem', sel: { id: hashDam, n: 1, nome: hashDam, numero: hashDam, tipo: 'Estrutura escolhida no radar', empresa: '—', km: 0, real: true, fonte: 'Radar LexIA' }, current: null, an: null, editando: true }); history.replaceState(null, '', '#/denuncia'); }
    const mine = ANON ? { items: [] } : await api('/api/denuncias').catch(() => ({ items: [] }));
    const cur = !st.current ? null : ANON ? await api('/api/denuncia-anonima?codigo=' + encodeURIComponent(st.codigo || '')).catch(() => null) : await api('/api/denuncias?id=' + st.current).catch(() => null);
    const showForm = !cur || st.editando;
    return `<header class="page-head"><div><span class="eyebrow">${ANON ? 'Sem conta · sem nome' : 'LexIA Cidadão'}</span><h2>${ANON ? 'Denúncia anônima' : 'Fazer denúncia'}</h2><p class="muted">${ANON ? 'Não precisa de conta. Nenhum dado seu é guardado nem enviado: você recebe um código para acompanhar a resposta.' : 'Três passos: escolha o assunto, marque no mapa e conte o que viu. A LexIA organiza a denúncia e você revisa antes de enviar.'}</p></div></header>
    ${ANON ? `<form class="dn-acomp" id="dn-acomp"><span>Já fez uma denúncia anônima?</span><input id="dn-cod" placeholder="Código LX-…" aria-label="Código de acompanhamento"><button class="btn sm">Acompanhar</button></form>` : ''}
    <div class="warn-note">${icon('phone')} Risco imediato à vida (rompimento, lama descendo, fio caído energizado, evacuação)? Ligue <b>199 (Defesa Civil)</b> ou <b>193 (Bombeiros)</b> antes de qualquer outro passo.</div>
    <div class="dn-flow">${showForm ? passo1(st) + passo2(st) + passo3(st) : ''}${passo4(st, cur)}</div>
    ${mine.items.length ? `<section class="card mt16"><header class="card-h"><h3>${icon('book', 'h-ic')}Minhas denúncias</h3></header><div class="table-wrap"><table class="table compact"><thead><tr><th>#</th><th>Sobre</th><th>Situação</th><th>Criada</th><th>Protocolo</th></tr></thead><tbody>${mine.items.map((d) => `<tr><td><button class="link" data-open="${d.id}">${d.id}</button></td><td>${e(d.dam_id || catInfo(d.categoria)[1])}</td><td>${e({ RASCUNHO: 'Rascunho', CONFIRMADA: 'Enviada', ENCAMINHADA_PELO_USUARIO: 'Enviada ao órgão' }[d.state] || d.state)}</td><td>${fmtDateTime(d.created_at)}</td><td>${e(d.protocol || '—')}</td></tr>`).join('')}</tbody></table></div></section>` : ''}`;
  }

function mountDen(root, ctx) {
    const st = DS();
    if (st.rolar) { const el = root.querySelector(st.rolar); st.rolar = null; el?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    const keep = () => { const r = root.querySelector('#dn-rel'); if (r) st.relato = r.value; const q = root.querySelector('#dn-q'); if (q) st.quando = q.value; const d = root.querySelector('#dn-d'); if (d) st.data = d.value; };
    const buscar = async (lat, lon, nome) => {
      try { st.me = { lat, lon, nome }; st.near = await api('/api/proximos', { lat, lon, categoria: st.cat }); st.sel = null; st.rolar = '#dn-passo2'; } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    };
    root.querySelectorAll('[data-cat]').forEach((b) => b.addEventListener('click', () => { keep(); st.cat = b.dataset.cat; st.near = null; st.sel = null; st.rolar = '#dn-passo2'; if (st.me) buscar(st.me.lat, st.me.lon, st.me.nome); else ctx.rerender(); }));
    root.querySelector('#dn-geo')?.addEventListener('click', (ev) => {
      if (!navigator.geolocation) return toast('Este navegador não oferece localização. Use o local de exemplo.', 'err');
      keep(); ev.target.disabled = true; ev.target.textContent = 'Localizando…';
      navigator.geolocation.getCurrentPosition((pos) => buscar(pos.coords.latitude, pos.coords.longitude, 'sua localização'),
        (err) => { toast(err.code === 1 ? 'Permissão de localização negada. Use o local de exemplo ou descreva o local.' : 'Não foi possível obter a localização.', 'err'); ctx.rerender(); },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
    });
    root.querySelector('#dn-ex')?.addEventListener('click', () => { keep(); buscar(EXEMPLO.lat, EXEMPLO.lon, EXEMPLO.nome); });
    root.querySelector('#dn-skip')?.addEventListener('click', () => { keep(); st.sel = false; st.near = null; st.rolar = '#dn-rel'; ctx.rerender(); });
    root.querySelectorAll('[data-pick]').forEach((b) => b.addEventListener('click', () => { keep(); st.sel = st.near.items.find((x) => x.id === b.dataset.pick) || null; st.rolar = '.dm-det'; ctx.rerender(); }));
    root.querySelector('#dn-q')?.addEventListener('change', () => { keep(); ctx.rerender(); });
    root.querySelector('#dn-files')?.addEventListener('change', async (ev) => {
      keep();
      if (!currentUser()) return toast('Entre com uma conta para anexar.', 'err');
      for (const f of [...ev.target.files].slice(0, 5)) {
        if (f.size > 5 * 1024 * 1024) { toast(`${f.name}: máximo 5 MB.`, 'err'); continue; }
        const b64 = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.readAsDataURL(f); });
        try { st.ev.push(await api('/api/docs/upload', { name: f.name, mime: f.type || 'application/octet-stream', data: b64, kind: 'evidencia' })); } catch (err) { toast(err.message, 'err'); }
      }
      ctx.rerender();
    });
    root.querySelector('#dn-go')?.addEventListener('click', async (ev) => {
      keep(); if (st.relato.trim().length < 15) return toast('Conte um pouco mais do que você viu.', 'err');
      const qd = st.quando === 'data' && st.data ? st.data.split('-').reverse().join('/') : st.quando && st.quando !== 'nao lembro' ? st.quando : '';
      const relato = st.relato.trim() + (qd ? `\n(Quando: ${qd})` : '');
      ev.target.disabled = true; ev.target.textContent = 'Organizando a denúncia…';
      try {
        const r = await api('/api/denuncia', { dam_id: st.sel?.id || '', categoria: st.cat, relato, evidence_ids: st.ev.map((x) => x.id), anonimo: ANON });
        if (ANON && r.codigo_acompanhamento) st.codigo = r.codigo_acompanhamento;
        Object.assign(st, { current: r.id, an: r.analysis, destino: null, vaiEmpresa: r.vai_para_empresa, empresa: r.empresa, editando: false });
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    });
    const editar = () => { st.editando = true; st.current = null; st.an = null; ctx.rerender(); };
    root.querySelector('#dn-edit')?.addEventListener('click', editar);
    root.querySelector('#dn-edit2')?.addEventListener('click', editar);
    root.querySelector('#dn-ok')?.addEventListener('click', async (ev) => {
      ev.target.disabled = true;
      try { const r = await api('/api/denuncia', { action: 'confirm', id: st.current, identificar: !ANON && !!root.querySelector('#dn-id')?.checked, anonimo: ANON, codigo: st.codigo }); st.destino = r.empresa_destino; toast(r.empresa_destino?.cadastrada_na_lexia ? 'Denúncia enviada para a empresa.' : 'Confirmada. Envie pelo canal oficial.'); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    });
    root.querySelector('#dn-fw')?.addEventListener('submit', async (ev) => { ev.preventDefault(); try { await api('/api/denuncia', { action: 'forwarded', anonimo: ANON, codigo: st.codigo, id: st.current, protocol: root.querySelector('#dn-proto').value }); toast('Registrado.'); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); });
    root.querySelector('#dn-dl')?.addEventListener('click', () => { const t = root.querySelector('.rd-draft').value; const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], { type: 'text/plain;charset=utf-8' })); a.download = `denuncia_${st.current}.txt`; a.click(); URL.revokeObjectURL(a.href); });
    root.querySelector('#dn-new')?.addEventListener('click', () => { if (ANON) state.denA = null; else state.den = null; ctx.rerender(); });
  root.querySelector('#dn-acomp')?.addEventListener('submit', async (ev) => { ev.preventDefault(); const c = root.querySelector('#dn-cod').value.trim().toUpperCase(); if (!c) return;
    try { const d = await api('/api/denuncia-anonima?codigo=' + encodeURIComponent(c)); Object.assign(st, { codigo: c, current: d.id, editando: false, destino: d.empresa_resposta ? { cadastrada_na_lexia: true, empresa: d.empresa_resposta.empresa } : null,
      an: { resumo: d.resumo, dossie: d.dossie, temas: [], normas: [], consequencias: [], gravidade: '—', engine: 'regras', destinatario: '', canais: [] } }); } catch (err) { toast(err.message, 'err'); } ctx.rerender(); });
    root.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', async () => {
      const d = await api('/api/denuncias?id=' + b.dataset.open).catch(() => null); if (!d) return;
      Object.assign(st, { current: d.id, editando: false, an: st.current === d.id && st.an ? st.an : { resumo: d.resumo, temas: [], normas: [], consequencias: [], gravidade: '—', engine: 'regras', destinatario: '', canais: [] } });
      ctx.rerender();
    }));
}

export const denunciaPage = { citizen: true, both: true, title: 'Fazer denúncia', render: () => { ANON = false; return renderDen(); }, mount: (r, c) => { ANON = false; mountDen(r, c); } };
export const denunciaAnonimaPage = { public: true, title: 'Denúncia anônima', render: () => { ANON = true; return renderDen(); }, mount: (r, c) => { ANON = true; mountDen(r, c); } };

