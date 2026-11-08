"""Documentos por cliente no cofre (Amazon S3 privado + KMS, ou cópia local no mesmo formato).

- Cada organização vira um Customer ID opaco: HMAC-SHA256(segredo local, organização). O nome do cliente nunca entra
  no caminho do arquivo: clientes/<customer_id>/documentos/<data>/<nome>.<hash>.
- O cadastro (quem é o cliente) fica no banco da aplicação, separado dos documentos.
- Acesso só por sessão autenticada da mesma organização; gestor/compliance pode revogar o acesso de um usuário.
- No S3, a política de exemplo em infra/aws/template.yaml limita cada papel ao prefixo do seu Customer ID.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path

from .store import WorkflowError, now

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
MIME_OK = {'application/pdf': 'pdf', 'image/png': 'png', 'image/jpeg': 'jpg', 'text/plain': 'txt'}
SCHEMA = """
CREATE TABLE IF NOT EXISTS tenant_docs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT, kind TEXT, name TEXT, mime TEXT, bytes INTEGER, sha256 TEXT,
  vault_key TEXT, vault_mode TEXT, uploaded_by TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS tenant_access(
  customer_id TEXT, user_id TEXT, revoked_at TEXT, revoked_by TEXT, PRIMARY KEY(customer_id, user_id));
"""


def _secret(var_dir: Path) -> bytes:
    env = os.environ.get('TORRE_TENANT_SECRET')
    if env:
        return env.encode()
    p = var_dir / 'tenant_secret'
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(32), encoding='utf8')
    return p.read_text(encoding='utf8').strip().encode()


class TenantDocs:
    def __init__(self, store, vault, var_dir: Path = ROOT / 'var'):
        self.store, self.vault, self.key = store, vault, _secret(var_dir)
        with store.lock:
            store.db.executescript(SCHEMA)
            store.db.commit()

    def customer_id(self, org_key: str) -> str:
        return 'C-' + hmac.new(self.key, (org_key or '').encode('utf8'), hashlib.sha256).hexdigest()[:16]

    def org_key(self, user: dict) -> str:
        # organização da conta empresa; cidadão é o próprio cliente
        return (user.get('cnpj') or user.get('org_name') or '') if user.get('kind') == 'empresa' else f"cidadao:{user.get('id')}"

    def allowed(self, cid: str, user: dict) -> bool:
        with self.store.lock:
            r = self.store.db.execute('SELECT revoked_at FROM tenant_access WHERE customer_id=? AND user_id=?', (cid, str(user.get('id')))).fetchone()
        return not (r and r['revoked_at'])

    def upload(self, user: dict, name: str, mime: str, data_b64: str, kind: str = 'documento') -> dict:
        if mime not in MIME_OK:
            raise WorkflowError('Tipo de arquivo não aceito (PDF, PNG, JPG ou TXT).')
        try:
            body = base64.b64decode(data_b64, validate=True)
        except Exception:
            raise WorkflowError('Arquivo inválido.')
        if not body or len(body) > MAX_BYTES:
            raise WorkflowError('Arquivo vazio ou maior que 5 MB.')
        cid = self.customer_id(self.org_key(user))
        if not self.allowed(cid, user):
            raise WorkflowError('Acesso deste usuário aos documentos da organização foi revogado.')
        safe = re.sub(r'[^A-Za-z0-9._-]+', '_', (name or 'arquivo'))[:60]
        sha = hashlib.sha256(body).hexdigest()
        with self.store.lock:  # custo: documento idêntico (mesmo hash) já guardado para este cliente não é regravado nem reprocessado
            dup = self.store.db.execute('SELECT id,name,sha256,bytes,vault_mode FROM tenant_docs WHERE customer_id=? AND sha256=? AND kind=?', (cid, sha, kind)).fetchone()
        if dup:
            return {'id': dup['id'], 'customer_id': cid, 'name': dup['name'], 'sha256': sha, 'bytes': dup['bytes'], 'mode': dup['vault_mode'], 'duplicado': True}
        rec = self.vault.put(f'clientes/{cid}/{re.sub(r"[^a-z_]", "", kind) or "documento"}', safe, body, {'mime': mime})
        with self.store.lock:
            cur = self.store.db.execute('INSERT INTO tenant_docs(customer_id,kind,name,mime,bytes,sha256,vault_key,vault_mode,uploaded_by,at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                        (cid, kind, safe, mime, len(body), rec['sha256'], rec['key'], rec['mode'], str(user.get('id')), now()))
            self.store.db.commit()
            did = cur.lastrowid
        self.store.audit(f"usuario:{user.get('id')}", 'docs.upload', cid, {'doc_id': did, 'sha256': rec['sha256'], 'mode': rec['mode']})
        return {'id': did, 'customer_id': cid, 'name': safe, 'sha256': rec['sha256'], 'bytes': len(body), 'mode': rec['mode']}

    def list(self, user: dict) -> dict:
        cid = self.customer_id(self.org_key(user))
        with self.store.lock:
            docs = [dict(r) for r in self.store.db.execute('SELECT id,kind,name,mime,bytes,sha256,vault_mode,uploaded_by,at FROM tenant_docs WHERE customer_id=? ORDER BY id DESC', (cid,))]
            acc = [dict(r) for r in self.store.db.execute('SELECT user_id,revoked_at,revoked_by FROM tenant_access WHERE customer_id=?', (cid,))]
        return {'customer_id': cid, 'docs': docs, 'access': acc, 'allowed': self.allowed(cid, user), 'mode': self.vault.mode}

    def read(self, user: dict, did: int) -> tuple[dict, bytes]:
        cid = self.customer_id(self.org_key(user))
        if not self.allowed(cid, user):
            raise WorkflowError('Acesso revogado.')
        with self.store.lock:
            r = self.store.db.execute('SELECT * FROM tenant_docs WHERE id=? AND customer_id=?', (did, cid)).fetchone()
        if not r:
            raise WorkflowError('Documento não encontrado para esta organização.')
        body = self.vault.get(r['vault_key'])
        if hashlib.sha256(body).hexdigest() != r['sha256']:
            raise WorkflowError('Integridade do documento não confere (hash diferente).')
        return dict(r), body

    def set_access(self, admin: dict, user_id: str, revoke: bool) -> dict:
        cid = self.customer_id(self.org_key(admin))
        with self.store.lock:
            self.store.db.execute('INSERT INTO tenant_access(customer_id,user_id,revoked_at,revoked_by) VALUES(?,?,?,?) ON CONFLICT(customer_id,user_id) '
                                  'DO UPDATE SET revoked_at=excluded.revoked_at, revoked_by=excluded.revoked_by',
                                  (cid, str(user_id), now() if revoke else None, str(admin.get('id'))))
            self.store.db.commit()
        self.store.audit(f"usuario:{admin.get('id')}", 'docs.revoke' if revoke else 'docs.restore', cid, {'user_id': str(user_id)})
        return {'customer_id': cid, 'user_id': str(user_id), 'revoked': revoke}
