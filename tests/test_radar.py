"""Testes do Radar de abandono/órfãs, ferramentas de IA (consulta → filtros, inconsistências) e rascunhos com quatro olhos.
Casos: positivo, negativo, falta de dados e conflito (dados incoerentes)."""
import json
import os
os.environ['TORRE_LLM'] = '0'
os.environ['TORRE_QUIET'] = '1'
import threading
import unittest
import urllib.error
import urllib.request
from collections import Counter
from datetime import date
from http.server import ThreadingHTTPServer

from app import abandono as A, ai_tools as T, server
from app.connectors import snisb
from app.store import Store, WorkflowError

TODAY = date(2026, 11, 6)


def rec(**kw):
    base = {'id': 'SIGBM-1', 'name': 'Teste', 'uf': 'MG', 'municipio': 'X', 'lat': -19.0, 'lon': -44.0, 'owner_doc_type': 'CNPJ',
            'owner_cnpj': '11222333000181', 'owner_name': 'EMPRESA EXEMPLO', 'owner_name_norm': 'empresa exemplo', 'pnsb': 'Sim',
            'operational_status': 'Ativa', 'dpa': 'Baixa', 'cri': 'Baixa', 'emergency_level': 'Sem emergência', 'dce_risr': '2º Campanha 2026 - Atestado'}
    base.update(kw)
    return base


class AbandonoRules(unittest.TestCase):
    def assess(self, r, sn=None):
        return A.assess_mining([r], {r['id']: sn} if sn else {}, TODAY)[0]

    def test_positive_inactive_without_project_with_population_is_critical(self):
        x = self.assess(rec(operational_status='Inativa', dce_risr='2º Campanha 2026 - Não Enviado', dpa='Alta',
                            downstream_population='Existente (Existem pessoas...)'))
        codes = {s['code'] for s in x['signals']}
        self.assertIn('INATIVA_SEM_PROJETO', codes)
        self.assertIn('DCE_NAO_ENVIADA', codes)
        self.assertEqual(x['attention'], 'Crítica')
        for s in x['signals']:  # todo sinal tem evidência e base legal
            self.assertTrue(s['evidence']['field'] and s['evidence']['source'])
            self.assertTrue(all(b['url'].startswith('https://www.planalto.gov.br') for b in s['basis']))

    def test_negative_healthy_dam_has_no_signal(self):
        x = self.assess(rec())
        self.assertEqual(x['signals'], [])
        self.assertEqual(x['attention'], 'Sem sinal')

    def test_generic_signals_alone_never_reach_high(self):
        # autuada + inspeção antiga + instrumentação: sem sinal central -> no máximo Moderada
        x = self.assess(rec(dpa='Alta', instrumentation='Existe instrumentação em desacordo com o projeto sem processo de instalação de instrumentos'),
                        {'fined': 'Sim', 'last_inspection': '2018-01-01'})
        self.assertNotIn(x['attention'], ('Crítica', 'Alta'))

    def test_person_owner_name_is_hidden(self):
        x = self.assess(rec(owner_doc_type='CPF_MASCARADO_OCULTO', owner_cnpj=None, owner_name='Pessoa física (nome não exibido)', operational_status='Inativa'))
        self.assertEqual(x['owner']['kind'], 'Pessoa física')
        self.assertEqual(x['owner_label'], 'Pessoa física (nome não exibido)')
        self.assertIn('nome não exibido', A.draft_representation(x, TODAY) + x['owner_label'])

    def test_orphan_responsibles_include_landowner_and_missing_owner(self):
        o = A.assess_orphan({'id': 'SNISB-1', 'snisb_id': 1, 'name': 'Açude', 'uf': 'RN', 'municipio': 'Y', 'damage_potential': 'Alto', 'has_pae': 'Não',
                             'last_inspection': None, 'regulator': 'RN - IGARN', 'use': 'Irrigação', 'phase': 'Operação'}, TODAY)
        self.assertEqual(o['attention'], 'Crítica')
        roles = {r['role']: r for r in A.responsibles(o)}
        self.assertEqual(roles['Empreendedor']['status'], 'faltando')
        self.assertIn('Proprietário do terreno (responsável subsidiário)', roles)
        self.assertTrue(A.plan(o)['viability'].startswith('Baixa'))

    def test_plan_dependencies_and_conditional_steps(self):
        x = self.assess(rec(operational_status='Inativa', containment='Rejeitos', dpa='Alta', downstream_population='Existente'))
        p = A.plan(x)
        ids = [s['id'] for s in p['steps']]
        self.assertIn('garantia', ids)   # rejeitos + DPA alta -> Art. 17 §2º
        self.assertIn('zas', ids)        # população a jusante
        self.assertTrue(next(s for s in p['steps'] if s['id'] == 'responsavel')['blocked'])
        p2 = A.plan(x, {'confirmar': {'status': 'feito'}})
        self.assertFalse(next(s for s in p2['steps'] if s['id'] == 'responsavel')['blocked'])
        healthy = A.plan(self.assess(rec()))
        self.assertNotIn('garantia', [s['id'] for s in healthy['steps']])

    def test_draft_is_marked_unsent(self):
        x = self.assess(rec(operational_status='Inativa'))
        d = A.draft_representation(x, TODAY)
        self.assertTrue(d.startswith('RASCUNHO'))
        self.assertIn('NÃO FOI ENVIADO', d)
        self.assertIn('art. 17-A, §2º', d)

    def test_brazilian_number_parsing(self):
        self.assertEqual(A.br_num('1.000.000,00'), 1000000.0)
        self.assertEqual(A.br_num('410689,73'), 410689.73)
        self.assertIsNone(A.br_num('-'))


