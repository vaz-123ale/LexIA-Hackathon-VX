"""Detector de risco oculto — aprendizado de máquina sobre o SIGBM/ANM (sem dependências externas).

Pergunta que o modelo responde:
  "Quais barragens têm o PERFIL TÉCNICO declarado parecido com o das que estão em nível de emergência,
   mas se declaram 'Sem emergência'?"

- Modelo: regressão logística com regularização L2, treinada nos campos técnicos declarados
  (conservação, instrumentação, documentação, equipe, método construtivo, DCE, idade, altura, volume).
- NÃO usa CRI/DPA (categorias oficiais derivadas) nem população a jusante (consequência, não causa).
- Qualidade medida por validação cruzada estratificada (5 dobras): AUC e precisão no topo, calculadas
  aqui, sobre os dados do snapshot. Nada é inventado: se os dados mudarem, os números mudam.
- Cada barragem sinalizada traz as 3 características que mais pesaram (contribuição = coeficiente × valor).
- Saída é PEDIDO DE CONFERÊNCIA, não diagnóstico: o nível de emergência é declarado pelo empreendedor
  e a avaliação de segurança é do engenheiro responsável e da ANM.
"""
from __future__ import annotations

import math
import random
import re
from datetime import date

from .abandono import br_date, br_num

MODEL_VERSION = 'risco-oculto-v1'
CATEGORICAL = {
    'spillway': 'Extravasor', 'percolation': 'Percolação', 'deformation': 'Deformações', 'slope_deterioration': 'Taludes',
    'instrumentation': 'Instrumentação', 'project_docs': 'Documentação de projeto', 'safety_team': 'Equipe de segurança',
    'pae_status': 'PAE', 'build_method': 'Método construtivo', 'containment': 'Contenção', 'dam_type': 'Tipo de barragem',
    'operational_status': 'Situação',
}
# Fora de propósito (vazamento): DCE não atestada já leva a nível de emergência pela norma da ANM;
# CRI/DPA são classificações derivadas; população a jusante é consequência.


def _cat(field: str, v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip()
    if field in ('spillway', 'percolation', 'deformation', 'slope_deterioration'):
        m = re.match(r'(\d+)', v)
        NOTE = {'0': 'sem problema', '2': 'problema com correção em curso', '3': 'problema com correção em curso', '5': 'inexistente', '6': 'problema sem correção', '10': 'situação grave'}
        return f'nota {m[1]} ({NOTE.get(m[1], "ver fonte")})' if m else v[:40]
    if field in ('dce_risr', 'dce_rpsb'):
        return 'Não enviado' if 'Não Enviado' in v else 'Não atestado' if 'Não Atestado' in v else 'Atestado' if 'Atestado' in v else None
    return v[:60]


def _numeric(r: dict, today: date) -> dict[str, float]:
    out = {}
    h, hp, vol = br_num(r.get('height_current_m')), br_num(r.get('height_project_m')), br_num(r.get('volume_current_m3'))
    d = br_date(r.get('op_start'))
    if h and h > 0:
        out['log altura atual'] = math.log10(h + 1)
    if vol and vol > 0:
        out['log volume atual'] = math.log10(vol + 1)
    if h and hp and hp > 0:
        out['altura atual / licenciada'] = min(3.0, h / hp)
    if d and 1900 < d.year <= today.year:
        out['idade (anos)'] = min(80, (today - d).days / 365.25)
    return out


def featurize(records: list[dict], today: date):
    vocab: dict[str, int] = {}
    labels: dict[str, str] = {}
    raw = []
    for r in records:
        feats = {}
        for f, lab in CATEGORICAL.items():
            c = _cat(f, r.get(f))
            key = f'{f}={c}' if c else f'{f}=(não informado)'
            feats[key] = 1.0
            labels[key] = f'{lab}: {c or "não informado"}'
        for k, v in _numeric(r, today).items():
            feats[k] = v
            labels[k] = k
        raw.append(feats)
    for feats in raw:
        for k in feats:
            vocab.setdefault(k, len(vocab))
    num_keys = [k for k in vocab if '=' not in k]
    stats = {}
    for k in num_keys:
        vals = [f[k] for f in raw if k in f]
        mu = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / max(1, len(vals) - 1)) or 1.0
        stats[k] = (mu, sd)
    rows = []
    for feats in raw:
        row = []
        for k, v in feats.items():
            if k in stats:
                v = (v - stats[k][0]) / stats[k][1]
            row.append((vocab[k], v))
        rows.append(row)
    return rows, vocab, labels


