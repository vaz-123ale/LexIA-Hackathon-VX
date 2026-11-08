// Triagem (regra triagem-v1): quem recebe algo que não é da sua área repassa para a função certa. Aviso vai para a área; fica na trilha.
import { api, e, icon, toast, state } from './core.js';

export const AREAS = { juridico: 'Jurídico', compliance: 'Compliance', engenharia: 'Engenharia', operacao: 'Operação', seguranca_trabalho: 'Segurança do trabalho (SESMT)',
  meio_ambiente: 'Meio ambiente', radioprotecao: 'Proteção radiológica', financas: 'Gestão / finanças', auditoria: 'Auditoria', regulatorio: 'Curadoria regulatória' };
let CACHE = [];
export async function carregarRepasses() { CACHE = (await api('/api/repasses' + (state.perfil ? '?empresa=' + encodeURIComponent(state.perfil) : '')).catch(() => ({ items: [] }))).items; return CACHE; }

export const repasseHtml = (tipo, ref, titulo) => {
  const ja = CACHE.filter((r) => r.tipo === tipo && r.ref === String(ref));
  return `<div class="tg" data-tg-tipo="${e(tipo)}" data-tg-ref="${e(ref)}" data-tg-titulo="${e(titulo)}">
    ${ja.map((r) => `<span class="tg-feito">${icon('arrow')} Repassado para <b>${e(r.para_rotulo)}</b> por ${e(r.de_nome)}${r.nota ? ` · “${e(r.nota)}”` : ''}</span>`).join('')}
    <button type="button" class="btn sm ghost tg-abrir">${icon('arrow')} Não é da minha área: repassar</button>
    <form class="tg-form" hidden><select aria-label="Área de destino">${Object.entries(AREAS).map(([k, l]) => `<option value="${k}">${e(l)}</option>`).join('')}</select>
      <input maxlength="400" placeholder="Nota para a área (opcional)" aria-label="Nota"><button class="btn sm primary">Repassar</button></form></div>`;
};

export function bindRepasse(root, ctx) {
  root.querySelectorAll('.tg').forEach((box) => {
    box.querySelector('.tg-abrir')?.addEventListener('click', () => { const f = box.querySelector('.tg-form'); f.hidden = !f.hidden; if (!f.hidden) f.querySelector('select').focus(); });
    box.querySelector('.tg-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const f = ev.currentTarget;
      try {
        const r = await api('/api/repassar', { tipo: box.dataset.tgTipo, ref: box.dataset.tgRef, titulo: box.dataset.tgTitulo, para: f.querySelector('select').value, nota: f.querySelector('input').value, empresa: state.perfil });
        toast(`Repassado para ${r.para_rotulo}. A área foi avisada e ficou na trilha.`);
        await carregarRepasses(); ctx.rerender();
      } catch (err) { toast(err.message, 'err'); }
    });
  });
}
