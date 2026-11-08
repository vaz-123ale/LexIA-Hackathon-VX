"""Organiza o relato do cidadão em campos (regra organiza-v1).

Determinístico primeiro: datas relativas ("ontem", "outro dia", "sexta passada", "há 3 dias", "desde março") são
resolvidas por regra a partir da data do registro; cada campo guarda o TRECHO literal do relato que o sustenta.
A IA generativa (opcional) só reescreve os fatos em frases objetivas; não pode inventar data, número ou nome:
frases com número que não está no relato são descartadas pelo verificador.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from .ai import norm

RULE_VERSION = 'organiza-v1'
MESES = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
DIAS = {'segunda': 0, 'terca': 1, 'quarta': 2, 'quinta': 3, 'sexta': 4, 'sabado': 5, 'domingo': 6}
NUM = {'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'tres': 3, 'quatro': 4, 'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10, 'quinze': 15}


def _fmt(d: date) -> str:
    return d.strftime('%d/%m/%Y')


def _trecho(original: str, t: str, m: re.Match) -> str:
    """Trecho do texto ORIGINAL (com acentos) correspondente ao match no texto normalizado (mesmo comprimento)."""
    a, b = m.span()
    return original[a:b] if len(original) == len(t) else m.group(0)


def quando(relato: str, hoje: date) -> dict | None:
    t = norm(relato)
    o = relato.lower()
    pats = [
        (r'\banteontem\b', lambda m: (hoje - timedelta(days=2), 'exata')),
        (r'\bontem\b', lambda m: (hoje - timedelta(days=1), 'exata')),
        (r'\bhoje\b|\bagora ha pouco\b|\bagorinha\b|\bnesta manha\b|\bhoje cedo\b', lambda m: (hoje, 'exata')),
        (r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b', lambda m: (_dmy(m, hoje), 'exata')),
        (r'\bdia (\d{1,2})\b', lambda m: (_dia(int(m.group(1)), hoje), 'exata')),
        (r'\b(?:na |no |nesta |neste |ultima |ultimo )?(segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?(?: passad[oa])?\b',
         lambda m: (_ultimo_dia_semana(DIAS[m.group(1)], hoje), 'aproximada')),
        (r'\bha (\d+|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|quinze) (dia|dias|semana|semanas)\b',
         lambda m: (hoje - timedelta(days=_n(m.group(1)) * (7 if m.group(2).startswith('semana') else 1)), 'aproximada')),
        (r'\bsemana passada\b', lambda m: (hoje - timedelta(days=7), 'aproximada')),
        (r'\bmes passado\b', lambda m: (_mes_passado(hoje), 'mes')),
    ]
    for p, f in pats:
        m = re.search(p, t)
        if m:
            d, prec = f(m)
            if d and d <= hoje:
                txt = _fmt(d) if prec == 'exata' else (f"por volta de {_fmt(d)}" if prec == 'aproximada' else d.strftime('%m/%Y'))
                return {'data': d.isoformat(), 'texto': txt, 'precisao': prec, 'trecho': _trecho(o, t, m)}
    m = re.search(r'\b(outro dia|dia desses|uns dias atras|recentemente|esses dias)\b', t)
    if m:
        return {'data': None, 'texto': 'data não informada com precisão', 'precisao': 'vaga', 'trecho': _trecho(o, t, m),
                'pergunta': 'Se lembrar, informe o dia aproximado (ex.: "ontem", "sexta passada", "12/10").'}
    return None


def desde(relato: str, hoje: date) -> dict | None:
    t, o = norm(relato), relato.lower()
    m = re.search(r'\bdesde (o |a )?(' + '|'.join(MESES) + r')(?: de (\d{4}))?\b', t)
    if m:
        mes = MESES.index(m.group(2)) + 1
        ano = int(m.group(3)) if m.group(3) else (hoje.year if mes <= hoje.month else hoje.year - 1)
        return {'texto': f"desde {m.group(2).replace('marco', 'março')}/{ano}", 'trecho': _trecho(o, t, m)}
    m = re.search(r'\b(ha|faz) (\d+|um|uma|dois|duas|tres|quatro|cinco|seis) (mes|meses|ano|anos)\b', t)
    if m:
        return {'texto': f"há {_n(m.group(2))} {m.group(3)}", 'trecho': _trecho(o, t, m)}
    m = re.search(r'\b(desde (o ano passado|sempre|que me mudei|a chuva|o inicio do ano))\b', t)
    if m:
        return {'texto': m.group(1), 'trecho': _trecho(o, t, m)}
    return None


def periodo(relato: str) -> str | None:
    t = norm(relato)
    for k, v in (('madrugada', 'madrugada'), ('de manha|pela manha|cedo', 'manhã'), ('a tarde|de tarde|pela tarde', 'tarde'), ('a noite|de noite|anoitecer', 'noite')):
        if re.search(r'\b(' + k + r')\b', t):
            return v
    return None


def afetados(relato: str) -> list[str]:
    t = norm(relato)
    out = []
    for p, l in ((r'morador|vizinh|comunidade|bairro|casas', 'moradores próximos'), (r'crianc|escola', 'crianças / escola'),
                 (r'trabalhador|operario|funcionari|colega', 'trabalhadores'), (r'\brio\b|corrego|nascente|peixe', 'rio ou córrego'),
                 (r'gado|animais|criacao|plantacao|lavoura', 'animais ou plantações'), (r'estrada|rodovia|ponte', 'estrada ou ponte')):
        if re.search(p, t):
            out.append(l)
    return out


def recorrente(relato: str) -> bool:
    return bool(re.search(r'\b(de novo|novamente|toda vez|sempre que|varias vezes|todo dia|todos os dias|continua|ainda esta)\b', norm(relato)))


def organizar(relato: str, hoje: date, alvo: dict | None = None, categoria: str | None = None) -> dict:
    frases = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', (relato or '').strip()) if len(s.strip()) > 3 and not s.strip().startswith('(Quando:')][:8]
    q = quando(relato, hoje)
    faltando = []
    if not q or q.get('precisao') == 'vaga':
        faltando.append('quando aconteceu')
    if not alvo:
        faltando.append('qual estrutura (escolha no mapa ou descreva o local)')
    if len((relato or '').split()) < 8:
        faltando.append('mais detalhes do que foi visto')
    return {'rule_version': RULE_VERSION, 'quando': q, 'desde': desde(relato, hoje), 'periodo': periodo(relato), 'afetados': afetados(relato),
            'recorrente': recorrente(relato), 'fatos': frases, 'faltando': faltando, 'registrado_em': _fmt(hoje),
            'onde': (f"{alvo.get('name')} ({alvo.get('id')}) — {alvo.get('municipio') or ''}{'/' + alvo['uf'] if alvo.get('uf') else ''}".strip(' —') if alvo else None),
            'categoria': categoria}


def verificar_fatos(fatos: list[str], relato: str) -> list[str]:
    """Aceita frases da IA só se todo número citado existir no relato (sem data, quantidade ou valor inventado)."""
    nums = set(re.findall(r'\d+', relato or ''))
    return [f for f in fatos if f and len(f) < 400 and set(re.findall(r'\d+', f)) <= nums]


def _n(x: str) -> int:
    return int(x) if x.isdigit() else NUM.get(x, 1)


def _dmy(m, hoje: date) -> date | None:
    try:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else hoje.year
        y = y + 2000 if y < 100 else y
        r = date(y, mo, d)
        return r if r <= hoje or m.group(3) else date(y - 1, mo, d)
    except ValueError:
        return None


def _dia(d: int, hoje: date) -> date | None:
    try:
        r = date(hoje.year, hoje.month, d)
        if r > hoje:
            pm = hoje.replace(day=1) - timedelta(days=1)
            r = date(pm.year, pm.month, d)
        return r
    except ValueError:
        return None


def _ultimo_dia_semana(wd: int, hoje: date) -> date:
    delta = (hoje.weekday() - wd) % 7 or 7
    return hoje - timedelta(days=delta)


def _mes_passado(hoje: date) -> date:
    return (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
