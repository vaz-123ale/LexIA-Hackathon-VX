"""Servidor HTTP sem dependências obrigatórias (LexIA v3).

Execute na raiz do projeto:  python -m app.server   ->  http://localhost:8765
- Funciona offline: usa o snapshot oficial SIGBM mais recente em data/snapshots/sigbm.
- Mutações exigem token de DEMONSTRAÇÃO (cabeçalho Authorization: Bearer demo-...). Não é autenticação de produção.
- Nada é enviado para sistemas externos; a única coleta online é o conector SIGBM, acionado manualmente.
"""
from __future__ import annotations

import csv
from collections import Counter
import re
import io
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'app'

from .config import load_env  # noqa: E402
ENV_LOADED = load_env() if not os.environ.get('TORRE_NO_DOTENV') else []
from .engine import analyze, AS_OF  # noqa: E402
from .temporal import snapshot, milestones  # noqa: E402
from .store import Store, WorkflowError  # noqa: E402
from .ingest import check as ingest_check  # noqa: E402
from .ai import ask, llm_status  # noqa: E402
from .project_screen import screen_project  # noqa: E402
from .workbench import Workbench, reference, changes, compare_projects, extract_conditions, dossier  # noqa: E402
from .chain import build_chain, build_graph, EVIDENCE_TEMPLATES  # noqa: E402
from .assessment import assess, explanation, analyze_official_anm  # noqa: E402
from .connectors import sigbm  # noqa: E402
from .entities import build_registry, search as entity_search  # noqa: E402
from .finance import evaluate as finance_evaluate  # noqa: E402
from .diff import scenario_diffs  # noqa: E402
from . import decision_pack  # noqa: E402
from .accounts import Accounts  # noqa: E402
from .monitor import Monitor, BLOCKED_CHANNELS  # noqa: E402
from . import abandono, radar, ai_tools, risk_model, business  # noqa: E402
from .mlops import MLOps  # noqa: E402
from .agent import Agent, claude_planner_factory, gemini_planner_factory  # noqa: E402
from .cloud_aws import EvidenceVault  # noqa: E402
from . import compliance, denuncia, hidro  # noqa: E402
from .compliance import ComplianceDesk  # noqa: E402
from .denuncia import DenunciaDesk  # noqa: E402
from .tenant import TenantDocs  # noqa: E402
from .mailer import Mailer  # noqa: E402
from . import ativos  # noqa: E402
from .connectors import sigmine  # noqa: E402
from .connectors import snisb  # noqa: E402
from http.cookies import SimpleCookie  # noqa: E402
import threading  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
FRONTEND = ROOT / 'web'
SCENARIO_IDS = ('eir', 'nr20', 'anm', 'anp_cp21', 'ansn')
_cache: dict[str, object] = {}
OFFICIAL: dict[str, object] = {'manifest': None, 'records': [], 'by_id': {}, 'orgs': {}, 'snap_root': sigbm.SNAP_ROOT}


def load(name):
    if name not in _cache:
        _cache[name] = json.loads((DATA / name).read_text(encoding='utf8'))
    return _cache[name]


def provisions_by_id():
    return {p['id']: p for p in load('provisions.json')}


def parse_date(value) -> date:
    if not value:
        return AS_OF
    d = date.fromisoformat(str(value)[:10])
    if not date(2020, 1, 1) <= d <= date(2035, 12, 31):
        raise ValueError('Data fora do intervalo simulável (2020–2035).')
    return d


def load_official(snap_root: Path | None = None) -> None:
    root = snap_root or OFFICIAL['snap_root']
    OFFICIAL['snap_root'] = root
    snap = sigbm.latest(root)
    if snap:
        OFFICIAL.update(manifest=snap['manifest'], records=snap['records'], by_id={r['id']: r for r in snap['records']},
                        orgs=build_registry(snap['records']), snapshots=snap['snapshots'])
    else:
        OFFICIAL.update(manifest=None, records=[], by_id={}, orgs={}, snapshots=[])
    radar.compute(OFFICIAL['records'], OFFICIAL['manifest'] and OFFICIAL['manifest']['snapshot_id'], max(date.today(), AS_OF))


def all_findings(when: date) -> list[dict]:
    return [analyze(a, s, when).payload() for s in SCENARIO_IDS for a in load('assets.json')]


def official_finding(rec: dict, when: date) -> dict:
    return analyze_official_anm(rec, when, OFFICIAL['manifest']['fetched_at'])


def finding_by_id(fid: str, when: date) -> tuple[dict, dict] | tuple[None, None]:
    """fid = '<cenario>:<ativo>' — ativo sintético (A-01) ou oficial (SIGBM-9149, somente cenário anm)."""
    if ':' not in fid:
        return None, None
    sc, aid = fid.split(':', 1)
    if aid.startswith('SIGBM-'):
        rec = OFFICIAL['by_id'].get(aid)
        if not rec or sc != 'anm':
            return None, None
        return official_finding(rec, when), official_asset(rec)
    a = next((x for x in load('assets.json') if x['id'] == aid), None)
    if not a or sc not in SCENARIO_IDS:
        return None, None
    return analyze(a, sc, when).payload(), {**a, 'origin': 'CENARIO_HIPOTETICO'}


def official_asset(rec: dict) -> dict:
    return {**rec, 'region': f"{rec.get('municipio')}/{rec.get('uf')}", 'facts': {k: rec.get(k) for k in (
        'uf', 'municipio', 'owner_name', 'dam_type', 'operational_status', 'pnsb', 'paebm_required', 'cri', 'dpa', 'emergency_level', 'main_ore')}}


def seed(store: Store) -> int:
    return store.seed_reviews(all_findings(AS_OF))


def events_from_audit(store: Store, owner_id=None) -> list[dict]:
    names = {'review.created': 'applicability.triaged', 'review.opened': 'review.opened', 'review.transition': 'review.decided',
             'review.assigned': 'review.assigned', 'evidence.attached': 'evidence.attached', 'source.ingested': 'regulatory.source.ingested',
             'integration.dispatched': 'integration.outbox.enqueued', 'finance.scenario.saved': 'decision.finance.saved',
             'connector.synced': 'connector.snapshot.created', 'entity.link.decided': 'entity.link.decided'}
    return [{'seq': a['seq'], 'at': a['at'], 'topic': names.get(a['action'], a['action']), 'entity': a['entity'], 'actor': a['actor'], 'hash': a['hash'][:12]} for a in store.audit_log(80) if a['payload'].get('owner_id') in (None,owner_id)]


ACTIONABLE = ('REVIEW', 'INSUFFICIENT', 'FUTURE_REVIEW', 'MONITOR')
STATE_ORDER = ['REVIEW', 'INSUFFICIENT', 'FUTURE_REVIEW', 'MONITOR', 'OUT_OF_SCOPE', 'NO_LINK']


def orgs() -> dict:
    return {o['id']: o for o in load('organizations.json')['items']}


def _uf(region: str) -> str | None:
    m = re.search(r'\b([A-Z]{2})\b', region or '')
    return m.group(1) if m else None


def org_scenarios(org_id: str) -> list[str]:
    o = orgs().get(org_id)
    return o['scenarios'] if o else ['anm']


def portfolio(when: date, watched: list[str], org: str = 'demo', reviews: dict | None = None) -> list[dict]:
    """Carteira da organização em contexto.
    demo  → ativos fictícios do Grupo Exemplo + estruturas oficiais adicionadas pelo usuário;
    org com CNPJ (ex.: Vale) → estruturas oficiais do SIGBM com a mesma raiz de CNPJ;
    org pesquisada sem dados → carteira vazia (nada é inventado)."""
    reviews = reviews or {}
    P = provisions_by_id()
    o = orgs().get(org) or orgs()['demo']
    out = []

    def official_item(rec):
        f = official_finding(rec, when)
        ax = assess(f, reviews.get(f"anm:{rec['id']}"), P, when, extra=rec)
        return {'id': rec['id'], 'name': rec['name'], 'kind': 'dam', 'sector': 'Mineração', 'lat': rec['lat'], 'lon': rec['lon'],
                'region': f"{rec['municipio']}/{rec['uf']}", 'uf': rec['uf'], 'municipio': rec['municipio'], 'organization': rec['owner_name'],
                'origin': 'DADO_OFICIAL', 'state': f['state'], 'scenario': 'anm', 'headline': f['headline'], 'states': {'anm': f['state']},
                'priority': ax['priority'], 'next_action': ax['next_action'], 'workflow': ax['workflow_state'], 'finding_id': f"anm:{rec['id']}",
                'details': {'Situação operacional': rec.get('operational_status'), 'Inserida na PNSB': rec.get('pnsb'), 'Tipo': rec.get('dam_type'), 'CRI (categoria oficial)': rec.get('cri'), 'DPA (categoria oficial)': rec.get('dpa')}}

    if o['id'] == 'demo':
        for a in load('assets.json'):
            fs = [analyze(a, sc, when) for sc in SCENARIO_IDS]
            best = min(fs, key=lambda f: STATE_ORDER.index(f.state))
            ax = assess(best.payload(), reviews.get(f"{best.scenario}:{a['id']}"), P, when)
            out.append({'id': a['id'], 'name': a['name'], 'kind': a['kind'], 'sector': a['sector'], 'lat': a['lat'], 'lon': a['lon'], 'region': a['region'],
                        'uf': _uf(a['region']), 'municipio': None, 'organization': a['organization'], 'origin': 'CENARIO_HIPOTETICO',
                        'state': best.state, 'scenario': best.scenario, 'headline': best.headline, 'states': {f.scenario: f.state for f in fs},
                        'priority': ax['priority'], 'next_action': ax['next_action'], 'workflow': ax['workflow_state'], 'finding_id': f"{best.scenario}:{a['id']}",
                        'details': {'Descrição': a['description'], 'Setor': a['sector']}})
        reviewed = [k.split(':', 1)[1] for k in reviews if k.startswith('anm:SIGBM-')]
        for aid in dict.fromkeys(list(watched) + reviewed):  # carteira + estruturas oficiais com revisão aberta
            rec = OFFICIAL['by_id'].get(aid)
            if rec:
                out.append(official_item(rec))
    elif o.get('cnpj_root'):
        out = [official_item(r) for r in OFFICIAL['records'] if r.get('owner_cnpj_root') == o['cnpj_root']]
    return out


API_MODULO = [('/api/ativos', 'operacao'), ('/api/minas', 'operacao'), ('/api/radar-setor', 'operacao'), ('/api/hidro', 'operacao'),
              ('/api/compliance', 'conformidade'), ('/api/obrigacoes', 'obrigacoes'), ('/api/denuncias/recebidas', 'denuncias'),
              ('/api/denuncias/responder', 'denuncias'), ('/api/docs', 'documentos'), ('/api/ai/', 'ia'), ('/api/ask', 'ia'), ('/api/agent', 'ia'),
              ('/api/ml/', 'ia'), ('/api/relatorio-empresa', 'relatorio'), ('/api/sistemas', 'sistemas')]


_ANON: dict[str, list[float]] = {}


def _anon_ok(ip: str, limite: int = 5) -> bool:
    import time as _t
    agora = _t.time()
    hist = [x for x in _ANON.get(ip, []) if agora - x < 3600]
    if len(hist) >= limite:
        return False
    _ANON[ip] = hist + [agora]
    return True


def demo_users():
    return load('demo_users.json')


def snapshot_age_days() -> int | None:
    m = OFFICIAL['manifest']
    if not m:
        return None
    return (datetime.now(timezone.utc) - datetime.fromisoformat(m['fetched_at'])).days


