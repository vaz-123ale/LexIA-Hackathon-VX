"""Testes v4: contas (cidadão/empresa), sessões por cookie, carteira, notificações, insight,
monitor de fontes (com rede falsa) e origem das requisições."""
import json
import os
os.environ['TORRE_LLM'] = '0'
os.environ['TORRE_QUIET'] = '1'
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from app.store import Store, WorkflowError
from app.accounts import Accounts, valid_cnpj, hash_pw
from app.monitor import Monitor, normalize
from app import server


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.acc = Accounts(Store(':memory:'))

    def test_cnpj_validation(self):
        self.assertTrue(valid_cnpj('11.222.333/0001-81'))
        self.assertFalse(valid_cnpj('11.222.333/0001-82'))
        self.assertFalse(valid_cnpj('00000000000000'))

    def test_password_is_hashed(self):
        u = self.acc.register({'kind': 'cidadao', 'name': 'Maria', 'email': 'maria@ex.com', 'password': 'segura123', 'consent': True})
        row = self.acc.db.execute('SELECT pw_hash, pw_salt FROM users WHERE id=?', (u['id'],)).fetchone()
        self.assertNotIn('segura123', row['pw_hash'])
        self.assertEqual(hash_pw('segura123', row['pw_salt'])[1], row['pw_hash'])

    def test_register_validations(self):
        bad = [{'kind': 'x'}, {'kind': 'cidadao', 'name': 'A', 'email': 'a@b.co', 'password': 'abc12345', 'consent': True},
               {'kind': 'cidadao', 'name': 'Ana', 'email': 'nao-email', 'password': 'abc12345', 'consent': True},
               {'kind': 'cidadao', 'name': 'Ana', 'email': 'a@b.co', 'password': 'curta1', 'consent': True},
               {'kind': 'cidadao', 'name': 'Ana', 'email': 'a@b.co', 'password': 'semnumero', 'consent': True},
               {'kind': 'cidadao', 'name': 'Ana', 'email': 'a@b.co', 'password': 'abc12345'},
               {'kind': 'empresa', 'name': 'Ana', 'email': 'a@b.co', 'password': 'abc12345', 'consent': True, 'function': 'juridico', 'org_name': 'X SA', 'cnpj': '123'}]
        for d in bad:
            with self.assertRaises(WorkflowError, msg=str(d)):
                self.acc.register(d)

    def test_company_role_from_function_and_login_kind(self):
        u = self.acc.register({'kind': 'empresa', 'name': 'Rui', 'email': 'rui@ex.com', 'password': 'abc12345', 'consent': True,
                               'function': 'operacao', 'org_name': 'Exemplo SA', 'cnpj': '11222333000181'})
        self.assertEqual(u['role'], 'operacao')
        with self.assertRaises(WorkflowError):
            self.acc.login('rui@ex.com', 'abc12345', 'cidadao')
        token, user = self.acc.login('rui@ex.com', 'abc12345', 'empresa')
        self.assertEqual(self.acc.session_user(token)['email'], 'rui@ex.com')
        self.acc.logout(token)
        self.assertIsNone(self.acc.session_user(token))

    def test_duplicate_and_wrong_password(self):
        self.acc.register({'kind': 'cidadao', 'name': 'Bia', 'email': 'bia@ex.com', 'password': 'abc12345', 'consent': True})
        with self.assertRaises(WorkflowError):
            self.acc.register({'kind': 'cidadao', 'name': 'Bia', 'email': 'BIA@ex.com', 'password': 'abc12345', 'consent': True})
        with self.assertRaises(WorkflowError):
            self.acc.login('bia@ex.com', 'errada123')

    def test_watchlist_and_notifications(self):
        u = self.acc.register({'kind': 'cidadao', 'name': 'Leo', 'email': 'leo@ex.com', 'password': 'abc12345', 'consent': True})
        self.assertEqual(self.acc.watch(u['id'], 'SIGBM-1'), ['SIGBM-1'])
        self.assertEqual(self.acc.watch(u['id'], 'SIGBM-1', add=False), [])
        n = self.acc.notify('empresa', 'norma', 'Só empresas', 'x')
        self.acc.notify('todos', 'dados', 'Para todos', 'y')
        mine = self.acc.notifications(u)
        self.assertEqual([i['title'] for i in mine['items']], ['Para todos'])
        self.assertEqual(mine['unread'], 1)
        self.acc.mark_read(u['id'], [mine['items'][0]['id']])
        self.assertEqual(self.acc.notifications(u)['unread'], 0)
        self.assertNotIn(n, [i['id'] for i in mine['items']])


