"""Negócio & Impacto — mercado, segmentos, eficiência da IA e valor social calculados sobre dados oficiais.

Regras de honestidade (AGENTS.md):
- Contagens de mercado e de impacto vêm do SIGBM/ANM e do SNISB/ANA, com origem declarada.
- Preço e adoção são PREMISSAS da equipe (data/business_assumptions.json), rotuladas como tal e editáveis.
- Nenhum ganho de produtividade, economia ou acurácia é inventado: a eficiência da IA usa métricas de validação
  cruzada e as probabilidades dos modelos.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEOPLE = {'1-100': (1, 100), '101-500': (101, 500), '501-1000': (501, 1000), '1001-5000': (1001, 5000), 'acima de 5001': (5001, None)}


def segments(records: list[dict]) -> dict:
    key = lambda r: r.get('owner_key') or r.get('owner_cnpj') or r.get('owner_name_norm') or r['id']
    own = Counter(key(r) for r in records)
    pf = {key(r) for r in records if r.get('owner_doc_type') == 'CPF_MASCARADO_OCULTO'}
    coop = {key(r) for r in records if 'cooperativa' in (r.get('owner_name_norm') or '')}
    seg = {'essencial': 0, 'profissional': 0, 'corporativo': 0}
    dams = {'essencial': 0, 'profissional': 0, 'corporativo': 0}
    for k, n in own.items():
        s = 'essencial' if n <= 5 or k in pf or k in coop else 'profissional' if n <= 30 else 'corporativo'
        seg[s] += 1
        dams[s] += n
    return {'owners': seg, 'dams': dams, 'total_owners': len(own), 'municipalities': len({(r.get('uf'), r.get('municipio')) for r in records})}


def people_range(recs: list[dict]) -> dict:
    lo = hi = 0
    open_top = False
    for r in recs:
        rg = PEOPLE.get(r.get('people_affected') or '')
        if rg:
            lo += rg[0]
            if rg[1] is None:
                open_top = True
                hi += rg[0]
            else:
                hi += rg[1]
    return {'min': lo, 'max': hi, 'open_top': open_top}


def social(records: list[dict], items: list[dict], flagged_ids: set[str]) -> dict:
    by_id = {r['id']: r for r in records}
    attention = {x['id'] for x in items if x['kind'] == 'mineracao' and x['attention'] in ('Crítica', 'Alta')}
    union = [by_id[i] for i in (flagged_ids | attention) if i in by_id]
    pop = [r for r in union if (r.get('downstream_population') or '').startswith('Existente')]
    orph = [x for x in items if x['kind'] == 'orfa']
    return {
        'dams_flagged_or_attention': len(union), 'with_permanent_population': len(pop),
        'people_declared_range': people_range(union), 'municipalities': len({(r.get('uf'), r.get('municipio')) for r in union}),
        'orphans_human_supply': sum(1 for x in orph if x.get('use') == 'Abastecimento humano'),
        'orphans_high_dpa': sum(1 for x in orph if x.get('damage_potential') == 'Alto'),
        'reading': 'Faixas de pessoas declaradas pelo empreendedor no SIGBM ("pessoas possivelmente afetadas em caso de rompimento") somadas para as barragens apontadas pelos modelos ou em atenção crítica/alta. É ordem de grandeza, não estimativa de vítimas.',
    }


def ai_efficiency(agent_queue: list[dict], models: dict) -> dict:
    """Quanto a fila do agente concentra problemas, com base nas probabilidades e na validação cruzada."""
    out = {}
    for t, m in models.items():
        if m:
            out[t] = {'precision_top10': m['metrics'].get('precision_top10'), 'precision_top50': m['metrics']['precision_top50'],
                      'base_rate': m['metrics']['base_rate'], 'lift_top50': m['metrics']['lift_top50'], 'cv_auc': m['metrics']['cv_auc']}
    top = agent_queue[:10]
    return {'models': out, 'queue_top10_expected': round(sum(r['p_algum_problema'] for r in top), 1) if top else None,
            'reading': 'Precisão no topo = fração das barragens mais bem ranqueadas que eram de fato positivas, medida em validação cruzada (sem ver a resposta). Taxa-base = acerto esperado escolhendo ao acaso.'}


def build(records: list[dict], items: list[dict], flagged_ids: set[str], agent_queue: list[dict], models: dict) -> dict:
    market = json.loads((ROOT / 'data' / 'market_snisb.json').read_text(encoding='utf8'))
    assumptions = json.loads((ROOT / 'data' / 'business_assumptions.json').read_text(encoding='utf8'))
    estudo_path = ROOT / 'data' / 'estudo_mercado.json'
    estudo = json.loads(estudo_path.read_text(encoding='utf8')) if estudo_path.exists() else None
    seg = segments(records)
    return {
        'market': {
            'tam': {'label': 'Barragens cadastradas no Brasil (SNISB)', 'dams': market['total_dams'], 'with_owner': market['dams_with_owner'], 'source': market['source']},
            'sam_expansion': {'label': 'Barragens sob a PNSB (obrigações da Lei 12.334)', 'dams': market['pnsb_dams'], 'owners': market['pnsb_distinct_owners'],
                              'by_use': market['by_use_pnsb'], 'source': market['source']},
            'beachhead': {'label': 'Mineração (SIGBM/ANM) — mercado inicial', 'dams': len(records), 'owners': seg['total_owners'], 'segments': seg, 'source': 'ANM · SIGBM'},
            'public': {'label': 'Municípios com barragem de mineração', 'count': seg['municipalities']},
            'collected_at': market['collected_at'], 'method': market['method'],
        },
        'assumptions': assumptions,
        'estudo': estudo,
        'unit_costs': {'fixo_ano5': 336743, 'comercial_por_venda': 12000, 'implantacao_preco': 10000, 'implantacao_custo': 6000,
                       'atendimento_por_conta': 12000, 'reserva_receita': 0.10, 'fonte': 'Relatório de mercado, cap. 11 (cenário-base, ano 5)'},
        'multa_simulada_dce': {'valor': 26337.70, 'regra': 'Res. ANM 223/2025, art. 26, §2º, VII (grupo VI-2) e Res. ANM 230/2026, Anexo II; produção mineral hipotética de R$ 30 mi', 'evidencia': 'E55–E56'},
        'social': social(records, items, flagged_ids),
        'ai_efficiency': ai_efficiency(agent_queue, models),
        'sales_calendar': [
            {'when': 'março e setembro (todo ano)', 'what': 'Campanhas de Declaração de Condição de Estabilidade (DCE) da ANM', 'why': 'Momento de dor: a previsão de falha na próxima DCE vira gatilho de venda e de preparação.'},
            {'when': 'a cada snapshot diário do SIGBM', 'what': 'Mudança de situação, nível de emergência ou DCE', 'why': 'O agente gera propostas e notificações: produto vivo, não relatório parado.'},
            {'when': 'transições normativas (ex.: Resoluções ANM 220/2025 e 245/2026)', 'what': 'Dispositivos que entram em vigor por etapas', 'why': 'Monitor de normas por dispositivo cria urgência datada.'},
        ],
    }
