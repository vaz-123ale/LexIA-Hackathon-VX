"""Motor multissetorial de ativos (configuração em data/setores.json + cadastro de cada empresa).

O mesmo código atende mineração, energia, saneamento e indústria: muda só a configuração.
Para cada ativo, por REGRA (sem IA generativa, custo zero):
- documentos: vencido / até 30 dias / até 90 dias / em dia;
- indicadores: leitura atual contra limites configurados e z-score robusto contra o histórico do próprio ativo;
- radiológico: ativo marcado como radioativo exige autorização da autoridade nuclear e leitura de dose dentro do limite.
Cada ocorrência vira um alerta com tipo, nível, base, ação e DESTINATÁRIOS (roteamento por papel configurado na empresa):
a informação certa para a pessoa certa, sem notificar quem não precisa.
"""
from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE_VERSION = 'ativos-v1'
LEVEL_ORDER = {'Crítico': 0, 'Alto': 1, 'Médio': 2, 'Baixo': 3}
STATUS = {'Crítico': 'critico', 'Alto': 'pendencia', 'Médio': 'pendencia', 'Baixo': 'normal'}


def load(root: Path = ROOT) -> tuple[dict, dict]:
    return (json.loads((root / 'data' / 'setores.json').read_text(encoding='utf8')),
            json.loads((root / 'data' / 'empresas_demo.json').read_text(encoding='utf8')))


def _z(vals):
    if not vals or len(vals) < 6:
        return None
    hist, cur = vals[:-3], vals[-1]
    med = statistics.median(hist)
    mad = statistics.median(abs(v - med) for v in hist) or (statistics.pstdev(hist) or 0)
    return None if not mad else round((cur - med) / (1.4826 * mad), 1)


def _doc_level(days, radiological=False):
    if days is None:
        return None
    if days < 0:
        return 'Crítico' if radiological else 'Alto'
    if days <= 30:
        return 'Alto' if radiological else 'Médio'
    if days <= 90:
        return 'Baixo'
    return None


ESCALA = ['compliance', 'gestor']   # se o papel não tem pessoa: sobe para compliance, depois gestão, depois curadoria


def recipients(company: dict, cfg: dict, occ: str, pessoas: set | None = None) -> list[dict]:
    """Destinatários por papel. pessoas = funções com pelo menos uma pessoa cadastrada na empresa (None = não verificado).
    Regra: nenhum alerta fica sem dono. Papel sem pessoa vira 'sem_pessoa' e o alerta escala."""
    roles = cfg['roteamento_padrao'].get(occ) or ['compliance']   # ocorrência sem rota configurada → compliance
    m = company.get('usuarios_por_papel', {})
    rot = lambda r: cfg['papeis'].get(r, 'Responsável pelo documento' if r == 'dono_do_documento' else r)
    tem = lambda f: bool(f) and (pessoas is None or f in pessoas)
    out = [{'papel': r, 'rotulo': rot(r), 'funcao_usuario': m.get(r), 'sem_pessoa': not tem(m.get(r))} for r in roles]
    if not any(not x['sem_pessoa'] for x in out):
        esc = next((r for r in ESCALA if tem(m.get(r))), None)
        out.append({'papel': esc or 'curadoria', 'rotulo': (rot(esc) if esc else 'Curadoria LexIA') + ' (escalado: papel original sem pessoa)',
                    'funcao_usuario': m.get(esc) if esc else 'curadoria', 'sem_pessoa': False, 'escalado': True})
    return out


