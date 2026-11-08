"""Ciclo de evolução dos modelos (MLOps leve, só biblioteca padrão).

dados (snapshot oficial) → treino → validação → registro de versão → implantação (campeão)
→ monitoramento (deriva + acerto nas conferências humanas) → retorno humano → retreino (desafiante)
→ comparação campeão × desafiante → promoção SOMENTE com aprovação humana → …

- Cada versão guarda: alvo, snapshot, parâmetros, métricas de validação cruzada, quantidade de retorno humano usado,
  pontuações por barragem (para servir sem retreinar) e quem promoveu.
- Métricas sempre contra o rótulo oficial do snapshot: comparáveis entre versões.
- Retorno humano: "confirmo" (1) / "não procede" (0) por barragem e modelo; entra no próximo treino com peso maior.
- Deriva: PSI (índice de estabilidade populacional) das variáveis categóricas entre o snapshot de treino e o atual.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import date
from typing import Any

from . import risk_model
from .store import WorkflowError, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, version TEXT, status TEXT, snapshot_id TEXT, created_at TEXT,
  created_by TEXT, params TEXT, metrics TEXT, feedback_used INTEGER, flagged_total INTEGER, scores TEXT, summary TEXT,
  feature_profile TEXT, promoted_by TEXT, promoted_at TEXT, promote_reason TEXT);
CREATE TABLE IF NOT EXISTS model_feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, target TEXT, dam_id TEXT, label INTEGER, reason TEXT, actor TEXT, at TEXT,
  model_version_id INTEGER);
"""
_TRAIN_CACHE: dict = {}


def feature_profile(records: list[dict], target: str) -> dict:
    T = risk_model.TARGETS[target]
    recs = [r for r in records if T['eligible'](r)]
    prof = {}
    for f in risk_model.CATEGORICAL:
        c = Counter(risk_model._cat(f, r.get(f)) or '(não informado)' for r in recs)
        prof[f] = {k: v / max(1, len(recs)) for k, v in c.items()}
    return prof


