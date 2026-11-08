// E2E do Radar de abandono, Central de IA e mini-chat (CDP, sem dependências). Uso: node scripts/e2e_radar_ia.mjs <pasta-saida>
// Requer o servidor rodando em http://127.0.0.1:8765 e o Chrome instalado (caminho Windows abaixo).
import { resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
const OUT = resolve(process.argv[2] || 'e2e_out'); mkdirSync(OUT, { recursive: true });
const CH = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8765';
const proc = spawn(CH, ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=9336', `--user-data-dir=${OUT}/prof`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map(); const errors = []; const log = [];
async function connect() { for (let i = 0; i < 40; i++) { try { const l = await (await fetch('http://127.0.0.1:9336/json')).json(); const t = l.find((x) => x.type === 'page'); if (t) return t.webSocketDebuggerUrl; } catch {} await sleep(250); } throw new Error('chrome não respondeu'); }
const send = (method, params = {}) => new Promise((res, reject) => { const i = ++id; const timeout = setTimeout(() => { pending.delete(i); reject(new Error('CDP sem resposta: ' + method)); }, 15000); pending.set(i, (value) => { clearTimeout(timeout); res(value); }); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text); return r.result?.value; };
const shot = async (name) => { const r = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(`${OUT}/${name}.png`, Buffer.from(r.data, 'base64')); log.push('shot ' + name); };
const size = (w, h) => send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 });
const go = async (hash, wait = 2000) => { await ev(`location.hash='${hash}'`); await sleep(wait); };
const waitFor = async (sel, ms = 9000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(`!!document.querySelector(${JSON.stringify(sel)})`)) return true; await sleep(150); } throw new Error('timeout ' + sel); };
const click = (sel) => ev(`(()=>{const el=document.querySelector(${JSON.stringify(sel)}); if(!el) throw new Error('não achei ' + ${JSON.stringify(sel)}); el.click(); return true})()`);
const setVal = (sel, v, evt = 'input') => ev(`(()=>{const el=document.querySelector(${JSON.stringify(sel)}); el.value=${JSON.stringify(v)}; el.dispatchEvent(new Event('${evt}',{bubbles:true})); return true})()`);
const text = (sel = '#content') => ev(`(document.querySelector(${JSON.stringify(sel)})?.innerText || '').toLowerCase()`);
const check = (cond, msg) => { log.push((cond ? 'OK   ' : 'FALHA ') + msg); if (!cond) errors.push(msg); };
const kpi = async (n) => Number(await ev(`document.querySelectorAll('.kpi .kpi-v')[${n}]?.textContent`));
const noHScroll = async (label) => { const [sw, cw] = await ev('[document.documentElement.scrollWidth, document.documentElement.clientWidth]'); check(sw <= cw + 1, `${label}: sem rolagem horizontal (${sw}/${cw})`); };

