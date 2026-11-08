"""Radares por setor — mesmas ideias do radar de barragens (abandono-v1): sinais de campos OFICIAIS, cada um com peso,
campo e valor de origem; consequência; nível de atenção. Sinal não é conclusão nem acusação.

- minas-v1 (mineração): fechamento e paralisação de minas pelo último evento do título no SIGMINE, cruzado por DISTÂNCIA
  (≤ 5 km) com barragens do SIGBM — "a mina fecha e a barragem fica".
- outorgas-v1 (energia): outorgas de usinas vencidas/vencendo e outorgas antigas sem obra iniciada (ANEEL/SIGA);
  barragens de usinas fiscalizadas pela ANEEL no SNISB (plano de segurança, PAE com dano alto, desativação).
  O campo de inspeção do SNISB está vazio para TODAS as barragens da ANEEL (a ANEEL usa formulário próprio): não vira sinal.
- abastecimento-v1 (saneamento): barragens de abastecimento humano do SNISB (empreendedor, plano de segurança, inspeção, PAE, fase).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, timedelta

LEVELS = ['Crítica', 'Alta', 'Moderada', 'Baixa']
ORDER = {k: i for i, k in enumerate(LEVELS)}


def _sig(code, label, weight, field, value, source):
    return {'code': code, 'label': label, 'weight': weight, 'evidence': {'field': field, 'value': value, 'source': source}}


def nivel(score: int, high: bool, central: bool, critica: int = 5, alta: int = 3) -> str | None:
    """Mesma régua do radar de barragens: Crítica exige sinal central + pontos + consequência alta."""
    if not score:
        return None
    if central and score >= critica and high:
        return 'Crítica'
    if central and ((score >= alta and high) or score >= critica + 1):
        return 'Alta'
    if score >= 2:
        return 'Moderada'
    return 'Baixa'


def _km(a, b, c, d):
    p = math.pi / 180
    x = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def _dt(s) -> date | None:
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', s or '')
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', s or '')
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def _pack(items, rule, criterios, fonte):
    items.sort(key=lambda x: (ORDER[x['atencao']], -x['pontos']))
    return {'rule_version': rule, 'items': items, 'niveis': {k: sum(1 for x in items if x['atencao'] == k) for k in LEVELS},
            'por_uf': Counter(x.get('uf') for x in items if x['atencao'] in ('Crítica', 'Alta')).most_common(), 'criterios': criterios, 'fonte': fonte}


# ------------------------------------------------------------------ mineração
MINAS_EVENTOS = [
    ('PLANO_FECHAMENTO', r'PLANO DE FECHAMENTO', 'Plano de fechamento de mina protocolado', 3, True),
    ('CADUCIDADE', r'CADUC', 'Processo de caducidade/nulidade aberto pela ANM', 3, True),
    ('RENUNCIA', r'RENÚNCIA', 'Renúncia ao título', 2, True),
    ('SUSPENSAO', r'SUSPENSÃO TRABALHOS LAVRA', 'Pedido de suspensão da lavra', 2, True),
    ('SEM_INICIO', r'PRORROGAÇÃO INÍCIO LAVRA', 'Pedido de prorrogação para começar a lavra (concessão sem operar)', 1, False),
    ('MULTA', r'MULTA APLICADA', 'Multa aplicada pela ANM (último evento)', 1, False),
]
MINAS_CRIT = ['Sinais (último evento do título no SIGMINE): plano de fechamento 3 · caducidade 3 · renúncia 2 · suspensão da lavra 2 · prorrogação de início de lavra 1 · multa 1 · concessão sem evento há mais de 3 anos 2 (possível paralisação).',
              'Consequência alta: barragem do SIGBM a até 5 km com dano potencial alto, ou substância com sinal radiológico (CNEN/ANSN).',
              'Crítica: sinal central (fechamento, caducidade, renúncia, suspensão ou sem evento há 3 anos) + 3 pontos + consequência alta. Alta: sinal central + 2 pontos + consequência alta. Sem consequência alta, no máximo Moderada (2 pontos).',
              'O cruzamento com barragens é por distância, não pelo nome da empresa (grupo econômico não é inferido).']


def minas_fechamento(minas: list[dict], barragens: list[dict], today: date) -> dict:
    grid: dict = {}
    for b in barragens:
        if b.get('lat') is not None:
            grid.setdefault((round(b['lat'] * 10), round(b['lon'] * 10)), []).append(b)
    out = []
    for m in minas:
        ev = m.get('ultimo_evento') or ''
        sig, central = [], False
        for code, pat, label, w, c in MINAS_EVENTOS:
            if re.search(pat, ev):
                sig.append(_sig(code, label, w, 'ULT_EVENTO', ev[:120], 'ANM_SIGMINE'))
                central |= c
        d = _dt(ev)
        if d and (today - d).days > 3 * 365 and (m.get('fase') or '').startswith('CONCESS') and not sig:
            sig.append(_sig('SEM_EVENTO_3A', f'Concessão sem nenhum evento desde {d.strftime("%d/%m/%Y")} (possível paralisação)', 2, 'ULT_EVENTO', ev[:120], 'ANM_SIGMINE'))
            central = True
        if not sig:
            continue
        near = []
        gx, gy = round(m['lat'] * 10), round(m['lon'] * 10)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for b in grid.get((gx + dx, gy + dy), []):
                    k = _km(m['lat'], m['lon'], b['lat'], b['lon'])
                    if k <= 5:
                        near.append({'id': b['id'], 'nome': b.get('name'), 'dpa': b.get('dpa'), 'situacao': b.get('operational_status'), 'km': round(k, 1)})
        near.sort(key=lambda x: x['km'])
        high = any((x['dpa'] or '') == 'Alta' for x in near) or bool(m.get('radiologico'))
        score = sum(s['weight'] for s in sig)
        cons = [x for x in (any((y['dpa'] or '') == 'Alta' for y in near) and f"{sum(1 for y in near if (y['dpa'] or '') == 'Alta')} barragem(ns) de dano potencial alto a até 5 km",
                            near and f'{len(near)} barragem(ns) do SIGBM a até 5 km', m.get('radiologico') and 'Substância com sinal radiológico (CNEN/ANSN)') if x]
        out.append({'id': m['id'], 'nome': f"{m['substancia']} · processo {m['processo']}", 'uf': m['uf'], 'lat': m['lat'], 'lon': m['lon'],
                    'empresa': m['titular'], 'categoria': m.get('categoria_label'), 'fase': m.get('fase'), 'evento': ev, 'data_evento': d and d.isoformat(),
                    'sinais': sig, 'pontos': score, 'consequencia': cons or ['Sem agravante classificado'], 'barragens_proximas': near[:8],
                    'atencao': nivel(score, high, central, critica=3, alta=2) if high else ('Moderada' if score >= 2 else 'Baixa'), 'radiologico': bool(m.get('radiologico'))})
    r = _pack(out, 'minas-v1', MINAS_CRIT, 'ANM/SIGMINE (último evento do título) + ANM/SIGBM (barragens)')
    r['barragens_afetadas'] = len({b['id'] for x in out for b in x['barragens_proximas']})
    r['barragens_afetadas_dpa_alta'] = len({b['id'] for x in out for b in x['barragens_proximas'] if (b['dpa'] or '') == 'Alta'})
    return r


# ------------------------------------------------------------------ nuclear / radiológico
RAD_CRIT = ['Inventário real de locais com material radioativo: títulos de lavra do SIGMINE com substância nuclear (urânio, tório) ou de radioatividade natural associada (terras raras, monazita, zircônio, ilmenita, nióbio, fosfato…) e barragens do SIGBM com minério de urânio.',
            'Sinais: os mesmos do fechamento de minas (plano de fechamento 3, caducidade 3, renúncia 2, suspensão 2…) e os do radar de barragens (abandono-v1). Sem sinal = “Baixa” (monitorar).',
            'Consequência alta: substância nuclear (monopólio da União; autoridade nuclear) ou barragem com dano potencial alto.',
            'Sinal radiológico é para avaliação da proteção radiológica (Norma CNEN NN 4.01 / NN 3.01), não conclusão de risco.']


def radiologico(minas: list[dict], fech: dict | None, barragens: list[dict], radar_by_id: dict) -> dict:
    fb = {x['id']: x for x in (fech or {}).get('items', [])}
    out = []
    for m in minas:
        if not m.get('radiologico'):
            continue
        f = fb.get(m['id'])
        nuclear = m.get('categoria') == 'nuclear'
        sig = list(f['sinais']) if f else []
        cons = (['Substância nuclear: monopólio da União (CF art. 21, XXIII); autoridade nuclear'] if nuclear else ['Radioatividade natural associada: avaliar proteção radiológica (CNEN NN 4.01)'])
        cons += [c for c in (f['consequencia'] if f else []) if c != 'Sem agravante classificado']
        at = f['atencao'] if f else 'Baixa'
        if nuclear and f and at in ('Moderada', 'Baixa'):
            at = 'Alta'   # substância nuclear com sinal de fechamento/paralisação sobe um nível
        out.append({'id': m['id'], 'nome': f"{m['substancia']} · processo {m['processo']}", 'uf': m['uf'], 'lat': m['lat'], 'lon': m['lon'], 'empresa': m['titular'],
                    'categoria': 'Nuclear' if nuclear else 'Radioatividade natural associada', 'fase': m.get('fase'), 'evento': m.get('ultimo_evento'),
                    'sinais': sig or [_sig('MONITORAR', 'Sem sinal de fechamento/paralisação: monitorar proteção radiológica', 0, 'SUBS', m['substancia'], 'ANM_SIGMINE')],
                    'pontos': sum(s['weight'] for s in sig), 'consequencia': cons, 'atencao': at, 'barragens_proximas': f['barragens_proximas'] if f else []})
    for b in barragens:
        if 'URAN' not in (b.get('main_ore') or '').upper().replace('Â', 'A'):
            continue
        x = radar_by_id.get(b['id']) or {}
        sig = [s for s in x.get('signals', []) if s.get('code') != 'CONTEXTO_PORTE']
        at = x.get('attention', 'Sem sinal')
        out.append({'id': b['id'], 'nome': b.get('name'), 'uf': b.get('uf'), 'municipio': b.get('municipio'), 'lat': b.get('lat'), 'lon': b.get('lon'),
                    'empresa': b.get('owner_name') if b.get('owner_doc_type') != 'CPF_MASCARADO_OCULTO' else 'Pessoa física (nome não exibido)',
                    'categoria': 'Barragem com minério de urânio (SIGBM)', 'fase': b.get('operational_status'), 'dpa': b.get('dpa'), 'cri': b.get('cri'),
                    'sinais': sig or [_sig('MONITORAR', 'Sem sinal no radar de barragens: monitorar', 0, 'Minério principal', b.get('main_ore'), 'ANM_SIGBM')],
                    'pontos': x.get('score', 0), 'consequencia': ['Rejeito com urânio: autoridade nuclear e ANM'] + ([f"Dano potencial {b.get('dpa')}"] if b.get('dpa') else []),
                    'atencao': at if at in LEVELS else 'Baixa'})
    return _pack(out, 'nuclear-v1', RAD_CRIT, 'ANM/SIGMINE (substância) + ANM/SIGBM (minério de urânio) + radares minas-v1 e abandono-v1')


# ------------------------------------------------------------------ energia
OUTORGAS_CRIT = ['Sinais (ANEEL/SIGA): em operação com outorga já vencida no cadastro 3 (conferir prorrogação) · outorga vence em até 24 meses 2 · outorga há mais de 4 anos sem obra iniciada 2 · há mais de 2 anos 1.',
                 'Consequência alta: usina hidrelétrica (UHE) ou potência outorgada de 30 MW ou mais.',
                 'Crítica: outorga vencida no cadastro (3) em usina de consequência alta. Alta: 2 pontos + consequência alta. Moderada: 2 pontos.']
BARR_USINA_CRIT_NIVEL = 'Crítica: sinal central + 5 pontos + consequência alta. Alta: sinal central + 3 pontos + consequência alta, ou 6 pontos. Moderada: 2 pontos.'
BARR_USINA_CRIT = ['Sinais (ANA/SNISB, barragens fiscalizadas pela ANEEL): dano potencial alto sem PAE declarado 3 · fase de vida desativada 2 · sem plano de segurança declarado 2 · sem revisão periódica declarada 1 · barragem autuada 1.',
                   'Consequência alta: dano potencial alto ou categoria de risco alta.',
                   'O campo de inspeção do SNISB está vazio em TODAS as barragens da ANEEL (a ANEEL usa formulário próprio, o FSB): por isso não é usado como sinal.',
                   BARR_USINA_CRIT_NIVEL]


def outorgas(usinas: list[dict], today: date) -> dict:
    out = []
    lim24, lim4a, lim2a = today + timedelta(days=730), today - timedelta(days=4 * 365), today - timedelta(days=2 * 365)
    for u in usinas:
        sig = []
        fim, ini = _dt(u.get('fim_vigencia')), _dt(u.get('inicio_vigencia'))
        if u['fase'] == 'Operação' and fim:
            if fim < today:
                sig.append(_sig('OUTORGA_VENCIDA', f'Em operação com outorga vencida no cadastro em {fim.strftime("%d/%m/%Y")} (conferir prorrogação)', 3, 'DatFimVigencia', u['fim_vigencia'], 'ANEEL_SIGA'))
            elif fim <= lim24:
                sig.append(_sig('OUTORGA_VENCENDO', f'Outorga vence em {fim.strftime("%d/%m/%Y")}', 2, 'DatFimVigencia', u['fim_vigencia'], 'ANEEL_SIGA'))
        if u['fase'] == 'Construção não iniciada' and ini:
            if ini < lim4a:
                sig.append(_sig('SEM_OBRA_4A', f'Outorga desde {ini.strftime("%d/%m/%Y")} e obra não iniciada', 2, 'DscFaseUsina / DatInicioVigencia', f"{u['fase']} / {u['inicio_vigencia']}", 'ANEEL_SIGA'))
            elif ini < lim2a:
                sig.append(_sig('SEM_OBRA_2A', f'Outorga desde {ini.strftime("%d/%m/%Y")} e obra não iniciada', 1, 'DscFaseUsina / DatInicioVigencia', f"{u['fase']} / {u['inicio_vigencia']}", 'ANEEL_SIGA'))
        if not sig:
            continue
        mw = (u.get('potencia_kw') or 0) / 1000
        high = u['tipo'] == 'UHE' or mw >= 30
        score = sum(s['weight'] for s in sig)
        out.append({'id': u['id'], 'nome': u['nome'], 'uf': u['uf'], 'lat': u.get('lat'), 'lon': u.get('lon'), 'empresa': u.get('proprietarios') or '—',
                    'categoria': u['tipo_rotulo'], 'fase': u['fase'], 'potencia_mw': round(mw, 1), 'fim_vigencia': u.get('fim_vigencia'), 'municipios': u.get('municipios'),
                    'sinais': sig, 'pontos': score, 'consequencia': [x for x in (u['tipo'] == 'UHE' and 'Usina hidrelétrica de grande porte (UHE)', mw >= 30 and f'Potência outorgada {mw:,.0f} MW'.replace(',', '.')) if x] or ['Sem agravante classificado'],
                    'atencao': nivel(score, high, True, critica=3, alta=2)})
    return _pack(out, 'outorgas-v1', OUTORGAS_CRIT, 'ANEEL/SIGA (dados abertos)')


def _snisb_items(rows, today, extra_sig, crit, rule, fonte, high_fn):
    out = []
    for o in rows:
        sig, central = extra_sig(o, today)
        if not sig:
            continue
        score = sum(s['weight'] for s in sig)
        high = high_fn(o)
        cons = [x for x in (o.get('damage_potential') == 'Alto' and 'Dano potencial alto (SNISB)', o.get('risk_category') == 'Alto' and 'Categoria de risco alta',
                            o.get('use') == 'Abastecimento humano' and 'Abastece população') if x]
        out.append({'id': o['id'], 'nome': o.get('name'), 'uf': o.get('uf'), 'municipio': o.get('municipio'), 'lat': o.get('lat'), 'lon': o.get('lon'),
                    'empresa': o.get('owner') or '—', 'categoria': o.get('use'), 'fase': o.get('phase'), 'fiscalizador': o.get('regulator'),
                    'dpa': o.get('damage_potential'), 'cri': o.get('risk_category'), 'capacidade_hm3': o.get('capacity_hm3'), 'altura_m': o.get('height_m'),
                    'ultima_inspecao': o.get('last_inspection'), 'sinais': sig, 'pontos': score, 'consequencia': cons or ['Sem agravante classificado'],
                    'atencao': nivel(score, high, central)})
    return _pack(out, rule, crit, fonte)


def barragens_usinas(rows: list[dict], today: date) -> dict:
    def s(o, today):
        sig, c = [], False
        if o.get('damage_potential') == 'Alto' and o.get('has_pae') == 'Não':
            sig.append(_sig('PAE_AUSENTE', 'Dano potencial alto sem PAE declarado', 3, 'POSSUI_PAE / DANO_POTENCIAL', 'Não / Alto', 'ANA_SNISB')); c = True
        if o.get('phase') == 'Desativada':
            sig.append(_sig('DESATIVADA', 'Fase de vida: desativada', 2, 'FASE_DE_VIDA', 'Desativada', 'ANA_SNISB')); c = True
        if o.get('has_safety_plan') == 'Não':
            sig.append(_sig('SEM_PSB', 'Sem plano de segurança declarado no SNISB', 2, 'POSSUI_PLANO_SEGURANCA', 'Não', 'ANA_SNISB')); c = True
        if o.get('has_periodic_review') == 'Não':
            sig.append(_sig('SEM_RPS', 'Sem revisão periódica de segurança declarada', 1, 'POSSUI_REVISAO_PERIODICA', 'Não', 'ANA_SNISB'))
        if o.get('fined') == 'Sim':
            sig.append(_sig('AUTUADA', 'Barragem autuada', 1, 'BARRAGEM_AUTUADA', 'Sim', 'ANA_SNISB'))
        return sig, c
    return _snisb_items(rows, today, s, BARR_USINA_CRIT, 'barragens-usinas-v1', 'ANA/SNISB (fiscalizador ANEEL)',
                        lambda o: o.get('damage_potential') == 'Alto' or o.get('risk_category') == 'Alto')


ABAST_CRIT = ['Sinais (ANA/SNISB, uso principal "Abastecimento humano"): sem empreendedor identificado 3 · dano potencial alto sem PAE 3 · fase desativada ou rompida 2 · na PNSB sem plano de segurança 2 · na PNSB sem inspeção registrada 1 (ou inspeção com mais de 3 anos 1) · autuada 1.',
              'Consequência alta: dano potencial alto ou categoria de risco alta (toda barragem desta lista abastece população).',
              'Crítica: sinal central (sem empreendedor, PAE ausente com dano alto, desativada/rompida ou sem plano de segurança) + 5 pontos + consequência alta. Alta: sinal central + 3 pontos + consequência alta, ou 6 pontos. Moderada: 2 pontos.']


def abastecimento(rows: list[dict], today: date) -> dict:
    def s(o, today):
        sig, c = [], False
        if (o.get('owner') or '').startswith('Sem empreendedor'):
            sig.append(_sig('SEM_EMPREENDEDOR', 'Sem empreendedor identificado no cadastro nacional', 3, 'NM_EMPREENDEDOR', '(vazio)', 'ANA_SNISB')); c = True
        if o.get('damage_potential') == 'Alto' and o.get('has_pae') == 'Não':
            sig.append(_sig('PAE_AUSENTE', 'Dano potencial alto sem PAE declarado', 3, 'POSSUI_PAE / DANO_POTENCIAL', 'Não / Alto', 'ANA_SNISB')); c = True
        if o.get('phase') in ('Desativada', 'Rompida'):
            sig.append(_sig('FASE', f"Fase de vida: {o['phase']}", 2, 'FASE_DE_VIDA', o['phase'], 'ANA_SNISB')); c = True
        if o.get('pnsb') == 'Sim' and o.get('has_safety_plan') == 'Não':
            sig.append(_sig('SEM_PSB', 'Na Política Nacional de Segurança de Barragens e sem plano de segurança declarado', 2, 'POSSUI_PLANO_SEGURANCA', 'Não', 'ANA_SNISB')); c = True
        if o.get('pnsb') == 'Sim':
            li = o.get('last_inspection')
            if not li:
                sig.append(_sig('SEM_INSPECAO', 'Sem inspeção registrada', 1, 'INS_DT_INSPECAO', '(vazio)', 'ANA_SNISB'))
            elif (today - date.fromisoformat(li)).days > 3 * 365:
                sig.append(_sig('INSPECAO_ANTIGA', f'Última inspeção registrada em {li}', 1, 'INS_DT_INSPECAO', li, 'ANA_SNISB'))
        if o.get('fined') == 'Sim':
            sig.append(_sig('AUTUADA', 'Barragem autuada', 1, 'BARRAGEM_AUTUADA', 'Sim', 'ANA_SNISB'))
        return sig, c
    return _snisb_items(rows, today, s, ABAST_CRIT, 'abastecimento-v1', 'ANA/SNISB (uso: abastecimento humano)',
                        lambda o: o.get('damage_potential') == 'Alto' or o.get('risk_category') == 'Alto')
