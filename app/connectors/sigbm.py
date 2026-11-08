"""Conector oficial ANM SIGBM (Sistema Integrado de Gestão de Barragens de Mineração).

Fonte: https://dadosabertos.anm.gov.br/SIGBM/  (dados abertos da ANM)
- fetch() é opcional e manual (botão/endpoint com papel de curador); NUNCA roda a cada carregamento de página.
- Cada coleta gera um snapshot imutável: arquivo original + manifest (URL, horário, SHA-256, tamanho) +
  registros normalizados + relatório de qualidade.
- Sem internet: o servidor usa o snapshot local mais recente e informa a idade dele.
- O conector NÃO interpreta CRI/DPA como risco de rompimento ou prioridade; são categorias oficiais.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / 'data' / 'connectors' / 'sigbm_schema.json'
SNAP_ROOT = ROOT / 'data' / 'snapshots' / 'sigbm'
USER_AGENT = 'Torre360-demo/0.3 (hackathon; coleta manual de dados abertos)'
BR_BBOX = (-34.8, 5.4, -74.1, -28.6)  # lat_min, lat_max, lon_min, lon_max
MAX_BYTES = 50 * 1024 * 1024


class SchemaDriftError(ValueError):
    """Colunas obrigatórias ausentes: o arquivo mudou e o mapeamento precisa de revisão."""


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding='utf8'))


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s.replace('\xa0', ' '))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[–—]', '-', s)
    return re.sub(r'\s+', ' ', s).strip()


def norm_name(s: str) -> str:
    s = _norm(s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def parse_dms(value: str) -> float | None:
    """Converte 'sGG°MM'SS.SSS''' (formato do dicionário oficial) em graus decimais."""
    m = re.match(r"^\s*(-?)(\d{1,3})\s*°\s*(\d{1,2})\s*'\s*([\d.]+)\s*''\s*$", value or '')
    if not m:
        return None
    deg, mins, secs = int(m[2]), int(m[3]), float(m[4])
    if mins >= 60 or secs >= 60:
        return None
    v = deg + mins / 60 + secs / 3600
    return round(-v if m[1] else v, 6)


def decode(raw: bytes) -> tuple[str, str]:
    try:
        return raw.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        return raw.decode('cp1252', errors='replace'), 'cp1252'


def detect_delimiter(text: str) -> str:
    header = text.split('\n', 1)[0]
    return max([',', ';', '\t'], key=header.count)


def map_columns(header: list[str], schema: dict[str, Any]) -> tuple[dict[str, str], list[str], list[str]]:
    by_norm = {_norm(h): h for h in header}
    mapping, missing = {}, []
    for canon, aliases in schema['fields'].items():
        hit = next((by_norm[_norm(a)] for a in aliases if _norm(a) in by_norm), None)
        if hit:
            mapping[canon] = hit
        elif canon in schema['required']:
            missing.append(canon)
    used = set(mapping.values())
    extra = [h for h in header if h not in used]
    return mapping, missing, extra


def _clean(v: str | None) -> str | None:
    v = (v or '').strip()
    return None if v in ('', '-') else v


def parse(raw: bytes, snapshot_id: str = 'fixture', schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = schema or load_schema()
    text, encoding = decode(raw)
    delim = detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delim)
    header = reader.fieldnames or []
    mapping, missing, extra = map_columns(header, schema)
    if missing:
        raise SchemaDriftError('Colunas obrigatórias ausentes: ' + ', '.join(missing))
    records, rejected, seen, dups = [], [], set(), []
    missing_counts = {k: 0 for k in mapping}
    for line_no, row in enumerate(reader, start=2):
        get = lambda k: _clean(row.get(mapping[k])) if k in mapping else None
        oid = get('official_id')
        reasons = []
        lat, lon = parse_dms(get('lat_dms') or ''), parse_dms(get('lon_dms') or '')
        if not oid:
            reasons.append('ID ausente')
        if lat is None or lon is None:
            reasons.append('coordenada inválida na fonte (fora do formato sGG°MM\'SS.SSS\'\' ou minutos/segundos ≥ 60)')
        elif not (BR_BBOX[0] <= lat <= BR_BBOX[1] and BR_BBOX[2] <= lon <= BR_BBOX[3]):
            reasons.append('coordenada fora do território brasileiro')
        hemi = get('hemisphere')
        if lat is not None and hemi and ((hemi.startswith('Norte') and lat < 0) or (hemi.startswith('Sul') and lat > 0)):
            reasons.append('latitude incoerente com o hemisfério declarado')
        if reasons:
            rejected.append({'line': line_no, 'official_id': oid, 'reasons': reasons})
            continue
        if oid in seen:
            dups.append({'line': line_no, 'official_id': oid})
            continue
        seen.add(oid)
        doc = re.sub(r'\D', '', get('owner_doc') or '')
        if len(doc) == 14:
            doc_type, cnpj = 'CNPJ', doc
        elif doc:
            doc_type, cnpj = 'CPF_MASCARADO_OCULTO', None  # pessoa física: não exibimos nem indexamos
        else:
            doc_type, cnpj = 'NAO_INFORMADO', None
        rec = {'id': f'SIGBM-{oid}', 'official_id': oid, 'source_id': 'ANM_SIGBM', 'snapshot_id': snapshot_id,
               'is_synthetic': False, 'origin': 'DADO_OFICIAL', 'lat': lat, 'lon': lon,
               'owner_doc_type': doc_type, 'owner_cnpj': cnpj, 'owner_cnpj_root': cnpj[:8] if cnpj else None,
               # chave anônima para contar empreendedores distintos sem expor documento de pessoa física
               'owner_key': hashlib.sha256(('torre|' + (get('owner_doc') or '')).encode()).hexdigest()[:12] if get('owner_doc') else None}
        for k in mapping:
            if k in ('owner_doc', 'lat_dms', 'lon_dms', 'official_id'):
                continue
            rec[k] = get(k)
            if rec[k] is None:
                missing_counts[k] += 1
        if doc_type == 'CPF_MASCARADO_OCULTO':
            rec['owner_name'] = 'Pessoa física (nome não exibido)'
        rec['owner_name_norm'] = norm_name(rec.get('owner_name') or '')
        rec['data_quality'] = [f'{k} ausente' for k in ('pnsb', 'operational_status', 'cri', 'dpa') if rec.get(k) is None]
        records.append(rec)
    declared = schema.get('declared_metadata', {})
    quality = {
        'rows_read': len(records) + len(rejected) + len(dups), 'accepted': len(records), 'rejected': len(rejected),
        'duplicates': len(dups), 'rejected_rows': rejected[:200], 'duplicate_rows': dups[:200],
        'encoding_detected': encoding, 'delimiter_detected': delim, 'columns_total': len(header),
        'columns_mapped': len(mapping), 'columns_unmapped': len(extra),
        'metadata_divergence': [m for m in (
            f"delimitador declarado '{declared.get('delimiter')}' ≠ detectado '{delim}'" if declared.get('delimiter') and declared['delimiter'] != delim else None,
        ) if m],
        'missing_values': {k: v for k, v in missing_counts.items() if v},
        'personal_data': {'owner_docs_hidden_cpf': sum(1 for r in records if r['owner_doc_type'] == 'CPF_MASCARADO_OCULTO')},
        'schema_version': schema['schema_version'],
    }
    return {'records': records, 'quality': quality, 'mapping': mapping}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch_listing(timeout: int = 20) -> list[dict[str, str]]:
    schema = load_schema()
    req = urllib.request.Request(schema['listing_url'], headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        html = r.read(1_000_000).decode('utf-8', errors='replace')
    out = []
    for m in re.finditer(r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AP]M)\s+(\d+)\s+<A HREF="([^"]+)">([^<]+)</A>', html, re.I):
        out.append({'listed_at': m[1], 'bytes': m[2], 'href': m[3], 'name': m[4]})
    return out


def save_snapshot(raw: bytes, meta: dict[str, Any], snap_root: Path = SNAP_ROOT) -> dict[str, Any]:
    fetched = meta.get('fetched_at') or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sid = 'sigbm-' + re.sub(r'[^0-9T]', '', fetched)[:15]
    folder = snap_root / sid
    folder.mkdir(parents=True, exist_ok=True)
    parsed = parse(raw, sid)
    (folder / load_schema()['file_name']).write_bytes(raw)
    manifest = {'snapshot_id': sid, 'connector': 'ANM_SIGBM', 'fetched_at': fetched, 'sha256': sha256_bytes(raw),
                'bytes': len(raw), **{k: v for k, v in meta.items() if k != 'fetched_at'}, 'quality': parsed['quality'],
                'records_schema_version': load_schema()['schema_version']}
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    (folder / 'records.json').write_text(json.dumps(parsed['records'], ensure_ascii=False), encoding='utf8')
    return manifest


def fetch(timeout: int = 60, snap_root: Path = SNAP_ROOT) -> dict[str, Any]:
    """Coleta online (manual). Verifica a listagem antes de baixar; limita o tamanho."""
    schema = load_schema()
    listing = fetch_listing(timeout=min(timeout, 20))
    entry = next((x for x in listing if x['name'] == schema['file_name']), None)
    if not entry:
        raise RuntimeError('Arquivo Barragens.csv não está na listagem oficial; nada foi baixado.')
    url = schema['listing_url'].rstrip('/') + '/' + schema['file_name']
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(MAX_BYTES + 1)
        last_mod = r.headers.get('Last-Modified')
    if len(raw) > MAX_BYTES:
        raise RuntimeError('Arquivo maior que o limite configurado.')
    return save_snapshot(raw, {'source_url': url, 'listing_entry': entry, 'http_last_modified': last_mod, 'user_agent': USER_AGENT}, snap_root)


def latest(snap_root: Path = SNAP_ROOT) -> dict[str, Any] | None:
    if not snap_root.exists():
        return None
    folders = sorted([p for p in snap_root.iterdir() if (p / 'manifest.json').exists()], reverse=True)
    if not folders:
        return None
    f = folders[0]
    manifest = json.loads((f / 'manifest.json').read_text(encoding='utf8'))
    schema = load_schema()
    rec_path = f / 'records.json'
    if (f / 'Barragens.csv').exists() and manifest.get('records_schema_version') != schema['schema_version']:
        # O CSV bruto é imutável; records.json é derivado e é regenerado quando o esquema evolui.
        parsed = parse((f / 'Barragens.csv').read_bytes(), manifest['snapshot_id'], schema)
        rec_path.write_text(json.dumps(parsed['records'], ensure_ascii=False), encoding='utf8')
        manifest['records_schema_version'] = schema['schema_version']
        manifest['quality'] = parsed['quality']
        (f / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    records = json.loads(rec_path.read_text(encoding='utf8'))
    return {'manifest': manifest, 'records': records, 'snapshots': [p.name for p in folders]}
