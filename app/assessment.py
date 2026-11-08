"""Quatro eixos INDEPENDENTES (v3) — não misturar escopo, vigência, andamento e prioridade.

1. normative_lifecycle  (por dispositivo): proposed | published_not_effective | effective | historical | revoked | unknown
2. applicability_assessment: candidate_review | missing_attributes | excluded_by_scope | no_supported_link |
                             confirmed_applicable_by_human | rejected_by_human
3. workflow_state: not_assigned | pending_review | reviewing | approved_for_action | action_in_progress | closed
4. priority: urgent | high | medium | low | not_assessed  (fórmula explícita; NÃO usa CRI/DPA da ANM)

Também: triagem ANM sobre barragens OFICIAIS do SIGBM, com explicação atributo/operador/valor/dispositivo/versão/data.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .engine import analyze, ANM_PHASES
from .temporal import status_at

LIFECYCLE = {'EM_CONSULTA': 'proposed', 'CONSULTA_ENCERRADA': 'proposed', 'FUTURA': 'published_not_effective',
             'VIGENTE': 'effective', 'HISTORICA': 'historical', 'REVOGADA': 'revoked', 'A_CONFERIR': 'unknown'}

RULE_TO_APPLICABILITY = {
    'NR20-R1-exclusao': 'excluded_by_scope', 'NR20-R2-vinculo': 'no_supported_link', 'NR20-R3-dados': 'missing_attributes',
    'NR20-R4-temporal': 'candidate_review', 'NR20-R5-candidato': 'candidate_review', 'NR20-R6-condicao': 'no_supported_link',
    'ANM-R1-futuro': 'candidate_review', 'ANM-R2-fase-ativa': 'candidate_review', 'ANM-R3-escopo': 'no_supported_link',
    'ANP-R1-consulta': 'candidate_review', 'ANP-R2-escopo': 'no_supported_link',
    'ANSN-R1-dados': 'missing_attributes', 'ANSN-R2-alias': 'candidate_review', 'ANSN-R3-escopo': 'no_supported_link',
    'ANM-OF1-sigbm': 'candidate_review', 'ANM-OF0-dados': 'missing_attributes',
}
WORKFLOW = {None: 'not_assigned', 'DRAFT': 'not_assigned', 'REVIEW_PENDING': 'pending_review', 'CONFIRMED': 'approved_for_action',
            'REJECTED': 'closed', 'ACTION_TRACKING': 'action_in_progress', 'CLOSED': 'closed'}
SUGGESTED_FUNCTION = {'eir': 'engenharia', 'nr20': 'engenharia', 'anm': 'engenharia', 'anp_cp21': 'regulatorio', 'ansn': 'protecao_radiologica'}
OPERATORS = {'building': '= verdadeiro', 'generator': '= verdadeiro', 'fuel': '∈ {diesel, biodiesel}', 'tank_config': '∈ {separado, integrado}',
             'offshore_excluded': '= verdadeiro (exclusão)', 'dam': '= verdadeiro', 'anp_regulated': '= verdadeiro', 'radiative': '= verdadeiro',
             'cites_cnen_designation': '= verdadeiro', 'sigbm_record': 'existe no snapshot oficial', 'pnsb': 'informado (Sim/Não)',
             'operational_status': 'informado'}


def lifecycle_of(p: dict[str, Any], when: date) -> str:
    return LIFECYCLE[status_at(p, when)]


def _days(a: date, iso: str | None) -> int | None:
    return (date.fromisoformat(iso) - a).days if iso else None


def assess(f: dict[str, Any], review: dict[str, Any] | None, provisions: dict[str, dict], when: date, extra: dict | None = None) -> dict[str, Any]:
    linked = [provisions[pid] for pid in (f.get('provisions') or []) if pid in provisions]
    if f['scenario'] == 'anm' and f['state'] == 'FUTURE_REVIEW':
        linked = [provisions[pid] for _, pid, _ in ANM_PHASES if pid in provisions]
    life = {p['id']: lifecycle_of(p, when) for p in linked}
    applic = RULE_TO_APPLICABILITY.get(f.get('rule_id'), 'candidate_review')
    rstate = review['state'] if review else None
    if rstate in ('CONFIRMED', 'ACTION_TRACKING', 'CLOSED'):
        applic = 'confirmed_applicable_by_human'
    elif rstate == 'REJECTED':
        applic = 'rejected_by_human'
    wf = WORKFLOW.get(rstate, 'not_assigned')
    if wf == 'pending_review' and review and review.get('assigned_function'):
        wf = 'reviewing'

    # ---- prioridade (fórmula transparente) ----
    parts, score = [], 0
    if applic in ('excluded_by_scope', 'no_supported_link', 'rejected_by_human'):
        level, parts = 'low', [f'Avaliação "{applic}": sem trabalho regulatório adicional sugerido.']
    elif wf == 'closed':
        level, parts = 'low', ['Fluxo encerrado.']
    else:
        add = {'candidate_review': 40, 'missing_attributes': 25, 'confirmed_applicable_by_human': 50}.get(applic, 0)
        score += add; parts.append(f'+{add} avaliação {applic}')
        upcoming = sorted([(p.get('effective_from'), p['id']) for p in linked if life[p['id']] == 'published_not_effective' and p.get('effective_from')])
        if any(v == 'effective' for v in life.values()):
            score += 30; parts.append('+30 há dispositivo vigente na data-base')
        elif upcoming:
            d = _days(when, upcoming[0][0])
            pts = 25 if d <= 180 else 15 if d <= 365 else 5
            score += pts; parts.append(f'+{pts} próximo dispositivo entra em vigor em {d} dias ({upcoming[0][1]})')
        elif any(v == 'proposed' for v in life.values()):
            score += 5; parts.append('+5 texto em consulta (sem obrigação vigente)')
        elif any(v == 'unknown' for v in life.values()):
            score += 10; parts.append('+10 data de efeito a conferir')
        if wf == 'not_assigned':
            score += 10; parts.append('+10 ainda sem responsável')
        if wf == 'action_in_progress':
            score -= 10; parts.append('−10 ação já em andamento')
        if extra and extra.get('pnsb') == 'Sim':
            score += 5; parts.append('+5 estrutura declarada inserida na PNSB (escopo provável maior)')
        level = 'urgent' if score >= 85 else 'high' if score >= 60 else 'medium' if score >= 35 else 'low'
    primary = None
    if life:
        order = ['effective', 'published_not_effective', 'proposed', 'unknown', 'historical', 'revoked']
        primary = sorted(life.items(), key=lambda kv: order.index(kv[1]))[0]
    fn = (review or {}).get('assigned_function') or SUGGESTED_FUNCTION.get(f['scenario'])
    next_action = {
        'missing_attributes': 'Coletar dados: ' + '; '.join(f.get('missing', [])[:3]),
        'excluded_by_scope': 'Sem ação regulatória sugerida; registrar o motivo da exclusão se necessário',
        'no_supported_link': 'Sem vínculo suportado; nenhuma tarefa gerada',
        'rejected_by_human': 'Rejeitado pela revisão humana',
    }.get(applic)
    if not next_action:
        next_action = {'not_assigned': f'Atribuir revisão à função {fn}', 'pending_review': 'Decisão jurídica pendente',
                       'reviewing': f'Em análise pela função {fn}', 'approved_for_action': 'Planejar ação e evidências',
                       'action_in_progress': 'Registrar evidência da execução', 'closed': 'Encerrado'}[wf]
        if primary and primary[1] == 'proposed':
            next_action = 'Monitorar a consulta pública; não criar tarefa de cumprimento'
    return {'normative_lifecycle': life, 'primary_provision': primary[0] if primary else None,
            'primary_lifecycle': primary[1] if primary else None, 'applicability_assessment': applic,
            'workflow_state': wf, 'priority': {'level': level if parts else 'not_assessed', 'score': score, 'justification': parts,
                                               'formula_version': 'prio-v1', 'uses_official_risk_category': False},
            'next_action': next_action, 'suggested_function': fn}


def explanation(f: dict[str, Any], provisions: dict[str, dict]) -> list[dict[str, Any]]:
    """Explicação da triagem: atributo, operador, valor, dispositivo, versão e data."""
    pids = f.get('provisions') or []
    p = provisions.get(pids[0]) if pids else None
    return [{'attribute': c['label'], 'key': c['key'], 'operator': OPERATORS.get(c['key'], '—'), 'value': c['value'],
             'result': c['status'], 'provision': p['provision'] if p else None, 'provision_id': p['id'] if p else None,
             'version': p['version'] if p else None, 'as_of': f['as_of']} for c in f.get('conditions', [])]


def analyze_official_anm(rec: dict[str, Any], when: date, observed_at: str) -> dict[str, Any]:
    """Triagem ANM 220/2025 (+245/2026) para estrutura REAL do SIGBM. Não avalia segurança, risco nem conformidade."""
    obs = date.fromisoformat(observed_at[:10])
    conds = [{'key': 'sigbm_record', 'label': 'Estrutura cadastrada no SIGBM (barragem de mineração)', 'value': rec['official_id'], 'status': 'MET'},
             {'key': 'pnsb', 'label': 'Inserida na PNSB (dado oficial)', 'value': rec.get('pnsb'), 'status': 'MET' if rec.get('pnsb') else 'MISSING'},
             {'key': 'operational_status', 'label': 'Situação operacional (dado oficial)', 'value': rec.get('operational_status'), 'status': 'MET' if rec.get('operational_status') else 'MISSING'}]
    temporal_note = ('Atributos observados no snapshot de ' + obs.strftime('%d/%m/%Y') + '; NÃO representam o estado da estrutura na data simulada.' if when < obs
                     else 'Atributos atuais do snapshot projetados para a data simulada; podem mudar até lá.' if when > obs else
                     'Atributos do snapshot da data-base.')
    missing = [c['label'] for c in conds if c['status'] == 'MISSING']
    base = analyze({'id': rec['id'], 'facts': {'dam': True}}, 'anm', when).payload()
    if missing:
        base.update(state='INSUFFICIENT', headline='Faltam atributos oficiais para a triagem', rule_id='ANM-OF0-dados',
                    missing=missing, actions=['Solicitar o dado ao responsável ou aguardar atualização da fonte oficial.', 'Não emitir declaração de aplicabilidade.'])
    else:
        base['rule_id'] = 'ANM-OF1-sigbm'
        base['missing'] = ['Leitura integral dos dispositivos aplicáveis (o conteúdo dos artigos não foi auditado no dossiê).',
                           'Enquadramento técnico-jurídico pelo responsável técnico.'] + base['missing'][:1]
    base.update(asset_id=rec['id'], conditions=conds, origin='DADO_OFICIAL', snapshot_id=rec['snapshot_id'],
                temporal_note=temporal_note, attributes_observed_at=observed_at)
    base['rationale'] = (base['rationale'] + ' Triagem preliminar: estrutura real do SIGBM; não avalia segurança, estabilidade, risco nem conformidade.')
    return base
