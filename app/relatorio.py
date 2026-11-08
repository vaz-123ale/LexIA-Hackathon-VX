"""Relatório gratuito por empresa (isca comercial) e mercado por setor — só dados PÚBLICOS, regra relatorio-v1.

- Busca por CNPJ (raiz de 8 dígitos) ou por nome de pessoa jurídica; pessoa física nunca é buscada nem exibida.
- Junta: barragens SIGBM (+ radar de atenção), títulos SIGMINE com nome idêntico (+ radar de fechamento), usinas ANEEL/SIGA
  em que a empresa aparece como proprietária (+ radar de outorgas) e barragens SNISB de energia/abastecimento.
- Não é auditoria, parecer nem acusação: mostra sinais em campos públicos para uma conversa.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

RULE_VERSION = 'relatorio-v1'


def _n(s) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().upper()).strip()


def _donos_siga(txt: str) -> list[str]:
    return [m.strip() for m in re.findall(r'para (.+?) \(', txt or '')]


def relatorio(q: str, sigbm: list[dict], radar_by_id: dict, minas: list[dict], fech: dict | None, usinas: list[dict], outorg: dict | None, snisb_set: dict | None) -> dict:
    q = (q or '').strip()
    raiz = re.sub(r'\D', '', q)[:8] if re.sub(r'\D', '', q) and len(re.sub(r'\D', '', q)) >= 8 else None
    nq = _n(q)
    tem = lambda nome: bool(re.search(r'(?<![A-Z0-9])' + re.escape(nq) + r'(?![A-Z0-9])', _n(nome)))   # palavra inteira (evita ITAMINAS ⊂ BRITAMINAS)
    if not raiz and len(nq) < 4:
        return {'error': 'Digite o CNPJ (ao menos 8 dígitos) ou o nome da empresa (ao menos 4 letras).'}
    pj = [r for r in sigbm if r.get('owner_cnpj_root') and r.get('owner_doc_type') != 'CPF_MASCARADO_OCULTO']
    dams = [r for r in pj if (raiz and r['owner_cnpj_root'] == raiz) or (not raiz and tem(r.get('owner_name')))]
    nomes = sorted({r.get('owner_name') for r in dams}) or ([] if raiz else [q])
    nn = {_n(x) for x in nomes}
    tit = [m for m in minas if 'não exibido' not in m.get('titular', '') and (_n(m['titular']) in nn or (not raiz and tem(m['titular'])))]
    fech_by = {x['id']: x for x in (fech or {}).get('items', [])}
    us = [u for u in usinas if any(_n(d) in nn or (not raiz and tem(d)) for d in _donos_siga(u.get('proprietarios')))]
    out_by = {x['id']: x for x in (outorg or {}).get('items', [])}
    sn = [o for k in ('energia', 'abastecimento') for o in (snisb_set or {}).get(k, []) if 'não exibido' not in (o.get('owner') or '')
          and (_n(o.get('owner')) in nn or (not raiz and tem(o.get('owner'))))]
    if not (dams or tit or us or sn):
        return {'q': q, 'encontrado': False, 'rule_version': RULE_VERSION,
                'mensagem': 'Nada encontrado com esse CNPJ/nome nos cadastros públicos (SIGBM, SIGMINE, ANEEL/SIGA, SNISB). Confira a razão social: a empresa pode operar com outro nome jurídico.'}
    att = lambda i: (radar_by_id.get(i) or {}).get('attention', 'Sem sinal')
    b_items = [{'id': r['id'], 'nome': r.get('name'), 'local': f"{r.get('municipio')}/{r.get('uf')}", 'dpa': r.get('dpa'), 'situacao': r.get('operational_status'),
                'emergencia': r.get('emergency_level'), 'atencao': att(r['id']),
                'sinais': [s['label'] for s in (radar_by_id.get(r['id']) or {}).get('signals', []) if s.get('code') != 'CONTEXTO_PORTE'][:3]} for r in dams]
    b_items.sort(key=lambda x: ['Crítica', 'Alta', 'Moderada', 'Baixa', 'Sem sinal'].index(x['atencao']))
    t_items = [{'id': m['id'], 'nome': f"{m['substancia']} · {m['processo']}", 'uf': m['uf'], 'fase': m['fase'], 'evento': m.get('ultimo_evento', '')[:120],
                'atencao': (fech_by.get(m['id']) or {}).get('atencao'), 'sinais': [s['label'] for s in (fech_by.get(m['id']) or {}).get('sinais', [])],
                'radiologico': m.get('radiologico')} for m in tit]
    t_items.sort(key=lambda x: (x['atencao'] is None, x['atencao'] or ''))
    u_items = [{'id': u['id'], 'nome': u['nome'], 'tipo': u['tipo_rotulo'], 'uf': u['uf'], 'fase': u['fase'], 'mw': round((u.get('potencia_kw') or 0) / 1000, 1),
                'fim_outorga': u.get('fim_vigencia'), 'atencao': (out_by.get(u['id']) or {}).get('atencao'),
                'sinais': [s['label'] for s in (out_by.get(u['id']) or {}).get('sinais', [])]} for u in us]
    u_items.sort(key=lambda x: (x['atencao'] is None, -(x['mw'] or 0)))
    s_items = [{'id': o['id'], 'nome': o.get('name'), 'local': f"{o.get('municipio')}/{o.get('uf')}", 'uso': o.get('use'), 'dpa': o.get('damage_potential'),
                'plano_seguranca': o.get('has_safety_plan'), 'pae': o.get('has_pae')} for o in sn]
    nivel = Counter(x['atencao'] for x in b_items)
    destaques = []
    if nivel.get('Crítica') or nivel.get('Alta'):
        destaques.append(f"{nivel.get('Crítica', 0) + nivel.get('Alta', 0)} barragem(ns) com atenção crítica ou alta no radar")
    em = sum(1 for x in b_items if x['emergencia'] not in (None, '', 'Sem emergência'))
    if em:
        destaques.append(f'{em} barragem(ns) em nível de emergência declarado')
    tf = [x for x in t_items if x['atencao']]
    if tf:
        destaques.append(f'{len(tf)} título(s) de lavra com sinal de fechamento, suspensão, renúncia ou caducidade')
    uo = [x for x in u_items if x['atencao']]
    if uo:
        destaques.append(f'{len(uo)} usina(s) com outorga vencida, vencendo ou sem obra')
    sp = sum(1 for x in s_items if x['plano_seguranca'] == 'Não')
    if sp:
        destaques.append(f'{sp} barragem(ns) de abastecimento/energia sem plano de segurança declarado no SNISB')
    sa = sum(1 for x in s_items if x['pae'] == 'Não' and x['dpa'] == 'Alto')
    if sa:
        destaques.append(f'{sa} barragem(ns) com dano potencial alto e sem PAE declarado')
    rad = sum(1 for x in t_items if x['radiologico'])
    if rad:
        destaques.append(f'{rad} título(s) com substância de sinal radiológico (CNEN/ANSN)')
    modulos = [m for m, ok in (('Barragens de mineração', b_items), ('Minas e fechamento', t_items), ('Usinas e outorgas', u_items),
                                ('Barragens de abastecimento/energia', s_items), ('Radiológico (CNEN)', rad)) if ok] + ['Documentos e licenças', 'Alertas de compliance']
    return {'q': q, 'encontrado': True, 'rule_version': RULE_VERSION, 'empresa': nomes[:3], 'cnpj_raiz': raiz or (dams[0]['owner_cnpj_root'] if dams else None),
            'resumo': {'barragens': len(b_items), 'titulos': len(t_items), 'usinas': len(u_items), 'snisb': len(s_items)},
            'destaques': destaques or ['Nenhum sinal relevante nos campos públicos — bom ponto de partida para manter assim.'],
            'barragens': b_items[:15], 'titulos': t_items[:15], 'usinas': u_items[:15], 'snisb': s_items[:15], 'modulos_sugeridos': modulos,
            'aviso': 'Relatório com dados públicos (ANM, ANA, ANEEL). Não é auditoria, parecer ou acusação: são sinais em campos declarados para uma conversa. Confirme os dados com a própria empresa.'}


def mercado(usinas: list[dict], outorg: dict | None, snisb_set: dict | None, sigbm: list[dict]) -> dict:
    hid = [u for u in usinas if u['tipo'] in ('UHE', 'PCH', 'CGH') and u['fase'] == 'Operação']
    donos_hid = Counter(d for u in hid for d in _donos_siga(u.get('proprietarios')))
    risco = {x['id'] for x in (outorg or {}).get('items', []) if x['atencao'] in ('Crítica', 'Alta')}
    donos_risco = {d for u in usinas if u['id'] in risco for d in _donos_siga(u.get('proprietarios'))}
    ab = [o for o in (snisb_set or {}).get('abastecimento', []) if 'não exibido' not in (o.get('owner') or '') and not (o.get('owner') or '').startswith('Sem empreendedor')]
    en = [o for o in (snisb_set or {}).get('energia', []) if 'não exibido' not in (o.get('owner') or '') and not (o.get('owner') or '').startswith('Sem empreendedor')]
    op_ab = Counter(o['owner'] for o in ab)
    min_pj = Counter(r.get('owner_cnpj_root') for r in sigbm if r.get('owner_cnpj_root') and r.get('owner_doc_type') != 'CPF_MASCARADO_OCULTO')
    return {'rule_version': RULE_VERSION, 'setores': [
        {'setor': 'Mineração', 'contas': len(min_pj), 'com_3_ou_mais': sum(1 for v in min_pj.values() if v >= 3), 'base': 'Pessoas jurídicas com barragem no SIGBM (raiz de CNPJ)', 'fonte': 'ANM/SIGBM'},
        {'setor': 'Energia (hidrelétricas)', 'contas': len(donos_hid), 'com_3_ou_mais': sum(1 for v in donos_hid.values() if v >= 3),
         'em_risco_outorga': len(donos_risco), 'base': 'Proprietários de UHE/PCH/CGH em operação (nome no cadastro)', 'fonte': 'ANEEL/SIGA'},
        {'setor': 'Energia (barragens fiscalizadas pela ANEEL)', 'contas': len({o['owner'] for o in en}), 'base': 'Empreendedores identificados no SNISB', 'fonte': 'ANA/SNISB'},
        {'setor': 'Saneamento (barragens de abastecimento)', 'contas': len(op_ab), 'com_3_ou_mais': sum(1 for v in op_ab.values() if v >= 3),
         'base': 'Empreendedores identificados (pessoa jurídica/órgão público) de barragens de abastecimento humano', 'fonte': 'ANA/SNISB'}],
        'aviso': 'Contagem de organizações nos cadastros oficiais (nomes, sem consolidar grupos econômicos). É o universo endereçável, não previsão de vendas. Receita = contas × ticket é hipótese.'}
