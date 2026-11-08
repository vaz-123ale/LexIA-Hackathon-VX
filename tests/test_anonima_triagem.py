import os as _os
_os.environ['TORRE_LLM'] = '0'
import unittest

from app import triagem
from app.accounts import Accounts
from app.store import Store, WorkflowError


class TriagemTests(unittest.TestCase):
    def setUp(self):
        self.st = Store(':memory:')
        self.acc = Accounts(self.st)
        self.gestor = {'id': 1, 'name': 'Gestora', 'function': 'financas', 'kind': 'empresa'}

    def test_repasse_avisa_area_e_fica_registrado(self):
        r = triagem.repassar(self.st, self.acc, self.gestor, '11222333', 'mudanca', 'res220', 'Resolução ANM 220', 'juridico', 'Avaliar prazos')
        self.assertEqual(r['para_rotulo'], 'Jurídico')
        itens = triagem.listar(self.st, '11222333', 'mudanca')
        self.assertEqual((itens[0]['ref'], itens[0]['de_nome'], itens[0]['nota']), ('res220', 'Gestora', 'Avaliar prazos'))
        with self.acc.lock:
            n = self.acc.db.execute("SELECT audience FROM notifications WHERE kind='repasse'").fetchone()
        self.assertEqual(n['audience'], 'orgfunc:11222333:juridico')

    def test_outra_org_nao_ve(self):
        triagem.repassar(self.st, self.acc, self.gestor, '11222333', 'alerta', 'A1', 'Alerta', 'engenharia', '')
        self.assertEqual(triagem.listar(self.st, '99999999'), [])

    def test_validacoes(self):
        with self.assertRaises(WorkflowError):
            triagem.repassar(self.st, self.acc, self.gestor, 'org', 'alerta', 'A1', 'x', 'inexistente', '')
        with self.assertRaises(WorkflowError):
            triagem.repassar(self.st, self.acc, self.gestor, 'org', 'tipo_ruim', 'A1', 'x', 'juridico', '')
        with self.assertRaises(WorkflowError):
            triagem.repassar(self.st, self.acc, self.gestor, 'org', 'alerta', 'A1', 'x', 'financas', '')   # já é da área


class AnonimaServidorTests(unittest.TestCase):
    """Denúncia anônima ponta a ponta pela API (servidor em memória)."""
    @classmethod
    def setUpClass(cls):
        import threading, tempfile
        from http.server import ThreadingHTTPServer
        from app import server
        cls.tmp = tempfile.TemporaryDirectory()
        st = Store(':memory:')
        acc = Accounts(st)
        from app.monitor import Monitor
        handler = server.make_handler(st, acc, None) if 'monitor' in server.make_handler.__code__.co_varnames[:3] else server.make_handler(st, acc)
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def call(self, path, body=None):
        import json, urllib.request
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json'})
        try:
            r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def test_anonima_com_codigo(self):
        s, r = self.call('/api/denuncia', {'anonimo': True, 'categoria': 'saneamento', 'relato': 'Ontem a água da torneira veio com cor estranha e cheiro forte no bairro todo.'})
        self.assertEqual(s, 201)
        cod = r['codigo_acompanhamento']
        self.assertRegex(cod, r'^LX-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$')
        self.assertEqual(self.call('/api/denuncia', {'action': 'confirm', 'id': r['id'], 'anonimo': True})[0], 400)        # sem código, não confirma
        s2, c = self.call('/api/denuncia', {'action': 'confirm', 'id': r['id'], 'anonimo': True, 'codigo': cod, 'identificar': True})
        self.assertEqual(s2, 200)
        s3, d = self.call('/api/denuncia-anonima?codigo=' + cod)
        self.assertEqual((s3, d['state']), (200, 'CONFIRMADA'))
        self.assertTrue(d['owner'].startswith('anonimo:') and cod not in d['owner'])                           # só o hash fica guardado
        self.assertEqual(self.call('/api/denuncia-anonima?codigo=LX-0000-0000-0000')[0], 404)


if __name__ == '__main__':
    unittest.main()


class NotificacoesPorPerfilTests(unittest.TestCase):
    def setUp(self):
        self.acc = Accounts(Store(':memory:'))
        self.u = self.acc.register({'kind': 'empresa', 'name': 'Ana', 'email': 'ana@x.com.br', 'password': 'Senha1234', 'consent': True,
                                    'function': 'juridico', 'org_name': 'Grupo', 'cnpj': '11222333000181'})
        n = self.acc.notify
        n('empresa', 'dados', 'ANM publicou nova versão do SIGBM', '', '#/gov', 'X')
        n('empresa', 'norma', 'Mudança detectada: Diário Oficial da União', '', '#/gov', 'X')
        n('org:99888777', 'denuncia', 'Denúncia recebida sobre Subestação', '', '#/compliance', 'X')
        n('orgfunc:99888777:juridico', 'ativos', 'Energia Exemplo: inspeção vencida', '', '#/ativos?empresa=demo-energia', 'X')
        n('orgfunc:11222333:juridico', 'ativos', 'Mineração Exemplo: revisão vencida', '', '#/ativos?empresa=demo-mineracao', 'X')

    def titulos(self, perfil):
        return {x['title'] for x in self.acc.notifications(self.u, perfil=perfil)['items']}

    def test_energia_ve_so_energia_e_gerais(self):
        t = self.titulos({'cid': 'demo-energia', 'root': '99888777', 'setor': 'energia'})
        self.assertEqual(t, {'Mudança detectada: Diário Oficial da União', 'Denúncia recebida sobre Subestação', 'Energia Exemplo: inspeção vencida'})

    def test_mineracao_ve_so_mineracao_e_gerais(self):
        t = self.titulos({'cid': 'demo-mineracao', 'root': '11222333', 'setor': 'mineracao'})
        self.assertEqual(t, {'ANM publicou nova versão do SIGBM', 'Mudança detectada: Diário Oficial da União', 'Mineração Exemplo: revisão vencida'})
