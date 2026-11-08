"""Testes v3: conector SIGBM (fixture, sem rede), schema drift, coordenadas, entidades, quatro eixos,
temporalidade com dados oficiais, RBAC nas mutações, Decision Pack, Decision Lab e diff."""
import json
import os
os.environ['TORRE_LLM'] = '0'
os.environ['TORRE_QUIET'] = '1'
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.connectors import sigbm
from app.entities import build_registry, search
from app.assessment import assess, analyze_official_anm, explanation
from app.engine import analyze
from app.finance import evaluate
from app.diff import scenario_diffs, diff
from app.store import Store
from app import server

FIX = Path(__file__).resolve().parent / 'fixtures'
DATA = Path(__file__).resolve().parents[1] / 'data'
PROV = {p['id']: p for p in json.loads((DATA / 'provisions.json').read_text(encoding='utf8'))}
ASSETS = {a['id']: a for a in json.loads((DATA / 'assets.json').read_text(encoding='utf8'))}


class SigbmConnectorTests(unittest.TestCase):
    def setUp(self):
        self.parsed = sigbm.parse((FIX / 'sigbm_sample.csv').read_bytes(), 'snap-teste')
        self.by = {r['official_id']: r for r in self.parsed['records']}

    def test_dms_parsing(self):
        self.assertAlmostEqual(sigbm.parse_dms("-20°10'00.000''"), -20.166667, places=5)
        self.assertAlmostEqual(sigbm.parse_dms("00°52'25.600''"), 0.873778, places=5)
        self.assertIsNone(sigbm.parse_dms("-13°69'40.142''"))
        self.assertIsNone(sigbm.parse_dms('abc'))

    def test_counts_rejections_and_duplicates(self):
        q = self.parsed['quality']
        self.assertEqual(q['rows_read'], 8)
        self.assertEqual(q['accepted'], 4)          # 1001, 1002, 1003, 1007
        self.assertEqual(q['duplicates'], 1)        # 1001 repetido
        self.assertEqual(q['rejected'], 3)          # minutos>=60, hemisfério incoerente, fora do Brasil
        reasons = ' '.join(r for x in q['rejected_rows'] for r in x['reasons'])
        self.assertIn('minutos/segundos', reasons)
        self.assertIn('hemisfério', reasons)
        self.assertIn('território', reasons)

    def test_encoding_and_delimiter_detection(self):
        self.assertEqual(self.parsed['quality']['encoding_detected'], 'cp1252')
        self.assertEqual(self.parsed['quality']['delimiter_detected'], ',')
        self.assertTrue(self.parsed['quality']['metadata_divergence'])
        semi = sigbm.parse((FIX / 'sigbm_semicolon.csv').read_bytes())
        self.assertEqual(semi['quality']['delimiter_detected'], ';')
        self.assertEqual(semi['quality']['accepted'], 2)
        self.assertEqual(self.by['1001']['municipio'], 'CIDADE A')

    def test_schema_drift_is_detected(self):
        with self.assertRaises(sigbm.SchemaDriftError):
            sigbm.parse((FIX / 'sigbm_schema_drift.csv').read_bytes())

    def test_personal_data_hidden(self):
        r = self.by['1003']
        self.assertEqual(r['owner_doc_type'], 'CPF_MASCARADO_OCULTO')
        self.assertIsNone(r['owner_cnpj'])
        self.assertNotIn('JOAO', r['owner_name'])
        self.assertNotIn('123456', json.dumps(self.parsed['records']))

    def test_missing_value_dash_is_none(self):
        self.assertIsNone(self.by['1007']['pnsb'])
        self.assertIn('pnsb ausente', self.by['1007']['data_quality'])

    def test_categories_are_not_numbers(self):
        self.assertIn(self.by['1001']['dpa'], ('Baixa', 'Média', 'Alta'))
        self.assertIn(self.by['1001']['cri'], ('Baixa', 'Média', 'Alta'))

    def test_snapshot_roundtrip_offline(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            m = sigbm.save_snapshot((FIX / 'sigbm_sample.csv').read_bytes(), {'fetched_at': '2026-11-06T10:00:00+00:00', 'source_url': 'fixture'}, tmp)
            self.assertEqual(len(m['sha256']), 64)
            snap = sigbm.latest(tmp)
            self.assertEqual(snap['manifest']['snapshot_id'], m['snapshot_id'])
            self.assertEqual(len(snap['records']), 4)
        finally:
            shutil.rmtree(tmp)

    def test_real_snapshot_shipped_if_present(self):
        snap = sigbm.latest()
        if not snap:
            self.skipTest('sem snapshot real local')
        q = snap['manifest']['quality']
        self.assertEqual(q['accepted'] + q['rejected'] + q['duplicates'], q['rows_read'])
        self.assertEqual(len(snap['records']), q['accepted'])
        self.assertTrue(all(-34.8 <= r['lat'] <= 5.4 for r in snap['records']))


class EntityTests(unittest.TestCase):
    def setUp(self):
        self.orgs = build_registry(sigbm.parse((FIX / 'sigbm_sample.csv').read_bytes())['records'])

    def test_textual_match_is_not_a_link(self):
        res = search('Vale', self.orgs)
        self.assertTrue(res)
        self.assertTrue(all(r['match'] == 'TEXTUAL' and r['link_status'] == 'A_CONFIRMAR' for r in res))
        self.assertTrue(all(r['entity_match_confidence'] < 0.6 for r in res))

    def test_cnpj_exact_and_root(self):
        exact = search('11.222.333/0001-81', self.orgs)
        self.assertEqual(exact[0]['match'], 'CNPJ_IDENTICO')
        root = search('11222333', self.orgs)
        self.assertEqual({r['match'] for r in root}, {'RAIZ_CNPJ'})
        self.assertEqual(len(root), 2)  # dois estabelecimentos da mesma raiz

    def test_person_not_searchable(self):
        self.assertEqual(search('JOAO', self.orgs), [])


class AxesTests(unittest.TestCase):
    W = date(2026, 11, 6)

    def test_axes_are_independent(self):
        f = analyze(ASSETS['B-01'], 'anm', self.W).payload()
        ax = assess(f, None, PROV, self.W)
        self.assertEqual(ax['applicability_assessment'], 'candidate_review')
        self.assertEqual(ax['workflow_state'], 'not_assigned')
        self.assertEqual(set(ax['normative_lifecycle'].values()), {'published_not_effective'})
        self.assertIn(ax['priority']['level'], ('urgent', 'high', 'medium', 'low'))
        self.assertFalse(ax['priority']['uses_official_risk_category'])

    def test_missing_attribute_never_becomes_not_applicable(self):
        f = analyze(ASSETS['A-02'], 'nr20', self.W).payload()
        ax = assess(f, None, PROV, self.W)
        self.assertEqual(ax['applicability_assessment'], 'missing_attributes')
        self.assertTrue(ax['next_action'].startswith('Coletar dados'))

    def test_scope_vs_no_link(self):
        self.assertEqual(assess(analyze(ASSETS['A-03'], 'nr20').payload(), None, PROV, self.W)['applicability_assessment'], 'excluded_by_scope')
        self.assertEqual(assess(analyze(ASSETS['B-03'], 'anm').payload(), None, PROV, self.W)['applicability_assessment'], 'no_supported_link')

    def test_human_decision_changes_applicability(self):
        f = analyze(ASSETS['A-01'], 'nr20').payload()
        self.assertEqual(assess(f, {'state': 'CONFIRMED'}, PROV, self.W)['applicability_assessment'], 'confirmed_applicable_by_human')
        self.assertEqual(assess(f, {'state': 'REJECTED'}, PROV, self.W)['applicability_assessment'], 'rejected_by_human')

    def test_consultation_is_proposed(self):
        ax = assess(analyze(ASSETS['D-01'], 'anp_cp21').payload(), None, PROV, self.W)
        self.assertEqual(ax['primary_lifecycle'], 'proposed')
        self.assertIn('Monitorar', ax['next_action'])

    def test_priority_does_not_use_cri(self):
        rec = {'id': 'SIGBM-1', 'official_id': '1', 'snapshot_id': 's', 'pnsb': 'Não', 'operational_status': 'Ativa', 'cri': 'Alta', 'dpa': 'Alta'}
        rec2 = {**rec, 'cri': 'Baixa', 'dpa': 'Baixa'}
        a = assess(analyze_official_anm(rec, self.W, '2026-11-06T00:00:00+00:00'), None, PROV, self.W, extra=rec)
        b = assess(analyze_official_anm(rec2, self.W, '2026-11-06T00:00:00+00:00'), None, PROV, self.W, extra=rec2)
        self.assertEqual(a['priority'], b['priority'])


class OfficialTemporalTests(unittest.TestCase):
    rec = {'id': 'SIGBM-1001', 'official_id': '1001', 'snapshot_id': 's', 'pnsb': 'Sim', 'operational_status': 'Ativa'}
    obs = '2026-11-06T19:53:13+00:00'

    def test_three_anm_dates(self):
        self.assertEqual(analyze_official_anm(self.rec, date(2026, 11, 6), self.obs)['state'], 'FUTURE_REVIEW')
        f = analyze_official_anm(self.rec, date(2027, 4, 22), self.obs)
        self.assertEqual(f['provisions'], ['ANM220-arts76-77'])
        self.assertEqual(len(analyze_official_anm(self.rec, date(2027, 8, 2), self.obs)['provisions']), 2)
        self.assertEqual(len(analyze_official_anm(self.rec, date(2029, 12, 26), self.obs)['provisions']), 3)

    def test_current_attributes_not_presented_as_historical(self):
        past = analyze_official_anm(self.rec, date(2025, 1, 1), self.obs)
        self.assertIn('NÃO representam o estado', past['temporal_note'])
        fut = analyze_official_anm(self.rec, date(2027, 8, 2), self.obs)
        self.assertIn('projetados', fut['temporal_note'])

    def test_missing_official_attribute_requests_data(self):
        f = analyze_official_anm({**self.rec, 'pnsb': None}, date(2026, 11, 6), self.obs)
        self.assertEqual(f['state'], 'INSUFFICIENT')
        self.assertEqual(f['rule_id'], 'ANM-OF0-dados')

    def test_never_claims_safety(self):
        f = analyze_official_anm(self.rec, date(2026, 11, 6), self.obs)
        self.assertIn('não avalia segurança', f['rationale'])
        self.assertIsNone(f['legal_deadline'])

    def test_explanation_has_operator_value_version(self):
        f = analyze_official_anm(self.rec, date(2027, 8, 2), self.obs)
        e = explanation(f, PROV)
        self.assertTrue(all({'attribute', 'operator', 'value', 'provision', 'version', 'as_of'} <= set(x) for x in e))


class FinanceDiffTests(unittest.TestCase):
    def test_finance_reproducible(self):
        r = evaluate([{'name': 'Agora', 'horas_internas': [10, 20, 40], 'custo_hora': [100, 150, 200], 'custo_externo': [0, 1000, 5000], 'duracao_meses': [1, 2, 3]}])
        o = r['options'][0]
        self.assertEqual(o['total'], {'low': 1000.0, 'base': 4000.0, 'high': 13000.0})
        self.assertEqual(o['sensitivity'][0]['variable'], 'custo_externo')  # amplitudes: ext 5000 > horas 30*150=4500 > custo/h 20*100=2000
        self.assertTrue(any('multas' in c for c in r['caveats']))

    def test_finance_validation(self):
        with self.assertRaises(ValueError):
            evaluate([{'name': 'x', 'horas_internas': [10, 5, 20]}])
        with self.assertRaises(ValueError):
            evaluate([])

    def test_diff_nr20(self):
        d = scenario_diffs('nr20', PROV)[0]
        types = {c['type'] for c in d['changes']}
        self.assertIn('vigência alterada', types)
        self.assertIn('exceção alterada', types)
        self.assertIn('texto integral não armazenado', d['basis'])

    def test_diff_added(self):
        self.assertTrue(all(c['type'] == 'adicionado' for c in diff(None, PROV['ANM220-geral'])))


class HttpV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        sigbm.save_snapshot((FIX / 'sigbm_sample.csv').read_bytes(), {'fetched_at': '2026-11-06T10:00:00+00:00', 'source_url': 'fixture'}, cls.tmp)
        server.load_official(cls.tmp)
        cls.store = Store(':memory:'); server.seed(cls.store)
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(cls.store))
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()
        server.load_official(sigbm.SNAP_ROOT)
        shutil.rmtree(cls.tmp)

    def call(self, path, body=None, token=None, raw=False):
        h = {'Content-Type': 'application/json'}
        if token:
            h['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(req) as r:
                b = r.read().decode('utf8')
                return r.status, (b if raw else json.loads(b))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_official_layer_exact_count(self):
        st, j = self.call('/api/official/sigbm')
        self.assertEqual(st, 200)
        self.assertEqual(len(j['records']), 4)
        self.assertEqual(j['quality']['accepted'], 4)
        self.assertEqual(j['origin'], 'DADO_OFICIAL')
        self.assertIn('fetched_at', j['snapshot'])

    def test_record_card(self):
        st, j = self.call('/api/official/sigbm/record?id=SIGBM-1007&as_of=2027-08-02')
        self.assertEqual(j['finding']['state'], 'INSUFFICIENT')   # 1007 não informa PNSB na fonte
        self.assertIn('categoria', j['categorical_note'].lower())
        self.assertEqual(j['axes']['applicability_assessment'], 'missing_attributes')
        st, j = self.call('/api/official/sigbm/record?id=SIGBM-1001&as_of=2027-08-02')
        self.assertEqual(j['finding']['state'], 'REVIEW')

    def test_rbac_on_mutations(self):
        body = {'finding_id': 'anm:SIGBM-1001'}
        self.assertEqual(self.call('/api/reviews/open', body)[0], 401)
        self.assertEqual(self.call('/api/reviews/open', body, 'demo-auditor')[0], 403)
        self.assertEqual(self.call('/api/reviews/open', body, 'token-falso')[0], 401)
        st, r = self.call('/api/reviews/open', body, 'demo-operacao')
        self.assertEqual(st, 200)
        self.assertEqual(r['state'], 'DRAFT')
        st, _ = self.call('/api/reviews/transition', {'review_id': 'anm:SIGBM-1001', 'to_state': 'REVIEW_PENDING', 'reason': 'encaminhar', 'source_version': 'ANM245-art1'}, 'demo-operacao')
        self.assertEqual(st, 200)
        st, _ = self.call('/api/reviews/transition', {'review_id': 'anm:SIGBM-1001', 'to_state': 'CONFIRMED', 'reason': 'ok', 'source_version': 'v'}, 'demo-operacao')
        self.assertEqual(st, 403)
        st, r = self.call('/api/reviews/transition', {'review_id': 'anm:SIGBM-1001', 'to_state': 'CONFIRMED', 'reason': 'dispositivos conferidos', 'source_version': 'ANM245-art1', 'actor': 'Falsificado'}, 'demo-juridico')
        self.assertEqual(st, 200)
        self.assertEqual(r['transitions'][-1]['actor'], 'Ana (jurídico, demo)')  # ator vem do token, não do corpo

    def test_full_flow_and_decision_pack(self):
        tok = 'demo-juridico'
        self.call('/api/reviews/open', {'finding_id': 'anm:SIGBM-1002'}, tok)
        self.call('/api/reviews/assign', {'review_id': 'anm:SIGBM-1002', 'function': 'engenharia'}, tok)
        self.call('/api/reviews/transition', {'review_id': 'anm:SIGBM-1002', 'to_state': 'REVIEW_PENDING', 'reason': 'r', 'source_version': 'v'}, tok)
        self.call('/api/reviews/evidence', {'review_id': 'anm:SIGBM-1002', 'item': 'Enquadramento legal da estrutura', 'description': 'GED/1'}, tok)
        self.call('/api/finance/save', {'review_id': 'anm:SIGBM-1002', 'options': [{'name': 'Fases', 'horas_internas': [1, 2, 3], 'custo_hora': [1, 1, 1], 'custo_externo': [0, 0, 0], 'duracao_meses': [1, 1, 1]}]}, tok)
        st, html = self.call('/api/export/decision-pack?finding=anm:SIGBM-1002&as_of=2027-08-02', raw=True)
        self.assertEqual(st, 200)
        for needle in ('AVALIAÇÃO PRELIMINAR', 'DADO OFICIAL', 'engenharia', 'Enquadramento legal da estrutura', 'Fases', 'não usa a Categoria de Risco'):
            self.assertIn(needle, html)
        st, ex = self.call('/api/executive')
        self.assertEqual([m['id'] for m in ex['metrics']], ['changes', 'pending', 'milestones', 'affected'])
        self.assertTrue(any(a['finding_id'] == 'anm:SIGBM-1002' for a in ex['portfolio']))  # revisão aberta → entra na carteira

    def test_entity_search_endpoint(self):
        st, j = self.call('/api/entities/search?q=Vale')
        self.assertTrue(all(r['link_status'] == 'A_CONFIRMAR' for r in j['results']))
        self.assertEqual(self.call('/api/entities/link', {'org_id': j['results'][0]['org_id'], 'group_label': 'Grupo X', 'decision': 'CONFIRMADO', 'reason': 'r'}, 'demo-operacao')[0], 403)

    def test_sync_requires_curator(self):
        self.assertEqual(self.call('/api/connectors/sigbm/sync', {'x': 1}, 'demo-juridico')[0], 403)

    def test_concurrent_reads_do_not_break_sqlite(self):
        from concurrent.futures import ThreadPoolExecutor
        paths = ['/api/reviews', '/api/executive', '/api/findings', '/api/audit', '/api/official/sigbm'] * 8
        with ThreadPoolExecutor(max_workers=12) as ex:
            codes = list(ex.map(lambda p: self.call(p)[0], paths))
        self.assertEqual(set(codes), {200})

    def test_pwa_assets_served(self):
        for path, ctype in (('/manifest.webmanifest', 'application/manifest+json'), ('/sw.js', 'javascript'), ('/icons/icon-192.png', 'image/png'), ('/icons/icon-512.png', 'image/png')):
            with urllib.request.urlopen(f'http://127.0.0.1:{self.port}{path}') as r:
                self.assertEqual(r.status, 200, path)
                self.assertIn(ctype, r.headers.get('Content-Type', ''), path)
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/manifest.webmanifest') as r:
            m = json.loads(r.read())
        self.assertEqual(m['display'], 'standalone')
        self.assertTrue(any(i['sizes'] == '512x512' for i in m['icons']))

    def test_findings_have_axes(self):
        st, j = self.call('/api/findings')
        self.assertTrue(all({'normative_lifecycle', 'applicability_assessment', 'workflow_state', 'priority'} <= set(f['axes']) for f in j))


if __name__ == '__main__':
    unittest.main()
