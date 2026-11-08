"""Diff determinístico entre versões de dispositivos (metadados e resumo curado).

O texto integral das normas NÃO está armazenado (sem snapshot do documento); por isso o diff
compara campos estruturados e o resumo do dossiê, e diz isso explicitamente.
Classes: adicionado | alterado | removido | vigência alterada | exceção alterada.
"""
from __future__ import annotations

from typing import Any

FIELDS = [('version', 'Versão'), ('provision', 'Dispositivo'), ('valid_from', 'Início de vigência'), ('valid_to', 'Fim de vigência'),
          ('exceptions', 'Exceções'), ('conditions', 'Condições modeladas'), ('summary', 'Resumo curado'), ('sources', 'Fontes')]

PAIRS = {
    'eir': [('ANM95-art21', 'ANM-EIR-PRORROG-2026')],
    'nr20': [('NR20-AIII-2.1.1@2024', 'NR20-AIII-2.1.1@2025')],
    'anm': [(None, 'ANM245-art1'), (None, 'ANM220-arts76-77'), (None, 'ANM220-geral'), (None, 'ANM220-art7-p1')],
    'anp_cp21': [(None, 'ANP-CP21-2026')],
    'ansn': [(None, 'ANSN-RES1-2025')],
}


def diff(before: dict[str, Any] | None, after: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for key, label in FIELDS:
        a, b = (before or {}).get(key), after.get(key)
        if a == b:
            continue
        if before is not None and key in ('valid_from', 'valid_to'):
            kind = 'vigência alterada'
        elif before is None or a in (None, [], ''):
            kind = 'adicionado'
        elif b in (None, [], ''):
            kind = 'removido'
        elif key == 'exceptions':
            kind = 'exceção alterada'
        else:
            kind = 'alterado'
        changes.append({'field': key, 'label': label, 'before': a, 'after': b, 'type': kind})
    return changes


def scenario_diffs(scenario_id: str, provisions: dict[str, dict]) -> list[dict[str, Any]]:
    out = []
    for b, a in PAIRS.get(scenario_id, []):
        before, after = provisions.get(b) if b else None, provisions[a]
        out.append({'before_id': b, 'after_id': a, 'before': before, 'after': after, 'changes': diff(before, after),
                    'basis': 'Comparação de metadados e resumo curado; texto integral não armazenado.',
                    'origin': 'REGRA (determinístico)', 'ai_proposal': None})
    return out
