"""Plataforma multissetorial: motor de ativos por configuração, SIGMINE (minas/radiológico), denúncia destinada à empresa,
fila de e-mail e isolamento de notificações por organização."""
import os
os.environ['TORRE_LLM'] = '0'
os.environ.pop('TORRE_SES_FROM', None)
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import ativos, denuncia
from app.accounts import Accounts
from app.connectors import sigmine
from app.mailer import Mailer
from app.store import Store, WorkflowError

TODAY = date(2026, 11, 7)
CFG, EMP = ativos.load()
BY_ID = {c['id']: c for c in EMP['empresas']} if isinstance(EMP, dict) and 'empresas' in EMP else {c['id']: c for c in EMP}


class AtivosTests(unittest.TestCase):
    def test_same_engine_three_sectors(self):
        for cid in ('demo-mineracao', 'demo-energia', 'demo-saneamento'):
            r = ativos.evaluate(BY_ID[cid], CFG, TODAY)
            self.assertEqual(r['setor']['id'], BY_ID[cid]['setor'])
            self.assertTrue(r['assets'])
            self.assertTrue(set(r['abas_ativas']) <= set(r['setor']['abas']))
            for a in r['alerts']:
                self.assertTrue(a['basis'] and a['action'] and a['recipients'] and a['rule_version'] == 'ativos-v1')
            for x in r['assets']:
                self.assertIn(x['status'], ('critico', 'pendencia', 'normal'))

    def test_disabled_tab_is_hidden(self):
        c = dict(BY_ID['demo-mineracao'])
        sector_tabs = CFG['setores'][c['setor']]['abas']
        c['abas_ativas'] = sector_tabs[:1]
        self.assertEqual(ativos.evaluate(c, CFG, TODAY)['abas_ativas'], sector_tabs[:1])

    def test_radiological_asset_routes_to_radioprotection(self):
        r = ativos.evaluate(BY_ID['demo-mineracao'], CFG, TODAY)
        rad = [a for a in r['alerts'] if a['kind'] == 'radiologico']
        self.assertTrue(rad, 'ativo radiológico sintético deve gerar alerta')
        roles = {x['papel'] for a in rad for x in a['recipients']}
        self.assertTrue(roles & set(CFG['roteamento_padrao']['radiologico']))

    def test_missing_document_is_flagged_not_assumed(self):
        c = dict(BY_ID['demo-energia'])
        c['ativos'] = [dict(c['ativos'][0], documentos={})]
        r = ativos.evaluate(c, CFG, TODAY)
        self.assertTrue(all(d['status'] == 'não cadastrado' for d in r['assets'][0]['documentos']))

    def test_robust_z(self):
        self.assertIsNone(ativos._z([1, 2, 3]))                       # histórico insuficiente
        self.assertGreater(ativos._z([10, 10.2, 9.9, 10.1, 10, 10.1, 10, 10, 30]), 8)


