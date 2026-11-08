import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
const code=readFileSync(new URL('../web/sw.js',import.meta.url),'utf8');
async function run(offline) {
  const listeners={};let cacheReads=0,cacheWrites=0,pending;
  const ctx={URL,Response,location:{origin:'http://localhost:8766'},self:{addEventListener:(k,f)=>listeners[k]=f},
    fetch:async()=>{if(offline)throw new Error('offline');return new Response('{"owner":1}',{headers:{'Content-Type':'application/json'}});},
    caches:{match:async()=>{cacheReads++;return new Response('{"owner":2}');},open:async()=>({put:()=>{cacheWrites++;}})}};
  vm.runInNewContext(code,ctx);
  listeners.fetch({request:{method:'GET',url:'http://localhost:8766/api/workbench/project?id=private'},respondWith:p=>pending=p});
  const response=await pending;return {status:response.status,body:await response.json(),cacheReads,cacheWrites};
}
test('resultado por conta online nunca é gravado no cache compartilhado',async()=>{
  const r=await run(false);assert.equal(r.status,200);assert.equal(r.body.owner,1);assert.equal(r.cacheWrites,0);assert.equal(r.cacheReads,0);
});
test('sem rede não reapresenta resultado de outra conta em cache',async()=>{
  const r=await run(true);assert.equal(r.status,503);assert.equal(r.body.owner,undefined);assert.equal(r.cacheReads,0);
});