def psi(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    eps = 1e-4
    return sum((b.get(k, eps) - a.get(k, eps)) * math.log(max(b.get(k, eps), eps) / max(a.get(k, eps), eps)) for k in keys)


class MLOps:
    def __init__(self, store):
        self.store = store
        with store.lock:
            store.db.executescript(SCHEMA)
            store.db.commit()

    # ---------------------------------------------------------------- treino e registro
    def feedback_map(self, target: str) -> dict[str, int]:
        with self.store.lock:
            rows = self.store.db.execute('SELECT dam_id, label FROM model_feedback WHERE target=? ORDER BY id', (target,)).fetchall()
        return {r['dam_id']: int(r['label']) for r in rows}  # o último retorno vale

    def train(self, target: str, records: list[dict], today: date, snapshot_id: str | None, actor: str, l2: float = 0.03) -> dict:
        fb = self.feedback_map(target)
        key = (target, snapshot_id, len(records), json.dumps(sorted(fb.items())), l2)
        if key not in _TRAIN_CACHE:
            _TRAIN_CACHE[key] = risk_model.run(records, today, target=target, feedback=fb, l2=l2)
        res = _TRAIN_CACHE[key]
        if not res.get('available'):
            raise WorkflowError(res.get('reason', 'Treino indisponível.'))
        summary = {k: res[k] for k in ('name', 'question', 'trained_on', 'positives', 'features', 'threshold', 'top_features', 'method',
                                       'limits', 'flag_text', 'positive_label', 'flagged')}
        champion = self.champion(target)
        status = 'campeao' if champion is None else 'desafiante'
        with self.store.lock:
            cur = self.store.db.execute(
                'INSERT INTO model_versions(target,version,status,snapshot_id,created_at,created_by,params,metrics,feedback_used,flagged_total,scores,summary,feature_profile,promoted_by,promoted_at,promote_reason) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (target, res['version'], status, snapshot_id, now(), actor, json.dumps(res['params']), json.dumps(res['metrics']), len(fb),
                 res['flagged_total'], json.dumps(res['by_id']), json.dumps(summary, ensure_ascii=False),
                 json.dumps(feature_profile(records, target)), 'sistema (versão inicial)' if status == 'campeao' else None,
                 now() if status == 'campeao' else None, 'Primeira versão treinada' if status == 'campeao' else None))
            self.store.db.commit()
            vid = cur.lastrowid
        self.store.audit(actor, 'model.train', f'{target}#{vid}', {'status': status, 'metrics': res['metrics'], 'feedback_used': len(fb),
                                                                  'snapshot_id': snapshot_id, 'digest': hashlib.sha256(json.dumps(res['by_id'], sort_keys=True).encode()).hexdigest()[:16]})
        return self.version(vid)

    def bootstrap(self, records: list[dict], today: date, snapshot_id: str | None) -> None:
        for t in risk_model.TARGETS:
            if self.champion(t) is None:
                try:
                    self.train(t, records, today, snapshot_id, 'sistema')
                except WorkflowError:
                    pass

    # ---------------------------------------------------------------- consulta
    def _row(self, r, full=False) -> dict:
        d = {k: r[k] for k in r.keys() if k not in ('scores', 'feature_profile')}
        for k in ('params', 'metrics', 'summary'):
            d[k] = json.loads(d[k]) if d[k] else None
        if full:
            d['scores'] = json.loads(r['scores'])
            d['feature_profile'] = json.loads(r['feature_profile'])
        return d

    def version(self, vid: int, full: bool = False) -> dict | None:
        with self.store.lock:
            r = self.store.db.execute('SELECT * FROM model_versions WHERE id=?', (vid,)).fetchone()
        return self._row(r, full) if r else None

    def versions(self, target: str | None = None) -> list[dict]:
        with self.store.lock:
            rows = self.store.db.execute('SELECT * FROM model_versions' + (' WHERE target=?' if target else '') + ' ORDER BY id DESC',
                                         (target,) if target else ()).fetchall()
        return [self._row(r) for r in rows]

    def champion(self, target: str, full: bool = False) -> dict | None:
        with self.store.lock:
            r = self.store.db.execute("SELECT * FROM model_versions WHERE target=? AND status='campeao' ORDER BY id DESC LIMIT 1", (target,)).fetchone()
        return self._row(r, full) if r else None

    def challenger(self, target: str) -> dict | None:
        with self.store.lock:
            r = self.store.db.execute("SELECT * FROM model_versions WHERE target=? AND status='desafiante' ORDER BY id DESC LIMIT 1", (target,)).fetchone()
        return self._row(r) if r else None

    # ---------------------------------------------------------------- retorno humano
    def add_feedback(self, target: str, dam_id: str, label: int, reason: str, actor: str) -> dict:
        if target not in risk_model.TARGETS:
            raise WorkflowError('Modelo inexistente.')
        if label not in (0, 1):
            raise WorkflowError('Retorno inválido.')
        if not (reason or '').strip():
            raise WorkflowError('Explique o que foi conferido (evidência).')
        ch = self.champion(target)
        with self.store.lock:
            self.store.db.execute('INSERT INTO model_feedback(target,dam_id,label,reason,actor,at,model_version_id) VALUES(?,?,?,?,?,?,?)',
                                  (target, dam_id, label, reason[:500], actor, now(), ch and ch['id']))
            self.store.db.commit()
        self.store.audit(actor, 'model.feedback', dam_id, {'target': target, 'label': label, 'reason': reason[:200]})
        return {'target': target, 'dam_id': dam_id, 'label': label}

    def feedback_list(self, target: str | None = None, dam_id: str | None = None) -> list[dict]:
        q, a = 'SELECT * FROM model_feedback WHERE 1=1', []
        if target:
            q += ' AND target=?'; a.append(target)
        if dam_id:
            q += ' AND dam_id=?'; a.append(dam_id)
        with self.store.lock:
            return [dict(r) for r in self.store.db.execute(q + ' ORDER BY id DESC LIMIT 200', a).fetchall()]

    # ---------------------------------------------------------------- monitoramento e promoção
    def monitor(self, target: str, records: list[dict]) -> dict:
        ch = self.champion(target, full=True)
        if not ch:
            return {'available': False}
        now_prof = feature_profile(records, target)
        drift = {f: round(psi(ch['feature_profile'].get(f, {}), now_prof.get(f, {})), 4) for f in now_prof}
        worst = max(drift.values()) if drift else 0
        fb = [f for f in self.feedback_list(target) if f['model_version_id'] == ch['id']]
        flagged = set(ch['summary']['flagged'])
        on_flag = [f for f in fb if f['dam_id'] in flagged]
        hits = sum(f['label'] for f in on_flag)
        new_fb = len(self.feedback_map(target)) - (ch['feedback_used'] or 0)
        return {'available': True, 'champion_id': ch['id'], 'drift_psi_max': round(worst, 4), 'drift_by_feature': drift,
                'drift_status': 'estável' if worst < 0.1 else 'atenção' if worst < 0.25 else 'deriva forte',
                'feedback_total': len(fb), 'feedback_on_flagged': len(on_flag), 'field_precision': round(hits / len(on_flag), 3) if on_flag else None,
                'new_feedback_since_champion': max(0, new_fb),
                'retrain_recommended': worst >= 0.1 or new_fb >= 3,
                'reading': 'PSI < 0,1 estável · 0,1–0,25 atenção · > 0,25 deriva forte. Precisão de campo = conferências humanas que confirmaram o alerta.'}

    def compare(self, target: str) -> dict | None:
        ch, cd = self.champion(target), self.challenger(target)
        if not ch or not cd:
            return None
        a, b = ch['metrics'], cd['metrics']
        better = b['cv_auc'] >= a['cv_auc'] + 0.005 and b['precision_top50'] >= a['precision_top50'] - 0.02
        tie = abs(b['cv_auc'] - a['cv_auc']) < 0.005
        return {'champion': ch, 'challenger': cd, 'delta_auc': round(b['cv_auc'] - a['cv_auc'], 3),
                'delta_prec50': round(b['precision_top50'] - a['precision_top50'], 3),
                'recommendation': 'promover' if better else ('promover se o retorno humano for relevante' if tie and cd['feedback_used'] > ch['feedback_used'] else 'manter campeão'),
                'rule': 'Promover só se AUC subir ≥ 0,005 sem perder mais de 2 p.p. de precisão no topo; decisão final é humana.'}

    def promote(self, vid: int, actor: str, reason: str) -> dict:
        v = self.version(vid)
        if not v or v['status'] != 'desafiante':
            raise WorkflowError('Só um desafiante pode ser promovido.')
        if not (reason or '').strip():
            raise WorkflowError('Justificativa obrigatória.')
        with self.store.lock:
            self.store.db.execute("UPDATE model_versions SET status='aposentado' WHERE target=? AND status='campeao'", (v['target'],))
            self.store.db.execute("UPDATE model_versions SET status='campeao', promoted_by=?, promoted_at=?, promote_reason=? WHERE id=?", (actor, now(), reason, vid))
            self.store.db.commit()
        self.store.audit(actor, 'model.promote', f"{v['target']}#{vid}", {'reason': reason, 'metrics': v['metrics']})
        return self.version(vid)

    def discard(self, vid: int, actor: str, reason: str) -> dict:
        v = self.version(vid)
        if not v or v['status'] != 'desafiante':
            raise WorkflowError('Só um desafiante pode ser descartado.')
        with self.store.lock:
            self.store.db.execute("UPDATE model_versions SET status='descartado', promote_reason=? WHERE id=?", (reason, vid))
            self.store.db.commit()
        self.store.audit(actor, 'model.discard', f"{v['target']}#{vid}", {'reason': reason})
        return self.version(vid)

    def scores(self, target: str) -> dict:
        ch = self.champion(target, full=True)
        return {'version': ch, 'by_id': ch['scores'] if ch else {}}
