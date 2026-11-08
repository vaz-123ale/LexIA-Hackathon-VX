// E2E v5 via Chrome DevTools Protocol (sem dependências). Uso: node scripts/e2e_cdp.mjs <pasta-saida>
// Requer o servidor rodando em http://127.0.0.1:8765 e o Chrome instalado (caminho Windows abaixo).
import { resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
const OUT = resolve(process.argv[2] || 'e2e_out'); mkdirSync(OUT, { recursive: true });
const CH = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8765';
const proc = spawn(CH, ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=9334', `--user-data-dir=${OUT}/prof`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map(); const errors = []; const log = [];
async function connect() { for (let i = 0; i < 40; i++) { try { const l = await (await fetch('http://127.0.0.1:9334/json')).json(); const t = l.find((x) => x.type === 'page'); if (t) return t.webSocketDebuggerUrl; } catch {} await sleep(250); } throw new Error('chrome não respondeu'); }
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

  // 1. Site público
  await send('Page.navigate', { url: BASE + '/#/inicio' }); await sleep(3500);
  const home = await text();
  check(home.includes('decisão executável') && home.includes('902'), 'Página inicial com proposta e 902 barragens oficiais');
  check(home.includes('para empresas') || home.includes('empresas'), 'Página inicial separa empresas e cidadãos');
  await shot('01_inicio'); await noHScroll('1440 início');
  await go('#/sobre'); check((await text()).includes('privacidade'), 'Página Sobre com privacidade (LGPD)'); await shot('02_sobre');
  await go('#/exec', 1500); check((await ev('location.hash')) === '#/entrar', 'Painel protegido redireciona para login');

  // 2. Login empresa
  await click('[data-at="empresa"]'); await sleep(500); await shot('03_entrar');
  await click('[data-demo="ana@demo.lexia.app"]'); await sleep(3500);
  check((await ev('location.hash')) === '#/exec', 'Login empresa (Ana) abre Visão Executiva');
  const ex = await text();
  check(ex.includes('panorama de risco e conformidade') && ex.includes('operação da empresa') && ex.includes('mudanças que exigem atenção') && ex.includes('fila prioritária'), 'Visão Executiva no layout da referência');
  check(await ev("document.querySelectorAll('.kpis4 .kpi').length") === 4, '4 indicadores calculados');
  check(await ev("document.querySelectorAll('.change-card').length") >= 3, 'Mudanças normativas listadas com ação de análise');
  const llmOn = await ev("fetch('/api/ai/status').then(r=>r.json()).then(d=>d.llm.enabled)");
  check(!(await ev("!!document.querySelector('.ins-tag')")) || (await ev("document.querySelector('.ins-tag').textContent")) === (llmOn ? 'IA + Regras' : 'Regras'), `Insight rotulado conforme a IA (${llmOn ? 'ligada' : 'desligada'})`);
  const affected0 = await kpi(3);
  await shot('04_exec');

  // 2b. Perfil da empresa: mesmo sistema, módulos diferentes (mineração x energia)
  check(await ev("document.querySelectorAll('#nav .nav-item').length") === 4, 'Menu agrupado em 4 áreas (sem Gestão & Negócio)');
  check(!(await ev("document.querySelector('#nav').innerText")).includes('Negócio'), 'Negócio fora do menu da empresa');
  await go('#/perfil', 2000); const pf = await text();
  check(pf.includes('meu perfil') && pf.includes('foto e dados pessoais') && pf.includes('organização'), 'Página Meu perfil');
  await setVal('#pf-phone', '(31) 3333-0000'); await click('#pf-form button.primary'); await sleep(1500);
  check((await ev("fetch('/api/auth/me').then(r=>r.json()).then(d=>d.user.phone)")) === '(31) 3333-0000', 'Perfil salvo (telefone)');
  await shot('04c_perfil'); await go('#/exec', 1500);
  await go('#/ativos', 2500);
  const subMin = await text('.subtabs');
  check(subMin.includes('minas') && subMin.includes('fechamento de minas') && subMin.includes('barragens de mineração') && subMin.includes('atlas') && !subMin.includes('outorgas'), 'Perfil mineração: Minas, Fechamento, Barragens de mineração e Atlas');
  await click('#perfil-btn'); await sleep(400); await click('[data-perfil="demo-energia"]'); await sleep(2500);
  const subEn = await text('.subtabs');
  check(subEn.includes('usinas e outorgas') && subEn.includes('reservatórios') && !subEn.includes('minas') && !subEn.includes('barragens de mineração'), 'Perfil energia: Usinas e outorgas e Reservatórios, sem mineração');
  check((await text()).includes('energia exemplo'), 'Ativos mostram a empresa do perfil');
  await shot('04b_perfil_energia');
  await click('#perfil-btn'); await sleep(400); await click('[data-perfil="demo-mineracao"]'); await sleep(1500);
  await go('#/exec', 2000);

  // 3. Atlas + carteira + globo
  await go('#/atlas', 2800); await setVal('#atlas-q', 'Vale'); await sleep(2000); await waitFor('#entity-box .ent');
  await click('[data-ent-filter="33592510000154"]'); await sleep(2200);
  await click('tr[data-row]'); await sleep(1800); await waitFor('.panel details');
  check((await text('#side-panel')).includes('dado oficial'), 'Ficha da estrutura oficial');
  if (await ev(`!!document.querySelector('[data-watch][data-action="remove"]')`)) { await click('[data-watch][data-action="remove"]'); await sleep(1500); }
  await click('[data-watch][data-action="add"]'); await sleep(1500);
  check(await ev(`!!document.querySelector('[data-watch][data-action="remove"]')`), 'Estrutura adicionada à carteira');
  check(await ev("!!document.querySelector('#side-panel .sat img, #side-panel .sat-off')"), 'Ficha mostra imagem de satélite (ou aviso de ponto fictício)');
  await click('[data-view="map"]').catch(()=>{}); await sleep(800);
  await ev("(()=>{const c=document.querySelector('.map-frame .cluster');if(!c)return 0;c.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));c.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}));return 1})()"); await sleep(1200);
  check(await ev("!!document.querySelector('.map-pop:not([hidden]) .pop-list button')"), 'Clique no número do mapa abre cartão com lista e satélite');
  await shot('05_atlas');
  await click('[data-view="globe"]'); await sleep(2500);
  const g = await ev("(()=>{const f=document.querySelector('.globe-frame'),c=f.querySelector('canvas');return [f.clientWidth,f.clientHeight,c.clientWidth,c.clientHeight]})()");
  check(g[2] === g[0] && g[3] === g[1], `Globo ocupa o quadro inteiro (${g.join('×')})`);
  check(await ev("!document.querySelector('#globe-card').hidden"), 'Globo mostra a ficha do ponto selecionado');
  check((await text('#globe-card')).includes('ver ficha completa'), 'Ficha do globo tem ações');
  await shot('06_globo');
  await go('#/exec', 2800);
  const affected1 = await kpi(3); check(Number.isFinite(affected1) && affected1 >= affected0, `Indicador de ativos afetados considera a carteira (${affected0} → ${affected1})`);

  // 4. Laboratório + decisão + dossiê
  await click('[data-analyze]'); await sleep(3000); await waitFor('.cascade');
  const qd = await ev("[...document.querySelectorAll('.quick [data-date]')].map(b=>b.dataset.date)");
  check(qd.length >= 2, `Laboratório oferece datas de simulação (${qd.join(', ')})`);
  await click(`[data-date="${qd.at(-1)}"]`); await sleep(3000); check((await ev('document.querySelector("[data-bind-date]")?.value')) === qd.at(-1), 'Laboratório: simulação muda a data-base'); await shot('07_impacto');
  await ev("document.querySelector('#asof-reset')?.click()"); await sleep(2500);
  await go('#/decision', 2500); await click('.kcard'); await sleep(1500);
  await setVal('#tr-reason', 'Encaminhado para análise'); await click('#tr-form button'); await sleep(1800);
  await click('.kcard.sel'); await sleep(1200);
  const rid = await ev("document.querySelector('.kcard.sel')?.dataset.review || document.querySelector('.kcard')?.dataset.review");
  await setVal('#tr-to', 'CONFIRMED', 'change'); await setVal('#tr-reason', 'Dispositivos conferidos no texto oficial'); await click('#tr-form button'); await sleep(2000);
  check((await text()).includes('ana (jurídico, demo)'), 'Decisão registrada com o nome da sessão');
  await shot('08_decisao');
  const pack = (await ev(`fetch('/api/export/decision-pack?finding=' + encodeURIComponent(${JSON.stringify(rid)})).then(r=>r.text())`)).toLowerCase();
  check(pack.includes('avaliação preliminar'), 'Dossiê de decisão exportado');

  // 5. Governança: monitor de fontes
  await go('#/gov'); await click('[data-tab="gov:monitor"]'); await sleep(2000);
  const mon = await text();
  check(mon.includes('monitor de fontes oficiais') && mon.includes('lexml') && mon.includes('diário oficial'), 'Monitor de fontes com canais bloqueados declarados');
  await shot('09_monitor');
  await click('#bell'); await sleep(600); check(await ev("!document.querySelector('#bell-panel').hidden"), 'Sino de notificações abre'); await shot('10_notificacoes');
  await click('#avatar'); await sleep(400); await click('#logout'); await sleep(2500);
  check((await ev('location.hash')) === '#/inicio', 'Sair volta para o início');

  // 6. Cidadão
  await go('#/entrar'); await click('[data-at="cidadao"]'); await sleep(500); await click('[data-demo="joana@demo.lexia.app"]'); await sleep(3500);
  const cid = await text();
  check((await ev('location.hash')) === '#/cidadao' && cid.includes('olá, joana') && cid.includes('defesa civil: 199'), 'Portal do cidadão com linguagem simples e emergência');
  check(cid.includes('barragens em'), 'Cidadão vê barragens da região');
  await shot('11_cidadao');
  await go('#/exec', 2000); check((await ev('location.hash')) === '#/cidadao', 'Cidadão não acessa o painel da empresa');
  await click('#avatar'); await sleep(300); await click('#logout'); await sleep(2000);

  // 7. Cadastro de empresa (CNPJ inválido e válido)
  await go('#/cadastro'); await click('[data-at="empresa"]'); await sleep(500);
  const fill = async (cnpj) => { await setVal('#r-name', 'Teste E2E'); await setVal('#r-email', `e2e${Date.now()}@ex.com`); await setVal('#r-org', 'Exemplo E2E Ltda'); await setVal('#r-cnpj', cnpj); await setVal('#r-fn', 'compliance', 'change'); await setVal('#r-pw', 'senha12345'); await ev("document.querySelector('#r-ok').checked=true"); await click('#reg button'); await sleep(2500); };
  await fill('11.222.333/0001-82'); await sleep(300);
  for (let i = errors.length - 1; i >= 0; i--) if (/status of 400/.test(errors[i])) errors.splice(i, 1); // 400 esperado: CNPJ inválido é recusado pelo servidor
  check((await ev('location.hash')) === '#/cadastro' && await ev("!!document.querySelector('.toast.err')"), 'Cadastro recusa CNPJ inválido');
  await shot('12_cadastro');
  await fill('11.222.333/0001-81'); check((await ev('location.hash')) === '#/exec', 'Cadastro de empresa válido entra no painel');

  // 8. Responsivo
  check(await ev("navigator.serviceWorker.getRegistration().then(r=>!!r)"), 'App (PWA) registrado');
  for (const [w, h] of [[1366, 768], [768, 1024], [390, 844]]) {
    await size(w, h);
    for (const r of ['exec', 'atlas', 'impact', 'decision', 'gov']) { await go('#/' + r, 2200); await noHScroll(`${w}x${h} ${r}`); if (w !== 1366 || r === 'exec') await shot(`r_${w}_${r}`); }
  }
  await size(390, 844); await click('#avatar'); await sleep(300); await click('#logout'); await sleep(2000); await noHScroll('390 início'); await shot('r_390_inicio');
} catch (err) { errors.push('E2E: ' + err.message); }
writeFileSync(`${OUT}/e2e_report.txt`, log.join('\n') + '\n\nERROS:\n' + (errors.join('\n') || 'nenhum'));
console.log(log.join('\n')); console.log('\nERROS:', errors.length ? errors.join('\n') : 'nenhum');
proc.kill(); process.exit(errors.length ? 1 : 0);
