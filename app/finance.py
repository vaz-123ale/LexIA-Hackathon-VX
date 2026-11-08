"""Decision Lab: comparação de opções por PREMISSAS do usuário (mín/base/máx).

Nada aqui é derivado de multa, sanção ou dado empresarial real. O resultado é cálculo
reproduzível sobre números informados por quem usa, com memória de cálculo e sensibilidade.
"""
from __future__ import annotations

from typing import Any

ESTIMATOR_VERSION = 'decision-lab-v1'
VARS = {
    'horas_internas': ('Horas internas', 'h'),
    'custo_hora': ('Custo por hora interna', 'R$/h'),
    'custo_externo': ('Custo externo (consultoria, obra, laudo)', 'R$'),
    'duracao_meses': ('Duração da execução', 'meses'),
}


def _triplet(v: Any, name: str) -> tuple[float, float, float]:
    if isinstance(v, (int, float)):
        v = [v, v, v]
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise ValueError(f'{name}: informe [mínimo, base, máximo].')
    lo, base, hi = (float(x) for x in v)
    if lo < 0 or not (lo <= base <= hi):
        raise ValueError(f'{name}: exige 0 ≤ mínimo ≤ base ≤ máximo.')
    return lo, base, hi


def _cost(h: float, ch: float, ext: float) -> float:
    return h * ch + ext


def evaluate(options: list[dict[str, Any]]) -> dict[str, Any]:
    if not options or len(options) > 5:
        raise ValueError('Informe de 1 a 5 opções.')
    out = []
    for opt in options:
        name = str(opt.get('name', 'Opção'))[:80]
        t = {k: _triplet(opt.get(k, 0), VARS[k][0]) for k in VARS}
        (hl, hb, hh), (cl, cb, chh), (el, eb, eh) = t['horas_internas'], t['custo_hora'], t['custo_externo']
        low, base, high = _cost(hl, cl, el), _cost(hb, cb, eb), _cost(hh, chh, eh)
        sens = []
        for k, idx in (('horas_internas', 0), ('custo_hora', 1), ('custo_externo', 2)):
            def with_(val):
                args = [hb, cb, eb]; args[idx] = val
                return _cost(*args)
            lo_v, hi_v = with_(t[k][0]), with_(t[k][2])
            sens.append({'variable': k, 'label': VARS[k][0], 'low_total': round(lo_v, 2), 'high_total': round(hi_v, 2), 'swing': round(hi_v - lo_v, 2)})
        sens.sort(key=lambda s: -s['swing'])
        out.append({
            'name': name, 'note': str(opt.get('note', ''))[:300],
            'total': {'low': round(low, 2), 'base': round(base, 2), 'high': round(high, 2)},
            'duration_months': {'low': t['duracao_meses'][0], 'base': t['duracao_meses'][1], 'high': t['duracao_meses'][2]},
            'memory': [f'mínimo = {hl:g} h × R$ {cl:,.2f}/h + R$ {el:,.2f} = R$ {low:,.2f}',
                       f'base = {hb:g} h × R$ {cb:,.2f}/h + R$ {eb:,.2f} = R$ {base:,.2f}',
                       f'máximo = {hh:g} h × R$ {chh:,.2f}/h + R$ {eh:,.2f} = R$ {high:,.2f}'],
            'sensitivity': sens,
            'inputs': {k: list(v) for k, v in t.items()},
        })
    return {'estimator_version': ESTIMATOR_VERSION, 'options': out,
            'caveats': ['Estimativa baseada exclusivamente em premissas informadas pelo usuário.',
                        'Não inclui multas, sanções nem perdas: nenhum valor desse tipo foi verificado em dispositivo.',
                        'Mínimo e máximo combinam os extremos de todas as variáveis (cenário conservador de amplitude).']}
