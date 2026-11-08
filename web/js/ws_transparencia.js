// Portal da Transparência — público, sem login. Dados oficiais (ANM/ANA) + o que aconteceu com as denúncias feitas na LexIA.
import { state, api, e, fmtDateTime, icon, currentUser } from './core.js';
import { createMap } from './map.js';

const ATT = { 'Crítica': ['#C83037', 'crit', 'Vários sinais graves juntos nos dados públicos'], 'Alta': ['#D9762D', 'alta', 'Sinais importantes que pedem verificação'],
  'Moderada': ['#D4A12E', 'mod', 'Algum sinal a acompanhar'], 'Baixa': ['#63768A', 'baixa', 'Poucos sinais'], 'Sem sinal': ['#9EA8AE', 'sem', 'Nenhum sinal nos campos públicos'] };
const TS = () => (state.tp = state.tp || { so: true, q: '', uf: '', busca: '' });
const norm = (x) => String(x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const n = (x) => Number(x || 0).toLocaleString('pt-BR');

export const transparencia = {
  public: true, inApp: true, citizen: true, both: true, title: 'Portal da Transparência',
  async render() {
    const st = TS();
    const D = await api('/api/transparencia');
    state.tpData = D;
    const T = D.totais, dn = D.denuncias;
    const q = st.q.trim().toLowerCase();
    const emps = D.empresas.filter((o) => (!q || o.empresa.toLowerCase().includes(q)) && (!st.uf || o.ufs.includes(st.uf)));
    const casos = D.casos.filter((c) => !st.uf || c.uf === st.uf);
    const maxUf = Math.max(...D.por_uf.map((u) => u.barragens), 1);
    const logado = !!currentUser(), b = norm(st.busca.trim());
    const rB = b.length < 2 ? [] : D.pontos.filter((p) => norm(p.n).includes(b) || norm(p.id).includes(b) || norm(p.uf) === b).slice(0, 8);
    const rC = b.length < 2 ? [] : D.casos.filter((c) => norm(c.nome).includes(b) || norm(c.municipio).includes(b) || norm(c.empresa).includes(b)).slice(0, 8);
    const rE = b.length < 2 ? [] : D.empresas.filter((o) => norm(o.empresa).includes(b)).slice(0, 6);
    const busca = `<form class="tp-search" id="tp-bform" role="search"><input id="tp-busca" value="${e(st.busca)}" placeholder="Pesquisar barragem, cidade, empresa ou código (ex.: Itabirito, VALE, SIGBM-8303)" aria-label="Pesquisar na transparência"><button class="btn primary">${icon('search')} Pesquisar</button></form>
      ${b.length < 2 ? '' : `<section class="card tp-res"><header class="card-h"><h3>${icon('search', 'h-ic')}Resultados para “${e(st.busca)}”</h3><button class="btn sm ghost" id="tp-limpa" type="button">Limpar</button></header>
        ${!rB.length && !rC.length && !rE.length ? '<p class="muted">Nada encontrado nos dados públicos. Tente o nome da cidade ou da empresa.</p>' : ''}
        ${rC.length ? `<h4>Casos em atenção</h4><div class="tp-cases">${rC.map((c) => `<article><span class="lx-chip ${ATT[c.atencao][1]}">${e(c.atencao)}</span><b>${e(c.nome)}</b><small>${e(c.municipio)}/${e(c.uf)} · ${e(c.empresa)}</small></article>`).join('')}</div>` : ''}
        ${rB.length ? `<h4>Barragens</h4><ul class="ticks">${rB.map((p) => `<li><b>${e(p.n)}</b> <small class="muted">${e(p.id)} · ${e(p.uf)} · atenção ${e(p.a)}</small></li>`).join('')}</ul>` : ''}
        ${rE.length ? `<h4>Empresas</h4><ul class="ticks">${rE.map((o) => `<li><b>${e(o.empresa)}</b> <small class="muted">${o.barragens} barragem(ns) · ${o.critica + o.alta} em atenção crítica/alta</small></li>`).join('')}</ul>` : ''}</section>`}`;
    return `<section class="tp-wrap">
    <header class="page-head"><div><span class="eyebrow">${logado ? 'Dados oficiais · dentro da sua conta' : 'Aberto a todos · sem login · dados oficiais'}</span><h2>Portal da Transparência</h2>
      <p class="muted">Barragens e minas do Brasil com os dados públicos da ANM e da ANA, e o que aconteceu com as denúncias feitas pela <b>LexIA Cidadão</b>: quantas chegaram às empresas e quantas foram respondidas.</p></div></header>
    ${busca}

    <div class="tp-kpis">
      <div><b>${n(T.barragens_mineracao)}</b><span>barragens de mineração no cadastro oficial (SIGBM)</span></div>
      <div class="c"><b>${n(D.atencao['Crítica'] + D.atencao['Alta'])}</b><span>com atenção <b>crítica ou alta</b> no radar da LexIA</span></div>
      <div class="a"><b>${n(T.em_emergencia)}</b><span>em nível de emergência declarado</span></div>
      <div><b>${n(T.barragens_sem_dono)}</b><span>barragens sem empreendedor identificado (SNISB)</span></div>
      <div><b>${n(T.minas_lavra)}</b><span>minas com título de lavra (SIGMINE), ${n(T.minas_radiologicas)} com sinal radiológico</span></div>
    </div>

    <section class="tp-how"><h3>${icon('book')} Como ler esta página</h3><ol>
      <li><b>Cada ponto do mapa é uma barragem oficial</b> (cadastro da ANM). A cor é o nível de atenção que a LexIA calcula juntando os campos públicos: declaração de estabilidade, dano potencial, situação, empreendedor.</li>
      <li><b>Atenção não é acusação.</b> É um sinal para alguém conferir, não prova de irregularidade nem previsão de rompimento.</li>
      <li><b>Denúncias aparecem só como números.</b> Ninguém vê o texto, quem denunciou nem de onde.</li></ol></section>

    <div class="tp-grid">
      <section class="card flush"><div class="rd-maph"><b>Mapa das barragens de mineração</b>
        <label class="chip-btn ${st.so ? 'on' : ''}"><input type="checkbox" id="tp-so" ${st.so ? 'checked' : ''}> mostrar só crítica e alta</label></div>
        <div id="tp-map" class="tp-map map-frame"></div>
        <div class="tp-leg">${Object.entries(ATT).map(([k, [c, , d]]) => `<span><i style="background:${c}"></i><b>${k}</b> ${n(D.atencao[k])}<small>${d}</small></span>`).join('')}</div></section>
      <section class="card"><header class="card-h"><h3>${icon('alert', 'h-ic')}Casos com atenção crítica ou alta</h3><select id="tp-uf" aria-label="Estado"><option value="">Todo o Brasil</option>${D.por_uf.map((u) => `<option ${st.uf === u.uf ? 'selected' : ''}>${e(u.uf)}</option>`).join('')}</select></header>
        <div class="tp-cases">${casos.slice(0, 14).map((c) => `<article><span class="lx-chip ${ATT[c.atencao][1]}">${e(c.atencao)}</span><b>${e(c.nome)}</b><small>${e(c.municipio)}/${e(c.uf)} · ${e(c.empresa)}${c.dpa ? ` · dano potencial ${e(c.dpa).toLowerCase()}` : ''}</small>
          <ul>${c.sinais.map((s) => `<li>${e(s)}</li>`).join('')}</ul></article>`).join('') || '<p class="muted">Nenhum caso crítico ou alto neste estado.</p>'}</div></section>
    </div>

    <section class="card mt16"><header class="card-h"><h3>${icon('doc', 'h-ic')}Denúncias feitas pela LexIA Cidadão</h3></header>
      <div class="tp-den"><div><b>${n(dn.registradas)}</b><span>denúncias confirmadas por quem denunciou</span></div><div><b>${n(dn.encaminhadas_empresa)}</b><span>chegaram direto à empresa responsável</span></div>
        <div><b>${n(dn.em_apuracao)}</b><span>em apuração pela empresa</span></div><div class="ok"><b>${n(dn.respondidas)}</b><span>respondidas pela empresa</span></div><div><b>${n(dn.enviadas_ao_orgao)}</b><span>enviadas também ao órgão oficial</span></div></div>
      ${D.denuncias_por_empresa.length ? `<table class="table compact mt12"><thead><tr><th>Empresa (usa a LexIA)</th><th>Recebidas</th><th>Em apuração</th><th>Respondidas</th><th>Sem resposta</th><th>Taxa de resposta</th></tr></thead>
        <tbody>${D.denuncias_por_empresa.map((x) => `<tr><td>${e(x.empresa)}</td><td>${x.recebidas}</td><td>${x.em_apuracao}</td><td>${x.respondidas}</td><td>${x.sem_resposta}</td><td>${x.taxa_resposta == null ? '—' : Math.round(x.taxa_resposta * 100) + '%'}</td></tr>`).join('')}</tbody></table>` : ''}
      <p class="hint">Empresas que não usam a LexIA recebem a denúncia pelo órgão oficial (ANM, ANA, Defesa Civil); por isso não aparecem aqui. As empresas da demonstração são fictícias.</p></section>

    <section class="card mt16"><header class="card-h"><h3>${icon('building', 'h-ic')}Empresas com barragens — dados públicos</h3><input class="search" id="tp-q" value="${e(st.q)}" placeholder="Buscar empresa" style="max-width:260px"></header>
      <div class="table-wrap tall"><table class="table compact"><thead><tr><th>Empresa (pessoa jurídica)</th><th>UF</th><th>Barragens</th><th>Crítica / alta</th><th>Dano potencial alto</th><th>Em emergência</th><th>Minério principal</th><th>Títulos de lavra</th><th>Na LexIA</th></tr></thead>
        <tbody>${emps.slice(0, 40).map((o) => `<tr><td><b>${e(o.empresa)}</b></td><td>${o.ufs.map(e).join(', ')}</td><td>${o.barragens}</td><td>${o.critica || o.alta ? `<span class="lx-chip ${o.critica ? 'crit' : 'alta'}">${o.critica} / ${o.alta}</span>` : '0'}</td><td>${o.dpa_alta}</td><td>${o.emergencia ? `<b style="color:#C83037">${o.emergencia}</b>` : 0}</td><td>${o.minerio.map(e).join(', ') || '—'}</td><td>${o.titulos_lavra || '—'}</td><td>${o.usa_lexia ? 'sim' : 'não'}</td></tr>`).join('')}</tbody></table></div>
      <p class="hint">Ordenado pelo número de barragens em atenção crítica ou alta. ${n(T.empresas_pj)} empresas no cadastro. Títulos de lavra contados só quando o nome é idêntico no SIGMINE.</p></section>

    <section class="card mt16"><header class="card-h"><h3>${icon('chart', 'h-ic')}Por estado</h3></header>
      <div class="tp-uf">${D.por_uf.slice(0, 16).map((u) => `<div><span>${e(u.uf)}</span><i><em style="width:${(u.barragens / maxUf * 100).toFixed(1)}%"></em><em class="c" style="width:${(u.critica_alta / maxUf * 100).toFixed(1)}%"></em></i><small>${u.barragens} · ${u.critica_alta} em crítica/alta</small></div>`).join('')}</div></section>

    <div class="tp-notes">${D.avisos.map((a) => `<p>${icon('shield')} ${e(a)}</p>`).join('')}<p>Fonte: ANM/SIGBM ${D.snapshot ? `(snapshot ${e(D.snapshot.snapshot_id)}, ${fmtDateTime(D.snapshot.fetched_at)})` : ''}, ANA/SNISB, ANM/SIGMINE. Regra ${e(D.rule_version)}.</p></div>
    <div class="row gap wrap center mt16"><a class="btn primary lg" href="#/denuncia">${icon('doc')} Fazer uma denúncia</a>${logado ? '' : '<a class="btn lg" href="#/cadastro" data-auth-tab="cidadao">Criar conta na LexIA Cidadão</a>'}</div>
    </section>`;
  },
  mount(root, ctx) {
    const st = TS(), D = state.tpData;
    const pts = D.pontos.filter((p) => (!st.so || p.a === 'Crítica' || p.a === 'Alta') && (!st.uf || p.uf === st.uf))
      .map((p) => ({ id: p.id, lat: p.lat, lon: p.lon, kind: 'official', color: ATT[p.a]?.[0] || '#9EA8AE', label: `${p.n} · ${p.a}` }));
    const el = root.querySelector('#tp-map');
    if (el) createMap(el, { points: pts, selected: null, controls: true, legend: false, onlyBrazil: true, pinScale: 1.3, height: 460, onSelect: () => {} });
    root.querySelector('#tp-bform')?.addEventListener('submit', (ev) => { ev.preventDefault(); st.busca = root.querySelector('#tp-busca').value; ctx.rerender(); });
    root.querySelector('#tp-limpa')?.addEventListener('click', () => { st.busca = ''; ctx.rerender(); });
    root.querySelector('#tp-so')?.addEventListener('change', (ev) => { st.so = ev.target.checked; ctx.rerender(); });
    root.querySelector('#tp-uf')?.addEventListener('change', (ev) => { st.uf = ev.target.value; ctx.rerender(); });
    let t; root.querySelector('#tp-q')?.addEventListener('input', (ev) => { clearTimeout(t); t = setTimeout(async () => { st.q = ev.target.value; await ctx.rerender(); const q = document.querySelector('#tp-q'); q?.focus(); q?.setSelectionRange(q.value.length, q.value.length); }, 350); });
  },
};
