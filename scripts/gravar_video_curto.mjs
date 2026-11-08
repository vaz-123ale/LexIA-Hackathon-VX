// Grava o vídeo curto (≈40 s, sem áudio, legenda no topo) da LexIA: a plataforma é usada de verdade, com cursor, quadrado dourado onde clicar
// e legenda curta, sincronizada com a narração (docs/video/duracoes.json, gerada por scripts/gerar_narracao.py).
// Uso: servidor rodando em http://127.0.0.1:8765 → node scripts/gravar_video_demo.mjs → python scripts/montar_video.py
import { resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs';

const ROOT = resolve(import.meta.dirname, '..');
const OUT = resolve(ROOT, 'var', 'video_frames_curto');
rmSync(OUT, { recursive: true, force: true }); mkdirSync(OUT, { recursive: true });
rmSync(resolve(OUT, '..', 'video_prof_curto'), { recursive: true, force: true });   // navegador limpo: começa deslogado
import('node:child_process').then(() => {});
const CH = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8765';
const proc = spawn(CH, ['--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars', '--remote-debugging-port=9342', `--user-data-dir=${OUT}/../video_prof_curto`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map(); const frames = []; const cenas = []; let nf = 0;

async function connect() { for (let i = 0; i < 40; i++) { try { const l = await (await fetch('http://127.0.0.1:9342/json')).json(); const t = l.find((x) => x.type === 'page'); if (t) return t.webSocketDebuggerUrl; } catch {} await sleep(250); } throw new Error('chrome não respondeu'); }
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; const to = setTimeout(() => { pending.delete(i); rej(new Error('CDP sem resposta: ' + method)); }, 30000); pending.set(i, (v) => { clearTimeout(to); res(v); }); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text); return r.result?.value; };
const J = JSON.stringify;

// ------------------------------------------------ sobreposição: cursor, quadrado dourado, legenda e cartão final
const OVERLAY = `(() => { if (window.__v) return;
  const css = document.createElement('style'); css.textContent = \`
  #vx-box{position:fixed;border:3px solid #F2C14E;border-radius:12px;box-shadow:0 0 0 5px #F2C14E40,0 0 26px #F2C14E99;pointer-events:none;z-index:2147483646;transition:all .35s ease;opacity:0}
  #vx-cur{position:fixed;left:-60px;top:-60px;width:26px;height:26px;z-index:2147483647;pointer-events:none;transition:left .55s cubic-bezier(.3,.7,.3,1),top .55s cubic-bezier(.3,.7,.3,1);filter:drop-shadow(0 2px 3px #0008)}
  #vx-rip{position:fixed;width:16px;height:16px;border-radius:50%;border:3px solid #F2C14E;pointer-events:none;z-index:2147483646;opacity:0}
  #vx-rip.on{animation:vxr .5s ease-out}@keyframes vxr{from{transform:translate(-50%,-50%) scale(.6);opacity:1}to{transform:translate(-50%,-50%) scale(3.2);opacity:0}}
  #vx-cap{position:fixed;left:50%;top:14px;transform:translateX(-50%);max-width:86%;background:#0A2540F2;color:#fff;font:700 22px/1.3 Inter,system-ui,sans-serif;padding:10px 24px;border-radius:14px;border-bottom:4px solid #F2C14E;white-space:nowrap;z-index:2147483645;box-shadow:0 8px 24px #0006;transition:opacity .3s;opacity:0}
  #vx-end{position:fixed;inset:0;z-index:2147483647;background:radial-gradient(ellipse at 70% 30%,#12458f,#071d3f 70%);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;font-family:Inter,system-ui,sans-serif;opacity:0;transition:opacity .6s}
  #vx-end img{height:110px;filter:drop-shadow(2px 0 0 #fff) drop-shadow(-2px 0 0 #fff) drop-shadow(0 2px 0 #fff) drop-shadow(0 -2px 0 #fff)}
  #vx-end ul{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:1fr 1fr;gap:12px 34px;font-size:22px}
  #vx-end li{display:flex;gap:10px;align-items:center}#vx-end li b{color:#F2C14E;font-size:24px}
  #vx-end h2{margin:0;font-size:34px;font-weight:700;color:#fff!important}#vx-end small{color:#C9D6E8;font-size:17px}\`;
  document.head.appendChild(css);
  const mk = (id, html = '') => { const d = document.createElement('div'); d.id = id; d.innerHTML = html; document.body.appendChild(d); return d; };
  const box = mk('vx-box'), cap = mk('vx-cap'), rip = mk('vx-rip');
  const cur = mk('vx-cur', '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 2l16 9.5-7 1.6-3.6 6.9z" fill="#fff" stroke="#0A2540" stroke-width="1.8" stroke-linejoin="round"/></svg>');
  const find = (sel, txt) => { const all = [...document.querySelectorAll(sel)].filter((x) => x.offsetParent !== null || getComputedStyle(x).position === 'fixed');
    return txt ? all.find((x) => x.textContent.toLowerCase().includes(txt.toLowerCase())) : all[0]; };
  const rectOf = (el) => { const r = el.getBoundingClientRect(); return r; };
  window.__v = {
    async focus(sel, txt, pad = 8) { const el = find(sel, txt); if (!el) return false; el.scrollIntoView({ block: 'center', behavior: 'smooth' }); await new Promise((r) => setTimeout(r, 430));
      const r = rectOf(el); Object.assign(box.style, { left: (r.left - pad) + 'px', top: (r.top - pad) + 'px', width: (r.width + pad * 2) + 'px', height: (r.height + pad * 2) + 'px', opacity: 1 }); return true; },
    async move(sel, txt) { const el = find(sel, txt); if (!el) return null; const r = rectOf(el); cur.style.left = (r.left + Math.min(r.width / 2, 60)) + 'px'; cur.style.top = (r.top + r.height / 2) + 'px'; await new Promise((x) => setTimeout(x, 430)); return el; },
    async click(sel, txt) { if (!(await this.focus(sel, txt, 5))) return false; const el = await this.move(sel, txt); const r = rectOf(el);
      rip.style.left = (r.left + Math.min(r.width / 2, 60) + 4) + 'px'; rip.style.top = (r.top + r.height / 2 + 4) + 'px'; rip.classList.remove('on'); void rip.offsetWidth; rip.classList.add('on');
      await new Promise((x) => setTimeout(x, 170)); el.click(); await new Promise((x) => setTimeout(x, 180)); box.style.opacity = 0; return true; },
    async type(sel, text, ms = 17) { const el = find(sel); if (!el) return false; await this.focus(sel); el.focus(); el.value = '';
      for (const ch of text) { el.value += ch; el.dispatchEvent(new Event('input', { bubbles: true })); await new Promise((x) => setTimeout(x, ms)); } box.style.opacity = 0; return true; },
    cap(t) { const [a, b] = String(t || '').split('|'); cap.innerHTML = t ? (b ? '<span style="color:#F2C14E;text-transform:uppercase;font-size:15px;letter-spacing:1.5px;margin-right:12px">' + a + '</span>' + b : a) : ''; cap.style.opacity = t ? 1 : 0; },
    hide() { box.style.opacity = 0; },
    fim() { const d = mk('vx-end', '<img src="/img/brand/logo-lexia-v6.png" alt=""><h2>Da mudança regulatória à decisão executável</h2><ul><li><b>✓</b>Dados oficiais reais: ANM, ANA, ANEEL, ONS</li><li><b>✓</b>Vigência calculada artigo por artigo</li><li><b>✓</b>4 frentes no mesmo núcleo</li><li><b>✓</b>IA propõe · regras verificam · humano decide</li><li><b>✓</b>Denúncia vira dossiê para a empresa</li><li><b>✓</b>Norma → sistema → linha de código</li><li><b>✓</b>Prova de cada decisão, com trilha</li></ul><small>Hackathon VX · Desafio 02</small>'); cap.style.opacity = 0; box.style.opacity = 0; cur.style.left = '-60px'; requestAnimationFrame(() => { d.style.opacity = 1; }); },
  };
})();`;
const V = {
  cap: (t) => ev(`__v.cap(${J(t)})`), hide: () => ev('__v.hide()'),
  focus: (s, t) => ev(`__v.focus(${J(s)}, ${J(t || null)})`), click: async (s, t) => { const ok = await ev(`__v.click(${J(s)}, ${J(t || null)})`); if (!ok) console.log('  ! não achei', s, t || ''); return ok; },
  type: (s, x) => ev(`__v.type(${J(s)}, ${J(x)})`),
};
const goto = async (hash, wait = 2500) => { await send('Page.navigate', { url: BASE + '/' + hash }); await sleep(wait); await ev(OVERLAY); };
const PAUSAS = [];
async function cena(nome, dur, legenda, durante, antes) {
  if (antes) { await send('Page.stopScreencast'); const p0 = Date.now() / 1000; await V.cap(''); await antes(); await V.cap(legenda); await sleep(350);
    PAUSAS.push([p0, Date.now() / 1000]); await send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 }); }
  else await V.cap(legenda);
  const t0 = Date.now(); cenas.push({ id: nome, t: t0 / 1000 }); console.log('cena', nome);
  await Promise.all([durante(t0), sleep(dur * 1000)]);
}
const K = 0.68, sl = (ms) => sleep(ms * K);
const ate = async (t0, s) => { const w = t0 + s * 1000 - Date.now(); if (w > 0) await sleep(w); };

