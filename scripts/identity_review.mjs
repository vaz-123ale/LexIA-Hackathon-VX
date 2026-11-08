// Verificação visual somente leitura; login em banco isolado, sem alterar decisões.
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
const out=resolve('docs/screenshots/identity-review');mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:8766';
const profile=mkdtempSync(resolve(tmpdir(),'lexia-identity-'));
const proc=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
  '--headless=new','--disable-gpu','--disable-extensions','--no-first-run',
  '--remote-debugging-port=9345',`--user-data-dir=${profile}`,'about:blank'
],{stdio:'ignore'});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let ws,id=0;const jobs=new Map(),report=[];
const send=(method,params={})=>new Promise((res,rej)=>{
  const key=++id;const timer=setTimeout(()=>{jobs.delete(key);rej(Error('Timeout '+method));},15000);
  jobs.set(key,{res,rej,timer});ws.send(JSON.stringify({id:key,method,params}));
});
const ev=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result?.value;};
try{
  let target;for(let n=0;n<50;n++){try{target=(await(await fetch('http://127.0.0.1:9345/json')).json()).find(x=>x.type==='page');if(target)break;}catch{}await pause(200);}
  if(!target)throw Error('Chrome indisponível');
  ws=new WebSocket(target.webSocketDebuggerUrl);
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);const job=jobs.get(m.id);if(job){clearTimeout(job.timer);jobs.delete(m.id);m.error?job.rej(Error(m.error.message)):job.res(m.result||{});}});
  await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
  await send('Page.enable');await send('Runtime.enable');
  await send('Page.navigate',{url:base});await pause(1500);
  for(const width of (process.env.QA_WIDTHS||'1600,1366,390').split(',').map(Number)){
    await send('Emulation.setDeviceMetricsOverride',{width,height:width===390?844:900,deviceScaleFactor:1,mobile:width===390});
    for(const route of (process.env.QA_ROUTES||'inicio,sobre,entrar,cadastro,exec,ativos,minas,radar,hidro,atlas,compliance,impact,decision,denuncia,ia,negocio,contas,gov').split(',')){
      if(route==='exec')await ev(`fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'ana@demo.lexia.app',password:'LexIA2026demo',kind:'empresa'})}).then(r=>r.json())`);
      await send('Page.navigate',{url:base+'/?identity='+width+'-'+route+'#/'+route});await pause(900);
      for(let n=0;n<200;n++){if(await ev(`document.querySelector('#content')?.dataset.page===${JSON.stringify(route)}&&!document.querySelector('#content>.loading')`))break;await pause(200);}
      await ev(`Promise.all(Array.from(document.images).filter(x=>new URL(x.src).origin===location.origin).map(x=>x.decode().catch(()=>{})))`);
      const check=await ev(`({route:document.querySelector('#content')?.dataset.page,scroll:document.documentElement.scrollWidth,viewport:innerWidth,error:document.querySelector('#content')?.textContent.includes('Não foi possível carregar'),broken:Array.from(document.images).filter(x=>new URL(x.src).origin===location.origin&&x.complete&&!x.naturalWidth).map(x=>x.src)})`);
      report.push({width,requested:route,...check});
      const shot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(out+'/'+width+'_'+route+'.png',Buffer.from(shot.data,'base64'));
      if(check.scroll>width+1||check.route!==route||check.error||check.broken.length){
        report.push({overflow:await ev(`Array.from(document.querySelectorAll('#content *,.topbar *')).filter(x=>x.getBoundingClientRect().right>innerWidth+2).slice(0,15).map(x=>({tag:x.tagName,cls:x.className,right:x.getBoundingClientRect().right}))`)});
      }
    }
    await ev(`fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})`);
    await ev(`fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'joana@demo.lexia.app',password:'LexIA2026demo',kind:'cidadao'})}).then(r=>r.json())`);
    await send('Page.navigate',{url:base+'/?identity='+width+'-cidadao#/cidadao'});
    for(let n=0;n<200;n++){if(await ev(`document.querySelector('#content')?.dataset.page==='cidadao'`))break;await pause(200);}
    const citizen=await ev(`({route:document.querySelector('#content')?.dataset.page,scroll:document.documentElement.scrollWidth,viewport:innerWidth,error:document.querySelector('#content')?.textContent.includes('Não foi possível carregar'),broken:Array.from(document.images).filter(x=>new URL(x.src).origin===location.origin&&x.complete&&!x.naturalWidth).map(x=>x.src)})`);
    report.push({width,requested:'cidadao',...citizen});
    const shot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(out+'/'+width+'_cidadao.png',Buffer.from(shot.data,'base64'));
    await ev(`fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})`);
  }
}catch(e){report.push({failure:e.message});process.exitCode=1;}
finally{writeFileSync(out+'/identity-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));ws?.close();proc.kill();}
