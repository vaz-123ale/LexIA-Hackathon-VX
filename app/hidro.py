"""Monitoramento hidrológico e manutenção preventiva com dados abertos do ONS (reservatórios do SIN).

Fonte: ONS — Dados Abertos, conjuntos "Dados Hidrológicos por Reservatório (base diária)" e "Reservatórios".
Os arquivos ficam no Amazon S3 público do ONS (ons-aws-prod-opendata). A API do portal (dados.ons.org.br/api) é
proibida pelo robots.txt e NÃO é usada; baixamos só os arquivos publicados.

Técnicas (sem dependências, explicáveis):
- Z-score robusto (mediana e MAD) da vazão afluente e da variação diária do nível contra o histórico do próprio reservatório.
- Tendência: regressão linear do nível nos últimos 30 dias e dias projetados até a cota máxima/mínima operativa.
- KNN: compara a janela dos últimos 14 dias (vazão afluente normalizada) com todas as janelas do histórico e mostra o que
  aconteceu nos 7 dias seguintes às 5 mais parecidas.
- Recomendações de inspeção e manutenção por regra. É apoio à manutenção preventiva, não diagnóstico de segurança;
  a operação dos reservatórios é do ONS e dos agentes.
"""
from __future__ import annotations

import csv
import io
import json
import math
import statistics
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'snapshots' / 'ons' / 'raw'
RULE_VERSION = 'hidro-v1'
STATE: dict = {'items': None, 'by_id': {}, 'meta': None}


def _f(v):
    try:
        return float(v) if v not in (None, '') else None
    except ValueError:
        return None


def _read(path: Path) -> list[dict]:
    raw = path.read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252')
    return list(csv.DictReader(io.StringIO(text), delimiter=';'))


def load(raw_dir: Path = RAW) -> dict:
    meta = {}
    for r in _read(raw_dir / 'RESERVATORIOS.csv'):
        meta[(r.get('nom_reservatorio') or '').strip().upper()] = {
            'cota_max': _f(r.get('val_cotamaxima')), 'cota_min': _f(r.get('val_cotaminima')), 'rio': (r.get('nom_rio') or '').strip(),
            'bacia': (r.get('nom_bacia') or '').strip(), 'lat': _f(r.get('val_latitude')), 'lon': _f(r.get('val_longitude')),
            'usina': (r.get('nom_usina') or '').strip(), 'tipo': (r.get('tip_reservatorio') or '').strip()}
    series: dict[str, dict] = {}
    for f in sorted(raw_dir.glob('DADOS_HIDROLOGICOS_RES_*.csv')):
        for r in _read(f):
            rid = (r.get('id_reservatorio') or '').strip()
            if not rid:
                continue
            s = series.setdefault(rid, {'id': rid, 'nome': (r.get('nom_reservatorio') or '').strip(), 'subsistema': (r.get('nom_subsistema') or '').strip(),
                                        'bacia': (r.get('nom_bacia') or '').strip(), 'tipo': (r.get('tip_reservatorio') or '').strip(), 'rows': []})
            s['rows'].append((r['din_instante'][:10], _f(r.get('val_nivelmontante')), _f(r.get('val_volumeutilcon')), _f(r.get('val_vazaoafluente')),
                              _f(r.get('val_vazaovertida')), _f(r.get('val_vazaodefluente'))))
    for s in series.values():
        s['rows'].sort()
        s['meta'] = meta.get(s['nome'].upper(), {})
    return series


def robust_z(x: float, hist: list[float]) -> float | None:
    h = [v for v in hist if v is not None]
    if x is None or len(h) < 30:
        return None
    med = statistics.median(h)
    mad = statistics.median(abs(v - med) for v in h) or (statistics.pstdev(h) / 1.4826 if len(set(h)) > 1 else 0)
    if not mad:
        return None
    return (x - med) / (1.4826 * mad)


def slope(vals: list[float]) -> float | None:
    pts = [(i, v) for i, v in enumerate(vals) if v is not None]
    if len(pts) < 10:
        return None
    n = len(pts)
    mx = sum(i for i, _ in pts) / n
    my = sum(v for _, v in pts) / n
    den = sum((i - mx) ** 2 for i, _ in pts)
    return sum((i - mx) * (v - my) for i, v in pts) / den if den else None


