"""Triagem local de projeto: menções não são fatos nem obrigações confirmadas."""
from __future__ import annotations
import base64
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from .ingest import INTERNAL_MARKS, INJECTION
from .temporal import snapshot

TOPICS = {
    'eir': ('Barragens · Extrato de Inspeção Regular (EIR)', r'\b(eir|inspecao regular|extrato de inspecao)\b'),
    'nr20': ('Combustíveis, tanques e geradores', r'\b(diesel|biodiesel|gerador|geradores|tanque|inflamaveis|combustiveis)\b'),
    'anm': ('Barragens de mineração', r'\b(barragem|barragens|rejeitos)\b'),
    'anp_cp21': ('Atividade regulada pela ANP / consulta', r'\b(anp|petroleo|gas natural)\b'),
    'ansn': ('Instalação radiativa / CNEN / ANSN', r'\b(radiativa|radiativo|radioativo|cnen|ansn)\b'),
}
PDF_WORKER = """
import sys,io,json
from pypdf import PdfReader
r=PdfReader(io.BytesIO(sys.stdin.buffer.read()),strict=True)
if r.is_encrypted: raise ValueError('PDF cifrado')
if len(r.pages)>40: raise ValueError('Mais de 40 paginas')
out=[];total=0
for i,p in enumerate(r.pages):
 t=p.extract_text() or '';total+=len(t)
 if total>60000: raise ValueError('Texto extraido excede o limite')
 out.append({'page':i+1,'text':t})
print(json.dumps(out,ensure_ascii=True))
"""

def _norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if not unicodedata.combining(c))

def read_project(payload):
    if payload.get('authorized') is not True:
        raise ValueError('Confirme autorização e use somente projeto público ou sintético nesta demo.')
    encoded = payload.get('pdf_base64')
    if encoded:
        if not isinstance(encoded, str) or len(encoded) > 1400000:
            raise ValueError('PDF excede 1 MB.')
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            raise ValueError('Arquivo PDF inválido.') from None
        if len(raw) > 1048576 or not raw.startswith(b'%PDF-'):
            raise ValueError('Envie um PDF válido com até 1 MB.')
        try:
            proc = subprocess.run([sys.executable, '-I', '-c', PDF_WORKER], input=raw,
                                  capture_output=True, timeout=12)
        except subprocess.TimeoutExpired:
            raise ValueError('Extração excedeu o tempo permitido. Use uma descrição textual.') from None
        if proc.returncode:
            msg = 'Leitura PDF indisponível: instale requirements-project.txt.' if b'No module named' in proc.stderr else 'PDF ilegível, cifrado ou acima dos limites (40 páginas/60 mil caracteres).'
            raise ValueError(msg)
        pages = json.loads(proc.stdout)
    else:
        text = payload.get('description', '')
        if not isinstance(text, str) or len(text) > 60000:
            raise ValueError('Descrição excede 60 mil caracteres.')
        raw = text.encode('utf-8')
        pages = [{'page': None, 'text': text}]
    text = '\n'.join(p['text'] for p in pages)
    if len(text.strip()) < 40:
        raise ValueError('Sem texto suficiente. PDF digitalizado exige OCR externo autorizado ou descrição textual.')
    if INTERNAL_MARKS.search(text):
        raise ValueError('Marcação INTERNA/CONFIDENCIAL/RESTRITO: documento bloqueado nesta demo.')
    if INJECTION.search(text):
        raise ValueError('Possível instrução maliciosa no documento: triagem bloqueada para revisão.')
    return pages, hashlib.sha256(raw).hexdigest()

