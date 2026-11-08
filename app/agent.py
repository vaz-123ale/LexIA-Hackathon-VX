"""Agente LexIA — agente autônomo de vigilância com aprovação humana.

Ciclo de cada execução (gatilho: início do servidor, novo snapshot, agendamento ou botão):
  1. perceber   — verificar_fontes: snapshots SIGBM/SNISB, idade, mudança desde a última execução
  2. avaliar    — monitorar_modelos: deriva (PSI) e acerto nas conferências humanas
  3. aprender   — retreinar: cria DESAFIANTE quando há dado novo, deriva ou retorno humano suficiente
  4. decidir    — comparar: campeão × desafiante; propõe promoção (nunca promove sozinho)
  5. priorizar  — fila de conferência por valor esperado (probabilidade dos modelos × consequência declarada)
  6. agir       — propor_acoes: cria AÇÕES PENDENTES (conferir, rascunho, promoção). Humano aprova ou rejeita.
  7. relatar    — resumo + notificação

Planejador: com a Claude configurada, o modelo escolhe quais ferramentas chamar (tool use) dentro de um limite de passos;
sem ela, planejador por regras com a mesma lista de ferramentas. Em ambos, as ferramentas só leem dados, treinam
desafiantes ou criam propostas — nenhuma envia nada para fora nem muda o campeão sem humano.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import date
from typing import Any, Callable

from .store import WorkflowError, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, trigger TEXT, planner TEXT, started_at TEXT, finished_at TEXT, steps TEXT, summary TEXT, actions_created INTEGER);
CREATE TABLE IF NOT EXISTS agent_actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, kind TEXT, dam_id TEXT, title TEXT, rationale TEXT, payload TEXT,
  value REAL, state TEXT, created_at TEXT, decided_by TEXT, decided_at TEXT, reason TEXT);
"""
CONSEQ = {'Alta': 2, 'Média': 1}


def consequence_weight(x: dict) -> float:
    c = 1 + CONSEQ.get(x.get('dpa'), 0)
    if any('População' in i for i in x['consequence']['items']):
        c += 2
    return c