class AiToolsTests(unittest.TestCase):
    def test_rules_parse_portuguese(self):
        f = T.parse_rules('inativas sem projeto em Minas Gerais com população abaixo')['filters']
        self.assertEqual(f['uf'], ['MG'])
        self.assertIn('Inativa', f['operational_status'])
        self.assertIn('INATIVA_SEM_PROJETO', f['signals'])
        self.assertTrue(f['population'])
        self.assertEqual(f['dataset'], 'mineracao')

    def test_rules_do_not_invent_uf_from_common_words(self):
        f = T.parse_rules('barragens que estão para descaracterizar')['filters']
        self.assertEqual(f['uf'], [])

    def test_llm_proposal_is_verified_against_vocabulary(self):
        fake = lambda q: {'dataset': 'orfas', 'uf': ['RN', 'XX'], 'attention': ['Crítica', 'Gravíssima'], 'owner_kind': [], 'operational_status': [],
                          'signals': ['INVENTADO'], 'text': ''}
        it = T.interpret('órfãs críticas', use_llm=True, llm=fake)
        self.assertEqual(it['engine'], 'ia')
        self.assertEqual(it['filters']['uf'], ['RN'])
        self.assertEqual(it['filters']['attention'], ['Crítica'])
        self.assertEqual(sorted(it['dropped']), ['attention=Gravíssima', 'signals=INVENTADO', 'uf=XX'])

    def test_llm_echoing_query_as_name_search_is_dropped(self):
        fake = lambda q: {'dataset': 'mineracao', 'uf': ['MG'], 'attention': [], 'owner_kind': [], 'operational_status': ['Inativa'], 'signals': [], 'text': q}
        it = T.interpret('inativas sem projeto em MG', use_llm=True, llm=fake)
        self.assertEqual(it['filters']['text'], '')
        self.assertTrue(any(d.startswith('text=') for d in it['dropped']))

    def test_llm_failure_falls_back_to_rules(self):
        def boom(q):
            raise TimeoutError
        it = T.interpret('órfãs no RN', use_llm=True, llm=boom)
        self.assertEqual(it['engine'], 'regras')
        self.assertIn('IA indisponível', it['note'])

    def test_anomalies_conflicting_data(self):
        rs = [rec(id='SIGBM-2', height_project_m='10,00', height_current_m='15,00'),
              rec(id='SIGBM-3', operational_status='Inativa', emergency_level='Emergência Nivel 1'),
              rec(id='SIGBM-4', dpa='Alta', pnsb='Não'),
              rec(id='SIGBM-5')]
        codes = {a['id']: a['code'] for a in T.anomalies(rs, TODAY)['items']}
        self.assertEqual(codes.get('SIGBM-2'), 'ALTURA_ACIMA_LICENCIADA')
        self.assertEqual(codes.get('SIGBM-3'), 'INATIVA_EM_EMERGENCIA')
        self.assertEqual(codes.get('SIGBM-4'), 'DPA_FORA_PNSB')
        self.assertNotIn('SIGBM-5', codes)

    def test_quick_help_and_law(self):
        self.assertEqual(T.quick('oi', [])['kind'], 'help')
        q = T.quick('quem é responsável por barragem abandonada?', [])
        self.assertEqual(q['kind'], 'law')
        self.assertIn('art. 2º, IV', q['answer'])


