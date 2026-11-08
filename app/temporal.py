"""Vigência por DISPOSITIVO (não por norma inteira).

Estados: EM_CONSULTA, CONSULTA_ENCERRADA, VIGENTE, HISTORICA, FUTURA, REVOGADA, A_CONFERIR.
A_CONFERIR é usado quando a data de efeito não foi verificada no dossiê: o sistema
não presume vigência.
"""
from __future__ import annotations

from datetime import date
from typing import Any

LABELS = {
    'EM_CONSULTA': 'Em consulta',
    'CONSULTA_ENCERRADA': 'Consulta encerrada (sem ato final na base)',
    'VIGENTE': 'Vigente',
    'HISTORICA': 'Histórica',
    'FUTURA': 'Futura',
    'REVOGADA': 'Revogada',
    'A_CONFERIR': 'Data de efeito a conferir',
}


def _d(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


def status_at(p: dict[str, Any], when: date) -> str:
    if _d(p.get('revoked_at')) and _d(p['revoked_at']) <= when:
        return 'REVOGADA'
    if p.get('kind') == 'consulta':
        start, end = _d(p.get('consultation_from')), _d(p.get('consultation_to'))
        if start and when < start:
            return 'FUTURA'
        if end and when > end:
            return 'CONSULTA_ENCERRADA'
        return 'EM_CONSULTA'
    start, end = _d(p.get('effective_from')), _d(p.get('effective_to'))
    if end and when > end:
        return 'HISTORICA'
    if start is None:
        return 'A_CONFERIR'
    if when < start:
        return 'FUTURA'
    return 'VIGENTE'


def snapshot(provisions: list[dict[str, Any]], when: date) -> list[dict[str, Any]]:
    out = []
    for p in provisions:
        st = status_at(p, when)
        out.append({**p, 'status': st, 'status_label': LABELS[st], 'as_of': when.isoformat()})
    return out


def milestones(provisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Datas relevantes ordenadas, para a linha do tempo."""
    seen = []
    for p in provisions:
        for key, label in (('published_at', 'Publicação'), ('effective_from', 'Início de efeito'),
                           ('effective_to', 'Fim de efeito'), ('consultation_from', 'Abertura de consulta'),
                           ('consultation_to', 'Encerramento de consulta')):
            if p.get(key):
                seen.append({'date': p[key], 'event': label, 'provision_id': p['id'], 'provision': p['provision'], 'document': p['document']})
    return sorted(seen, key=lambda x: x['date'])