def evaluate(company: dict, cfg: dict, today: date, pessoas: set | None = None) -> dict:
    sector = cfg['setores'][company['setor']]
    assets, alerts = [], []
    for a in company['ativos']:
        tdef = sector['ativos'].get(a['tipo'], {})
        docs, inds, occs = [], [], []
        for d in tdef.get('documentos', []):
            info = (a.get('documentos') or {}).get(d['tipo'])
            if info is None:
                docs.append({**d, 'status': 'não cadastrado', 'nivel': 'Médio'})
                occs.append(('sst' if d.get('sst') else 'documento_vencendo', 'Médio', f"{d['nome']}: não cadastrado para este ativo", d['base'], 'Cadastrar o documento ou registrar que não se aplica.'))
                continue
            due = date.fromisoformat(info['vence']) if info.get('vence') else None
            days = (due - today).days if due else None
            lvl = _doc_level(days, a.get('radiologico') and d['tipo'] in ('autorizacao_cnen', 'plano_radioprotecao'))
            st = 'vencido' if days is not None and days < 0 else ('vence em %d dias' % days if days is not None and days <= 90 else 'em dia')
            ex = d.get('exige')
            ex_hit = bool(ex and today >= date.fromisoformat(ex['desde']) and info.get(ex['campo']) is False)
            if ex_hit:
                lvl2 = 'Alto'
                st = ex['texto']
                lvl = lvl2 if (lvl is None or LEVEL_ORDER[lvl2] < LEVEL_ORDER[lvl]) else lvl
                occs.append(('sst' if d.get('sst') else 'documento_vencido', lvl2, f"{d['nome']}: {ex['texto']}", d['base'], ex['acao']))
            docs.append({**d, 'vence': info.get('vence'), 'ultimo': info.get('ultimo'), 'dias': days, 'status': st, 'nivel': lvl})
            if lvl and not ex_hit:
                occ = 'documento_vencido' if days is not None and days < 0 else 'documento_vencendo'
                if a.get('radiologico') and d['tipo'] in ('autorizacao_cnen', 'plano_radioprotecao'):
                    occ = 'radiologico'
                elif d.get('sst'):
                    occ = 'sst'
                occs.append((occ, lvl, f"{d['nome']}: {st}" + (f" ({due.strftime('%d/%m/%Y')})" if due else ''), d['base'],
                             'Renovar / atualizar o documento e anexar a evidência ao cofre.'))
        for i in tdef.get('indicadores', []):
            vals = (a.get('leituras') or {}).get(i['id'])
            if not vals:
                continue
            cur, z = vals[-1], _z(vals)
            lvl, why = None, []
            la, lc, up = i.get('limite_alerta'), i.get('limite_critico'), i.get('sentido', 'acima') == 'acima'
            if lc is not None and ((cur >= lc) if up else (cur <= lc)):
                lvl, why = 'Crítico', [f"acima do limite crítico ({lc} {i['unidade']})" if up else f"abaixo do limite crítico ({lc} {i['unidade']})"]
            elif la is not None and ((cur >= la) if up else (cur <= la)):
                lvl, why = 'Alto', [f"acima do limite de alerta ({la} {i['unidade']})" if up else f"abaixo do limite de alerta ({la} {i['unidade']})"]
            if z is not None and abs(z) >= 3.5:
                lvl = lvl or ('Alto' if abs(z) >= 8 else 'Médio')
                why.append(f'fora do padrão do próprio ativo (z = {z})')
            trend = round(vals[-1] - vals[-4], 3) if len(vals) >= 4 else None
            inds.append({**i, 'atual': cur, 'z': z, 'tendencia_3': trend, 'serie': vals, 'nivel': lvl, 'motivo': '; '.join(why)})
            if lvl:
                occ = 'radiologico' if i['id'] == 'dose' else 'anomalia_operacional'
                occs.append((occ, lvl, f"{i['nome']}: {cur} {i['unidade']} — {'; '.join(why)}", 'Limite configurado pela empresa / norma técnica do setor',
                             'Inspecionar o ativo, confirmar a leitura do sensor e registrar a manutenção corretiva.'))
        worst = min((o[1] for o in occs), key=lambda l: LEVEL_ORDER[l], default='Baixo')
        status = STATUS[worst] if occs else 'normal'
        assets.append({**{k: a[k] for k in a if k not in ('documentos', 'leituras')}, 'tipo_rotulo': tdef.get('rotulo', a['tipo']), 'simbolo': tdef.get('simbolo', 'circulo'),
                       'aba': tdef.get('aba', 'documentos'), 'documentos': docs, 'indicadores': inds, 'status': status,
                       'ocorrencias': len(occs), 'reguladores': sector['reguladores']})
        for n, (occ, lvl, text, base, action) in enumerate(occs):
            alerts.append({'id': f"{company['id']}:{a['id']}:{occ}:{n}", 'kind': occ, 'asset_id': a['id'], 'asset_name': a['nome'], 'title': text,
                           'detail': f"{tdef.get('rotulo', a['tipo'])} · {a.get('municipio', '')}", 'level': lvl,
                           'urgency': 'Vencido' if 'vencido' in text else ('Agora' if occ in ('anomalia_operacional', 'radiologico') else 'Até 90 dias'),
                           'days_to_due': None, 'due': None, 'safety': occ in ('anomalia_operacional', 'radiologico') and lvl in ('Crítico', 'Alto'),
                           'origin': f"Configuração do setor {sector['nome']} (regra {RULE_VERSION})",
                           'basis': [{'key': occ, 'ref': base, 'text': base, 'url': ''}],
                           'consequences': ('Situação técnica: tratar como segurança operacional antes do trâmite documental.' if occ in ('anomalia_operacional', 'radiologico')
                                            else 'Documento vencido pode gerar notificação, autuação ou embargo pelo órgão competente, conforme apuração.'),
                           'action': action, 'responsibles': [r['rotulo'] for r in recipients(company, cfg, occ, pessoas) if not r['sem_pessoa']],
                           'recipients': recipients(company, cfg, occ, pessoas), 'rule_version': RULE_VERSION, 'source': 'Cadastro da empresa (fictícia)'})
            alerts[-1]['escalado'] = any(r.get('escalado') for r in alerts[-1]['recipients'])
    alerts.sort(key=lambda x: LEVEL_ORDER[x['level']])
    tabs = [t for t in company.get('abas_ativas', sector['abas']) if t in sector['abas']]
    return {'empresa': {k: company[k] for k in ('id', 'nome', 'setor', 'uf')}, 'setor': {'id': company['setor'], 'nome': sector['nome'], 'reguladores': sector['reguladores'],
            'abas': sector['abas']}, 'abas_ativas': tabs, 'abas_rotulos': cfg['rotulos_abas'], 'assets': assets, 'alerts': alerts,
            'legenda': {k: {'rotulo': v['rotulo'], 'simbolo': v['simbolo'], 'caractere': cfg['simbolos'].get(v['simbolo'], '●')} for k, v in sector['ativos'].items()},
            'rule_version': RULE_VERSION,
            'donos': {'alertas_sem_dono': sum(1 for a in alerts if not any(not r['sem_pessoa'] for r in a['recipients'])),
                      'alertas_escalados': sum(1 for a in alerts if a.get('escalado')),
                      'papeis_sem_pessoa': sorted({r['rotulo'] for a in alerts for r in a['recipients'] if r['sem_pessoa']}),
                      'verificado': pessoas is not None}}