class SnisbConnectorTests(unittest.TestCase):
    def test_pagination_and_normalization(self):
        pages = [{'features': [{'attributes': {'BAR_CD_SNISB': 1, 'BAR_NM_NOME': 'A', 'BAR_NU_LATITUDE': -6.1, 'BAR_NU_LONGITUDE': -38.2, 'DANO_POTENCIAL': 'Alto',
                                               'INS_DT_INSPECAO': None, 'CATEGORIA_RISCO': 'Não Classificado'}}], 'exceededTransferLimit': True},
                 {'features': [{'attributes': {'BAR_CD_SNISB': 2, 'BAR_NU_LATITUDE': 99, 'BAR_NU_LONGITUDE': 0}}]},
                 {'features': []}]
        calls = []
        rows = snisb._all('x', [], page=1, delay=0, fetch=lambda w, f, o, p, t: (calls.append(o), pages[len(calls) - 1])[1])
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(len(rows), 2)
        self.assertIsNone(snisb.normalize_orphan(rows[1]))  # coordenada fora do Brasil
        o = snisb.normalize_orphan(rows[0])
        self.assertEqual(o['id'], 'SNISB-1')
        self.assertIsNone(o['risk_category'])
        self.assertIsNone(o['owner'])

    def test_error_response_raises(self):
        with self.assertRaises(RuntimeError):
            snisb._all('x', [], fetch=lambda *a: {'error': {'code': 400}})


class DraftWorkflow(unittest.TestCase):
    def test_four_eyes_and_reason(self):
        s = Store(':memory:')
        d = s.save_draft('SIGBM-1', 'representacao', 'texto', 'Ana')
        with self.assertRaises(WorkflowError):
            s.decide_draft(d['id'], 'APROVADO_PARA_ENVIO', 'Ana', 'ok')
        with self.assertRaises(WorkflowError):
            s.decide_draft(d['id'], 'APROVADO_PARA_ENVIO', 'Bruno', '')
        self.assertEqual(s.decide_draft(d['id'], 'APROVADO_PARA_ENVIO', 'Bruno', 'Conferido')['state'], 'APROVADO_PARA_ENVIO')
        with self.assertRaises(WorkflowError):
            s.decide_draft(d['id'], 'DESCARTADO', 'Bruno', 'de novo')
        self.assertTrue(s.verify_chain()['ok'])

    def test_plan_step_done_requires_evidence(self):
        s = Store(':memory:')
        with self.assertRaises(WorkflowError):
            s.set_plan_step('SIGBM-1', 'confirmar', 'feito', 'Ana', '')
        s.set_plan_step('SIGBM-1', 'confirmar', 'feito', 'Ana', 'conferido')
        self.assertEqual(s.plan_progress('SIGBM-1')['confirmar']['status'], 'feito')


@unittest.skipUnless(snisb.latest(), 'snapshot SNISB ausente')
class RadarHttp(unittest.TestCase):
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
                raw = r.read()
                return r.status, (json.loads(raw) if r.headers.get_content_type() == 'application/json' else raw.decode('utf8'))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_panorama_and_list(self):
        st, p = self.call('/api/radar/panorama')
        self.assertEqual(st, 200)
        self.assertGreater(p['orphans']['total'], 1000)
        self.assertEqual(p['rule_version'], A.RULE_VERSION)
        st, l = self.call('/api/radar/list?dataset=orfas&attention=Cr%C3%ADtica&limit=5')
        self.assertTrue(all(x['kind'] == 'orfa' and x['attention'] == 'Crítica' for x in l['items']))

    def test_item_has_chain_plan_and_no_person_name(self):
        st, l = self.call('/api/radar/list?dataset=mineracao&owner_kind=Pessoa%20f%C3%ADsica&limit=1')
        st, x = self.call('/api/radar/item?id=' + l['items'][0]['id'])
        self.assertEqual(st, 200)
        self.assertEqual(x['owner_label'], 'Pessoa física (nome não exibido)')
        self.assertTrue(x['responsibles'] and x['plan']['steps'])

    def test_permissions(self):
        st, l = self.call('/api/radar/list?dataset=mineracao&attention=Cr%C3%ADtica&limit=1')
        dam = l['items'][0]['id']
        self.assertEqual(self.call('/api/radar/plan-step', {'dam_id': dam, 'step_id': 'confirmar', 'status': 'em_andamento'}, 'demo-auditor')[0], 403)
        self.assertEqual(self.call('/api/radar/plan-step', {'dam_id': dam, 'step_id': 'inexistente', 'status': 'feito'}, 'demo-operacao')[0], 400)
        st, p = self.call('/api/radar/plan-step', {'dam_id': dam, 'step_id': 'confirmar', 'status': 'feito', 'note': 'ok'}, 'demo-operacao')
        self.assertEqual(st, 200)
        st, d = self.call('/api/radar/draft', {'dam_id': dam}, 'demo-operacao')
        self.assertEqual(st, 201)
        self.assertEqual(self.call('/api/radar/draft/decide', {'id': d['id'], 'decision': 'APROVADO_PARA_ENVIO', 'reason': 'x'}, 'demo-operacao')[0], 403)
        st, dd = self.call('/api/radar/draft/decide', {'id': d['id'], 'decision': 'APROVADO_PARA_ENVIO', 'reason': 'Conferido'}, 'demo-juridico')
        self.assertEqual(dd['state'], 'APROVADO_PARA_ENVIO')

    def test_ai_endpoints(self):
        st, s = self.call('/api/ai/status')
        self.assertEqual(s['llm']['mode'], 'controlado')
        self.assertFalse(any(c['engine'].startswith('IA generativa') for c in s['capabilities']))  # sem chave: nada rotulado como IA generativa
        st, q = self.call('/api/ai/quick', {'q': 'órfãs críticas no RN'})
        self.assertEqual(q['kind'], 'filter')
        self.assertGreater(q['total'], 0)
        st, a = self.call('/api/ai/anomalies?limit=3')
        self.assertLessEqual(len(a['items']), 3)

    def test_hidden_risk_endpoint(self):
        st, m = self.call('/api/ai/hidden-risk')
        self.assertEqual(st, 200)
        self.assertTrue(m['available'])
        self.assertGreater(m['metrics']['cv_auc'], 0.6)
        self.assertTrue(all(x['why'] is not None for x in m['items']))
        st, l = self.call('/api/radar/list?dataset=mineracao&hidden_risk=1&limit=500')
        self.assertEqual(l['total'], len(m['items']))

    def test_csv_export(self):
        st, body = self.call('/api/export/radar.csv?dataset=orfas&attention=Cr%C3%ADtica')
        self.assertEqual(st, 200)
        self.assertIn('abandono-v1', body)
        self.assertNotIn('NM_EMPREENDEDOR', body)


