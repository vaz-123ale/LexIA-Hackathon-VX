"""Conector oficial ANA · SNISB (Sistema Nacional de Informações sobre Segurança de Barragens).

Serviço público ArcGIS REST da ANA: https://portal1.snirh.gov.br/server/rest/services/SRE/Barragens_SNISB/MapServer/0
Coleta dois recortes, com paginação educada e snapshot imutável:
1. orphans.json — barragens SEM empreendedor identificado (NM_EMPREENDEDOR nulo): as "órfãs" do cadastro.
   Não contém nome de pessoa.
2. mining.json — informações complementares das barragens de mineração fiscalizadas pela ANM
   (última inspeção, autuação, PAE, plano de segurança, fase de vida), indexadas pelo ID do SIGBM
   (campo BAR_CD_BAR_ENT_FISCALIZADORA). O nome do empreendedor NÃO é coletado.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SNAP_ROOT = ROOT / 'data' / 'snapshots' / 'snisb'
SERVICE = 'https://portal1.snirh.gov.br/server/rest/services/SRE/Barragens_SNISB/MapServer/0'
USER_AGENT = 'Torre360-monitor/0.4 (hackathon; coleta de dados abertos)'
ORPHAN_FIELDS = ['BAR_CD_SNISB', 'BAR_NM_NOME', 'ING_SG_UFMUNICIPIO', 'ING_NM_MUNICIPIO', 'BAR_NU_LATITUDE', 'BAR_NU_LONGITUDE', 'USO_PRINCIPAL',
                 'ORG_NM_ORGANIZACAO', 'FASE_DE_VIDA', 'CATEGORIA_RISCO', 'DANO_POTENCIAL', 'REGULADA_PELO_PNSB', 'POSSUI_PAE',
                 'POSSUI_PLANO_SEGURANCA', 'INS_DT_INSPECAO', 'BARRAGEM_AUTUADA', 'COMPLETUDE', 'BAR_NU_CAP_TOTAL_RESERV', 'BAR_NU_ALT_MAX_NIVEL_TERRENO']
MINING_FIELDS = ['BAR_CD_BAR_ENT_FISCALIZADORA', 'INS_DT_INSPECAO', 'TP_INSPECAO', 'POSSUI_PAE', 'POSSUI_PLANO_SEGURANCA', 'POSSUI_REVISAO_PERIODICA',
                 'BARRAGEM_AUTUADA', 'FASE_DE_VIDA', 'COMPLETUDE']


def _query(where: str, fields: list[str], offset: int, page: int, timeout: int) -> dict:
    qs = urllib.parse.urlencode({'where': where, 'outFields': ','.join(fields), 'returnGeometry': 'false', 'orderByFields': 'OBJECTID',
                                 'resultOffset': offset, 'resultRecordCount': page, 'f': 'json'})
    req = urllib.request.Request(f'{SERVICE}/query?{qs}', headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(30_000_000))


def _all(where: str, fields: list[str], page: int = 2000, timeout: int = 90, delay: float = 1.0, fetch=None) -> list[dict]:
    fetch = fetch or _query
    out, offset = [], 0
    while True:
        d = fetch(where, fields, offset, page, timeout)
        if 'error' in d:
            raise RuntimeError(f"SNISB respondeu erro: {d['error']}")
        feats = [f['attributes'] for f in d.get('features', [])]
        out.extend(feats)
        if not d.get('exceededTransferLimit') and len(feats) < page:
            break
        offset += len(feats)
        if not feats or offset > 200_000:
            break
        time.sleep(delay)
    return out


def _ms_to_date(v):
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc).date().isoformat() if isinstance(v, (int, float)) else None


def normalize_orphan(a: dict) -> dict | None:
    lat, lon = a.get('BAR_NU_LATITUDE'), a.get('BAR_NU_LONGITUDE')
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not (-34.8 <= lat <= 5.4 and -74.1 <= lon <= -28.6):
        return None
    clean = lambda v: None if v in (None, '', 'Não Classificado', 'Não Classificada', 'Não informado') else v
    return {'id': f"SNISB-{int(a['BAR_CD_SNISB'])}", 'snisb_id': int(a['BAR_CD_SNISB']), 'name': a.get('BAR_NM_NOME') or 'Sem nome cadastrado',
            'uf': a.get('ING_SG_UFMUNICIPIO'), 'municipio': a.get('ING_NM_MUNICIPIO'), 'lat': round(lat, 5), 'lon': round(lon, 5),
            'use': a.get('USO_PRINCIPAL'), 'regulator': a.get('ORG_NM_ORGANIZACAO'), 'phase': a.get('FASE_DE_VIDA'),
            'risk_category': clean(a.get('CATEGORIA_RISCO')), 'damage_potential': clean(a.get('DANO_POTENCIAL')),
            'pnsb': clean(a.get('REGULADA_PELO_PNSB')), 'has_pae': a.get('POSSUI_PAE'), 'has_safety_plan': a.get('POSSUI_PLANO_SEGURANCA'),
            'last_inspection': _ms_to_date(a.get('INS_DT_INSPECAO')), 'fined': a.get('BARRAGEM_AUTUADA'), 'completeness': a.get('COMPLETUDE'),
            'capacity_hm3': a.get('BAR_NU_CAP_TOTAL_RESERV'), 'height_m': a.get('BAR_NU_ALT_MAX_NIVEL_TERRENO'),
            'source_id': 'ANA_SNISB', 'origin': 'DADO_OFICIAL', 'owner': None}


def normalize_mining(a: dict) -> tuple[str, dict] | None:
    sid = (a.get('BAR_CD_BAR_ENT_FISCALIZADORA') or '').strip()
    if not sid.isdigit():
        return None
    return f'SIGBM-{sid}', {'last_inspection': _ms_to_date(a.get('INS_DT_INSPECAO')), 'inspection_type': a.get('TP_INSPECAO'),
                            'has_pae': a.get('POSSUI_PAE'), 'has_safety_plan': a.get('POSSUI_PLANO_SEGURANCA'),
                            'has_periodic_review': a.get('POSSUI_REVISAO_PERIODICA'), 'fined': a.get('BARRAGEM_AUTUADA'),
                            'phase': a.get('FASE_DE_VIDA'), 'completeness': a.get('COMPLETUDE')}


def fetch(snap_root: Path = SNAP_ROOT, fetch_fn=None) -> dict[str, Any]:
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    raw_orph = _all('NM_EMPREENDEDOR IS NULL', ORPHAN_FIELDS, fetch=fetch_fn)
    raw_min = _all("ORG_NM_ORGANIZACAO LIKE '%Minera%'", MINING_FIELDS, fetch=fetch_fn)
    orphans, rejected = [], 0
    for a in raw_orph:
        o = normalize_orphan(a)
        if o:
            orphans.append(o)
        else:
            rejected += 1
    mining = dict(filter(None, (normalize_mining(a) for a in raw_min)))
    sid = 'snisb-' + at.replace('-', '').replace(':', '')[:15]
    folder = snap_root / sid
    folder.mkdir(parents=True, exist_ok=True)
    body_o = json.dumps(orphans, ensure_ascii=False)
    body_m = json.dumps(mining, ensure_ascii=False)
    (folder / 'orphans.json').write_text(body_o, encoding='utf8')
    (folder / 'mining.json').write_text(body_m, encoding='utf8')
    manifest = {'snapshot_id': sid, 'connector': 'ANA_SNISB', 'fetched_at': at, 'service': SERVICE, 'user_agent': USER_AGENT,
                'orphans': {'raw': len(raw_orph), 'accepted': len(orphans), 'rejected_coordinates': rejected,
                            'sha256': hashlib.sha256(body_o.encode()).hexdigest(), 'filter': 'NM_EMPREENDEDOR IS NULL'},
                'mining': {'raw': len(raw_min), 'indexed': len(mining), 'sha256': hashlib.sha256(body_m.encode()).hexdigest(),
                           'filter': "ORG_NM_ORGANIZACAO LIKE '%Minera%'", 'join_key': 'BAR_CD_BAR_ENT_FISCALIZADORA = ID do SIGBM'},
                'privacy': 'Nome do empreendedor não coletado.'}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    return manifest


def latest(snap_root: Path = SNAP_ROOT) -> dict[str, Any] | None:
    if not snap_root.exists():
        return None
    folders = sorted([p for p in snap_root.iterdir() if (p / 'manifest.json').exists()], reverse=True)
    if not folders:
        return None
    f = folders[0]
    return {'manifest': json.loads((f / 'manifest.json').read_text(encoding='utf8')),
            'orphans': json.loads((f / 'orphans.json').read_text(encoding='utf8')),
            'mining': json.loads((f / 'mining.json').read_text(encoding='utf8'))}


# ---------------------------------------------------------------- recortes por setor (energia e abastecimento)
SETOR_SNAP = ROOT / 'data' / 'snapshots' / 'snisb_setores'
SETOR_WHERE = {'energia': "ORG_NM_ORGANIZACAO LIKE '%Energia El%'", 'abastecimento': "USO_PRINCIPAL = 'Abastecimento humano'"}
_PJ = re.compile(r'\b(LTDA|S\.?\s?A\.?|S/A|EIRELI|CIA|COMPANHIA|COOPERATIVA|PREFEITURA|MUNIC[IÍ]PIO|SERVI[CÇ]O AUT[OÔ]NOMO|SAAE|AUTARQUIA|DEPARTAMENTO|'
                 r'SECRETARIA|GOVERNO|ESTADO D|ENERGIA|ENERG[EÉ]TICA|EL[EÉ]TRICA|SANEAMENTO|[AÁ]GUAS?|CONS[OÓ]RCIO|FUNDA[CÇ][AÃ]O|AG[EÊ]NCIA|DNOCS|CODEVASF|COMPESA|SABESP|COPASA|EMBASA|CAGECE|SANEAGO|CEDAE|CASAN|SANEPAR|CORSAN)\b', re.I)


def owner_publico(nome: str | None) -> str:
    """Nome do empreendedor só quando é claramente pessoa jurídica ou órgão público; pessoa física não é exibida."""
    n = (nome or '').strip()
    if not n:
        return 'Sem empreendedor identificado'
    return n if _PJ.search(n) else 'Pessoa física ou não identificado (nome não exibido)'


def normalize_setor(a: dict) -> dict | None:
    o = normalize_orphan(a)
    if not o:
        return None
    o['owner'] = owner_publico(a.get('NM_EMPREENDEDOR'))
    o['has_periodic_review'] = a.get('POSSUI_REVISAO_PERIODICA')
    return o


def fetch_setores(snap_root: Path = SETOR_SNAP, fetch_fn=None) -> dict[str, Any]:
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sid = 'snisb-setores-' + at.replace('-', '').replace(':', '')[:15]
    folder = snap_root / sid
    folder.mkdir(parents=True, exist_ok=True)
    man = {'snapshot_id': sid, 'connector': 'ANA_SNISB_SETORES', 'fetched_at': at, 'service': SERVICE, 'user_agent': USER_AGENT, 'recortes': {},
           'privacy': 'Nome do empreendedor só quando pessoa jurídica/órgão público.'}
    for k, where in SETOR_WHERE.items():
        raw = _all(where, ORPHAN_FIELDS + ['NM_EMPREENDEDOR', 'POSSUI_REVISAO_PERIODICA'], fetch=fetch_fn)
        items = [x for x in (normalize_setor(a) for a in raw) if x]
        body = json.dumps(items, ensure_ascii=False)
        (folder / f'{k}.json').write_text(body, encoding='utf8')
        man['recortes'][k] = {'filter': where, 'raw': len(raw), 'accepted': len(items), 'sha256': hashlib.sha256(body.encode()).hexdigest()}
    (folder / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding='utf8')
    return man


def latest_setores(snap_root: Path = SETOR_SNAP) -> dict[str, Any] | None:
    if not snap_root.exists():
        return None
    fs = sorted([p for p in snap_root.iterdir() if (p / 'manifest.json').exists()], reverse=True)
    if not fs:
        return None
    f = fs[0]
    return {'manifest': json.loads((f / 'manifest.json').read_text(encoding='utf8')),
            **{k: json.loads((f / f'{k}.json').read_text(encoding='utf8')) for k in SETOR_WHERE if (f / f'{k}.json').exists()}}
