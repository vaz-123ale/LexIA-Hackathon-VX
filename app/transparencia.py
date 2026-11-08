"""Portal da Transparência (público, sem login) e busca do que está perto de quem denuncia.

Regra transparencia-v1:
- números das estruturas vêm SÓ de dados oficiais (ANM/SIGBM, ANA/SNISB, ANM/SIGMINE) e do radar da LexIA
  (sinal calculado a partir de campos públicos: não é declaração de irregularidade);
- pessoa física nunca tem nome exibido;
- denúncias: só agregados (quantas foram feitas, encaminhadas à empresa, respondidas) — nunca texto, autor ou local;
- contagem de denúncias por empresa só aparece para empresas que usam a LexIA (recebem e respondem na plataforma);
  para as demais, a denúncia vai ao órgão oficial e a LexIA não publica contagem por empresa.
- a localização de quem denuncia é usada só para a busca (requisição POST, não fica em log nem no banco).
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

RULE_VERSION = 'transparencia-v1'
ORDER = {'Crítica': 0, 'Alta': 1, 'Moderada': 2, 'Baixa': 3, 'Sem sinal': 4}


def _n(s) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().upper()).strip()


def km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def owner_label(rec: dict) -> str:
    if rec.get('owner_doc_type') == 'CPF_MASCARADO_OCULTO' or not rec.get('owner_cnpj'):
        return 'Pessoa física (nome não exibido)' if rec.get('owner_doc_type') == 'CPF_MASCARADO_OCULTO' else (rec.get('owner_name') or 'Não identificado')
    return rec.get('owner_name') or '—'


def denuncia_stats(db) -> dict:
    def one(q, *a):
        try:
            return db.execute(q, a).fetchone()[0] or 0
        except Exception:
            return 0
    return {'registradas': one("SELECT COUNT(*) FROM denuncias WHERE state != 'RASCUNHO'"),
            'enviadas_ao_orgao': one("SELECT COUNT(*) FROM denuncias WHERE state = 'ENCAMINHADA_PELO_USUARIO'"),
            'encaminhadas_empresa': one('SELECT COUNT(*) FROM denuncia_destino'),
            'em_apuracao': one("SELECT COUNT(*) FROM denuncia_destino WHERE state = 'EM_APURACAO'"),
            'respondidas': one("SELECT COUNT(*) FROM denuncia_destino WHERE state = 'RESPONDIDA'")}


def por_empresa_lexia(db, empresas_lexia: dict) -> list[dict]:
    """empresas_lexia: {cnpj_root: nome}. Só empresas que recebem denúncias na plataforma."""
    out = []
    for root, nome in empresas_lexia.items():
        try:
            rows = db.execute('SELECT state, COUNT(*) FROM denuncia_destino WHERE org=? GROUP BY state', (root,)).fetchall()
        except Exception:
            rows = []
        c = {r[0]: r[1] for r in rows}
        tot = sum(c.values())
        out.append({'empresa': nome, 'recebidas': tot, 'em_apuracao': c.get('EM_APURACAO', 0), 'respondidas': c.get('RESPONDIDA', 0),
                    'sem_resposta': c.get('RECEBIDA', 0), 'taxa_resposta': round(c.get('RESPONDIDA', 0) / tot, 2) if tot else None})
    return sorted(out, key=lambda x: -x['recebidas'])


def panorama(records: list[dict], radar_by_id: dict, radar_items: list[dict], minas: list[dict], db, empresas_lexia: dict, snapshot: dict | None) -> dict:
    mining = [x for x in radar_items if x.get('kind') == 'mineracao']
    orphans = [x for x in radar_items if x.get('kind') == 'orfa']
    att = Counter(x.get('attention', 'Sem sinal') for x in mining)
    by_rec = {r['id']: r for r in records}
    casos = sorted([x for x in mining if x.get('attention') in ('Crítica', 'Alta')], key=lambda x: (ORDER.get(x['attention'], 9), -x.get('score', 0)))
    casos_out = [{'id': x['id'], 'nome': x.get('name'), 'municipio': x.get('municipio'), 'uf': x.get('uf'), 'atencao': x['attention'], 'pontos': x.get('score'),
                  'empresa': owner_label(by_rec.get(x['id'], {})), 'dpa': by_rec.get(x['id'], {}).get('dpa'), 'emergencia': by_rec.get(x['id'], {}).get('emergency_level'),
                  'sinais': [s['label'] for s in x.get('signals', []) if s.get('code') != 'CONTEXTO_PORTE'][:3], 'lat': x.get('lat'), 'lon': x.get('lon')} for x in casos[:40]]
    pts = [{'id': x['id'], 'lat': x.get('lat'), 'lon': x.get('lon'), 'a': x.get('attention', 'Sem sinal'), 'n': x.get('name'), 'uf': x.get('uf')}
           for x in mining if x.get('lat') is not None]
    uf = Counter()
    uf_crit = Counter()
    for x in mining:
        uf[x.get('uf')] += 1
        if x.get('attention') in ('Crítica', 'Alta'):
            uf_crit[x.get('uf')] += 1
    # empresas reais (pessoa jurídica) com mais barragens — só dados públicos
    orgs: dict[str, dict] = {}
    for r in records:
        if not r.get('owner_cnpj_root') or r.get('owner_doc_type') == 'CPF_MASCARADO_OCULTO':
            continue
        o = orgs.setdefault(r['owner_cnpj_root'], {'cnpj_root': r['owner_cnpj_root'], 'empresa': r.get('owner_name'), 'barragens': 0, 'dpa_alta': 0, 'emergencia': 0,
                                                    'critica': 0, 'alta': 0, 'ufs': set(), 'minerio': Counter()})
        o['barragens'] += 1
        o['dpa_alta'] += (r.get('dpa') or '').lower() == 'alta'
        o['emergencia'] += r.get('emergency_level') not in (None, '', 'Sem emergência')
        a = (radar_by_id.get(r['id']) or {}).get('attention')
        o['critica'] += a == 'Crítica'
        o['alta'] += a == 'Alta'
        o['ufs'].add(r.get('uf'))
        if r.get('main_ore'):
            o['minerio'][r['main_ore']] += 1
    titles = Counter(_n(m.get('titular')) for m in minas)
    emp = []
    for o in orgs.values():
        o['ufs'] = sorted(u for u in o['ufs'] if u)
        o['minerio'] = [m for m, _ in o['minerio'].most_common(2)]
        o['titulos_lavra'] = titles.get(_n(o['empresa']), 0)   # mesmo nome exato no SIGMINE
        o['usa_lexia'] = o['cnpj_root'] in empresas_lexia
        emp.append(o)
    emp.sort(key=lambda o: (-(o['critica'] + o['alta']), -o['barragens']))
    return {'rule_version': RULE_VERSION, 'snapshot': snapshot,
            'totais': {'barragens_mineracao': len(mining), 'barragens_sem_dono': len(orphans), 'em_emergencia': sum(1 for r in records if r.get('emergency_level') not in (None, '', 'Sem emergência')),
                       'dpa_alta': sum(1 for r in records if (r.get('dpa') or '').lower() == 'alta'), 'minas_lavra': len(minas),
                       'minas_radiologicas': sum(1 for m in minas if m.get('radiologico')), 'empresas_pj': len(orgs)},
            'atencao': {k: att.get(k, 0) for k in ORDER}, 'casos': casos_out, 'pontos': pts,
            'por_uf': [{'uf': u, 'barragens': n, 'critica_alta': uf_crit.get(u, 0)} for u, n in uf.most_common()],
            'empresas': emp[:60], 'denuncias': denuncia_stats(db), 'denuncias_por_empresa': por_empresa_lexia(db, empresas_lexia),
            'avisos': ['Nível de atenção é um sinal calculado pela LexIA a partir de campos públicos do SIGBM/SNISB (regra abandono-v1); não é declaração de irregularidade nem de risco de rompimento.',
                       'Denúncias: só números agregados. Texto, autor e localização nunca são publicados. Contagem por empresa só para empresas que recebem e respondem na LexIA.',
                       'Pessoa física não tem nome exibido.']}


def proximos(lat: float, lon: float, radar_items: list[dict], records_by_id: dict, minas: list[dict], ativos_demo: list[dict], recebe, k: int = 10) -> list[dict]:
    """Estruturas mais próximas do ponto informado (barragens SIGBM/SNISB, minas SIGMINE e ativos de empresas na LexIA)."""
    cands = []
    for x in radar_items:
        if x.get('lat') is None:
            continue
        rec = records_by_id.get(x['id'], {})
        org = rec.get('owner_cnpj_root')
        cands.append({'id': x['id'], 'tipo': 'Barragem de mineração' if x['kind'] == 'mineracao' else 'Barragem sem empreendedor identificado',
                      'nome': x.get('name'), 'local': f"{x.get('municipio') or '—'}/{x.get('uf') or '—'}", 'empresa': owner_label(rec) if rec else 'Sem empreendedor identificado',
                      'atencao': x.get('attention'), 'lat': x['lat'], 'lon': x['lon'], 'recebe_direto': bool(org and recebe(org)), 'fonte': 'ANM/SIGBM' if x['kind'] == 'mineracao' else 'ANA/SNISB'})
    for m in minas:
        cands.append({'id': m['id'], 'tipo': f"Mina · {m.get('categoria_label')}", 'nome': m.get('substancia'), 'local': m.get('uf'), 'empresa': m.get('titular'),
                      'atencao': None, 'lat': m['lat'], 'lon': m['lon'], 'recebe_direto': False, 'fonte': 'ANM/SIGMINE', 'radiologico': m.get('radiologico')})
    for a in ativos_demo:
        cands.append({**a, 'recebe_direto': True, 'fonte': 'Empresa na LexIA (fictícia, demonstração)'})
    for c in cands:
        c['km'] = round(km(lat, lon, c['lat'], c['lon']), 1)
    cands.sort(key=lambda c: c['km'])
    return cands[:k]


# ---------------------------------------------------------------- denúncia por categoria (regra proximos-v2)
# A pessoa escolhe SOBRE O QUE é a denúncia; só aparecem estruturas daquele tipo perto dela. Cada item traz o número
# oficial (código SIGBM/SNISB, processo ANM, CEG ANEEL) para a denúncia citar a estrutura certa.
CATEGORIAS = {
    'barragem': 'Barragem', 'mineracao': 'Mina ou mineração', 'energia': 'Energia elétrica',
    'saneamento': 'Água e esgoto', 'trabalho': 'Segurança do trabalho', 'radiacao': 'Radiação', 'outro': 'Outro assunto',
}
SETOR_IMG = {'mineracao': '/img/brand/sector-mining.jpg', 'energia': '/img/brand/sector-energy.jpg',
             'saneamento': '/img/brand/sector-sanitation.jpg', 'nuclear': '/img/brand/sector-nuclear.jpg'}
_SETOR_CATS = {'mineracao': {'mineracao', 'trabalho'}, 'energia': {'energia', 'trabalho'}, 'saneamento': {'saneamento', 'trabalho'},
               'nuclear': {'radiacao', 'trabalho'}, 'industria': {'trabalho'}}
_PJ = re.compile(r'\b(LTDA|S\.?\s?A\.?|S/A|EIRELI|ME|EPP|COMPANHIA|CIA|CONSORCIO|CONSÓRCIO|COOPERATIVA|PREFEITURA|MUNICIPIO|MUNICÍPIO|ESTADO|GOVERNO|DEPARTAMENTO|SECRETARIA|AUTARQUIA|SERVIÇO|SERVICO|SANEAMENTO|ENERGIA|ELETR|HIDRO|MINERA|FUNDAÇÃO|FUNDACAO|INSTITUTO|UNIÃO|UNIAO|DNOCS|CODEVASF|COPASA|SABESP|CEMIG|FURNAS|CHESF|PETROBRAS|VALE)\b', re.I)


def _empresa_pj(txt: str | None) -> str:
    """Nome de empresa só quando é claramente pessoa jurídica ou órgão; pessoa física não aparece."""
    t = re.sub(r'^\s*\d+([.,]\d+)?%\s*para\s*', '', str(txt or '')).split(';')[0].strip()
    t = re.sub(r'\s*\((APE|SP|PIE|REG|APE-COM)\)\s*$', '', t)
    return t if t and _PJ.search(t) else 'Responsável não exibido (pessoa física ou não identificado)'


def proximos_categoria(lat: float, lon: float, categoria: str, *, radar_items, records_by_id, minas, ativos_demo, snisb_setores, usinas, recebe, k: int = 8) -> dict:
    cat = categoria if categoria in CATEGORIAS else 'outro'
    want = (lambda cats: True) if cat == 'outro' else (lambda cats: cat in cats)
    cands = []

    def add(c, cats):
        if want(cats) and c.get('lat') is not None and c.get('lon') is not None:
            c['km'] = round(km(lat, lon, c['lat'], c['lon']), 1)
            if c['km'] <= 150:
                cands.append(c)
    for x in radar_items:
        rec = records_by_id.get(x['id'], {})
        org = rec.get('owner_cnpj_root')
        mine = x.get('kind') == 'mineracao'
        add({'id': x['id'], 'numero': x['id'], 'tipo': 'Barragem de mineração' if mine else 'Barragem sem empreendedor identificado', 'nome': x.get('name'),
             'local': f"{x.get('municipio') or '—'}/{x.get('uf') or '—'}", 'empresa': owner_label(rec) if rec else 'Sem empreendedor identificado',
             'lat': x.get('lat'), 'lon': x.get('lon'), 'setor': 'mineracao' if mine else None, 'real': True,
             'recebe_direto': bool(org and recebe(org)), 'fonte': 'ANM/SIGBM' if mine else 'ANA/SNISB'},
            {'barragem', 'mineracao', 'trabalho'} if mine else {'barragem'})
    for setor, lista in (('energia', (snisb_setores or {}).get('energia', [])), ('saneamento', (snisb_setores or {}).get('abastecimento', []))):
        for b in lista:
            add({'id': b['id'], 'numero': b['id'], 'tipo': f"Barragem · {b.get('use') or setor}", 'nome': b.get('name'), 'local': f"{(b.get('municipio') or '—').title()}/{b.get('uf') or '—'}",
                 'empresa': b.get('owner') or 'Sem empreendedor identificado', 'lat': b.get('lat'), 'lon': b.get('lon'), 'setor': setor, 'real': True,
                 'recebe_direto': False, 'fonte': 'ANA/SNISB'}, {'barragem', setor})
    for m in minas:
        add({'id': m['id'], 'numero': f"Processo ANM {m.get('processo') or m['id']}", 'tipo': f"Mina · {m.get('categoria_label') or 'lavra'}", 'nome': f"Mina de {str(m.get('substancia') or '').lower()}",
             'local': m.get('uf') or '—', 'empresa': _empresa_pj(m.get('titular')), 'lat': m.get('lat'), 'lon': m.get('lon'), 'setor': 'mineracao', 'real': True,
             'radiologico': bool(m.get('radiologico')), 'recebe_direto': False, 'fonte': 'ANM/SIGMINE'},
            {'mineracao', 'trabalho'} | ({'radiacao'} if m.get('radiologico') else set()))
    if cat in ('energia', 'trabalho', 'outro'):
        for u in usinas or []:
            if abs((u.get('lat') or 99) - lat) > 1.5 or abs((u.get('lon') or 99) - lon) > 1.5:
                continue
            add({'id': u['id'], 'numero': f"CEG {u.get('ceg') or u['id']}", 'tipo': u.get('tipo_rotulo') or 'Usina', 'nome': f"{u.get('tipo') or 'Usina'} {u.get('nome') or ''}".strip(),
                 'local': (u.get('municipios') or u.get('uf') or '—').split(';')[0], 'empresa': _empresa_pj(u.get('proprietarios')), 'lat': u.get('lat'), 'lon': u.get('lon'),
                 'setor': 'energia', 'real': True, 'recebe_direto': False, 'fonte': 'ANEEL/SIGA'}, {'energia', 'trabalho'})
    for a in ativos_demo:
        s = a.get('setor')
        cats = set(_SETOR_CATS.get(s, set())) | ({'barragem'} if 'barragem' in str(a.get('tipo_raw') or a.get('tipo') or '').lower() else set())
        if a.get('radiologico'):
            cats.add('radiacao')
        add({**a, 'numero': a['id'].split(':')[-1], 'real': False, 'recebe_direto': True, 'fonte': 'Empresa na LexIA (fictícia, demonstração)',
             'imagem': SETOR_IMG.get(s)}, cats)
    for c in cands:
        c['nome'] = re.sub(r'\s+', ' ', str(c.get('nome') or '')).strip(' -')
    cands.sort(key=lambda c: c['km'])
    # Evita que várias barragens próximas ocultem minas, usinas e outros tipos.
    varied, seen = [], set()
    for c in cands:
        family = str(c.get('tipo_raw') or c.get('tipo') or '').lower().split(' · ')[0]
        if family not in seen:
            varied.append(c)
            seen.add(family)
    selected = varied[:k]
    selected_ids = {c['id'] for c in selected}
    selected += [c for c in cands if c['id'] not in selected_ids][:max(0, k - len(selected))]
    out = sorted(selected, key=lambda c: c['km'])
    if not any(not c['real'] for c in out):  # demonstração: o ativo fictício mais próximo da categoria, mesmo longe, para mostrar o envio direto à empresa
        demo = []
        for a in ativos_demo:
            s_ = a.get('setor')
            cats = set(_SETOR_CATS.get(s_, set())) | ({'barragem'} if 'barragem' in str(a.get('tipo_raw') or '').lower() else set()) | ({'radiacao'} if a.get('radiologico') else set())
            if cat == 'outro' or cat in cats:
                demo.append({**a, 'numero': a['id'].split(':')[-1], 'real': False, 'recebe_direto': True, 'fonte': 'Empresa na LexIA (fictícia, demonstração)',
                             'imagem': SETOR_IMG.get(s_), 'km': round(km(lat, lon, a['lat'], a['lon']), 1), 'longe': True})
        if demo:
            out = out[:k - 1] + [min(demo, key=lambda c: c['km'])]
    for i, c in enumerate(out, 1):
        c['n'] = i
    return {'categoria': cat, 'categoria_nome': CATEGORIAS[cat], 'items': out, 'rule_version': 'proximos-v3-tipos',
            'vazio': None if out else 'Nada deste tipo num raio de 150 km nos cadastros públicos. Você pode descrever o local no relato.'}