class DamBriefTests(unittest.TestCase):
    def item(self):
        return A.assess_mining([rec(operational_status='Inativa', dpa='Alta', downstream_population='Existente')], {}, TODAY)[0]

    def test_template_without_llm(self):
        b = T.dam_brief(self.item(), use_llm=False)
        self.assertEqual(b['engine'], 'regras')
        self.assertIn('Teste', b['simple'])

    def test_verifier_rejects_invented_numbers_and_forbidden_claims(self):
        bad = lambda f: {'simple': 'A barragem está segura e afeta 999 pessoas.', 'technical': 'ok'}
        b = T.dam_brief(self.item(), use_llm=True, llm=bad)
        self.assertEqual(b['engine'], 'regras')
        self.assertTrue(any('999' in r for r in b['rejected']))
        self.assertTrue(any('segura' in r for r in b['rejected']))

    def test_grounded_llm_text_is_accepted(self):
        good = lambda f: {'simple': f"A barragem {f['nome']} está em atenção {f['nivel_de_atencao']}.", 'technical': 'Próximo passo: confirmar com o fiscalizador.'}
        self.assertEqual(T.dam_brief(self.item(), use_llm=True, llm=good)['engine'], 'ia')

    def test_provider_failure_falls_back(self):
        def boom(f):
            raise TimeoutError
        b = T.dam_brief(self.item(), use_llm=True, llm=boom)
        self.assertIn('indisponível', b['engine_label'])


class RiskModelTests(unittest.TestCase):
    def synthetic(self, n=240):
        import random
        rnd = random.Random(1)
        out = []
        for i in range(n):
            bad = rnd.random() < 0.25
            out.append(rec(id=f'SIGBM-{i}', pnsb='Sim', emergency_level='Emergência Nivel 1' if bad and rnd.random() < 0.8 else 'Sem emergência',
                           spillway=('6 - problema' if bad else '0 - ok'), operational_status=('Inativa' if bad and rnd.random() < .6 else 'Ativa'),
                           dce_risr='2º Campanha 2026 - Não Atestado' if bad else '2º Campanha 2026 - Atestado'))
        return out

    def test_learns_profile_and_flags_hidden_risk(self):
        from app import risk_model as M
        o = M.run(self.synthetic(), TODAY)
        self.assertTrue(o['available'])
        self.assertGreater(o['metrics']['cv_auc'], 0.8)
        flagged = [o['by_id'][i] for i in o['flagged']]
        self.assertTrue(flagged and all(not f['emergency'] for f in flagged))
        self.assertTrue(any('Extravasor' in w['feature'] for f in flagged for w in f['why']))

    def test_does_not_use_leaky_fields(self):
        from app import risk_model as M
        rows, vocab, labels = M.featurize(self.synthetic(60), TODAY)
        self.assertFalse(any(k.startswith(('dce_', 'cri', 'dpa', 'downstream')) for k in vocab))

    def test_insufficient_data_abstains(self):
        from app import risk_model as M
        self.assertFalse(M.run(self.synthetic(20), TODAY)['available'])


if __name__ == '__main__':
    unittest.main()
