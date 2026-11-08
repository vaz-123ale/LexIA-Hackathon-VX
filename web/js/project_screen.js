import { state, api, e, fmtDate, toast } from './core.js';
const TOPICS = [['nr20','Combustíveis, tanques e geradores'],['anm','Barragens de mineração'],['anp_cp21','Atividade ANP / consulta pública'],['ansn','Instalação radiativa / CNEN / ANSN']];

export function projectForm() {
  return `<section class="card project-screen"><header class="card-h"><h3>Projeto → normas candidatas</h3><span class="assistant-mode">Triagem local · sem IA generativa</span></header><p>Envie um projeto público ou sintético. Confira os trechos e confirme as atividades antes de consultar o corpus de dispositivos. O nome da empresa serve apenas para identificar o projeto.</p><form id="project-screen-form"><div class="form-grid"><label class="field"><span>Empresa / projeto (rótulo opcional)</span><input name="company" maxlength="160" placeholder="Projeto demonstrativo"></label><label class="field"><span>PDF textual · até 1 MB e 40 páginas</span><input name="file" type="file" accept="application/pdf,.pdf"></label><label class="field"><span>UF</span><input name="uf" maxlength="2" placeholder="MG"></label><label class="field"><span>Município</span><input name="municipio" maxlength="100"></label></div><label class="field mt12"><span>Ou descreva o projeto (mínimo 40 caracteres)</span><textarea name="description" rows="3" maxlength="60000" placeholder="Descreva atividade, instalações, fase do projeto e localização. Não inclua informações sensíveis."></textarea></label><label class="check mt12"><input name="authorized" type="checkbox" required>Tenho autorização para processar este documento público ou sintético. Nesta demo não envio documentos internos, confidenciais ou dados sensíveis.</label><p class="hint">O PDF fica em memória durante a triagem e não é gravado nem enviado ao provedor de IA. Desenhos, tabelas complexas e digitalizações exigem revisão própria.</p><button class="btn primary mt12" id="project-preview">1 · Ler projeto e apontar menções</button><div id="project-scope" hidden><h4>2 · Confirme as atividades do projeto</h4><p class="hint">Uma palavra no documento pode estar negada ou ser apenas hipótese. Marque somente atividades confirmadas por você.</p>${TOPICS.map(([id,l])=>`<label class="check"><input type="checkbox" name="topic" value="${id}">${e(l)}</label>`).join('')}<button type="button" class="btn primary mt12" id="project-confirm">Consultar dispositivos candidatos</button></div></form><div id="project-result" aria-live="polite"></div><div id="project-error" role="alert"></div></section>`;
}