def train(rows, y, dim, l2=0.03, epochs=300, lr=0.3, weights=None):
    weights = weights or [1.0] * len(rows)
    w = [0.0] * dim
    pos = sum(t * sw for t, sw in zip(y, weights)) / sum(weights)
    b = math.log(pos / (1 - pos)) if 0 < pos < 1 else 0.0
    n = sum(weights)
    for _ in range(epochs):
        gw = [0.0] * dim
        gb = 0.0
        for row, t, sw in zip(rows, y, weights):
            z = b + sum(w[i] * v for i, v in row)
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            err = (p - t) * sw
            gb += err
            for i, v in row:
                gw[i] += err * v
        b -= lr * gb / n
        for i in range(dim):
            w[i] -= lr * (gw[i] / n + l2 * w[i])
    return w, b


def predict(w, b, row):
    z = b + sum(w[i] * v for i, v in row)
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def auc(scores, y):
    pairs = sorted(zip(scores, y))
    rank_sum, n_pos = 0.0, sum(y)
    n_neg = len(y) - n_pos
    i = 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        rank_sum += avg * sum(t for _, t in pairs[i:j])
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg) if n_pos and n_neg else float('nan')


def is_emergency(r: dict) -> int:
    return int(bool(r.get('emergency_level')) and r.get('emergency_level') != 'Sem emergência')


def dce_failed(r: dict) -> int:
    s = (r.get('dce_risr') or '') + ' ' + (r.get('dce_rpsb') or '')
    return int('Não Atestado' in s or 'Não Enviado' in s)


# Alvos de predição. Nenhum usa como variável o próprio campo que define o rótulo.
TARGETS = {
    'emergencia': {
        'name': 'Emergência não declarada', 'version': 'risco-oculto-v1',
        'question': 'Quais barragens têm perfil técnico de barragem em emergência, mas se declaram “sem emergência”?',
        'eligible': lambda r: bool(r.get('emergency_level')) and r.get('pnsb') == 'Sim', 'label': is_emergency,
        'positive': 'em emergência', 'flag_text': 'perfil de emergência, declarada sem emergência',
        'limits': ['O nível de emergência é declarado pelo empreendedor; o modelo aprende o que foi declarado, não a verdade de campo.',
                   'Correlação não é causa: o modelo indica parecença de perfil, não instabilidade.',
                   'Não usa DCE (a norma já liga DCE não atestada à emergência), CRI/DPA nem população a jusante.',
                   'Treinado só com barragens inseridas na PNSB, as únicas que declaram nível de emergência.'],
    },
    'dce': {
        'name': 'Falha na próxima declaração de estabilidade', 'version': 'previsao-dce-v1',
        'question': 'Quais barragens com declaração atestada hoje têm o perfil de quem não atestou ou não enviou — e tendem a falhar na próxima campanha (março/2027)?',
        'eligible': lambda r: r.get('pnsb') == 'Sim' and bool(r.get('dce_risr') or r.get('dce_rpsb')), 'label': dce_failed,
        'positive': 'com DCE não atestada ou não enviada', 'flag_text': 'atestada hoje, com perfil de quem falha na DCE',
        'limits': ['Previsão baseada no perfil declarado hoje; a próxima campanha depende de obras e inspeções que ainda vão acontecer.',
                   'Uma única campanha observada: sem série histórica ainda; o ciclo de evolução guarda cada snapshot para medir acerto real na campanha seguinte.',
                   'Não usa o status da DCE nem o nível de emergência como variáveis.',
                   'Serve para priorizar a preparação da campanha, não para concluir sobre estabilidade.'],
    },
}


def _folds(y, folds, seed):
    rnd = random.Random(seed)
    idx_pos = [i for i, t in enumerate(y) if t]
    idx_neg = [i for i, t in enumerate(y) if not t]
    rnd.shuffle(idx_pos)
    rnd.shuffle(idx_neg)
    fold_of = {}
    for k, i in enumerate(idx_pos):
        fold_of[i] = k % folds
    for k, i in enumerate(idx_neg):
        fold_of[i] = k % folds
    return fold_of