def knn_analogs(aflu: list[float | None], win: int = 14, ahead: int = 7, k: int = 5) -> dict | None:
    """Janela atual vs. todas as janelas anteriores (normalizadas pela média da janela). Retorna o que veio depois."""
    vals = list(aflu)
    if len(vals) < win * 4 or any(v is None for v in vals[-win:]):
        return None
    cur = vals[-win:]
    m = statistics.mean(cur) or 1e-9
    curn = [v / m for v in cur]
    cands = []
    for s in range(0, len(vals) - win - ahead - win):  # deixa folga para não usar a janela atual
        w = vals[s:s + win]
        nxt = vals[s + win:s + win + ahead]
        if any(v is None for v in w + nxt):
            continue
        mw = statistics.mean(w) or 1e-9
        d = math.sqrt(sum((a - b / mw) ** 2 for a, b in zip(curn, w)))
        cands.append((d, s, (statistics.mean(nxt) - w[-1]) / (w[-1] or 1e-9)))
    if len(cands) < k:
        return None
    cands.sort()
    top = cands[:k]
    change = statistics.mean(c[2] for c in top)
    return {'k': k, 'window_days': win, 'ahead_days': ahead, 'expected_change_pct': round(100 * change, 1),
            'agreement': round(sum(1 for c in top if (c[2] > 0) == (change > 0)) / k, 2), 'mean_distance': round(statistics.mean(c[0] for c in top), 3)}


