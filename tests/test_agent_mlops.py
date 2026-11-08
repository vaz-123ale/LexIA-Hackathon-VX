"""Testes do agente autônomo, do ciclo de evolução dos modelos (MLOps) e do módulo de negócio."""
import json
import os
os.environ['TORRE_LLM'] = '0'
os.environ['TORRE_QUIET'] = '1'
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer

from app import risk_model as M, business, server
from app.agent import Agent
from app.mlops import MLOps, psi
from app.store import Store, WorkflowError

TODAY = date(2026, 11, 6)


def synthetic(n=260, seed=1):
    import random
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        bad = rnd.random() < 0.25
        out.append({'id': f'SIGBM-{i}', 'name': f'B{i}', 'uf': 'MG', 'municipio': 'X', 'pnsb': 'Sim', 'owner_cnpj': f'{i % 40:014d}',
                    'emergency_level': 'Emergência Nivel 1' if bad and rnd.random() < .8 else 'Sem emergência',
                    'spillway': '6 - problema' if bad else '0 - ok', 'percolation': '6 - x' if bad and rnd.random() < .5 else '0 - ok',
                    'operational_status': 'Inativa' if bad and rnd.random() < .6 else 'Ativa', 'dpa': 'Alta' if i % 3 == 0 else 'Baixa',
                    'dce_risr': '2º Campanha 2026 - Não Atestado' if bad and rnd.random() < .7 else '2º Campanha 2026 - Atestado',
                    'downstream_population': 'Existente' if i % 4 == 0 else 'Inexistente', 'people_affected': '101-500' if i % 4 == 0 else None})
    return out


class TargetsTests(unittest.TestCase):
    def test_dce_target_trains_without_leaky_field(self):
        o = M.run(synthetic(), TODAY, target='dce')
        self.assertTrue(o['available'])
        self.assertGreater(o['metrics']['cv_auc'], 0.75)
        self.assertTrue(all(not o['by_id'][i]['positive'] for i in o['flagged']))  # só atestadas hoje são “previsão”

    def test_feedback_changes_labels_but_metrics_use_official(self):
        recs = synthetic()
        base = M.run(recs, TODAY)
        flagged = base['flagged'][:3]
        with_fb = M.run(recs, TODAY, feedback={i: 0 for i in flagged})
        self.assertEqual(with_fb['feedback_used'], 3)
        self.assertTrue(all(i not in with_fb['flagged'] for i in flagged))  # “não procede” não volta a ser alerta
        self.assertEqual(base['positives'], with_fb['positives'])


class MLOpsCycle(unittest.TestCase):
    def setUp(self):
        self.s = Store(':memory:')
        self.ml = MLOps(self.s)
        self.recs = synthetic()

    def test_bootstrap_feedback_retrain_compare_promote(self):
        self.ml.bootstrap(self.recs, TODAY, 'snap-1')
        ch = self.ml.champion('emergencia')
        self.assertEqual(ch['status'], 'campeao')
        with self.assertRaises(WorkflowError):
            self.ml.add_feedback('emergencia', 'SIGBM-1', 1, '', 'Carla')  # evidência obrigatória
        for i in ch['summary']['flagged'][:3]:
            self.ml.add_feedback('emergencia', i, 1, 'vistoria', 'Carla')
        mon = self.ml.monitor('emergencia', self.recs)
        self.assertTrue(mon['retrain_recommended'])
        self.assertEqual(mon['field_precision'], 1.0)
        cd = self.ml.train('emergencia', self.recs, TODAY, 'snap-1', 'agente')
        self.assertEqual(cd['status'], 'desafiante')
        self.assertEqual(cd['feedback_used'], 3)
        self.assertIsNotNone(self.ml.compare('emergencia'))
        with self.assertRaises(WorkflowError):
            self.ml.promote(cd['id'], 'Bruno', '')
        self.ml.promote(cd['id'], 'Bruno', 'Incorpora vistorias')
        self.assertEqual(self.ml.champion('emergencia')['id'], cd['id'])
        self.assertEqual(self.ml.version(ch['id'])['status'], 'aposentado')
        self.assertTrue(self.s.verify_chain()['ok'])

    def test_psi_detects_drift(self):
        self.assertAlmostEqual(psi({'a': .5, 'b': .5}, {'a': .5, 'b': .5}), 0.0)
        self.assertGreater(psi({'a': .9, 'b': .1}, {'a': .1, 'b': .9}), 0.25)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.s = Store(':memory:')
        self.ml = MLOps(self.s)
        recs = synthetic()
        items = [{'id': r['id'], 'kind': 'mineracao', 'name': r['name'], 'uf': 'MG', 'municipio': 'X', 'attention': 'Moderada', 'dpa': r['dpa'],
                  'consequence': {'items': ['População permanente a jusante'] if r['downstream_population'] == 'Existente' else []}} for r in recs]
        self.ctx = {'records': recs, 'items': items, 'today': TODAY, 'sigbm_snapshot': 's1', 'snisb_snapshot': 'n1'}
        self.ml.bootstrap(recs, TODAY, 's1')
        self.agent = Agent(self.s, self.ml, lambda: self.ctx)

    def test_run_creates_pending_actions_only(self):
        r = self.agent.run('teste')
        tools = [s['tool'] for s in r['steps']]
        self.assertEqual(tools[:2], ['verificar_fontes', 'monitorar_modelos'])
        self.assertIn('propor_acoes', tools)
        pend = self.agent.actions('PENDENTE')
        self.assertTrue(pend and all(a['kind'] == 'conferir' for a in pend))
        # segunda execução não duplica propostas pendentes
        self.agent.run('teste2')
        self.assertEqual(len(self.agent.actions('PENDENTE')), len(pend))

    def test_rejection_feeds_model_and_approval_starts_plan(self):
        self.agent.run('t')
        a, b = self.agent.actions('PENDENTE')[:2]
        with self.assertRaises(WorkflowError):
            self.agent.decide(a['id'], True, 'Ana', '', {})
        out = self.agent.decide(a['id'], True, 'Ana', 'vamos conferir', {})
        self.assertIn('confirmar', out['effect'])
        self.assertEqual(self.s.plan_progress(a['dam_id'])['confirmar']['status'], 'em_andamento')
        self.agent.decide(b['id'], False, 'Ana', 'já vistoriada', {'label_rejection': True})
        self.assertEqual(self.ml.feedback_map('emergencia').get(b['dam_id']), 0)

    def test_full_loop_proposes_promotion(self):
        for i in self.ml.champion('emergencia')['summary']['flagged'][:3]:
            self.ml.add_feedback('emergencia', i, 1, 'vistoria', 'Carla')
        r = self.agent.run('loop')
        self.assertIn('emergencia', r['steps'][2]['output'])  # retreinou
        kinds = [a['kind'] for a in self.agent.actions('PENDENTE')]
        self.assertTrue('promover_modelo' in kinds or self.ml.compare('emergencia')['recommendation'] == 'manter campeão')

    def test_llm_planner_failure_falls_back(self):
        def bad(*a):
            raise RuntimeError('sem rede')
        ag = Agent(self.s, self.ml, lambda: self.ctx, llm_planner=bad)
        r = ag.run('t')
        self.assertEqual(r['planner'], 'regras')
        self.assertTrue(any(s['tool'] == 'planejador_ia' and s.get('error') for s in r['steps']))


