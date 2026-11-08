import { test } from 'node:test';
import assert from 'node:assert/strict';
import { accountBriefing, accountIntent } from '../web/js/account_assistant.mjs';
const user = { name: 'Ana Silva', kind: 'empresa', function: 'juridico' };
const review = { id: 'anm:A', asset_id: 'A', asset_name: 'Ativo de teste', scenario: 'anm', state: 'DRAFT', assigned_function: 'engenharia', provisions: ['p'], evidence: [], origin: 'CENARIO_HIPOTETICO' };
const provision = { id: 'p', valid_from: '2027-04-22', document: 'Documento', provision: 'Artigo', version: 'v1', sources: ['F40'] };
const brief = (u = user, watched = ['A'], r = review, asOf = '2026-11-06') => accountBriefing(u, [r], watched, {anm:['Laudo']}, [provision], asOf);
test('carteira gera revisão, lacuna e marco com fonte, sem atribuição pessoal falsa', () => {
  const b = brief(); assert.equal(b.name, 'Ana'); assert.deepEqual(b.items.map(x=>x.kind), ['review','evidence','milestone']);
  assert.match(b.items[0].text, /Na carteira/); assert.deepEqual(b.items[2].sources, ['F40']);
});
test('conta comum não recebe itens fora da carteira, nem normas vinculadas a eles', () => assert.equal(brief(user, []).items.length, 0));
test('cidadão não recebe agenda empresarial', () => assert.equal(brief({...user,kind:'cidadao'}).items.length, 0));
test('demo inclui apenas cenários sintéticos fora da carteira', () => {
  assert.equal(brief({...user,is_demo:1}, []).items.length, 3);
  assert.equal(brief({...user,is_demo:1}, [], {...review,origin:'DADO_OFICIAL'}).items.length, 0);
});
test('decisão encerrada não gera pendência e marco passado não aparece como futuro', () => {
  assert.equal(brief(user,['A'],{...review,state:'CLOSED'},'2028-01-01').items.length, 0);
});
test('evidência registrada e atribuição por função respeitadas', () => {
  const b = brief(user,['A'],{...review,assigned_function:'juridico',evidence:[{item:'Laudo'}]});
  assert.equal(b.items.some(x=>x.kind==='evidence'),false); assert.match(b.items[0].text,/Da sua função/);
});
test('intenção pessoal separada de pergunta normativa', () => {
  assert.equal(accountIntent('Quais são minhas pendências?'),'all'); assert.equal(accountIntent('minhas evidências'),'evidence');
  assert.equal(accountIntent('O que falta confirmar?'),'review'); assert.equal(accountIntent('meus prazos'),'milestone');
  assert.equal(accountIntent('Quando a norma entrou em vigor?'),null);
});
