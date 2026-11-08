"""Estado em memória do Radar de abandono (SIGBM + SNISB) e notificações de mudança.

Recalculado quando um snapshot novo do SIGBM ou do SNISB é carregado. As notificações
avisam quando barragens ENTRAM no nível Crítica entre dois cálculos (por snapshot).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import abandono as A
from .ai_tools import anomalies
from . import risk_model
from .connectors import snisb

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / 'var' / 'radar_state.json'
RADAR: dict = {'items': [], 'by_id': {}, 'panorama': None, 'anomalies': None, 'snisb_manifest': None, 'sigbm_snapshot': None, 'model': None}
_MODEL_CACHE: dict = {}


def compute(records: list[dict], sigbm_snapshot: str | None, today: date, snisb_root: Path | None = None) -> dict:
    sn = snisb.latest(snisb_root or snisb.SNAP_ROOT) or {'manifest': None, 'orphans': [], 'mining': {}}
    mining = A.assess_mining(records, sn['mining'], today)
    orphans = A.assess_orphans(sn['orphans'], today)
    key = (sigbm_snapshot, len(records))
    if key not in _MODEL_CACHE:  # treino leva alguns segundos: uma vez por snapshot
        _MODEL_CACHE.clear()
        _MODEL_CACHE[key] = risk_model.run(records, today)
    model = _MODEL_CACHE[key]
    for x in mining:
        x['model'] = model.get('by_id', {}).get(x['id']) if model.get('available') else None
    items = mining + orphans
    RADAR.update(items=items, by_id={x['id']: x for x in items}, panorama=A.panorama(mining, orphans),
                 model=model, anomalies=anomalies(records, today), snisb_manifest=sn['manifest'], sigbm_snapshot=sigbm_snapshot, today=today.isoformat())
    return RADAR


def light(x: dict) -> dict:
    return {'id': x['id'], 'kind': x['kind'], 'name': x.get('name'), 'uf': x.get('uf'), 'municipio': x.get('municipio'), 'lat': x.get('lat'), 'lon': x.get('lon'),
            'attention': x['attention'], 'score': x['score'], 'signals': [s['label'] for s in x['signals'] if s['code'] != 'CONTEXTO_PORTE'][:4],
            'n_signals': len(x['signals']), 'owner_kind': x['owner']['kind'] if x['kind'] == 'mineracao' else 'Sem empreendedor',
            'status': x.get('operational_status') or x.get('phase'), 'dpa': x.get('dpa') or x.get('damage_potential'),
            'consequence': x['consequence']['items'][:2], 'hidden_risk': bool(x.get('model') and x['model'].get('hidden_risk')), 'use': x.get('use'), 'regulator': x.get('regulator') or (x.get('managing_unit') and f"ANM · {x['managing_unit']}")}


def notify_changes(accounts, state_file: Path = STATE_FILE) -> list[str]:
    """Compara o conjunto de críticas com o último cálculo e publica notificação (uma por mudança de snapshot)."""
    if accounts is None:
        return []
    crit = sorted(x['id'] for x in RADAR['items'] if x['attention'] == 'Crítica')
    key = f"{RADAR.get('sigbm_snapshot')}|{(RADAR.get('snisb_manifest') or {}).get('snapshot_id')}"
    prev = {}
    if state_file.exists():
        try:
            prev = json.loads(state_file.read_text(encoding='utf8'))
        except ValueError:
            prev = {}
    if prev.get('key') == key:
        return []
    new = [i for i in crit if i not in set(prev.get('critical', []))]
    if prev.get('key') is None:
        p = RADAR['panorama']
        accounts.notify('todos', 'radar', f"Radar de abandono: {p['mining']['levels'].get('Crítica', 0)} barragens de mineração e "
                        f"{p['orphans']['levels'].get('Crítica', 0)} órfãs em atenção crítica",
                        'Sinais calculados a partir dos dados declarados no SIGBM/ANM e no SNISB/ANA. Sinal não é conclusão.', '#/radar', 'RADAR')
    elif new:
        names = ', '.join((RADAR['by_id'][i].get('name') or i) for i in new[:3])
        accounts.notify('todos', 'radar', f'{len(new)} barragem(ns) entraram em atenção crítica', f'Ex.: {names}. Confira os sinais e o plano de contingência.',
                        f'#/radar?id={new[0]}', 'RADAR')
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({'key': key, 'critical': crit}), encoding='utf8')
    return new
