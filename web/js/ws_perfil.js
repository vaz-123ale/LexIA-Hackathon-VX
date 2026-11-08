// Meu perfil: nome, foto e informações essenciais da conta. E-mail, organização, CNPJ e papel só mudam com a gestão/curadoria.
import { state, api, e, card, icon, toast, currentUser, refreshMe } from './core.js';

const FUNC = { juridico: 'Jurídico', compliance: 'Compliance', engenharia: 'Engenharia', operacao: 'Operação', financas: 'Finanças / gestão', auditoria: 'Auditoria',
  curadoria: 'Curadoria', seguranca_trabalho: 'Segurança do trabalho (SESMT)', radioprotecao: 'Proteção radiológica', meio_ambiente: 'Meio ambiente', regulatorio: 'Regulatório', cidadao: 'Cidadão' };
const UFS = 'AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO'.split(' ');
export const initials = (n) => (n || '?').split(' ').map((p) => p[0]).filter((c) => /[A-ZÁ-Ú]/i.test(c)).slice(0, 2).join('').toUpperCase();

function resize(file) {
  return new Promise((res, rej) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      const s = Math.min(img.width, img.height), c = document.createElement('canvas'); c.width = c.height = 160;
      c.getContext('2d').drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, 160, 160);
      URL.revokeObjectURL(url); res(c.toDataURL('image/jpeg', 0.85));
    };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('Não consegui ler a imagem.')); };
    img.src = url;
  });
}

export const perfilPage = {
  citizen: true, both: true, title: 'Meu perfil',
  async render() {
    const u = currentUser();
    const st = (state.pf = state.pf || { avatar: undefined });
    const av = st.avatar !== undefined ? st.avatar : u.avatar;
    const emp = u.kind === 'empresa';
    return `<header class="page-head"><div><span class="eyebrow">Conta</span><h2>Meu perfil</h2><p class="muted">Seu nome e sua foto aparecem no topo da plataforma. Os dados de acesso e da organização são definidos pela gestão da conta.</p></div></header>
    <div class="grid-6-6">
      ${card('Foto e dados pessoais', `<form id="pf-form" class="pf-form">
        <div class="pf-photo"><div class="pf-av">${av ? `<img src="${e(av)}" alt="Sua foto">` : `<span>${e(initials(u.name))}</span>`}</div>
          <div><label class="btn sm">${icon('user')} Escolher foto<input type="file" id="pf-file" accept="image/jpeg,image/png,image/webp" hidden></label>
          ${av ? `<button type="button" class="btn sm ghost" id="pf-rm">Remover foto</button>` : ''}<p class="hint">JPG, PNG ou WEBP. A foto é recortada em quadrado e reduzida no seu navegador antes de enviar.</p></div></div>
        <label class="field"><span>Nome</span><input id="pf-name" value="${e(u.name)}" maxlength="80" required></label>
        ${emp ? `<label class="field"><span>Cargo</span><input id="pf-cargo" value="${e(u.cargo || '')}" maxlength="60" placeholder="Ex.: Analista de compliance"></label>` : ''}
        <label class="field"><span>Telefone (opcional)</span><input id="pf-phone" value="${e(u.phone || '')}" maxlength="20" inputmode="tel" placeholder="(31) 99999-0000"></label>
        <div class="row gap wrap"><label class="field" style="flex:0 0 110px"><span>UF</span><select id="pf-uf"><option value="">—</option>${UFS.map((x) => `<option ${u.uf === x ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
          <label class="field" style="flex:1"><span>Município</span><input id="pf-mun" value="${e(u.municipio || '')}" maxlength="60"></label></div>
        <button class="btn primary mt8">${icon('check')} Salvar perfil</button></form>`, { icon: 'user' })}
      ${card('Conta', `<dl class="kv"><dt>E-mail</dt><dd>${e(u.email || '—')}</dd><dt>Tipo de conta</dt><dd>${emp ? 'Empresa' : 'Cidadão (LexIA Cidadão)'}</dd>
        ${emp ? `<dt>Organização</dt><dd>${e(u.org_name || '—')}</dd><dt>CNPJ</dt><dd>${e(u.cnpj ? String(u.cnpj).replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5') : '—')}</dd>
        <dt>Função</dt><dd>${e(FUNC[u.function] || u.function || '—')}</dd><dt>Papel na plataforma</dt><dd>${e(u.role || '—')}</dd>` : ''}
        <dt>Conta criada</dt><dd>${e((u.created_at || '').slice(0, 10) || '—')}</dd></dl>
        <p class="hint">${emp ? 'A função define quais alertas chegam até você. Para mudar e-mail, organização ou função, fale com a gestão da conta.' : 'Sua localização em tempo real nunca é guardada; aqui fica só a cidade que você escolher.'}</p>
        ${u.is_demo ? '<p class="warn-note">Conta de demonstração: outras pessoas usam este mesmo acesso.</p>' : ''}`, { icon: 'shield' })}
    </div>`;
  },
  mount(root, ctx) {
    const st = state.pf;
    root.querySelector('#pf-file')?.addEventListener('change', async (ev) => {
      const f = ev.target.files[0]; if (!f) return;
      if (f.size > 15 * 1024 * 1024) return toast('Imagem acima de 15 MB.', 'err');
      try { st.avatar = await resize(f); ctx.rerender(); } catch (err) { toast(err.message, 'err'); }
    });
    root.querySelector('#pf-rm')?.addEventListener('click', () => { st.avatar = null; ctx.rerender(); });
    root.querySelector('#pf-form')?.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const v = (id) => root.querySelector(id)?.value ?? '';
      const body = { name: v('#pf-name'), cargo: v('#pf-cargo'), phone: v('#pf-phone'), uf: v('#pf-uf'), municipio: v('#pf-mun') };
      if (st.avatar !== undefined) body.avatar = st.avatar || '';
      try { await api('/api/account/profile', body); st.avatar = undefined; await refreshMe(); toast('Perfil salvo.'); ctx.rerender(); } catch (err) { toast(err.message, 'err'); }
    });
  },
};
