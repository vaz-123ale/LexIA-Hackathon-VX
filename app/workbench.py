"""Acompanhamento por conta. Nenhuma decisão normativa é automatizada."""
from __future__ import annotations
import html
import json
import re
import uuid
from .store import locked, now, sha256, WorkflowError, DECISION_ROLES
from .project_screen import read_project, _norm

QUESTIONS = {
    'eir': [('dam','A estrutura é barragem de mineração?'),('pnsb','Está inserida na PNSB?'),('inspection','A inspeção regular foi entre 16 e 31/03/2026?')],
    'nr20': [('building','Há instalação em edificação?'),('generator','Há grupo gerador?'),('diesel','O combustível é diesel/biodiesel?'),('tank','Há tanque de consumo?'),('offshore','É plataforma marítima?')],
    'anm': [('dam','A estrutura é barragem de mineração?'),('pnsb','O enquadramento na PNSB foi conferido?')],
    'anp_cp21': [('anp','Há atividade regulada pela ANP?')],
    'ansn': [('radiative','Há instalação radiativa?')],
}
BASE_FIELDS = ['id','version','summary','sources','conditions','exceptions','effective_from','effective_to','valid_from','valid_to','revoked_at','status','status_at_date','jurisdiction','verification','source_snapshot_id','observed_at','text_status']

def questions(topics, facts=None):
    facts = {} if facts is None else facts
    if not isinstance(facts, dict) or any(k not in {k for qs in QUESTIONS.values() for k,_ in qs} or v not in ('yes','no','unknown') for k,v in facts.items()):
        raise ValueError('Respostas técnicas inválidas.')
    return [{'id': k, 'question': label, 'answer': facts.get(k,'unknown'), 'scenario': sc}
            for sc in topics for k,label in QUESTIONS.get(sc,[])]

def reference(provisions):
    return {p['id']: {k:p.get(k) for k in BASE_FIELDS} for p in provisions}

def changes(before, after):
    return [{'id': key, 'before': before.get(key), 'after': after.get(key)}
            for key in sorted(set(before)|set(after)) if before.get(key) != after.get(key)]

def compare_projects(a, b):
    fields = ['company_label','uf','municipio','topics','facts']
    delta = changes({k:a.get(k) for k in fields}, {k:b.get(k) for k in fields})
    ca={x['id']:x for x in a.get('candidates',[])};cb={x['id']:x for x in b.get('candidates',[])}
    return {'facts_changed': delta, 'document_changed': a['sha256'] != b['sha256'],
            'candidates_added':sorted(set(cb)-set(ca)), 'candidates_removed':sorted(set(ca)-set(cb)),
            'candidates_changed': changes(reference(list(ca.values())),reference(list(cb.values()))),
            'mentions_changed':changes({x['scenario']:x for x in a.get('mentions',[])},{x['scenario']:x for x in b.get('mentions',[])}),
            'note':'Diferenças entre resultados salvos. Remoção de candidato não revoga obrigação; exige revisão. Comparação de conteúdo integral e desenhos não executada.'}

def extract_conditions(payload):
    pages,digest=read_project(payload)
    out=[]
    for p in pages:
        # Regra lexical conservadora: lista linhas, não interpreta o ato ou a licença.
        for line in p['text'].splitlines():
            line=line.strip()
            if len(line)<15 or not re.search(r'\b(devera|deverao|condicionante|apresentar|enviar|manter|realizar|comprovar|protocolar)\b',_norm(line)): continue
            dates=re.findall(r'\b\d{2}/\d{2}/\d{4}\b|\b\d+\s+dias\b',line,re.I)
            trigger=re.search(r'\b(?:após|apos|a partir de|contados? d[ao])\s+[^.;]+',line,re.I)
            evidence=re.search(r'\b(?:relatório|relatorio|protocolo|certificado|laudo)\b[^.;]*',line,re.I)
            out.append({'id':str(len(out)+1),'page':p['page'],'excerpt':line[:1600],
                        'candidate_action':line[:1600], 'deadline_text':dates or [], 'deadline_date':None,
                        'trigger':None,'responsible_function':None,'expected_evidence':None,
                        'trigger_candidate':trigger.group(0) if trigger else None,'evidence_candidate':evidence.group(0) if evidence else None,
                        'status':'PENDENTE_REVISAO','missing':['Confirmar identificação, validade e autoridade da licença.','Confirmar evento de início, prazo, responsável e evidência; não calculados por esta regra.']})
            if len(out)>=80: break
        if len(out)>=80: break
    metadata={k:str(payload.get('license_'+k,'')).strip()[:600] for k in ['name','issuer','jurisdiction','url','validity']}
    return {'sha256':digest,'items':out,'document':metadata,'document_verification':'DADOS_DECLARADOS_A_CONFERIR','mode':'EXTRACAO_LEXICAL_SEM_LLM','complete':False,
            'note':'Candidatos extraídos de linhas do documento, não obrigações confirmadas. Datas e dias são texto literal, sem cálculo de vencimento. Lista limitada a 80 linhas; conferir documento integral.'}

