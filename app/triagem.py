"""Triagem e repasse (regra triagem-v1): quem recebe algo que não é da sua área repassa para a função certa da empresa.

Vale para alerta, mudança normativa e denúncia recebida. O repasse avisa as pessoas da função de destino (notificação),
fica na trilha de auditoria e aparece no próprio item ("repassado ao Jurídico por Ana, com a nota ...").
"""
from __future__ import annotations

from .accounts import FUNCOES
from .store import WorkflowError, now

RULE_VERSION = 'triagem-v1'
TIPOS = {'alerta': ('Alerta', '#/compliance'), 'mudanca': ('Mudança normativa', '#/impact'), 'denuncia': ('Denúncia recebida', '#/compliance'),
         'sistema': ('Impacto em sistema', '#/sistemas')}
SCHEMA = """
CREATE TABLE IF NOT EXISTS repasses(
  id INTEGER PRIMARY KEY AUTOINCREMENT, org TEXT, tipo TEXT, ref TEXT, titulo TEXT, de_nome TEXT, de_funcao TEXT, para TEXT, nota TEXT, created_at TEXT);
"""


def _db(store):
    with store.lock:
        store.db.executescript(SCHEMA)
        store.db.commit()


def repassar(store, accounts, u: dict, org: str, tipo: str, ref: str, titulo: str, para: str, nota: str) -> dict:
    if tipo not in TIPOS:
        raise WorkflowError('Tipo de item inválido.')
    if para not in FUNCOES:
        raise WorkflowError('Escolha a área de destino.')
    if para == u.get('function'):
        raise WorkflowError('O item já é da sua área.')
    ref, titulo, nota = str(ref)[:120], str(titulo or '')[:200], str(nota or '').strip()[:400]
    if not ref:
        raise WorkflowError('Item não identificado.')
    _db(store)
    with store.lock:
        cur = store.db.execute('INSERT INTO repasses(org,tipo,ref,titulo,de_nome,de_funcao,para,nota,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                               (org, tipo, ref, titulo, u.get('name'), u.get('function'), para, nota or None, now()))
        store.db.commit()
    rot, link = TIPOS[tipo]
    accounts.notify(f'orgfunc:{org}:{para}', 'repasse', f'{rot} repassado para {FUNCOES[para]}: {titulo[:110]}',
                    f"De {u.get('name')}{' · ' + nota if nota else ''}", link, 'TRIAGEM')
    store.audit(u.get('name') or 'usuario', 'triagem.repasse', org, {'id': cur.lastrowid, 'tipo': tipo, 'ref': ref, 'para': para})
    return {'id': cur.lastrowid, 'para': para, 'para_rotulo': FUNCOES[para]}


def listar(store, org: str, tipo: str | None = None) -> list[dict]:
    _db(store)
    q, a = 'SELECT id,tipo,ref,titulo,de_nome,de_funcao,para,nota,created_at FROM repasses WHERE org=?', [org]
    if tipo:
        q += ' AND tipo=?'; a.append(tipo)
    with store.lock:
        rows = [dict(r) for r in store.db.execute(q + ' ORDER BY id DESC LIMIT 300', a)]
    for r in rows:
        r['para_rotulo'] = FUNCOES.get(r['para'], r['para'])
    return rows
