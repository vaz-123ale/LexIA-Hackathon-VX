"""Conector oficial ANEEL · SIGA (Sistema de Informações de Geração) — dados abertos.

- Fonte: arquivo CSV publicado em dadosabertos.aneel.gov.br (caminho /dataset/.../download/, permitido pelo robots.txt).
- O robots.txt da ANEEL PROÍBE /api/ e pede Crawl-Delay de 10 s: este conector não usa a API CKAN e espera 10 s antes de baixar.
- Guarda um subconjunto normalizado (não redistribui o CSV bruto), com SHA-256 do arquivo original no manifesto.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / 'data' / 'snapshots' / 'aneel_siga'
URL = ('https://dadosabertos.aneel.gov.br/dataset/6d90b77c-c5f5-4d81-bdec-7bc619494bb9/resource/'
       '11ec447d-698d-4ab8-977f-b424d5deee6a/download/siga-empreendimentos-geracao.csv')
UA = 'LexIA-monitor/0.5 (hackathon; coleta de dados abertos)'
RULE_VERSION = 'aneel-siga-v1'
TIPO = {'UHE': 'Usina hidrelétrica', 'PCH': 'Pequena central hidrelétrica', 'CGH': 'Central geradora hidrelétrica', 'UTE': 'Termelétrica',
        'EOL': 'Eólica', 'UFV': 'Solar fotovoltaica', 'UTN': 'Termonuclear'}


def _num(v):
    try:
        return float(str(v).replace('.', '').replace(',', '.')) if v not in (None, '') else None
    except ValueError:
        return None


def normalize(r: dict) -> dict | None:
    lat, lon = _num(r.get('NumCoordNEmpreendimento')), _num(r.get('NumCoordEEmpreendimento'))
    if lat is not None and not (-34.8 <= lat <= 5.4 and -74.1 <= (lon or 0) <= -28.6):
        lat = lon = None
    ceg = (r.get('CodCEG') or '').strip()
    if not ceg:
        return None
    return {'id': 'CEG-' + ceg, 'ceg': ceg, 'nome': (r.get('NomEmpreendimento') or '').strip(), 'uf': (r.get('SigUFPrincipal') or '').strip(),
            'tipo': (r.get('SigTipoGeracao') or '').strip(), 'tipo_rotulo': TIPO.get((r.get('SigTipoGeracao') or '').strip(), r.get('SigTipoGeracao')),
            'fase': (r.get('DscFaseUsina') or '').strip(), 'fonte': (r.get('DscFonteCombustivel') or '').strip(), 'outorga': (r.get('DscTipoOutorga') or '').strip(),
            'entrada_operacao': r.get('DatEntradaOperacao') or None, 'potencia_kw': _num(r.get('MdaPotenciaOutorgadaKw')),
            'inicio_vigencia': r.get('DatInicioVigencia') or None, 'fim_vigencia': r.get('DatFimVigencia') or None,
            'proprietarios': (r.get('DscPropriRegimePariticipacao') or '').strip()[:240], 'municipios': (r.get('DscMuninicpios') or '').strip()[:160],
            'lat': lat, 'lon': lon}


def parse(raw: bytes) -> tuple[list[dict], str | None]:
    text = raw.decode('utf-8-sig', errors='replace')
    rows = list(csv.DictReader(io.StringIO(text), delimiter=';'))
    out = [n for n in (normalize(r) for r in rows) if n]
    return out, (rows[0].get('DatGeracaoConjuntoDados') if rows else None)


def fetch(snap_root: Path = SNAP, download=None) -> dict:
    if download is None:
        time.sleep(10)  # Crawl-Delay do robots.txt da ANEEL
        req = urllib.request.Request(URL, headers={'User-Agent': UA})
        raw = urllib.request.urlopen(req, timeout=240).read()
    else:
        raw = download()
    items, gerado = parse(raw)
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sid = 'aneel-siga-' + at.replace('-', '').replace(':', '')[:15]
    folder = snap_root / sid
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'usinas.json').write_text(json.dumps(items, ensure_ascii=False), encoding='utf8')
    man = {'snapshot_id': sid, 'connector': 'ANEEL_SIGA', 'fetched_at': at, 'url': URL, 'dataset_generated_at': gerado, 'rows': len(items),
           'raw_sha256': hashlib.sha256(raw).hexdigest(), 'rule_version': RULE_VERSION,
           'robots': 'Disallow /api/ respeitado; Crawl-Delay 10 s respeitado; download pelo caminho /dataset/.../download/.'}
    (folder / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf8')
    return man


def latest(snap_root: Path = SNAP) -> dict | None:
    if not snap_root.exists():
        return None
    fs = sorted([p for p in snap_root.iterdir() if (p / 'manifest.json').exists()], reverse=True)
    if not fs:
        return None
    return {'manifest': json.loads((fs[0] / 'manifest.json').read_text(encoding='utf8')), 'items': json.loads((fs[0] / 'usinas.json').read_text(encoding='utf8'))}