class Workbench:
    def __init__(self, store):
        self.store=store;self.db=store.db;self.lock=store.lock
        with self.lock:
            self.db.executescript('''
            CREATE TABLE IF NOT EXISTS wb_projects(id TEXT PRIMARY KEY,user_id INTEGER,title TEXT,result TEXT,at TEXT);
            CREATE TABLE IF NOT EXISTS wb_conditions(id TEXT PRIMARY KEY,user_id INTEGER,project_id TEXT,result TEXT,at TEXT);
            CREATE TABLE IF NOT EXISTS wb_baselines(user_id INTEGER,review_id TEXT,payload TEXT,at TEXT,PRIMARY KEY(user_id,review_id));
            CREATE TABLE IF NOT EXISTS wb_revalidations(id TEXT PRIMARY KEY,user_id INTEGER,review_id TEXT,previous TEXT,current TEXT,reason TEXT,state TEXT,decision_reason TEXT,actor TEXT,at TEXT);
            CREATE TABLE IF NOT EXISTS wb_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,kind TEXT,entity TEXT,title TEXT,at TEXT);
            CREATE TABLE IF NOT EXISTS wb_seen(user_id INTEGER PRIMARY KEY,event_seq INTEGER,audit_seq INTEGER,note_seq INTEGER,at TEXT);
            CREATE TABLE IF NOT EXISTS wb_project_reviews(user_id INTEGER,project_id TEXT,review_id TEXT,reason TEXT,at TEXT,PRIMARY KEY(user_id,project_id,review_id));
            ''');self.db.commit()

    def event(self, uid, kind, entity, title):
        self.db.execute('INSERT INTO wb_events(user_id,kind,entity,title,at) VALUES(?,?,?,?,?)',(uid,kind,entity,title[:240],now()))
        self.db.commit()

    @locked
    def save_project(self, user, title, result):
        pid=uuid.uuid4().hex;at=now()
        self.db.execute('INSERT INTO wb_projects VALUES(?,?,?,?,?)',(pid,user['id'],title[:160] or 'Projeto',json.dumps(result,ensure_ascii=False),at));self.db.commit()
        self.event(user['id'],'project.saved',pid,'Resultado de projeto salvo: '+(title[:160] or 'Projeto'))
        self.store.audit('humano:'+user['name'],'project.saved',pid,{'owner_id':user['id'],'sha256':result['sha256']})
        return self.project(user['id'],pid)

    @locked
    def project(self, uid, pid):
        row=self.db.execute('SELECT * FROM wb_projects WHERE id=? AND user_id=?',(pid,uid)).fetchone()
        if not row:raise WorkflowError('Projeto não encontrado nesta conta.')
        return {**dict(row),'result':json.loads(row['result'])}

    @locked
    def projects(self, uid):
        return [{k:r[k] for k in ['id','title','at']} for r in self.db.execute('SELECT * FROM wb_projects WHERE user_id=? ORDER BY at DESC,rowid DESC',(uid,))]

    @locked
    def link_review(self,user,pid,review,reason):
        p=self.project(user['id'],pid)
        if review['scenario'] not in p['result']['topics']:raise WorkflowError('O cenário da revisão não foi confirmado neste projeto.')
        if not reason.strip():raise WorkflowError('Justifique a associação entre projeto e revisão.')
        self.db.execute('INSERT OR IGNORE INTO wb_project_reviews VALUES(?,?,?,?,?)',(user['id'],pid,review['id'],reason[:1000],now()));self.db.commit()
        self.event(user['id'],'project.review.linked',pid,'Revisão vinculada ao dossiê: '+review['id'])
        self.store.audit('humano:'+user['name'],'project.review.linked',pid,{'owner_id':user['id'],'review_id':review['id'],'reason':reason[:1000]})
        return {'ok':True}

    @locked
    def linked_reviews(self,uid,pid):
        self.project(uid,pid)
        return [dict(r) for r in self.db.execute('SELECT * FROM wb_project_reviews WHERE user_id=? AND project_id=?',(uid,pid))]

    @locked
    def save_conditions(self,user,pid,result):
        self.project(user['id'],pid)
        cid=uuid.uuid4().hex
        self.db.execute('INSERT INTO wb_conditions VALUES(?,?,?,?,?)',(cid,user['id'],pid,json.dumps(result,ensure_ascii=False),now()));self.db.commit()
        self.event(user['id'],'license.extracted',pid,'Condicionantes candidatas extraídas para revisão')
        self.store.audit('humano:'+user['name'],'license.extracted',pid,{'owner_id':user['id'],'sha256':result['sha256'],'batch_id':cid})
        return {'id':cid,'result':result}

    @locked
    def conditions(self,uid,pid):
        self.project(uid,pid)
        return [{**dict(r),'result':json.loads(r['result'])} for r in self.db.execute('SELECT * FROM wb_conditions WHERE user_id=? AND project_id=? ORDER BY rowid',(uid,pid))]

    @locked
    def decide_condition(self,user,cid,item_id,decision,reason,fields):
        if user['role'] not in DECISION_ROLES:raise WorkflowError('Aceite/rejeição exige jurídico, compliance ou especialista.')
        if decision not in ('ACEITO_PARA_ACOMPANHAMENTO','REJEITADO') or not reason.strip():raise WorkflowError('Informe decisão e fundamentação.')
        r=self.db.execute('SELECT * FROM wb_conditions WHERE id=? AND user_id=?',(cid,user['id'])).fetchone()
        if not r:raise WorkflowError('Extração não encontrada nesta conta.')
        result=json.loads(r['result']);item=next((x for x in result['items'] if x['id']==item_id),None)
        if not item:raise WorkflowError('Item inexistente.')
        if item['status']!='PENDENTE_REVISAO':raise WorkflowError('Item já decidido; preserve a decisão e extraia nova versão se necessário.')
        item.update(status=decision,decision_reason=reason[:1000],actor=user['name'],decided_at=now())
        for k in ['trigger','responsible_function','expected_evidence']:
            item[k]=str(fields.get(k,'')).strip()[:500] or None
        if decision=='ACEITO_PARA_ACOMPANHAMENTO' and not all(item[k] for k in ['trigger','responsible_function','expected_evidence']):
            raise WorkflowError('Aceite exige evento/condição, função responsável e evidência esperada; use “a confirmar” se houver lacuna explícita.')
        self.db.execute('UPDATE wb_conditions SET result=? WHERE id=?',(json.dumps(result,ensure_ascii=False),cid));self.db.commit()
        self.event(user['id'],'license.decided',r['project_id'],'Revisão humana de condicionante registrada')
        self.store.audit('humano:'+user['name'],'license.decided',r['project_id'],{'owner_id':user['id'],'batch_id':cid,'item_id':item_id,'decision':decision,'reason':reason[:1000]})
        return result

    @locked
    def baseline(self,uid,rid):
        r=self.db.execute('SELECT * FROM wb_baselines WHERE user_id=? AND review_id=?',(uid,rid)).fetchone()
        return {**dict(r),'payload':json.loads(r['payload'])} if r else None

    @locked
    def set_baseline(self,user,rid,payload):
        old=self.baseline(user['id'],rid)
        self.db.execute('INSERT OR REPLACE INTO wb_baselines VALUES(?,?,?,?)',(user['id'],rid,json.dumps(payload,ensure_ascii=False),now()));self.db.commit()
        self.store.audit('humano:'+user['name'],'review.reference.saved',rid,{'owner_id':user['id'],'fingerprint':sha256(json.dumps(payload,sort_keys=True)),'previous':old and old['payload'],'current':payload})
        return self.baseline(user['id'],rid)

    @locked
    def propose_revalidation(self,user,rid,current,reason):
        old=self.baseline(user['id'],rid)
        if not old:raise WorkflowError('Sem referência anterior estruturada. Registre a referência atual; não é possível comprovar mudança retroativa.')
        delta=changes(old['payload'],current)
        if not delta:raise WorkflowError('Nenhuma diferença detectada nesta referência.')
        if not reason.strip():raise WorkflowError('Informe o motivo da proposta.')
        for r in self.revalidations(user['id']):
            if r['review_id']==rid and r['state']=='PENDENTE_REVISAO':raise WorkflowError('Já existe proposta pendente para esta revisão.')
        vid=uuid.uuid4().hex
        self.db.execute('INSERT INTO wb_revalidations VALUES(?,?,?,?,?,?,?,?,?,?)',(vid,user['id'],rid,json.dumps(old['payload'],ensure_ascii=False),json.dumps(current,ensure_ascii=False),reason[:1000],'PENDENTE_REVISAO',None,user['name'],now()));self.db.commit()
        self.event(user['id'],'review.revalidation',rid,'Mudança detectada: proposta de reavaliação pendente')
        self.store.audit('humano:'+user['name'],'review.revalidation.proposed',rid,{'owner_id':user['id'],'proposal_id':vid,'reason':reason[:1000]})
        return {'id':vid,'changes':delta}

    @locked
    def revalidations(self,uid):
        return [{**dict(r),'previous':json.loads(r['previous']),'current':json.loads(r['current'])} for r in self.db.execute('SELECT * FROM wb_revalidations WHERE user_id=? ORDER BY rowid DESC',(uid,))]

    @locked
    def decide_revalidation(self,user,vid,decision,reason,current):
        if user['role'] not in DECISION_ROLES:raise WorkflowError('Reavaliação exige jurídico, compliance ou especialista.')
        r=next((r for r in self.revalidations(user['id']) if r['id']==vid),None)
        if not r or r['state']!='PENDENTE_REVISAO':raise WorkflowError('Proposta pendente não encontrada nesta conta.')
        if decision not in ('REVALIDADO','REJEITADO') or not reason.strip():raise WorkflowError('Informe decisão e fundamentação.')
        if decision=='REVALIDADO' and r['current']!=current:raise WorkflowError('A fonte mudou novamente; a referência desta proposta ficou desatualizada.')
        self.db.execute('UPDATE wb_revalidations SET state=?,decision_reason=?,actor=? WHERE id=?',(decision,reason[:1000],user['name'],vid));self.db.commit()
        if decision=='REVALIDADO':self.set_baseline(user,r['review_id'],current)
        self.event(user['id'],'review.revalidated',r['review_id'],'Decisão sobre reavaliação registrada: '+decision)
        self.store.audit('humano:'+user['name'],'review.revalidation.decided',r['review_id'],{'owner_id':user['id'],'proposal_id':vid,'decision':decision,'reason':reason[:1000]})
        return {'id':vid,'state':decision,'note':'A decisão anterior e o estado do workflow original foram preservados.'}

    @locked
    def summary(self,uid,review_ids,notes):
        cursor=self.db.execute('SELECT * FROM wb_seen WHERE user_id=?',(uid,)).fetchone()
        old=dict(cursor) if cursor else {'event_seq':0,'audit_seq':0,'note_seq':0}
        events=[dict(r) for r in self.db.execute('SELECT * FROM wb_events WHERE user_id=? AND seq>? ORDER BY seq LIMIT 100',(uid,old['event_seq']))]
        audits=[]
        if review_ids:
            placeholders=','.join('?' for _ in review_ids)
            for row in self.db.execute(f'SELECT * FROM audit WHERE seq>? AND entity IN ({placeholders}) ORDER BY seq',(old['audit_seq'],*sorted(review_ids))):
                entry={**dict(row),'payload':json.loads(row['payload'])}
                if entry['payload'].get('owner_id') in (None,uid):audits.append(entry)
                if len(audits)>=100:break
        notices=[n for n in sorted(notes,key=lambda n:n['id']) if n['id']>old['note_seq']][:100]
        mark={'event_seq':max([old['event_seq']]+[e['seq'] for e in events]),'audit_seq':max([old['audit_seq']]+[a['seq'] for a in audits]),'note_seq':max([old['note_seq']]+[n['id'] for n in notices])}
        return {'first_access':not bool(cursor),'since':cursor['at'] if cursor else None,'events':events,
                'review_events':[{'seq':a['seq'],'review_id':a['entity'],'action':a['action'],'at':a['at']} for a in audits],
                'notices':notices,'watermark':mark,'note':'Primeiro acesso: histórico disponível; nos próximos, somente eventos após o recorte marcado. Até 100 por categoria; marque e atualize para continuar.'}

    @locked
    def mark_seen(self,uid,mark,allowed):
        # Recorte só pode avançar até o retorno atual autorizado pelo servidor.
        if not isinstance(mark,dict) or any(type(mark.get(k)) is not int or not 0<=mark[k]<=allowed[k] for k in allowed):raise WorkflowError('Marcador inválido.')
        old=self.db.execute('SELECT * FROM wb_seen WHERE user_id=?',(uid,)).fetchone()
        mark={k:max(mark[k],old[k] if old else 0) for k in allowed}
        self.db.execute('INSERT OR REPLACE INTO wb_seen VALUES(?,?,?,?,?)',(uid,mark['event_seq'],mark['audit_seq'],mark['note_seq'],now()));self.db.commit()
        return {'ok':True}