try {
  ws = new WebSocket(await connect()); await new Promise((r) => ws.addEventListener('open', r));
  ws.addEventListener('message', (m) => { const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) { pending.get(d.id)(d.result || {}); pending.delete(d.id); }
    if (d.method === 'Page.screencastFrame') { const f = `f${String(++nf).padStart(5, '0')}.jpg`; writeFileSync(`${OUT}/${f}`, Buffer.from(d.params.data, 'base64')); frames.push({ f, t: d.params.metadata.timestamp });
      ws.send(JSON.stringify({ id: ++id, method: 'Page.screencastFrameAck', params: { sessionId: d.params.sessionId } })); } });
  await send('Runtime.enable'); await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 720, deviceScaleFactor: 1.5, mobile: false });
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `window.addEventListener('DOMContentLoaded', () => { ${OVERLAY} });` });
  await goto('#/inicio', 5000);
  await ev(`(async()=>{ for (const r of ['/img/brand/sector-mining.jpg','/img/brand/sector-energy.jpg','/img/brand/sector-sanitation.jpg','/img/brand/sector-nuclear.jpg']) await fetch(r); })()`);
  await send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  await sleep(400);

  const RELATO = "Semana passada, voltando da escola com meu filho, vi um cabo de energia caído perto da cerca da subestação, soltando faísca. Ninguém isolou a área e as crianças passam ali todo dia.";
  const sub = (t) => V.click('.subtabs a', t);
  const nav = (t) => V.click('#nav .nav-item', t);
  await cena('inicio', 4, 'LexIA|Risco e conformidade regulatória em 4 frentes', async () => { await sl(500); await V.focus('.l-hero-frentes'); });
  await cena('denuncia', 7.5, 'Cidadão|A história vira relato formal, com normas e custo', async () => {
    await V.click('#dn-go'); await sleep(1500); await V.focus('.dz-formal'); await sl(2000); await V.focus('.dz-impl');
  }, async () => {
    await goto('#/denuncia-anonima', 2200); await V.click('[data-cat="energia"]'); await sleep(500); await V.click('#dn-ex'); await sleep(2600);
    await ev(`(()=>{ const b=[...document.querySelectorAll('.dn-li')].find(x=>x.querySelector('.dm-n.demo')); if(b) b.click(); })()`); await sleep(1200);
    await ev(`(()=>{ const t=document.querySelector('#dn-rel'); t.value=${JSON.stringify(RELATO)}; t.dispatchEvent(new Event('input',{bubbles:true})); t.scrollIntoView({block:'center'}); })()`); await sleep(400); await V.hide();
  });
  await cena('radar', 5.5, 'Mineração|7.937 barragens sem dono · dados reais ANM e ANA', async () => {
    await V.click('.seg button', 'Órfãs'); await sl(1300); await V.focus('.kpis4');
  }, async () => {
    await ev(`document.querySelector('#dn-ok')?.click()`); await sleep(2200);   // envia a denúncia (fora do vídeo)
    await goto('#/entrar', 1500); await V.click('[data-quick="empresa"]'); await sleep(2600); await goto('#/radar', 2600); await V.hide();
  });
  await cena('energia', 4.5, 'Energia|1.916 usinas reais avaliadas pela outorga (ANEEL)', async () => {
    await sl(300); await V.focus('.kpis4'); await sl(2200); await V.focus('.rd-grid');
  }, async () => {
    await V.click('#perfil-btn'); await sleep(400); await V.click('[data-perfil="demo-energia"]'); await sleep(1500); await sub('Usinas e outorgas'); await sleep(2200);
    await ev(`document.querySelector('.kpis4')?.scrollIntoView({block:'center'})`); await V.hide();
  });
  await cena('dossie', 6.5, 'Empresa|Recebe o dossiê e repassa para a área certa', async () => {
    await V.focus('.dz-box .dz-passos'); await sl(1400); await V.click('.cp-alert .tg-abrir'); await sl(300);
    await ev(`(()=>{ const f=document.querySelector('.tg-form:not([hidden])'); if(f){ f.querySelector('select').value='engenharia'; f.querySelector('input').value='Verificar o ponto e programar o reparo.'; } })()`);
    await V.click('.tg-form:not([hidden]) button'); await sl(1200); await V.focus('.tg-feito');
  }, async () => {
    await nav('Conformidade'); await sleep(1300); await sub('Alertas'); await sleep(1300); await V.click('[data-ctab="denuncias"]'); await sleep(2000);
    await ev(`document.querySelector('.dz-box')?.scrollIntoView({block:'start'})`); await V.hide();
  });
  await cena('sistemas', 7, 'Norma muda|Sistemas afetados → arquivo, linha e alteração de código', async () => {
    await V.focus('.si-res'); await sl(1600); await V.click('[data-sel="sgb-inspecoes"]'); await sl(1000); await V.focus('.si-achado');
  }, async () => { await sub('Impacto em sistemas'); await sleep(2600); await ev(`document.querySelector('.si-res')?.scrollIntoView({block:'center'})`); await V.hide(); });
  await cena('fim', 3.5, '', async () => { await ev('__v.fim()'); });
  await sleep(300);
  await send('Page.stopScreencast');
  await sleep(400);
  writeFileSync(resolve(ROOT, 'var/video_timeline_curto.json'), JSON.stringify({ frames, cenas, pausas: PAUSAS, fim: Date.now() / 1000 }, null, 0));
  console.log('quadros:', frames.length);
} catch (err) { console.log('ERRO', err.message); } finally { proc.kill(); process.exit(0); }
