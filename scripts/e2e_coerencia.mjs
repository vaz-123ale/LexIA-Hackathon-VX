// E2E de coerência por perfil (Visão Executiva e Mudanças normativas filtradas pelo setor) e mapa do cidadão. Uso: node scripts/e2e_coerencia.mjs <pasta>
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

try {
  ws = new WebSocket(await connect()); await new Promise((r) => ws.addEventListener('open', r));
  ws.addEventListener('message', (m) => { const d = JSON.parse(m.data); if (d.id && pending.has(d.id)) { pending.get(d.id)(d.result || {}); pending.delete(d.id); }
    if (d.method === 'Runtime.exceptionThrown') errors.push('JS: ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text).split('\n')[0]); });
  await send('Runtime.enable'); await send('Page.enable'); await size(1440, 900);
  await send('Page.navigate', { url: BASE + '/#/entrar' }); await sleep(3500);
  await click('[data-at="empresa"]'); await sleep(400); await click('[data-demo="ana@demo.lexia.app"]'); await sleep(3500);
  for (const [perfil, proibido] of [['demo-energia', 'prazo excepcional do eir'], ['demo-saneamento', 'transição futura']]) {
    await click('#perfil-btn'); await sleep(400); await click(`[data-perfil="${perfil}"]`); await sleep(1500);
    await go('#/exec', 3000); const t = await text();
    check(!t.includes(proibido) && !t.includes('barragens · prazo excepcional'), `${perfil}: Visão Executiva sem mudanças da ANM`); await shot('c_exec_' + perfil);
    await go('#/impact', 3500); const opts = await ev("[...document.querySelectorAll('[data-bind=scenario] option')].map(o=>o.textContent).join(' | ')");
    check(!/Barragens/.test(opts), `${perfil}: Laboratório só com mudanças do setor (${opts})`); await shot('c_impact_' + perfil);
  }
  await click('#perfil-btn'); await sleep(400); await click('[data-perfil="demo-nuclear"]'); await sleep(1500);
  await go('#/ativos', 3500); const sub = await text('.subtabs'); const tnu = await text();
  check(sub.includes('instalações radiológicas') && !sub.includes('barragens de mineração') && tnu.includes('nuclear exemplo'), 'Perfil nuclear: abas e empresa do setor');
  check((await ev('document.body.dataset.visualSector')) === 'nuclear', 'Perfil nuclear: imagem do setor'); await shot('c_nuclear_ativos');
  await go('#/radiologico', 4500); const trad = await text(); check(trad.includes('instalações e locais radiológicos') && trad.includes('como este radar decide'), 'Radar radiológico com dados oficiais'); await shot('c_nuclear_radar');
  await click('#perfil-btn'); await sleep(400); await click('[data-perfil="demo-mineracao"]'); await sleep(1500);
  await go('#/extrator', 2500); await click('[data-ex="0"]'); await sleep(500); await click('#ex-go'); await sleep(2500);
  check((await ev("document.querySelectorAll('.ex-ob').length")) >= 3, 'Norma → obrigação: 3 obrigações com trecho literal'); await shot('c_extrator');
  await click('[data-ok="1"]'); await sleep(1200); check((await text()).includes('obrigações já decididas'), 'Confirmação humana registrada');
  await go('#/negocio', 3500); check(!(await text()).includes('conta por cliente') && (await ev('location.hash')) === '#/exec', 'Negócio (interno) não abre para cliente'); await shot('c_negocio_bloqueado');
  await go('#/exec', 3000); check((await text()).includes('prazo excepcional do eir'), 'mineração: mudanças da ANM aparecem');
  await go('#/equipe', 3000); check((await text()).includes('equipe e acessos'), 'Equipe e acessos abre para o jurídico (admin)');
  const mail = 'convite' + Date.now() + '@exemplo.invalid';
  await setVal('#eq-nome', 'Pessoa Convidada'); await setVal('#eq-email', mail); await ev("document.querySelector('#eq-funcao').value='radioprotecao'");
  await ev("document.querySelector('#eq-inv').requestSubmit()"); await sleep(2000);
  const link = await ev("document.querySelector('.eq-links input')?.value || ''"); check(link.includes('#/convite?t='), 'Convite gera link'); await shot('c_equipe');
  await go('#/ia', 2500); await ev("document.querySelector('#ia-q') && (document.querySelector('#ia-q').value='O que mudou na NR-20 sobre tanque de gerador?')");
  await ev("document.querySelector('#ia-f')?.requestSubmit()"); await sleep(5000);
  check((await text()).includes('para você · jurídico'), 'IA responde com foco da função (jurídico)'); await shot('c_ia_persp');
  await click('#avatar'); await sleep(300); await click('#logout'); await sleep(1500);
  if (link) { await ev(`location.href=${JSON.stringify(link)}`); await sleep(3000); await setVal('#cv-pw', 'senha12345'); await ev("document.querySelector('#cv-ok').checked=true");
    await ev("document.querySelector('#cv-form').requestSubmit()"); await sleep(3500);
    check((await ev('location.hash')) === '#/exec', 'Convidado aceita e entra no painel');
    check((await ev("fetch('/api/auth/me').then(r=>r.json()).then(d=>d.user.function)")) === 'radioprotecao', 'Convidado entra com a função definida pela gestão');
    await click('#avatar'); await sleep(300); await click('#logout'); await sleep(1500); }
  await go('#/relatorio', 2500); check((await ev('location.hash')) === '#/entrar', 'Relatório não é público: pede login');
  await click('[data-quick="empresa"]'); await sleep(3500); await go('#/relatorio', 3500);
  const tr = await text(); check(tr.includes('relatório da empresa') && tr.includes('alertas e prazos'), 'Relatório da própria empresa dentro da conta'); await shot('c_relatorio');
  await click('#avatar'); await sleep(300); await click('#logout'); await sleep(1500);
  await go('#/entrar', 1500); await click('[data-at="cidadao"]'); await sleep(400); await click('[data-demo="joana@demo.lexia.app"]'); await sleep(4000);
  const pinsRegiao = await ev("document.querySelectorAll('#cid-map .dm-pin').length"); check(pinsRegiao > 0, `Minha região: mapa de ruas com as barragens numeradas (${pinsRegiao})`);
  await shot('c_cidadao_mapa');
} catch (err) { errors.push('E2E: ' + err.message); }
writeFileSync(`${OUT}/e2e_report.txt`, log.join('\n') + '\n\nERROS:\n' + (errors.join('\n') || 'nenhum'));
console.log(log.join('\n')); console.log('\nERROS:', errors.length ? errors.join('\n') : 'nenhum');
proc.kill(); process.exit(errors.length ? 1 : 0);
