"""Contas, sessões, carteira/acompanhamento e notificações.

- Dois tipos de conta: 'cidadao' (público leigo) e 'empresa' (organização).
- Senha: PBKDF2-HMAC-SHA256, 200 mil iterações, sal aleatório. Nunca armazenada em texto.
- Sessão: token aleatório entregue em cookie HttpOnly; no banco fica só o SHA-256 do token.
- Papel da conta empresa vem da função escolhida no cadastro (DEMONSTRAÇÃO: em produção, quem
  atribui papéis é o administrador da organização).
"""
from __future__ import annotations

import hashlib
import json
import hmac
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .store import Store, WorkflowError, now, locked

ITER = 200_000
SESSION_HOURS = 8
FUNCTION_TO_ROLE = {'juridico': 'juridico', 'compliance': 'compliance', 'engenharia': 'especialista', 'operacao': 'operacao',
                    'financas': 'gestor', 'auditoria': 'auditor', 'meio_ambiente': 'especialista', 'regulatorio': 'compliance', 'radioprotecao': 'especialista', 'seguranca_trabalho': 'especialista'}
ADMIN_ROLES = ('gestor', 'compliance', 'juridico')   # quem administra a equipe da empresa
FUNCOES = {'juridico': 'Jurídico', 'compliance': 'Compliance', 'engenharia': 'Engenharia', 'operacao': 'Operação', 'financas': 'Gestão / finanças',
           'auditoria': 'Auditoria', 'meio_ambiente': 'Meio ambiente', 'radioprotecao': 'Proteção radiológica', 'seguranca_trabalho': 'Segurança do trabalho (SESMT)', 'regulatorio': 'Curadoria regulatória'}
# Acesso por módulo (regra acessos-v1): a gestão marca o que cada pessoa vê. NULL = acesso padrão do papel (contas antigas e de demonstração).
MODULOS = {
    'visao': 'Visão Executiva', 'operacao': 'Operação & Ativos', 'conformidade': 'Alertas e mudanças normativas',
    'obrigacoes': 'Norma → obrigação', 'denuncias': 'Denúncias recebidas', 'documentos': 'Documentos da empresa',
    'ia': 'Central de IA', 'relatorio': 'Relatório da empresa', 'sistemas': 'Impacto em sistemas',
}
MODULOS_PADRAO = {
    'juridico': list(MODULOS), 'compliance': list(MODULOS), 'regulatorio': list(MODULOS), 'financas': ['visao', 'conformidade', 'relatorio', 'ia'],
    'auditoria': ['visao', 'conformidade', 'denuncias', 'documentos', 'relatorio'], 'engenharia': ['visao', 'operacao', 'conformidade', 'documentos', 'ia', 'sistemas'],
    'operacao': ['visao', 'operacao', 'ia'], 'meio_ambiente': ['visao', 'operacao', 'conformidade', 'documentos', 'ia'],
    'seguranca_trabalho': ['visao', 'operacao', 'conformidade', 'documentos', 'ia'], 'radioprotecao': ['visao', 'operacao', 'conformidade', 'documentos', 'ia'],
}


import re as _re
_SETOR_PAL = [('nuclear', r'CNEN|ANSN|nuclear|radiol|radioativ|ur[aâ]nio'), ('energia', r'ANEEL|usina|ONS|hidrel|subesta|outorga|energia'),
              ('saneamento', r'saneamento|abastecimento|[aá]gua tratada|turbidez|potab'), ('mineracao', r'ANM|SIGBM|SIGMINE|minera|barragens? de rejeito|radar de abandono|lavra')]


def setor_da_notificacao(n: dict) -> str | None:
    """Setor de uma notificação: pela empresa do link ou por palavras do título; None = vale para todos os setores."""
    link = n.get('link') or ''
    for cid, s in (('demo-mineracao', 'mineracao'), ('demo-energia', 'energia'), ('demo-saneamento', 'saneamento'), ('demo-nuclear', 'nuclear')):
        if f'empresa={cid}' in link:
            return s
    if n.get('kind') == 'agente' or link == '#/radar':
        return 'mineracao'   # o agente e o radar de abandono trabalham sobre barragens de mineração
    texto = f"{n.get('title', '')} {n.get('body', '')}"
    for s, pad in _SETOR_PAL:
        if _re.search(pad, texto, _re.I):
            return s
    return None


