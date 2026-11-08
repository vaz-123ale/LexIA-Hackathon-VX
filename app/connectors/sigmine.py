"""Conector oficial ANM · SIGMINE — processos minerários (minas em operação), além das barragens.

Serviço público ArcGIS da ANM: https://geo.anm.gov.br/arcgis/rest/services/SIGMINE/dados_anm/MapServer/0
- Fases coletadas: CONCESSÃO DE LAVRA e LAVRA GARIMPEIRA (títulos que permitem extrair).
- Guarda só o centro aproximado da área (não o polígono), substância, uso, fase, área, UF e último evento.
- Nome do titular só quando é claramente pessoa jurídica (LTDA, S.A., EIRELI, COOPERATIVA, MINERAÇÃO…); pessoa física não é exibida.
- O servidor da ANM entrega a cadeia de certificados incompleta para o Python; a coleta usa o curl do sistema (que completa
  a cadeia pelo repositório do Windows) — a verificação de certificado NUNCA é desligada.

Classificação (regra sigmine-v1): tipo de mineração e alerta radiológico:
- nuclear (urânio, tório): monopólio da União (CF, art. 21, XXIII, e art. 177, V); regulação nuclear (CNEN/ANSN).
- radioatividade natural associada (terras raras, monazita, zircônio, ilmenita, nióbio, columbita, tântalo, fosfato…):
  avaliar proteção radiológica de instalação mínero-industrial (norma CNEN NN 4.01) — sinal para avaliação, não conclusão.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / 'data' / 'snapshots' / 'sigmine'
SERVICE = 'https://geo.anm.gov.br/arcgis/rest/services/SIGMINE/dados_anm/MapServer/0'
UA = 'LexIA-monitor/0.5 (hackathon; coleta de dados abertos)'
FIELDS = ['PROCESSO', 'FASE', 'NOME', 'SUBS', 'USO', 'AREA_HA', 'UF', 'ULT_EVENTO']
WHERE = "(FASE LIKE 'CONCESS%' AND FASE LIKE '%LAVRA') OR FASE = 'LAVRA GARIMPEIRA'"
RULE_VERSION = 'sigmine-v1'

CATEGORIES = [
    ('nuclear', 'Nuclear', r'UR[AÂ]NIO|T[OÓ]RIO'),
    ('norm', 'Radioatividade natural associada', r'TERRAS RARAS|MONAZ|ZIRC|ILMENITA|NI[OÓ]BIO|COLUMBITA|T[AÂ]NTALO|FOSFATO|XENOT|PIROCLORO'),
    ('agua', 'Água mineral', r'[AÁ]GUA MINERAL|[AÁ]GUA POT[AÁ]VEL'),
    ('energetico', 'Energético (carvão, turfa)', r'CARV[AÃ]O|TURFA|LINHITO|FOLHELHO BETUMINOSO'),
    ('metalico', 'Metálico', r'FERRO|OURO|COBRE|MANGAN|BAUXITA|ALUM[IÍ]NIO|ESTANHO|CASSITERITA|N[IÍ]QUEL|ZINCO|CHUMBO|CROM|VAN[AÁ]DIO|L[IÍ]TIO|TUNGST|PRATA|COBALTO|MOLIBD|TITÂNIO|TIT[AÂ]NIO|HEMATITA|ITABIRITO'),
    ('gemas', 'Gemas e diamante', r'DIAMANTE|ESMERALDA|TURMALINA|[AÁ]GUA MARINHA|AMETISTA|GEMA|OPALA|TOPÁZIO|TOP[AÁ]ZIO'),
    ('construcao', 'Construção civil', r'AREIA|CASCALHO|ARGILA|BRITA|GRANITO|BASALTO|SAIBRO|GNAISSE|QUARTZITO|M[AÁ]RMORE|DIAB[AÁ]SIO|ARENITO|ROCHA|PEDRA|SIENITO|CALC[AÁ]RIO|DOLOMITO|ARD[OÓ]SIA|SERPENTINITO'),
    ('industrial', 'Mineral industrial', r'CAULIM|GIPSITA|FELDSPATO|FLUORITA|POT[AÁ]SSIO|SAL|TALCO|MAGNESITA|BARITA|GRAFITA|VERMICULITA|QUARTZO|MICA|DIATOMITO|BENTONITA'),
]
COMPANY = re.compile(r'\b(LTDA|S\.?/?A\.?|EIRELI|COOPERATIVA|MINERA[CÇ][AÃ]O|MINERADORA|MINERAIS|EMPRESA|IND[UÚ]STRIA|COMPANHIA|CIA\.?|EPP|ME)\b', re.I)


def category(subs: str) -> tuple[str, str]:
    s = (subs or '').upper()
    for key, label, pat in CATEGORIES:
        if re.search(pat, s):
            return key, label
    return 'outros', 'Outros'


def _curl_json(url: str, timeout: int = 120) -> dict:
    out = subprocess.run(['curl', '-s', '-m', str(timeout), '-A', UA, url], capture_output=True, timeout=timeout + 10)
    if out.returncode != 0:
        raise RuntimeError(f'curl falhou ({out.returncode})')
    return json.loads(out.stdout.decode('utf8'))


def _centroid(geom: dict) -> tuple[float, float] | None:
    rings = (geom or {}).get('rings') or []
    pts = [p for r in rings for p in r]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return round((min(ys) + max(ys)) / 2, 5), round((min(xs) + max(xs)) / 2, 5)


def normalize(attrs: dict, geom: dict | None) -> dict | None:
    c = _centroid(geom)
    if not c:
        return None
    lat, lon = c
    if not (-34.8 <= lat <= 5.4 and -74.1 <= lon <= -28.6):
        return None
    key, label = category(attrs.get('SUBS'))
    nome = (attrs.get('NOME') or '').strip()
    return {'id': f"ANM-{(attrs.get('PROCESSO') or '').replace('/', '-')}", 'processo': attrs.get('PROCESSO'), 'fase': (attrs.get('FASE') or '').strip(),
            'substancia': (attrs.get('SUBS') or '').strip(), 'uso': (attrs.get('USO') or '').strip(), 'area_ha': attrs.get('AREA_HA'),
            'uf': (attrs.get('UF') or '').strip(), 'ultimo_evento': (attrs.get('ULT_EVENTO') or '').strip()[:160],
            'titular': nome if COMPANY.search(nome) else 'Pessoa física ou não identificado (nome não exibido)',
            'categoria': key, 'categoria_label': label, 'radiologico': key in ('nuclear', 'norm'), 'lat': lat, 'lon': lon}


def fetch(snap_root: Path = SNAP, page: int = 2000, delay: float = 2.0, fetch_json=None) -> dict:
    fetch_json = fetch_json or _curl_json
    out, offset, raw = [], 0, 0
    while True:
        qs = urllib.parse.urlencode({'where': WHERE, 'outFields': ','.join(FIELDS), 'returnGeometry': 'true', 'outSR': 4326,
                                     'maxAllowableOffset': 0.01, 'geometryPrecision': 4, 'orderByFields': 'OBJECTID',
                                     'resultOffset': offset, 'resultRecordCount': page, 'f': 'json'})
        d = fetch_json(f'{SERVICE}/query?{qs}')
        if 'error' in d:
            raise RuntimeError(f"SIGMINE respondeu erro: {d['error']}")
        feats = d.get('features', [])
        raw += len(feats)
        for f in feats:
            n = normalize(f.get('attributes', {}), f.get('geometry'))
            if n:
                out.append(n)
        if not feats or (not d.get('exceededTransferLimit') and len(feats) < page) or offset > 100000:
            break
        offset += len(feats)
        time.sleep(delay)
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sid = 'sigmine-' + at.replace('-', '').replace(':', '')[:15]
    folder = snap_root / sid
    folder.mkdir(parents=True, exist_ok=True)
    body = json.dumps(out, ensure_ascii=False)
    (folder / 'minas.json').write_text(body, encoding='utf8')
    man = {'snapshot_id': sid, 'connector': 'ANM_SIGMINE', 'fetched_at': at, 'service': SERVICE, 'where': WHERE, 'raw': raw, 'accepted': len(out),
           'sha256': hashlib.sha256(body.encode()).hexdigest(), 'rule_version': RULE_VERSION,
           'privacy': 'Nome do titular só quando pessoa jurídica; polígono não armazenado (só o centro aproximado).'}
    (folder / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf8')
    return man


def latest(snap_root: Path = SNAP) -> dict | None:
    if not snap_root.exists():
        return None
    folders = sorted([p for p in snap_root.iterdir() if (p / 'manifest.json').exists()], reverse=True)
    if not folders:
        return None
    f = folders[0]
    return {'manifest': json.loads((f / 'manifest.json').read_text(encoding='utf8')), 'items': json.loads((f / 'minas.json').read_text(encoding='utf8'))}
