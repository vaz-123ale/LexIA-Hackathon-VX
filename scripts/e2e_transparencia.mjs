// E2E das telas públicas e do cidadão: Portal da Transparência, denúncia com localização, mapa de ativos (demo e empresa real). Uso: node scripts/e2e_transparencia.mjs <pasta>
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
    if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error' && !/favicon|arcgisonline/.test(d.params.entry.text)) errors.push('console: ' + d.params.entry.text); });
  await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable'); await size(1440, 900);
  // localização simulada (Brumadinho/MG) para a busca do cidadão
  await send('Browser.grantPermissions', { origin: BASE, permissions: ['geolocation'] }).catch(() => {});
  await send('Emulation.setGeolocationOverride', { latitude: -20.12, longitude: -44.12, accuracy: 30 });

  // 1. Portal da Transparência sem login
  await send('Page.navigate', { url: BASE + '/#/transparencia' }); await sleep(4500);
  const t = await text();
  check(t.includes('portal da transparência') && t.includes('902'), 'Transparência abre sem login com dados oficiais');
  check(t.includes('casos com atenção crítica ou alta') && (await ev("document.querySelectorAll('.tp-cases article').length")) >= 5, 'Lista de casos reais crítica/alta');
  check(t.includes('vale s.a.'), 'Empresas reais (dados públicos) na tabela');
  check(/respondidas pela empresa/.test(t), 'Bloco de denúncias com respondidas');
  check(await ev("!!document.querySelector('#tp-map svg')"), 'Mapa renderizado');
  await shot('t1_transparencia'); await noHScroll('1440 transparência');
  await ev('window.scrollTo(0, 1100)'); await sleep(500); await shot('t2_transparencia_baixo');
  await size(390, 844); await sleep(800); await noHScroll('390 transparência'); await shot('t3_transparencia_390'); await size(1440, 900);

  // 2. Cidadão: denúncia com localização
  await go('#/entrar', 1500); await click('[data-at="cidadao"]'); await sleep(400);
  await click('[data-demo="joana@demo.lexia.app"]'); await sleep(3000);
  await go('#/denuncia', 2500); await click('#dn-geo'); await sleep(3500);
  const n = await ev("document.querySelectorAll('.dn-n').length");
  check(n >= 5, `Localização encontrou estruturas próximas (${n})`);
  await shot('t4_denuncia_perto');
  await click('.dn-n'); await sleep(1500);
  check((await text()).includes('escolhido:'), 'Escolher o mais próximo preenche o alvo');
  await click('#avatar'); await sleep(300); await click('#logout'); await sleep(1500);

  // 3. Empresa: mapa de ativos demo e empresa real
  await go('#/entrar', 1500); await click('[data-at="empresa"]'); await sleep(400);
  await click('[data-demo="ana@demo.lexia.app"]'); await sleep(3500);
  await go('#/ativos', 3000);
  check(await ev("document.querySelectorAll('.atv-lbl').length") >= 3, 'Mapa de ativos com rótulos');
  await shot('t5_ativos_demo');
  await click('[data-modo="real"]'); await sleep(4000);
  const r = await text();
  check(r.includes('dados públicos') && r.includes('barragens no sigbm'), 'Modo empresa real com dados públicos');
  await shot('t6_ativos_real');
  await click('.rd-row[data-aid]'); await sleep(2000); await shot('t7_ativos_real_ficha');
  await click('[data-modo="demo"]'); await sleep(1500);
  await go('#/radar', 4000); await ev("document.querySelector('.rd-svg')?.scrollIntoView({block:'center'})"); await sleep(600); await shot('t8_radar_mapa');
  await go('#/minas', 4000); await ev("document.querySelector('.rd-svg')?.scrollIntoView({block:'center'})"); await sleep(600); await shot('t9_minas_mapa');
  await click('#perfil-btn'); await sleep(400); await click('[data-perfil="demo-energia"]'); await sleep(2000); await go('#/ativos', 3000);
  await ev("document.querySelector('.atv-svg')?.scrollIntoView({block:'center'})"); await sleep(600); await shot('t10_ativos_energia');
  check((await text()).includes('escalado'), 'Energia sem pessoas cadastradas: alertas escalados, nenhum sem dono');
  await go('#/outorgas', 4500); const tO = await text(); check(tO.includes('usinas, outorgas') && tO.includes('como este radar decide'), 'Energia: radar de usinas e outorgas (ANEEL)'); await shot('t14_outorgas');
  await click('[data-rtipo="barragens_usinas"]'); await sleep(3000); check((await text()).includes('barragens de usinas'), 'Energia: barragens de usinas (SNISB/ANEEL)'); await shot('t15_barragens_usinas');
  await click('.rd-row[data-rid]'); await sleep(2000); await shot('t16_barragem_usina_ficha');

  await ev('window.scrollTo(0,0)'); await sleep(300); await shot('t11_ativos_energia_donos');
  await click('#perfil-btn'); await sleep(400); await click('[data-perfil="demo-saneamento"]'); await sleep(1500);
  await go('#/abastecimento', 4500); check((await text()).includes('barragens de abastecimento humano'), 'Saneamento: radar de barragens de abastecimento'); await shot('t17_abastecimento');
  await click('#perfil-btn'); await sleep(400); await click('[data-perfil="demo-mineracao"]'); await sleep(1500);
  await go('#/fechamento', 5000); const tF = await text(); check(tF.includes('fechamento e paralisação de minas') && tF.includes('barragens a até 5 km'), 'Mineração: radar de fechamento de minas'); await shot('t18_fechamento');
  await click('.rd-row[data-rid]'); await sleep(2000); await shot('t19_fechamento_ficha');
  await go('#/ia', 2500); await click('[data-iatab="eval"]'); await sleep(4000);
  const ev2 = await text();
  check(ev2.includes('normas do setor certo') && ev2.includes('nenhum alerta sem dono') && ev2.includes('matriz de cobertura'), 'Avaliação com categorias por setor, donos e matriz de cobertura');
  await shot('t12_avaliacao'); await ev("document.querySelector('.cov')?.scrollIntoView({block:'center'})"); await sleep(500); await shot('t13_matriz');
} catch (err) { errors.push('E2E: ' + err.message); }
writeFileSync(`${OUT}/e2e_report.txt`, log.join('\n') + '\n\nERROS:\n' + (errors.join('\n') || 'nenhum'));
console.log(log.join('\n')); console.log('\nERROS:', errors.length ? errors.join('\n') : 'nenhum');
proc.kill(); process.exit(errors.length ? 1 : 0);