def modulos_validos(mods) -> list[str]:
    return [m for m in (mods or []) if m in MODULOS]


INVITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS invites(
  id INTEGER PRIMARY KEY AUTOINCREMENT, token_hash TEXT UNIQUE, cnpj TEXT, org_name TEXT, email TEXT, name TEXT, function TEXT, role TEXT,
  invited_by INTEGER, created_at TEXT, expires_at TEXT, used_at TEXT, revoked_at TEXT);
"""
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
  pw_salt TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL, function TEXT, org_name TEXT, cnpj TEXT,
  uf TEXT, municipio TEXT, created_at TEXT, consent_at TEXT, is_demo INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER, created_at TEXT, expires_at TEXT);
CREATE TABLE IF NOT EXISTS watchlist(user_id INTEGER, asset_id TEXT, created_at TEXT, PRIMARY KEY(user_id, asset_id));
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, audience TEXT, kind TEXT, title TEXT, body TEXT, link TEXT, source_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS notification_reads(user_id INTEGER, notification_id INTEGER, PRIMARY KEY(user_id, notification_id));
CREATE TABLE IF NOT EXISTS monitor_checks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, target_id TEXT, url TEXT, checked_at TEXT, status TEXT, http_status INTEGER,
  sha256 TEXT, changed INTEGER, detail TEXT);
"""
_failed: dict[str, list[float]] = {}


