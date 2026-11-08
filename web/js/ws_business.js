// Negócio & Impacto — modelo de negócio do estudo de mercado (planilhas reproduzíveis) + dados ao vivo do sistema.
import { state, api, e, card, icon } from './core.js';

const n = (v) => Number(v || 0).toLocaleString('pt-BR');
const brl = (v) => (v < 0 ? '−' : '') + 'R$ ' + Math.round(Math.abs(v)).toLocaleString('pt-BR');
const mil = (v) => (v < 0 ? '−' : '') + 'R$ ' + (Math.abs(v) / 1e6 >= 1 ? (Math.abs(v) / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' mi' : Math.round(Math.abs(v) / 1000).toLocaleString('pt-BR') + ' mil');
const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`);
const BS = () => (state.biz = state.biz || { price: 48000, clients: 15, sales: 7 });

const CRITERIA = [
  ['Negócios e empreendedorismo', 5, 'Problema de empresa com dor recorrente (campanhas da ANM em março e setembro), assinatura corporativa de R$ 48 mil/ano, equilíbrio com 13 clientes, payback de venda em 4,6 meses.', '#/negocio'],
  ['Engenharia de software e IA', 5, 'MVP funcionando com dados oficiais: agente autônomo, 2 modelos preditivos validados, ciclo de evolução, IA generativa com verificador (Gemini/Claude/Bedrock), 200+ testes, cofre AWS.', '#/ia'],
  ['Economia e análise de mercado', 4, 'TAM/SAM/SOM com fonte: 217 organizações → 89 contas atendíveis (R$ 4,27 mi/ano); 3 cenários; concorrentes mapeados com evidência.', '#/negocio'],
  ['Marketing e vendas', 3, 'Gatilho datado de compra (DCE), isca "sua barragem no radar", prova com dado público, venda consultiva ao comitê compliance + geotecnia + jurídico.', '#/negocio'],
  ['Impacto social', 1, 'Valor adicional: barragens sem dono, portal do cidadão e representação pronta — sem entrar na conta de receita.', '#/radar'],
];
const MARK = { C: ['Confirmado', '#46774E'], P: ['Parcial', '#D4A12E'], NI: ['Não identificado', '#CBD5E1'], PL: ['Planejado', '#94A3B8'], D: ['Demonstrado nesta versão', '#1570EF'] };
const TORRE_NOW = { oferta: 'LexIA (esta versão)', monitora: 'D', contexto: 'D', obrigacoes: 'D', prazos: 'D', historico: 'D', trilha: 'D', encaminha: 'P', evidencia: 'Demo' };

function simulate(st, U) {
  const rec = st.clients * st.price + st.sales * U.implantacao_preco;
  const cost = U.fixo_ano5 + st.sales * U.comercial_por_venda + st.sales * U.implantacao_custo + st.clients * U.atendimento_por_conta + U.reserva_receita * rec;
  const contrib = st.price * (1 - U.reserva_receita) - U.atendimento_por_conta;
  const need = (U.fixo_ano5 + st.sales * U.comercial_por_venda - st.sales * (U.implantacao_preco * (1 - U.reserva_receita) - U.implantacao_custo)) / contrib;
  return { rec, cost, res: rec - cost, contrib, need };
}

export const negocio = {
  async render() {
    const st = BS(), B = await api('/api/business');
    const MS = await api('/api/mercado-setores').catch(() => null);
    st.cli = st.cli || { plano: 'Profissional', uso: 'Base' };
    // preços: hipóteses do estudo (Torre_Regulatoria_Planilhas.xlsx · Precos); custo técnico: LexIA_Custo_Operacao_por_Empresa.xlsx (opção Gemini, PTAX 06/11/2026)
    const PLANOS = { Entrada: 36000, Profissional: 48000, Corporativo: 60000 }, CUSTO = { Baixo: 17.87, Base: 38.63, Alto: 138.41 }, EQUIPE = 1000;
    const precoMes = PLANOS[st.cli.plano] / 12, tec = CUSTO[st.cli.uso], total = tec + (EQUIPE - 38.63);
    const fmt = (v) => 'R$ ' + Math.round(v).toLocaleString('pt-BR');
    const mercadoCard = MS ? `<section class="card mt16"><header class="card-h"><h3>${icon('layers', 'h-ic')}Mercado por setor — contas nos cadastros oficiais</h3></header>
      <table class="table compact"><thead><tr><th>Setor</th><th>Organizações</th><th>Com 3+ ativos</th><th>Base</th><th>Fonte</th></tr></thead>
      <tbody>${MS.setores.map((x) => `<tr><td><b>${e(x.setor)}</b></td><td>${x.contas.toLocaleString('pt-BR')}${x.em_risco_outorga ? `<br><small class="muted">${x.em_risco_outorga} com outorga em atenção crítica/alta</small>` : ''}</td><td>${x.com_3_ou_mais ?? '—'}</td><td><small>${e(x.base)}</small></td><td>${e(x.fonte)}</td></tr>`).join('')}</tbody></table>
      <p class="hint">${e(MS.aviso)} Mineração já tem o mercado consolidado do estudo (89 contas atendíveis); energia e saneamento mostram o universo real a qualificar.</p></section>` : '';
    const simCard = `<section class="card mt16"><header class="card-h"><h3>${icon('chart', 'h-ic')}Conta por cliente (mensal)</h3></header>
      <div class="row gap wrap"><label class="field"><span>Plano</span><select data-cli="plano">${Object.keys(PLANOS).map((k) => `<option ${st.cli.plano === k ? 'selected' : ''}>${k}</option>`).join('')}</select></label>
        <label class="field"><span>Uso de IA</span><select data-cli="uso">${Object.keys(CUSTO).map((k) => `<option ${st.cli.uso === k ? 'selected' : ''}>${k}</option>`).join('')}</select></label></div>
      <div class="eff-grid mt8"><div><b>${fmt(precoMes)}</b><span>assinatura por mês (hipótese de preço)</span></div><div><b>${fmt(tec)}</b><span>custo técnico: IA + nuvem (planilha de custo)</span></div>
        <div><b>${fmt(total)}</b><span>custo total com curadoria e suporte (estudo: R$ 1.000/mês)</span></div><div><b>${Math.round((1 - total / precoMes) * 100)}%</b><span>margem bruta por cliente</span></div></div>
      <p class="hint">Preço e custo de equipe são hipóteses a validar no piloto; o custo técnico vem dos preços de IA e AWS pesquisados (conferir os marcados como “CONFERIR” na planilha). Nenhuma economia ou multa evitada é prometida.</p></section>`;
    const E = B.estudo, P = E.painel, R = E.retorno, U = B.unit_costs, M = B.market, AI = B.ai_efficiency, S = B.social;
    const base = (k) => P[k]?.base, ret = (k) => R[k]?.base;
    const sim = simulate(st, U);
    const occ = (k) => E.ocorrencias.find((o) => String(o.evento || '').includes(k));
    const dce = occ('referência combinada') || { obrigatorias: 919, nao_enviadas: 39, embargos: 76 };
    const eq = E.equilibrio, maxAbs = Math.max(...eq.map((x) => Math.abs(x.resultado)));
    const scen = [['Assinatura anual', (c) => mil(P['SAM mineral anual'][c] / P['SAM mineral em contas'][c])], ['Contas atendíveis (mineração)', (c) => n(P['SAM mineral em contas'][c])],
      ['Mercado atendível por ano', (c) => mil(P['SAM mineral anual'][c])], ['Clientes no fim do ano 5', (c) => n(P['SOM A5 em contas'][c])], ['ARR no fim do ano 5', (c) => mil(P['SOM A5 em ARR'][c])],
      ['Resultado do ano 5 (após reserva)', (c) => mil(P['Resultado após reserva A5'][c])], ['Capital mínimo indicativo', (c) => mil(P['Capital mínimo indicativo'][c])]];
    const matriz = [...E.matriz.filter((m) => !String(m.oferta).startsWith('LexIA')), TORRE_NOW];
    const cols = [['monitora', 'Monitora'], ['contexto', 'Contexto'], ['obrigacoes', 'Obrigações'], ['prazos', 'Prazos'], ['historico', 'Histórico'], ['trilha', 'Trilha'], ['encaminha', 'Encaminha']];
    const obs = E.precos.filter((p) => p.natureza !== 'Hipótese');
    const planos = E.precos.filter((p) => p.natureza === 'Hipótese' && !String(p.nome).startsWith('Institucional'));
    const benefit = P['Benefício esperado • cliente/ano'] || {};
    return `<header class="page-head"><div><span class="eyebrow">IA para um problema de negócio</span><h2>Negócio & Impacto</h2><p class="muted">Quem tem a dor, quanto custa, por que agora e como vira receita — com fonte e planilha reproduzível.</p></div></header>
    <section class="biz-hero"><div><h3>Plataforma de risco, conformidade e manutenção. Primeiro mercado: mineração, onde cada barragem e cada mina têm prazos que mudam.</h3>
      <p>Em 2026, <b>${n(dce.nao_enviadas)} de ${n(dce.obrigatorias)}</b> declarações de estabilidade obrigatórias não foram enviadas e houve <b>${n(dce.embargos)} embargos</b> nas campanhas. Em 2025 a ANM lavrou <b>${n(occ('Autos de infração')?.obrigatorias ?? 620)} autos</b> e aplicou <b>${n(occ('Multas aplicadas')?.obrigatorias ?? 212)} multas</b>. A LexIA lê a publicação oficial, mostra qual unidade muda, atualiza a obrigação com prazo, dono e prova — e a IA prevê onde o próximo problema vai aparecer.</p>
      <p class="sm"><b>Escala por configuração:</b> o mesmo núcleo já roda cenários de energia e saneamento (empresas fictícias na demo) trocando só o cadastro de setor, ativos, limites e papéis. Os números de receita abaixo são da mineração (estudo); o universo de energia e saneamento está contado nos cadastros oficiais no quadro “Mercado por setor”.</p></div>
      <div class="biz-big"><b>${mil(base('SAM mineral anual'))}</b><span>mercado atendível por ano<br><small>${n(base('SAM mineral em contas'))} contas na mineração (cenário-base)</small></span></div></section>

    <div class="kpis4 mt16">
      <div class="kpi" style="--k:#28518A"><span class="kpi-ic">${icon('building')}</span><div><div class="kpi-v">${n(base('SAM mineral em contas'))}</div><div class="kpi-l">contas atendíveis na mineração</div></div></div>
      <div class="kpi" style="--k:#46774E"><span class="kpi-ic">${icon('target')}</span><div><div class="kpi-v">13</div><div class="kpi-l">clientes para o equilíbrio anual</div></div></div>
      <div class="kpi" style="--k:#68487A"><span class="kpi-ic">${icon('refresh')}</span><div><div class="kpi-v">${ret('Payback de CAC em meses').toFixed(1).replace('.', ',')}</div><div class="kpi-l">meses para pagar o custo de cada venda</div></div></div>
      <div class="kpi" style="--k:#DB2777"><span class="kpi-ic">${icon('chart')}</span><div><div class="kpi-v">${Math.round(ret('LTV sobre CAC variável'))}×</div><div class="kpi-l">valor do cliente sobre custo de venda</div></div></div></div>

    ${mercadoCard}${simCard}
    <div class="grid-6-6 mt16">
      ${card('Quem tem a dor (mercado com fonte)', `<div class="funnel">
          <div class="fn" style="--w:100%;--c:#CBD5E1"><b>${n(M.beachhead.dams)}</b><span>barragens de mineração no SIGBM (dado ao vivo)</span><small>${n(M.beachhead.owners)} documentos responsáveis, incluindo pessoas físicas</small></div>
          <div class="fn" style="--w:84%;--c:#BFDBFE"><b>217</b><span>organizações identificáveis pelo nome (SNISB, E57)</span></div>
          <div class="fn" style="--w:68%;--c:#93C5FD"><b>${n(E.mercado.find((m) => m.etapa === 'Contas minerais')?.base)}</b><span>contas compradoras após consolidar grupos (75%)</span></div>
          <div class="fn" style="--w:52%;--c:#28518A"><b>${n(base('SAM mineral em contas'))}</b><span>contas atendíveis (aderência 55%) = ${mil(base('SAM mineral anual'))}/ano</span></div></div>
        <table class="table compact"><thead><tr><th>Recorte</th><th>Mercado potencial anual (base)</th></tr></thead><tbody>
          <tr><td>Empresas: mineração + saúde suplementar + saneamento (TAM B2B)</td><td>${mil(base('TAM B2B anual'))}</td></tr>
          <tr><td>Setor público: 12 agências + 27 UFs (TAM B2G)</td><td>${mil(base('TAM B2G anual'))}</td></tr>
          <tr><td>Expansão no mesmo problema: donos de barragem na PNSB (SNISB)</td><td>${n(M.sam_expansion.owners)} empreendedores</td></tr></tbody></table>
        <p class="hint">Projeção de vendas só em mineração; demais setores ficam como expansão. Fonte: ${e(E.fonte)}.</p>`, { icon: 'chart' })}
      ${card('Por que pagam: consequência medida', `<div class="pan-big"><div><b>${pct(dce.nao_enviadas / dce.obrigatorias)}</b><span>das entregas obrigatórias de DCE em 2026 sem envio (E51–E52)</span></div>
          <div><b>${brl(B.multa_simulada_dce.valor)}</b><span>multa simulada por DCE não enviada (${e(B.multa_simulada_dce.evidencia)})</span></div>
          <div><b>${n(occ('Autos de embargo')?.obrigatorias ?? 85)}</b><span>autos de embargo da ANM em 2025 (E06)</span></div>
          <div><b>${brl(49680)} – ${brl(62580)}</b><span>contratos públicos anuais de monitoramento já pagos (E18–E19)</span></div></div>
        <p class="hint">${e(B.multa_simulada_dce.regra)}. Acordos de Brumadinho (R$ 37,69 bi) e Rio Doce (R$ 170 bi) entram só como dimensão da consequência; a contribuição atribuída à IA na conta é zero.</p>`, { icon: 'alert' })}
    </div>

    <div class="grid-6-6">
      ${card('Modelo e preço', `<div class="plans">${planos.map((p) => `<div class="plan ${p.nome === 'Profissional' ? 'corporativo' : ''}"><b>${e(p.nome)}${p.nome === 'Profissional' ? ' · base' : ''}</b><span class="price">${brl(p.anual / 12)}<small>/mês</small></span><small>${brl(p.anual)}/ano + ${brl(p.implantacao)} de implantação</small><small>${e(p.escopo)}</small></div>`).join('')}</div>
        <h4>Preços que o mercado já paga (referência)</h4><table class="table compact"><tbody>${obs.map((p) => `<tr><td>${e(p.nome)}</td><td>${p.anual ? brl(p.anual) + '/ano' : '—'}</td><td><small class="muted">${e(String(p.escopo || '').slice(0, 80))} · ${e(p.evidencia)}</small></td></tr>`).join('')}</tbody></table>`, { icon: 'star' })}
      ${card('Economia por cliente', `<div class="eff-grid">
          <div><b>${brl(ret('Contribuição recorrente anual'))}</b><span>contribuição por conta/ano (após reserva e atendimento)</span></div>
          <div><b>${pct(ret('Margem recorrente'))}</b><span>margem recorrente</span></div>
          <div><b>${ret('Payback de CAC em meses').toFixed(1).replace('.', ',')} meses</b><span>para recuperar o custo de cada venda</span></div>
          <div><b>${brl(ret('LTV simples'))}</b><span>valor do cliente (LTV simples)</span></div></div>
        <h4>Cenários (5 anos)</h4><table class="table compact"><thead><tr><th></th><th>Conservador</th><th>Base</th><th>Otimista</th></tr></thead><tbody>${scen.map(([l, f]) => `<tr><td>${l}</td><td>${f('conservador')}</td><td><b>${f('base')}</b></td><td>${f('otimista')}</td></tr>`).join('')}</tbody></table>`, { icon: 'chart' })}
    </div>

    <div class="grid-6-6">
      ${card('Ponto de equilíbrio (ano 5, cenário-base)', `<div class="be-chart">${eq.map((x) => `<div class="be ${x.clientes === 13 ? 'hit' : ''}" title="${x.clientes} clientes: ${brl(x.resultado)}"><i style="--h:${(50 * Math.abs(x.resultado)) / maxAbs}%" class="${x.resultado >= 0 ? 'pos' : 'neg'}"></i><span>${x.clientes}</span></div>`).join('')}</div>
        <p class="hint">Barras = resultado anual por número médio de clientes (receita − custos − reserva de 10%). A partir de <b>13 clientes</b> o ano fecha positivo; o cenário-base projeta 15.</p>`, { icon: 'target' })}
      ${card('Simulador (mesma fórmula do estudo)', `<div class="sim-f">
          <label class="field"><span>Preço anual (R$)</span><input type="number" step="1000" min="0" data-sim="price" value="${st.price}"></label>
          <label class="field"><span>Clientes médios no ano</span><input type="number" step="1" min="0" data-sim="clients" value="${st.clients}"></label>
          <label class="field"><span>Novas implantações no ano</span><input type="number" step="1" min="0" data-sim="sales" value="${st.sales}"></label></div>
        <div class="eff-grid mt8"><div><b>${brl(sim.rec)}</b><span>receita no ano</span></div><div><b>${brl(sim.cost)}</b><span>custos + reserva</span></div>
          <div class="${sim.res >= 0 ? 'ok' : 'bad'}"><b>${brl(sim.res)}</b><span>resultado do ano</span></div><div><b>${sim.contrib > 0 ? Math.ceil(sim.need) : '—'}</b><span>clientes para equilibrar com esse preço</span></div></div>
        <p class="hint">Custos do ano 5 do cenário-base: fixo ${brl(U.fixo_ano5)}, atendimento ${brl(U.atendimento_por_conta)}/conta, venda ${brl(U.comercial_por_venda)}, implantação ${brl(U.implantacao_custo)} (cobrada a ${brl(U.implantacao_preco)}), reserva de 10% da receita. Com R$ 24 mil/ano, seriam ~42 clientes.</p>`, { icon: 'spark', right: '<small class="muted">premissas do estudo, editáveis</small>' })}
    </div>

    <div class="grid-6-6">
      ${card('Retorno para quem compra (honesto)', `<table class="table compact"><thead><tr><th></th><th>Conservador</th><th>Base</th><th>Otimista</th></tr></thead><tbody>
          <tr><td>Horas liberadas por ano (R$)</td><td>${brl(R['Economia laboral anual'].conservador)}</td><td>${brl(R['Economia laboral anual'].base)}</td><td>${brl(R['Economia laboral anual'].otimista)}</td></tr>
          <tr><td>Benefício total esperado/ano</td><td>${brl(benefit.conservador || 0)}</td><td>${brl(benefit.base || 0)}</td><td>${brl(benefit.otimista || 0)}</td></tr>
          <tr><td>Saldo após assinatura</td><td>${brl(R['Saldo após assinatura'].conservador)}</td><td>${brl(R['Saldo após assinatura'].base)}</td><td>${brl(R['Saldo após assinatura'].otimista)}</td></tr></tbody></table>
        <p>Para uma operação média, o benefício (${brl(benefit.base || 0)}) fica <b>abaixo</b> da assinatura de R$ 48 mil. Por isso o cliente-alvo é quem tem <b>várias unidades, mais carga de obrigações ou despesa externa para substituir</b> — ali o benefício chega a ${brl(benefit.otimista || 0)}/ano.</p>
        <p class="hint">Paridade: ~${Math.round(R['Horas mensais para paridade recorrente'].base)} horas/mês de trabalho regulatório. Os modelos de IA deste sistema aumentam esse valor ao dizer <i>onde</i> conferir primeiro.</p>`, { icon: 'users' })}
      ${card('Concorrência (evidência pública)', `<div class="table-wrap"><table class="table compact matrix"><thead><tr><th>Oferta</th>${cols.map(([, l]) => `<th>${l}</th>`).join('')}</tr></thead><tbody>${matriz.map((m) => `<tr class="${m.evidencia === 'Demo' ? 'me' : ''}"><td><b>${e(m.oferta)}</b></td>${cols.map(([k]) => `<td><span class="mk" style="--c:${MARK[m[k]]?.[1] || '#CBD5E1'}" title="${e(MARK[m[k]]?.[0] || m[k])}">${e(m[k] || '—')}</span></td>`).join('')}</tr>`).join('')}</tbody></table></div>
        <p class="hint">C = confirmado em material público · P = parcial · NI = não identificado · D = demonstrado nesta versão. Nenhuma oferta da matriz declara <b>previsão por estrutura</b> (qual barragem vai falhar na próxima DCE) nem <b>modelo que aprende com a conferência do cliente</b>: esse é o diferencial de IA.</p>`, { icon: 'layers' })}
    </div>

    <div class="grid-6-6">
      ${card('Como a IA multiplica o valor', `<div class="eff">${Object.entries(AI.models).map(([t, m]) => `<div><span class="eyebrow">${t === 'emergencia' ? 'Emergência não declarada' : 'Falha na próxima DCE'}</span>
          <div class="eff-row"><b>${pct(m.precision_top10)}</b><span>acerto nas 10 primeiras da fila</span></div><div class="eff-row"><b>${String(m.lift_top50).replace('.', ',')}×</b><span>melhor que ao acaso (top 50)</span></div><div class="eff-row"><b>${String(m.cv_auc).replace('.', ',')}</b><span>AUC (validação cruzada)</span></div></div>`).join('')}</div>
        <p class="hint">O agente roda sozinho a cada dado novo da ANM, prioriza a conferência e propõe ações; cada “confirmo / não procede” vira treino. ${e(AI.reading)}</p>`, { icon: 'target' })}
      ${card('Go-to-market', `<ul class="gtm">${B.sales_calendar.map((s) => `<li><time>${e(s.when)}</time><b>${e(s.what)}</b><small>${e(s.why)}</small></li>`).join('')}</ul>
        <h4>Ordem de expansão (nota do estudo)</h4><div class="hbars">${E.segmentos.filter((s) => s.segmento !== 'Pesos').slice(0, 6).map((s) => `<div class="hb"><span>${e(s.segmento)}</span><i style="--w:${(100 * s.nota) / 5}%;--c:#28518A"></i><b>${s.nota.toFixed(2).replace('.', ',')}</b></div>`).join('')}</div>`, { icon: 'arrow' })}
    </div>

    ${card('Valor adicional para a sociedade', `<div class="pan-big three"><div><b>${n(S.with_permanent_population)}</b><span>barragens apontadas com moradores abaixo</span></div><div><b>${n(M.tam.dams - M.tam.with_owner)}</b><span>barragens no país sem dono identificado (SNISB)</span></div><div><b>${n(S.orphans_human_supply)}</b><span>órfãs usadas para abastecimento humano</span></div></div>
      <p class="hint">Não entra na receita projetada. Reforça reputação e abre a porta do setor público (municípios, Defesa Civil).</p>`, { icon: 'users' })}

    ${card('Como cada critério da banca é atendido (peso do guia)', `<div class="crit">${CRITERIA.map(([c, w, d, href]) => `<a class="crit-i" href="${href}"><div class="row between"><b>${e(c)}</b><span class="dots" title="peso ${w}/5">${'●'.repeat(w)}${'○'.repeat(5 - w)}</span></div><p>${e(d)}</p><span>Ver ${icon('arrow')}</span></a>`).join('')}</div>
      <p class="hint">${e(E.aviso)} Nenhuma empresa é apresentada como cliente ou parceira.</p>`, { icon: 'check' })}`;
  },
  mount(root, ctx) {
    root.querySelectorAll('[data-cli]').forEach((el) => el.addEventListener('change', () => { BS().cli[el.dataset.cli] = el.value; ctx.rerender(); }));
    const st = BS();
    let t;
    root.querySelectorAll('[data-sim]').forEach((i) => i.addEventListener('input', () => {
      st[i.dataset.sim] = Math.max(0, +i.value || 0); st.focus = `[data-sim="${i.dataset.sim}"]`;
      clearTimeout(t); t = setTimeout(() => ctx.rerender(), 450);
    }));
    if (st.focus) { const f = root.querySelector(st.focus); if (f) { f.focus({ preventScroll: true }); const v = f.value; f.value = ''; f.value = v; } st.focus = null; }
  },
};
