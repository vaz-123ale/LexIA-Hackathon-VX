"""Agente de alertas jurídicos e compliance (determinístico; nenhuma chamada de IA generativa).

Fontes dos alertas:
1. Obrigações cadastradas pela organização (data/obrigacoes.json): vencidas, perto do vencimento, documento desatualizado.
2. Barragens oficiais acompanhadas pela organização (SIGBM/ANM + SNISB/ANA): DCE não enviada/não atestada, PAE exigido
   e ausente, inspeção antiga, nível de emergência declarado.
Cada alerta traz: risco × urgência → nível, base legal (catálogo fixo), consequências possíveis (texto do catálogo, sem
inventar valor), ação recomendada, responsáveis e status com histórico. Situação de SEGURANÇA é sinalizada para tratamento
imediato. Nenhum envio externo: os avisos vão para o sino da plataforma, para a área responsável.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from .abandono import ARTICLES, LAW, LAW_URL
from .store import WorkflowError, now

ROOT = Path(__file__).resolve().parents[1]
RULE_VERSION = 'compliance-v1'

CATALOG = {
    **{k: {'ref': f"{LAW} — {v['ref']}", 'text': v['text'], 'url': v.get('url', LAW_URL)} for k, v in ARTICLES.items()},
    'res95': {'ref': 'Resolução ANM 95/2022 (texto consolidado)', 'text': 'Obrigações de segurança de barragens de mineração: inspeções (EIR), DCE, revisão periódica, PAEBM e cadastro no SIGBM.',
              'url': 'https://www.gov.br/anm/pt-br/assuntos/barragens/legislacao/resolucao-no-95-2022.pdf'},
    'aviso_eir': {'ref': 'Aviso ANM de 16/04/2026', 'text': 'Prazo excepcional do EIR das inspeções de 16 a 31/03/2026: de 15/04 para 23/04/2026.',
                  'url': 'https://www.gov.br/anm/pt-br/assuntos/noticias/alteracao-de-dominio-do-sigbm-e-prorrogacao-do-prazo-para-envio-de-eir'},
    'res223': {'ref': 'Resolução ANM 223/2025, art. 26, §2º, VII', 'text': 'Classifica a falta de envio da DCE do Relatório de Inspeção Regular como infração (grupo VI-2); o valor depende da produção mineral e das circunstâncias.',
               'url': 'https://www.gov.br/anm/pt-br/assuntos/barragens/legislacao'},
    'condicionante': {'ref': 'Condicionantes da licença ambiental', 'text': 'Prazos e exigências da própria licença emitida pelo órgão ambiental competente.', 'url': ''},
    'cnen_nn401': {'ref': 'Norma CNEN NN 4.01 — instalações mínero-industriais', 'text': 'Requisitos de segurança e proteção radiológica para minerações e beneficiamentos com material radioativo associado (conferir a versão vigente na autoridade nuclear).',
                   'url': 'https://www.gov.br/cnen/pt-br/acesso-rapido/normas'},
    'lei14222': {'ref': 'Lei 14.222/2021 (ANSN)', 'text': 'Cria a Autoridade Nacional de Segurança Nuclear, que regula, licencia e fiscaliza atividades nucleares e com fontes de radiação.',
                 'url': 'https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14222.htm'},
    'cf_nuclear': {'ref': 'Constituição Federal, art. 21, XXIII, e art. 177, V', 'text': 'Monopólio da União sobre minérios e minerais nucleares; atividades nucleares sob controle federal.',
                   'url': 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm'},
    **__import__('app.normas_setor', fromlist=['NOVAS']).NOVAS,
    'nr20': {'ref': 'NR-20 (MTE)', 'text': 'Segurança e saúde no trabalho com inflamáveis e combustíveis: prontuário da instalação.', 'url': 'https://www.gov.br/trabalho-e-emprego/pt-br'},
}

CONSEQ = {
    'dce': 'DCE não enviada é infração classificada pela ANM (Res. 223/2025, grupo VI-2); DCE não atestada leva a barragem a nível de emergência e pode resultar em embargo (nas campanhas de 2026 houve 76 embargos). Valor de multa depende de apuração.',
    'eir': 'Falta do EIR no prazo pode gerar exigência, auto de infração e sanção administrativa da ANM, conforme apuração.',
    'rpsb': 'Revisão periódica vencida é descumprimento de obrigação de segurança; pode resultar em fiscalização, autuação e exigências técnicas.',
    'pae': 'PAEBM desatualizado ou sem cópias com a Defesa Civil compromete a resposta a emergências; pode gerar autuação e, em omissão, atuação da Defesa Civil com custos ao empreendedor (Lei 12.334, art. 18, §2º).',
    'licenca': 'Operar com licença vencida pode levar a auto de infração, multa e embargo pelo órgão ambiental, conforme a legislação estadual.',
    'documento': 'Documento desatualizado pode gerar notificação e exigência em fiscalização.',
    'emergencia': 'Nível de emergência declarado exige execução do PAEBM e comunicação às autoridades; é situação de segurança, não apenas documental.',
    'inspecao': 'Inspeção antiga sem registro recente reduz a capacidade de comprovar a segurança e pode motivar fiscalização.',
}
ACTION = {
    'dce': 'Acionar o responsável técnico para preparar a DCE, conferir a campanha vigente e anexar o protocolo do SIGBM.',
    'eir': 'Localizar o protocolo do EIR no SIGBM e anexar; se não houver, enviar e registrar a pendência ao jurídico.',
    'rpsb': 'Contratar ou agendar a revisão periódica, registrar o cronograma e informar o jurídico.',
    'pae': 'Revisar o PAEBM (contatos, mancha, rotas) e protocolar as cópias na prefeitura e na Defesa Civil.',
    'licenca': 'Protocolar a renovação junto ao órgão ambiental com antecedência e anexar o comprovante.',
    'documento': 'Solicitar a revisão do documento e anexar a nova versão.',
    'emergencia': 'Tratar imediatamente: confirmar com o responsável técnico, executar o PAEBM e comunicar autoridades conforme o plano.',
    'inspecao': 'Agendar inspeção e anexar o relatório.',
}
ROLES = {'geotecnia': 'Geotecnia / responsável técnico', 'compliance': 'Compliance', 'juridico': 'Jurídico', 'meio_ambiente': 'Meio ambiente', 'engenharia': 'Engenharia'}
TYPE_RISK = {'dce': 3, 'eir': 2, 'rpsb': 3, 'pae': 3, 'licenca': 2, 'documento': 1, 'emergencia': 4, 'inspecao': 2}
LEVEL_ORDER = {'Crítico': 0, 'Alto': 1, 'Médio': 2, 'Baixo': 3}

SCHEMA = """
CREATE TABLE IF NOT EXISTS compliance_alerts(
  id TEXT PRIMARY KEY, org TEXT, payload TEXT, status TEXT, level TEXT, regularize_by TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS compliance_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id TEXT, at TEXT, actor TEXT, action TEXT, note TEXT);