def hash_pw(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    return salt, hashlib.pbkdf2_hmac('sha256', password.encode('utf8'), bytes.fromhex(salt), ITER).hex()


def valid_cnpj(cnpj: str) -> bool:
    d = re.sub(r'\D', '', cnpj or '')
    if len(d) != 14 or d == d[0] * 14:
        return False
    def dv(base, weights):
        s = sum(int(a) * b for a, b in zip(base, weights)) % 11
        return '0' if s < 2 else str(11 - s)
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(d[:12], w1)
    d2 = dv(d[:12] + d1, [6] + w1)
    return d[12:] == d1 + d2


class Accounts:
    def __init__(self, store: Store):
        self.store = store
        self.lock = store.lock
        self.db = store.db
        with self.lock:
            self.db.executescript(SCHEMA)
            cols = {r[1] for r in self.db.execute('PRAGMA table_info(users)')}
            self.db.executescript(INVITE_SCHEMA)
            for c in ('phone', 'avatar', 'cargo', 'status', 'empresa_id', 'modulos'):   # perfil; status ativo/suspenso; frente (empresa) e módulos liberados
                if c not in cols:
                    self.db.execute(f'ALTER TABLE users ADD COLUMN {c} TEXT')
            icols = {r[1] for r in self.db.execute('PRAGMA table_info(invites)')}
            for c in ('empresa_id', 'modulos', 'cargo'):
                if c not in icols:
                    self.db.execute(f'ALTER TABLE invites ADD COLUMN {c} TEXT')
            self.db.commit()

    # ---------------- cadastro / login ----------------
    @locked
    def register(self, data: dict[str, Any], demo: bool = False) -> dict[str, Any]:
        kind = str(data.get('kind', '')).strip()
        name = str(data.get('name', '')).strip()[:120]
        email = str(data.get('email', '')).strip().lower()[:160]
        pw = str(data.get('password', ''))
        if kind not in ('cidadao', 'empresa'):
            raise WorkflowError('Escolha o tipo de conta: cidadão ou empresa.')
        if len(name) < 2:
            raise WorkflowError('Informe seu nome.')
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            raise WorkflowError('E-mail inválido.')
        if len(pw) < 8 or not re.search(r'\d', pw) or not re.search(r'[A-Za-zÀ-ÿ]', pw):
            raise WorkflowError('A senha precisa ter 8+ caracteres, com letras e números.')
        if not data.get('consent'):
            raise WorkflowError('É preciso aceitar o uso dos dados conforme a LGPD para criar a conta.')
        role, function, org, cnpj = 'cidadao', None, None, None
        if kind == 'empresa':
            function = str(data.get('function_signup') or data.get('function', '')).strip()
            if function not in FUNCTION_TO_ROLE:
                raise WorkflowError('Escolha sua função na organização.')
            org = str(data.get('org_name', '')).strip()[:160]
            if len(org) < 2:
                raise WorkflowError('Informe a razão social.')
            cnpj = re.sub(r'\D', '', str(data.get('cnpj', '')))
            if not valid_cnpj(cnpj):
                raise WorkflowError('CNPJ inválido (dígitos verificadores não conferem).')
            role = data.get('role') if demo and data.get('role') else FUNCTION_TO_ROLE[function]
            if demo and data.get('role') == 'curador':
                function = 'regulatorio'
        if self.db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
            raise WorkflowError('Já existe uma conta com este e-mail.')
        salt, h = hash_pw(pw)
        at = now()
        cur = self.db.execute('INSERT INTO users(kind,name,email,pw_salt,pw_hash,role,function,org_name,cnpj,uf,municipio,created_at,consent_at,is_demo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                              (kind, name, email, salt, h, role, function, org, cnpj, (data.get('uf') or '')[:2].upper() or None,
                               str(data.get('municipio') or '')[:80] or None, at, at, 1 if demo else 0))
        self.db.commit()
        self.store.audit('sistema:contas', 'account.created', f'user:{cur.lastrowid}', {'kind': kind, 'role': role, 'demo': demo})
        return self.user(cur.lastrowid)

    def login(self, email: str, password: str, kind: str | None = None) -> tuple[str, dict[str, Any]]:
        email = (email or '').strip().lower()
        hits = [t for t in _failed.get(email, []) if time.time() - t < 600]
        if len(hits) >= 5:
            raise WorkflowError('Muitas tentativas. Aguarde 10 minutos.')
        with self.lock:
            row = self.db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        ok = bool(row) and hmac.compare_digest(hash_pw(password or '', row['pw_salt'])[1], row['pw_hash'])
        if not ok:
            _failed.setdefault(email, []).append(time.time())
            raise WorkflowError('E-mail ou senha incorretos.')
        if row['status'] == 'suspenso':
            raise WorkflowError('Acesso suspenso pela gestão da sua empresa.')
        if kind and row['kind'] != kind:
            raise WorkflowError('Esta conta é de ' + ('empresa' if row['kind'] == 'empresa' else 'cidadão') + '. Use a aba correspondente.')
        _failed.pop(email, None)
        token = secrets.token_urlsafe(32)
        exp = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).replace(microsecond=0).isoformat()
        with self.lock:
            self.db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], now(), exp))
            self.db.commit()
        self.store.audit(f"usuario:{row['id']}", 'session.login', f"user:{row['id']}", {'kind': row['kind']})
        return token, self.user(row['id'])

    @locked
    def session_user(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        r = self.db.execute('SELECT * FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not r or r['expires_at'] < now():
            return None
        return self.user(r['user_id'])

    @locked
    def logout(self, token: str) -> None:
        self.db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256((token or '').encode()).hexdigest(),))
        self.db.commit()

    @locked
    def user(self, uid: int) -> dict[str, Any] | None:
        r = self.db.execute('SELECT id,kind,name,email,role,function,org_name,cnpj,uf,municipio,created_at,is_demo,phone,avatar,cargo,status,empresa_id,modulos FROM users WHERE id=?', (uid,)).fetchone()
        if r and r['status'] == 'suspenso':
            return None   # suspenso: sessão deixa de valer
        if not r:
            return None
        d = dict(r)
        d['modulos'] = json.loads(d['modulos']) if d.get('modulos') else None
        return d

    # ---------------- equipe e permissões ----------------
    @staticmethod
    def is_admin(u: dict | None) -> bool:
        return bool(u and u.get('kind') == 'empresa' and u.get('role') in ADMIN_ROLES)

    @locked
    def team(self, admin: dict) -> dict[str, Any]:
        root = str(admin.get('cnpj') or '')[:8]
        def _m(d):
            d = dict(d)
            d['modulos'] = json.loads(d['modulos']) if d.get('modulos') else None
            return d
        mem = [_m(r) for r in self.db.execute("SELECT id,name,email,function,role,cargo,status,created_at,is_demo,empresa_id,modulos FROM users WHERE kind='empresa' AND substr(cnpj,1,8)=? ORDER BY name", (root,))]
        inv = [_m(r) for r in self.db.execute('SELECT id,email,name,function,cargo,empresa_id,modulos,created_at,expires_at FROM invites WHERE substr(cnpj,1,8)=? AND used_at IS NULL AND revoked_at IS NULL AND expires_at > ? ORDER BY id DESC', (root, now()))]
        return {'org': admin.get('org_name'), 'cnpj_raiz': root, 'membros': mem, 'convites': inv}

    @locked
    def invite(self, admin: dict, name: str, email: str, function: str, cargo: str = '', empresa_id: str | None = None, modulos: list | None = None) -> dict[str, Any]:
        if not self.is_admin(admin):
            raise WorkflowError('Só gestão, compliance ou jurídico da empresa podem convidar.')
        email = (email or '').strip().lower()[:160]
        name = ' '.join(str(name or '').split())[:120]
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            raise WorkflowError('E-mail inválido.')
        if not name:   # só o e-mail: o nome provisório sai do próprio e-mail e a pessoa ajusta no perfil
            name = ' '.join(p.capitalize() for p in re.split(r'[._-]+', email.split('@')[0]) if p)[:120] or email
        function = function or 'operacao'
        if len(name) < 2:
            raise WorkflowError('Informe o nome da pessoa.')
        if function not in FUNCTION_TO_ROLE:
            raise WorkflowError('Escolha a função da pessoa.')
        if self.db.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
            raise WorkflowError('Já existe uma conta com este e-mail.')
        token = secrets.token_urlsafe(24)
        exp = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat()
        if self.db.execute('SELECT 1 FROM invites WHERE email=? AND used_at IS NULL AND revoked_at IS NULL AND expires_at > ?', (email, now())).fetchone():
            raise WorkflowError('Já existe um convite pendente para este e-mail.')
        mods = modulos_validos(modulos) if modulos is not None else MODULOS_PADRAO.get(function, ['visao'])
        cur = self.db.execute('INSERT INTO invites(token_hash,cnpj,org_name,email,name,function,role,invited_by,created_at,expires_at,cargo,empresa_id,modulos) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                              (hashlib.sha256(token.encode()).hexdigest(), admin.get('cnpj'), admin.get('org_name'), email, name, function, FUNCTION_TO_ROLE[function], admin.get('id'), now(), exp,
                               str(cargo or '')[:80] or None, empresa_id, json.dumps(mods)))
        self.db.commit()
        self.store.audit(f"usuario:{admin.get('id')}", 'equipe.convite', f"invite:{cur.lastrowid}", {'email': email, 'funcao': function, 'frente': empresa_id, 'modulos': mods})
        return {'id': cur.lastrowid, 'token': token, 'email': email, 'name': name, 'function': function, 'expires_at': exp, 'modulos': mods, 'empresa_id': empresa_id}

    @locked
    def invite_info(self, token: str) -> dict[str, Any] | None:
        r = self.db.execute('SELECT * FROM invites WHERE token_hash=?', (hashlib.sha256((token or '').encode()).hexdigest(),)).fetchone()
        if not r or r['used_at'] or r['revoked_at'] or r['expires_at'] < now():
            return None
        return {'org_name': r['org_name'], 'email': r['email'], 'name': r['name'], 'function': r['function'], 'funcao': FUNCOES.get(r['function'], r['function'])}

    def accept_invite(self, token: str, password: str, consent: bool) -> dict[str, Any]:
        with self.lock:
            r = self.db.execute('SELECT * FROM invites WHERE token_hash=?', (hashlib.sha256((token or '').encode()).hexdigest(),)).fetchone()
        if not r or r['used_at'] or r['revoked_at'] or r['expires_at'] < now():
            raise WorkflowError('Convite inválido, usado ou vencido. Peça um novo à gestão da empresa.')
        pw = str(password or '')
        if len(pw) < 8 or not re.search(r'\d', pw) or not re.search(r'[A-Za-zÀ-ÿ]', pw):
            raise WorkflowError('A senha precisa ter 8+ caracteres, com letras e números.')
        if not consent:
            raise WorkflowError('É preciso aceitar o uso dos dados conforme a LGPD.')
        salt, h = hash_pw(pw)
        at = now()
        with self.lock:
            cur = self.db.execute('INSERT INTO users(kind,name,email,pw_salt,pw_hash,role,function,org_name,cnpj,created_at,consent_at,is_demo,status,cargo,empresa_id,modulos) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                  ('empresa', r['name'], r['email'], salt, h, r['role'], r['function'], r['org_name'], r['cnpj'], at, at, 0, 'ativo', r['cargo'], r['empresa_id'], r['modulos']))
            self.db.execute('UPDATE invites SET used_at=? WHERE id=?', (at, r['id']))
            self.db.commit()
        self.store.audit(f"usuario:{cur.lastrowid}", 'equipe.convite_aceito', f"invite:{r['id']}", {'funcao': r['function']})
        return self.user(cur.lastrowid)

    @locked
    def change_member(self, admin: dict, uid: int, function: str | None = None, status: str | None = None, motivo: str = '') -> dict[str, Any]:
        if not self.is_admin(admin):
            raise WorkflowError('Só gestão, compliance ou jurídico da empresa podem alterar a equipe.')
        if len((motivo or '').strip()) < 5:
            raise WorkflowError('Explique o motivo da alteração (fica na trilha).')
        r = self.db.execute("SELECT id,cnpj,function,role,status FROM users WHERE id=? AND kind='empresa'", (uid,)).fetchone()
        if not r or str(r['cnpj'] or '')[:8] != str(admin.get('cnpj') or '')[:8]:
            raise WorkflowError('Pessoa não pertence à sua organização.')
        if uid == admin.get('id') and status == 'suspenso':
            raise WorkflowError('Você não pode suspender a própria conta.')
        sets = {}
        if function:
            if function not in FUNCTION_TO_ROLE:
                raise WorkflowError('Função inválida.')
            sets.update(function=function, role=FUNCTION_TO_ROLE[function])
        if status:
            if status not in ('ativo', 'suspenso'):
                raise WorkflowError('Situação inválida.')
            sets['status'] = status
        if not sets:
            raise WorkflowError('Nada para alterar.')
        self.db.execute('UPDATE users SET ' + ', '.join(f'{k}=?' for k in sets) + ' WHERE id=?', (*sets.values(), uid))
        if sets.get('status') == 'suspenso':
            self.db.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
        self.db.commit()
        self.store.audit(f"usuario:{admin.get('id')}", 'equipe.alteracao', f'user:{uid}', {'antes': {'funcao': r['function'], 'status': r['status']}, 'depois': sets, 'motivo': motivo[:300]})
        return {'id': uid, **sets}

    @locked
    def set_access(self, admin: dict, alvo: str, aid: int, modulos: list) -> dict[str, Any]:
        """Marca/desmarca módulos de uma pessoa (ou de um convite pendente). Vale na hora: a próxima tela já respeita."""
        if not self.is_admin(admin):
            raise WorkflowError('Só gestão, compliance ou jurídico da empresa podem dar ou tirar acesso.')
        mods = modulos_validos(modulos)
        root = str(admin.get('cnpj') or '')[:8]
        if alvo == 'convite':
            cur = self.db.execute('UPDATE invites SET modulos=? WHERE id=? AND substr(cnpj,1,8)=? AND used_at IS NULL AND revoked_at IS NULL', (json.dumps(mods), aid, root))
        else:
            if aid == admin.get('id'):
                raise WorkflowError('Você não pode mudar o próprio acesso.')
            r = self.db.execute("SELECT is_demo FROM users WHERE id=? AND kind='empresa' AND substr(cnpj,1,8)=?", (aid, root)).fetchone()
            if not r:
                raise WorkflowError('Pessoa não pertence à sua organização.')
            if r['is_demo']:
                raise WorkflowError('Contas de demonstração compartilhadas têm acesso fixo.')
            cur = self.db.execute('UPDATE users SET modulos=? WHERE id=?', (json.dumps(mods), aid))
        self.db.commit()
        if not cur.rowcount:
            raise WorkflowError('Não encontrado.')
        self.store.audit(f"usuario:{admin.get('id')}", 'equipe.acesso', f'{alvo}:{aid}', {'modulos': mods})
        return {'id': aid, 'alvo': alvo, 'modulos': mods}

    @locked
    def revoke_invite(self, admin: dict, iid: int) -> None:
        if not self.is_admin(admin):
            raise WorkflowError('Sem permissão.')
        cur = self.db.execute('UPDATE invites SET revoked_at=? WHERE id=? AND substr(cnpj,1,8)=? AND used_at IS NULL', (now(), iid, str(admin.get('cnpj') or '')[:8]))
        self.db.commit()
        if not cur.rowcount:
            raise WorkflowError('Convite não encontrado.')
        self.store.audit(f"usuario:{admin.get('id')}", 'equipe.convite_revogado', f'invite:{iid}', {})

    @locked
    def update_profile(self, uid: int, data: dict[str, Any]) -> dict[str, Any]:
        """Perfil essencial: nome, foto, telefone, cargo e local. E-mail, organização, CNPJ e papel não mudam aqui (exigem gestor/curadoria)."""
        import base64
        import re as _re
        name = ' '.join(str(data.get('name', '')).split())[:80]
        if len(name) < 2:
            raise WorkflowError('Informe o nome (mínimo 2 caracteres).')
        phone = _re.sub(r'[^\d+() -]', '', str(data.get('phone') or ''))[:20] or None
        cargo = ' '.join(str(data.get('cargo') or '').split())[:60] or None
        uf = str(data.get('uf') or '').upper()[:2] or None
        municipio = ' '.join(str(data.get('municipio') or '').split())[:60] or None
        sets = {'name': name, 'phone': phone, 'cargo': cargo, 'uf': uf, 'municipio': municipio}
        if 'avatar' in data:
            av = data.get('avatar')
            if av in (None, ''):
                sets['avatar'] = None
            else:
                m = _re.fullmatch(r'data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)', str(av))
                if not m:
                    raise WorkflowError('Foto inválida: use JPG, PNG ou WEBP.')
                if len(base64.b64decode(m[2])) > 150_000:
                    raise WorkflowError('Foto grande demais (máximo 150 KB depois de reduzida).')
                sets['avatar'] = str(av)
        self.db.execute('UPDATE users SET ' + ', '.join(f'{k}=?' for k in sets) + ' WHERE id=?', (*sets.values(), uid))
        self.db.commit()
        return self.user(uid)

    def seed_demo(self, demo_users: list[dict[str, Any]]) -> int:
        n = 0
        for u in demo_users:
            if not u.get('email'):
                continue
            with self.lock:
                exists = self.db.execute('SELECT 1 FROM users WHERE email=?', (u['email'],)).fetchone()
            if exists:
                continue
            self.register({**u, 'consent': True}, demo=True)
            n += 1
        return n

    # ---------------- carteira / acompanhamento ----------------
    @locked
    def watch(self, uid: int, asset_id: str, add: bool = True) -> list[str]:
        if add:
            self.db.execute('INSERT OR IGNORE INTO watchlist VALUES(?,?,?)', (uid, asset_id, now()))
        else:
            self.db.execute('DELETE FROM watchlist WHERE user_id=? AND asset_id=?', (uid, asset_id))
        self.db.commit()
        return self.watchlist(uid)

    @locked
    def watchlist(self, uid: int) -> list[str]:
        return [r['asset_id'] for r in self.db.execute('SELECT asset_id FROM watchlist WHERE user_id=? ORDER BY created_at', (uid,))]

    # ---------------- notificações ----------------
    @locked
    def notify(self, audience: str, kind: str, title: str, body: str, link: str = '', source_id: str = '') -> int:
        cur = self.db.execute('INSERT INTO notifications(audience,kind,title,body,link,source_id,created_at) VALUES(?,?,?,?,?,?,?)',
                              (audience, kind, title[:200], body[:1000], link[:300], source_id[:60], now()))
        self.db.commit()
        return cur.lastrowid

    @locked
    def notifications(self, user: dict[str, Any] | None, limit: int = 30, perfil: dict | None = None) -> dict[str, Any]:
        """perfil = {'cid', 'root', 'setor'} da empresa escolhida no topo: as notificações seguem a frente (regra notificacoes-v2)."""
        aud = ['todos'] + (['empresa'] if user and user['kind'] == 'empresa' else ['cidadao'] if user else [])
        if user:  # roteamento: só a função, o papel e a organização de quem precisa receber
            aud += [f"func:{user.get('function')}", f"role:{user.get('role')}"]
            root = (perfil or {}).get('root') or (str(user['cnpj'])[:8] if user.get('cnpj') else None)
            if root:
                aud.append(f"org:{root}")
                aud.append(f"orgfunc:{root}:{user.get('function')}")
        q = 'SELECT * FROM notifications WHERE audience IN (%s) ORDER BY id DESC LIMIT ?' % ','.join('?' * len(aud))
        rows = [dict(r) for r in self.db.execute(q, (*aud, limit * 4 if perfil else limit))]
        if perfil:
            rows = [r for r in rows if setor_da_notificacao(r) in (None, perfil.get('setor')) and (('empresa=' not in (r.get('link') or '')) or f"empresa={perfil.get('cid')}" in r['link'])][:limit]
        read = set()
        if user:
            read = {r['notification_id'] for r in self.db.execute('SELECT notification_id FROM notification_reads WHERE user_id=?', (user['id'],))}
        for r in rows:
            r['read'] = r['id'] in read
        return {'items': rows, 'unread': sum(1 for r in rows if not r['read'])}

    @locked
    def mark_read(self, uid: int, ids: list[int]) -> None:
        for i in ids:
            self.db.execute('INSERT OR IGNORE INTO notification_reads VALUES(?,?)', (uid, int(i)))
        self.db.commit()

    # ---------------- monitor ----------------
    @locked
    def save_check(self, target_id: str, url: str, status: str, http_status: int | None, sha: str | None, changed: bool, detail: str) -> None:
        self.db.execute('INSERT INTO monitor_checks(target_id,url,checked_at,status,http_status,sha256,changed,detail) VALUES(?,?,?,?,?,?,?,?)',
                        (target_id, url, now(), status, http_status, sha, 1 if changed else 0, detail[:400]))
        self.db.commit()

    @locked
    def last_ok_hash(self, target_id: str) -> str | None:
        r = self.db.execute("SELECT sha256 FROM monitor_checks WHERE target_id=? AND status='OK' ORDER BY id DESC LIMIT 1", (target_id,)).fetchone()
        return r['sha256'] if r else None

    @locked
    def monitor_status(self) -> list[dict[str, Any]]:
        rows = self.db.execute('SELECT * FROM monitor_checks WHERE id IN (SELECT MAX(id) FROM monitor_checks GROUP BY target_id) ORDER BY target_id').fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d['changes_total'] = self.db.execute('SELECT COUNT(*) c FROM monitor_checks WHERE target_id=? AND changed=1', (r['target_id'],)).fetchone()['c']
            out.append(d)
        return out
