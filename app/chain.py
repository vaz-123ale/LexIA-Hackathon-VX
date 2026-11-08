"""Cadeia explicável: fonte → versão → dispositivo → condição → ativo → ação → revisão → evidência.

Cada etapa declara QUEM atua: IA (propõe), REGRA (verifica), HUMANO (decide), SISTEMA (registra).
Nesta demo as etapas de IA mostram extrações de referência curadas manualmente — o que o
extrator/curador deve produzir — e são rotuladas como tal.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .engine import analyze, STATES
from .temporal import status_at, LABELS

EVIDENCE_TEMPLATES = {
    'eir': ['Data da inspeção regular do ciclo', 'Protocolo de envio do EIR no SIGBM', 'Registro da data anterior (15/04) e da nova (23/04)', 'Aprovação do responsável técnico'],
    'nr20': ['Ficha técnica do grupo gerador', 'Configuração e volume do tanque de consumo', 'Classificação da instalação (Anexo III)', 'Parecer do profissional competente'],
    'anm': ['Enquadramento legal da estrutura', 'Classificação técnica vigente', 'Plano de transição por dispositivo e fase', 'Parecer do responsável técnico'],
    'anp_cp21': ['Registro de acompanhamento da consulta', 'Decisão interna sobre contribuição'],
    'ansn': ['Inventário de normas citadas nos procedimentos', 'Conferência de edição no catálogo ANSN', 'Revisão documental aprovada'],
}

ACTOR_INFO = {
    'IA': 'IA propõe',
    'REGRA': 'Regra versionada verifica',
    'HUMANO': 'Humano competente decide',
    'SISTEMA': 'Sistema registra',
}


def critic(finding: dict[str, Any], provisions: list[dict], sources: dict[str, dict], when: date) -> list[dict[str, Any]]:
    """Agente crítico (determinístico nesta demo): procura motivos para NÃO concluir."""
    checks = []
    statuses = [status_at(p, when) for p in provisions]
    checks.append({'check': 'Vigência por dispositivo conferida na data', 'ok': True,
                   'detail': ', '.join(f"{p['id']}: {LABELS[s]}" for p, s in zip(provisions, statuses)) or 'Sem dispositivos ligados.'})
    fut = [p['id'] for p, s in zip(provisions, statuses) if s in ('FUTURA', 'EM_CONSULTA', 'A_CONFERIR')]
    checks.append({'check': 'Nenhum dispositivo futuro/em consulta tratado como vigente', 'ok': not (fut and finding['state'] == 'REVIEW' and all(s != 'VIGENTE' for s in statuses)),
                   'detail': ('Dispositivos não vigentes: ' + ', '.join(fut)) if fut else 'Todos os dispositivos ligados estão vigentes ou históricos.'})
    weak = [sid for sid in finding['source_ids'] if sources.get(sid, {}).get('verification') == 'I']
    checks.append({'check': 'Fontes com verificação textual (T) ou catálogo (C)', 'ok': not weak,
                   'detail': ('Fontes só indicativas: ' + ', '.join(weak)) if weak else 'Nenhuma fonte apenas indicativa (I).'})
    checks.append({'check': 'Prazo legal só se expresso na fonte', 'ok': finding['legal_deadline'] is None,
                   'detail': 'Nenhum prazo inventado (legal_deadline = null).'})
    checks.append({'check': 'Dados faltantes declarados', 'ok': True, 'detail': '; '.join(finding['missing']) or 'Nenhum.'})
    checks.append({'check': 'Sem inferência pelo nome da organização', 'ok': True,
                   'detail': 'Triagem usa apenas atributos do ativo, não nome ou setor do grupo.'})
    return checks


def build_chain(asset: dict, scenario: dict, provisions_all: list[dict], sources: list[dict], review: dict | None, when: date, finding: dict | None = None) -> dict[str, Any]:
    f = finding or analyze(asset, scenario['id'], when).payload()
    src = {s['id']: s for s in sources}
    pmap = {p['id']: p for p in provisions_all}
    linked = [pmap[pid] for pid in (f['provisions'] or scenario['provisions']) if pid in pmap]
    evidence_done = {e['item'] for e in (review or {}).get('evidence', [])}
    stages = [
        {'key': 'fonte', 'title': 'Fonte oficial', 'actor': 'IA', 'agent': 'Curador',
         'summary': f"{len(f['source_ids'])} fonte(s) catalogada(s) com URL, nível T/C/I e data de verificação.",
         'items': [{'label': f"{sid} · {src[sid]['title']}", 'meta': f"Nível {src[sid]['verification']} · verificado em {src[sid]['verified_on']}", 'url': src[sid]['url']} for sid in f['source_ids'] if sid in src],
         'note': 'Extração de referência curada (o que o agente Curador deve produzir). Abrir a página não verifica vigência.'},
        {'key': 'versao', 'title': 'Versão', 'actor': 'IA', 'agent': 'Versionador',
         'summary': 'Identifica a redação aplicável na data e o ato modificador.',
         'items': [{'label': f"{p['document']} · {p['version']}", 'meta': f"{LABELS[status_at(p, when)]}" + (f" · substitui {p['supersedes']}" if p.get('supersedes') else '')} for p in linked],
         'note': 'Comparação de versões por dispositivo; a decisão de vigência é da regra temporal.'},
        {'key': 'dispositivo', 'title': 'Dispositivo', 'actor': 'IA', 'agent': 'Extrator',
         'summary': 'Obrigação candidata estruturada com trecho verificável.',
         'items': [{'label': p['provision'], 'meta': p['summary']} for p in linked],
         'note': 'Resumo curado a partir do dossiê; não é transcrição integral da norma.'},
        {'key': 'condicao', 'title': 'Condições e exceções', 'actor': 'REGRA', 'agent': f"Regra {f['rule_id']}",
         'summary': 'Cada condição é testada contra os atributos cadastrados do ativo.',
         'items': [{'label': c['label'], 'meta': f"valor: {c['value'] if c['value'] is not None else '— (ausente)'}", 'status': c['status']} for c in f['conditions']]
                  + [{'label': 'Exceção: ' + ex, 'meta': 'verificar', 'status': 'CHECK'} for p in linked for ex in p.get('exceptions', [])],
         'note': 'Motor determinístico versionado (app/engine.py). Mesma entrada → mesma saída.'},
        {'key': 'ativo', 'title': 'Ativo (gêmeo digital)', 'actor': 'SISTEMA', 'agent': 'Cadastro de ativos',
         'summary': f"{asset['id']} · {asset['name']} — {asset['region']}",
         'items': [{'label': k, 'meta': str(v)} for k, v in asset.get('facts', {}).items()],
         'note': ('Dado oficial do SIGBM (snapshot ' + str(asset.get('snapshot_id')) + '). Não indica segurança nem conformidade.') if asset.get('origin') == 'DADO_OFICIAL' else 'CENÁRIO HIPOTÉTICO: dados sintéticos. Em produção: cadastro de ativos autorizado.'},
        {'key': 'acao', 'title': 'Ação candidata', 'actor': 'IA', 'agent': 'Aplicabilidade + Explicador',
         'summary': f"{STATES.get(f['state'], f['state'])}: {f['headline']}",
         'items': [{'label': a, 'meta': 'proposta — requer aceite humano'} for a in f['actions']] + [{'label': 'Prazo legal', 'meta': f['legal_deadline'] or 'não expresso na fonte (null)'}],
         'note': 'Sugestão, nunca ordem. Nenhuma tarefa é publicada sem aceite.'},
        {'key': 'revisao', 'title': 'Revisão humana', 'actor': 'HUMANO', 'agent': 'Jurídico / especialista',
         'summary': f"Estado do fluxo: {review['state'] if review else 'sem revisão aberta (achado não acionável)'}",
         'items': [{'label': f"{t['from_state']} → {t['to_state']}", 'meta': f"{t['actor']} ({t['role']}) · {t['at']} · {t['reason']} · fonte {t['source_version']}"} for t in (review or {}).get('transitions', [])],
         'note': 'DRAFT → REVIEW_PENDING → CONFIRMED/REJECTED → ACTION_TRACKING → CLOSED.'},
        {'key': 'evidencia', 'title': 'Evidência', 'actor': 'HUMANO', 'agent': 'Responsável da área',
         'summary': f"{len(evidence_done)} de {len(EVIDENCE_TEMPLATES.get(scenario['id'], []))} evidência(s) registradas.",
         'items': [{'label': item, 'meta': 'registrada (hash na trilha)' if item in evidence_done else 'faltante', 'status': 'MET' if item in evidence_done else 'MISSING'} for item in EVIDENCE_TEMPLATES.get(scenario['id'], [])],
         'note': 'Evidência é registro, não declaração de conformidade.'},
    ]
    return {'finding': f, 'stages': stages, 'critic': critic(f, linked, src, when), 'actors': ACTOR_INFO,
            'contract': {
                'finding_id': f"{scenario['id']}:{asset['id']}", 'asset_id': asset['id'], 'status': f['state'],
                'document_ids': f['source_ids'], 'provisions': [p['id'] for p in linked],
                'effective_by_provision': {p['id']: p.get('effective_from') for p in linked},
                'observed_as_of': when.isoformat(), 'jurisdiction': linked[0]['jurisdiction'] if linked else None,
                'conditions': [c['label'] for c in f['conditions']], 'exceptions': [ex for p in linked for ex in p.get('exceptions', [])],
                'missing_context': f['missing'], 'legal_deadline': f['legal_deadline'], 'review_required': True,
                'review_state': review['state'] if review else None, 'rule_id': f['rule_id']}}


def build_graph(assets: list[dict], scenarios: list[dict], provisions: list[dict], sources: list[dict], reviews: list[dict], when: date) -> dict[str, Any]:
    nodes, edges = {}, []
    used_sources = set()
    rev = {r['id']: r for r in reviews}

    def node(nid, kind, label, **extra):
        nodes.setdefault(nid, {'id': nid, 'kind': kind, 'label': label, **extra})

    def edge(a, b, rel, source_id=None, review_status='SINTETICO'):
        edges.append({'from': a, 'to': b, 'rel': rel, 'source_id': source_id, 'review_status': review_status})

    for sc in scenarios:
        for pid in sc['provisions']:
            p = next((x for x in provisions if x['id'] == pid), None)
            if not p:
                continue
            doc_id = 'DOC:' + p['document']
            node(doc_id, 'documento', p['document'], regulator=p['regulator'])
            node('PROV:' + pid, 'dispositivo', p['provision'], status=status_at(p, when), version=p['version'], provision_id=pid)
            edge(doc_id, 'PROV:' + pid, 'contém', p['sources'][0])
            for sid in p['sources']:
                used_sources.add(sid)
                edge('SRC:' + sid, doc_id, 'publica', sid, 'CATALOGADO')
            if p.get('supersedes'):
                edge('PROV:' + pid, 'PROV:' + p['supersedes'], 'substitui', p['sources'][0])
        for a in assets:
            f = analyze(a, sc['id'], when)
            if f.state in ('OUT_OF_SCOPE', 'NO_LINK'):
                continue
            node('AST:' + a['id'], 'ativo', f"{a['id']} · {a['name']}", asset_id=a['id'])
            fid = f"{sc['id']}:{a['id']}"
            node('FND:' + fid, 'achado', f"{fid} · {STATES[f.state]}", state=f.state, scenario=sc['id'], asset_id=a['id'])
            for pid in f.provisions:
                edge('PROV:' + pid, 'FND:' + fid, 'condição testada', f.source_ids[0], f.rule_id)
            edge('FND:' + fid, 'AST:' + a['id'], 'refere-se a', None, f.rule_id)
            r = rev.get(fid)
            if r:
                node('REV:' + fid, 'revisao', f"Revisão · {r['state']}", state=r['state'])
                edge('FND:' + fid, 'REV:' + fid, 'exige revisão', None, r['state'])
                for e in r.get('evidence', []):
                    node(f"EVD:{e['id']}", 'evidencia', e['item'], sha256=e['sha256'])
                    edge('REV:' + fid, f"EVD:{e['id']}", 'comprovada por', None, 'REGISTRADO')
    src = {s['id']: s for s in sources}
    for sid in used_sources:
        node('SRC:' + sid, 'fonte', f"{sid} · {src[sid]['title']}", url=src[sid]['url'], verification=src[sid]['verification'])
    return {'nodes': list(nodes.values()), 'edges': edges, 'synthetic': True, 'as_of': when.isoformat()}