def analyze(s: dict) -> dict | None:
    rows = s['rows']
    if len(rows) < 60:
        return None
    dates = [r[0] for r in rows]
    nivel = [r[1] for r in rows]
    vol = [r[2] for r in rows]
    aflu = [r[3] for r in rows]
    vert = [r[4] for r in rows]
    last = rows[-1]
    # base sazonal: mesma época do ano anterior (±45 dias), para não chamar de anomalia o início da estação chuvosa
    try:
        ref = date.fromisoformat(last[0]) - timedelta(days=365)
        seasonal = [r[3] for r in rows if abs((date.fromisoformat(r[0]) - ref).days) <= 45]
    except ValueError:
        seasonal = []
    hist_aflu = seasonal if sum(1 for v in seasonal if v is not None) >= 30 else aflu[:-7]
    dniv = [None if (a is None or b is None) else b - a for a, b in zip(nivel[:-1], nivel[1:])]
    z_aflu = robust_z(statistics.mean([v for v in aflu[-3:] if v is not None]) if any(v is not None for v in aflu[-3:]) else None, hist_aflu)
    z_dniv = robust_z(dniv[-1] if dniv else None, dniv[:-7])
    sl = slope(nivel[-30:])
    m = s.get('meta') or {}
    cmax, cmin, nv = m.get('cota_max'), m.get('cota_min'), last[1]
    margin = ((cmax - nv) / (cmax - cmin)) if (cmax and cmin and nv is not None and cmax > cmin) else None
    cota_ok = margin is not None and -0.05 <= margin <= 1.5  # fora disso, a cota cadastral não corresponde à medição
    if not cota_ok:
        margin = None
    days_to_max = ((cmax - nv) / sl) if (cota_ok and sl and sl > 0 and cmax and nv is not None and cmax > nv) else None
    days_to_min = ((nv - cmin) / -sl) if (cota_ok and sl and sl < 0 and cmin and nv is not None and nv > cmin) else None
    spill_days = sum(1 for v in vert[-7:] if v and v > 0)
    knn = knn_analogs(aflu)
    # sinais e recomendações (regra hidro-v1)
    sig, rec = [], []
    if z_aflu is not None and z_aflu >= 3.5:
        sig.append({'code': 'PICO_AFLUENCIA', 'label': f'Vazão afluente muito acima da mesma época do ano anterior (z = {z_aflu:.1f})', 'weight': 3})
        rec.append('Verificar órgãos extravasores e leitura de instrumentação antes do pico chegar.')
    elif z_aflu is not None and z_aflu >= 2:
        sig.append({'code': 'AFLUENCIA_ALTA', 'label': f'Vazão afluente acima da mesma época do ano anterior (z = {z_aflu:.1f})', 'weight': 1})
    if z_dniv is not None and abs(z_dniv) >= 4:
        sig.append({'code': 'SALTO_NIVEL', 'label': f'Variação diária de nível atípica (z = {z_dniv:.1f})', 'weight': 2})
        rec.append('Conferir o dado de nível (possível erro de leitura) e a régua/instrumento.')
    if margin is not None and margin <= 0.05:
        sig.append({'code': 'PERTO_COTA_MAX', 'label': f'Nível a {100 * margin:.0f}% da faixa operativa até a cota máxima', 'weight': 3})
        rec.append('Inspeção do vertedouro e das comportas; revisar plano de operação de cheias.')
    if days_to_max is not None and days_to_max <= 30:
        sig.append({'code': 'TENDENCIA_MAX', 'label': f'Tendência de alta: cota máxima em ~{days_to_max:.0f} dias se mantido o ritmo', 'weight': 2})
    if days_to_min is not None and days_to_min <= 30:
        sig.append({'code': 'TENDENCIA_MIN', 'label': f'Tendência de baixa: cota mínima em ~{days_to_min:.0f} dias se mantido o ritmo', 'weight': 2})
        rec.append('Inspecionar tomada d’água e taludes expostos com o rebaixamento.')
    if spill_days >= 5:
        sig.append({'code': 'VERTIMENTO', 'label': f'Vertimento em {spill_days} dos últimos 7 dias', 'weight': 1})
        rec.append('Inspeção pós-vertimento: dissipador de energia, erosão a jusante, concreto do vertedouro.')
    if knn and knn['expected_change_pct'] >= 30 and knn['agreement'] >= 0.8:
        sig.append({'code': 'ANALOGOS_ALTA', 'label': f"Padrões parecidos no histórico foram seguidos de alta média de {knn['expected_change_pct']:.0f}% na afluência", 'weight': 1})
    if cmax and cmin and nv is not None and not cota_ok:
        sig.append({'code': 'COTA_INCOMPATIVEL', 'label': 'Cota cadastral não corresponde ao nível medido (referência diferente): margem não calculada', 'weight': 0})
    missing = sum(1 for r in rows[-30:] if r[1] is None or r[3] is None)
    if missing >= 10:
        sig.append({'code': 'DADO_FALTANTE', 'label': f'{missing} dos últimos 30 dias sem nível ou vazão', 'weight': 1})
        rec.append('Verificar a telemetria/envio de dados.')
    score = sum(x['weight'] for x in sig)
    level = 'Crítica' if score >= 5 else 'Alta' if score >= 3 else 'Moderada' if score >= 1 else 'Normal'
    tail = rows[-120:]
    return {'id': s['id'], 'nome': s['nome'], 'subsistema': s['subsistema'], 'bacia': s['bacia'], 'tipo': s['tipo'], 'rio': m.get('rio'),
            'lat': m.get('lat'), 'lon': m.get('lon'), 'usina': m.get('usina'), 'last_date': last[0], 'nivel': nv, 'volume_util': last[2],
            'vazao_afluente': last[3], 'vazao_vertida': last[4], 'vazao_defluente': last[5], 'cota_max': cmax, 'cota_min': cmin,
            'margem_cota': None if margin is None else round(margin, 3), 'tendencia_m_dia': None if sl is None else round(sl, 4),
            'dias_ate_cota_max': None if days_to_max is None else round(days_to_max), 'dias_ate_cota_min': None if days_to_min is None else round(days_to_min),
            'z_afluencia': None if z_aflu is None else round(z_aflu, 2), 'z_variacao_nivel': None if z_dniv is None else round(z_dniv, 2),
            'knn': knn, 'signals': sig, 'score': score, 'attention': level, 'recommendations': list(dict.fromkeys(rec)),
            'series': {'datas': [r[0] for r in tail], 'nivel': [r[1] for r in tail], 'afluente': [r[3] for r in tail], 'vertida': [r[4] for r in tail],
                       'volume_util': [r[2] for r in tail]},
            'rule_version': RULE_VERSION}


def compute(raw_dir: Path = RAW) -> dict:
    if not (raw_dir / 'RESERVATORIOS.csv').exists():
        STATE.update(items=[], by_id={}, meta=None)
        return STATE
    series = load(raw_dir)
    items = [a for a in (analyze(s) for s in series.values()) if a]
    order = {'Crítica': 0, 'Alta': 1, 'Moderada': 2, 'Normal': 3}
    items.sort(key=lambda x: (order[x['attention']], -x['score'], x['nome']))
    man_path = raw_dir.parent / 'manifest.json'
    STATE.update(items=items, by_id={x['id']: x for x in items},
                 meta=json.loads(man_path.read_text(encoding='utf8')) if man_path.exists() else None)
    return STATE


def light(x: dict) -> dict:
    return {k: x[k] for k in ('id', 'nome', 'subsistema', 'bacia', 'rio', 'tipo', 'lat', 'lon', 'last_date', 'nivel', 'volume_util', 'vazao_afluente',
                              'vazao_vertida', 'margem_cota', 'z_afluencia', 'attention', 'score')} | {'signals': [s['label'] for s in x['signals']][:3]}