def screen_project(payload, provisions, sources, scenarios, when: date):
    uf = str(payload.get('uf', '')).strip().upper()
    if uf and uf not in 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split():
        raise ValueError('UF inválida.')
    pages, digest = read_project(payload)
    mentions = []
    for sid, (label, pattern) in TOPICS.items():
        for page in pages:
            match = re.search(pattern, _norm(page['text']))
            if match:
                # Acentos decompostos podem alterar offsets: apresentar a linha como trecho.
                lines = page['text'].splitlines()
                excerpt = next((line for line in lines if re.search(pattern, _norm(line))), page['text'])[:420]
                mentions.append({'scenario': sid, 'label': label, 'page': page['page'], 'excerpt': excerpt,
                                 'status': 'MENCAO_A_CONFIRMAR'})
                break
    selected = payload.get('topics', [])
    if not isinstance(selected, list) or any(not isinstance(s, str) or s not in TOPICS for s in selected):
        raise ValueError('Escopo inválido.')
    confirmed = payload.get('scope_confirmed') is True
    selected = list(dict.fromkeys(selected)) if confirmed else []
    pids = {pid for s in scenarios if s['id'] in selected for pid in s['provisions']}
    source_map = {s['id']: s for s in sources}
    missing = ['Confirmar atividade real, atributos técnicos, porte, condições e exceções de cada dispositivo.',
               'Cobertura estadual, municipal, licenças e normas técnicas ainda não curada nesta triagem.']
    if not uf: missing.append('UF do projeto não informada.')
    if not str(payload.get('municipio', '')).strip(): missing.append('Município do projeto não informado.')
    candidates = []
    for p in snapshot(provisions, when):
        if p['id'] not in pids: continue
        candidates.append({'id': p['id'], 'document': p['document'], 'provision': p['provision'],
            'version': p['version'], 'jurisdiction': p['jurisdiction'], 'status_at_date': p['status'],
            'valid_from': p.get('valid_from'), 'valid_to': p.get('valid_to'), 'conditions': p.get('conditions', []),
            'exceptions': p.get('exceptions', []), 'summary': p['summary'], 'verification': p.get('verification'),
            'text_status': p.get('text_status'), 'sources': [{'id': sid, 'title': source_map[sid]['title'], 'url': source_map[sid]['url'], 'verified_on': source_map[sid].get('verified_on')} for sid in p['sources'] if sid in source_map],
            'finding_status': 'CANDIDATO_A_REVISAO', 'missing': missing})
    from .workbench import questions
    interview = questions(selected or [m['scenario'] for m in mentions], payload.get('facts'))
    unanswered = [q['question'] for q in interview if q['answer']=='unknown']
    missing.extend('Pergunta sem resposta: '+q for q in unanswered)
    excluded = [{'scenario':sid,'label':label,'reason':'Atividade não confirmada pelo usuário; fora do recorte de recuperação, não é conclusão de não incidência.' if confirmed else 'Escopo ainda não confirmado; não foram sugeridas obrigações.'}
                for sid,(label,_) in TOPICS.items() if sid not in selected]
    conflicts = [{'question':q['question'],'answer':q['answer'],'note':'Tema mencionado e resposta negativa. Confira se o trecho nega, descarta ou apenas cita a atividade; nenhuma conclusão automática.'}
                 for q in interview if q['answer']=='no' and q['scenario'] in {m['scenario'] for m in mentions}]
    return {'company_label': str(payload.get('company', ''))[:160], 'sha256': digest, 'as_of': when.isoformat(),
        'mode': 'REGRAS_LOCAIS_SEM_LLM', 'state': 'CANDIDATOS' if candidates else 'ESCOPO_A_CONFIRMAR' if mentions and not confirmed else 'ABSTAIN',
        'mentions': mentions, 'candidates': candidates, 'missing': missing, 'topics': selected,
        'questions': interview, 'facts': {q['id']:q['answer'] for q in interview}, 'excluded':excluded,'conflicts':conflicts,
        'uf':uf,'municipio':str(payload.get('municipio',''))[:100],
        'privacy': 'Documento processado em memória; não gravado, não incluído no corpus e não enviado a modelo de IA.',
        'disclaimer': 'Triagem preliminar limitada ao corpus curado. Não é lista completa de normas, parecer ou confirmação de aplicabilidade. Nome empresarial não determina obrigações. Menções podem ser negativas ou hipotéticas; confirme o escopo.'}
