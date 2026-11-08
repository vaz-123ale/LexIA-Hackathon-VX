// Contas-alvo: o que os dados públicos da ANM mostram de cada empresa da lista comercial (sem inferir grupo econômico).
import { api, e, card, icon } from './core.js';

const ATT = { 'Crítica': 'crit', 'Alta': 'alta', 'Moderada': 'mod', 'Baixa': 'baixa' };

export const contasPage = {
  async render() {
    const D = await api('/api/contas-alvo');
    const found = D.items.filter((x) => x.encontrada).length;
    return `<header class="page-head"><div><span class="eyebrow">Gestão & Negócio · regra ${e(D.rule_version)}</span><h2>Contas-alvo</h2>
      <p class="muted">Empresas da lista comercial e o que os cadastros públicos da ANM (SIGBM e SIGMINE) mostram sobre cada uma: barragens, títulos de lavra e os módulos da LexIA que fariam sentido. ${found} de ${D.items.length} encontradas pelo nome.</p></div></header>
    <p class="warn-note">${icon('shield')} ${e(D.aviso)}</p>
    <div class="ct-grid mt12">${D.items.map((x) => `<article class="ct">
        <div class="row between wrap"><h3>${e(x.nome)}</h3><span class="lx-chip ${x.relacao.startsWith('Cliente') ? 'ok' : 'oficial'}">${e(x.relacao)}</span></div>
        ${x.encontrada ? `<small class="muted">Nome no cadastro: ${x.nomes_no_cadastro.map(e).join(' · ')}${x.ufs.length ? ` · ${x.ufs.map(e).join(', ')}` : ''}</small>
          <div class="ct-n"><div><b>${x.barragens}</b><span>barragens (SIGBM)</span></div><div><b>${x.dpa_alta}</b><span>com dano potencial alto</span></div><div><b>${x.titulos_lavra}</b><span>títulos de lavra (SIGMINE)</span></div></div>
          ${x.substancias.length ? `<p class="sm mt8">Substâncias: ${x.substancias.map(e).join(', ')}${x.radiologico ? ' · <span class="lx-chip ia">☢ sinal radiológico</span>' : ''}</p>` : ''}
          ${x.barragens_lista.length ? `<ul>${x.barragens_lista.map((b) => `<li>${e(b.nome)} · ${e(b.municipio)}/${e(b.uf)} · DPA ${e(b.dpa || '—')}${b.atencao ? ` · <span class="lx-chip ${ATT[b.atencao] || 'baixa'}">${e(b.atencao)}</span>` : ''}</li>`).join('')}</ul>` : ''}
          <p class="sm mt8"><b>Módulos sugeridos:</b> ${x.modulos_sugeridos.map(e).join(' · ')}</p>`
        : `<p class="muted sm">Não encontrada pelo nome no SIGBM nem no SIGMINE. Confirmar a razão social e o CNPJ (a empresa pode operar com outro nome jurídico).</p><p class="sm"><b>Módulos sugeridos:</b> ${x.modulos_sugeridos.map(e).join(' · ')}</p>`}
      </article>`).join('')}</div>
    ${card('Como usar na venda', `<ul class="ticks"><li>Os números vêm de cadastro público e servem para preparar a conversa, não para afirmar irregularidade.</li><li>A demonstração usa empresas fictícias (perfis Mineração, Energia e Saneamento no topo). Dados internos de uma conta real só entram com contrato e autorização.</li><li>Para marcar uma conta como cliente, registre o contrato no cadastro (<code>data/contas_alvo.json</code>, campo <code>relacao</code>).</li></ul>`, { icon: 'target' })}`;
  },
};