class Agent:
    def __init__(self, store, mlops, get_ctx: Callable[[], dict], accounts=None, llm_planner=None):
        self.store, self.mlops, self.get_ctx, self.accounts = store, mlops, get_ctx, accounts
        self.llm_planner = llm_planner
        self.lock = threading.Lock()
        with store.lock:
            store.db.executescript(SCHEMA)
            store.db.commit()

    # ---------------------------------------------------------------- ferramentas
    def tool_verificar_fontes(self, st: dict) -> dict:
        c = self.get_ctx()
        last = self.last_run()
        prev = (json.loads(last['summary']) or {}).get('snapshots') if last and last['summary'] else None
        snaps = {'sigbm': c['sigbm_snapshot'], 'snisb': c['snisb_snapshot']}
        st['snapshots'] = snaps
        st['new_data'] = prev is not None and prev != snaps
        return {'snapshots': snaps, 'registros_sigbm': len(c['records']), 'mudou_desde_ultima_execucao': st['new_data'],
                'primeira_execucao': prev is None}

    def tool_monitorar_modelos(self, st: dict) -> dict:
        c = self.get_ctx()
        out = {}
        for t in ('emergencia', 'dce'):
            m = self.mlops.monitor(t, c['records'])
            out[t] = {k: m.get(k) for k in ('champion_id', 'drift_psi_max', 'drift_status', 'feedback_total', 'field_precision', 'new_feedback_since_champion', 'retrain_recommended')}
        st['monitor'] = out
        return out

    def tool_retreinar(self, st: dict, alvo: str | None = None) -> dict:
        c = self.get_ctx()
        done = {}
        targets = [alvo] if alvo else [t for t, m in (st.get('monitor') or {}).items() if m.get('retrain_recommended') or st.get('new_data')]
        for t in targets:
            if self.mlops.challenger(t):
                done[t] = 'já existe desafiante aguardando decisão'
                continue
            try:
                v = self.mlops.train(t, c['records'], c['today'], c['sigbm_snapshot'], 'agente')
                done[t] = f"desafiante #{v['id']} treinado · AUC {v['metrics']['cv_auc']} · retorno humano usado: {v['feedback_used']}"
            except WorkflowError as exc:
                done[t] = f'não treinado: {exc}'
        if not targets:
            done['motivo'] = 'sem deriva, sem dado novo e sem retorno humano suficiente: retreino desnecessário'
        st['retrained'] = done
        return done

    def tool_comparar(self, st: dict) -> dict:
        out = {}
        for t in ('emergencia', 'dce'):
            cmp = self.mlops.compare(t)
            if cmp:
                out[t] = {'campeao': cmp['champion']['id'], 'desafiante': cmp['challenger']['id'], 'delta_auc': cmp['delta_auc'],
                          'delta_prec50': cmp['delta_prec50'], 'recomendacao': cmp['recommendation']}
        st['compare'] = out
        return out or {'resultado': 'nenhum desafiante pendente'}

    def tool_priorizar(self, st: dict, k: int = 10) -> dict:
        c = self.get_ctx()
        se, sd = self.mlops.scores('emergencia')['by_id'], self.mlops.scores('dce')['by_id']
        q = []
        for x in c['items']:
            if x['kind'] != 'mineracao':
                continue
            e_, d_ = se.get(x['id']), sd.get(x['id'])
            pe = e_['p'] if e_ and not e_['positive'] else 0.0      # risco ainda não declarado
            pd = d_['p'] if d_ and not d_['positive'] else 0.0      # atestada hoje, pode falhar
            p_any = 1 - (1 - pe) * (1 - pd)
            bonus = {'Crítica': 0.25, 'Alta': 0.12}.get(x['attention'], 0)
            value = round(consequence_weight(x) * (p_any + bonus), 3)
            if value <= 0:
                continue
            why = [w['feature'] for w in ((e_ or {}).get('why') or [])[:2]] + [w['feature'] for w in ((d_ or {}).get('why') or [])[:1]]
            q.append({'id': x['id'], 'name': x.get('name'), 'uf': x.get('uf'), 'municipio': x.get('municipio'), 'attention': x['attention'],
                      'p_emergencia_oculta': round(pe, 3), 'p_falha_dce': round(pd, 3), 'p_algum_problema': round(p_any, 3),
                      'peso_consequencia': consequence_weight(x), 'valor': value, 'motivos': list(dict.fromkeys(why))})
        q.sort(key=lambda r: -r['valor'])
        top = q[:k]
        st['queue'] = top
        return {'avaliadas': len(q), 'top': [{k2: r[k2] for k2 in ('id', 'name', 'valor', 'p_algum_problema')} for r in top],
                'problemas_esperados_no_top': round(sum(r['p_algum_problema'] for r in top), 1)}

    def tool_propor_acoes(self, st: dict, maximo: int = 6) -> dict:
        run_id = st['run_id']
        created = []
        pending = {(a['kind'], a['dam_id']) for a in self.actions('PENDENTE')}
        for r in (st.get('queue') or [])[:maximo]:
            if ('conferir', r['id']) in pending:
                continue
            title = f"Conferir {r['name']} ({r['municipio']}/{r['uf']})"
            rationale = (f"Probabilidade de algum problema não declarado {round(100 * r['p_algum_problema'])}% "
                         f"(emergência oculta {round(100 * r['p_emergencia_oculta'])}%, falha na próxima DCE {round(100 * r['p_falha_dce'])}%) "
                         f"× peso de consequência {r['peso_consequencia']}. Motivos: {'; '.join(r['motivos']) or '—'}.")
            created.append(self._new_action(run_id, 'conferir', r['id'], title, rationale, r, r['valor']))
        for t, cmp in (st.get('compare') or {}).items():
            if cmp['recomendacao'].startswith('promover') and ('promover_modelo', f'{t}#{cmp["desafiante"]}') not in pending:
                created.append(self._new_action(run_id, 'promover_modelo', f'{t}#{cmp["desafiante"]}',
                                                f"Promover desafiante #{cmp['desafiante']} ({t})",
                                                f"ΔAUC {cmp['delta_auc']:+} · Δprecisão no topo {cmp['delta_prec50']:+}. Regra: promover só se melhorar; decisão humana.",
                                                cmp, 0))
        st['actions'] = created
        return {'acoes_criadas': len(created), 'tipos': [a['kind'] for a in created]}

    TOOLS = {
        'verificar_fontes': 'Lê os snapshots oficiais (SIGBM/SNISB) e diz se mudaram desde a última execução.',
        'monitorar_modelos': 'Mede deriva dos dados (PSI) e acerto dos modelos nas conferências humanas.',
        'retreinar': 'Treina um DESAFIANTE quando há deriva, dado novo ou retorno humano suficiente. Não muda o campeão.',
        'comparar': 'Compara campeão e desafiante pelas métricas de validação.',
        'priorizar': 'Monta a fila de conferência por valor esperado (probabilidade × consequência).',
        'propor_acoes': 'Cria ações PENDENTES de aprovação humana a partir da fila e da comparação.',
    }

    # ---------------------------------------------------------------- execução
    def run(self, trigger: str = 'manual') -> dict:
        if not self.lock.acquire(blocking=False):
            raise WorkflowError('O agente já está em execução.')
        try:
            with self.store.lock:
                cur = self.store.db.execute('INSERT INTO agent_runs(trigger,planner,started_at) VALUES(?,?,?)', (trigger, 'regras', now()))
                self.store.db.commit()
                run_id = cur.lastrowid
            st: dict[str, Any] = {'run_id': run_id}
            steps = []

            def call(name, **kw):
                fn = getattr(self, f'tool_{name}')
                try:
                    out = fn(st, **kw)
                    steps.append({'tool': name, 'input': kw, 'output': out, 'at': now()})
                except Exception as exc:  # ferramenta falhou: registra e segue
                    out = {'erro': f'{type(exc).__name__}: {exc}'}
                    steps.append({'tool': name, 'input': kw, 'output': out, 'at': now(), 'error': True})
                return out

            planner = 'regras'
            if self.llm_planner:
                try:
                    self.llm_planner(self.TOOLS, call, steps)
                    planner = 'ia'
                except Exception as exc:
                    steps.append({'tool': 'planejador_ia', 'output': {'erro': f'{type(exc).__name__}; usando planejador por regras'}, 'at': now(), 'error': True})
            if planner == 'regras' or not any(s['tool'] == 'propor_acoes' for s in steps):
                for name in ('verificar_fontes', 'monitorar_modelos'):
                    if not any(s['tool'] == name for s in steps):
                        call(name)
                need = st.get('new_data') or any(m.get('retrain_recommended') for m in (st.get('monitor') or {}).values())
                if need:
                    call('retreinar')
                else:
                    steps.append({'tool': 'retreinar', 'skipped': True, 'output': {'motivo': 'sem deriva, sem dado novo e menos de 3 retornos humanos novos'}, 'at': now()})
                call('comparar')
                call('priorizar')
                call('propor_acoes')
            n = len(st.get('actions') or [])
            q = st.get('queue') or []
            summary = {'snapshots': st.get('snapshots'), 'actions_created': n, 'queue_top': [r['id'] for r in q[:10]],
                       'expected_findings_top10': round(sum(r['p_algum_problema'] for r in q[:10]), 1),
                       'text': (f"Analisei {len(self.get_ctx()['records'])} barragens. "
                                f"Fila de conferência: nas 10 primeiras, os modelos esperam ~{round(sum(r['p_algum_problema'] for r in q[:10]), 1)} problemas não declarados. "
                                + (f"Criei {n} proposta(s) nova(s) para aprovação humana." if n else
                                 f"Nenhuma proposta nova: {len(self.actions('PENDENTE'))} ainda aguardam decisão humana."))}
            with self.store.lock:
                self.store.db.execute('UPDATE agent_runs SET finished_at=?, steps=?, summary=?, actions_created=?, planner=? WHERE id=?',
                                      (now(), json.dumps(steps, ensure_ascii=False, default=str), json.dumps(summary, ensure_ascii=False), n, planner, run_id))
                self.store.db.commit()
            self.store.audit('agente', 'agent.run', f'run#{run_id}', {'trigger': trigger, 'planner': planner, 'actions': n})
            if n and self.accounts:
                self.accounts.notify('empresa', 'agente', f'Agente LexIA: {n} proposta(s) aguardando aprovação', summary['text'], '#/ia', 'AGENTE')
            return self.run_detail(run_id)
        finally:
            self.lock.release()

    def _new_action(self, run_id, kind, dam_id, title, rationale, payload, value) -> dict:
        with self.store.lock:
            cur = self.store.db.execute('INSERT INTO agent_actions(run_id,kind,dam_id,title,rationale,payload,value,state,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                        (run_id, kind, dam_id, title, rationale, json.dumps(payload, ensure_ascii=False, default=str), value, 'PENDENTE', now()))
            self.store.db.commit()
            return {'id': cur.lastrowid, 'kind': kind, 'dam_id': dam_id, 'title': title}

    # ---------------------------------------------------------------- decisões humanas
    def decide(self, aid: int, approve: bool, actor: str, reason: str, store_ops: dict) -> dict:
        a = self.action(aid)
        if not a or a['state'] != 'PENDENTE':
            raise WorkflowError('Ação inexistente ou já decidida.')
        if not (reason or '').strip():
            raise WorkflowError('Justificativa obrigatória.')
        effect = None
        if approve:
            if a['kind'] == 'conferir':
                self.store.set_plan_step(a['dam_id'], 'confirmar', 'em_andamento', actor, f'Conferência aceita da proposta do agente #{aid}: {reason}')
                effect = 'Etapa “confirmar” do plano de contingência iniciada.'
            elif a['kind'] == 'promover_modelo':
                vid = int(a['dam_id'].split('#')[1])
                self.mlops.promote(vid, actor, reason)
                effect = f'Desafiante #{vid} promovido a campeão.'
        else:
            if a['kind'] == 'conferir' and store_ops.get('label_rejection'):
                # “não procede” vira rótulo negativo para o próximo treino (fecha o ciclo)
                for t in ('emergencia', 'dce'):
                    self.mlops.add_feedback(t, a['dam_id'], 0, f'Proposta do agente rejeitada: {reason}', actor)
                effect = 'Registrado como “não procede” para os dois modelos (entra no próximo treino).'
            elif a['kind'] == 'promover_modelo':
                self.mlops.discard(int(a['dam_id'].split('#')[1]), actor, reason)
                effect = 'Desafiante descartado.'
        with self.store.lock:
            self.store.db.execute('UPDATE agent_actions SET state=?, decided_by=?, decided_at=?, reason=? WHERE id=?',
                                  ('APROVADA' if approve else 'REJEITADA', actor, now(), reason, aid))
            self.store.db.commit()
        self.store.audit(actor, 'agent.decide', f'action#{aid}', {'approve': approve, 'reason': reason, 'effect': effect})
        return {**self.action(aid), 'effect': effect}

    # ---------------------------------------------------------------- consulta
    def action(self, aid: int) -> dict | None:
        with self.store.lock:
            r = self.store.db.execute('SELECT * FROM agent_actions WHERE id=?', (aid,)).fetchone()
        return {**dict(r), 'payload': json.loads(r['payload'])} if r else None

    def actions(self, state: str | None = None, limit: int = 100) -> list[dict]:
        q = 'SELECT * FROM agent_actions' + (' WHERE state=?' if state else '') + ' ORDER BY id DESC LIMIT ?'
        with self.store.lock:
            rows = self.store.db.execute(q, ((state, limit) if state else (limit,))).fetchall()
        return [{**dict(r), 'payload': json.loads(r['payload'])} for r in rows]

    def last_run(self) -> dict | None:
        with self.store.lock:
            r = self.store.db.execute('SELECT * FROM agent_runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 1').fetchone()
        return dict(r) if r else None

    def runs(self, limit: int = 20) -> list[dict]:
        with self.store.lock:
            rows = self.store.db.execute('SELECT id,trigger,planner,started_at,finished_at,summary,actions_created FROM agent_runs ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [{**dict(r), 'summary': json.loads(r['summary']) if r['summary'] else None} for r in rows]

    def run_detail(self, run_id: int) -> dict:
        with self.store.lock:
            r = self.store.db.execute('SELECT * FROM agent_runs WHERE id=?', (run_id,)).fetchone()
        d = dict(r)
        d['steps'] = json.loads(d['steps'] or '[]')
        d['summary'] = json.loads(d['summary']) if d['summary'] else None
        return d


def gemini_planner_factory():
    """Planejador com Gemini (function calling). Mesmas ferramentas e mesmos limites do planejador com Claude."""
    from .cloud_aws import gemini_request

    def planner(tools: dict, call, steps: list) -> None:
        decl = [{'name': n, 'description': d} for n, d in tools.items()]
        contents = [{'role': 'user', 'parts': [{'text': ('Você é o Agente LexIA. Execute um ciclo de vigilância regulatória de barragens chamando as ferramentas, '
                                                         'uma de cada vez. Sempre termine chamando propor_acoes. Não invente dados; use só as saídas das ferramentas. '
                                                         'Ao final, escreva uma frase de resumo em português.')}]}]
        for _ in range(10):
            d = gemini_request({'contents': contents, 'tools': [{'functionDeclarations': decl}]})
            parts = ((d.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []
            contents.append({'role': 'model', 'parts': parts})
            calls = [p['functionCall'] for p in parts if 'functionCall' in p]
            if not calls:
                break
            responses = []
            for fc in calls:
                name = fc.get('name')
                out = call(name) if name in tools else {'erro': 'ferramenta não permitida'}
                responses.append({'functionResponse': {'name': name, 'response': {'resultado': json.loads(json.dumps(out, ensure_ascii=False, default=str)[:6000]) if len(json.dumps(out, default=str)) <= 6000 else {'resumo': str(out)[:6000]}}}})
            contents.append({'role': 'user', 'parts': responses})
    return planner


def claude_planner_factory():
    """Planejador com Claude (tool use). Só é usado se o pacote e a chave existirem."""
    from .cloud_aws import make_client, model_name
    client = make_client()
    model = model_name()

    def planner(tools: dict, call, steps: list) -> None:
        defs = [{'name': n, 'description': d, 'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False}} for n, d in tools.items()]
        msgs = [{'role': 'user', 'content': ('Você é o Agente LexIA. Execute um ciclo de vigilância regulatória de barragens usando as ferramentas. '
                                             'Sempre termine chamando propor_acoes. Não invente dados; use apenas as saídas das ferramentas. '
                                             'Ao final, escreva uma frase de resumo em português.')}]
        for _ in range(10):
            r = client.messages.create(model=model, max_tokens=1500, tools=defs, messages=msgs)
            msgs.append({'role': 'assistant', 'content': r.content})
            uses = [b for b in r.content if b.type == 'tool_use']
            if not uses:
                break
            results = []
            for u in uses:
                if u.name not in tools:
                    out = {'erro': 'ferramenta não permitida'}
                else:
                    out = call(u.name)
                results.append({'type': 'tool_result', 'tool_use_id': u.id, 'content': json.dumps(out, ensure_ascii=False, default=str)[:6000]})
            msgs.append({'role': 'user', 'content': results})
    return planner