try {
  ws = new WebSocket(await connect()); await new Promise((r) => ws.addEventListener('open', r));
  ws.addEventListener('message', (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d.result || {}); pending.delete(d.id); }
    if (d.method === 'Runtime.exceptionThrown') errors.push('JS: ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text).split('\n')[0]);
    if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error' && !/favicon/.test(d.params.entry.text)) errors.push('console: ' + d.params.entry.text); });
  await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable'); await size(1440, 900);
  await send('Page.navigate', { url: BASE + '/#/entrar' }); await sleep(3000);
  await click('[data-at="empresa"]'); await sleep(500); await click('[data-demo="ana@demo.lexia.app"]'); await sleep(3500);
  await send('Page.navigate', { url: BASE + '/#/radar' }); await sleep(3500);
  check(await ev("[...document.querySelectorAll('.nav-item')].some((a)=>a.textContent.includes('Operação'))"), 'Menu tem a área Operação & Ativos (Barragens fica dentro dela)');
  check(await ev("!!document.querySelector('.nav-item[href=\"#/ia\"]')"), 'Menu tem Central de IA');
  check(await ev("!!document.querySelector('.tb-ia')") && !(await ev("!!document.querySelector('.assistant-top')")), 'Topo tem só o botão pequeno da IA');
  check(!(await ev("!!document.getElementById('assistant-rail')")), 'Trilho lateral antigo removido');
  check(await ev("!!document.querySelector('.bubble .bub-btn')"), 'Bolinha do mini-chat presente');
  check((await text()).includes('radar de abandono'), 'Página do radar renderizada');
  check(await ev("document.querySelectorAll('.rd-pt').length") > 100, 'Mapa com pontos de barragens');
  await shot('r01_radar'); await noHScroll('radar 1440');
  await setVal('#ai-q', 'inativas sem projeto em MG'); await ev("document.querySelector('#ai-bar').requestSubmit()"); await waitFor('.chip-f', 45000); await sleep(1500);
  check((await text()).includes('situação: inativa') && (await text()).includes('uf: mg'), 'Consulta em português vira filtros visíveis');
  await shot('r02_filtro');
  await click('.rd-row'); await sleep(2500); await waitFor('#ficha');
  check((await text('#ficha')).includes('sinais'), 'Ficha abre com sinais');
  check(await ev("document.querySelectorAll('#ficha .law').length") > 0, 'Sinais citam artigos da Lei 12.334');
  check(await ev("!!document.querySelector('#ficha .ml-box')"), 'Ficha mostra a leitura do modelo de IA');
  check(await ev("!!document.querySelector('#ficha .sat img')"), 'Ficha mostra imagem de satélite do ponto');
  await shot('r03_ficha_sinais');
  for (const [t, name, must] of [['resp', 'r04_responsaveis', 'órgão fiscalizador'], ['plano', 'r05_plano', 'viabilidade'], ['repr', 'r06_representacao', 'rascunho'], ['anom', 'r07_inconsistencias', '']]) {
    await click(`[data-ftab="${t}"]`); await sleep(2000);
    if (must) check((await text('#ficha')).includes(must), `Aba ${t} mostra “${must}”`);
    await ev("document.getElementById('ficha').scrollIntoView()"); await shot(name);
  }
  await click('[data-ftab="plano"]'); await sleep(1800);
  await ev(`(()=>{const f=document.querySelector('.rd-stepf'); f.querySelector('select').value='feito'; f.querySelector('input').value='Conferido no snapshot SIGBM do dia'; f.requestSubmit(); return 1})()`); await sleep(2500);
  check((await text('#ficha')).includes('conferido no snapshot'), 'Etapa do plano registrada com evidência');
  await click('[data-ftab="repr"]'); await sleep(2000); await click('#draft-save'); await sleep(2000);
  check((await text('#ficha')).includes('rascunho') && await ev("!!document.querySelector('.rd-dr')"), 'Rascunho salvo para revisão');
  check(await ev("!!document.querySelector('.rd-dec')"), 'Jurídico vê botões de decisão (quatro olhos aplicado no servidor)');
  await click('#ficha-close'); await sleep(1800); await click('#clear-f'); await sleep(1500); await click('#ml-toggle'); await sleep(2500);
  check((await text()).includes('risco oculto (modelo): sim') && await ev("document.querySelectorAll('.ml-badge').length") > 0, 'Filtro Risco oculto (IA) funciona'); await shot('r02b_risco_oculto');
  await click('#clear-f'); await sleep(2000);
  await ev("document.querySelector('.rd-uf[data-uf=\"MG\"]').dispatchEvent(new MouseEvent('click',{bubbles:true}))"); await sleep(2500);
  check((await text()).includes('uf: mg'), 'Clique no estado filtra o radar');
  await click('#clear-f'); await sleep(1500);
  await click('[data-ptab="panorama"]'); await sleep(2200); check((await text()).includes('92%'), 'Panorama do setor'); await shot('r08_panorama');
  await click('[data-ptab="como"]'); await sleep(1500); await shot('r09_como');
  await click('.bub-btn'); await sleep(600); await click('.bub-sug [data-s]'); await sleep(2500);
  check(await ev("document.querySelectorAll('.bub-msgs .cm').length") >= 2, 'Mini-chat responde'); await shot('r10_bolinha');
  await go('#/ia', 3000); check((await text()).includes('central de ia') && !(await ev("!!document.querySelector('.bubble')")), 'Página IA (bolinha oculta nela)'); await shot('r11_ia_chat');
  await click('[data-iatab="risco"]'); await sleep(2500); check((await text()).includes('auc na validação cruzada'), 'IA: detector de risco oculto com validação'); await shot('r11b_ia_risco');
  await click('[data-target="dce"]'); await sleep(2500); check((await text()).includes('próxima declaração de estabilidade'), 'IA: predição de falha na próxima DCE'); await shot('r11c_ia_predicao_dce');
  await click('[data-iatab="agente"]'); await sleep(2500);
  check((await text()).includes('propostas aguardando'), 'Agente: painel com propostas');
  await click('#ag-run'); await sleep(3000); await waitFor('#ag-run:not([disabled])', 90000); await waitFor('.ag-steps', 30000);
  check(await ev("document.querySelectorAll('.ag-step').length") >= 5, 'Agente: execução mostra os passos (perceber → agir)');
  if (await ev("!!document.querySelector('.ag-dec')")) {
    await ev("document.querySelector('.ag-dec input').value='Vamos conferir na próxima vistoria'"); await click('.ag-dec [data-ok="1"]'); await sleep(2500);
    check((await text()).includes('decisões recentes'), 'Agente: aprovação humana registrada');
  }
  await shot('r11d_agente');
  await click('[data-iatab="ciclo"]'); await sleep(2500);
  check((await text()).includes('campeão') && (await text()).includes('deriva'), 'Ciclo de evolução: campeão, deriva e retorno humano'); await shot('r11e_ciclo');
  await click('#avatar'); await sleep(300); await click('#logout'); await sleep(2000);   // Negócio é área interna: entra como curadoria (equipe LexIA)
  await go('#/entrar', 2000); await click('[data-at="empresa"]'); await sleep(500); await click('[data-demo="gabi@demo.lexia.app"]'); await sleep(3500);
  await go('#/negocio', 3500);
  const nb = await text(); check(nb.includes('negócio & impacto') && nb.includes('simulador') && nb.includes('ponto de equilíbrio') && nb.includes('concorrência'), 'Negócio & Impacto: mercado, equilíbrio, simulador e concorrência');
  check(nb.includes('68.257'), 'Simulador reproduz o resultado do estudo (R$ 68.257 no ano 5)');
  await setVal('[data-sim="price"]', '24000'); await sleep(2000); check((await text()).includes('clientes para equilibrar'), 'Simulador recalcula com premissa editada'); await shot('r11f_negocio');
  await ev("window.scrollTo(0, document.body.scrollHeight)"); await sleep(500); await shot('r11g_negocio_criterios');
  await go('#/ia', 2500);
  for (const [t, n] of [['interp', 'r12_ia_consulta'], ['anom', 'r13_ia_inconsistencias'], ['drafts', 'r14_ia_rascunhos'], ['transp', 'r15_ia_transparencia']]) { await click(`[data-iatab="${t}"]`); await sleep(2200); await shot(n); }
  await click('[data-iatab="interp"]'); await sleep(1500); await click('[data-iq]'); await sleep(2500); check((await text()).includes('de onde veio cada filtro'), 'Consulta → filtros mostra a origem'); await shot('r12_ia_consulta');
  await click('#avatar'); await sleep(300); await click('#logout'); await sleep(2000);
  await go('#/entrar', 2000); await click('[data-at="cidadao"]'); await sleep(500); await click('[data-demo="joana@demo.lexia.app"]'); await sleep(4000);
  await ev("(()=>{const p=document.querySelector('#cid-map .pin, #cid-map .cluster');p.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));p.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));return 1})()"); await sleep(1500);
  const pk = await ev("!!document.querySelector('#cid-pick .cid-pick, #cid-map .map-pop:not([hidden])')"); check(pk, 'Cidadão: clique no mapa mostra a barragem/área'); await shot('r15b_cidadao_clique');
  await go('#/radar', 3000); check((await text()).includes('radar de abandono'), 'Cidadão acessa o Radar');
  await size(390, 844); await go('#/radar', 3000); await noHScroll('radar 390'); await shot('r16_mobile_radar');
  await go('#/ia', 2500); await noHScroll('ia 390'); await shot('r17_mobile_ia');
} catch (err) { errors.push('ERRO: ' + err.message); }
finally {
  writeFileSync(`${OUT}/log.txt`, log.join('\n') + '\n\nERROS:\n' + errors.join('\n'));
  console.log(log.join('\n')); console.log(errors.length ? 'ERROS:\n' + errors.join('\n') : 'SEM ERROS');
  try { ws?.close(); } catch {} proc.kill();
}
