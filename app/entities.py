"""organization_registry + asset_registry e correspondência de entidades.

Regras:
- Vínculo por CNPJ idêntico = correspondência CADASTRAL (alta), ainda assim "a confirmar" para grupo econômico.
- Mesma raiz de CNPJ (8 dígitos) = mesma pessoa jurídica, outro estabelecimento.
- Nome parecido = correspondência TEXTUAL apenas. Nunca vira vínculo automático
  (ex.: "Vale" no nome NÃO prova relação com a Vale S.A.).
- entity_match_confidence mede o vínculo cadastral, não certeza jurídica nem grupo econômico.
"""
from __future__ import annotations

import re
from typing import Any

from .connectors.sigbm import norm_name

STOP = {'s', 'a', 'sa', 'ltda', 'me', 'epp', 'eireli', 'cia', 'companhia', 'de', 'da', 'do', 'dos', 'das', 'e', 'mineracao', 'mineradora', 'mineracoes'}


def build_registry(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    orgs: dict[str, dict[str, Any]] = {}
    for r in records:
        if r.get('owner_cnpj'):
            key = 'CNPJ:' + r['owner_cnpj']
        elif r.get('owner_doc_type') == 'CPF_MASCARADO_OCULTO':
            key = 'PF:' + r['id']  # pessoa física: não agrupamos por nome
        else:
            key = 'NOME:' + r.get('owner_name_norm', '')
        o = orgs.setdefault(key, {'org_id': key, 'legal_name': r.get('owner_name'), 'name_norm': r.get('owner_name_norm'),
                                  'cnpj': r.get('owner_cnpj'), 'cnpj_root': r.get('owner_cnpj_root'),
                                  'is_person': r.get('owner_doc_type') == 'CPF_MASCARADO_OCULTO',
                                  'source_id': r['source_id'], 'snapshot_id': r['snapshot_id'], 'asset_ids': []})
        o['asset_ids'].append(r['id'])
    for o in orgs.values():
        o['asset_count'] = len(o['asset_ids'])
    return orgs


def _tokens(s: str) -> set[str]:
    return {t for t in norm_name(s).split() if t not in STOP and len(t) > 1}


def search(query: str, orgs: dict[str, dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    q = (query or '').strip()
    if not q:
        return []
    digits = re.sub(r'\D', '', q)
    qt = _tokens(q)
    out = []
    for o in orgs.values():
        if o['is_person']:
            continue
        if len(digits) == 14 and o['cnpj'] == digits:
            out.append({**o, 'match': 'CNPJ_IDENTICO', 'entity_match_confidence': 0.95,
                        'explanation': 'CNPJ idêntico ao informado no SIGBM.', 'link_status': 'A_CONFIRMAR_GRUPO'})
        elif len(digits) >= 8 and o['cnpj_root'] and o['cnpj_root'] == digits[:8]:
            out.append({**o, 'match': 'RAIZ_CNPJ', 'entity_match_confidence': 0.85,
                        'explanation': 'Mesma raiz de CNPJ (8 primeiros dígitos): mesma pessoa jurídica, possivelmente outro estabelecimento.', 'link_status': 'A_CONFIRMAR'})
        elif qt:
            ot = _tokens(o['legal_name'] or '')
            inter = qt & ot
            if not inter:
                continue
            exact = norm_name(q) == o['name_norm']
            score = round(0.6 if exact else 0.25 + 0.3 * len(inter) / max(len(qt | ot), 1), 2)
            out.append({**o, 'match': 'NOME_EXATO' if exact else 'TEXTUAL', 'entity_match_confidence': score,
                        'explanation': ('Nome normalizado idêntico; confirme pelo CNPJ.' if exact else
                                        f"Correspondência textual nos termos: {', '.join(sorted(inter))}. Não prova vínculo societário."),
                        'link_status': 'A_CONFIRMAR'})
    out.sort(key=lambda x: (-x['entity_match_confidence'], -x['asset_count']))
    return [{k: v for k, v in x.items() if k != 'asset_ids'} | {'asset_ids': x['asset_ids'][:2000]} for x in out[:limit]]
