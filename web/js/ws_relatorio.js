// Relatório da empresa (dentro da conta): cada frente gera e baixa o PRÓPRIO relatório — operação, alertas com base legal,
// obrigações confirmadas, denúncias recebidas e o que os cadastros públicos mostram sobre o CNPJ. Imprimir/salvar em PDF.
import { state, api, e, icon, fmtDate } from './core.js';

const NIV = { 'Crítico': 'crit', 'Alto': 'alta', 'Médio': 'mod', 'Baixo': 'baixa' };
const ST = { critico: ['Crítico', 'crit'], pendencia: ['Pendência', 'mod'], normal: ['Normal', 'ok'] };
const DST = { RECEBIDA: 'recebidas', EM_APURACAO: 'em apuração', RESPONDIDA: 'respondidas' };
const tabela = (cols, linhas) => `<table class="table compact"><thead><tr>${cols.map(([h]) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${linhas.map((x) => `<tr>${cols.map(([, f]) => `<td>${f(x)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
const baseTxt = (b) => (Array.isArray(b) ? b.map((x) => x?.ref || x).join('; ') : (b?.ref || b || '—'));

export const relatorioPage = {
  title: 'Relatório da empresa',
  async render() {
    const R = await api('/api/relatorio-empresa' + (state.perfil ? '?empresa=' + encodeURIComponent(state.perfil) : '')).catch((err) => ({ error: err.message }));
    if (R.error) return `<div class="card"><h3>Relatório da empresa</h3><p class="warn-note">${e(R.error)}</p></div>`;
    const P = R.dados_publicos;
    const n = (k) => R.status[k] || 0;
    return `<header class="page-head no-print"><div><span class="eyebrow">Relatório · ${e(R.setor)}</span><h2>Relatório da empresa</h2>
      <p class="muted">O retrato da sua frente na LexIA para levar à diretoria ou à auditoria: operação, alertas com base legal, obrigações confirmadas e denúncias. Só a sua empresa vê e baixa este relatório.</p></div>
      <button class="btn primary lg" id="rel-print" type="button">${icon('doc')} Baixar PDF</button></header>
    <article class="rl-doc rel-emp">
      <div class="rel-capa"><img src="/img/brand/logo-lexia-v6.png" alt="LexIA"><div><span class="eyebrow">Relatório regulatório · ${e(fmtDate(R.gerado_em))} · regra ${e(R.rule_version)}</span><h2>${e(R.empresa)}</h2>
        <p class="muted">${e(R.setor)} · reguladores: ${e(R.reguladores.join(', '))}${R.cnpj_raiz ? ` · CNPJ raiz ${e(R.cnpj_raiz)}` : ''}</p></div></div>
      ${R.ficticia ? '<p class="warn-note">Empresa e ativos fictícios de demonstração. Com um cliente real, este relatório usa os documentos, sensores e cadastros dele.</p>' : ''}
      <div class="tp-kpis rl-kpis"><div><b>${R.ativos.length}</b><span>ativos acompanhados</span></div><div class="c"><b>${n('critico')}</b><span>em situação crítica</span></div>
        <div class="a"><b>${n('pendencia')}</b><span>com pendência</span></div><div><b>${R.alertas.length}</b><span>alertas com base legal</span></div><div><b>${R.denuncias.recebidas}</b><span>denúncias recebidas</span></div></div>
      <h3>1. Operação</h3>${tabela([['Ativo', (a) => `<b>${e(a.nome)}</b>`], ['Tipo', (a) => e(a.tipo)], ['Local', (a) => e(a.municipio || '—')], ['Situação', (a) => `<span class="lx-chip ${ST[a.status]?.[1] || ''}">${e(ST[a.status]?.[0] || a.status)}</span>`], ['Ocorrências', (a) => a.ocorrencias]], R.ativos)}
      <h3>2. Alertas e prazos</h3>${R.alertas.length ? tabela([['Nível', (a) => `<span class="lx-chip ${NIV[a.nivel] || ''}">${e(a.nivel)}</span>`], ['Alerta', (a) => `<b>${e(a.titulo)}</b><br><small class="muted">${e(a.ativo)}</small>`], ['Prazo', (a) => e(a.prazo ? fmtDate(a.prazo) : '—')], ['Base legal', (a) => `<small>${e(baseTxt(a.base))}</small>`], ['Responde', (a) => e(a.responsavel || '—')], ['Situação', (a) => e(a.status)]], R.alertas) : '<p class="muted">Nenhum alerta aberto.</p>'}
      <h3>3. Obrigações confirmadas (Norma → obrigação)</h3>${R.obrigacoes.length ? tabela([['Obrigação', (o) => e(o.obrigacao.slice(0, 160))], ['Prazo', (o) => e(o.prazo || '—')], ['Responde', (o) => e(o.papel || '—')]], R.obrigacoes) : '<p class="muted">Nenhuma obrigação confirmada ainda. Use Conformidade → Norma → obrigação.</p>'}
      <h3>4. Denúncias recebidas pela LexIA Cidadão</h3><p>${R.denuncias.recebidas ? Object.entries(R.denuncias.por_situacao).map(([k, v]) => `<b>${v}</b> ${DST[k] || k}`).join(' · ') : 'Nenhuma denúncia recebida.'}</p>
      <h3>5. O que os cadastros públicos mostram</h3>${P ? `<p>${e(P.empresa.join(' · '))}: <b>${P.resumo.barragens}</b> barragens (ANM/SIGBM), <b>${P.resumo.titulos}</b> títulos de lavra (SIGMINE), <b>${P.resumo.usinas}</b> usinas (ANEEL), <b>${P.resumo.snisb}</b> barragens de energia/abastecimento (ANA/SNISB).</p><ul class="ticks">${P.destaques.map((d) => `<li>${e(d)}</li>`).join('')}</ul>`
        : `<p class="muted">Nenhum registro encontrado pelo CNPJ ${e(R.cnpj_raiz || '')} nos cadastros públicos (ANM, ANA, ANEEL)${R.ficticia ? ', como esperado para uma empresa fictícia' : ''}.</p>`}
      <p class="hint">${e(R.aviso)}</p>
    </article>`;
  },
  mount(root) {
    root.querySelector('#rel-print')?.addEventListener('click', () => window.print());
  },
};
