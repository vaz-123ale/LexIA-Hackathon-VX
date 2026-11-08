// Norma → obrigação: regras (e IA, se pedida) propõem; o verificador exige trecho literal; uma pessoa confirma ou descarta com motivo.
import { state, api, e, card, icon, toast, fmtDateTime } from './core.js';

const EXEMPLOS = [
  ['Barragens (exemplo ilustrativo)', 'Art. 21. O empreendedor deverá enviar, por meio do SIGBM, o Extrato de Inspeção Regular no prazo de 15 (quinze) dias após a realização da inspeção. Para as barragens com Dano Potencial Associado alto, a Declaração de Condição de Estabilidade deverá ser apresentada semestralmente. Caso seja identificada anomalia, o responsável técnico deverá comunicar a ANM imediatamente.'],
  ['Licença ambiental (exemplo ilustrativo)', 'Condicionante 4. O empreendimento deverá apresentar ao órgão ambiental, anualmente, relatório de monitoramento da qualidade dos efluentes. Sempre que houver alteração no processo produtivo, o titular deverá protocolar comunicação no prazo de 30 (trinta) dias.'],
  ['NR-1 riscos psicossociais (exemplo ilustrativo)', 'A organização deverá incluir no Programa de Gerenciamento de Riscos a identificação e a avaliação dos fatores de risco psicossociais relacionados ao trabalho. O inventário de riscos deverá ser revisado a cada 2 (dois) anos. Sempre que houver acidente ou doença relacionada ao trabalho, o empregador deverá revisar as medidas de prevenção imediatamente.'],
  ['Água potável (exemplo ilustrativo)', 'O prestador do serviço de abastecimento deverá manter plano de amostragem da qualidade da água para consumo humano e enviar os resultados à vigilância sanitária mensalmente. Quando houver resultado fora do padrão de potabilidade, o responsável deverá comunicar a autoridade de saúde imediatamente.'],
];
const ES = () => (state.ex = state.ex || { texto: EXEMPLOS[0][1], norma: '', ia: false, r: null, feitas: {} });

