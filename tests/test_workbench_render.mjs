import {test} from 'node:test';
import assert from 'node:assert/strict';
import {workbenchHtml,summaryHtml} from '../web/js/workbench.js';
import {state,data} from '../web/js/core.js';
const summary={first_access:true,note:'Recorte',events:[],review_events:[],notices:[],watermark:{event_seq:0,audit_seq:0,note_seq:0}};
const fixtures={
 '/api/workbench/projects':[],
 '/api/workbench/summary':summary,
 '/api/workbench/revalidations':{items:[],proposals:[]},
 '/api/workbench/exclusions':{items:[],note:'Sem conclusao de dispensa'}
};
test('painel vazio é renderizado sem exigir projeto ou baseline inexistente',async()=>{
 globalThis.fetch=async url=>new Response(JSON.stringify(fixtures[String(url).split('?')[0]]),{headers:{'Content-Type':'application/json'}});
 const html=await workbenchHtml();assert.match(html,/Nenhum projeto salvo/);assert.match(html,/Comparar duas/);assert.match(html,/Reavaliar/);
});
test('painel com condicionante pendente e projeto escapa texto e oferece os fluxos',async()=>{
 state.workProject='p';data.me={authenticated:true,permissions:['review.transition','review.decide']};
 const r={...fixtures,'/api/workbench/projects':[{id:'p',title:'<script>alert(1)</script>',at:'2026-11-06T20:00:00Z'}],
 '/api/workbench/project':{id:'p',title:'<script>alert(1)</script>',result:{sha256:'hash',as_of:'2026-11-06',topics:['nr20'],candidates:[],missing:[],facts:{},questions:[]},
 conditions:[{id:'b',at:'2026-11-06T20:00:00Z',result:{note:'Verificar',sha256:'hash',document:{},items:[{id:'1',excerpt:'Devera apresentar relatorio',status:'PENDENTE_REVISAO',deadline_text:['30 dias'],missing:['Evento nao informado']}]}}]}};
 globalThis.fetch=async url=>new Response(JSON.stringify(r[String(url).split('?')[0]]),{headers:{'Content-Type':'application/json'}});
 const html=await workbenchHtml();assert.ok(!html.includes('<script>'));assert.match(html,/&lt;script&gt;/);assert.match(html,/license-form/);assert.match(html,/condition-decision/);assert.match(html,/project-link-review/);assert.match(html,/Exportar dossiê/);
});
test('resumo escapa notificações e não marca automaticamente como lidas',()=>{
 const html=summaryHtml({...summary,notices:[{title:'<img src=x onerror=alert(1)>',body:'Texto'}]});assert.ok(!html.includes('<img'));assert.match(html,/data-seen-watermark/);
});