class FakeSigbm:
    def __init__(self, listed='11/6/2026 6:18 AM', size='100'):
        self.listed, self.size, self.fetched = listed, size, 0

    def load_schema(self):
        return {'listing_url': 'https://dadosabertos.anm.gov.br/SIGBM/'}

    def fetch_listing(self):
        return [{'name': 'Barragens.csv', 'listed_at': self.listed, 'bytes': self.size}]

    def fetch(self):
        self.fetched += 1
        return {'snapshot_id': 'sigbm-novo', 'quality': {'accepted': 10, 'rejected': 0}}


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.acc = Accounts(Store(':memory:'))
        self.pages = {'https://www.gov.br/robots.txt': (200, b'User-agent: *\nDisallow: /proibido/\n', 'text/plain'),
                      'https://www.gov.br/a': (200, b'<html><script>var t=1</script><p>Norma A</p></html>', 'text/html'),
                      'https://www.gov.br/proibido/b': (200, b'x', 'text/html')}
        self.sources = [{'id': 'S1', 'title': 'A', 'url': 'https://www.gov.br/a', 'verification': 'T'},
                        {'id': 'S2', 'title': 'B', 'url': 'https://www.gov.br/proibido/b', 'verification': 'C'},
                        {'id': 'S3', 'title': 'C', 'url': 'https://empresa.com/c', 'verification': 'T'},
                        {'id': 'S4', 'title': 'D', 'url': 'https://www.gov.br/d', 'verification': 'I'}]
        self.sig = FakeSigbm()
        self.synced = []
        self.mon = Monitor(self.acc, self.sources, [], self.sig, lambda: self.synced.append(1), delay=0, fetch=lambda u, timeout=20: self.pages[u])

    def test_only_official_and_verified_targets(self):
        self.assertEqual([t['id'] for t in self.mon.targets], ['S1', 'S2'])

    def test_robots_respected(self):
        self.mon.run_once({'listing_entry': {'listed_at': '11/6/2026 6:18 AM', 'bytes': '100'}})
        st = {s['target_id']: s['status'] for s in self.acc.monitor_status()}
        self.assertEqual(st['S2'], 'BLOQUEADO_ROBOTS')
        self.assertEqual(st['S1'], 'OK')

    def test_change_detection_ignores_scripts_and_notifies(self):
        m = {'listing_entry': {'listed_at': '11/6/2026 6:18 AM', 'bytes': '100'}}
        self.mon.run_once(m)
        self.pages['https://www.gov.br/a'] = (200, b'<html><script>var t=999</script><p>Norma A</p></html>', 'text/html')
        self.mon.run_once(m)
        self.assertEqual(self.acc.notifications(None)['items'], [])  # só script mudou: sem alerta
        self.pages['https://www.gov.br/a'] = (200, b'<html><p>Norma A alterada</p></html>', 'text/html')
        r = self.mon.run_once(m)
        self.assertEqual(r['changed'], 1)
        notes = self.acc.notifications({'id': 0, 'kind': 'empresa'})['items']
        self.assertTrue(any('Mudança detectada' in n['title'] and 'Requer curadoria' in n['body'] for n in notes))

    def test_sigbm_new_version_triggers_sync(self):
        self.sig.listed = '11/7/2026 6:18 AM'
        r = self.mon.run_once({'listing_entry': {'listed_at': '11/6/2026 6:18 AM', 'bytes': '100'}})
        self.assertTrue(r['sigbm']['changed'])
        self.assertEqual(self.sig.fetched, 1)
        self.assertEqual(self.synced, [1])

    def test_normalize(self):
        self.assertEqual(normalize(b'<p>a</p>\n\n<style>x</style><b> b </b>', 'text/html'), b'a b')
        self.assertEqual(normalize(b'%PDF-1.4 x', 'application/pdf'), b'%PDF-1.4 x')


class HttpAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store(':memory:'); server.seed(cls.store)
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(cls.store))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def call(self, path, body=None, cookie=None, origin=None):
        h = {'Content-Type': 'application/json'}
        if cookie:
            h['Cookie'] = cookie
        if origin:
            h['Origin'] = origin
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read()), r.headers.get('Set-Cookie', '')
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read()), ''

    def login(self, email, kind=None):
        st, j, sc = self.call('/api/auth/login', {'email': email, 'password': 'LexIA2026demo', 'kind': kind})
        self.assertEqual(st, 200, j)
        self.assertIn('HttpOnly', sc)
        return sc.split(';')[0]

    def test_demo_accounts_login_and_me(self):
        ck = self.login('ana@demo.lexia.app', 'empresa')
        st, me, _ = self.call('/api/auth/me', cookie=ck)
        self.assertTrue(me['authenticated'])
        self.assertEqual(me['user']['role'], 'juridico')
        self.assertNotIn('pw_hash', json.dumps(me))
        st, me, _ = self.call('/api/auth/me')
        self.assertFalse(me['authenticated'])

    def test_register_sets_session(self):
        st, j, sc = self.call('/api/auth/register', {'kind': 'cidadao', 'name': 'Teste', 'email': 'novo@ex.com', 'password': 'abc12345', 'consent': True})
        self.assertEqual(st, 201)
        self.assertEqual(j['user']['kind'], 'cidadao')
        self.assertIn('torre_session=', sc)

    def test_citizen_cannot_mutate_workflow_but_can_watch(self):
        ck = self.login('joana@demo.lexia.app', 'cidadao')
        self.assertEqual(self.call('/api/reviews/open', {'finding_id': 'nr20:A-01'}, cookie=ck)[0], 403)
        st, j, _ = self.call('/api/watchlist', {'asset_id': 'A-01'}, cookie=ck)
        self.assertEqual((st, j['items']), (200, ['A-01']))

    def test_session_actor_is_recorded(self):
        ck = self.login('diego@demo.lexia.app')
        st, r, _ = self.call('/api/reviews/transition', {'review_id': 'nr20:A-05', 'to_state': 'REVIEW_PENDING', 'reason': 'encaminhar', 'source_version': 'v'}, cookie=ck)
        self.assertEqual(st, 200)
        self.assertEqual(r['transitions'][-1]['actor'], 'Diego (operação, demo)')

    def test_cross_origin_post_blocked(self):
        self.assertEqual(self.call('/api/auth/login', {'email': 'x', 'password': 'y'}, origin='https://site-malicioso.com')[0], 403)

    def test_logout(self):
        ck = self.login('bruno@demo.lexia.app')
        st, _, sc = self.call('/api/auth/logout', {'x': 1}, cookie=ck)
        self.assertIn('Max-Age=0', sc)
        self.assertFalse(self.call('/api/auth/me', cookie=ck)[1]['authenticated'])

    def test_executive_insight_and_portfolio(self):
        st, ex, _ = self.call('/api/executive')
        self.assertEqual(len(ex['metrics']), 4)
        self.assertEqual(sum(ex['triage'].values()), 12)
        st, ins, _ = self.call('/api/insight')
        self.assertEqual(ins['generated_by'], 'Regras')  # sem LLM, não se rotula como IA
        self.assertIn('05/01/2027', ins['text'])  # próximo marco do Grupo Exemplo: fim da consulta ANP 21/2026
        self.assertIn('ativo(s) de Grupo Exemplo', ins['text'])
        st, vale, _ = self.call('/api/insight?org=vale')
        self.assertIn('22/04/2027', vale['text'])
        st, petro, _ = self.call('/api/insight?org=petrobras')
        self.assertIn('não tem ativos conectados', petro['text'])

    def test_organization_context(self):
        st, orgs, _ = self.call('/api/organizations')
        by = {o['id']: o for o in orgs['items']}
        self.assertEqual(by['demo']['nature'], 'FICTICIA')
        self.assertEqual(by['petrobras']['asset_count'], 0)
        st, ex, _ = self.call('/api/executive?org=petrobras')
        self.assertEqual(ex['portfolio'], [])
        self.assertIsNone(ex['metrics'][3]['value'])  # sem ativos: não inventa número
        st, ex, _ = self.call('/api/executive?org=demo')
        self.assertTrue(all(a['organization'] == 'Grupo Exemplo S.A. (fictício)' for a in ex['portfolio'] if a['origin'] == 'CENARIO_HIPOTETICO'))

    def test_monitor_endpoint_lists_blocked_channels(self):
        st, m, _ = self.call('/api/monitor')
        self.assertEqual({c['id'] for c in m['blocked_channels']}, {'DOU_SITE', 'LEXML'})


if __name__ == '__main__':
    unittest.main()
