"""Alertas de compliance, denúncia assistida, documentos por cliente, monitoramento hidrológico (ONS) e política de custo da IA."""
import os
os.environ['TORRE_LLM'] = '0'
import base64
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from app import cloud_aws, compliance, denuncia, hidro
from app.cloud_aws import EvidenceVault
from app.store import Store, WorkflowError
from app.tenant import TenantDocs

TODAY = date(2026, 11, 7)
ASSETS = json.load(open('data/assets.json', encoding='utf8'))


class ComplianceTests(unittest.TestCase):
    def test_obligations_become_classified_alerts(self):
        al = {a['id']: a for a in compliance.build(TODAY, ASSETS, [], {})}
        self.assertEqual(al['OB-B01-RPSB']['level'], 'Crítico')            # vencida + segurança
        self.assertEqual(al['OB-B01-EIR-2026-03']['urgency'], 'Vencido')
        self.assertIn('OB-B02-LO', al)                                     # licença vence em ~24 dias
        self.assertNotIn('OB-A01-NR20', al)                                # em dia, com evidência, longe do prazo
        for a in al.values():
            self.assertTrue(a['basis'] and a['action'] and a['consequences'])

    def test_official_watched_dam_alerts(self):
        rec = {'id': 'SIGBM-1', 'name': 'X', 'emergency_level': 'Emergência Nivel 1', 'dce_risr': '2º Campanha 2026 - Não Enviado'}
        al = compliance.build(TODAY, [], [rec], {}, {'itens': []})
        kinds = {a['kind'] for a in al}
        self.assertEqual(kinds, {'emergencia', 'dce'})
        self.assertTrue(all(a['level'] == 'Crítico' for a in al))

    def test_workflow_requires_deadline_evidence_and_role(self):
        s = Store(':memory:')
        desk = compliance.ComplianceDesk(s)
        alerts = compliance.build(TODAY, ASSETS, [], {})
        r = desk.sync(alerts, 'demo')
        self.assertEqual(r['novos'], len(alerts))
        self.assertEqual(desk.sync(alerts, 'demo')['novos'], 0)            # idempotente
        aid = alerts[0]['id']
        with self.assertRaises(WorkflowError):
            desk.transition(aid, 'EM_REGULARIZACAO', 'Ana', 'juridico')       # sem prazo
        desk.transition(aid, 'EM_REGULARIZACAO', 'Ana', 'juridico', regularize_by='2026-11-01')
        with self.assertRaises(WorkflowError):
            desk.transition(aid, 'RESOLVIDO', 'Ana', 'juridico', '')          # sem evidência
        r = desk.sync(alerts, 'demo')                                         # prazo de regularização vencido → escala
        self.assertEqual(r['escalados'], 1)
        with self.assertRaises(WorkflowError):
            desk.transition(alerts[1]['id'], 'DESCARTADO', 'Diego', 'operacao', 'não procede')
        desk.transition(aid, 'RESOLVIDO', 'Ana', 'juridico', 'Protocolo 123')
        self.assertGreaterEqual(len(desk.history(aid)), 3)


class DenunciaTests(unittest.TestCase):
    def test_rules_find_norms_without_llm(self):
        out = denuncia.build('A barragem está abandonada, sem manutenção, com uma trinca e água saindo.', {'id': 'SIGBM-1', 'kind': 'mineracao', 'name': 'X'}, [], TODAY)
        keys = [n['key'] for n in out['normas']]
        self.assertIn('art17a_p2', keys)
        self.assertIn('art18', keys)
        self.assertEqual(out['engine'], 'regras')
        self.assertIn('NÃO FOI ENVIADO', out['body'])

    def test_llm_only_when_rules_fail_and_norms_are_checked(self):
        calls = []
        fake = lambda s, u, sch: (calls.append(1), json.dumps({'fatos': ['Fato.'], 'normas': ['art18', 'INVENTADA'], 'pedidos': ['Verificar.']}))[1]
        denuncia.build('trinca no talude', None, [], TODAY, llm=fake)
        self.assertEqual(calls, [])                                           # regra resolveu: IA não chamada
        out = denuncia.build('algo estranho perto da comunidade', None, [], TODAY, llm=fake)
        self.assertEqual(out['engine'], 'ia')
        self.assertNotIn('INVENTADA', [n['key'] for n in out['normas']])

    def test_confirm_before_forward(self):
        d = denuncia.DenunciaDesk(Store(':memory:'))
        x = d.save('usuario:1', 'SIGBM-1', denuncia.build('trinca', None, [], TODAY), [])
        with self.assertRaises(WorkflowError):
            d.forwarded(x['id'], 'usuario:1', '')
        d.confirm(x['id'], 'usuario:1')
        self.assertEqual(d.forwarded(x['id'], 'usuario:1', 'P-1')['state'], 'ENCAMINHADA_PELO_USUARIO')
        with self.assertRaises(WorkflowError):
            d.get(x['id'], 'usuario:2')                                       # outra conta não vê


class TenantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Store(':memory:')
        self.t = TenantDocs(self.s, EvidenceVault(bucket='', local_root=Path(self.tmp.name)), var_dir=Path(self.tmp.name))
        self.a = {'id': 1, 'kind': 'empresa', 'cnpj': '11222333000181', 'role': 'gestor'}
        self.b = {'id': 2, 'kind': 'empresa', 'cnpj': '99888777000166', 'role': 'gestor'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_isolation_no_names_and_revocation(self):
        up = self.t.upload(self.a, 'relatório.pdf', 'application/pdf', base64.b64encode(b'%PDF teste').decode())
        self.assertTrue(up['customer_id'].startswith('C-'))
        self.assertNotIn('11222333', self.t.list(self.a)['docs'][0]['sha256'])
        key = self.s.db.execute('SELECT vault_key FROM tenant_docs').fetchone()[0]
        self.assertIn(up['customer_id'], key)
        self.assertNotIn('11222333', key)                                     # nome/CNPJ fora do caminho
        with self.assertRaises(WorkflowError):
            self.t.read(self.b, up['id'])                                      # outra organização
        self.assertEqual(self.t.read(self.a, up['id'])[1], b'%PDF teste')
        self.t.set_access(self.a, '1', True)
        with self.assertRaises(WorkflowError):
            self.t.read(self.a, up['id'])

    def test_rejects_bad_files(self):
        with self.assertRaises(WorkflowError):
            self.t.upload(self.a, 'x.exe', 'application/x-msdownload', base64.b64encode(b'MZ').decode())


class HidroTests(unittest.TestCase):
    def test_robust_z_slope_knn(self):
        self.assertAlmostEqual(hidro.slope([float(i) for i in range(30)]), 1.0, places=6)
        hist = [10 + (i % 5) for i in range(100)]
        self.assertGreater(hidro.robust_z(40, hist), 3.5)
        self.assertIsNone(hidro.robust_z(10, hist[:10]))
        pattern = ([100.0] * 14 + [200.0] * 7) * 8 + [100.0] * 14
        k = hidro.knn_analogs(pattern)
        self.assertGreater(k['expected_change_pct'], 50)                      # janelas parecidas foram seguidas de alta

    @unittest.skipUnless((hidro.RAW / 'RESERVATORIOS.csv').exists(), 'snapshot ONS ausente')
    def test_real_snapshot(self):
        st = hidro.compute()
        self.assertGreater(len(st['items']), 100)
        x = st['items'][0]
        self.assertTrue(x['recommendations'] or x['signals'])
        self.assertTrue(all(s['label'] for s in x['signals']))


class CostPolicyTests(unittest.TestCase):
    def setUp(self):
        cloud_aws._CACHE.clear()
        cloud_aws.USAGE.update(dia=None)

    def test_cache_cap_and_tier(self):
        sent = []
        with mock.patch.dict(os.environ, {'TORRE_LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'x', 'TORRE_LLM_MAX_CALLS_DIA': '1'}), \
                mock.patch.object(cloud_aws, 'structured_call', side_effect=lambda *a, **k: (sent.append(k.get('model')), '{"ok":1}')[1]):
            cloud_aws.llm_call('filtros', 's', 'u', {})
            cloud_aws.llm_call('filtros', 's', 'u', {})                       # cache
            with self.assertRaises(RuntimeError):
                cloud_aws.llm_call('perguntas', 's', 'outra', {})              # teto diário
        self.assertEqual(sent, ['gemini-3.5-flash-lite'])                     # tarefa leve → modelo mais barato
        u = cloud_aws.usage()
        self.assertEqual((u['chamadas'], u['cache'], u['teto_atingido']), (1, 1, 1))

    def test_rules_first_for_filters(self):
        from app import ai_tools
        with mock.patch.dict(os.environ, {'TORRE_LLM': '1', 'TORRE_LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'x'}), \
                mock.patch.object(ai_tools, 'parse_llm', side_effect=AssertionError('não deveria chamar IA')):
            it = ai_tools.interpret('órfãs críticas no RN')
        self.assertEqual(it['engine'], 'regras')


if __name__ == '__main__':
    unittest.main()