export function mountProject(root, ctx) {
  const form = root.querySelector('#project-screen-form');
  if (!form) return;
  const result = root.querySelector('#project-result'), error = root.querySelector('#project-error');
  let original = null, latest = null, busy = false;
  const clear = () => { original = null; latest=null; result.innerHTML = ''; root.querySelector('#project-scope').hidden = true; form.querySelectorAll('[name="topic"]').forEach(x=>x.checked=false); };
  const interview=document.createElement('div');interview.id='project-questions';root.querySelector('#project-confirm').before(interview);
  form.addEventListener('input', ev => { latest=null; if (ev.target.name !== 'topic' && !ev.target.matches('[data-project-fact]')) { clear();interview.innerHTML=''; } else result.innerHTML=''; });
  form.addEventListener('change', ev => { if (ev.target.name === 'file') clear(); });
  async function run(confirmScope) {
    if (busy || !form.reportValidity()) return;
    if (confirmScope && !original) return;
    busy = true; error.textContent = ''; form.setAttribute('aria-busy','true');
    form.querySelectorAll('input,select,textarea,button').forEach(b=>b.disabled=true);
    try {
      let payload;
      if (!confirmScope) {
        const f = form.elements.file.files[0];
        payload = {company:form.elements.company.value, uf:form.elements.uf.value, municipio:form.elements.municipio.value, description:form.elements.description.value, authorized:form.elements.authorized.checked, as_of:state.asOf};
        if (f) {
          if (f.size > 1048576) throw new Error('PDF excede 1 MB. Use um recorte textual do projeto.');
          const bytes = new Uint8Array(await f.arrayBuffer()); let binary='';
          for (let i=0;i<bytes.length;i+=8192) binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
          payload.pdf_base64=btoa(binary); delete payload.description;
        }
      } else payload = {...original, scope_confirmed:true, topics:[...form.querySelectorAll('[name="topic"]:checked')].map(x=>x.value),facts:Object.fromEntries([...interview.querySelectorAll('[data-project-fact]')].map(x=>[x.dataset.projectFact,x.value]))};
      const r = await api('/api/projects/screen',payload);
      latest=confirmScope ? payload : null;
      interview.innerHTML=`<h4>Perguntas de enquadramento · respostas humanas</h4><p class="hint">Responda e consulte novamente para atualizar o resultado. Não sei mantém a lacuna; resposta negativa não dispensa automaticamente uma norma.</p>${r.questions.map(q=>`<label class="field"><span>${e(q.question)}</span><select data-project-fact="${e(q.id)}" name="fact-${e(q.id)}">${[['unknown','Não sei / conferir'],['yes','Sim'],['no','Não']].map(([v,l])=>`<option value="${v}" ${q.answer===v?'selected':''}>${l}</option>`).join('')}</select></label>`).join('')}`;
      if (!confirmScope) { original=payload; root.querySelector('#project-scope').hidden=false; }
      result.innerHTML = `<p class="hint">${e(r.privacy)}<br>SHA-256: <code>${e(r.sha256)}</code> · data-base ${fmtDate(r.as_of)}</p><p class="warn-note">${e(r.disclaimer)}</p><h4>Menções localizadas · não confirmam atividade</h4>${r.mentions.map(m=>`<blockquote><b>${e(m.label)} · ${m.page ? 'página '+m.page : 'descrição'}</b><p>${e(m.excerpt)}</p></blockquote>`).join('') || '<p>Não foram identificados temas cobertos. Confirme o escopo ou encaminhe à curadoria.</p>'}${confirmScope ? `<h3>${r.candidates.length} dispositivo(s) candidato(s) à revisão</h3>${r.candidates.map(p=>`<article class="agenda-item"><h4>${e(p.document)} · ${e(p.provision)}</h4><p><b>${e(p.status_at_date)}</b> · ${e(p.version)} · ${e(p.jurisdiction)}</p><p>${e(p.summary)}</p><dl class="kv"><dt>Início de vigência</dt><dd>${fmtDate(p.valid_from) || 'A conferir'}</dd><dt>Fim</dt><dd>${fmtDate(p.valid_to) || 'Não informado'}</dd><dt>Verificação do dossiê</dt><dd>${e(p.verification || 'A conferir')} · não comprova vigência atual</dd></dl><p><b>Condições:</b> ${e(p.conditions.join('; ') || 'A conferir')}</p><p><b>Exceções:</b> ${e(p.exceptions.join('; ') || 'Não curadas; conferir no original')}</p><p>${p.sources.map(s=>`<a href="${e(s.url)}" target="_blank" rel="noopener noreferrer">${e(s.id)} · ${e(s.title)} ↗</a>`).join('<br>')}</p><p class="hint">${e(p.text_status || 'Texto integral não disponibilizado.')}</p></article>`).join('')}` : ''}<h4>Dados e cobertura faltantes</h4><ul>${r.missing.map(m=>`<li>${e(m)}</li>`).join('')}</ul>${confirmScope && r.candidates.length ? `<p>Confira o cenário no laboratório para analisar ativos e submeter a revisão.</p>${r.topics.map(s=>`<button type="button" class="btn sm" data-project-scenario="${e(s)}">Abrir ${e(TOPICS.find(x=>x[0]===s)?.[1] || s)}</button>`).join(' ')}` : ''}`;
      result.querySelectorAll('[data-project-scenario]').forEach(b=>b.addEventListener('click',()=>{ state.scenario=b.dataset.projectScenario; state.lab.sel=null; ctx.rerender(); }));
      result.insertAdjacentHTML('beforeend',`<details class="mt12"><summary>O que ficou fora do filtro e por quê (${r.excluded.length})</summary><ul>${r.excluded.map(x=>`<li><b>${e(x.label)}</b>: ${e(x.reason)}</li>`).join('')}</ul><p class="hint">Você pode alterar o escopo e consultar novamente. Este recorte não cobre todo o universo regulatório.</p></details>${r.conflicts.length ? `<p class="warn-note">Respostas negativas em temas mencionados: ${e(r.conflicts.map(x=>x.question).join('; '))}. Confira negações e hipóteses antes de decidir.</p>` : ''}${confirmScope ? `<label class="check mt12"><input type="checkbox" id="project-save-consent">Autorizo salvar na minha conta este resultado, fatos e trechos. O PDF integral não será armazenado.</label><button type="button" class="btn primary mt12" id="project-save">Salvar versão do projeto e preparar dossiê</button>` : ''}`);
      result.querySelector('#project-save')?.addEventListener('click',async ev=>{
        const b=ev.currentTarget;
        if(!latest || !result.querySelector('#project-save-consent').checked){toast('Aceite salvar o resultado e confira se a consulta está atualizada.','err');return;}
        b.disabled=true;
        try{const saved=await api('/api/workbench/save',{...latest,consent_save:true});state.workProject=saved.id;toast('Versão salva nesta conta.');result.insertAdjacentHTML('beforeend',`<p><a class="btn" href="/api/workbench/dossier?id=${encodeURIComponent(saved.id)}">Exportar dossiê</a> <button class="btn" data-go-tab="decision:workbench">Comparar versões e revisar condicionantes</button></p>`);}catch(err){toast(err.message,'err');b.disabled=false;}
      });
    } catch(err) { error.textContent=err.message; }
    finally { busy=false; form.removeAttribute('aria-busy'); form.querySelectorAll('input,select,textarea,button').forEach(b=>b.disabled=false); }
  }
  form.addEventListener('submit',ev=>{ev.preventDefault();run(false);});
  root.querySelector('#project-confirm').addEventListener('click',()=>run(true));
}
