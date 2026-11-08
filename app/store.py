"""Persistência local (SQLite, biblioteca padrão) para revisão humana, evidências,
ingestão, caixa de saída de integrações e trilha de auditoria encadeada por hash.

Nada aqui envia dados para fora da máquina.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS = '0' * 64

# Fluxo obrigatório: a IA/regra só cria rascunho; humano decide.
TRANSITIONS = {
    'DRAFT': {'REVIEW_PENDING'},
    'REVIEW_PENDING': {'CONFIRMED', 'REJECTED', 'DRAFT'},
    'CONFIRMED': {'ACTION_TRACKING'},
    'REJECTED': {'DRAFT'},
    'ACTION_TRACKING': {'CLOSED'},
    'CLOSED': set(),
}
DECISION_ROLES = {'juridico', 'especialista', 'compliance'}
ROLES = {'juridico', 'especialista', 'compliance', 'operacao', 'gestor', 'auditor'}

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews(
  id TEXT PRIMARY KEY, asset_id TEXT, scenario TEXT, finding_state TEXT, headline TEXT,
  state TEXT, assignee TEXT, created_at TEXT, updated_at TEXT, source_ids TEXT, provisions TEXT);
CREATE TABLE IF NOT EXISTS transitions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT, from_state TEXT, to_state TEXT,
  actor TEXT, role TEXT, reason TEXT, source_version TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT, item TEXT, description TEXT,
  sha256 TEXT, actor TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS ingestions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, issuer TEXT, url TEXT, final_url TEXT,
  sha256 TEXT, status TEXT, checks TEXT, collected_at TEXT);
CREATE TABLE IF NOT EXISTS outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT, connector TEXT, review_id TEXT, payload TEXT,
  status TEXT, actor TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS financial_scenarios(
  id INTEGER PRIMARY KEY AUTOINCREMENT, review_id TEXT, payload TEXT, result TEXT, estimator_version TEXT, actor TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS entity_links(
  id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT, group_label TEXT, decision TEXT, reason TEXT, actor TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS contingency_steps(
  dam_id TEXT, step_id TEXT, status TEXT, note TEXT, actor TEXT, at TEXT, PRIMARY KEY(dam_id, step_id));
CREATE TABLE IF NOT EXISTS drafts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, dam_id TEXT, kind TEXT, body TEXT, sha256 TEXT, state TEXT,
  created_by TEXT, created_at TEXT, decided_by TEXT, decided_at TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS audit(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, actor TEXT, action TEXT, entity TEXT,
  payload TEXT, prev_hash TEXT, hash TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf8')).hexdigest()


class WorkflowError(ValueError):
    pass


def locked(fn):
    """Serializa o acesso à conexão SQLite compartilhada entre threads do servidor."""
    import functools

    @functools.wraps(fn)
    def wrapper(self, *a, **k):
        with self.lock:
            return fn(self, *a, **k)
    return wrapper


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ':memory:':
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        cols = {r['name'] for r in self.db.execute('PRAGMA table_info(reviews)')}
        if 'assigned_function' not in cols:  # migração v3
            self.db.execute('ALTER TABLE reviews ADD COLUMN assigned_function TEXT')
        if 'origin' not in cols:
            self.db.execute("ALTER TABLE reviews ADD COLUMN origin TEXT DEFAULT 'CENARIO_HIPOTETICO'")
        self.db.commit()

    # ---------- auditoria encadeada ----------
    def audit(self, actor: str, action: str, entity: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            row = self.db.execute('SELECT hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
            prev = row['hash'] if row else GENESIS
            at = now()
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            digest = sha256('|'.join([prev, at, actor, action, entity, body]))
            cur = self.db.execute('INSERT INTO audit(at,actor,action,entity,payload,prev_hash,hash) VALUES(?,?,?,?,?,?,?)',
                                  (at, actor, action, entity, body, prev, digest))
            self.db.commit()
            return {'seq': cur.lastrowid, 'hash': digest, 'prev_hash': prev}

    @locked
    def audit_log(self, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.db.execute('SELECT * FROM audit ORDER BY seq DESC LIMIT ?', (limit,)).fetchall()
        return [{**dict(r), 'payload': json.loads(r['payload'])} for r in rows]

    @locked
    def verify_chain(self) -> dict[str, Any]:
        prev = GENESIS
        n = 0
        for r in self.db.execute('SELECT * FROM audit ORDER BY seq'):
            expected = sha256('|'.join([prev, r['at'], r['actor'], r['action'], r['entity'], r['payload']]))
            if r['prev_hash'] != prev or r['hash'] != expected:
                return {'ok': False, 'broken_at': r['seq'], 'checked': n}
            prev = r['hash']
            n += 1
        return {'ok': True, 'checked': n, 'head': prev}

    # ---------- plano de contingência (barragens com sinais de abandono) ----------
    STEP_STATUS = {'pendente', 'em_andamento', 'feito', 'nao_aplicavel'}

    @locked
    def plan_progress(self, dam_id: str) -> dict[str, dict[str, Any]]:
        rows = self.db.execute('SELECT * FROM contingency_steps WHERE dam_id=?', (dam_id,)).fetchall()
        return {r['step_id']: dict(r) for r in rows}

    def set_plan_step(self, dam_id: str, step_id: str, status: str, actor: str, note: str = '') -> dict[str, Any]:
        if status not in self.STEP_STATUS:
            raise WorkflowError('Status de etapa inválido.')
        if status == 'feito' and not (note or '').strip():
            raise WorkflowError('Para marcar como feito, registre a evidência ou observação.')
        with self.lock:
            at = now()
            self.db.execute('INSERT INTO contingency_steps(dam_id,step_id,status,note,actor,at) VALUES(?,?,?,?,?,?) '
                            'ON CONFLICT(dam_id,step_id) DO UPDATE SET status=excluded.status, note=excluded.note, actor=excluded.actor, at=excluded.at',
                            (dam_id, step_id, status, note, actor, at))
            self.db.commit()
        self.audit(actor, 'contingency.step', dam_id, {'step': step_id, 'status': status, 'note': note})
        return {'dam_id': dam_id, 'step_id': step_id, 'status': status, 'at': at}

    @locked
    def plans_started(self) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT dam_id, COUNT(*) n, SUM(status='feito') done, MAX(at) last FROM contingency_steps GROUP BY dam_id ORDER BY last DESC").fetchall()
        return [dict(r) for r in rows]

    # ---------- rascunhos (representação/ofício): só humano aprova ----------
    def save_draft(self, dam_id: str, kind: str, body: str, actor: str) -> dict[str, Any]:
        with self.lock:
            at = now()
            cur = self.db.execute('INSERT INTO drafts(dam_id,kind,body,sha256,state,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                                  (dam_id, kind, body, sha256(body), 'RASCUNHO', actor, at))
            self.db.commit()
            did = cur.lastrowid
        self.audit(actor, 'draft.create', dam_id, {'draft_id': did, 'kind': kind, 'sha256': sha256(body)})
        return self.draft(did)

    @locked
    def draft(self, did: int) -> dict[str, Any] | None:
        r = self.db.execute('SELECT * FROM drafts WHERE id=?', (did,)).fetchone()
        return dict(r) if r else None

    @locked
    def drafts_for(self, dam_id: str | None = None) -> list[dict[str, Any]]:
        q, a = ('SELECT * FROM drafts WHERE dam_id=? ORDER BY id DESC', (dam_id,)) if dam_id else ('SELECT * FROM drafts ORDER BY id DESC LIMIT 100', ())
        return [dict(r) for r in self.db.execute(q, a).fetchall()]

    def decide_draft(self, did: int, decision: str, actor: str, reason: str) -> dict[str, Any]:
        d = self.draft(did)
        if not d:
            raise WorkflowError('Rascunho não encontrado.')
        if d['state'] != 'RASCUNHO':
            raise WorkflowError('Rascunho já decidido.')
        if decision not in ('APROVADO_PARA_ENVIO', 'DESCARTADO'):
            raise WorkflowError('Decisão inválida.')
        if not (reason or '').strip():
            raise WorkflowError('Justificativa obrigatória.')
        if d['created_by'] == actor and decision == 'APROVADO_PARA_ENVIO':
            raise WorkflowError('Quem gerou o rascunho não pode aprová-lo (quatro olhos).')
        with self.lock:
            self.db.execute('UPDATE drafts SET state=?, decided_by=?, decided_at=?, reason=? WHERE id=?', (decision, actor, now(), reason, did))
            self.db.commit()
        self.audit(actor, 'draft.decide', d['dam_id'], {'draft_id': did, 'decision': decision, 'reason': reason})
        return self.draft(did)

    # ---------- revisão humana ----------
    def seed_reviews(self, findings: list[dict[str, Any]]) -> int:
        """Cria rascunhos para achados acionáveis que ainda não têm revisão."""
        created = 0
        with self.lock:
            for f in findings:
                if f['state'] not in ('REVIEW', 'INSUFFICIENT', 'FUTURE_REVIEW', 'MONITOR'):
                    continue
                rid = f"{f['scenario']}:{f['asset_id']}"
                if self.db.execute('SELECT 1 FROM reviews WHERE id=?', (rid,)).fetchone():
                    continue
                at = now()
                self.db.execute('INSERT INTO reviews(id,asset_id,scenario,finding_state,headline,state,assignee,created_at,updated_at,source_ids,provisions,origin) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                                (rid, f['asset_id'], f['scenario'], f['state'], f['headline'], 'DRAFT', None, at, at,
                                 json.dumps(f['source_ids']), json.dumps(f.get('provisions', [])), f.get('origin', 'CENARIO_HIPOTETICO')))
                self.db.commit()
                self.audit('sistema:triagem', 'review.created', rid, {'finding_state': f['state'], 'rule_id': f.get('rule_id'), 'state': 'DRAFT'})
                created += 1
        return created

    def open_review(self, f: dict[str, Any], actor: str) -> dict[str, Any]:
        """Abre revisão sob demanda (ex.: barragem oficial do SIGBM). Idempotente."""
        rid = f"{f['scenario']}:{f['asset_id']}"
        if not self.db.execute('SELECT 1 FROM reviews WHERE id=?', (rid,)).fetchone():
            if f['state'] not in ('REVIEW', 'INSUFFICIENT', 'FUTURE_REVIEW', 'MONITOR'):
                raise WorkflowError('Achado sem vínculo/escopo: não há revisão a abrir.')
            self.seed_reviews([f])
            self.audit(f'humano:{actor}', 'review.opened', rid, {'origin': f.get('origin'), 'snapshot_id': f.get('snapshot_id')})
        return self.review(rid)

    def assign(self, rid: str, function: str, actor: str) -> dict[str, Any]:
        function = (function or '').strip().lower()
        if function not in {'juridico', 'compliance', 'engenharia', 'operacao', 'financas', 'regulatorio', 'protecao_radiologica', 'meio_ambiente'}:
            raise WorkflowError('Função inválida.')
        with self.lock:
            if not self.db.execute('SELECT 1 FROM reviews WHERE id=?', (rid,)).fetchone():
                raise WorkflowError('Revisão não encontrada.')
            self.db.execute('UPDATE reviews SET assigned_function=?, updated_at=? WHERE id=?', (function, now(), rid))
            self.db.commit()
            self.audit(f'humano:{actor}', 'review.assigned', rid, {'function': function})
        return self.review(rid)

    def save_finance(self, rid: str | None, payload: dict, result: dict, actor: str) -> dict[str, Any]:
        with self.lock:
            cur = self.db.execute('INSERT INTO financial_scenarios(review_id,payload,result,estimator_version,actor,at) VALUES(?,?,?,?,?,?)',
                                  (rid, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False), result['estimator_version'], actor, now()))
            self.db.commit()
            self.audit(f'humano:{actor}', 'finance.scenario.saved', rid or 'sem-revisao', {'id': cur.lastrowid, 'estimator_version': result['estimator_version']})
        return {'id': cur.lastrowid}

    @locked
    def finance(self, rid: str | None = None) -> list[dict[str, Any]]:
        q = 'SELECT * FROM financial_scenarios' + (' WHERE review_id=?' if rid else '') + ' ORDER BY id DESC'
        return [{**dict(r), 'payload': json.loads(r['payload']), 'result': json.loads(r['result'])} for r in self.db.execute(q, (rid,) if rid else ())]

    def link_entity(self, org_id: str, group_label: str, decision: str, reason: str, actor: str) -> dict[str, Any]:
        if decision not in ('CONFIRMADO', 'REJEITADO') or not reason.strip():
            raise WorkflowError('Decisão de vínculo exige CONFIRMADO/REJEITADO e motivo.')
        with self.lock:
            cur = self.db.execute('INSERT INTO entity_links(org_id,group_label,decision,reason,actor,at) VALUES(?,?,?,?,?,?)',
                                  (org_id, group_label[:120], decision, reason[:500], actor, now()))
            self.db.commit()
            self.audit(f'humano:{actor}', 'entity.link.decided', org_id, {'group': group_label, 'decision': decision})
        return {'id': cur.lastrowid}

    @locked
    def entity_links(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute('SELECT * FROM entity_links ORDER BY id DESC')]

    @locked
    def reviews(self) -> list[dict[str, Any]]:
        rows = self.db.execute('SELECT * FROM reviews ORDER BY id').fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d['source_ids'] = json.loads(d['source_ids'])
            d['provisions'] = json.loads(d['provisions'])
            d['transitions'] = [dict(t) for t in self.db.execute('SELECT * FROM transitions WHERE review_id=? ORDER BY id', (r['id'],))]
            d['evidence'] = [dict(e) for e in self.db.execute('SELECT * FROM evidence WHERE review_id=? ORDER BY id', (r['id'],))]
            out.append(d)
        return out

    @locked
    def review(self, rid: str) -> dict[str, Any] | None:
        return next((r for r in self.reviews() if r['id'] == rid), None)

    def transition(self, rid: str, to_state: str, actor: str, role: str, reason: str, source_version: str) -> dict[str, Any]:
        actor, role, reason, source_version = (actor or '').strip(), (role or '').strip().lower(), (reason or '').strip(), (source_version or '').strip()
        with self.lock:
            row = self.db.execute('SELECT * FROM reviews WHERE id=?', (rid,)).fetchone()
            if row is None:
                raise WorkflowError('Revisão não encontrada.')
            if not actor or not reason or not source_version:
                raise WorkflowError('Toda transição exige quem, motivo e versão da fonte.')
            if role not in ROLES:
                raise WorkflowError('Papel inválido.')
            current = row['state']
            if to_state not in TRANSITIONS.get(current, set()):
                raise WorkflowError(f'Transição {current} → {to_state} não permitida.')
            if to_state in ('CONFIRMED', 'REJECTED') and role not in DECISION_ROLES:
                raise WorkflowError('Somente jurídico, compliance ou especialista podem confirmar ou rejeitar.')
            if to_state == 'CLOSED' and not self.db.execute('SELECT 1 FROM evidence WHERE review_id=?', (rid,)).fetchone():
                raise WorkflowError('Encerramento exige ao menos uma evidência registrada.')
            at = now()
            self.db.execute('INSERT INTO transitions(review_id,from_state,to_state,actor,role,reason,source_version,at) VALUES(?,?,?,?,?,?,?,?)',
                            (rid, current, to_state, actor, role, reason, source_version, at))
            self.db.execute('UPDATE reviews SET state=?, assignee=?, updated_at=? WHERE id=?', (to_state, actor, at, rid))
            self.db.commit()
            self.audit(f'humano:{actor}', 'review.transition', rid,
                       {'from': current, 'to': to_state, 'role': role, 'reason': reason, 'source_version': source_version})
        return self.review(rid)

    def add_evidence(self, rid: str, item: str, description: str, actor: str) -> dict[str, Any]:
        item, description, actor = (item or '').strip(), (description or '').strip(), (actor or '').strip()
        if not item or not actor:
            raise WorkflowError('Evidência exige item e responsável.')
        with self.lock:
            if not self.db.execute('SELECT 1 FROM reviews WHERE id=?', (rid,)).fetchone():
                raise WorkflowError('Revisão não encontrada.')
            digest = sha256(f'{rid}|{item}|{description}')
            at = now()
            self.db.execute('INSERT INTO evidence(review_id,item,description,sha256,actor,at) VALUES(?,?,?,?,?,?)',
                            (rid, item, description, digest, actor, at))
            self.db.commit()
            self.audit(f'humano:{actor}', 'evidence.attached', rid, {'item': item, 'sha256': digest})
        return self.review(rid)

    # ---------- ingestão ----------
    def save_ingestion(self, rec: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            cur = self.db.execute('INSERT INTO ingestions(title,issuer,url,final_url,sha256,status,checks,collected_at) VALUES(?,?,?,?,?,?,?,?)',
                                  (rec['title'], rec['issuer'], rec['url'], rec['final_url'], rec['sha256'], rec['status'], json.dumps(rec['checks'], ensure_ascii=False), rec['collected_at']))
            self.db.commit()
            self.audit('sistema:ingestao', 'source.ingested', f"ING-{cur.lastrowid}", {'status': rec['status'], 'sha256': rec['sha256'], 'url': rec['url']})
        return {**rec, 'id': cur.lastrowid}

    @locked
    def ingestions(self) -> list[dict[str, Any]]:
        return [{**dict(r), 'checks': json.loads(r['checks'])} for r in self.db.execute('SELECT * FROM ingestions ORDER BY id DESC')]

    # ---------- caixa de saída (integrações) ----------
    def dispatch(self, connector: str, rid: str, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        with self.lock:
            row = self.db.execute('SELECT state FROM reviews WHERE id=?', (rid,)).fetchone()
            if row is None:
                raise WorkflowError('Revisão não encontrada.')
            if row['state'] not in ('CONFIRMED', 'ACTION_TRACKING', 'CLOSED'):
                raise WorkflowError('Envio bloqueado: o achado precisa estar CONFIRMADO por humano.')
            if not (actor or '').strip():
                raise WorkflowError('Envio exige responsável.')
            at = now()
            body = json.dumps(payload, ensure_ascii=False)
            cur = self.db.execute('INSERT INTO outbox(connector,review_id,payload,status,actor,at) VALUES(?,?,?,?,?,?)',
                                  (connector, rid, body, 'SIMULADO_ENFILEIRADO', actor.strip(), at))
            self.db.commit()
            self.audit(f'humano:{actor.strip()}', 'integration.dispatched', rid, {'connector': connector, 'outbox_id': cur.lastrowid, 'payload_sha256': sha256(body)})
        return {'id': cur.lastrowid, 'connector': connector, 'review_id': rid, 'status': 'SIMULADO_ENFILEIRADO', 'at': at, 'payload': payload}

    @locked
    def outbox(self) -> list[dict[str, Any]]:
        return [{**dict(r), 'payload': json.loads(r['payload'])} for r in self.db.execute('SELECT * FROM outbox ORDER BY id DESC')]

    def reset(self) -> None:
        with self.lock:
            for t in ('reviews', 'transitions', 'evidence', 'ingestions', 'outbox', 'financial_scenarios', 'entity_links', 'audit',
                      'contingency_steps', 'drafts'):
                self.db.execute(f'DELETE FROM {t}')
            existing = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for t in ('watchlist', 'notification_reads', 'model_feedback', 'model_versions', 'agent_runs', 'agent_actions', 'compliance_alerts', 'compliance_events', 'denuncias', 'tenant_docs', 'tenant_access'):  # estado de demonstração
                if t in existing:
                    self.db.execute(f'DELETE FROM {t}')
            self.db.execute("DELETE FROM sqlite_sequence")
            self.db.commit()
