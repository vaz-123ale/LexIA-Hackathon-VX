import { test } from 'node:test';
import assert from 'node:assert/strict';
import { state } from '../web/js/core.js';
import { denunciaPage, denunciaAnonimaPage, streetMap } from '../web/js/ws_denuncia.js';

test('mapa mostra exemplo distante identificado pela API', () => {
  const html = streetMap([{ id: 'DEMO-ETA', n: 1, nome: 'ETA fictícia', numero: 'ETA', lat: -22.9, lon: -47.06, real: false, longe: true }],
    { lat: -20.253, lon: -43.803 }, null);
  assert.match(html, /data-pick="DEMO-ETA"/);
});

test('endereço disponível e enviado nos fluxos público e autenticado', async () => {
  globalThis.location = { hash: '' };
  globalThis.window = { scrollTo() {} };
  for (const [page, key, anon] of [[denunciaAnonimaPage, 'denA', true], [denunciaPage, 'den', false]]) {
    state[key] = { cat: 'energia', sel: false, endereco: 'Rua <Teste>, 42, Centro', relato: 'Vi um fio caído na calçada perto da escola.', quando: '', data: '', ev: [], editando: true };
    let sent;
    globalThis.fetch = async (url, opts) => {
      if (opts?.method === 'POST') { sent = JSON.parse(opts.body); return new Response(JSON.stringify({ id: 1, analysis: {} })); }
      return new Response(JSON.stringify({ items: [] }));
    };
    const html = await page.render();
    assert.match(html, /id="dn-address"/);
    assert.match(html, /Rua &lt;Teste&gt;, 42, Centro/);
    assert.ok(!html.includes('value="Rua <Teste>'));
    const fields = {
      '#dn-address': { value: 'Rua das Flores, 42, Cidade/MG' },
      '#dn-rel': { value: state[key].relato },
      '#dn-q': { value: '' },
      '#dn-go': {}, '#dn-address-use': {},
    };
    for (const f of Object.values(fields)) f.addEventListener = (event, callback) => { f[event] = callback; };
    const root = { querySelector: s => fields[s] || null, querySelectorAll: () => [] };
    page.mount(root, { rerender() {} });
    fields['#dn-address-use'].click();
    assert.equal(state[key].endereco, fields['#dn-address'].value);
    assert.equal(state[key].sel, false);
    await fields['#dn-go'].click({ target: {} });
    assert.equal(sent.anonimo, anon);
    assert.match(sent.relato, /\(Endereço informado: Rua das Flores, 42, Cidade\/MG\)/);
  }
});
