// Grava o vídeo de demonstração da LexIA (≈2 min): a plataforma é usada de verdade, com cursor, quadrado dourado onde clicar
// e legenda curta, sincronizada com a narração (docs/video/duracoes.json, gerada por scripts/gerar_narracao.py).
// Uso: servidor rodando em http://127.0.0.1:8765 → node scripts/gravar_video_demo.mjs → python scripts/montar_video.py
import { resolve } from 'node:path';
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync, readFileSync, rmSync } from 'node:fs';

const ROOT = resolve(import.meta.dirname, '..');
const OUT = resolve(ROOT, 'var', 'video_frames');
rmSync(OUT, { recursive: true, force: true }); mkdirSync(OUT, { recursive: true });
rmSync(resolve(OUT, '..', 'video_prof'), { recursive: true, force: true });   // navegador limpo: começa deslogado
import('node:child_process').then(() => {});
const DUR = JSON.parse(readFileSync(resolve(ROOT, 'docs/video/duracoes.json'), 'utf8'));
const ROT = JSON.parse(readFileSync(resolve(ROOT, 'docs/video/roteiro.json'), 'utf8'));
const CAP = Object.fromEntries(ROT.cenas.map((c) => [c.id, c.legenda]));
const CH = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = 'http://127.0.0.1:8765';
const proc = spawn(CH, ['--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars', '--remote-debugging-port=9341', `--user-data-dir=${OUT}/../video_prof`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, id = 0; const pending = new Map(); const frames = []; const cenas = []; let nf = 0;

async function connect() { for (let i = 0; i < 40; i++) { try { const l = await (await fetch('http://127.0.0.1:9341/json')).json(); const t = l.find((x) => x.type === 'page'); if (t) return t.webSocketDebuggerUrl; } catch {} await sleep(250); } throw new Error('chrome não respondeu'); }
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
  #vx-cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);max-width:78%;background:#0A2540EB;color:#fff;font:600 21px/1.35 Inter,system-ui,sans-serif;padding:11px 22px;border-radius:14px;border-left:5px solid #F2C14E;z-index:2147483645;box-shadow:0 8px 24px #0006;transition:opacity .3s;opacity:0}
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
    cap(t) { cap.textContent = t || ''; cap.style.opacity = t ? 1 : 0; },
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
async function cena(nome, durante, antes) {
  if (antes) { await V.cap(''); await antes(); }
  const t0 = Date.now(); cenas.push({ id: nome, t: t0 / 1000 }); console.log('cena', nome, (DUR[nome] || 0) + 's');
  if (CAP[nome] !== undefined) await V.cap(CAP[nome]);
  await Promise.all([durante(t0), sleep((DUR[nome] || 0) * 1000 + 350)]);
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

  const sub = (t) => V.click('.subtabs a', t);
  const nav = (t) => V.click('#nav .nav-item', t);
  const perfil = async (p) => { await V.click('#perfil-btn'); await sl(500); await V.click(`[data-perfil="${p}"]`); await sl(1400); };
  await cena('abertura', async (t0) => {
    await ate(t0, 1.0); await V.focus('.l-hero h1');
    await ate(t0, 5.5); await V.focus('.l-hero-frentes');
  });
  await cena('anonima', async () => {
    await V.click('.site-nav a', 'Denúncia anônima'); await sl(1900); await V.focus('.page-head'); await sl(2600); await V.focus('.dn-acomp'); await sl(2200);
    await V.click('.site-head a', 'Entrar');
  });
  await cena('cidadao_assunto', async () => {
    await V.click('[data-quick="cidadao"]'); await sl(1900); await V.click('#nav a[href="#/denuncia"]'); await sl(900);
    await V.focus('.dn-cats'); await sl(1500); await V.click('[data-cat="energia"]');
  });
  await cena('cidadao_mapa', async () => {
    await V.click('#dn-ex'); await sleep(2300); await V.focus('.dm-map'); await sl(900);
    await V.click('.dm-pin.real'); await sl(1100); await V.focus('.dm-det');
  });
  await cena('cidadao_relato', async () => {
    await V.type('#dn-rel', "Semana passada, voltando da escola com meu filho, vi um cabo de energia caído perto da cerca da subestação, soltando faísca. Ninguém isolou a área e as crianças passam ali todo dia.");
  }, async () => {
    await ev(`(()=>{ const b=[...document.querySelectorAll('.dn-li')].find(x=>x.querySelector('.dm-n.demo')); if(b) b.setAttribute('data-vx','demo'); })()`);
    await V.click('[data-vx="demo"]'); await sl(1000);
  });
  await cena('cidadao_organizada', async () => {
    await V.focus('.dz-formal'); await sl(3600); await V.focus('.dz-normas'); await sl(2800); await V.focus('.dz-impl');
  }, async () => { await V.click('#dn-go'); await sleep(3200); });
  await cena('cidadao_envio', async () => {
    await V.focus('.dn-confirm'); await sl(1600); await V.click('#dn-ok'); await sl(1400); await V.focus('.dn-result .cp-act');
  });
  await cena('ia_cidadao', async () => {
    await V.click('#nav a[href="#/ia"]'); await sl(1700);
    await V.type('#ia-q', 'O que mudou nas regras da ANM para barragens?'); await V.click('#ia-f button.primary'); await sleep(1600); await V.focus('.ia-msgs .cm.ia'); await sl(2600); await V.focus('.ia-msgs .persp');
  });
  await cena('empresa_visao', async () => {
    await V.click('[data-quick="empresa"]'); await sleep(2400);
    await V.focus('.card', 'Mudanças que exigem atenção'); await sl(2200); await V.focus('.card', 'Fila prioritária');
  }, async () => {
    await ev(`fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"x":1}'})`);
    await send('Page.navigate', { url: BASE + '/?conta=empresa#/entrar' }); await sleep(1600); await ev(OVERLAY);   // recarrega: limpa a conversa do cidadão
  });
  await cena('impacto', async () => {
    await nav('Conformidade'); await sl(1200); await sub('Mudanças normativas'); await sl(1900); await V.focus('.card', 'Mudança por dispositivo');
  });
  await cena('radar_kpis', async () => {
    await nav('Operação'); await sl(1200); await sub('Barragens de mineração'); await sl(1800); await V.focus('.kpis4');
  });
  await cena('radar_orfas', async () => {
    await V.click('.seg button', 'Órfãs'); await sl(1800); await V.focus('.rd-listc');
  });
  await cena('fechamento_minas', async () => {
    await sub('Fechamento de minas'); await sl(2000); await V.focus('.kpis4');
  });
  await cena('energia_outorgas', async () => {
    await perfil('demo-energia'); await sub('Usinas e outorgas'); await sl(1900); await V.focus('.kpis4');
  });
  await cena('denuncia_recebida', async () => {
    await nav('Conformidade'); await sl(1100); await sub('Alertas'); await sl(1300); await V.click('[data-ctab="denuncias"]'); await sl(1800);
    await V.focus('.dz-box .dz-formal'); await sl(2200); await V.focus('.dz-box .dz-passos'); await sl(1600); await V.click('.dz-box [data-passo="0"]'); await sl(900); await V.focus('.dz-box .dz-passos');
  });
  await cena('triagem', async () => {
    await V.click('.cp-alert .tg-abrir'); await sl(700);
    await ev(`(()=>{ const s=document.querySelector('.tg-form:not([hidden]) select'); if(s) s.value='engenharia'; })()`); await V.focus('.tg-form:not([hidden])'); await sl(500);
    await V.type('.tg-form:not([hidden]) input', 'Verificar o ponto e programar o reparo.'); await V.click('.tg-form:not([hidden]) button'); await sl(1600); await V.focus('.tg-feito');
  });
  await cena('outras_frentes', async () => {
    await perfil('demo-saneamento'); await nav('Operação'); await sl(900); await sub('abastecimento'); await sl(1700); await V.focus('.kpis4');
    await perfil('demo-nuclear'); await sub('radiológicas'); await sl(1700); await V.focus('.kpis4');
  });
  await cena('extrator', async () => {
    await nav('Conformidade'); await sl(1100); await sub('obrigação'); await sl(1500); await V.click('#ex-go'); await sl(1800); await V.focus('.ex-ob'); await sl(2200); await V.click('.ex-ob [data-ok]');
  });
  await cena('sistemas_portfolio', async () => {
    await sub('Impacto em sistemas'); await sl(2200); await V.focus('.si-kpis'); await sl(2600); await V.focus('.si-mud.on'); await sl(2400); await V.focus('.si-res');
  });
  await cena('sistemas_codigo', async () => {
    await V.click('[data-sel="sgb-inspecoes"]'); await sl(1300); await V.focus('.si-achado'); await sl(3200); await V.click('.si-achado [data-ok="0"]'); await sl(900); await V.focus('.si-achado');
  });
  await cena('equipe', async () => {
    await nav('Equipe e acessos'); await sl(1500);
    await V.type('#eq-email', 'operador.video@exemplo.invalid'); await V.click('#eq-inv button'); await sl(1600);
    await V.focus('.eq-check'); await sl(700); await V.click('[data-mod="ia"]'); await sl(600);
    await nav('Relatório'); await sl(1700); await V.focus('#rel-print');
  });
  await cena('ia_juridico', async () => {
    await nav('Central de IA'); await sl(1500); await V.click('[data-prof="tecnico"]'); await sl(500);
    await V.type('#ia-q', 'O que mudou nas regras da ANM para barragens?'); await V.click('#ia-f button.primary'); await sleep(1300); await V.focus('.ia-msgs .cm.ia:last-of-type p'); await sl(2600); await V.focus('.ia-msgs .cm.ia:last-of-type .persp'); await sl(2000); await V.focus('.ia-msgs .cm.ia:last-of-type .cm-src');
  });
  await cena('fechamento', async () => { await ev('__v.fim()'); });
  await sleep(600);
  await send('Page.stopScreencast');
  await sleep(500);
  writeFileSync(resolve(ROOT, 'var/video_timeline.json'), JSON.stringify({ frames, cenas, fim: Date.now() / 1000 }, null, 0));
  console.log('quadros:', frames.length, '· duração:', ((Date.now() / 1000) - cenas[0].t).toFixed(1) + 's');
} catch (err) { console.log('ERRO', err.message); } finally { proc.kill(); process.exit(0); }
