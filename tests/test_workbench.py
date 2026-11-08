import os as _os
_os.environ['TORRE_LLM'] = '0'  # testes nunca chamam provedor externo
import json
import threading
import unittest
import urllib.request
import urllib.error
from datetime import date
from http.server import ThreadingHTTPServer
from app import server
from app.store import Store, WorkflowError
from app.workbench import Workbench, questions, reference, changes, compare_projects, extract_conditions, dossier
from app.project_screen import screen_project


def payload(**kw):
    return {'authorized':True,'description':'Projeto demonstrativo com gerador diesel e tanque em edificio.','scope_confirmed':True,'topics':['nr20'],**kw}

def screen(**kw):
    return screen_project(payload(**kw),server.load('provisions.json'),server.load('sources.json'),server.load('scenarios.json'),date(2026,11,6))

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(':memory:'); self.w=Workbench(self.store)
        self.u={'id':1,'name':'Ana teste','role':'juridico'}

    def tearDown(self):self.store.db.close()

    def test_questions_unknown_no_and_invalid(self):
        self.assertTrue(all(x['answer']=='unknown' for x in questions(['nr20'])))
        self.assertEqual(questions(['anm'],{'dam':'no'})[0]['answer'],'no')
        for bad in [['bad'],{'dam':'inventado'},{'fake':'yes'}]:
            with self.assertRaises(ValueError):questions(['anm'],bad)

    def test_exclusions_are_not_legal_exemptions(self):
        r=screen(facts={'generator':'no'})
        self.assertEqual(len(r['excluded']),4)  # inclui o tema EIR
        self.assertTrue(r['conflicts'])
        self.assertTrue(r['candidates'])
        self.assertIn('não é conclusão',r['excluded'][0]['reason'])

    def test_unanswered_fields_remain_missing(self):
        r=screen(facts={'generator':'yes'})
        self.assertTrue(any('Pergunta sem resposta:' in m for m in r['missing']))
        self.assertEqual(r['facts']['generator'],'yes')

    def test_project_ownership_and_saved_snapshot(self):
        p=self.w.save_project(self.u,'Teste',screen())
        self.assertEqual(self.w.project(1,p['id'])['result']['sha256'],screen()['sha256'])
        self.assertEqual(self.w.projects(2),[])
        with self.assertRaises(WorkflowError):self.w.project(2,p['id'])

    def test_compare_changes_in_facts_scope_and_text(self):
        a=screen(facts={'generator':'yes'})
        b=screen(description='Projeto demonstrativo de barragem de rejeitos em area de mineracao.',topics=['anm'])
        r=compare_projects(a,b)
        self.assertTrue(r['document_changed']);self.assertTrue(r['facts_changed'])
        self.assertTrue(r['candidates_added']);self.assertTrue(r['candidates_removed']);self.assertTrue(r['mentions_changed'])

    def test_same_project_has_no_difference(self):
        r=compare_projects(screen(),screen())
        self.assertFalse(r['facts_changed']);self.assertFalse(r['document_changed']);self.assertFalse(r['candidates_changed'])

    def test_license_extraction_literal_deadline_and_missing_fields(self):
        r=extract_conditions(payload(description='Licenca demonstrativa publica.\nDevera apresentar relatorio em 30 dias apos o inicio da operacao.'))
        self.assertEqual(len(r['items']),1)
        i=r['items'][0];self.assertEqual(i['deadline_text'],['30 dias'])
        self.assertIsNone(i['deadline_date']);self.assertIsNone(i['trigger']);self.assertFalse(r['complete'])

    def test_license_without_candidates_is_not_complete(self):
        r=extract_conditions(payload(description='Documento demonstrativo com descricao geografica sem ordem ou requisito.'))
        self.assertEqual(r['items'],[]);self.assertFalse(r['complete'])

    def test_license_decision_role_and_immutable_decision(self):
        p=self.w.save_project(self.u,'Teste',screen())
        b=self.w.save_conditions(self.u,p['id'],extract_conditions(payload(description='Licenca demonstrativa publica.\nDevera enviar relatorio assinado em 01/12/2027.')))
        with self.assertRaises(WorkflowError):self.w.decide_condition({**self.u,'role':'operacao'},b['id'],'1','REJEITADO','Conferido',{})
        with self.assertRaises(WorkflowError):self.w.decide_condition(self.u,b['id'],'1','ACEITO_PARA_ACOMPANHAMENTO','Conferido',{})
        fields={'trigger':'Emissao','responsible_function':'Engenharia','expected_evidence':'Protocolo'}
        r=self.w.decide_condition(self.u,b['id'],'1','ACEITO_PARA_ACOMPANHAMENTO','Conferido',fields)
        self.assertEqual(r['items'][0]['actor'],self.u['name'])
        with self.assertRaises(WorkflowError):self.w.decide_condition(self.u,b['id'],'1','REJEITADO','Troca',{})
        with self.assertRaises(WorkflowError):self.w.conditions(2,p['id'])

    def test_reference_missing_and_revalidation_keeps_old_record(self):
        before={'p':{'version':'v1'}};after={'p':{'version':'v2'}}
        with self.assertRaises(WorkflowError):self.w.propose_revalidation(self.u,'review',after,'Mudou')
        self.w.set_baseline(self.u,'review',before)
        v=self.w.propose_revalidation(self.u,'review',after,'Mudou')
        self.assertEqual(self.w.baseline(1,'review')['payload'],before)
        with self.assertRaises(WorkflowError):self.w.propose_revalidation(self.u,'review',after,'Duplicada')
        with self.assertRaises(WorkflowError):self.w.decide_revalidation(self.u,v['id'],'REVALIDADO','Conferido',{'p':{'version':'v3'}})
        self.w.decide_revalidation(self.u,v['id'],'REVALIDADO','Conferido',after)
        self.assertEqual(self.w.baseline(1,'review')['payload'],after)
        self.assertEqual(self.w.revalidations(1)[0]['previous'],before)
        self.assertTrue(self.store.verify_chain()['ok'])

    def test_summary_read_marker_is_explicit_and_per_account(self):
        self.w.event(1,'project.saved','p','Meu projeto');self.w.event(2,'project.saved','q','Segredo outra conta')
        a=self.w.summary(1,set(),[]);b=self.w.summary(1,set(),[])
        self.assertEqual(a['watermark'],b['watermark']);self.assertTrue(a['first_access'])
        self.assertEqual([x['title'] for x in a['events']],['Meu projeto'])
        self.w.mark_seen(1,a['watermark'],a['watermark'])
        self.assertEqual(self.w.summary(1,set(),[])['events'],[])
        self.assertTrue(self.w.summary(2,set(),[])['first_access'])

    def test_events_arriving_after_read_are_not_lost(self):
        self.w.event(1,'x','p','A');a=self.w.summary(1,set(),[])
        self.w.event(1,'x','p','B');current=self.w.summary(1,set(),[])
        self.w.mark_seen(1,a['watermark'],current['watermark'])
        self.assertEqual([x['title'] for x in self.w.summary(1,set(),[])['events']],['B'])

    def test_summary_excludes_audit_payloads_owned_by_another_account(self):
        self.store.audit('user','review.reference.saved','r',{'owner_id':2,'secret':'other'})
        self.store.audit('user','review.transition','r',{})
        r=self.w.summary(1,{'r'},[])
        self.assertEqual(len(r['review_events']),1)
        self.assertNotIn('secret',json.dumps(r))

    def test_summary_rejects_invalid_watermark(self):
        with self.assertRaises(WorkflowError):self.w.mark_seen(1,{'event_seq':99,'audit_seq':0,'note_seq':0},{'event_seq':0,'audit_seq':0,'note_seq':0})

    def test_dossier_escapes_html_and_includes_trace(self):
        p=self.w.save_project(self.u,'<script>alert(1)</script>',screen())
        text=dossier(p,[])
        self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
        self.assertIn(p['result']['sha256'],text);self.assertIn('NR-20',text)


class WorkbenchHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=Store(':memory:');server.seed(cls.store)
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.make_handler(cls.store))
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()

    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close()

    def call(self,path,body=None,cookie=None):
        headers={'Content-Type':'application/json'}
        if cookie:headers['Cookie']=cookie
        req=urllib.request.Request(f'http://127.0.0.1:{self.http.server_address[1]}'+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req) as r:
                raw=r.read();return r.status,json.loads(raw) if r.headers.get('Content-Type','').startswith('application/json') else raw.decode(),r.headers
        except urllib.error.HTTPError as r:return r.code,json.loads(r.read()),r.headers

    def login(self,who='ana'):
        return self.call('/api/auth/login',{'email':who+'@demo.lexia.app','password':'LexIA2026demo'})[2].get('Set-Cookie').split(';')[0]

    def save(self,ck,**kw):
        st,p,_=self.call('/api/workbench/save',payload(consent_save=True,**kw),ck)
        self.assertEqual(st,201,p);return p

    def test_new_routes_auth_and_citizen(self):
        self.assertEqual(self.call('/api/workbench/projects')[0],401)
        self.assertEqual(self.call('/api/workbench/projects',cookie=self.login('joana'))[0],403)
        self.assertEqual(self.call('/api/workbench/save',payload(consent_save=True),self.login('joana'))[0],403)

    def test_confirmed_decision_records_structured_reference(self):
        ck=self.login();rid='nr20:A-01'
        for state in ['REVIEW_PENDING','CONFIRMED']:
            st,r,_=self.call('/api/reviews/transition',{'review_id':rid,'to_state':state,'reason':'Dispositivo conferido','source_version':'referencia de teste','as_of':'2026-11-06'},ck)
            self.assertEqual(st,200,r)
        st,r,_=self.call('/api/workbench/revalidations',cookie=ck)
        self.assertEqual(next(x for x in r['items'] if x['review_id']==rid)['status'],'SEM_DIFERENCA')

    def test_save_requires_consent_and_confirmed_scope(self):
        ck=self.login()
        self.assertEqual(self.call('/api/workbench/save',payload(),ck)[0],400)
        self.assertEqual(self.call('/api/workbench/save',payload(consent_save=True,scope_confirmed=False),ck)[0],400)

    def test_cross_account_list_fetch_compare_and_export_denied(self):
        ana=self.login();bruno=self.login('bruno');p=self.save(ana)
        self.assertFalse(any(x['id']==p['id'] for x in self.call('/api/workbench/projects',cookie=bruno)[1]))
        for path in ['/api/workbench/project?id=','/api/workbench/dossier?id=']:
            self.assertEqual(self.call(path+p['id'],cookie=bruno)[0],400)
        self.assertEqual(self.call('/api/workbench/compare',{'before':p['id'],'after':p['id']},bruno)[0],409)

    def test_dossier_and_comparison_work_end_to_end(self):
        ck=self.login();a=self.save(ck);b=self.save(ck,topics=['anm'])
        st,r,_=self.call('/api/workbench/compare',{'before':a['id'],'after':b['id']},ck)
        self.assertEqual(st,200);self.assertTrue(r['candidates_added'])
        st,text,h=self.call('/api/workbench/dossier?id='+a['id'],cookie=ck)
        self.assertEqual(st,200);self.assertIn('attachment;',h.get('Content-Disposition'));self.assertIn(a['result']['sha256'],text)

    def test_revalidation_of_temporal_change_does_not_modify_workflow(self):
        ck=self.login();rid='anm:B-01'
        before=self.store.review(rid)['state']
        self.assertEqual(self.call('/api/workbench/reference',{'review_id':rid,'as_of':'2026-11-06'},ck)[0],200)
        st,r,_=self.call('/api/workbench/revalidations?as_of=2027-08-02',cookie=ck)
        self.assertEqual(st,200);self.assertEqual(next(x for x in r['items'] if x['review_id']==rid)['status'],'MUDANCA_DETECTADA')
        st,v,_=self.call('/api/workbench/revalidate',{'review_id':rid,'reason':'Conferir marco','as_of':'2027-08-02'},ck)
        self.assertEqual(st,201,v)
        st,r,_=self.call('/api/workbench/revalidation/decide',{'id':v['id'],'decision':'REVALIDADO','reason':'Conferido','as_of':'2027-08-02'},ck)
        self.assertEqual(st,200,r);self.assertEqual(self.store.review(rid)['state'],before)

    def test_license_requires_competent_role(self):
        ck=self.login('diego');p=self.save(ck)
        st,b,_=self.call('/api/workbench/conditions/extract',payload(project_id=p['id'],consent_save=True,description='Licenca demonstrativa publica.\nDevera enviar relatorio em 30 dias.'),ck)
        self.assertEqual(st,201,b)
        self.assertEqual(self.call('/api/workbench/conditions/decide',{'batch_id':b['id'],'item_id':'1','decision':'REJEITADO','reason':'Conferido'},ck)[0],403)

    def test_summary_marker_and_exclusions(self):
        ck=self.login('fabio');self.save(ck)
        st,s,_=self.call('/api/workbench/summary',cookie=ck);self.assertEqual(st,200);self.assertTrue(s['events'])
        self.assertEqual(self.call('/api/workbench/seen',{'watermark':s['watermark']},ck)[0],200)
        self.assertEqual(self.call('/api/workbench/summary',cookie=ck)[1]['events'],[])
        st,r,_=self.call('/api/workbench/exclusions',cookie=ck);self.assertEqual(st,200);self.assertTrue(r['items'])

    def test_other_account_cannot_decide_license(self):
        ck=self.login();p=self.save(ck)
        st,b,_=self.call('/api/workbench/conditions/extract',payload(project_id=p['id'],consent_save=True,description='Licenca demonstrativa publica.\nDevera apresentar relatorio assinado.'),ck)
        self.assertEqual(st,201)
        self.assertEqual(self.call('/api/workbench/conditions/decide',{'batch_id':b['id'],'item_id':'1','decision':'REJEITADO','reason':'Rejeito'},self.login('bruno'))[0],409)

    def test_linked_review_exports_decisions_but_rejects_wrong_scope(self):
        ck=self.login();p=self.save(ck)
        st,r,_=self.call('/api/workbench/link-review',{'project_id':p['id'],'review_id':'nr20:A-01','reason':'Projeto correspondente ao ativo sintetico'},ck)
        self.assertEqual(st,200,r)
        st,p2,_=self.call('/api/workbench/project?id='+p['id'],cookie=ck)
        self.assertEqual(p2['linked_reviews'][0]['review_id'],'nr20:A-01')
        st,text,_=self.call('/api/workbench/dossier?id='+p['id'],cookie=ck)
        self.assertIn('nr20:A-01',text);self.assertIn('transitions',text)
        self.assertEqual(self.call('/api/workbench/link-review',{'project_id':p['id'],'review_id':'anm:B-01','reason':'Outro escopo'},ck)[0],409)
        self.assertEqual(self.call('/api/workbench/link-review',{'project_id':p['id'],'review_id':'nr20:A-01','reason':'Tentar acesso alheio'},self.login('bruno'))[0],409)

    def test_private_project_events_are_not_exposed_by_legacy_audit_routes(self):
        ck=self.login();p=self.save(ck)
        for path in ['/api/audit?limit=10000','/api/export/audit.json','/api/events']:
            st,data,_=self.call(path,cookie=self.login('bruno'))
            self.assertEqual(st,200)
            self.assertNotIn(p['id'],json.dumps(data))
            self.assertNotIn(p['id'],json.dumps(self.call(path)[1]))
