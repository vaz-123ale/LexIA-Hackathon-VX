// QA isolado de interface local. Não altera revisões, projetos ou evidências.
import {spawn} from 'node:child_process';
import {mkdirSync,writeFileSync,mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const out=resolve(process.argv[2] || 'docs/screenshots/v12');mkdirSync(out,{recursive:true});
const base=process.env.TORRE_QA_BASE || 'http://127.0.0.1:8766';
const chrome=process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const profile=mkdtempSync(resolve(tmpdir(),'torre-visual-'));
const child=spawn(chrome,['--headless=new','--disable-gpu','--hide-scrollbars','--no-first-run','--remote-debugging-port=9339',`--user-data-dir=${profile}`,'about:blank'],{stdio:['ignore','ignore','pipe']});
let stderr='';child.stderr.on('data',b=>{stderr=(stderr+b.toString()).slice(-1500);});
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let ws,seq=0;const pending=new Map(),report=[];
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Timeout '+method));},12000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);return r.result?.value;};
try {
  let page;
  for(let i=0;i<40;i++){try{page=(await(await fetch('http://127.0.0.1:9339/json')).json()).find(x=>x.type==='page');if(page)break;}catch{}await pause(250);}
  if(!page)throw new Error('Chrome indisponível: '+stderr);
  ws=new WebSocket(page.webSocketDebuggerUrl);
  ws.addEventListener('message',async ev=>{try{const m=JSON.parse(typeof ev.data==='string'?ev.data:await ev.data.text());const job=pending.get(m.id);if(job){clearTimeout(job.timer);pending.delete(m.id);if(m.error)job.reject(new Error(m.error.message));else job.resolve(m.result || {});}}catch(err){report.push('ERRO CDP '+err.message);}});
  await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
  await send('Runtime.enable');await send('Page.enable');await send('DOM.enable');await send('CSS.enable');
  await send('Page.navigate',{url:base+'/#/inicio'});await pause(1600);
  await evaluate(`fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'ana@demo.lexia.app',password:'LexIA2026demo'})}).then(r=>{if(!r.ok)throw new Error('Login de teste falhou');return r.json()})`);
  for(const width of (process.env.QA_WIDTHS || '1672,1366,390').split(',').map(Number)) {
    await send('Emulation.setDeviceMetricsOverride',{width,height:width===390?844:941,deviceScaleFactor:1,mobile:width===390});
    for(const route of (process.env.QA_ROUTES || 'exec,atlas,impact,decision,gov').split(',')) {
      await send('Page.navigate',{url:base+'/?qa='+width+'-'+route+'#/'+route});await pause(1800);
      for(let attempt=0;attempt<30;attempt++){if(await evaluate(`document.querySelector('#content')?.dataset.page===${JSON.stringify(route)}`))break;await pause(300);}
      const checks=await evaluate(`({page:document.querySelector('#content')?.dataset.page,error:document.querySelector('#content')?.textContent.includes('Não foi possível carregar'),scroll:document.documentElement.scrollWidth,viewport:document.documentElement.clientWidth,uf:document.querySelectorAll('#atlas-map .uf').length,feed:document.querySelectorAll('.change-card').length})`);
      const shot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(`${out}/${width}_${route}.png`,Buffer.from(shot.data,'base64'));report.push('OK '+width+' '+route+' '+JSON.stringify(checks));
      const layout=await evaluate(`Object.fromEntries(['.sidebar','.topbar','.page-head','.atlas-filters','.atlas-map-card','#atlas-map','#side-panel','.steps','.steps+.card','.hero','.kpis4','.kanban','.tabs'].map(s=>{const el=document.querySelector(s);if(!el)return[s,null];const r=el.getBoundingClientRect(),c=getComputedStyle(el);return[s,{x:r.x,y:r.y,width:r.width,height:r.height,font:c.fontFamily,size:c.fontSize}]}))`);
      writeFileSync(`${out}/${width}_${route}.json`,JSON.stringify(layout,null,2));
      if(width===1672&&route==='atlas'){const doc=await send('DOM.getDocument');const el=await send('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'.page-head h2'});report.push('FONT '+JSON.stringify(await send('CSS.getPlatformFontsForNode',{nodeId:el.nodeId})));}
      if(checks.error || checks.page!==route || checks.scroll>checks.viewport+1){report.push(JSON.stringify(await evaluate(`Array.from(document.querySelectorAll('body *')).filter(x=>x.getBoundingClientRect().right>innerWidth+2).slice(0,20).map(x=>({tag:x.tagName,cls:x.className,right:x.getBoundingClientRect().right}))`)));throw new Error(route+' '+width+': '+JSON.stringify(checks));}
      if(width===1672&&route==='atlas'&&process.env.QA_INTERACTIONS==='1') {
        const verify=async(name,expression)=>{if(!await evaluate(expression))throw new Error('INTERACAO '+name);report.push('INTERACAO OK '+name);};
        await verify('selecao e ficha do snapshot',`document.querySelector('.pin.sel')?.dataset.id==='SIGBM-9149'&&document.querySelector('#side-panel h3')?.textContent==='Jacaré Inferior'`);
        const initial=await evaluate(`document.querySelector('#atlas-map>svg').getAttribute('viewBox')`);
        await evaluate(`document.querySelector('[data-zoom="in"]').click()`);
        await verify('aproximar',`Number(document.querySelector('#atlas-map>svg').getAttribute('viewBox').split(' ')[2])<690`);
        await evaluate(`document.querySelector('[data-zoom="reset"]').click()`);
        await verify('restaurar enquadramento',`document.querySelector('#atlas-map>svg').getAttribute('viewBox')===${JSON.stringify(initial)}`);
        await evaluate(`document.querySelector('#atlas-map .cluster').focus()`);
        await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
        await verify('cluster por teclado',`Number(document.querySelector('#atlas-map>svg').getAttribute('viewBox').split(' ')[2])<690`);
        await evaluate(`document.querySelector('[data-zoom="reset"]').click();const q=document.querySelector('#atlas-q');q.value='zz_sem_resultado_93827';q.dispatchEvent(new Event('input',{bubbles:true}))`);await pause(1000);
        await verify('sem resultado limpa ficha e mapa',`!!document.querySelector('.panel-empty')&&document.querySelectorAll('#atlas-map .pin,#atlas-map .cluster').length===0`);
        await evaluate(`document.querySelector('#atlas-clear').click()`);await pause(800);
        await evaluate(`const uf=document.querySelector('[data-atlas="uf"]');uf.value='RS';uf.dispatchEvent(new Event('change',{bubbles:true}))`);await pause(900);
        await verify('filtro sincronizado com tabela',`Array.from(document.querySelectorAll('[data-row]')).length>0&&Array.from(document.querySelectorAll('[data-row]')).every(r=>r.children[4].textContent.endsWith('/RS'))`);
        await evaluate(`document.querySelector('#atlas-clear').click()`);await pause(800);
        await evaluate(`document.querySelector('[data-view="globe"]').click()`);await pause(1000);
        await verify('globo e ficha preservados',`!!document.querySelector('#atlas-map canvas')&&!!document.querySelector('#side-panel h3')`);
        await evaluate(`document.querySelector('[data-view="map"]').click()`);await pause(800);
        await verify('volta ao mapa',`document.querySelectorAll('#atlas-map .uf').length===27`);
        await evaluate(`document.querySelector('[data-layer="showOfficial"]').click()`);await pause(800);
        await verify('camada desativada limpa selecao',`!!document.querySelector('.panel-empty')&&document.querySelectorAll('#atlas-map .pin,#atlas-map .cluster').length===0`);
        await evaluate(`document.querySelector('[data-layer="showSynthetic"]').click()`);await pause(800);
        await verify('camada sintetica identificada',`document.querySelectorAll('#atlas-map .pin.synthetic').length>0&&document.querySelectorAll('#atlas-map .pin.official').length===0`);
      }
      if(width===1672&&['gov','decision'].includes(route)&&process.env.QA_SUBTABS==='1') {
        const ids=await evaluate(`Array.from(document.querySelectorAll('#content>.tabs [data-tab]')).map(b=>b.dataset.tab)`);
        for(const id of ids){
          await evaluate(`document.querySelector('[data-tab="${id}"]').click();window.scrollTo(0,0)`);await pause(500);
          for(let attempt=0;attempt<30;attempt++){if(await evaluate(`document.querySelector('#content>.tabs .tab.on')?.dataset.tab===${JSON.stringify(id)}&&!document.querySelector('#content>.loading')`))break;await pause(250);}
          const result=await evaluate(`({active:document.querySelector('#content>.tabs .tab.on')?.dataset.tab,width:document.documentElement.scrollWidth,viewport:document.documentElement.clientWidth,error:!!document.querySelector('#content>.err')})`);
          const shot=await send('Page.captureScreenshot',{format:'png'});writeFileSync(`${out}/1672_${id.replace(':','_')}.png`,Buffer.from(shot.data,'base64'));
          if(result.active!==id||result.error||result.width>result.viewport+1)throw new Error('ABA '+id+' '+JSON.stringify(result));
          report.push('ABA OK '+id+' '+JSON.stringify(result));
        }
      }
    }
  }
  await evaluate(`fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})`);
}catch(err){report.push('FALHA '+err.message);process.exitCode=1;}
finally{const suffix=process.env.QA_ROUTES?'-'+process.env.QA_ROUTES.replaceAll(',','-'):'';writeFileSync(out+'/report'+suffix+'.txt',report.join('\n'));console.log(report.join('\n'));ws?.close();child.kill();}