def run(records: list[dict], today: date, folds: int = 5, seed: int = 7, target: str = 'emergencia',
        feedback: dict | None = None, l2: float = 0.03, feedback_weight: float = 2.0) -> dict:
    """feedback: {dam_id: 1 (humano confirmou) | 0 (humano rejeitou)} — vira rótulo com peso maior (ciclo de evolução)."""
    import bisect
    T = TARGETS[target]
    feedback = feedback or {}
    recs = [r for r in records if T['eligible'](r)]
    if len(recs) < 50:
        return {'available': False, 'reason': 'Poucos registros para treinar.', 'target': target}
    rows, vocab, labels = featurize(recs, today)
    official = [T['label'](r) for r in recs]
    if sum(official) < 10:
        return {'available': False, 'reason': f"Poucas barragens {T['positive']} para aprender o perfil.", 'target': target}
    # rótulo de treino = oficial, substituído pela conferência humana quando existir
    y = [feedback.get(r['id'], o) for r, o in zip(recs, official)]
    wts = [feedback_weight if r['id'] in feedback else 1.0 for r in recs]
    fold_of = _folds(official, folds, seed)
    oof = [0.0] * len(rows)
    for f in range(folds):
        tr = [i for i in range(len(rows)) if fold_of[i] != f]
        w, b = train([rows[i] for i in tr], [y[i] for i in tr], len(vocab), l2=l2, weights=[wts[i] for i in tr])
        for i in range(len(rows)):
            if fold_of[i] == f:
                oof[i] = predict(w, b, rows[i])
    # métricas sempre contra o rótulo OFICIAL: comparáveis entre versões
    cv_auc = auc(oof, official)
    order = sorted(range(len(rows)), key=lambda i: -oof[i])
    prec = lambda k: sum(official[i] for i in order[:k]) / k
    base_rate = sum(official) / len(official)
    w, b = train(rows, y, len(vocab), l2=l2, weights=wts)
    inv = {i: k for k, i in vocab.items()}
    coefs = sorted(((inv[i], c) for i, c in enumerate(w)), key=lambda kc: -abs(kc[1]))
    group = lambda k: k.split('=', 1)[0]
    gmean: dict[str, float] = {}
    for row in rows:
        for i, v in row:
            gmean[group(inv[i])] = gmean.get(group(inv[i]), 0.0) + w[i] * v / len(rows)
    scored = []
    for r, row, t in zip(recs, rows, official):
        p = predict(w, b, row)
        contrib = sorted(((labels[inv[i]], w[i] * v - gmean[group(inv[i])]) for i, v in row), key=lambda kc: -kc[1])
        scored.append({'id': r['id'], 'p': round(p, 4), 'emergency': t, 'positive': t,
                       'why': [{'feature': k, 'weight': round(c, 2)} for k, c in contrib[:3] if c > 0.05]})
    pos_ps = sorted(s['p'] for s in scored if s['positive'])
    threshold = pos_ps[len(pos_ps) // 4] if pos_ps else 1.0  # 1º quartil dos positivos
    ps_sorted = sorted(s['p'] for s in scored)
    for s in scored:
        s['percentile'] = round(100 * bisect.bisect_right(ps_sorted, s['p']) / len(scored))
        s['hidden_risk'] = (not s['positive']) and s['p'] >= threshold and feedback.get(s['id']) != 0
    flagged = sorted([s for s in scored if s['hidden_risk']], key=lambda s: -s['p'])
    k50 = min(50, len(order))
    return {
        'available': True, 'target': target, 'name': T['name'], 'question': T['question'], 'version': T['version'],
        'trained_on': len(recs), 'positives': sum(official), 'features': len(vocab), 'feedback_used': len(feedback),
        'params': {'l2': l2, 'feedback_weight': feedback_weight, 'folds': folds, 'seed': seed},
        'metrics': {'cv_auc': round(cv_auc, 3), 'precision_top50': round(prec(k50), 3), 'precision_top10': round(prec(10), 3),
                    'base_rate': round(base_rate, 3), 'lift_top50': round(prec(k50) / base_rate, 1) if base_rate else None, 'folds': folds},
        'threshold': round(threshold, 3), 'flagged_total': len(flagged), 'flag_text': T['flag_text'], 'positive_label': T['positive'],
        'top_features': [{'feature': labels[k], 'coef': round(c, 2)} for k, c in coefs[:12]],
        'by_id': {s['id']: s for s in scored}, 'flagged': [s['id'] for s in flagged],
        'method': 'Regressão logística L2 (implementação própria) sobre variáveis técnicas declaradas no SIGBM de barragens na PNSB; validação cruzada estratificada em 5 dobras; conferências humanas entram como rótulo com peso maior.',
        'limits': [*T['limits'], f"Amostra: {sum(official)} casos positivos; resultados variam com novos snapshots."],
    }