export const extratorPage = {
  title: 'Norma → obrigação',
  async render() {
    const st = ES();
    const H = await api('/api/obrigacoes').catch(() => ({ items: [] }));
    const r = st.r;
    return `<header class="page-head"><div><span class="eyebrow">Conformidade · regra extrator-v1</span><h2>Norma → obrigação</h2>
      <p class="muted">Cole o texto de um dispositivo. A LexIA propõe as obrigações (o que fazer, prazo, quem responde, evidência e condição), cada uma presa a um trecho literal do texto. Você confirma ou descarta.</p></div></header>
    <div class="grid-6-6">
      ${card('1 · Texto do dispositivo', `<div class="row gap wrap">${EXEMPLOS.map(([l], i) => `<button class="chip-btn" data-ex="${i}">${e(l)}</button>`).join('')}</div>
        <label class="field mt8"><span>Norma e dispositivo (para a trilha)</span><input id="ex-norma" value="${e(st.norma)}" placeholder="Ex.: Res. ANM 95/2022, art. 21"></label>
        <label class="field mt8"><span>Texto</span><textarea id="ex-texto" rows="9">${e(st.texto)}</textarea></label>
        <label class="chip-btn mt8"><input type="checkbox" id="ex-ia" ${st.ia ? 'checked' : ''}> Pedir também à IA generativa (as regras rodam sempre primeiro)</label>
        <button class="btn primary mt12" id="ex-go">${icon('spark')} Extrair obrigações</button>
        <p class="hint">Exemplos ilustrativos escritos pela equipe (não são texto oficial). Para uso real, cole o texto da publicação oficial.</p>`, { icon: 'doc' })}
      ${card('2 · Obrigações propostas', !r ? '<div class="empty"><p>Escolha um exemplo ou cole um texto e clique em “Extrair obrigações”.</p></div>'
        : `<div class="row gap wrap"><span class="lx-chip ${r.motor.includes('IA') ? 'ia' : 'ok'}">${e(r.motor)}</span><span class="muted sm">${r.obrigacoes.length} aceita(s) pelo verificador · ${r.recusadas.length} recusada(s)</span></div>
        ${r.obrigacoes.map((o) => { const f = st.feitas[o.id]; return `<article class="ex-ob">
          <div class="row between wrap"><b>${e(o.obrigacao.length > 160 ? o.obrigacao.slice(0, 159) + '…' : o.obrigacao)}</b><span class="lx-chip ${o.origem === 'ia' ? 'ia' : 'oficial'}">${o.origem === 'ia' ? 'IA' : 'Regra'}</span></div>
          <dl class="kv"><dt>Prazo</dt><dd>${o.prazo ? e(o.prazo) : '<span class="lx-chip alta">sem prazo no texto</span>'}</dd><dt>Quem responde</dt><dd>${e(o.papel_rotulo)}</dd>
          <dt>Evidência</dt><dd>${e(o.evidencia)}</dd><dt>Condição</dt><dd>${o.condicao ? e(o.condicao) : '<span class="muted">aplica-se sem condição no texto</span>'}</dd></dl>
          <p class="ex-trecho">“${e(o.trecho)}”</p>
          ${f ? `<p class="cp-act">✓ ${f === 'CONFIRMADA' ? 'Confirmada por você — entrou na lista de obrigações com trilha.' : 'Descartada com motivo registrado.'}</p>`
            : `<div class="row gap wrap"><button class="btn sm primary" data-ok="${o.id}">${icon('check')} Confirmar obrigação</button><button class="btn sm" data-no="${o.id}">Descartar</button></div>`}</article>`; }).join('') || '<p class="muted">Nenhuma obrigação encontrada com segurança. Ative a IA ou revise o texto.</p>'}
        ${r.recusadas.length ? `<details class="sm mt8"><summary>${r.recusadas.length} proposta(s) recusada(s) pelo verificador</summary><ul>${r.recusadas.map((x) => `<li>${e((x.obrigacao || '').slice(0, 90))} — <b>${e(x.motivo)}</b></li>`).join('')}</ul></details>` : ''}
        <p class="hint">${e(r.aviso)}</p>`, { icon: 'check' })}
    </div>
    ${H.items.length ? card('Obrigações já decididas', `<table class="table compact"><thead><tr><th>Quando</th><th>Obrigação</th><th>Prazo</th><th>Responde</th><th>Decisão</th><th>Por</th></tr></thead>
      <tbody>${H.items.map((x) => `<tr><td>${fmtDateTime(x.created_at)}</td><td>${e((x.obrigacao || '').slice(0, 90))}</td><td>${e(x.prazo || '—')}</td><td>${e(x.papel)}</td><td><span class="lx-chip ${x.state === 'CONFIRMADA' ? 'ok' : 'baixa'}">${e(x.state)}</span>${x.motivo ? `<small class="muted"> ${e(x.motivo)}</small>` : ''}</td><td>${e(x.actor)}</td></tr>`).join('')}</tbody></table>`, { icon: 'book' }) : ''}`;
  },
  mount(root, ctx) {
    const st = ES();
    const sync = () => { st.texto = root.querySelector('#ex-texto').value; st.norma = root.querySelector('#ex-norma').value; st.ia = root.querySelector('#ex-ia').checked; };
    root.querySelectorAll('[data-ex]').forEach((b) => b.addEventListener('click', () => { st.texto = EXEMPLOS[+b.dataset.ex][1]; st.r = null; st.feitas = {}; ctx.rerender(); }));
    root.querySelector('#ex-go')?.addEventListener('click', async (ev) => {
      sync(); ev.target.disabled = true; ev.target.textContent = 'Extraindo…';
      try { st.r = await api('/api/obrigacoes/extrair', { texto: st.texto, norma: st.norma, ia: st.ia }); st.feitas = {}; } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    });
    const decide = async (id, decisao, motivo = '') => {
      const item = st.r.obrigacoes.find((o) => o.id === id);
      try { await api('/api/obrigacoes/decidir', { item, fonte: { norma: st.norma }, decisao, motivo }); st.feitas[id] = decisao; toast(decisao === 'CONFIRMADA' ? 'Obrigação confirmada.' : 'Descartada.'); } catch (err) { toast(err.message, 'err'); }
      ctx.rerender();
    };
    root.querySelectorAll('[data-ok]').forEach((b) => b.addEventListener('click', () => decide(+b.dataset.ok, 'CONFIRMADA')));
    root.querySelectorAll('[data-no]').forEach((b) => b.addEventListener('click', () => { const m = prompt('Por que descartar? (fica na trilha)'); if (m) decide(+b.dataset.no, 'DESCARTADA', m); }));
  },
};