def dossier(project,batches,reviews=()):
    """HTML independente com conteúdo escapado e cópia integral do resultado salvo."""
    esc=lambda x:html.escape(str(x),quote=True)
    result=project['result']
    sections=[f'<h1>Dossiê do projeto: {esc(project["title"])}</h1>',f'<p>Conta proprietária: {esc(project["user_id"])} · salvo {esc(project["at"])}</p>',
              '<p>Avaliação preliminar. Não é parecer, licença, laudo ou certificação. Resultados de regras locais; revisão humana obrigatória.</p>',
              f'<p>SHA-256 do documento: <code>{esc(result["sha256"])}</code> · data-base {esc(result["as_of"])}</p>']
    for p in result.get('candidates',[]):
        sections.append(f'<h2>{esc(p["document"])} — {esc(p["provision"])}</h2><p>{esc(p["version"])} · {esc(p["jurisdiction"])} · {esc(p["status_at_date"])}</p><p>{esc(p["summary"])}</p>')
        for s in p['sources']:
            url=s['url']
            sections.append(f'<p>Fonte {esc(s["id"])}: '+(f'<a href="{esc(url)}">{esc(s["title"])}</a>' if url.startswith('https://') else esc(url))+'</p>')
    sections+=['<h2>Fatos, perguntas, menções e lacunas registrados</h2>',f'<pre>{esc(json.dumps(result,ensure_ascii=False,indent=2))}</pre>',
               '<h2>Condicionantes e decisões humanas</h2>',f'<pre>{esc(json.dumps(batches,ensure_ascii=False,indent=2))}</pre>',
               '<h2>Revisões vinculadas, decisões e evidências</h2>',f'<p>Estado consultado na exportação: {esc(now())}. Vínculo não implica aplicabilidade confirmada.</p><pre>{esc(json.dumps(reviews,ensure_ascii=False,indent=2))}</pre>']
    return '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Dossiê do projeto</title><style>body{font:15px/1.5 system-ui;max-width:980px;margin:40px auto;padding:20px;color:#152342}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f0f5fc;padding:20px}a{color:#064bba}h2{margin-top:32px}@media print{body{margin:0}pre{font-size:10px}}</style>'+''.join(sections)+'</html>'
