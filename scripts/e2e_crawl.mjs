// Varredura: todas as páginas e abas, por perfil, desktop e celular. Uso: node scripts/e2e_crawl.mjs <pasta>
// Requer o servidor rodando em http://127.0.0.1:8765 e o Chrome instalado (caminho Windows abaixo).
import { resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
const OUT = resolve(process.argv[2] || 'e2e_out'); mkdirSync(OUT, { recursive: true });
const CH = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8765';
const proc = spawn(CH, ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=9338', `--user-data-dir=${OUT}/prof`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map(); const errors = []; const log = [];
async function connect() { for (let i = 0; i < 40; i++) { try { const l = await (await fetch('http://127.0.0.1:9338/json')).json(); const t = l.find((x) => x.type === 'page'); if (t) return t.webSocketDebuggerUrl; } catch {} await sleep(250); } throw new Error('chrome não respondeu'); }
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

const PROFILES = [
  ['empresa', 'ana@demo.lexia.app', ['exec', 'ativos', 'equipe', 'perfil', 'compliance', 'impact', 'extrator', 'decision', 'minas', 'fechamento', 'radar', 'hidro', 'outorgas', 'abastecimento', 'radiologico', 'atlas', 'denuncia', 'gov', 'ia']],
  ['empresa', 'fabio@demo.lexia.app', ['exec', 'radar', 'ia', 'decision']],
  ['empresa', 'gabi@demo.lexia.app', ['gov', 'ia', 'radar', 'negocio', 'contas']],
  ['cidadao', 'joana@demo.lexia.app', ['cidadao', 'radar', 'denuncia', 'ia']],
];
const pageErrors = (label) => { const n = errors.length; return () => errors.slice(n).map((x) => `${label}: ${x}`); };
try {
  ws = new WebSocket(await connect()); await new Promise((r) => ws.addEventListener('open', r));
  ws.addEventListener('message', (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d.result || {}); pending.delete(d.id); }
    if (d.method === 'Runtime.exceptionThrown') errors.push('JS: ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text).split('\n')[0]);
    if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error' && !/favicon/.test(d.params.entry.text)) errors.push('console: ' + d.params.entry.text + ' ' + (d.params.entry.url || ''));
    if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') errors.push('console.error: ' + JSON.stringify(d.params.args.map((a) => a.value || a.description)).slice(0, 200)); });
  await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');
  for (const [w, h] of [[1440, 900], [390, 844]]) {
    await size(w, h);
    for (const [kind, email, routes] of PROFILES) {
      await send('Page.navigate', { url: BASE + '/#/entrar' }); await sleep(2500);
      await ev(`fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"x":1}'})`); await send('Page.navigate', { url: BASE + '/#/entrar' }); await sleep(2500);
      const st = await ev(`fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'${email}',password:'LexIA2026demo',kind:'${kind}'})}).then(r=>r.status)`);
      check(st === 200, `${w} login ${email}`);
      await send('Page.navigate', { url: BASE + '/?s=' + Date.now() + '#/' + routes[0] }); await sleep(4000);
      check((await ev('location.hash')) === '#/' + routes[0], `${w} ${email} sessão ativa após login`);
      for (const r of routes) {
        await go('#/' + r, 3000);
        const here = await ev('location.hash');
        const len = (await text()).length;
        check(here === '#/' + r && len > 200, `${w} ${email} #/${r} → ${here} renderiza (${len} chars)`);
        check(!(await text()).includes('não foi possível carregar'), `${w} ${email} #/${r} sem erro de carregamento`);
        if (w === 390) await noHScroll(`${w} ${email} #/${r}`);
        // percorre abas da página
        const tabs = await ev(`[...document.querySelectorAll('#content [data-iatab],#content [data-tab],#content [data-ptab],#content [data-ftab]')].map(b=>b.getAttribute('data-iatab')?'[data-iatab="'+b.dataset.iatab+'"]':b.getAttribute('data-tab')?'[data-tab="'+b.dataset.tab+'"]':b.getAttribute('data-ptab')?'[data-ptab="'+b.dataset.ptab+'"]':'[data-ftab="'+b.dataset.ftab+'"]')`);
        for (const t of tabs) {
          if (!(await ev(`!!document.querySelector(${JSON.stringify(t)})`))) continue;
          await click(t); await sleep(1800);
          check(!(await text()).includes('não foi possível carregar'), `${w} ${email} #/${r} aba ${t}`);
          if (w === 390) await noHScroll(`${w} ${email} #/${r} ${t}`);
        }
        if (w === 1440) await shot(`c_${email.split('@')[0]}_${r}`);
      }
    }
  }
  // ficha completa do radar com todas as abas e resumo
  await size(1440, 900);
  await send('Page.navigate', { url: BASE + '/#/entrar' }); await sleep(2500);
  await click('[data-at="empresa"]'); await sleep(400); await click('[data-demo="ana@demo.lexia.app"]'); await sleep(3500);
  await go('#/radar', 3000); await click('.rd-row'); await sleep(2500);
  await click('#brief-btn'); await waitFor('.brief-box', 45000).catch(() => {}); check(await ev("!!document.querySelector('.brief-box')"), 'Resumo da barragem aparece'); await shot('c_ficha_resumo');
  check(await ev("[...document.querySelectorAll('#ficha .sat img')].some(i=>i.complete)"), 'Satélite carrega com a política de segurança (CSP)');
} catch (err) { errors.push('ERRO: ' + err.message); }
finally {
  const fails = log.filter((l) => l.startsWith('FALHA'));
  writeFileSync(`${OUT}/crawl.txt`, log.join('\n') + '\n\nERROS:\n' + errors.join('\n'));
  console.log(`verificações: ${log.filter((l) => l.startsWith('OK') || l.startsWith('FALHA')).length} · falhas: ${fails.length}`);
  console.log(fails.join('\n')); console.log(errors.length ? 'ERROS:\n' + [...new Set(errors)].join('\n') : 'SEM ERROS');
  try { ws?.close(); } catch {} proc.kill();
}
