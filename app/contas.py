"""Contas-alvo: o que os dados PÚBLICOS da ANM mostram sobre cada empresa da lista comercial.

Regra contas-v1:
- correspondência só pelo nome do titular/empreendedor no SIGBM (barragens) e no SIGMINE (títulos de lavra), com o padrão
  cadastrado para a conta; sem inferência de grupo econômico (AGENTS.md: não inferir obrigação de grupo pelo nome);
- a relação comercial exibida é a cadastrada ('alvo' por padrão); a LexIA não declara ninguém cliente ou parceiro;
- nenhum dado sintético é associado a empresa real.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE_VERSION = 'contas-v1'
RELACAO = {'alvo': 'Conta-alvo (prospecção)', 'cliente': 'Cliente (contrato registrado)'}


def _n(s) -> str:
    return unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().upper().strip()


def load(root: Path = ROOT) -> dict:
    return json.loads((root / 'data' / 'contas_alvo.json').read_text(encoding='utf8'))


def match(cfg: dict, sigbm_records: list[dict], radar_by_id: dict, minas: list[dict]) -> dict:
    out = []
    for c in cfg['contas']:
        rx = re.compile(c['padrao'])
        dams = [r for r in sigbm_records if rx.search(_n(r.get('owner_name')))]
        titles = [m for m in minas if rx.search(_n(m.get('titular')))]
        names = sorted({r.get('owner_name') for r in dams} | {m.get('titular') for m in titles})
        att = Counter((radar_by_id.get(r['id']) or {}).get('attention', 'Sem sinal') for r in dams)
        out.append({
            'id': c['id'], 'nome': c['nome'], 'relacao': RELACAO.get(c.get('relacao'), RELACAO['alvo']),
            'encontrada': bool(dams or titles), 'nomes_no_cadastro': names[:5],
            'barragens': len(dams), 'dpa_alta': sum(1 for r in dams if (r.get('dpa') or '').lower() == 'alta'),
            'em_emergencia': sum(1 for r in dams if r.get('emergency_level') not in (None, '', 'Sem emergência')),
            'atencao_radar': dict(att), 'ufs': sorted({r.get('uf') for r in dams} | {m.get('uf') for m in titles} - {None}),
            'titulos_lavra': len(titles), 'substancias': [s for s, _ in Counter(m['substancia'] for m in titles).most_common(4)],
            'radiologico': sum(1 for m in titles if m.get('radiologico')),
            'barragens_lista': [{'id': r['id'], 'nome': r.get('name'), 'municipio': r.get('municipio'), 'uf': r.get('uf'), 'dpa': r.get('dpa'),
                                 'emergencia': r.get('emergency_level'), 'atencao': (radar_by_id.get(r['id']) or {}).get('attention')} for r in dams[:12]],
            'modulos_sugeridos': [m for m, ok in (('Barragens', bool(dams)), ('Minas', bool(titles)), ('Radiológico (CNEN)', any(t.get('radiologico') for t in titles))) if ok] + ['Documentos e licenças', 'Jurídico e Compliance'],
        })
    return {'aviso': cfg['aviso'], 'items': out, 'rule_version': RULE_VERSION}