def make_handler(store: Store, accounts: Accounts | None = None, monitor: Monitor | None = None):
    accounts = accounts or Accounts(store)
    accounts.seed_demo(demo_users()['users'])
    workbench = Workbench(store)
    ml = MLOps(store)
    ml_state = {'ready_for': None}

    def ml_ctx():
        m = OFFICIAL['manifest']
        return {'records': OFFICIAL['records'], 'items': radar.RADAR['items'], 'today': max(date.today(), AS_OF),
                'sigbm_snapshot': m and m['snapshot_id'], 'snisb_snapshot': (radar.RADAR.get('snisb_manifest') or {}).get('snapshot_id')}

    def ml_ready():
        """Garante campeões treinados (1ª vez ~6 s; depois cache) e sincroniza o radar com o campeão de emergência."""
        key = (OFFICIAL['manifest'] and OFFICIAL['manifest']['snapshot_id'], ml.champion('emergencia') and ml.champion('emergencia')['id'])
        if ml.champion('emergencia') is None or ml.champion('dce') is None:
            c = ml_ctx()
            ml.bootstrap(c['records'], c['today'], c['sigbm_snapshot'])
        key = (OFFICIAL['manifest'] and OFFICIAL['manifest']['snapshot_id'], ml.champion('emergencia') and ml.champion('emergencia')['id'], len(radar.RADAR['items']))
        if ml_state['ready_for'] != key:
            se, sd = ml.scores('emergencia')['by_id'], ml.scores('dce')['by_id']
            for x in radar.RADAR['items']:
                if x['kind'] == 'mineracao':
                    x['model'] = se.get(x['id'])
                    x['model_dce'] = sd.get(x['id'])
            ml_state['ready_for'] = key

    planner = None
    if llm_status()['enabled'] and os.environ.get('TORRE_AGENT_LLM', '0') == '1':  # política econômica: planejador por regras
        try:
            from .cloud_aws import llm_provider
            planner = gemini_planner_factory() if llm_provider() == 'gemini' else claude_planner_factory()
        except Exception:
            planner = None
    agent = Agent(store, ml, ml_ctx, accounts, planner)
    if store.path == ':memory:':  # testes: cofre em pasta temporária, nunca no cofre da demonstração
        import tempfile
        vault = EvidenceVault(bucket='', local_root=Path(tempfile.mkdtemp(prefix='torre-vault-')))
    else:
        vault = EvidenceVault()

    def vault_sync() -> int:
        """Envia ao cofre o que ainda não está lá: snapshots, versões de modelo, decisões humanas e selo da auditoria. Idempotente."""
        n = 0
        try:
            m = OFFICIAL['manifest']
            if m and not vault.has('snapshot-sigbm', m['snapshot_id']):
                raw = OFFICIAL['snap_root'] / m['snapshot_id'] / 'Barragens.csv'
                if raw.exists():
                    vault.put('snapshot-sigbm', m['snapshot_id'], raw.read_bytes(), {'manifest_sha256': m.get('sha256'), 'source': m.get('source_url')}); n += 1
            sm = radar.RADAR.get('snisb_manifest')
            if sm and not vault.has('snapshot-snisb', sm['snapshot_id']):
                vault.put_json('snapshot-snisb', sm['snapshot_id'], sm); n += 1
            for v in ml.versions():
                nm = f"{v['target']}-v{v['id']}-{v['status']}"
                if not vault.has('modelo', nm):
                    vault.put_json('modelo', nm, {k: v[k] for k in ('id', 'target', 'version', 'status', 'snapshot_id', 'created_at', 'created_by', 'params', 'metrics',
                                                                       'feedback_used', 'promoted_by', 'promoted_at', 'promote_reason')}); n += 1
            for a_ in agent.actions():
                if a_['state'] != 'PENDENTE' and not vault.has('decisao-agente', f"acao-{a_['id']}"):
                    vault.put_json('decisao-agente', f"acao-{a_['id']}", a_); n += 1
            for d_ in store.drafts_for():
                if d_['state'] != 'RASCUNHO' and not vault.has('representacao', f"rascunho-{d_['id']}"):
                    vault.put_json('representacao', f"rascunho-{d_['id']}", d_); n += 1
            chain = store.verify_chain()
            if chain.get('ok') and chain.get('head') and not vault.has('selo-auditoria', chain['head'][:24]):
                vault.put_json('selo-auditoria', chain['head'][:24], {'head': chain['head'], 'checked': chain['checked'], 'at': datetime.now(timezone.utc).isoformat()}); n += 1
        except Exception as exc:  # o cofre nunca derruba o produto
            vault.last_error = f'{type(exc).__name__}: {str(exc)[:200]}'
        return n

    compliance_desk = ComplianceDesk(store)
    denuncias = DenunciaDesk(store)
    tenant = TenantDocs(store, vault)
    hidro_lock = threading.Lock()

    def hidro_ready():
        with hidro_lock:
            if hidro.STATE['items'] is None:
                hidro.compute()
        return hidro.STATE

    def comp_org(u):
        if not u:
            return None
        return 'demo' if (u.get('is_demo') or 'fictício' in (u.get('org_name') or '')) else (u.get('cnpj') or '')[:8] or f"user:{u.get('id')}"

    def compliance_scan(u_or_org, watched=None):
        org = u_or_org if isinstance(u_or_org, str) else comp_org(u_or_org)
        ids = watched if watched is not None else []
        official = [OFFICIAL['by_id'][i] for i in ids if i in OFFICIAL['by_id']]
        alerts = compliance.build(max(date.today(), AS_OF), load('assets.json') if org == 'demo' else [], official, radar.RADAR['by_id'],
                                  None if org == 'demo' else {'itens': []})
        return compliance_desk.sync(alerts, org, accounts.notify)

    mailer = Mailer(store)
    ativos_cfg = {'cfg': None, 'emp': None, 'notified': set()}
    DEMO_ORGS = ('demo', 'demo-mineracao', 'demo-energia', 'demo-saneamento')

    def ativos_load():
        if ativos_cfg['cfg'] is None:
            ativos_cfg['cfg'], ativos_cfg['emp'] = ativos.load()
        return ativos_cfg['cfg'], {e['id']: e for e in ativos_cfg['emp']['empresas']}

    def allowed_companies(u):
        _, emp = ativos_load()
        if not u or u.get('kind') != 'empresa':
            return []
        if u.get('empresa_id'):   # pessoa cadastrada numa frente (ex.: só a mineradora): acesso só a ela
            return [u['empresa_id']] if u['empresa_id'] in emp else []
        if u.get('is_demo') or 'fictício' in (u.get('org_name') or ''):
            return list(emp)  # modo demonstração: as três empresas fictícias
        root = str(u.get('cnpj') or '')[:8]
        return [k for k, e in emp.items() if e.get('cnpj_root') == root]

    def ativos_eval(cid):
        cfg, emp = ativos_load()
        root = emp[cid].get('cnpj_root')
        with accounts.lock:
            pessoas = {row['function'] for row in accounts.db.execute("SELECT DISTINCT function FROM users WHERE kind='empresa' AND substr(cnpj,1,8)=?", (root,))}
        r = ativos.evaluate(emp[cid], cfg, max(date.today(), AS_OF), pessoas)

        new = compliance_desk.sync(r['alerts'], cid, None)
        if new['novos'] and cid not in ativos_cfg['notified']:
            ativos_cfg['notified'].add(cid)
            for a in [x for x in r['alerts'] if x['level'] in ('Crítico', 'Alto')][:6]:
                for rc in a['recipients']:
                    if rc.get('funcao_usuario') == 'curadoria':  # empresa sem ninguém no papel: curadoria da LexIA recebe
                        accounts.notify('func:curadoria', 'ativos', f"[Escalado] {emp[cid]['nome']}: {a['title'][:110]}", f"{a['asset_name']} · nenhum responsável cadastrado na empresa", f'#/ativos?empresa={cid}', 'ATIVOS')
                    elif rc.get('funcao_usuario') and not rc.get('sem_pessoa'):
                        accounts.notify(f"orgfunc:{root}:{rc['funcao_usuario']}", 'ativos', f"{emp[cid]['nome']}: {a['title'][:120]}",
                                        f"{a['asset_name']} · nível {a['level']} · para {rc['rotulo']}", f'#/ativos?empresa={cid}', 'ATIVOS')
        return r

    def denuncia_target(dam_id):
        """Resolve a empresa responsável: ativo cadastrado na LexIA (empresa cliente) ou barragem SIGBM pelo CNPJ do empreendedor."""
        cfg, emp = ativos_load()
        if dam_id and dam_id.startswith('ATIVO:'):
            _, cid, aid = (dam_id.split(':') + ['', ''])[:3]
            e = emp.get(cid)
            a = next((x for x in (e or {}).get('ativos', []) if x['id'] == aid), None)
            if e and a:
                regs = cfg['setores'][e['setor']]['reguladores']
                dam = {'id': dam_id, 'kind': 'empresa_ativo', 'name': a['nome'], 'municipio': a.get('municipio'), 'uf': '', 'radiologico': bool(a.get('radiologico')),
                       'setor': e['setor'], 'tipo': a.get('tipo'),
                       'regulator': ', '.join(regs[:2] + (['CNEN/ANSN'] if a.get('radiologico') else []))}
                return dam, {'org': e['cnpj_root'], 'empresa': e['nome'], 'ativo': a['nome']}
            return None, None
        if dam_id and dam_id.startswith('ANM-'):  # mina (título de lavra) do SIGMINE
            m = next((m_ for m_ in (sigmine.latest() or {}).get('items', []) if m_['id'] == dam_id), None)
            if m:
                regs = 'ANM' + (', CNEN/ANSN' if m.get('radiologico') else '')
                return {'id': dam_id, 'kind': 'mina', 'name': f"Mina de {m['substancia'].lower()} · processo {m['processo']}", 'municipio': '', 'uf': m['uf'],
                        'radiologico': bool(m.get('radiologico')), 'regulator': regs, 'owner_label': m['titular']}, None
            return None, None
        if dam_id and dam_id.startswith('CEG-'):  # usina (ANEEL/SIGA)
            from .connectors import aneel_siga as _ag
            u_ = next((u_ for u_ in (_ag.latest() or {}).get('items', []) if u_['id'] == dam_id), None)
            if u_:
                from .transparencia import _empresa_pj
                mun = (u_.get('municipios') or '').split(';')[0]
                return {'id': dam_id, 'kind': 'usina', 'name': f"{u_.get('tipo_rotulo') or 'Usina'} {u_.get('nome') or ''} (CEG {u_.get('ceg')})".strip(),
                        'municipio': mun.split(' - ')[0], 'uf': u_.get('uf'), 'setor': 'energia', 'tipo': 'usina', 'regulator': 'ANEEL',
                        'owner_label': _empresa_pj(u_.get('proprietarios'))}, None
            return None, None
        x = radar.RADAR['by_id'].get(dam_id) if dam_id else None
        if not x and dam_id and dam_id.startswith('SNISB-'):  # barragem de energia ou abastecimento (ANA/SNISB)
            st_ = snisb.latest_setores() or {}
            for setor_, key_ in (('energia', 'energia'), ('saneamento', 'abastecimento')):
                b_ = next((b for b in st_.get(key_, []) if b['id'] == dam_id), None)
                if b_:
                    return {'id': dam_id, 'kind': 'barragem_' + setor_, 'name': b_.get('name'), 'municipio': (b_.get('municipio') or '').title(), 'uf': b_.get('uf'),
                            'setor': setor_, 'tipo': 'barragem', 'regulator': b_.get('regulator') or ('ANEEL' if setor_ == 'energia' else 'ANA'),
                            'owner_label': b_.get('owner')}, None
        if x and x['kind'] == 'mineracao':
            rec = OFFICIAL['by_id'].get(dam_id) or {}
            root = rec.get('owner_cnpj_root')
            if root:
                return x, {'org': root, 'empresa': rec.get('owner_name'), 'ativo': x.get('name')}
        return x, None

    def provs_setor(setor):
        from .normas_setor import provisao_aplica
        s = setor if setor in ('mineracao', 'energia', 'saneamento', 'industria') else None
        return [p for p in load('provisions.json') if provisao_aplica(p, s)]

    RADAR_SETOR = {}

    def radar_setor(tipo):
        """Radares por setor (minas-v1, outorgas-v1, barragens-usinas-v1, abastecimento-v1), calculados sob demanda e guardados por snapshot."""
        from . import radares
        from .connectors import aneel_siga
        today = max(date.today(), AS_OF)
        if tipo == 'fechamento':
            sm = sigmine.latest()
            key = (tipo, sm and sm['manifest']['snapshot_id'], OFFICIAL['manifest'] and OFFICIAL['manifest'].get('snapshot_id'))
            make = lambda: radares.minas_fechamento(sm['items'], OFFICIAL['records'], today) if sm else None
            snap = sm and sm['manifest']['snapshot_id']
        elif tipo == 'radiologico':
            sm = sigmine.latest()
            from .radar import RADAR as _R
            key = (tipo, sm and sm['manifest']['snapshot_id'], OFFICIAL['manifest'] and OFFICIAL['manifest'].get('snapshot_id'))
            snap = sm and sm['manifest']['snapshot_id']
            make = lambda: radares.radiologico(sm['items'], radar_setor('fechamento'), OFFICIAL['records'], _R.get('by_id', {})) if sm else None
        elif tipo == 'outorgas':
            ag = aneel_siga.latest()
            key, snap = (tipo, ag and ag['manifest']['snapshot_id']), ag and ag['manifest']['snapshot_id']
            make = lambda: radares.outorgas(ag['items'], today) if ag else None
        elif tipo in ('barragens_usinas', 'abastecimento'):
            st_ = snisb.latest_setores()
            key, snap = (tipo, st_ and st_['manifest']['snapshot_id']), st_ and st_['manifest']['snapshot_id']
            make = lambda: (radares.barragens_usinas(st_['energia'], today) if tipo == 'barragens_usinas' else radares.abastecimento(st_['abastecimento'], today)) if st_ else None
        else:
            return None
        if RADAR_SETOR.get(tipo, (None,))[0] != key:
            r = make()
            if r is not None:
                r['snapshot'] = snap
            RADAR_SETOR[tipo] = (key, r)
        return RADAR_SETOR[tipo][1]

    PERM_ROTULO = {'review.open': 'abrir revisões', 'review.transition': 'mover revisões', 'review.decide': 'decidir revisões', 'evidence.add': 'anexar evidências',
                   'dispatch': 'encaminhar ações', 'draft.create': 'criar rascunhos', 'draft.decide': 'aprovar rascunhos', 'agent.run': 'rodar o agente',
                   'agent.decide': 'aprovar propostas do agente', 'model.train': 'treinar modelos', 'model.promote': 'promover modelos', 'watch': 'acompanhar ativos',
                   'contingency.edit': 'editar plano de contingência', 'finance.save': 'salvar cenários financeiros', 'entity.confirm': 'confirmar entidades', 'model.feedback': 'dar retorno ao modelo'}

    def equipe_efeitos(u, empresa_id=None):
        """Para cada função: que alertas recebe (rota do setor × papel da empresa) e o que pode fazer (permissões do papel)."""
        from .accounts import FUNCOES, FUNCTION_TO_ROLE
        cfg, emp = ativos_load()
        ids = allowed_companies(u)
        cid = empresa_id if empresa_id in ids else (ids[0] if ids else None)
        comp = emp.get(cid) if cid else None
        perms = demo_users()['permissions']
        occ_nome = {'documento_vencendo': 'documento vencendo', 'documento_vencido': 'documento vencido', 'anomalia_operacional': 'anomalia em sensor',
                    'possivel_infracao': 'possível infração', 'denuncia_recebida': 'denúncia recebida', 'radiologico': 'ocorrência radiológica'}
        out = {}
        for f, rot in FUNCOES.items():
            papeis = [p for p, ff in ((comp or {}).get('usuarios_por_papel') or {}).items() if ff == f]
            rec = [occ_nome.get(o, o) for o, ps in cfg['roteamento_padrao'].items() if set(ps) & set(papeis)]
            out[f] = {'rotulo': rot, 'papeis': [cfg['papeis'].get(p, 'Responsável pelo documento' if p == 'dono_do_documento' else p) for p in papeis],
                      'recebe': rec, 'pode': [PERM_ROTULO.get(x, x) for x in perms.get(FUNCTION_TO_ROLE[f], []) if x in PERM_ROTULO],
                      'responde_denuncias': FUNCTION_TO_ROLE[f] in ('compliance', 'juridico', 'gestor')}
        vazios = []
        if comp:
            with accounts.lock:
                tem = {r['function'] for r in accounts.db.execute("SELECT DISTINCT function FROM users WHERE kind='empresa' AND substr(cnpj,1,8)=? AND COALESCE(status,'ativo')='ativo'", (str(u.get('cnpj') or '')[:8],))}
            for p, f in (comp.get('usuarios_por_papel') or {}).items():
                if f not in tem:
                    vazios.append({'papel': cfg['papeis'].get(p, 'Responsável pelo documento' if p == 'dono_do_documento' else p), 'funcao': f})
        return {'empresa': comp and comp['nome'], 'funcoes': out, 'papeis_sem_pessoa': vazios}

    def lexia_orgs():
        """{cnpj_root: nome} das empresas que recebem denúncias na LexIA (cadastro de demonstração + contas empresa)."""
        _, emp = ativos_load()
        out = {e_['cnpj_root']: e_['nome'] for e_ in emp.values() if e_.get('cnpj_root')}
        with accounts.lock:
            for r in accounts.db.execute("SELECT DISTINCT substr(cnpj,1,8) AS root, org_name FROM users WHERE kind='empresa' AND cnpj IS NOT NULL AND cnpj != ''"):
                out.setdefault(r['root'], r['org_name'] or r['root'])
        return out

    def ativos_geo():
        _, emp = ativos_load()
        return [{'id': f"ATIVO:{cid}:{a['id']}", 'tipo': a.get('tipo', 'ativo').replace('_', ' ').capitalize(), 'tipo_raw': a.get('tipo'), 'nome': a['nome'], 'local': a.get('municipio') or '',
                 'empresa': e_['nome'], 'atencao': None, 'lat': a['lat'], 'lon': a['lon'], 'setor': e_.get('setor'), 'radiologico': bool(a.get('radiologico'))}
                for cid, e_ in emp.items() for a in e_.get('ativos', []) if a.get('lat') is not None]

    def company_recipients(root):
        with accounts.lock:
            rows = accounts.db.execute("SELECT name,email,function,role FROM users WHERE kind='empresa' AND substr(cnpj,1,8)=?", (root,)).fetchall()
        return [dict(r) for r in rows if (r['function'] in ('compliance', 'juridico') or r['role'] in ('compliance', 'juridico'))]

    def agent_run(trigger):
        ml_ready()
        out = agent.run(trigger)
        ml_ready()
        try:  # agente de compliance da organização de demonstração roda junto
            compliance_scan('demo')
        except Exception:
            pass
        vault_sync()
        return out
    make_handler.agent_run = agent_run

    class Handler(SimpleHTTPRequestHandler):
        extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.webmanifest': 'application/manifest+json',
                          '.js': 'text/javascript', '.mjs': 'text/javascript', '.svg': 'image/svg+xml', '.json': 'application/json'}

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(FRONTEND), **kwargs)

        def log_message(self, fmt, *args):
            if os.environ.get('TORRE_QUIET') != '1':
                super().log_message(fmt, *args)

        def end_headers(self):
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            _pth = (self.path or '').split('?')[0]
            if not _pth.startswith('/api/') and (_pth == '/' or _pth.endswith(('.html', '.js', '.mjs', '.css', '.webmanifest', '.png', '.jpg', '.jpeg', '.svg'))):
                self.send_header('Cache-Control', 'no-cache')   # sempre confere a versão no servidor (evita logo/CSS antigos)
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                             "img-src 'self' data: blob: https://server.arcgisonline.com; font-src 'self'; connect-src 'self'; "
                             "worker-src 'self'; manifest-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
            super().end_headers()

        def _send(self, body: bytes, ctype: str, status=200, extra=None):
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=200):
            self._send(json.dumps(obj, ensure_ascii=False).encode('utf8'), 'application/json; charset=utf-8', status)

        def _cookie(self):
            c = SimpleCookie(self.headers.get('Cookie', ''))
            return c['torre_session'].value if 'torre_session' in c else ''

        def _user(self):
            su = accounts.session_user(self._cookie())
            if su:
                return {**su, 'token': None}
            auth = self.headers.get('Authorization', '')
            token = auth[7:].strip() if auth.startswith('Bearer ') else ''
            u = next((u for u in demo_users()['users'] if u['token'] == token), None)
            if u:  # token fixo de demonstração (scripts/testes); a interface usa sessão por cookie
                return {'id': None, 'kind': u.get('kind', 'empresa'), 'name': u['name'], 'role': u['role'], 'function': u.get('function'),
                        'org_name': u.get('org_name'), 'token': token}
            return None

        def _same_origin(self):
            origin = self.headers.get('Origin')
            if not origin:
                return True
            return urlparse(origin).netloc == self.headers.get('Host', '')

        def _require(self, perm: str):
            u = self._user()
            if not u:
                self._json({'error': 'Autenticação de demonstração necessária: escolha um usuário no topo.'}, 401)
                return None
            if perm not in demo_users()['permissions'].get(u['role'], []):
                self._json({'error': f"O papel '{u['role']}' não tem permissão para esta ação ({perm})."}, 403)
                return None
            return u

        # ---------------------------------------------------------------- GET
        def _work_user(self):
            u=self._user()
            if not u or not u.get('id'):
                self._json({'error':'Entre com uma conta empresarial (sessão).'},401);return None
            if u['kind']!='empresa':
                self._json({'error':'Área de acompanhamento exclusiva de conta empresarial.'},403);return None
            return u

        def _work_reviews(self,u):
            watched=set(accounts.watchlist(u['id']))
            return [r for r in store.reviews() if r['asset_id'] in watched or (u.get('is_demo') and r.get('origin')=='CENARIO_HIPOTETICO')]

        def _work_reference(self,rid,when,u):
            r=next((r for r in self._work_reviews(u) if r['id']==rid),None)
            if not r:raise WorkflowError('Revisão fora da carteira autorizada desta conta.')
            pids={pid for s in load('scenarios.json') if s['id']==r['scenario'] for pid in s['provisions']}
            return reference([p for p in snapshot(load('provisions.json'),when) if p['id'] in pids])

        def _work_summary(self,u):
            return workbench.summary(u['id'],{r['id'] for r in self._work_reviews(u)},accounts.notifications(u,10000)['items'])

        def _visible_audit(self,limit):
            u=self._user();uid=u and u.get('id')
            return [a for a in store.audit_log(limit) if a['payload'].get('owner_id') in (None,uid)]

        def _meter(self, route):
            if route.startswith('/api/'):
                try:
                    from .cloud_aws import meter_request
                    u = self._user()
                    meter_request(comp_org(u) if u else None, route.split('/')[2] if route.count('/') >= 2 else 'outros')
                except Exception:
                    pass

        def _bloqueio(self, route):
            """Módulo desmarcado pela gestão = API fechada para a pessoa (não só some do menu)."""
            if route == '/api/ativos/empresas' or not route.startswith('/api/'):
                return False
            mod = next((m for p, m in API_MODULO if route.startswith(p)), None)
            if not mod:
                return False
            u = self._user()
            if not u or u.get('modulos') is None or mod in u['modulos']:
                return False
            from .accounts import MODULOS
            self._json({'error': f"Seu acesso a “{MODULOS[mod]}” não foi liberado pela gestão da empresa."}, 403)
            return True

        def do_GET(self):
            url = urlparse(self.path)
            route, qs = url.path, {k: v[0] for k, v in parse_qs(url.query).items()}
            self._meter(route)
            if self._bloqueio(route):
                return
            try:
                when = parse_date(qs.get('as_of'))
            except ValueError as exc:
                return self._json({'error': str(exc)}, 400)
            static = {'/api/assets': 'assets.json', '/api/sources': 'sources.json', '/api/scenarios': 'scenarios.json',
                      '/api/connectors': 'connectors.json', '/api/checklist': 'checklist.json'}
            if route in static:
                return self._json(load(static[route]))
            P = provisions_by_id()
            reviews = {r['id']: r for r in store.reviews()}
            if route.startswith('/api/workbench/'):
                u=self._work_user()
                if not u:return
                try:
                    if route=='/api/workbench/projects':return self._json(workbench.projects(u['id']))
                    if route=='/api/workbench/project':
                        p=workbench.project(u['id'],qs.get('id',''))
                        visible={r['id'] for r in self._work_reviews(u)}
                        return self._json({**p,'conditions':workbench.conditions(u['id'],p['id']),'linked_reviews':[r for r in workbench.linked_reviews(u['id'],p['id']) if r['review_id'] in visible]})
                    if route=='/api/workbench/dossier':
                        p=workbench.project(u['id'],qs.get('id',''))
                        visible={r['id']:r for r in self._work_reviews(u)}
                        linked=[{'link':r,'review':visible[r['review_id']],'reference':workbench.baseline(u['id'],r['review_id'])} for r in workbench.linked_reviews(u['id'],p['id']) if r['review_id'] in visible]
                        return self._send(dossier(p,workbench.conditions(u['id'],p['id']),linked).encode('utf8'),'text/html; charset=utf-8',extra={'Content-Disposition':'attachment; filename="dossie-projeto.html"'})
                    if route=='/api/workbench/summary':return self._json(self._work_summary(u))
                    if route=='/api/workbench/exclusions':
                        watched=set(accounts.watchlist(u['id']))
                        out=[]
                        for f in all_findings(when):
                            if not u.get('is_demo') and f['asset_id'] not in watched:continue
                            if f['state'] not in ('OUT_OF_SCOPE','NO_LINK','INSUFFICIENT'):continue
                            out.append({'id':f"{f['scenario']}:{f['asset_id']}",'state':f['state'],'reason':f['rationale'],
                                        'missing':f['missing'],'source_ids':f['source_ids'],'provisions':f['provisions'],'as_of':f['as_of']})
                        return self._json({'items':out,'note':'Resultados de regras locais no recorte sintético autorizado. Fora do escopo não significa dispensa geral; dados insuficientes exigem complemento. Não é catálogo de todas as publicações oficiais.'})
                    if route=='/api/workbench/revalidations':
                        items=[]
                        for r in self._work_reviews(u):
                            old=workbench.baseline(u['id'],r['id']);current=self._work_reference(r['id'],when,u)
                            delta=changes(old['payload'],current) if old else []
                            items.append({'review_id':r['id'],'headline':r['headline'],'reference_at':old and old['at'],
                                          'status':'MUDANCA_DETECTADA' if delta else 'SEM_DIFERENCA' if old else 'REFERENCIA_AUSENTE','changes':delta})
                        return self._json({'items':items,'proposals':workbench.revalidations(u['id'])})
                except WorkflowError as exc:return self._json({'error':str(exc)},400)
                return self._json({'error':'Rota não encontrada.'},404)
            if route == '/api/health':
                m = OFFICIAL['manifest']
                return self._json({'ok': True, 'mode': 'demo', 'llm': llm_status(), 'llm_enabled': llm_status()['enabled'],
                                   'sources': len(load('sources.json')), 'assets': len(load('assets.json')), 'scenarios': len(SCENARIO_IDS),
                                   'as_of': AS_OF.isoformat(), 'audit_chain': store.verify_chain(),
                                   'official': {'connector': 'ANM_SIGBM', 'records': len(OFFICIAL['records']),
                                                'snapshot_id': m and m['snapshot_id'], 'fetched_at': m and m['fetched_at'],
                                                'age_days': snapshot_age_days()}})
            if route == '/api/auth/me':
                u = self._user()
                if not u:
                    return self._json({'authenticated': False})
                perms = demo_users()['permissions'].get(u['role'], [])
                wl = accounts.watchlist(u['id']) if u.get('id') else []
                return self._json({'authenticated': True, 'user': {k: v for k, v in u.items() if k != 'token'}, 'permissions': perms, 'watchlist': wl})
            if route == '/api/notifications':
                u = self._user()
                perfil = None
                if u and u.get('kind') == 'empresa' and qs.get('empresa') in allowed_companies(u):
                    cfg_, emp_ = ativos_load()
                    e_ = emp_[qs['empresa']]
                    perfil = {'cid': qs['empresa'], 'root': e_.get('cnpj_root'), 'setor': e_.get('setor')}
                return self._json(accounts.notifications(u, perfil=perfil))
            if route == '/api/watchlist':
                u = self._user()
                return self._json({'items': accounts.watchlist(u['id']) if u and u.get('id') else []})
            if route == '/api/portfolio':
                u = self._user()
                return self._json(portfolio(when, accounts.watchlist(u['id']) if u and u.get('id') else [], qs.get('org', 'demo'), reviews))
            if route == '/api/organizations':
                u = self._user()
                wl = accounts.watchlist(u['id']) if u and u.get('id') else []
                out = []
                for o in load('organizations.json')['items']:
                    n = (12 + len([w for w in wl if w in OFFICIAL['by_id']])) if o['id'] == 'demo' else sum(1 for r in OFFICIAL['records'] if o.get('cnpj_root') and r.get('owner_cnpj_root') == o['cnpj_root'])
                    out.append({**o, 'asset_count': n})
                return self._json({'notice': load('organizations.json')['notice'], 'items': out})
            if route == '/api/insight':
                return self._json(self._insight(when, qs.get('org', 'demo'), reviews))
            if route == '/api/monitor':
                return self._json({'targets': [{k: t[k] for k in ('id', 'name', 'url', 'kind')} for t in (monitor.targets if monitor else [])],
                                   'status': accounts.monitor_status(), 'blocked_channels': BLOCKED_CHANNELS,
                                   'running': bool(monitor and monitor.running), 'last_run': monitor and monitor.last_run,
                                   'interval_min': float(os.environ.get('TORRE_MONITOR_MIN', '360')), 'enabled': bool(monitor)})
            if route == '/api/demo/users':
                d = demo_users()
                return self._json({'warning': d['warning'], 'permissions': d['permissions'],
                                   'users': [{k: u.get(k) for k in ('id', 'name', 'role', 'function', 'token', 'email', 'kind')} for u in d['users']]})
            if route == '/api/llm/status':
                return self._json(llm_status())
            if route == '/api/provisions':
                return self._json(snapshot(load('provisions.json'), when))
            if route == '/api/timeline':
                return self._json(milestones(load('provisions.json')))
            if route == '/api/findings':
                out = []
                for f in all_findings(when):
                    r = reviews.get(f"{f['scenario']}:{f['asset_id']}")
                    out.append({**f, 'origin': 'CENARIO_HIPOTETICO', 'axes': assess(f, r, P, when)})
                return self._json(out)
            if route == '/api/diff':
                if qs.get('scenario') not in SCENARIO_IDS:
                    return self._json({'error': 'Cenário inválido.'}, 400)
                return self._json(scenario_diffs(qs['scenario'], P))
            if route == '/api/executive':
                return self._json(self._executive(when, P, reviews, qs.get('org', 'demo')))
            # ------------------------------------------------ Modelos (ciclo de evolução) e agente
            if route == '/api/ml/models':
                ml_ready()
                out = {}
                for t, T in risk_model.TARGETS.items():
                    cmp = ml.compare(t)
                    out[t] = {'name': T['name'], 'question': T['question'], 'champion': ml.champion(t), 'challenger': ml.challenger(t),
                              'compare': cmp and {k: cmp[k] for k in ('delta_auc', 'delta_prec50', 'recommendation', 'rule')},
                              'monitor': ml.monitor(t, OFFICIAL['records']), 'versions': ml.versions(t)[:12],
                              'feedback': ml.feedback_list(t)[:30]}
                return self._json(out)
            if route == '/api/ml/predictions' or route == '/api/ai/hidden-risk':
                ml_ready()
                t = qs.get('target', 'emergencia')
                if t not in risk_model.TARGETS:
                    return self._json({'error': 'Modelo inexistente.'}, 400)
                ch = ml.champion(t, full=True)
                if not ch:
                    return self._json({'available': False, 'reason': 'Modelo ainda não treinado.'})
                S, rows = ch['summary'], []
                for i in S['flagged']:
                    x = radar.RADAR['by_id'].get(i)
                    s_ = ch['scores'].get(i)
                    if x and s_:
                        rows.append({'id': i, 'name': x.get('name'), 'uf': x.get('uf'), 'municipio': x.get('municipio'), 'owner_kind': x['owner']['kind'],
                                     'status': x.get('operational_status'), 'attention': x['attention'], 'p': s_['p'], 'percentile': s_['percentile'], 'why': s_['why']})
                return self._json({'available': True, 'target': t, 'version_id': ch['id'], 'version': ch['version'], 'metrics': ch['metrics'],
                                   'feedback_used': ch['feedback_used'], 'flagged_total': len(rows), 'items': rows,
                                   **{k: S[k] for k in ('name', 'question', 'trained_on', 'positives', 'features', 'threshold', 'top_features', 'method', 'limits', 'flag_text', 'positive_label')},
                                   'reading': 'Pedido de conferência: perfil técnico declarado parecido com o dos casos positivos. Não é diagnóstico de segurança.'})
            if route == '/api/evidencias':
                import csv as _csv
                pth = ROOT / 'data' / 'estudo_evidencias.csv'
                if not pth.exists():
                    return self._json({'items': []})
                with pth.open(encoding='utf-8-sig', newline='') as fh:
                    rows = list(_csv.DictReader(fh, delimiter=';'))
                return self._json({'items': rows, 'fonte': 'Banco de evidências do relatório de mercado (07/11/2026)'})
            if route == '/api/business':
                if (self._user() or {}).get('role') != 'curador':  # material interno da equipe LexIA (custos, preço, mercado)
                    return self._json({'error': 'Área interna da equipe LexIA.'}, 403)
                ml_ready()
                stq: dict = {}
                agent.tool_priorizar(stq, k=50)
                models = {t: ml.champion(t) for t in risk_model.TARGETS}
                flagged = set()
                for t in risk_model.TARGETS:
                    ch = ml.champion(t)
                    if ch:
                        flagged |= set(ch['summary']['flagged'])
                return self._json(business.build(OFFICIAL['records'], radar.RADAR['items'], flagged, stq.get('queue') or [], models))
            # ------------------------------------------------ Compliance, denúncia, documentos, ONS, custo da IA
            if route == '/api/compliance':
                u = self._user()
                if not u or u.get('kind') != 'empresa' or not u.get('id'):
                    return self._json({'error': 'Área da empresa: entre com uma conta empresarial.'}, 401)
                org = comp_org(u)
                if qs.get('org') and (qs['org'] in allowed_companies(u)):
                    org = qs['org']
                    if not compliance_desk.list(org):
                        ativos_eval(org)
                if not compliance_desk.list(org):
                    compliance_scan(org, accounts.watchlist(u['id']))
                items = compliance_desk.list(org)
                if qs.get('id'):
                    a = next((x for x in items if x['id'] == qs['id']), None)
                    return self._json({**(a or {}), 'history': compliance_desk.history(qs['id'])} if a else {'error': 'Alerta não encontrado.'}, 200 if a else 404)
                from collections import Counter as _C
                return self._json({'org': org, 'items': items, 'by_level': dict(_C(a['level'] for a in items if a['status'] in ('ABERTO', 'EM_REGULARIZACAO'))),
                                   'by_status': dict(_C(a['status'] for a in items)), 'rule_version': compliance.RULE_VERSION,
                                   'note': 'Alertas por regra (sem IA generativa). Avisos vão para o sino da plataforma; nenhum envio externo automático.'})
            if route == '/api/denuncia/preview':
                x, _t = denuncia_target(qs.get('dam_id', ''))
                return self._json(denuncia.build(qs.get('relato', '')[:4000], x, [], max(date.today(), AS_OF)))
            if route == '/api/denuncia-anonima':
                import hashlib as _hl
                cod = qs.get('codigo', '').strip().upper()
                owner = 'anonimo:' + _hl.sha256(cod.encode()).hexdigest()
                with store.lock:
                    r_ = store.db.execute('SELECT id FROM denuncias WHERE owner=? ORDER BY id DESC LIMIT 1', (owner,)).fetchone()
                if not cod or not r_:
                    return self._json({'error': 'Código não encontrado. Confira as letras e os números.'}, 404)
                d_ = denuncias.get(r_['id'], owner)
                with store.lock:
                    try:
                        dest = store.db.execute('SELECT empresa, state, resposta, updated_at FROM denuncia_destino WHERE denuncia_id=?', (d_['id'],)).fetchone()
                    except Exception:
                        dest = None
                return self._json({**d_, 'empresa_resposta': dict(dest) if dest else None})
            if route == '/api/repasses':
                u = self._user()
                if not u or u.get('kind') != 'empresa':
                    return self._json({'items': []})
                from . import triagem as _tg
                org_ = comp_org(u)
                if qs.get('empresa') in allowed_companies(u):
                    org_ = ativos_load()[1][qs['empresa']].get('cnpj_root') or org_
                return self._json({'items': _tg.listar(store, org_, qs.get('tipo') or None)})
            if route == '/api/denuncias':
                u = self._user()
                if not u or not u.get('id'):
                    return self._json({'error': 'Entre com uma conta.'}, 401)
                if qs.get('id'):
                    return self._json(denuncias.get(int(qs['id']), f"usuario:{u['id']}"))
                return self._json({'items': denuncias.mine(f"usuario:{u['id']}")})
            if route == '/api/docs':
                u = self._user()
                if not u or not u.get('id'):
                    return self._json({'error': 'Entre com uma conta.'}, 401)
                return self._json(tenant.list(u))
            if route == '/api/docs/file':
                u = self._user()
                if not u or not u.get('id'):
                    return self._json({'error': 'Entre com uma conta.'}, 401)
                try:
                    meta, body = tenant.read(u, int(qs.get('id', 0)))
                except WorkflowError as exc:
                    return self._json({'error': str(exc)}, 403)
                return self._send(body, meta['mime'], extra={'Content-Disposition': f'attachment; filename="{meta["name"]}"', 'Cache-Control': 'no-store'})
            if route == '/api/hidro':
                st = hidro_ready()
                items = st['items'] or []
                if qs.get('id'):
                    x = st['by_id'].get(qs['id'])
                    return self._json(x or {'error': 'Reservatório não encontrado.'}, 200 if x else 404)
                from collections import Counter as _C
                lvl = qs.get('attention')
                return self._json({'items': [hidro.light(x) for x in items if not lvl or x['attention'] == lvl], 'levels': dict(_C(x['attention'] for x in items)),
                                   'total': len(items), 'meta': st['meta'], 'rule_version': hidro.RULE_VERSION,
                                   'reading': 'Apoio à manutenção preventiva com dados abertos do ONS. Não é diagnóstico de segurança; a operação é do ONS e dos agentes.'})
            if route == '/api/ativos/empresas':
                u = self._user()
                cfg, emp = ativos_load()
                ids = allowed_companies(u)
                return self._json({'items': [{'id': k, 'nome': emp[k]['nome'], 'setor': emp[k]['setor'], 'setor_nome': cfg['setores'][emp[k]['setor']]['nome'], 'ativos': len(emp[k]['ativos']),
                                             'rotas': cfg['setores'][emp[k]['setor']].get('rotas_operacao', ['ativos']) + cfg.get('rotas_conformidade', []), 'uf': emp[k].get('uf')} for k in ids],
                                   'setores': {k: {'nome': v['nome'], 'abas': v['abas'], 'reguladores': v['reguladores'], 'tipos': list(v['ativos'])} for k, v in cfg['setores'].items()},
                                   'aviso': ativos_cfg['emp']['aviso']})
            if route == '/api/ativos':
                u = self._user()
                cid = qs.get('empresa', '')
                if cid not in allowed_companies(u):
                    return self._json({'error': 'Empresa fora do seu acesso.'}, 403)
                r = ativos_eval(cid)
                st = {a['id']: a['status'] for a in compliance_desk.list(cid)}
                for a in r['alerts']:
                    a['status'] = st.get(a['id'], 'ABERTO')
                cfg, emp = ativos_load()
                r['config'] = {'setor': emp[cid]['setor'], 'abas_ativas': r['abas_ativas'], 'usuarios_por_papel': emp[cid].get('usuarios_por_papel'),
                               'roteamento': cfg['roteamento_padrao'], 'papeis': cfg['papeis'], 'uf': emp[cid].get('uf')}
                return self._json(r)
            if route == '/api/sistemas':   # impacto em sistemas: catálogo de mudanças e portfólio
                u = self._user()
                if not u or u.get('kind') != 'empresa':
                    return self._json({'error': 'Área da empresa.'}, 401)
                from . import sistemas as _si
                P = _si.portfolio()
                return self._json({'mudancas': [{k: m[k] for k in ('id', 'titulo', 'norma', 'vigencia', 'mudanca', 'provisao')} for m in _si.mudancas()],
                                   'portfolio': len(P['apps']), 'repos': sum(bool(a.get('repo')) for a in P['apps']), 'aviso': P['aviso'],
                                   'tarefas': _si.tarefas(store, comp_org(u)), 'ia': llm_status()['enabled'], 'rule_version': _si.RULE_VERSION})
            if route == '/api/sistemas/mapear':
                u = self._user()
                if not u or u.get('kind') != 'empresa':
                    return self._json({'error': 'Área da empresa.'}, 401)
                from . import sistemas as _si
                return self._json(_si.mapear(qs.get('mudanca', '')))
            if route == '/api/relatorio-empresa':  # relatório da própria empresa (frente ativa): operação, alertas, obrigações, denúncias e dados públicos
                u = self._user()
                ids = allowed_companies(u)
                cid = qs.get('empresa') if qs.get('empresa') in ids else (ids[0] if ids else None)
                if not cid:
                    return self._json({'error': 'Relatório disponível para contas de empresa.'}, 403)
                from . import relatorio as _rel
                from .connectors import aneel_siga as _ag
                from .radar import RADAR as _R
                cfg, emp = ativos_load()
                e_ = emp[cid]
                r = ativos_eval(cid)
                st = {a['id']: a['status'] for a in compliance_desk.list(cid)}
                alerts = [{**a, 'status': st.get(a['id'], 'ABERTO')} for a in r['alerts']]
                inbox = denuncia.inbox(store, e_.get('cnpj_root') or '')
                pub = _rel.relatorio(e_.get('cnpj_root') or e_['nome'], OFFICIAL['records'], _R.get('by_id', {}), (sigmine.latest() or {}).get('items', []),
                                     radar_setor('fechamento'), (_ag.latest() or {}).get('items', []), radar_setor('outorgas'), snisb.latest_setores())
                from collections import Counter as _C
                from . import extrator as _ex
                return self._json({
                    'empresa': e_['nome'], 'cnpj_raiz': e_.get('cnpj_root'), 'setor': cfg['setores'][e_['setor']]['nome'], 'reguladores': cfg['setores'][e_['setor']]['reguladores'],
                    'gerado_em': max(date.today(), AS_OF).isoformat(), 'ficticia': 'fictíci' in e_['nome'].lower(),
                    'ativos': [{'nome': a['nome'], 'tipo': a['tipo_rotulo'], 'municipio': a.get('municipio'), 'status': a['status'],
                                'ocorrencias': a.get('ocorrencias') or 0, 'documentos': len(a.get('documentos') or [])} for a in r['assets']],
                    'status': dict(_C(a['status'] for a in r['assets'])),
                    'alertas': [{'titulo': a['title'], 'ativo': a['asset_name'], 'nivel': a['level'], 'prazo': a.get('due'), 'base': a.get('basis'), 'status': a['status'],
                                 'responsavel': ', '.join(rc.get('rotulo', '') for rc in a.get('recipients', [])[:2])} for a in alerts][:30],
                    'alertas_por_nivel': dict(_C(a['level'] for a in alerts)),
                    'obrigacoes': [{'obrigacao': o['obrigacao'], 'prazo': o.get('prazo'), 'papel': o.get('papel'), 'state': o['state']} for o in _ex.listar(store, comp_org(u)) if o['state'] == 'CONFIRMADA'][:20],
                    'denuncias': {'recebidas': len(inbox), 'por_situacao': dict(_C(x['dest_state'] for x in inbox))},
                    'dados_publicos': pub if pub.get('encontrado') else None,
                    'aviso': 'Relatório de apoio à gestão: não é parecer jurídico nem certificação. Base legal e prazos vêm das regras versionadas da LexIA; confirme com o responsável técnico.',
                    'rule_version': 'relatorio-empresa-v1'})
            if route == '/api/relatorio':  # relatório gratuito por empresa (público, só dados públicos)
                from . import relatorio as _rel
                from .connectors import aneel_siga as _ag
                from .radar import RADAR as _R
                return self._json(_rel.relatorio(qs.get('q', '')[:120], OFFICIAL['records'], _R.get('by_id', {}), (sigmine.latest() or {}).get('items', []),
                                                 radar_setor('fechamento'), (_ag.latest() or {}).get('items', []), radar_setor('outorgas'), snisb.latest_setores()))
            if route == '/api/mercado-setores':
                from . import relatorio as _rel
                from .connectors import aneel_siga as _ag
                return self._json(_rel.mercado((_ag.latest() or {}).get('items', []), radar_setor('outorgas'), snisb.latest_setores(), OFFICIAL['records']))
            if route == '/api/equipe':
                u = self._user()
                if not u or u.get('kind') != 'empresa' or not u.get('id'):
                    return self._json({'error': 'Disponível para contas de empresa.'}, 401)
                from .accounts import MODULOS, MODULOS_PADRAO
                _, emp_ = ativos_load()
                return self._json({**accounts.team(u), **equipe_efeitos(u, qs.get('empresa')), 'sou_admin': accounts.is_admin(u), 'eu': u['id'],
                                   'modulos': MODULOS, 'modulos_padrao': MODULOS_PADRAO,
                                   'frentes': [{'id': k, 'nome': emp_[k]['nome'], 'setor': emp_[k]['setor']} for k in allowed_companies(u)]})
            if route == '/api/convite':
                info = accounts.invite_info(qs.get('t', ''))
                return self._json(info or {'error': 'Convite inválido, usado ou vencido.'}, 200 if info else 404)
            if route == '/api/obrigacoes':
                u = self._user()
                if not u:
                    return self._json({'error': 'Entre para ver.'}, 401)
                from . import extrator as _ex
                return self._json({'items': _ex.listar(store, comp_org(u))})
            if route == '/api/radar-setor':
                if not self._user():
                    return self._json({'error': 'Entre para ver.'}, 401)
                tipo = qs.get('tipo', '')
                r = radar_setor(tipo)
                if r is None:
                    return self._json({'error': 'Radar sem dados: rode a coleta do conector.'}, 404)
                its = r['items']
                if qs.get('nivel'):
                    its = [x for x in its if x['atencao'] == qs['nivel']]
                if qs.get('uf'):
                    its = [x for x in its if x.get('uf') == qs['uf']]
                if qs.get('q'):
                    q_ = qs['q'].lower()
                    its = [x for x in its if q_ in (f"{x.get('nome')} {x.get('empresa')} {x.get('municipio') or ''}").lower()]
                pts = [{'id': x['id'], 'lat': x['lat'], 'lon': x['lon'], 'a': x['atencao']} for x in its if x.get('lat') is not None and (x['atencao'] in ('Crítica', 'Alta', 'Moderada') or tipo == 'radiologico')]
                return self._json({**{k: v for k, v in r.items() if k != 'items'}, 'total': len(r['items']), 'filtrados': len(its),
                                   'items': its[:int(qs.get('limit', 300))], 'pontos': pts[:4000]})
            if route == '/api/cobertura':
                from .normas_setor import cobertura as _cob
                return self._json(_cob(compliance.CATALOG))
            if route == '/api/transparencia':
                from . import transparencia as _tp
                from .radar import RADAR as _R
                with store.lock:
                    return self._json(_tp.panorama(OFFICIAL['records'], _R.get('by_id', {}), _R.get('items', []), (sigmine.latest() or {}).get('items', []),
                                                   store.db, lexia_orgs(), OFFICIAL['manifest'] and {k: OFFICIAL['manifest'].get(k) for k in ('snapshot_id', 'fetched_at')}))
            if route == '/api/empresa-publica':  # exemplo real: só dados públicos da ANM de uma pessoa jurídica
                if not self._user():
                    return self._json({'error': 'Entre para ver.'}, 401)
                from . import transparencia as _tp
                from .radar import RADAR as _R
                root = re.sub(r'\D', '', qs.get('root', ''))[:8]
                recs = [r for r in OFFICIAL['records'] if r.get('owner_cnpj_root') == root and r.get('owner_doc_type') != 'CPF_MASCARADO_OCULTO']
                if not recs:
                    return self._json({'error': 'Empresa não encontrada no SIGBM.'}, 404)
                name = recs[0].get('owner_name')
                minas = [m for m in (sigmine.latest() or {}).get('items', []) if _tp._n(m.get('titular')) == _tp._n(name)]
                dams = []
                for r in recs:
                    x = _R.get('by_id', {}).get(r['id']) or {}
                    dams.append({'id': r['id'], 'nome': r.get('name'), 'municipio': r.get('municipio'), 'uf': r.get('uf'), 'lat': r.get('lat'), 'lon': r.get('lon'),
                                 'mina': r.get('mine_name'), 'minerio': r.get('main_ore'), 'tipo': r.get('dam_type'), 'situacao': r.get('operational_status'),
                                 'dpa': r.get('dpa'), 'cri': r.get('cri'), 'emergencia': r.get('emergency_level'), 'dce': r.get('dce_rpsb') or r.get('dce_risr'), 'paebm': r.get('paebm_required'),
                                 'atencao': x.get('attention', 'Sem sinal'), 'pontos': x.get('score'), 'sinais': [s_['label'] for s_ in x.get('signals', []) if s_.get('code') != 'CONTEXTO_PORTE'][:4]})
                return self._json({'empresa': name, 'cnpj_root': root, 'barragens': dams,
                                   'minas': [{k: m[k] for k in ('id', 'processo', 'substancia', 'categoria_label', 'fase', 'uf', 'lat', 'lon', 'radiologico', 'area_ha')} for m in minas[:80]],
                                   'aviso': 'Exemplo com dados públicos da ANM (SIGBM e SIGMINE). A empresa não é cliente nem parceira da LexIA; nenhum dado interno ou sintético foi associado a ela.',
                                   'snapshot': OFFICIAL['manifest'] and OFFICIAL['manifest'].get('snapshot_id')})
            if route == '/api/contas-alvo':
                if (self._user() or {}).get('role') != 'curador':  # prospecção comercial: só a equipe LexIA
                    return self._json({'error': 'Área interna da equipe LexIA.'}, 403)
                from . import contas as _contas
                from .radar import RADAR as _R
                return self._json(_contas.match(_contas.load(), OFFICIAL['records'], _R.get('by_id', {}), (sigmine.latest() or {}).get('items', [])))
            if route == '/api/minas':
                from collections import Counter as _C
                sm = sigmine.latest()
                items = (sm or {}).get('items', [])
                f = [m for m in items if (not qs.get('cat') or m['categoria'] == qs['cat']) and (not qs.get('uf') or m['uf'] == qs['uf'])
                     and (qs.get('rad') != '1' or m['radiologico']) and (not qs.get('q') or qs['q'].lower() in (m['substancia'] + ' ' + m['titular'] + ' ' + m['processo']).lower())]
                lim = min(int(qs.get('limit', 2000)), 5000)
                return self._json({'total': len(items), 'filtered': len(f), 'items': f[:lim], 'manifest': sm and sm['manifest'],
                                   'by_cat': _C(m['categoria_label'] for m in items).most_common(), 'by_uf': _C(m['uf'] for m in f).most_common(10),
                                   'radiologico': sum(1 for m in items if m['radiologico']), 'subs_rad': _C(m['substancia'] for m in items if m['radiologico']).most_common(15),
                                   'regras': {'nuclear': 'Urânio e tório: monopólio da União (CF, art. 21, XXIII, e art. 177, V); licenciamento nuclear pela autoridade competente (CNEN/ANSN, Lei 14.222/2021).',
                                              'norm': 'Minerais com radioatividade natural associada (terras raras, monazita, zircônio, ilmenita, nióbio, columbita, tântalo, fosfato): avaliar proteção radiológica conforme norma CNEN NN 4.01. Sinal para avaliação, não conclusão.',
                                              'todas': 'Toda lavra: ANM (título, Relatório Anual de Lavra, CFEM), órgão ambiental (licença) e MTE (NR-22). Água mineral: também vigilância sanitária.'}})
            if route == '/api/denuncias/recebidas':
                u = self._user()
                if not u or u.get('kind') != 'empresa':
                    return self._json({'error': 'Área da empresa.'}, 401)
                root = str(u.get('cnpj') or '')[:8]
                cid = qs.get('empresa', '')
                if cid and cid in allowed_companies(u):  # perfil de empresa escolhido no topo (demonstração multissetorial)
                    root = (ativos_load()[1].get(cid) or {}).get('cnpj_root') or root
                return self._json({'items': denuncia.inbox(store, root), 'emails': mailer.list(root), 'ses': Mailer.configured()})
            if route == '/api/ai/eval':
                from . import ia_eval
                if not hasattr(self.server, '_eval_cache') or qs.get('refresh'):
                    self.server._eval_cache = ia_eval.run()
                return self._json(self.server._eval_cache)
            if route == '/api/ai/usage':
                from .cloud_aws import usage as _usage
                u = self._user()
                if not u:
                    return self._json({'error': 'Entre para ver o uso da IA.'}, 401)
                us = _usage()
                if u.get('role') != 'curador':  # uso por cliente é dado interno da LexIA: cada organização vê só a própria linha
                    mine = comp_org(u)
                    us = {**us, 'por_cliente': {k: v for k, v in us.get('por_cliente', {}).items() if k == mine}, 'interno': False}
                else:
                    us = {**us, 'interno': True}
                return self._json(us)
            if route == '/api/vault':
                vault_sync()
                return self._json(vault.status())
            if route == '/api/agent':
                ml_ready()
                last = agent.last_run()
                return self._json({'planner': 'ia' if planner else 'regras', 'tools': agent.TOOLS, 'runs': agent.runs(),
                                   'last': last and agent.run_detail(last['id']), 'pending': agent.actions('PENDENTE'),
                                   'decided': [a for a in agent.actions() if a['state'] != 'PENDENTE'][:20], 'running': agent.lock.locked()})
            # ------------------------------------------------ Radar de abandono / órfãs
            if route == '/api/radar/panorama':
                return self._json({**radar.RADAR['panorama'], 'sources': {
                    'sigbm': OFFICIAL['manifest'] and {k: OFFICIAL['manifest'].get(k) for k in ('snapshot_id', 'fetched_at', 'source_url', 'sha256')},
                    'snisb': radar.RADAR['snisb_manifest']}, 'law_url': abandono.LAW_URL, 'started_plans': store.plans_started()[:20]})
            if route == '/api/radar/list':
                ml_ready()
                f = ai_tools.empty_filters()
                for k in ('uf', 'attention', 'owner_kind', 'operational_status', 'signals'):
                    if qs.get(k):
                        f[k] = [v for v in qs[k].split(',') if v]
                f['dataset'] = qs.get('dataset', 'ambos')
                for k in ('dpa_high', 'population', 'emergency', 'small_owner', 'hidden_risk'):
                    if qs.get(k) == '1':
                        f[k] = True
                f['text'] = qs.get('q', '')[:80]
                res = ai_tools.apply_filters(radar.RADAR['items'], f)
                lim = min(int(qs.get('limit', 60)), 3000)
                return self._json({'total': len(res), 'items': [radar.light(x) for x in res[:lim]], 'filters': f,
                                   'levels': dict(Counter(x['attention'] for x in res))})
            if route == '/api/radar/item':
                ml_ready()
                x = radar.RADAR['by_id'].get(qs.get('id', ''))
                if not x:
                    return self._json({'error': 'Barragem não encontrada no radar.'}, 404)
                return self._json({**x, 'responsibles': abandono.responsibles(x), 'plan': abandono.plan(x, store.plan_progress(x['id'])),
                                   'drafts': store.drafts_for(x['id']), 'anomalies': [a for a in radar.RADAR['anomalies']['items'] if a['id'] == x['id']],
                                   'model_feedback': ml.feedback_list(dam_id=x['id'])[:10]})
            if route == '/api/radar/brief':
                ml_ready()
                x = radar.RADAR['by_id'].get(qs.get('id', ''))
                if not x:
                    return self._json({'error': 'Barragem não encontrada no radar.'}, 404)
                return self._json(ai_tools.dam_brief(x))
            if route == '/api/radar/drafts':
                u = self._user()
                if not u or u.get('kind') == 'cidadao':
                    return self._json({'error': 'Rascunhos são da área empresarial.'}, 401)
                out = []
                for d_ in store.drafts_for():
                    x = radar.RADAR['by_id'].get(d_['dam_id'], {})
                    out.append({**{k: v for k, v in d_.items() if k != 'body'}, 'dam_name': x.get('name'), 'uf': x.get('uf'), 'attention': x.get('attention')})
                return self._json({'items': out})
            if route == '/api/radar/draft-preview':
                x = radar.RADAR['by_id'].get(qs.get('id', ''))
                if not x:
                    return self._json({'error': 'Barragem não encontrada no radar.'}, 404)
                return self._json({'body': abandono.draft_representation(x, max(date.today(), AS_OF)), 'state': 'PRÉVIA — não salvo, não enviado'})
            if route == '/api/export/radar.csv':
                res = ai_tools.apply_filters(radar.RADAR['items'], {**ai_tools.empty_filters(), 'dataset': qs.get('dataset', 'ambos'),
                                             'attention': [v for v in qs.get('attention', '').split(',') if v], 'uf': [v for v in qs.get('uf', '').split(',') if v]})
                buf = io.StringIO()
                w = csv.writer(buf, delimiter=';')
                w.writerow(['id', 'base', 'nome', 'uf', 'municipio', 'atencao', 'pontos', 'sinais', 'consequencia', 'tipo_dono', 'situacao', 'dpa', 'regra', 'fonte'])
                for x in res:
                    lt = radar.light(x)
                    w.writerow([x['id'], 'SIGBM/ANM' if x['kind'] == 'mineracao' else 'SNISB/ANA (órfã)', lt['name'], lt['uf'], lt['municipio'], lt['attention'], lt['score'],
                                ' | '.join(sg['label'] for sg in x['signals']), ' | '.join(x['consequence']['items']), lt['owner_kind'], lt['status'] or '', lt['dpa'] or '',
                                abandono.RULE_VERSION, x.get('source_id')])
                return self._send(('﻿' + buf.getvalue()).encode('utf8'), 'text/csv; charset=utf-8',
                                  extra={'Content-Disposition': 'attachment; filename="torre360_radar_abandono.csv"'})
            if route == '/api/export/anomalias.csv':
                buf = io.StringIO()
                w = csv.writer(buf, delimiter=';')
                w.writerow(['id', 'nome', 'uf', 'municipio', 'codigo', 'inconsistencia', 'detalhe', 'metodo', 'base_legal'])
                for a in radar.RADAR['anomalies']['items']:
                    w.writerow([a['id'], a['name'], a['uf'], a['municipio'], a['code'], a['label'], a['detail'], a['method'], a.get('basis') or ''])
                return self._send(('﻿' + buf.getvalue()).encode('utf8'), 'text/csv; charset=utf-8',
                                  extra={'Content-Disposition': 'attachment; filename="torre360_inconsistencias_sigbm.csv"'})
            # ------------------------------------------------ IA (ferramentas)
            if route == '/api/ai/status':
                st = llm_status()
                gen = st['enabled']
                return self._json({'llm': st, 'capabilities': [
                    {'id': 'consulta', 'name': 'Consulta em português → filtros', 'engine': 'IA generativa (Claude) + verificador de vocabulário' if gen else 'Interpretador por regras (sem IA generativa)', 'kind': 'nlp'},
                    {'id': 'perguntas', 'name': 'Perguntas sobre normas com citação verificada', 'engine': 'IA generativa + verificador de citações' if gen else 'Respostas controladas pré-validadas', 'kind': 'rag'},
                    {'id': 'risco', 'name': 'Detector de risco oculto (aprendizado de máquina)', 'engine': f"Regressão logística treinada no SIGBM · AUC validada {(radar.RADAR['model'] or {}).get('metrics', {}).get('cv_auc', '—')}", 'kind': 'ml'},
                    {'id': 'anomalias', 'name': 'Inconsistências nos dados oficiais', 'engine': 'Estatística robusta (mediana/MAD) + regras de coerência', 'kind': 'stats'},
                    {'id': 'sinais', 'name': 'Sinais de abandono e nível de atenção', 'engine': f'Regras versionadas ({abandono.RULE_VERSION})', 'kind': 'rules'},
                    {'id': 'rascunhos', 'name': 'Rascunho de representação ao fiscalizador', 'engine': 'Modelo com campos da fonte; aprovação humana (quatro olhos)', 'kind': 'draft'},
                    {'id': 'entidades', 'name': 'Resolução de entidades (CNPJ/grupo)', 'engine': 'Similaridade de nomes + confirmação humana', 'kind': 'match'},
                ]})
            if route == '/api/ai/hidden-risk-legacy':
                M = radar.RADAR['model'] or {'available': False}
                if not M.get('available'):
                    return self._json({'available': False, 'reason': M.get('reason', 'Modelo indisponível.')})
                rows = []
                for i in M['flagged']:
                    x = radar.RADAR['by_id'].get(i)
                    if x:
                        rows.append({'id': i, 'name': x.get('name'), 'uf': x.get('uf'), 'municipio': x.get('municipio'), 'owner_kind': x['owner']['kind'],
                                     'status': x.get('operational_status'), 'attention': x['attention'], 'p': round(x['model']['p'], 3),
                                     'percentile': x['model']['percentile'], 'why': x['model']['why']})
                return self._json({k: v for k, v in M.items() if k not in ('by_id', 'flagged')} | {'items': rows,
                                  'reading': 'Pedido de conferência: perfil técnico declarado parecido com o de barragens em emergência. Não é diagnóstico de segurança.'})
            if route == '/api/ai/interpret':
                it = ai_tools.interpret(qs.get('q', '')[:300])
                return self._json({**it, 'chips_text': [ai_tools.chip_text(c) for c in it['chips']]})
            if route == '/api/ai/anomalies':
                a = radar.RADAR['anomalies']
                code = qs.get('code')
                items = [x for x in a['items'] if not code or x['code'] == code]
                return self._json({**a, 'items': items[:int(qs.get('limit', 200))], 'filtered_total': len(items)})
            if route == '/api/official/sigbm':
                m = OFFICIAL['manifest']
                if not m:
                    return self._json({'available': False, 'message': 'Nenhum snapshot SIGBM disponível. Peça a um curador para sincronizar.'})
                rows = []
                for rec in OFFICIAL['records']:
                    f = official_finding(rec, when)
                    ax = assess(f, reviews.get(f"anm:{rec['id']}"), P, when, extra=rec)
                    rows.append({k: rec.get(k) for k in ('id', 'official_id', 'name', 'owner_name', 'owner_cnpj', 'uf', 'municipio', 'lat', 'lon',
                                                         'cri', 'dpa', 'pnsb', 'operational_status', 'emergency_level', 'dam_type', 'main_ore')}
                                | {'applicability': ax['applicability_assessment'], 'priority': ax['priority']['level'], 'workflow': ax['workflow_state'],
                                   'next_action': ax['next_action']})
                q = {k: v for k, v in m['quality'].items() if k not in ('rejected_rows', 'duplicate_rows')}
                return self._json({'available': True, 'snapshot': {k: m.get(k) for k in ('snapshot_id', 'fetched_at', 'sha256', 'source_url', 'http_last_modified', 'bytes')},
                                   'age_days': snapshot_age_days(), 'quality': q, 'records': rows, 'origin': 'DADO_OFICIAL'})
            if route == '/api/official/sigbm/record':
                rec = OFFICIAL['by_id'].get(qs.get('id', ''))
                if not rec:
                    return self._json({'error': 'Registro oficial não encontrado.'}, 404)
                f = official_finding(rec, when)
                r = reviews.get(f"anm:{rec['id']}")
                schema = sigbm.load_schema()
                return self._json({'record': rec, 'labels': schema['field_labels'], 'categorical_note': schema['categorical_note'],
                                   'finding': f, 'axes': assess(f, r, P, when, extra=rec), 'explanation': explanation(f, P), 'review': r,
                                   'snapshot': {k: OFFICIAL['manifest'].get(k) for k in ('snapshot_id', 'fetched_at', 'sha256', 'source_url')},
                                   'organization': next((o for o in OFFICIAL['orgs'].values() if rec['id'] in o['asset_ids']), None) and
                                   {k: v for k, v in next(o for o in OFFICIAL['orgs'].values() if rec['id'] in o['asset_ids']).items() if k != 'asset_ids'}})
            if route == '/api/official/sigbm/quality':
                return self._json(OFFICIAL['manifest'] or {})
            if route == '/api/entities/search':
                return self._json({'query': qs.get('q', ''), 'results': entity_search(qs.get('q', ''), OFFICIAL['orgs']), 'links': store.entity_links(),
                                   'note': 'Correspondência cadastral/textual. Vínculo societário ou de grupo econômico exige confirmação humana.'})
            if route == '/api/connectors/status':
                m = OFFICIAL['manifest']
                out = []
                for c in load('connectors.json'):
                    out.append({**c, 'live': None})
                sig = {'id': 'ANM_SIGBM', 'name': 'ANM · SIGBM (barragens de mineração)', 'category': 'Fonte pública oficial', 'direction': 'entrada',
                       'protocol': 'HTTPS, coleta manual, snapshot imutável', 'status': 'REAL' if m else 'NAO_CONECTADO',
                       'contract': 'ID, nome, empreendedor, CNPJ, UF, município, coordenadas, CRI, DPA, PNSB, situação…',
                       'owner': 'Curadoria de dados', 'notes': 'Dados abertos da ANM. CRI/DPA são categorias oficiais, não prioridade.',
                       'source_ids': ['F09'], 'stage': 'fontes',
                       'live': m and {'snapshot_id': m['snapshot_id'], 'fetched_at': m['fetched_at'], 'age_days': snapshot_age_days(),
                                      'sha256': m['sha256'], 'accepted': m['quality']['accepted'], 'rejected': m['quality']['rejected'],
                                      'snapshots': OFFICIAL.get('snapshots', [])}}
                return self._json([sig] + out)
            if route == '/api/chain':
                fid = f"{qs.get('scenario')}:{qs.get('asset')}"
                f, asset = finding_by_id(fid, when)
                if not f:
                    return self._json({'error': 'Ativo ou cenário inválido.'}, 400)
                sc = next(x for x in load('scenarios.json') if x['id'] == f['scenario'])
                c = build_chain(asset, sc, load('provisions.json'), load('sources.json'), reviews.get(fid), when, finding=f)
                c['axes'] = assess(f, reviews.get(fid), P, when, extra=asset)
                c['explanation'] = explanation(f, P)
                c['origin'] = asset.get('origin')
                return self._json(c)
            if route == '/api/graph':
                return self._json(build_graph(load('assets.json'), load('scenarios.json'), load('provisions.json'), load('sources.json'), list(reviews.values()), when))
            if route == '/api/reviews':
                out = []
                for r in reviews.values():
                    f, asset = finding_by_id(r['id'], when)
                    out.append({**r, 'axes': assess(f, r, P, when, extra=asset) if f else None, 'asset_name': asset and asset.get('name'),
                                'origin': (asset or {}).get('origin', r.get('origin')),
                                'organization': (asset or {}).get('owner_name') or (asset or {}).get('organization'),
                                'uf': (asset or {}).get('uf') or _uf((asset or {}).get('region', '')),
                                'scenario_name': next((sc['name'] for sc in load('scenarios.json') if sc['id'] == r['scenario']), r['scenario']),
                                'headline_now': f and f['headline']})
                return self._json({'reviews': out, 'evidence_templates': EVIDENCE_TEMPLATES})
            if route == '/api/finance':
                return self._json(store.finance(qs.get('review_id')))
            if route == '/api/audit':
                return self._json(self._visible_audit(int(qs.get('limit', 200))))
            if route == '/api/audit/verify':
                return self._json(store.verify_chain())
            if route == '/api/ingestions':
                return self._json(store.ingestions())
            if route == '/api/outbox':
                return self._json(store.outbox())
            if route == '/api/events':
                u=self._user()
                return self._json(events_from_audit(store,u and u.get('id')))
            if route == '/api/export/decision-pack':
                fid = qs.get('finding', '')
                f, asset = finding_by_id(fid, when)
                if not f:
                    return self._json({'error': 'Achado não encontrado.'}, 404)
                r = reviews.get(fid)
                ax = assess(f, r, P, when, extra=asset)
                sc = next(x for x in load('scenarios.json') if x['id'] == f['scenario'])
                pids = list(ax['normative_lifecycle'].keys()) or sc['provisions']
                ctx = {'finding': f, 'axes': ax, 'asset': asset, 'review': r, 'scenario': sc, 'provisions': [P[p] for p in pids if p in P],
                       'sources': load('sources.json'), 'explanation': explanation(f, P), 'as_of': when.isoformat(),
                       'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(), 'chain': store.verify_chain(),
                       'snapshot': OFFICIAL['manifest'] if asset.get('origin') == 'DADO_OFICIAL' else None, 'finance': store.finance(fid)}
                store.audit('sistema:export', 'decision_pack.exported', fid, {'as_of': when.isoformat()})
                return self._send(decision_pack.render(ctx).encode('utf8'), 'text/html; charset=utf-8')
            if route == '/api/export/findings.csv':
                buf = io.StringIO()
                w = csv.writer(buf, delimiter=';')
                w.writerow(['finding_id', 'origin', 'asset_id', 'scenario', 'engine_state', 'applicability', 'workflow', 'priority', 'next_action', 'source_ids', 'provisions', 'missing', 'legal_deadline', 'rule_id', 'as_of'])
                for f in all_findings(when):
                    fid = f"{f['scenario']}:{f['asset_id']}"
                    ax = assess(f, reviews.get(fid), P, when)
                    w.writerow([fid, 'CENARIO_HIPOTETICO', f['asset_id'], f['scenario'], f['state'], ax['applicability_assessment'], ax['workflow_state'], ax['priority']['level'], ax['next_action'],
                                ' '.join(f['source_ids']), ' '.join(f['provisions']), ' | '.join(f['missing']), f['legal_deadline'] or '', f['rule_id'], f['as_of']])
                return self._send(('﻿' + buf.getvalue()).encode('utf8'), 'text/csv; charset=utf-8', extra={'Content-Disposition': 'attachment; filename="torre360_achados.csv"'})
            if route == '/api/export/audit.json':
                body = json.dumps({'chain': store.verify_chain(), 'entries': self._visible_audit(10000),'note':'Recorte autorizado; cadeia global verificada pelo servidor, não reconstruível apenas a partir deste recorte.'}, ensure_ascii=False, indent=2).encode('utf8')
                return self._send(body, 'application/json; charset=utf-8', extra={'Content-Disposition': 'attachment; filename="torre360_auditoria.json"'})
            if route.startswith('/api/'):
                return self._json({'error': 'Rota não encontrada.'}, 404)
            if route == '/favicon.ico':
                return self._send((FRONTEND / 'favicon.svg').read_bytes(), 'image/svg+xml')
            return super().do_GET()

        def _executive(self, when: date, P: dict, reviews: dict, org: str = 'demo') -> dict:
            o = orgs().get(org) or orgs()['demo']
            scen = set(o['scenarios'])
            scen_prov = {pid for sc in load('scenarios.json') if sc['id'] in scen for pid in sc['provisions']}
            snap = [p for p in snapshot(load('provisions.json'), when) if p['id'] in scen_prov]
            changes = [p for p in snap if p['status'] in ('EM_CONSULTA', 'FUTURA') or
                       (p['status'] == 'VIGENTE' and p.get('valid_from') and (when - date.fromisoformat(p['valid_from'])).days <= 365)]
            u = self._user()
            pf = portfolio(when, accounts.watchlist(u['id']) if u and u.get('id') else [], o['id'], reviews)
            ids = {a['id'] for a in pf}
            pending = [r for r in reviews.values() if r['asset_id'] in ids and r['state'] in ('DRAFT', 'REVIEW_PENDING')]
            horizon = when + timedelta(days=365)
            ms = [m for m in milestones(load('provisions.json')) if m['provision_id'] in scen_prov and when < date.fromisoformat(m['date']) <= horizon]
            affected = [a for a in pf if a['state'] in ACTIONABLE]
            triage = {st: sum(1 for a in pf if a['state'] == st) for st in STATE_ORDER}
            queue = sorted([a for a in pf if a['state'] in ACTIONABLE], key=lambda a: -a['priority']['score'])[:6]
            return {'as_of': when.isoformat(), 'org': o,
                    'metrics': [{'id': 'changes', 'label': 'Mudanças normativas para análise', 'value': len(changes),
                                 'definition': 'Dispositivos das normas desta organização em consulta, publicados sem efeito, ou que entraram em vigor nos últimos 12 meses.', 'items': [p['id'] for p in changes]},
                                {'id': 'pending', 'label': 'Avaliações pendentes', 'value': len(pending),
                                 'definition': 'Revisões abertas sem decisão humana para ativos desta organização.'},
                                {'id': 'milestones', 'label': 'Marcos nos próximos 12 meses', 'value': len(ms),
                                 'definition': 'Datas de publicação, início de efeito ou encerramento de consulta dos dispositivos monitorados.'},
                                {'id': 'affected', 'label': 'Ativos potencialmente afetados', 'value': len(affected) if pf else None,
                                 'definition': 'Ativos da organização com ao menos um achado acionável na data-base. Não é conclusão de aplicabilidade.'}],
                    'portfolio': pf, 'triage': triage, 'queue': queue, 'milestones': ms,
                    'official': {'records': len(OFFICIAL['records']), 'fetched_at': OFFICIAL['manifest'] and OFFICIAL['manifest']['fetched_at']}}

        def _insight(self, when: date, org: str = 'demo', reviews: dict | None = None) -> dict:
            o = orgs().get(org) or orgs()['demo']
            u = self._user()
            pf = portfolio(when, accounts.watchlist(u['id']) if u and u.get('id') else [], o['id'], reviews or {})
            scen_prov = {pid for sc in load('scenarios.json') if sc['id'] in o['scenarios'] for pid in sc['provisions']}
            evs = [m for m in milestones(load('provisions.json')) if m['provision_id'] in scen_prov and m['date'] > when.isoformat()]
            st = llm_status()
            if not evs:
                text = f"Nenhum marco futuro catalogado para as normas monitoradas de {o['short']} após a data-base."
                scen = None
            else:
                m = evs[0]
                scen = next(sc['id'] for sc in load('scenarios.json') if m['provision_id'] in sc['provisions'])
                n = sum(1 for a in pf if a['states'].get(scen) in ('FUTURE_REVIEW', 'REVIEW', 'INSUFFICIENT', 'MONITOR'))
                when_txt = date.fromisoformat(m['date']).strftime('%d/%m/%Y')
                if pf:
                    text = f"{m['document']} — {m['provision']}: {m['event'].lower()} em {when_txt}. Pode demandar revisão em {n} ativo(s) de {o['short']}. Veja o impacto e as ações recomendadas."
                else:
                    text = f"{m['document']} — {m['provision']}: {m['event'].lower()} em {when_txt}. {o['short']} não tem ativos conectados na LexIA; o impacto não pode ser calculado sem dados autorizados."
            return {'text': text, 'scenario': scen, 'org': o['id'], 'generated_by': 'IA + Regras' if st['enabled'] else 'Regras', 'llm': st['enabled'],
                    'note': 'Texto montado por regra determinística a partir da vigência catalogada e da carteira.' if not st['enabled'] else 'Redação assistida; números vêm das regras.'}

        def _auth_ok(self, token: str, user: dict, status: int = 200):
            body = json.dumps({'ok': True, 'user': user, 'permissions': demo_users()['permissions'].get(user['role'], [])}, ensure_ascii=False).encode('utf8')
            return self._send(body, 'application/json; charset=utf-8', status,
                              extra={'Set-Cookie': f'torre_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={8 * 3600}'})

        # ---------------------------------------------------------------- POST
        def do_POST(self):
            route = urlparse(self.path).path
            self._meter(route)
            if self._bloqueio(route):
                return
            size = int(self.headers.get('Content-Length', '0') or 0)
            limit = 7200000 if route == '/api/docs/upload' else 1600000 if route in ('/api/projects/screen','/api/workbench/save','/api/workbench/conditions/extract') else 262144
            if size <= 0 or size > limit:
                return self._json({'error': 'Corpo vazio ou grande demais.'}, 400)
            try:
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                return self._json({'error': 'JSON inválido.'}, 400)
            if not self._same_origin():
                return self._json({'error': 'Origem não permitida.'}, 403)
            try:
                when = parse_date(data.get('as_of'))
                if route.startswith('/api/workbench/'):
                    u=self._work_user()
                    if not u:return
                    if route=='/api/workbench/save':
                        if data.get('consent_save') is not True:raise ValueError('Confirme o armazenamento do resultado e trechos por conta.')
                        result=screen_project(data,load('provisions.json'),load('sources.json'),load('scenarios.json'),when)
                        if data.get('scope_confirmed') is not True:raise ValueError('Confirme o escopo antes de salvar.')
                        return self._json(workbench.save_project(u,str(data.get('title') or data.get('company') or 'Projeto'),result),201)
                    if route=='/api/workbench/compare':
                        a=workbench.project(u['id'],str(data.get('before','')));b=workbench.project(u['id'],str(data.get('after','')))
                        return self._json(compare_projects(a['result'],b['result']))
                    if route=='/api/workbench/link-review':
                        rid=str(data.get('review_id',''));review=next((r for r in self._work_reviews(u) if r['id']==rid),None)
                        if not review:raise WorkflowError('Revisão fora da carteira autorizada desta conta.')
                        return self._json(workbench.link_review(u,str(data.get('project_id','')),review,str(data.get('reason',''))))
                    if route=='/api/workbench/conditions/extract':
                        if data.get('consent_save') is not True:raise ValueError('Confirme o armazenamento de trechos de condicionantes.')
                        pid=str(data.get('project_id',''));workbench.project(u['id'],pid)
                        return self._json(workbench.save_conditions(u,pid,extract_conditions(data)),201)
                    if route=='/api/workbench/conditions/decide':
                        if u['role'] not in ('juridico','compliance','especialista'):return self._json({'error':'Revisão exige papel competente.'},403)
                        fields=data.get('fields') or {}
                        if not isinstance(fields,dict):raise ValueError('Campos de revisão inválidos.')
                        return self._json(workbench.decide_condition(u,str(data.get('batch_id','')),str(data.get('item_id','')),str(data.get('decision','')),str(data.get('reason','')),fields))
                    if route=='/api/workbench/seen':return self._json(workbench.mark_seen(u['id'],data.get('watermark'),self._work_summary(u)['watermark']))
                    if route in ('/api/workbench/reference','/api/workbench/revalidate'):
                        if 'review.transition' not in demo_users()['permissions'].get(u['role'],[]):return self._json({'error':'Papel sem permissão para revisão.'},403)
                        rid=str(data.get('review_id',''));current=self._work_reference(rid,when,u)
                        if route.endswith('/reference'):return self._json(workbench.set_baseline(u,rid,current))
                        return self._json(workbench.propose_revalidation(u,rid,current,str(data.get('reason',''))),201)
                    if route=='/api/workbench/revalidation/decide':
                        if u['role'] not in ('juridico','compliance','especialista'):return self._json({'error':'Reavaliação exige papel competente.'},403)
                        proposal=next((r for r in workbench.revalidations(u['id']) if r['id']==data.get('id')),None)
                        if not proposal:raise ValueError('Proposta não encontrada nesta conta.')
                        return self._json(workbench.decide_revalidation(u,proposal['id'],str(data.get('decision','')),str(data.get('reason','')),self._work_reference(proposal['review_id'],when,u)))
                    return self._json({'error':'Rota não encontrada.'},404)
                if route == '/api/projects/screen':
                    u = self._user()
                    if not u:
                        return self._json({'error': 'Entre com uma conta empresarial.'}, 401)
                    if u.get('kind') != 'empresa':
                        return self._json({'error': 'Triagem de projetos exige conta empresarial.'}, 403)
                    return self._json(screen_project(data, load('provisions.json'), load('sources.json'), load('scenarios.json'), when))
                if route == '/api/auth/register':
                    try:
                        accounts.register(data)
                    except WorkflowError as exc:
                        return self._json({'error': str(exc)}, 400)
                    token, user = accounts.login(data.get('email'), data.get('password'))
                    return self._auth_ok(token, user, 201)
                if route == '/api/auth/login':
                    try:
                        token, user = accounts.login(data.get('email'), data.get('password'), data.get('kind') or None)
                    except WorkflowError as exc:
                        return self._json({'error': str(exc)}, 401)
                    return self._auth_ok(token, user)
                if route == '/api/equipe/convidar':
                    u = self._user()
                    if not u or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta de empresa.'}, 401)
                    frente = str(data.get('empresa') or '') or None
                    if frente and frente not in allowed_companies(u):
                        return self._json({'error': 'Frente (empresa) fora do seu acesso.'}, 403)
                    inv = accounts.invite(u, str(data.get('nome', '')), str(data.get('email', '')), str(data.get('funcao', '')), str(data.get('cargo', '')),
                                          frente, data.get('modulos') if isinstance(data.get('modulos'), list) else None)
                    host = self.headers.get('Host') or 'localhost:8765'
                    link = f"http://{host}/#/convite?t={inv['token']}"
                    from .accounts import FUNCOES
                    corpo = (f"Olá, {inv['name']}.\n\n{u.get('name')} convidou você para a equipe de {u.get('org_name')} na LexIA, na função {FUNCOES.get(inv['function'], inv['function'])}.\n"
                             f"A função define quais alertas chegam até você e o que você pode aprovar.\n\nAceite o convite (válido por 7 dias): {link}\n")
                    mail = mailer.queue(inv['email'], str(u.get('cnpj') or '')[:8], f"[LexIA] Convite para a equipe de {u.get('org_name')}", corpo, f"convite#{inv['id']}")
                    return self._json({'id': inv['id'], 'email': inv['email'], 'link': link, 'estado_email': mail.get('state'), 'expira': inv['expires_at']}, 201)
                if route == '/api/equipe/importar':   # só lê e devolve a prévia; nada é cadastrado
                    u = self._user()
                    if not accounts.is_admin(u):
                        return self._json({'error': 'Só a gestão da empresa importa listas.'}, 403)
                    from . import equipe_import
                    try:
                        return self._json(equipe_import.ler(str(data.get('nome_arquivo', '')), data.get('conteudo'), data.get('texto')))
                    except Exception:
                        return self._json({'error': 'Não consegui ler este arquivo. Tente CSV ou Excel, ou cole a lista.'}, 400)
                if route == '/api/equipe/convidar-lote':
                    u = self._user()
                    if not u or not u.get('id') or not accounts.is_admin(u):
                        return self._json({'error': 'Só a gestão da empresa convida.'}, 403)
                    frente = str(data.get('empresa') or '') or None
                    if frente and frente not in allowed_companies(u):
                        return self._json({'error': 'Frente (empresa) fora do seu acesso.'}, 403)
                    mods = data.get('modulos') if isinstance(data.get('modulos'), list) else None
                    host = self.headers.get('Host') or 'localhost:8765'
                    ok_, erros = [], []
                    for row in (data.get('linhas') or [])[:500]:
                        try:
                            inv = accounts.invite(u, str(row.get('nome', '')), str(row.get('email', '')), str(row.get('funcao') or data.get('funcao') or 'operacao'),
                                                  str(row.get('cargo', '')), frente, mods)
                            link = f"http://{host}/#/convite?t={inv['token']}"
                            mailer.queue(inv['email'], str(u.get('cnpj') or '')[:8], f"[LexIA] Convite para a equipe de {u.get('org_name')}",
                                         f"Olá, {inv['name']}.\n\n{u.get('name')} deu a você acesso à LexIA ({u.get('org_name')}).\nCrie sua senha (válido por 7 dias): {link}\n", f"convite#{inv['id']}")
                            ok_.append({'email': inv['email'], 'nome': inv['name'], 'link': link})
                        except WorkflowError as exc:
                            erros.append({'email': row.get('email'), 'erro': str(exc)})
                    return self._json({'convidados': ok_, 'erros': erros}, 201)
                if route == '/api/equipe/acesso':
                    u = self._user()
                    if not u or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta de empresa.'}, 401)
                    return self._json(accounts.set_access(u, 'convite' if data.get('alvo') == 'convite' else 'pessoa', int(data.get('id', 0)), data.get('modulos') or []))
                if route == '/api/equipe/alterar':
                    u = self._user()
                    if not u or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta de empresa.'}, 401)
                    return self._json(accounts.change_member(u, int(data.get('id', 0)), data.get('funcao') or None, data.get('status') or None, str(data.get('motivo', ''))))
                if route == '/api/equipe/revogar-convite':
                    u = self._user()
                    if not u or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta de empresa.'}, 401)
                    accounts.revoke_invite(u, int(data.get('id', 0)))
                    return self._json({'ok': True})
                if route == '/api/convite/aceitar':
                    nu = accounts.accept_invite(str(data.get('t', '')), str(data.get('senha', '')), bool(data.get('consent')))
                    token, user = accounts.login(nu['email'], str(data.get('senha', '')), 'empresa')
                    return self._auth_ok(token, user)
                if route == '/api/account/profile':
                    u = self._user()
                    if not u or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta para editar o perfil.'}, 401)
                    nu = accounts.update_profile(u['id'], data)
                    store.audit(f"usuario:{u['id']}", 'perfil.atualizado', str(u['id']), {'campos': sorted(k for k in data if k != 'avatar') + (['foto'] if 'avatar' in data else [])})
                    return self._json({'user': nu})
                if route == '/api/auth/logout':
                    accounts.logout(self._cookie())
                    return self._send(b'{"ok": true}', 'application/json', extra={'Set-Cookie': 'torre_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'})
                if route == '/api/compliance/scan':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa' or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta empresarial.'}, 401)
                    return self._json(compliance_scan(u, accounts.watchlist(u['id'])))
                if route == '/api/compliance/transition':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa' or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta empresarial.'}, 401)
                    aid = str(data.get('id', ''))
                    orgs_ok = [comp_org(u), *allowed_companies(u)]
                    if not any(a['id'] == aid for o in orgs_ok for a in compliance_desk.list(o)):
                        return self._json({'error': 'Alerta fora da sua organização.'}, 403)
                    return self._json(compliance_desk.transition(aid, str(data.get('to', '')), u['name'], u.get('role', ''), str(data.get('note', '')), data.get('regularize_by') or None))
                if route == '/api/obrigacoes/extrair':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa':
                        return self._json({'error': 'Disponível para contas de empresa.'}, 401)
                    from . import extrator as _ex
                    from .cloud_aws import llm_call, llm_provider
                    gen = (lambda sy, us, sc: llm_call('extracao', sy, us, sc, max_tokens=1800)) if llm_status()['enabled'] else None
                    r = _ex.extrair(str(data.get('texto', '')), {'dispositivo': str(data.get('dispositivo', ''))[:160], 'norma': str(data.get('norma', ''))[:160]},
                                    llm=gen, forcar_ia=bool(data.get('ia')))
                    if 'error' in r:
                        return self._json(r, 400)
                    return self._json(r)
                if route == '/api/obrigacoes/decidir':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa':
                        return self._json({'error': 'Disponível para contas de empresa.'}, 401)
                    from . import extrator as _ex
                    return self._json(_ex.decidir(store, comp_org(u), data.get('item') or {}, data.get('fonte') or {}, str(data.get('decisao', '')),
                                                  f"humano:{u.get('name')}", str(data.get('motivo', ''))))
                if route == '/api/proximos':  # POST: a coordenada não aparece no log de acesso nem é gravada
                    from . import transparencia as _tp
                    from .radar import RADAR as _R
                    lat, lon = float(data.get('lat')), float(data.get('lon'))
                    if not (-34.5 <= lat <= 6 and -74.5 <= lon <= -28):
                        raise ValueError('Localização fora do Brasil.')
                    orgs = lexia_orgs()
                    priv = 'Sua localização foi usada só para esta busca e não foi gravada.'
                    if data.get('categoria'):
                        from .connectors import aneel_siga as _ag
                        r_ = _tp.proximos_categoria(lat, lon, str(data.get('categoria')), radar_items=_R.get('items', []), records_by_id=OFFICIAL['by_id'],
                                                    minas=(sigmine.latest() or {}).get('items', []), ativos_demo=ativos_geo(), snisb_setores=snisb.latest_setores(),
                                                    usinas=(_ag.latest() or {}).get('items', []), recebe=lambda r: r in orgs)
                        return self._json({**r_, 'privacidade': priv})
                    return self._json({'items': _tp.proximos(lat, lon, _R.get('items', []), OFFICIAL['by_id'], (sigmine.latest() or {}).get('items', []), ativos_geo(), lambda r: r in orgs),
                                       'privacidade': priv})
                if route == '/api/denuncia':
                    u = self._user()
                    codigo_novo = None
                    if u and u.get('id') and not data.get('anonimo'):
                        owner = f"usuario:{u['id']}"
                    else:   # denúncia anônima: sem conta; o dono é o hash do código de acompanhamento
                        import hashlib as _hl, secrets as _sc
                        cod = str(data.get('codigo') or '').strip().upper()
                        if not cod:
                            if data.get('action'):
                                return self._json({'error': 'Informe o código de acompanhamento.'}, 400)
                            if not _anon_ok(self.client_address[0]):
                                return self._json({'error': 'Muitas denúncias anônimas seguidas deste endereço. Tente mais tarde.'}, 429)
                            cod = codigo_novo = 'LX-' + '-'.join(_sc.token_hex(2).upper() for _ in range(3))
                        owner = 'anonimo:' + _hl.sha256(cod.encode()).hexdigest()
                        u = None
                    if data.get('action') == 'confirm':
                        d_ = denuncias.confirm(int(data.get('id', 0)), owner)
                        _, tgt = denuncia_target(d_.get('dam_id') or '')
                        sent = []
                        if tgt and tgt['org'] not in lexia_orgs():
                            tgt = {**tgt, 'fora_da_lexia': True}
                        if tgt and not tgt.get('fora_da_lexia'):
                            ident = bool(data.get('identificar')) and bool(u)
                            denuncia.route_to_company(store, d_['id'], tgt['org'], tgt['empresa'], tgt['ativo'], ident)
                            accounts.notify(f"org:{tgt['org']}", 'denuncia', f"Denúncia recebida sobre {tgt['ativo']}", 'Confirmada por quem denunciou. Veja em Compliance & Alertas → Denúncias recebidas.', '#/compliance', 'DENUNCIA')
                            subj, text = denuncia.company_email(d_, tgt['empresa'], tgt['ativo'], ident, u)
                            for rc in company_recipients(tgt['org']):
                                sent.append(mailer.queue(rc['email'], tgt['org'], subj, text, f"denuncia#{d_['id']}"))
                        return self._json({**d_, 'empresa_destino': tgt and {'empresa': tgt['empresa'], 'ativo': tgt['ativo'], 'emails': len(sent),
                                                                              'estado_emails': sorted({s['state'] for s in sent}), 'cadastrada_na_lexia': not tgt.get('fora_da_lexia')}})
                    if data.get('action') == 'forwarded':
                        return self._json(denuncias.forwarded(int(data.get('id', 0)), owner, str(data.get('protocol', ''))))
                    x, _tgt = denuncia_target(str(data.get('dam_id', '')))
                    ev = []
                    for d_id in ((data.get('evidence_ids') or []) if u else [])[:10]:
                        try:
                            meta, _ = tenant.read(u, int(d_id))
                            ev.append({'id': meta['id'], 'name': meta['name'], 'sha256': meta['sha256']})
                        except (WorkflowError, ValueError):
                            pass
                    from .cloud_aws import llm_call
                    llm = (lambda sysm, usr, sch: llm_call('denuncia', sysm, usr, sch, max_tokens=1500)) if llm_status()['enabled'] else None
                    redacao = (lambda sysm, usr, sch: llm_call('redacao', sysm, usr, sch, max_tokens=700)) if llm_status()['enabled'] else None
                    out = denuncia.build(str(data.get('relato', ''))[:4000], x, ev, max(date.today(), AS_OF), llm=llm, categoria=str(data.get('categoria') or '') or None, llm_redacao=redacao)
                    return self._json({**denuncias.save(owner, x['id'] if x else '', out, ev), 'analysis': {k: out[k] for k in ('normas', 'temas', 'gravidade', 'consequencias', 'destinatario', 'canais', 'engine', 'aviso_risco', 'setor', 'tipo', 'recusadas', 'lacuna', 'areas', 'resumo', 'dossie')},
                                       'alvo': x and {k: x.get(k) for k in ('id', 'name', 'municipio', 'uf', 'regulator', 'owner_label')},
                                       'vai_para_empresa': bool(_tgt and _tgt['org'] in lexia_orgs()), 'empresa': _tgt and _tgt['empresa'],
                                       'codigo_acompanhamento': codigo_novo}, 201)
                if route == '/api/repassar':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa':
                        return self._json({'error': 'Área da empresa.'}, 401)
                    from . import triagem as _tg
                    org_ = comp_org(u)
                    if str(data.get('empresa') or '') in allowed_companies(u):
                        org_ = ativos_load()[1][data['empresa']].get('cnpj_root') or org_
                    return self._json(_tg.repassar(store, accounts, u, org_, str(data.get('tipo', '')), str(data.get('ref', '')),
                                                   str(data.get('titulo', '')), str(data.get('para', '')), str(data.get('nota', ''))), 201)
                if route == '/api/sistemas/decidir':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa':
                        return self._json({'error': 'Área da empresa.'}, 401)
                    from . import sistemas as _si
                    return self._json(_si.decidir(store, comp_org(u), data.get('item') or {}, str(data.get('decisao', '')), str(data.get('motivo', '')), u['name']))
                if route == '/api/sistemas/sugerir':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa':
                        return self._json({'error': 'Área da empresa.'}, 401)
                    if not llm_status()['enabled']:
                        return self._json({'error': 'IA generativa desligada: use os detectores por regra.'}, 400)
                    from . import sistemas as _si
                    from .cloud_aws import llm_call
                    return self._json(_si.sugerir_ia(str(data.get('repo', '')), str(data.get('mudanca', '')), lambda sy, us, sc: llm_call('extracao', sy, us, sc, max_tokens=1500)))
                if route == '/api/denuncias/passo':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa':
                        return self._json({'error': 'Área da empresa.'}, 401)
                    root = str(u.get('cnpj') or '')[:8]
                    cid = str(data.get('empresa') or '')
                    if cid and cid in allowed_companies(u):
                        root = (ativos_load()[1].get(cid) or {}).get('cnpj_root') or root
                    return self._json(denuncia.marcar_passo(store, int(data.get('id', 0)), root, int(data.get('passo', -1)), bool(data.get('feito')), u['name']))
                if route == '/api/denuncias/responder':
                    u = self._user()
                    if not u or u.get('kind') != 'empresa' or u.get('role') not in ('compliance', 'juridico', 'gestor'):
                        return self._json({'error': 'Responder exige compliance, jurídico ou gestor da empresa.'}, 403)
                    return self._json(denuncia.respond(store, int(data.get('id', 0)), str(u.get('cnpj') or '')[:8], str(data.get('state', '')), str(data.get('resposta', '')), u['name']))
                if route == '/api/connectors/sigmine/sync':
                    u = self._require('connector.sync')
                    if not u:
                        return
                    try:
                        return self._json(sigmine.fetch())
                    except Exception as exc:
                        return self._json({'ok': False, 'error': f'Coleta SIGMINE falhou ({type(exc).__name__}).'}, 502)
                if route == '/api/docs/upload':
                    u = self._user()
                    if not u or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta.'}, 401)
                    return self._json(tenant.upload(u, str(data.get('name', '')), str(data.get('mime', '')), str(data.get('data', '')), str(data.get('kind', 'documento'))), 201)
                if route == '/api/docs/access':
                    u = self._user()
                    if not u or u.get('role') not in ('gestor', 'compliance', 'juridico') or u.get('kind') != 'empresa':
                        return self._json({'error': 'Revogar acesso exige gestor, compliance ou jurídico.'}, 403)
                    return self._json(tenant.set_access(u, str(data.get('user_id', '')), bool(data.get('revoke', True))))
                if route == '/api/agent/run':
                    u = self._require('agent.run')
                    if not u:
                        return
                    return self._json(agent_run(f"manual:{u['name']}"))
                if route == '/api/agent/decide':
                    u = self._require('agent.decide')
                    if not u:
                        return
                    a_ = agent.action(int(data.get('id', 0)))
                    if a_ and a_['kind'] == 'promover_modelo' and 'model.promote' not in demo_users()['permissions'].get(u['role'], []):
                        return self._json({'error': 'Promover modelo exige papel com permissão model.promote.'}, 403)
                    out = agent.decide(int(data.get('id', 0)), bool(data.get('approve')), u['name'], str(data.get('reason', '')),
                                       {'label_rejection': bool(data.get('label_rejection', True))})
                    ml_ready()
                    vault_sync()
                    return self._json(out)
                if route == '/api/ml/feedback':
                    u = self._require('model.feedback')
                    if not u:
                        return
                    if str(data.get('dam_id', '')) not in OFFICIAL['by_id']:
                        return self._json({'error': 'Barragem não encontrada.'}, 404)
                    return self._json(ml.add_feedback(str(data.get('target', '')), str(data.get('dam_id')), int(data.get('label', -1)), str(data.get('reason', '')), u['name']))
                if route == '/api/ml/train':
                    u = self._require('model.train')
                    if not u:
                        return
                    t = str(data.get('target', ''))
                    if t not in risk_model.TARGETS:
                        return self._json({'error': 'Modelo inexistente.'}, 400)
                    if ml.challenger(t):
                        return self._json({'error': 'Já existe um desafiante aguardando decisão.'}, 409)
                    c = ml_ctx()
                    return self._json(ml.train(t, c['records'], c['today'], c['sigbm_snapshot'], u['name'], l2=float(data.get('l2', 0.03))))
                if route in ('/api/ml/promote', '/api/ml/discard'):
                    u = self._require('model.promote')
                    if not u:
                        return
                    fn = ml.promote if route.endswith('promote') else ml.discard
                    out = fn(int(data.get('id', 0)), u['name'], str(data.get('reason', '')))
                    ml_ready()
                    vault_sync()
                    return self._json(out)
                if route == '/api/ai/quick':
                    q = str(data.get('q', ''))[:400]
                    from . import perspectiva as _pp
                    _u = self._user()
                    _qn = ai_tools.norm(q) if hasattr(ai_tools, 'norm') else q.lower()
                    _normativa = re.search(r'\bnr-?\s?\d|\bnorma|resolu|portaria|\blei\b|artigo|\bart\.|vigen|mudou|obrigac|\bprazo|\bcnen\b|\bansn\b|\baneel\b|\banp\b', _qn)                         and not re.search(r'quant|lista|mostr|quais barragens|barragens? (em|no|na|de|do|da|com|sem)\b', _qn)
                    out = {'kind': 'help'} if _normativa else ai_tools.quick(q, radar.RADAR['items'])
                    if out['kind'] == 'help' and len(q) > 12 and (_normativa or re.search(r'\?|norma|regra|prazo|resolu|portaria', q, re.I)):
                        a = _pp.aplicar(ask(q, _pp.perfil_padrao(_u, data.get('profile')), provs_setor(data.get('setor')), load('sources.json')), _u)
                        from .normas_setor import aviso_fora_do_setor
                        _av = aviso_fora_do_setor(q, data.get('setor'))
                        out = {'kind': 'ask', 'answer': (_av + ' ' if _av else '') + a['answer'], 'state': a['state'], 'sources': [sx['title'] for sx in a.get('sources', [])][:3],
                               'engine': a.get('mode'), 'chips': [], 'results': [], 'perspectiva': a.get('perspectiva')}
                    elif out.get('kind') == 'law':
                        out = _pp.aplicar(_pp.simplificar_lei({**out, 'state': 'LEI'}, _u), _u)
                    elif out.get('kind') == 'filter' and not out.get('results'):
                        # filtro vazio: tenta o nome do município citado (ex.: “tem barragem perigosa em Itabirito?”)
                        _its = [x for x in radar.RADAR['items'] if x.get('municipio') and len(x['municipio']) > 3 and re.search(r'(?<![a-z])' + re.escape(ai_tools.norm(x['municipio'])) + r'(?![a-z])', _qn)]
                        if _its:
                            _ord = {'Crítica': 0, 'Alta': 1, 'Moderada': 2, 'Baixa': 3, 'Sem sinal': 4}
                            _its.sort(key=lambda x: _ord.get(x.get('attention'), 9))
                            _ca = sum(1 for x in _its if x.get('attention') in ('Crítica', 'Alta'))
                            _m = f"{_its[0]['municipio']}/{_its[0].get('uf')}"
                            out = {**out, 'results': [radar.light(x) for x in _its[:6]], 'chips': [_m],
                                   'answer': (f"Em {_m} há {len(_its)} barragem(ns) no cadastro oficial. " + (f"{_ca} delas têm atenção crítica ou alta nos dados públicos — isso pede verificação, não quer dizer que vá romper." if _ca else 'Nenhuma está em atenção crítica ou alta nos dados públicos.')
                                              + ' Em risco imediato, ligue 199 (Defesa Civil).')}
                    return self._json(out)
                if route == '/api/radar/plan-step':
                    u = self._require('contingency.edit')
                    if not u:
                        return
                    x = radar.RADAR['by_id'].get(str(data.get('dam_id', '')))
                    if not x:
                        return self._json({'error': 'Barragem não encontrada no radar.'}, 404)
                    sid = str(data.get('step_id', ''))
                    if sid not in {st_[0] for st_ in abandono.STEP_LIB}:
                        return self._json({'error': 'Etapa inexistente.'}, 400)
                    store.set_plan_step(x['id'], sid, str(data.get('status', '')), u['name'], str(data.get('note', ''))[:500])
                    return self._json(abandono.plan(x, store.plan_progress(x['id'])))
                if route == '/api/radar/draft':
                    u = self._require('draft.create')
                    if not u:
                        return
                    x = radar.RADAR['by_id'].get(str(data.get('dam_id', '')))
                    if not x:
                        return self._json({'error': 'Barragem não encontrada no radar.'}, 404)
                    body = str(data.get('body') or abandono.draft_representation(x, max(date.today(), AS_OF)))[:12000]
                    return self._json(store.save_draft(x['id'], 'representacao', body, u['name']), 201)
                if route == '/api/radar/draft/decide':
                    u = self._require('draft.decide')
                    if not u:
                        return
                    out = store.decide_draft(int(data.get('id', 0)), str(data.get('decision', '')), u['name'], str(data.get('reason', '')))
                    vault_sync()
                    return self._json(out)
                if route == '/api/connectors/snisb/sync':
                    u = self._require('connector.sync')
                    if not u:
                        return
                    try:
                        m = snisb.fetch()
                    except Exception as exc:
                        return self._json({'ok': False, 'error': f'Coleta SNISB falhou ({type(exc).__name__}). Mantido o snapshot local.'}, 502)
                    radar.compute(OFFICIAL['records'], OFFICIAL['manifest'] and OFFICIAL['manifest']['snapshot_id'], max(date.today(), AS_OF))
                    radar.notify_changes(accounts)
                    store.audit(u['name'], 'connector.sync', 'ANA_SNISB', {'snapshot_id': m['snapshot_id'], 'orphans': m['orphans']['accepted']})
                    return self._json(m)
                if route == '/api/watchlist':
                    u = self._require('watch')
                    if not u:
                        return
                    if not u.get('id'):
                        return self._json({'error': 'Entre com uma conta para montar a carteira.'}, 400)
                    aid = str(data.get('asset_id', ''))
                    if aid not in OFFICIAL['by_id'] and aid not in radar.RADAR['by_id'] and aid not in {a['id'] for a in load('assets.json')}:
                        return self._json({'error': 'Ativo não encontrado.'}, 404)
                    return self._json({'items': accounts.watch(u['id'], aid, data.get('action', 'add') != 'remove')})
                if route == '/api/notifications/read':
                    u = self._user()
                    if not u or not u.get('id'):
                        return self._json({'error': 'Entre com uma conta.'}, 401)
                    accounts.mark_read(u['id'], [int(i) for i in data.get('ids', [])][:200])
                    return self._json({'ok': True})
                if route == '/api/monitor/run':
                    u = self._require('monitor.run')
                    if not u:
                        return
                    if not monitor:
                        return self._json({'error': 'Monitor desativado (TORRE_MONITOR=0).'}, 409)
                    if monitor.running:
                        return self._json({'status': 'JA_EM_EXECUCAO'}, 202)
                    threading.Thread(target=monitor.run_once, args=(OFFICIAL['manifest'],), daemon=True).start()
                    store.audit(f"humano:{u['name']}", 'monitor.run', 'source_monitor', {'targets': len(monitor.targets)})
                    return self._json({'status': 'INICIADO', 'targets': len(monitor.targets)}, 202)
                # ---- leitura/cálculo (sem efeitos colaterais): não exigem login ----
                if route == '/api/analyze':
                    a = next((x for x in load('assets.json') if x['id'] == data.get('asset_id')), None)
                    sid = data.get('scenario_id')
                    if a is None or sid not in SCENARIO_IDS:
                        return self._json({'error': 'Ativo ou cenário inválido.'}, 400)
                    override = data.get('facts_override')
                    if isinstance(override, dict):
                        a = {**a, 'facts': {**a.get('facts', {}), **override}}
                    return self._json(analyze(a, sid, when).payload())
                if route == '/api/ask':
                    q = str(data.get('question', ''))[:1500]
                    if not q.strip():
                        return self._json({'error': 'Pergunta vazia.'}, 400)
                    ctx = data.get('context') if isinstance(data.get('context'), dict) else {}
                    from . import perspectiva as _pp
                    _u = self._user()
                    res = ask(q, _pp.perfil_padrao(_u, data.get('profile')), provs_setor(data.get('setor')), load('sources.json'))
                    res = _pp.aplicar(res, _u)
                    res['setor_filtro'] = data.get('setor') or None
                    from .normas_setor import aviso_fora_do_setor
                    res['aviso_setor'] = aviso_fora_do_setor(q, data.get('setor'))
                    res['context'] = {k: str(v)[:120] for k, v in ctx.items()}
                    return self._json(res)
                if route == '/api/finance/evaluate':
                    return self._json(finance_evaluate(data.get('options', [])))
                # ---- mutações: exigem usuário de demonstração com permissão ----
                if route == '/api/reviews/open':
                    u = self._require('review.open')
                    if not u:
                        return
                    f, _ = finding_by_id(str(data.get('finding_id', '')), when)
                    if not f:
                        return self._json({'error': 'Achado não encontrado.'}, 404)
                    return self._json(store.open_review(f, u['name']))
                if route == '/api/reviews/assign':
                    u = self._require('review.transition')
                    if not u:
                        return
                    return self._json(store.assign(str(data.get('review_id')), str(data.get('function', '')), u['name']))
                if route == '/api/reviews/transition':
                    u = self._require('review.transition')
                    if not u:
                        return
                    if data.get('to_state') in ('CONFIRMED', 'REJECTED') and 'review.decide' not in demo_users()['permissions'][u['role']]:
                        return self._json({'error': 'Somente jurídico, compliance ou especialista podem confirmar ou rejeitar.'}, 403)
                    rid=str(data.get('review_id'))
                    result=store.transition(rid, str(data.get('to_state')), u['name'], u['role'],
                                            str(data.get('reason', '')), str(data.get('source_version', '')))
                    if data.get('to_state')=='CONFIRMED' and u.get('id') and rid in {r['id'] for r in self._work_reviews(u)}:
                        workbench.set_baseline(u,rid,self._work_reference(rid,when,u))
                    return self._json(result)
                if route == '/api/reviews/evidence':
                    u = self._require('evidence.add')
                    if not u:
                        return
                    return self._json(store.add_evidence(str(data.get('review_id')), str(data.get('item', '')), str(data.get('description', ''))[:2000], u['name']))
                if route == '/api/finance/save':
                    u = self._require('finance.save')
                    if not u:
                        return
                    result = finance_evaluate(data.get('options', []))
                    rid = data.get('review_id') or None
                    return self._json({**store.save_finance(rid, {'options': data.get('options', [])}, result, u['name']), 'result': result})
                if route == '/api/entities/link':
                    u = self._require('entity.confirm')
                    if not u:
                        return
                    if data.get('org_id') not in OFFICIAL['orgs']:
                        return self._json({'error': 'Organização não encontrada no registro.'}, 404)
                    return self._json(store.link_entity(data['org_id'], str(data.get('group_label', '')), str(data.get('decision', '')), str(data.get('reason', '')), u['name']))
                if route == '/api/ingest':
                    u = self._require('ingest')
                    if not u:
                        return
                    return self._json(store.save_ingestion(ingest_check(data)))
                if route == '/api/integrations/dispatch':
                    u = self._require('dispatch')
                    if not u:
                        return
                    rid = str(data.get('review_id'))
                    conn = str(data.get('connector'))
                    if conn not in {c['id'] for c in load('connectors.json') if 'saída' in c['direction'] or c['direction'] == 'bidirecional'}:
                        return self._json({'error': 'Conector de saída inválido.'}, 400)
                    r = store.review(rid)
                    payload = {'finding_id': rid, 'state': r['state'] if r else None, 'headline': r['headline'] if r else None,
                               'source_ids': r['source_ids'] if r else [], 'provisions': r['provisions'] if r else [],
                               'reviewer': r['assignee'] if r else None, 'evidence': [e['sha256'] for e in (r or {}).get('evidence', [])],
                               'legal_deadline': None, 'note': 'Payload simulado; nenhum envio externo.'}
                    return self._json(store.dispatch(conn, rid, payload, u['name']))
                if route == '/api/connectors/sigbm/sync':
                    u = self._require('connector.sync')
                    if not u:
                        return
                    try:
                        m = sigbm.fetch(snap_root=OFFICIAL['snap_root'])
                    except Exception as exc:  # rede, schema drift, tamanho
                        store.audit(f"humano:{u['name']}", 'connector.sync.failed', 'ANM_SIGBM', {'error': f'{type(exc).__name__}: {exc}'[:300]})
                        return self._json({'ok': False, 'error': f'Coleta falhou ({type(exc).__name__}: {str(exc)[:200]}). Mantido o snapshot local de {OFFICIAL["manifest"] and OFFICIAL["manifest"]["fetched_at"]}.'}, 502)
                    load_official()
                    radar.notify_changes(accounts)
                    store.audit(f"humano:{u['name']}", 'connector.synced', 'ANM_SIGBM', {'snapshot_id': m['snapshot_id'], 'sha256': m['sha256'], 'accepted': m['quality']['accepted']})
                    return self._json({'ok': True, 'snapshot_id': m['snapshot_id'], 'accepted': m['quality']['accepted'], 'rejected': m['quality']['rejected']})
                if route == '/api/admin/reset':
                    u = self._require('demo.reset')
                    if not u:
                        return
                    store.reset()
                    return self._json({'ok': True, 'seeded': seed(store), 'note': 'Estado DEMO reiniciado; fontes, snapshots e originais preservados.'})
            except WorkflowError as exc:
                return self._json({'error': str(exc)}, 409)
            except ValueError as exc:
                return self._json({'error': str(exc)}, 400)
            return self._json({'error': 'Rota não encontrada.'}, 404)

    return Handler


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--host', default='127.0.0.1', help='Use 0.0.0.0 apenas em rede confiável (ex.: abrir no celular).')
    p.add_argument('--db', default=os.environ.get('TORRE_DB', str(ROOT / 'var' / 'torre.db')))
    args = p.parse_args()
    store = Store(args.db)
    created = seed(store)
    load_official()
    accounts = Accounts(store)
    radar.notify_changes(accounts)
    monitor = None
    if os.environ.get('TORRE_MONITOR', '1') != '0':
        monitor = Monitor(accounts, load('sources.json'), load('provisions.json'), sigbm, lambda: (load_official(), radar.notify_changes(accounts), threading.Thread(target=lambda: make_handler.agent_run('novo_snapshot_sigbm'), daemon=True).start()))
        radar.notify_changes(accounts)
        monitor.start_background(float(os.environ.get('TORRE_MONITOR_MIN', '360')), lambda: OFFICIAL['manifest'])
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(store, accounts, monitor))
    if os.environ.get('TORRE_AGENT', '1') != '0':
        threading.Thread(target=lambda: make_handler.agent_run('inicio_servidor'), daemon=True).start()
    st = llm_status()
    m = OFFICIAL['manifest']
    print(f'LexIA v3 | http://localhost:{args.port}')
    print(f'Banco local: {args.db} | revisões criadas agora: {created} | IA: {st["mode"]}' + (' (chave lida do .env)' if 'ANTHROPIC_API_KEY' in ENV_LOADED else ''))
    print(f'SIGBM: {len(OFFICIAL["records"])} estruturas oficiais | snapshot {m and m["snapshot_id"]} | idade {snapshot_age_days()} dia(s)')
    print('Monitor de fontes: ' + (f'ativo, a cada {os.environ.get("TORRE_MONITOR_MIN", "360")} min ({len(monitor.targets)} fontes)' if monitor else 'desativado (TORRE_MONITOR=0)'))
    print('Contas de demonstração: senha LexIA2026demo (ex.: ana@demo.lexia.app, joana@demo.lexia.app)')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