class SigmineTests(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(sigmine.category('MINÉRIO DE URÂNIO')[0], 'nuclear')
        self.assertEqual(sigmine.category('TERRAS RARAS')[0], 'norm')
        self.assertEqual(sigmine.category('AREIA')[0], 'construcao')
        self.assertEqual(sigmine.category('MINÉRIO DE FERRO')[0], 'metalico')

    def test_normalize_hides_person_and_rejects_outside(self):
        g = {'rings': [[[-44.0, -20.0], [-43.9, -20.0], [-43.9, -19.9], [-44.0, -20.0]]]}
        n = sigmine.normalize({'PROCESSO': '830.001/2001', 'NOME': 'Fulano de Tal', 'SUBS': 'FOSFATO', 'UF': 'MG', 'FASE': 'CONCESSÃO DE LAVRA'}, g)
        self.assertTrue(n['radiologico'])
        self.assertNotIn('Fulano', n['titular'])
        n2 = sigmine.normalize({'PROCESSO': '1', 'NOME': 'Mineração Exemplo LTDA', 'SUBS': 'OURO'}, g)
        self.assertIn('LTDA', n2['titular'])
        far = {'rings': [[[10.0, 50.0], [10.1, 50.0], [10.1, 50.1], [10.0, 50.0]]]}
        self.assertIsNone(sigmine.normalize({'PROCESSO': '2', 'SUBS': 'OURO'}, far))

    def test_fetch_with_fake_service(self):
        g = {'rings': [[[-44.0, -20.0], [-43.9, -20.0], [-43.9, -19.9], [-44.0, -20.0]]]}
        pages = [{'features': [{'attributes': {'PROCESSO': f'{i}', 'SUBS': 'AREIA', 'UF': 'MG'}, 'geometry': g} for i in range(3)]}]
        with tempfile.TemporaryDirectory() as tmp:
            man = sigmine.fetch(Path(tmp), page=10, delay=0, fetch_json=lambda url: pages.pop(0))
            self.assertEqual(man['accepted'], 3)
            last = sigmine.latest(Path(tmp))
            self.assertEqual(last['manifest']['snapshot_id'], man['snapshot_id'])
            self.assertEqual(len(last['items']), 3)

    def test_service_error_raises(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(RuntimeError):
            sigmine.fetch(Path(tmp), delay=0, fetch_json=lambda url: {'error': {'code': 500}})


class DenunciaEmpresaTests(unittest.TestCase):
    def setUp(self):
        self.s = Store(':memory:')
        self.d = denuncia.DenunciaDesk(self.s)
        out = denuncia.build('Há uma trinca no talude e água saindo na base desde março.', None, [], TODAY)
        self.x = self.d.save('usuario:9', 'ATIVO:demo-mineracao:B-01', out, [])
        self.d.confirm(self.x['id'], 'usuario:9')

    def test_inbox_only_for_target_org_and_anonymous(self):
        denuncia.route_to_company(self.s, self.x['id'], '11222333', 'Empresa fictícia', 'B-01', identificado=False)
        box = denuncia.inbox(self.s, '11222333')
        self.assertEqual(len(box), 1)
        self.assertIn('anônimo para a empresa', box[0]['body'])
        self.assertEqual(denuncia.inbox(self.s, '99888777'), [])           # outra empresa não vê

    def test_respond_rules(self):
        denuncia.route_to_company(self.s, self.x['id'], '11222333', 'Empresa fictícia', 'B-01', identificado=True)
        with self.assertRaises(WorkflowError):
            denuncia.respond(self.s, self.x['id'], '11222333', 'RESPONDIDA', '', 'bruno')      # resposta exige texto
        with self.assertRaises(WorkflowError):
            denuncia.respond(self.s, self.x['id'], '99888777', 'EM_APURACAO', '', 'x')        # não destinada
        with self.assertRaises(WorkflowError):
            denuncia.respond(self.s, self.x['id'], '11222333', 'INVENTADO', 'x', 'bruno')
        self.assertEqual(denuncia.respond(self.s, self.x['id'], '11222333', 'RESPONDIDA', 'Vistoria feita.', 'bruno')['state'], 'RESPONDIDA')

    def test_company_email_carries_norms_and_hash(self):
        d = self.d.get(self.x['id'], 'usuario:9')
        subj, body = denuncia.company_email(d, 'Empresa fictícia', 'B-01', False, {'name': 'Ana', 'email': 'a@x'})
        self.assertIn('B-01', subj)
        self.assertIn(d['sha256'], body)
        self.assertIn('Lei 12.334', body)
        self.assertNotIn('a@x', body)                                        # anônimo por padrão


class MailerAndNotificationTests(unittest.TestCase):
    def test_queue_without_ses(self):
        m = Mailer(Store(':memory:'))
        self.assertFalse(m.configured())
        r = m.queue('compliance@exemplo.invalid', '11222333', 'Assunto', 'Corpo', 'denuncia:1')
        self.assertIn('NA_FILA', r['state'])
        self.assertEqual(len(m.list('11222333')), 1)
        self.assertEqual(m.list('99888777'), [])

    def test_org_audience_isolation(self):
        acc = Accounts(Store(':memory:'))
        acc.notify('org:11222333', 'denuncia', 'Nova denúncia', 'x')
        acc.notify('orgfunc:11222333:compliance', 'alerta', 'Alerta compliance', 'x')
        bruno = {'id': 1, 'kind': 'empresa', 'cnpj': '11222333000181', 'function': 'compliance', 'role': 'gestor'}
        outra = {'id': 2, 'kind': 'empresa', 'cnpj': '99888777000100', 'function': 'compliance', 'role': 'gestor'}
        oper = {'id': 3, 'kind': 'empresa', 'cnpj': '11222333000181', 'function': 'operacao', 'role': 'analista'}
        cid = {'id': 4, 'kind': 'cidadao', 'cnpj': None, 'function': None, 'role': 'cidadao'}
        n = lambda u: {x['title'] for x in acc.notifications(u)['items']}
        self.assertEqual(n(bruno), {'Nova denúncia', 'Alerta compliance'})
        self.assertEqual(n(oper), {'Nova denúncia'})
        self.assertEqual(n(outra), set())
        self.assertEqual(n(cid), set())


if __name__ == '__main__':
    unittest.main()


class IAEvalTests(unittest.TestCase):
    def test_eval_set_passes_and_has_all_categories(self):
        from app import ia_eval
        r = ia_eval.run()
        falhas = [c for c in r['casos'] if not c['ok']]
        self.assertEqual(falhas, [])
        self.assertEqual(set(r['por_categoria']), {'relevancia_filtros', 'normas_denuncia', 'versao_vigente', 'roteamento', 'perguntas', 'alucinacao', 'isolamento', 'setor_normas', 'donos', 'extracao'})
        self.assertEqual(r['normas']['indevidas'], 0)

    def test_radiological_rule_does_not_match_inside_words(self):
        for t in ('Pedi o relatório no escritório.', 'O território é grande.'):
            self.assertNotIn('cnen_nn401', denuncia.analyze(t, None)['normas'])
        self.assertIn('cnen_nn401', denuncia.analyze('Há minério de tório e urânio no pátio.', {'kind': 'mina'})['normas'])

    def test_cost_meter_per_client_and_feature(self):
        from app import cloud_aws
        cloud_aws.meter_request('11222333', 'ativos')
        cloud_aws.note_deterministic('filtros')
        u = cloud_aws.usage()
        self.assertGreaterEqual(u['por_cliente']['11222333']['deterministico'], 1)
        self.assertGreaterEqual(u['por_funcionalidade']['ativos']['requisicoes'], 1)
        self.assertIsNone(u['por_cliente']['11222333']['custo_usd_est'] if not u['preco_configurado'] else None)


class TenantDedupTests(unittest.TestCase):
    def test_same_file_not_stored_twice(self):
        import base64
        from app.cloud_aws import EvidenceVault
        from app.tenant import TenantDocs
        with tempfile.TemporaryDirectory() as tmp:
            t = TenantDocs(Store(':memory:'), EvidenceVault(bucket='', local_root=Path(tmp)), var_dir=Path(tmp))
            u = {'id': 1, 'kind': 'empresa', 'cnpj': '11222333000181'}
            b = base64.b64encode(b'%PDF igual').decode()
            a1, a2 = t.upload(u, 'a.pdf', 'application/pdf', b), t.upload(u, 'b.pdf', 'application/pdf', b)
            self.assertEqual(a1['id'], a2['id'])
            self.assertTrue(a2.get('duplicado'))
            self.assertEqual(len(t.list(u)['docs']), 1)


class ContasAlvoTests(unittest.TestCase):
    def test_exact_name_only_no_group_inference(self):
        from app import contas
        cfg = {'aviso': 'x', 'contas': [{'id': 'a', 'nome': 'Exemplo Mining', 'padrao': 'EXEMPLO MINING', 'relacao': 'alvo'}]}
        recs = [{'id': 'S1', 'owner_name': 'Exemplo Mining Ltda', 'dpa': 'Alta', 'emergency_level': 'Sem emergência', 'uf': 'MG'},
                {'id': 'S2', 'owner_name': 'Mineração Subsidiária do Exemplo', 'dpa': 'Alta', 'uf': 'MG'}]
        minas = [{'titular': 'EXEMPLO MINING LTDA', 'substancia': 'OURO', 'uf': 'MG', 'radiologico': False}]
        x = contas.match(cfg, recs, {'S1': {'attention': 'Alta'}}, minas)['items'][0]
        self.assertEqual((x['barragens'], x['titulos_lavra'], x['dpa_alta']), (1, 1, 1))   # subsidiária com outro nome não entra
        self.assertEqual(x['relacao'], 'Conta-alvo (prospecção)')
        self.assertIn('Barragens', x['modulos_sugeridos'])

    def test_default_relation_is_target_not_client(self):
        from app import contas
        for c in contas.load()['contas']:
            self.assertEqual(c['relacao'], 'alvo')

    def test_sector_routes_configured(self):
        self.assertIn('minas', CFG['setores']['mineracao']['rotas_operacao'])
        self.assertNotIn('minas', CFG['setores']['energia']['rotas_operacao'])


class TransparenciaTests(unittest.TestCase):
    RECS = [{'id': 'S1', 'owner_cnpj_root': '11111111', 'owner_cnpj': '11111111000100', 'owner_name': 'Mineradora A S.A.', 'owner_doc_type': 'CNPJ', 'dpa': 'Alta', 'emergency_level': 'Nível 1', 'uf': 'MG', 'lat': -20.0, 'lon': -44.0},
            {'id': 'S2', 'owner_cnpj_root': None, 'owner_cnpj': None, 'owner_name': 'Fulano de Tal', 'owner_doc_type': 'CPF_MASCARADO_OCULTO', 'dpa': 'Baixa', 'uf': 'MT', 'lat': -15.0, 'lon': -56.0}]
    RADAR = [{'id': 'S1', 'kind': 'mineracao', 'attention': 'Crítica', 'score': 9, 'name': 'B1', 'municipio': 'X', 'uf': 'MG', 'lat': -20.0, 'lon': -44.0, 'signals': [{'code': 'A', 'label': 'DCE não enviada'}]},
             {'id': 'S2', 'kind': 'mineracao', 'attention': 'Alta', 'score': 5, 'name': 'B2', 'municipio': 'Y', 'uf': 'MT', 'lat': -15.0, 'lon': -56.0, 'signals': []}]

    def test_panorama_hides_person_and_aggregates(self):
        from app import transparencia as tp
        s = Store(':memory:')
        d = tp.panorama(self.RECS, {x['id']: x for x in self.RADAR}, self.RADAR, [], s.db, {'11222333': 'Demo'}, None)
        self.assertNotIn('Fulano', json.dumps(d, ensure_ascii=False))
        self.assertEqual(d['totais']['em_emergencia'], 1)
        self.assertEqual(d['empresas'][0]['critica'], 1)
        self.assertEqual(set(d['denuncias']), {'registradas', 'enviadas_ao_orgao', 'encaminhadas_empresa', 'em_apuracao', 'respondidas'})

    def test_counts_per_company_only_for_lexia_companies(self):
        from app import transparencia as tp
        s = Store(':memory:')
        dd = denuncia.DenunciaDesk(s)
        x = dd.save('usuario:1', 'ATIVO:demo-mineracao:B-01', denuncia.build('trinca no talude', None, [], TODAY), [])
        dd.confirm(x['id'], 'usuario:1')
        denuncia.route_to_company(s, x['id'], '11222333', 'Demo', 'B-01', False)
        denuncia.respond(s, x['id'], '11222333', 'RESPONDIDA', 'Feito.', 'bruno')
        rows = tp.por_empresa_lexia(s.db, {'11222333': 'Demo'})
        self.assertEqual((rows[0]['recebidas'], rows[0]['respondidas'], rows[0]['taxa_resposta']), (1, 1, 1.0))
        self.assertNotIn('relato', json.dumps(rows))

    def test_nearest_sorted_by_distance(self):
        from app import transparencia as tp
        out = tp.proximos(-20.01, -44.01, self.RADAR, {r['id']: r for r in self.RECS}, [], [], lambda r: False, k=2)
        self.assertEqual(out[0]['id'], 'S1')
        self.assertLess(out[0]['km'], out[1]['km'])
        self.assertEqual(out[1]['empresa'], 'Pessoa física (nome não exibido)')


class NormasSetorTests(unittest.TestCase):
    def test_same_complaint_different_sector_norms(self):
        rel = 'O vertedouro está transbordando com a chuva forte'
        usina = denuncia.analyze(rel, {'kind': 'empresa_ativo', 'setor': 'energia', 'tipo': 'barragem'})
        mina = denuncia.analyze(rel, {'kind': 'mineracao'})
        self.assertIn('aneel_1064', usina['normas']); self.assertNotIn('res95', usina['normas'])
        self.assertIn('res95', mina['normas']); self.assertNotIn('aneel_1064', mina['normas'])
        self.assertIn('res95', [r['norma'] for r in usina['recusadas']])

    def test_llm_cannot_pick_other_sector_norm(self):
        fake = lambda *a: json.dumps({'fatos': ['x'], 'normas': ['res95', 'aneel_1064'], 'pedidos': []})
        out = denuncia.build('relato que as regras não reconhecem', {'kind': 'empresa_ativo', 'setor': 'energia', 'tipo': 'barragem'}, [], TODAY, llm=fake)
        keys = [n['key'] for n in out['normas']]
        self.assertIn('aneel_1064', keys); self.assertNotIn('res95', keys)

    def test_gap_goes_to_curation(self):
        a = denuncia.analyze('Há trinca no reservatório', {'kind': 'empresa_ativo', 'setor': 'saneamento', 'tipo': 'reservatorio'})
        self.assertTrue(a['lacuna'])

    def test_every_catalog_norm_classified_and_matrix(self):
        from app.compliance import CATALOG
        from app.normas_setor import cobertura
        c = cobertura(CATALOG)
        self.assertEqual(c['sem_classificacao'], [])
        self.assertTrue(c['matriz']['energia']['seguranca'])

    def test_provisions_filtered_by_sector(self):
        from app.normas_setor import provisao_aplica
        self.assertFalse(provisao_aplica({'regulator': 'ANM'}, 'energia'))
        self.assertTrue(provisao_aplica({'regulator': 'MTE'}, 'energia'))
        self.assertTrue(provisao_aplica({'regulator': 'ANM'}, None))


class DonoTests(unittest.TestCase):
    def test_no_orphan_alerts(self):
        r = ativos.evaluate(BY_ID['demo-energia'], CFG, TODAY, pessoas=set())
        self.assertEqual(r['donos']['alertas_sem_dono'], 0)
        self.assertTrue(all(a['escalado'] for a in r['alerts']))
        self.assertTrue(any(x['papel'] == 'curadoria' for x in r['alerts'][0]['recipients']))

    def test_person_present_no_escalation(self):
        r = ativos.evaluate(BY_ID['demo-mineracao'], CFG, TODAY, pessoas={'compliance', 'juridico', 'engenharia', 'operacao', 'financas'})
        self.assertEqual(r['donos']['alertas_escalados'], 0)


class RadaresSetorTests(unittest.TestCase):
    def test_mina_fechando_perto_de_barragem_dpa_alta_e_critica(self):
        from app import radares
        minas = [{'id': 'ANM-1', 'substancia': 'FERRO', 'processo': '1/2000', 'uf': 'MG', 'lat': -20.0, 'lon': -44.0, 'titular': 'X LTDA', 'fase': 'CONCESSÃO DE LAVRA',
                  'ultimo_evento': '1338 - CONC LAV/PLANO DE FECHAMENTO DE MINA PROTOC EM 01/12/2022', 'radiologico': False},
                 {'id': 'ANM-2', 'substancia': 'AREIA', 'processo': '2/2000', 'uf': 'MG', 'lat': -15.0, 'lon': -44.0, 'titular': 'Y LTDA', 'fase': 'CONCESSÃO DE LAVRA',
                  'ultimo_evento': '1338 - CONC LAV/PLANO DE FECHAMENTO DE MINA PROTOC EM 01/12/2022', 'radiologico': False},
                 {'id': 'ANM-3', 'substancia': 'OURO', 'processo': '3/2000', 'uf': 'MG', 'lat': -16.0, 'lon': -44.0, 'titular': 'Z LTDA', 'fase': 'CONCESSÃO DE LAVRA',
                  'ultimo_evento': '418 - CONC LAV/RAL ANO BASE APRESENTADO EM 09/03/2026', 'radiologico': False}]
        barr = [{'id': 'SIGBM-1', 'name': 'B1', 'lat': -20.01, 'lon': -44.01, 'dpa': 'Alta', 'operational_status': 'Ativa'}]
        r = radares.minas_fechamento(minas, barr, TODAY)
        by = {x['id']: x for x in r['items']}
        self.assertEqual(by['ANM-1']['atencao'], 'Crítica')
        self.assertEqual(by['ANM-1']['barragens_proximas'][0]['id'], 'SIGBM-1')
        self.assertEqual(by['ANM-2']['atencao'], 'Moderada')       # sem consequência perto: não sobe
        self.assertNotIn('ANM-3', by)                               # mina em dia não entra
        self.assertEqual(by['ANM-1']['sinais'][0]['evidence']['field'], 'ULT_EVENTO')

    def test_outorga_vencida_uhe_critica_e_sem_obra(self):
        from app import radares
        us = [{'id': 'CEG-1', 'nome': 'U1', 'uf': 'SP', 'tipo': 'UHE', 'tipo_rotulo': 'Usina hidrelétrica', 'fase': 'Operação', 'fim_vigencia': '2016-06-28', 'inicio_vigencia': '1990-01-01', 'potencia_kw': 72000},
              {'id': 'CEG-2', 'nome': 'U2', 'uf': 'BA', 'tipo': 'UFV', 'tipo_rotulo': 'Solar', 'fase': 'Construção não iniciada', 'fim_vigencia': '2050-01-01', 'inicio_vigencia': '2019-01-01', 'potencia_kw': 5000},
              {'id': 'CEG-3', 'nome': 'U3', 'uf': 'BA', 'tipo': 'EOL', 'tipo_rotulo': 'Eólica', 'fase': 'Operação', 'fim_vigencia': '2050-01-01', 'inicio_vigencia': '2019-01-01', 'potencia_kw': 5000}]
        by = {x['id']: x for x in radares.outorgas(us, TODAY)['items']}
        self.assertEqual(by['CEG-1']['atencao'], 'Crítica')
        self.assertIn('SEM_OBRA_4A', [s['code'] for s in by['CEG-2']['sinais']])
        self.assertNotIn('CEG-3', by)

    def test_barragem_usina_nao_usa_inspecao(self):
        from app import radares
        o = {'id': 'SNISB-1', 'name': 'B', 'uf': 'PR', 'lat': -25.0, 'lon': -50.0, 'use': 'Hidrelétrica', 'phase': 'Operação', 'regulator': 'Agência Nacional de Energia Elétrica',
             'damage_potential': 'Baixo', 'risk_category': 'Baixo', 'has_pae': 'Sim', 'has_safety_plan': 'Sim', 'has_periodic_review': 'Sim', 'last_inspection': None, 'fined': 'Não', 'owner': 'X ENERGIA S.A.'}
        self.assertEqual(radares.barragens_usinas([o], TODAY)['items'], [])

    def test_abastecimento_sem_dono_dpa_alto_sem_pae_e_critica(self):
        from app import radares
        o = {'id': 'SNISB-2', 'name': 'A', 'uf': 'RN', 'lat': -6.0, 'lon': -36.0, 'use': 'Abastecimento humano', 'phase': 'Operação', 'regulator': 'X',
             'damage_potential': 'Alto', 'risk_category': 'Alto', 'pnsb': 'Sim', 'has_pae': 'Não', 'has_safety_plan': 'Não', 'last_inspection': None, 'fined': 'Não', 'owner': 'Sem empreendedor identificado'}
        x = radares.abastecimento([o], TODAY)['items'][0]
        self.assertEqual(x['atencao'], 'Crítica')
        self.assertIn('Abastece população', x['consequencia'])

    def test_owner_pessoa_fisica_oculto(self):
        from app.connectors.snisb import owner_publico
        self.assertIn('não exibido', owner_publico('José da Silva'))
        self.assertEqual(owner_publico('SAAE de Exemplo'), 'SAAE de Exemplo')
        self.assertEqual(owner_publico(None), 'Sem empreendedor identificado')

    def test_rotas_por_setor_coerentes(self):
        self.assertNotIn('radar', CFG['setores']['energia']['rotas_operacao'])
        self.assertNotIn('radar', CFG['setores']['saneamento']['rotas_operacao'])
        self.assertIn('abastecimento', CFG['setores']['saneamento']['rotas_operacao'])
        self.assertIn('fechamento', CFG['setores']['mineracao']['rotas_operacao'])


class PerfilTests(unittest.TestCase):
    def setUp(self):
        self.acc = Accounts(Store(':memory:'))
        self.u = self.acc.register({'kind': 'cidadao', 'name': 'Maria Teste', 'email': 'maria@exemplo.invalid', 'password': 'senha12345', 'consent': True, 'uf': 'MG'})

    def test_update_name_phone_photo(self):
        import base64
        jpg = 'data:image/jpeg;base64,' + base64.b64encode(b'\xff\xd8\xff' + b'0' * 500).decode()
        u = self.acc.update_profile(self.u['id'], {'name': '  Maria  da Silva ', 'phone': '(31) 9999-0000<script>', 'avatar': jpg})
        self.assertEqual(u['name'], 'Maria da Silva')
        self.assertEqual(u['phone'], '(31) 9999-0000')
        self.assertTrue(u['avatar'].startswith('data:image/jpeg'))
        u = self.acc.update_profile(self.u['id'], {'name': 'Maria', 'avatar': ''})
        self.assertIsNone(u['avatar'])

    def test_rejects_bad_input(self):
        with self.assertRaises(WorkflowError):
            self.acc.update_profile(self.u['id'], {'name': 'M'})
        with self.assertRaises(WorkflowError):
            self.acc.update_profile(self.u['id'], {'name': 'Maria', 'avatar': 'data:text/html;base64,PHNjcmlwdD4='})

    def test_email_and_org_not_editable(self):
        u = self.acc.update_profile(self.u['id'], {'name': 'Maria', 'email': 'outro@x.com', 'cnpj': '123', 'role': 'gestor'})
        self.assertEqual((u['email'], u['role']), ('maria@exemplo.invalid', self.u['role']))


class ExtratorTests(unittest.TestCase):
    T = 'Art. 21. O empreendedor deverá enviar o Extrato de Inspeção Regular no prazo de 15 (quinze) dias após a inspeção. Caso seja identificada anomalia, o responsável técnico deverá comunicar a ANM imediatamente.'

    def test_regras_extraem_prazo_papel(self):
        from app import extrator
        r = extrator.extrair(self.T)
        self.assertEqual(len(r['obrigacoes']), 2)
        self.assertIn('15', r['obrigacoes'][0]['prazo'])
        self.assertEqual(r['obrigacoes'][1]['papel'], 'engenharia')
        for o in r['obrigacoes']:
            self.assertIn(o['trecho'], self.T)

    def test_ia_com_trecho_ou_prazo_inventado_e_recusada(self):
        from app import extrator
        fake = lambda *a: json.dumps({'obrigacoes': [
            {'obrigacao': 'x', 'prazo': '30 dias', 'papel': 'compliance', 'evidencia': 'e', 'condicao': '', 'trecho': 'O empreendedor deverá enviar o Extrato de Inspeção Regular'},
            {'obrigacao': 'y', 'prazo': '', 'papel': 'compliance', 'evidencia': 'e', 'condicao': '', 'trecho': 'deverá pagar multa'}]})
        r = extrator.extrair(self.T, llm=fake, forcar_ia=True)
        motivos = [x['motivo'] for x in r['recusadas']]
        self.assertTrue(any('prazo' in m for m in motivos))
        self.assertTrue(any('literalmente' in m for m in motivos))

    def test_decidir_exige_motivo_para_descartar(self):
        from app import extrator
        s = Store(':memory:')
        with self.assertRaises(WorkflowError):
            extrator.decidir(s, 'demo', {'obrigacao': 'x'}, {}, 'DESCARTADA', 'humano:a', '')
        self.assertEqual(extrator.decidir(s, 'demo', {'obrigacao': 'x', 'papel': 'compliance'}, {}, 'CONFIRMADA', 'humano:a')['state'], 'CONFIRMADA')
        self.assertEqual(len(extrator.listar(s, 'demo')), 1)


class RelatorioTests(unittest.TestCase):
    def test_nome_palavra_inteira_e_pj(self):
        from app import relatorio
        sigbm = [{'id': 'S1', 'owner_cnpj_root': '11111111', 'owner_name': 'BRITAMINAS LTDA', 'owner_doc_type': 'CNPJ', 'name': 'B', 'municipio': 'X', 'uf': 'MG'},
                 {'id': 'S2', 'owner_cnpj_root': '22222222', 'owner_name': 'ITAMINAS SA', 'owner_doc_type': 'CNPJ', 'name': 'C', 'municipio': 'Y', 'uf': 'MG', 'emergency_level': 'Nível 1'}]
        r = relatorio.relatorio('ITAMINAS', sigbm, {}, [], None, [], None, None)
        self.assertEqual(r['empresa'], ['ITAMINAS SA'])
        self.assertTrue(any('emergência' in d for d in r['destaques']))
        self.assertIn('error', relatorio.relatorio('ab', sigbm, {}, [], None, [], None, None))
        self.assertFalse(relatorio.relatorio('99999999', sigbm, {}, [], None, [], None, None)['encontrado'])


class NuclearTests(unittest.TestCase):
    def test_setor_nuclear_configurado_e_avaliado(self):
        nuc = BY_ID['demo-nuclear']
        r = ativos.evaluate(nuc, CFG, TODAY)
        self.assertEqual(r['setor']['id'], 'nuclear')
        kinds = {a['kind'] for a in r['alerts']}
        self.assertIn('radiologico', kinds)
        rad = [a for a in r['alerts'] if a['kind'] == 'radiologico']
        self.assertTrue(all('radioprotecao' in [x['papel'] for x in a['recipients']] for a in rad))
        self.assertIn('radiologico', CFG['setores']['nuclear']['rotas_operacao'])

    def test_normas_nucleares_por_tipo(self):
        fonte = denuncia.analyze('O densímetro nuclear ficou sem blindagem e sem placa de radiação', {'kind': 'empresa_ativo', 'setor': 'nuclear', 'tipo': 'fonte_radioativa'})
        self.assertIn('cnen_nn602', fonte['normas']); self.assertNotIn('lei10308', fonte['normas'])
        dep = denuncia.analyze('Tambores de rejeito radioativo abandonados', {'kind': 'empresa_ativo', 'setor': 'nuclear', 'tipo': 'deposito_rejeitos'})
        self.assertIn('cnen_nn801', dep['normas']); self.assertIn('lei10308', dep['normas'])

    def test_radar_radiologico_inventario(self):
        from app import radares
        minas = [{'id': 'ANM-9', 'substancia': 'MINÉRIO DE URÂNIO', 'processo': '9/1990', 'uf': 'BA', 'lat': -14.0, 'lon': -42.4, 'titular': 'X SA', 'fase': 'CONCESSÃO DE LAVRA',
                  'ultimo_evento': '418 - RAL', 'radiologico': True, 'categoria': 'nuclear'}]
        r = radares.radiologico(minas, {'items': []}, [{'id': 'SIGBM-9', 'name': 'B', 'main_ore': 'Minério de Urânio', 'lat': -14.1, 'lon': -42.4, 'dpa': 'Alta'}], {})
        self.assertEqual(len(r['items']), 2)
        self.assertTrue(all(x['atencao'] in ('Crítica', 'Alta', 'Moderada', 'Baixa') for x in r['items']))


class PerspectivaTests(unittest.TestCase):
    RES = {'state': 'GROUNDED_DEMO', 'answer': 'x', 'source_ids': ['F02'], 'missing': ['configuração do tanque'], 'actions': ['Solicitar revisão.']}

    def test_muda_so_enfase_nunca_fonte_ou_certeza(self):
        from app import perspectiva as pp
        j = pp.aplicar(dict(self.RES), {'kind': 'empresa', 'function': 'juridico', 'role': 'juridico'})
        e_ = pp.aplicar(dict(self.RES), {'kind': 'empresa', 'function': 'engenharia', 'role': 'especialista'})
        self.assertEqual((j['answer'], j['source_ids'], j['state']), (e_['answer'], e_['source_ids'], e_['state']))
        self.assertNotEqual(j['perspectiva']['foco'], e_['perspectiva']['foco'])
        self.assertTrue(any('F02' in p for p in j['perspectiva']['pontos']))
        self.assertTrue(any('tanque' in p for p in e_['perspectiva']['pontos']))

    def test_cidadao_simples_e_abstencao_sem_bloco(self):
        from app import perspectiva as pp
        self.assertEqual(pp.perfil_padrao({'kind': 'cidadao'}, None), 'simples')
        self.assertEqual(pp.perfil_padrao({'kind': 'empresa'}, None), 'tecnico')
        self.assertNotIn('perspectiva', pp.aplicar({'state': 'ABSTAIN'}, {'kind': 'cidadao'}))


class EquipeTests(unittest.TestCase):
    def setUp(self):
        self.acc = Accounts(Store(':memory:'))
        self.gestor = self.acc.register({'kind': 'empresa', 'name': 'Gestora', 'email': 'g@exemplo.invalid', 'password': 'senha12345', 'consent': True,
                                         'function': 'financas', 'org_name': 'Empresa Teste', 'cnpj': '11222333000181'})
        self.outro = self.acc.register({'kind': 'empresa', 'name': 'Outra', 'email': 'o@exemplo.invalid', 'password': 'senha12345', 'consent': True,
                                        'function': 'financas', 'org_name': 'Outra SA', 'cnpj': '11444777000161'})

    def test_convite_aceite_funcao_e_suspensao(self):
        inv = self.acc.invite(self.gestor, 'Rafa', 'rafa@exemplo.invalid', 'radioprotecao')
        self.assertEqual(self.acc.invite_info(inv['token'])['funcao'], 'Proteção radiológica')
        u = self.acc.accept_invite(inv['token'], 'senha12345', True)
        self.assertEqual((u['function'], u['role'], u['cnpj']), ('radioprotecao', 'especialista', '11222333000181'))
        self.assertIsNone(self.acc.invite_info(inv['token']))                       # convite só vale uma vez
        self.acc.change_member(self.gestor, u['id'], function='compliance', motivo='mudou de área')
        self.assertEqual(self.acc.user(u['id'])['role'], 'compliance')
        self.acc.change_member(self.gestor, u['id'], status='suspenso', motivo='desligamento')
        self.assertIsNone(self.acc.user(u['id']))
        with self.assertRaises(WorkflowError):
            self.acc.login('rafa@exemplo.invalid', 'senha12345')

    def test_regras_de_permissao(self):
        inv = self.acc.invite(self.gestor, 'Op', 'op@exemplo.invalid', 'operacao')
        op = self.acc.accept_invite(inv['token'], 'senha12345', True)
        with self.assertRaises(WorkflowError):
            self.acc.invite(op, 'X', 'x@exemplo.invalid', 'juridico')               # operação não convida
        with self.assertRaises(WorkflowError):
            self.acc.change_member(self.outro, op['id'], function='juridico', motivo='tentativa externa')   # outra empresa
        with self.assertRaises(WorkflowError):
            self.acc.change_member(self.gestor, op['id'], function='juridico', motivo='')                   # sem motivo
        self.assertEqual(len(self.acc.team(self.gestor)['membros']), 2)
        self.assertEqual(len(self.acc.team(self.outro)['membros']), 1)


class CidadaoSimplesTests(unittest.TestCase):
    def test_cidadao_sempre_simples_e_lei_em_portugues_claro(self):
        from app import perspectiva as pp
        self.assertEqual(pp.perfil_padrao({'kind': 'cidadao'}, 'tecnico'), 'simples')
        self.assertEqual(pp.perfil_padrao(None, 'tecnico'), 'simples')
        self.assertEqual(pp.perfil_padrao({'kind': 'empresa'}, 'tecnico'), 'tecnico')
        lei = {'kind': 'law', 'answer': 'Pela Lei 12.334/2010: o empreendedor ... (art. 4º, III)', 'sources': []}
        c = pp.simplificar_lei(dict(lei), {'kind': 'cidadao'})
        self.assertNotIn('art.', c['answer']); self.assertIn('199', c['answer']); self.assertTrue(c['sources'])
        self.assertEqual(pp.simplificar_lei(dict(lei), {'kind': 'empresa'})['answer'], lei['answer'])


class SSTTests(unittest.TestCase):
    def test_pgr_sem_psicossociais_alerta_unico_para_sesmt(self):
        r = ativos.evaluate(BY_ID['demo-mineracao'], CFG, TODAY)
        ps = [a for a in r['alerts'] if 'psicossociais' in a['title']]
        self.assertEqual(len(ps), 1)
        self.assertEqual(ps[0]['level'], 'Alto')
        self.assertEqual(ps[0]['recipients'][0]['papel'], 'sst')

    def test_antes_da_vigencia_nao_cobra_psicossociais(self):
        r = ativos.evaluate(BY_ID['demo-mineracao'], CFG, date(2026, 5, 1))
        self.assertFalse([a for a in r['alerts'] if 'psicossociais' in a['title']])

    def test_denuncias_sst_por_tema(self):
        self.assertIn('nr35', denuncia.analyze('trabalhando no telhado sem cinto', {'kind': 'empresa_ativo', 'setor': 'energia', 'tipo': 'subestacao'})['normas'])
        self.assertIn('nr17', denuncia.analyze('assédio e metas abusivas', {'kind': 'empresa_ativo', 'setor': 'saneamento', 'tipo': 'eta'})['normas'])

    def test_funcao_sesmt_convidavel(self):
        from app.accounts import FUNCOES, FUNCTION_TO_ROLE
        self.assertIn('seguranca_trabalho', FUNCOES)
        self.assertEqual(FUNCTION_TO_ROLE['seguranca_trabalho'], 'especialista')