class BusinessTests(unittest.TestCase):
    def test_segments_and_social_from_data(self):
        recs = synthetic()
        seg = business.segments(recs)
        self.assertEqual(seg['total_owners'], 40)
        pr = business.people_range([{'people_affected': '101-500'}, {'people_affected': 'acima de 5001'}])
        self.assertEqual(pr, {'min': 5102, 'max': 5501, 'open_top': True})

    def test_assumptions_are_labeled(self):
        with open('data/business_assumptions.json', encoding='utf8') as fh:
            a = json.load(fh)
        self.assertIn('PREMISSAS', a['warning'])


class AgentHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.load_official()
        cls.store = Store(':memory:'); server.seed(cls.store)
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(cls.store))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def call(self, path, body=None, token=None):
        h = {'Content-Type': 'application/json'}
        if token:
            h['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_agent_and_models_endpoints(self):
        self.assertEqual(self.call('/api/agent/run', {'x': 1}, 'demo-auditor')[0], 403)
        st, r = self.call('/api/agent/run', {'x': 1}, 'demo-curador')
        self.assertEqual(st, 200)
        st, a = self.call('/api/agent')
        self.assertTrue(a['pending'])
        st, m = self.call('/api/ml/models')
        self.assertEqual(set(m), {'emergencia', 'dce'})
        self.assertEqual(m['dce']['champion']['status'], 'campeao')
        st, p = self.call('/api/ml/predictions?target=dce')
        self.assertTrue(p['available'] and p['metrics']['cv_auc'] > 0.6)
        dam = a['pending'][0]['dam_id']
        self.assertEqual(self.call('/api/ml/feedback', {'target': 'dce', 'dam_id': dam, 'label': 1, 'reason': 'ok'}, 'demo-financas')[0], 403)
        self.assertEqual(self.call('/api/ml/feedback', {'target': 'dce', 'dam_id': dam, 'label': 1, 'reason': 'vistoria'}, 'demo-engenharia')[0], 200)

    def test_business_endpoint(self):
        self.assertEqual(self.call('/api/business', token='demo-juridico')[0], 403)   # material interno: cliente não vê
        st, b = self.call('/api/business', token='demo-curador')
        self.assertEqual(st, 200)
        self.assertEqual(b['market']['beachhead']['owners'], 301)
        self.assertGreater(b['market']['sam_expansion']['owners'], 1000)
        self.assertLessEqual(b['social']['people_declared_range']['min'], b['social']['people_declared_range']['max'])
        # modelo de negócio vem do estudo de mercado (planilhas reproduzíveis)
        self.assertEqual(b['estudo']['painel']['SAM mineral em contas']['base'], 89)
        eq = {x['clientes']: x['resultado'] for x in b['estudo']['equilibrio']}
        self.assertLess(eq[12], 0); self.assertGreater(eq[13], 0)  # equilíbrio em 13 clientes


if __name__ == '__main__':
    unittest.main()