"""


def urgency(days: int | None) -> tuple[str, int]:
    if days is None:
        return 'Sem prazo', 0
    if days < 0:
        return 'Vencido', 3
    if days <= 30:
        return 'Até 30 dias', 2
    if days <= 90:
        return 'Até 90 dias', 1
    return 'Mais de 90 dias', 0


def level(risk: int, urg: int, safety: bool) -> str:
    if safety and urg >= 3:
        return 'Crítico'
    s = risk + urg
    return 'Crítico' if s >= 6 else 'Alto' if s >= 4 else 'Médio' if s >= 3 else 'Baixo'


def _alert(aid, kind, asset_id, asset_name, title, detail, base, days, due, resp, safety, origin, evidence=None, extra=None):
    urg_label, urg = urgency(days)
    lvl = 'Crítico' if kind == 'emergencia' else level(TYPE_RISK.get(kind, 1), urg, safety)
    return {'id': aid, 'kind': kind, 'asset_id': asset_id, 'asset_name': asset_name, 'title': title, 'detail': detail,
            'level': lvl, 'urgency': urg_label, 'days_to_due': days, 'due': due, 'safety': bool(safety), 'origin': origin,
            'basis': [{'key': k, **CATALOG[k]} for k in base if k in CATALOG], 'consequences': CONSEQ.get(kind, CONSEQ['documento']),
            'action': ACTION.get(kind, ACTION['documento']), 'responsibles': [ROLES.get(resp, resp), 'Jurídico', 'Compliance'],
            'evidence': evidence, 'rule_version': RULE_VERSION, **(extra or {})}


def build(today: date, assets: list[dict], official_watched: list[dict], radar_by_id: dict, obligations: dict | None = None) -> list[dict]:
    obligations = obligations or json.loads((ROOT / 'data' / 'obrigacoes.json').read_text(encoding='utf8'))
    names = {a['id']: a['name'] for a in assets}
    out = []
    for o in obligations['itens']:
        due = date.fromisoformat(o['vencimento']) if o.get('vencimento') else None
        days = (due - today).days if due else None
        stale = None
        if o.get('ultimo_documento'):
            age = (today - date.fromisoformat(o['ultimo_documento'])).days
            stale = age
        if o.get('evidencia') and days is not None and days > 90:
            continue  # em dia, com evidência e longe do prazo: sem alerta
        if days is not None and days < 0 and not o.get('evidencia'):
            detail = f"Prazo vencido há {-days} dia(s) ({due.strftime('%d/%m/%Y')}) e sem evidência de cumprimento anexada."
        elif days is not None and days <= 90:
            detail = f"Vence em {days} dia(s) ({due.strftime('%d/%m/%Y')})." + ('' if o.get('evidencia') else ' Ainda sem evidência anexada.')
        else:
            detail = f"Próximo vencimento em {due.strftime('%d/%m/%Y')}."
        if stale and stale > 365:
            detail += f" Último documento tem {stale // 30} meses: informação possivelmente desatualizada."
        out.append(_alert(o['id'], o['tipo'], o['ativo'], names.get(o['ativo'], o['ativo']), o['titulo'], detail, o['base'], days,
                          o.get('vencimento'), o['responsavel'], o['seguranca'], o['origem'], o.get('evidencia'), {'source': 'Cadastro da organização (fictícia)'}))
    for r in official_watched:
        x = radar_by_id.get(r['id']) or {}
        nm = r.get('name') or r['id']
        dce = f"{r.get('dce_risr') or ''} {r.get('dce_rpsb') or ''}"
        if r.get('emergency_level') and r['emergency_level'] != 'Sem emergência':
            out.append(_alert(f"SIGBM-EMERG-{r['id']}", 'emergencia', r['id'], nm, f"Nível declarado: {r['emergency_level']}",
                              'A própria ANM publica esta estrutura com nível de emergência declarado.', ['art4_iii', 'art18_p2', 'res95'], 0, None,
                              'geotecnia', True, 'SIGBM/ANM (dado oficial)', extra={'source': 'SIGBM/ANM'}))
        if 'Não Enviado' in dce:
            out.append(_alert(f"SIGBM-DCE-NE-{r['id']}", 'dce', r['id'], nm, 'Declaração de estabilidade não enviada na última campanha',
                              f'Status na ANM: {dce.strip()}.', ['res95', 'res223', 'art4_iii'], -1, None, 'geotecnia', True, 'SIGBM/ANM (dado oficial)', extra={'source': 'SIGBM/ANM'}))
        elif 'Não Atestado' in dce:
            out.append(_alert(f"SIGBM-DCE-NA-{r['id']}", 'dce', r['id'], nm, 'Estabilidade não atestada na última campanha',
                              f'Status na ANM: {dce.strip()}.', ['res95', 'art18', 'art4_iii'], -1, None, 'geotecnia', True, 'SIGBM/ANM (dado oficial)', extra={'source': 'SIGBM/ANM'}))
        if (r.get('pae_status') or '').startswith('Não possui PAE (quando for exigido'):
            out.append(_alert(f"SIGBM-PAE-{r['id']}", 'pae', r['id'], nm, 'PAE exigido e não declarado', r['pae_status'], ['res95', 'art4_iii'], -1, None,
                              'compliance', True, 'SIGBM/ANM (dado oficial)', extra={'source': 'SIGBM/ANM'}))
        sn = (x.get('snisb') or {})
        if sn.get('last_inspection'):
            age = (today - date.fromisoformat(sn['last_inspection'])).days
            if age > 3 * 365:
                out.append(_alert(f"SNISB-INSP-{r['id']}", 'inspecao', r['id'], nm, f"Última inspeção registrada há {age // 365} anos",
                                  f"Data no SNISB: {sn['last_inspection']}.", ['res95', 'art17a_p3'], 30, None, 'geotecnia', False, 'SNISB/ANA (dado oficial)', extra={'source': 'SNISB/ANA'}))
    out.sort(key=lambda a: (LEVEL_ORDER[a['level']], a['days_to_due'] if a['days_to_due'] is not None else 9999))
    return out


class ComplianceDesk:
    def __init__(self, store):
        self.store = store
        with store.lock:
            store.db.executescript(SCHEMA)
            store.db.commit()

    def _event(self, aid, actor, action, note=''):
        with self.store.lock:
            self.store.db.execute('INSERT INTO compliance_events(alert_id,at,actor,action,note) VALUES(?,?,?,?,?)', (aid, now(), actor, action, note[:500]))
            self.store.db.commit()

    def sync(self, alerts: list[dict], org: str, notify=None) -> dict:
        """Grava alertas novos, atualiza conteúdo dos existentes, escala prazos de regularização vencidos. Idempotente."""
        created, escalated = [], []
        today = date.today().isoformat()
        with self.store.lock:
            existing = {r['id']: dict(r) for r in self.store.db.execute('SELECT * FROM compliance_alerts WHERE org=?', (org,))}
        for a in alerts:
            if a['id'] not in existing:
                with self.store.lock:
                    self.store.db.execute('INSERT INTO compliance_alerts(id,org,payload,status,level,regularize_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                                          (a['id'], org, json.dumps(a, ensure_ascii=False), 'ABERTO', a['level'], None, now(), now()))
                    self.store.db.commit()
                self._event(a['id'], 'agente-compliance', 'criado', f"Nível {a['level']} · {a['urgency']}")
                created.append(a)
            else:
                old = existing[a['id']]
                with self.store.lock:
                    self.store.db.execute('UPDATE compliance_alerts SET payload=?, level=?, updated_at=? WHERE id=?', (json.dumps(a, ensure_ascii=False), a['level'], now(), a['id']))
                    self.store.db.commit()
                if old['status'] == 'EM_REGULARIZACAO' and old['regularize_by'] and old['regularize_by'] < today:
                    self._event(a['id'], 'agente-compliance', 'escalado', f"Prazo de regularização ({old['regularize_by']}) vencido sem resolução.")
                    escalated.append(a)
        if notify:
            crit = [a for a in created if a['level'] in ('Crítico', 'Alto')]
            if crit:
                notify('empresa', 'compliance', f'Compliance: {len(crit)} alerta(s) crítico(s)/alto(s) novo(s)',
                       '; '.join(f"{a['asset_name']}: {a['title']}" for a in crit[:3]), '#/compliance', 'COMPLIANCE')
            if escalated:
                notify('empresa', 'compliance', f'Compliance: {len(escalated)} regularização(ões) com prazo vencido',
                       '; '.join(a['title'] for a in escalated[:3]), '#/compliance', 'COMPLIANCE')
        return {'novos': len(created), 'escalados': len(escalated), 'total': len(alerts)}

    def list(self, org: str) -> list[dict]:
        with self.store.lock:
            rows = [dict(r) for r in self.store.db.execute('SELECT * FROM compliance_alerts WHERE org=?', (org,))]
        out = []
        for r in rows:
            a = json.loads(r['payload'])
            a.update(status=r['status'], regularize_by=r['regularize_by'], created_at=r['created_at'], updated_at=r['updated_at'])
            out.append(a)
        st = {'ABERTO': 0, 'EM_REGULARIZACAO': 1, 'RESOLVIDO': 3, 'DESCARTADO': 4}
        out.sort(key=lambda a: (st.get(a['status'], 2), LEVEL_ORDER[a['level']], a['days_to_due'] if a['days_to_due'] is not None else 9999))
        return out

    def history(self, aid: str) -> list[dict]:
        with self.store.lock:
            return [dict(r) for r in self.store.db.execute('SELECT * FROM compliance_events WHERE alert_id=? ORDER BY id', (aid,))]

    def transition(self, aid: str, to: str, actor: str, role: str, note: str = '', regularize_by: str | None = None) -> dict:
        with self.store.lock:
            r = self.store.db.execute('SELECT * FROM compliance_alerts WHERE id=?', (aid,)).fetchone()
        if not r:
            raise WorkflowError('Alerta não encontrado.')
        cur = r['status']
        allowed = {'ABERTO': {'EM_REGULARIZACAO', 'DESCARTADO'}, 'EM_REGULARIZACAO': {'RESOLVIDO', 'ABERTO'}, 'RESOLVIDO': {'ABERTO'}, 'DESCARTADO': {'ABERTO'}}
        if to not in allowed.get(cur, set()):
            raise WorkflowError(f'Transição {cur} → {to} não permitida.')
        if to == 'EM_REGULARIZACAO' and not regularize_by:
            raise WorkflowError('Informe o prazo de regularização.')
        if to == 'RESOLVIDO' and not note.strip():
            raise WorkflowError('Para resolver, registre a evidência (protocolo, documento, número do processo).')
        if to == 'DESCARTADO' and (role not in ('juridico', 'compliance') or not note.strip()):
            raise WorkflowError('Descartar exige jurídico ou compliance e justificativa.')
        with self.store.lock:
            self.store.db.execute('UPDATE compliance_alerts SET status=?, regularize_by=COALESCE(?, regularize_by), updated_at=? WHERE id=?', (to, regularize_by, now(), aid))
            self.store.db.commit()
        self._event(aid, actor, f'{cur} → {to}', (f'Prazo: {regularize_by}. ' if regularize_by else '') + note)
        self.store.audit(actor, 'compliance.transition', aid, {'from': cur, 'to': to, 'note': note[:200], 'regularize_by': regularize_by})
        return {'id': aid, 'status': to}
