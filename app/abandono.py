"""Radar de abandono e barragens órfãs — regras explicáveis e versionadas (abandono-v1).

O que este módulo faz:
- Lê campos DECLARADOS no SIGBM/ANM (e complementos do SNISB/ANA) e marca SINAIS de possível
  abandono ou falta de manutenção. Sinal não é conclusão: cada sinal mostra o campo e o valor de origem.
- Combina sinais com a CONSEQUÊNCIA declarada (DPA oficial, população a jusante, nível de emergência)
  para sugerir um NÍVEL DE ATENÇÃO. O nível não substitui CRI/DPA nem a decisão do órgão fiscalizador.
- Lista a cadeia de responsáveis prevista na Lei 12.334/2010 (com redação da Lei 14.066/2020)
  e monta um plano de contingência com base legal, dependências e viabilidade relativa.
- Gera RASCUNHO de representação (Art. 17-A §2º). Nada é enviado automaticamente.

Fontes legais citadas (texto compilado no Planalto):
https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12334.htm
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

RULE_VERSION = 'abandono-v1'
LAW_URL = 'https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2010/lei/l12334.htm'
LAW = 'Lei 12.334/2010 (red. Lei 14.066/2020)'

ARTICLES = {
    'art2_iv': {'ref': 'Art. 2º, IV', 'text': 'Empreendedor: quem explora a barragem; na falta de quem explore, responde subsidiariamente o proprietário do terreno.'},
    'art4_iii': {'ref': 'Art. 4º, III', 'text': 'O empreendedor é o responsável legal pela segurança da barragem e responde independentemente de culpa.'},
    'art17_i': {'ref': 'Art. 17, I', 'text': 'O empreendedor deve prover recursos para garantir a segurança da barragem até a completa descaracterização.'},
    'art17_p2': {'ref': 'Art. 17, §2º', 'text': 'Barragens de rejeitos com categoria de risco ou DPA médio/alto: o órgão fiscalizador pode exigir caução, seguro, fiança ou outra garantia.'},
    'art17a_p2': {'ref': 'Art. 17-A, §2º', 'text': 'Qualquer pessoa que constatar infração pode dirigir representação às autoridades competentes.'},
    'art17a_p3': {'ref': 'Art. 17-A, §3º', 'text': 'A autoridade que tiver conhecimento de infração deve promover a apuração imediata, sob pena de corresponsabilidade.'},
    'art18': {'ref': 'Art. 18, caput', 'text': 'Barragem que não atender aos requisitos de segurança deve ser recuperada, desativada ou descaracterizada.'},
    'art18_p2': {'ref': 'Art. 18, §2º', 'text': 'Em caso de omissão do empreendedor, o órgão fiscalizador informa a Defesa Civil (Lei 12.340/2010, art. 4º); os custos são ressarcidos pelo empreendedor.'},
    'art18_p3': {'ref': 'Art. 18, §3º', 'text': 'Empreendedor ou sucessor deve manter o monitoramento da barragem desativada até a descaracterização.'},
    'art18a': {'ref': 'Art. 18-A', 'text': 'Vedada a implantação de barragem de rejeitos com comunidade na Zona de Autossalvamento (ZAS); trata da segurança de quem está a jusante.'},
    'cf129': {'ref': 'CF, art. 129, III', 'text': 'O Ministério Público promove inquérito civil e ação civil pública para proteção do meio ambiente e de interesses difusos.', 'url': 'https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm'},
}


def cite(key: str) -> dict:
    a = ARTICLES[key]
    return {'law': 'Constituição Federal' if key == 'cf129' else LAW, 'ref': a['ref'], 'text': a['text'], 'url': a.get('url', LAW_URL)}


def br_num(v) -> float | None:
    """Converte '1.000.000,00' ou '410689,73' (formatos da fonte) em número."""
    if v in (None, '', '-'):
        return None
    s = str(v).strip()
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def br_date(v) -> date | None:
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})', str(v or ''))
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


def owner_profile(rec: dict, owner_counts: Counter) -> dict:
    n = owner_counts.get(rec.get('owner_key') or rec.get('owner_cnpj') or rec.get('owner_name_norm') or rec['id'], 1)
    if rec.get('owner_doc_type') == 'CPF_MASCARADO_OCULTO':
        kind = 'Pessoa física'
    elif 'cooperativa' in (rec.get('owner_name_norm') or '').lower():
        kind = 'Cooperativa'
    elif rec.get('owner_cnpj'):
        kind = 'Pessoa jurídica'
    else:
        kind = 'Não informado'
    return {'kind': kind, 'dams_in_sigbm': n, 'small': n <= 5 or kind in ('Pessoa física', 'Cooperativa')}


def _sig(code, label, weight, field, value, basis, source='ANM_SIGBM'):
    return {'code': code, 'label': label, 'weight': weight, 'evidence': {'field': field, 'value': value, 'source': source}, 'basis': basis}


def signals(rec: dict, snisb: dict | None, owner: dict, today: date) -> list[dict]:
    g = lambda k: rec.get(k) or ''
    out = []
    status = g('operational_status')
    if status == 'Inativa' and not rec.get('decom_phase'):
        out.append(_sig('INATIVA_SEM_PROJETO', 'Inativa sem projeto de descaracterização declarado', 3, 'Situação Operacional / Fase do projeto de descaracterização',
                        f'{status} / (vazio)', [cite('art18'), cite('art18_p3')]))
    if g('will_operate_again') == 'Não' and not rec.get('decom_works_start') and status != 'Em Descaracterização':
        out.append(_sig('NAO_VOLTA_SEM_OBRA', 'Não voltará a operar e não há início de obra declarado', 2, 'A barragem voltará a operar? / Início das obras',
                        'Não / (vazio)', [cite('art17_i'), cite('art18')]))
    dce = ' '.join([g('dce_risr'), g('dce_rpsb')])
    if 'Não Enviado' in dce or g('dce_reason') == 'Não foi entregue':
        out.append(_sig('DCE_NAO_ENVIADA', 'Declaração de estabilidade não enviada', 3, 'Status DCE RISR / RPSB / Motivo de envio',
                        ' · '.join(v for v in (g('dce_risr'), g('dce_rpsb'), g('dce_reason')) if v), [cite('art4_iii'), cite('art17a_p3')]))
    elif 'Não Atestado' in dce:
        out.append(_sig('DCE_NAO_ATESTADA', 'Estabilidade não atestada na última campanha', 3, 'Status DCE RISR / RPSB',
                        ' · '.join(v for v in (g('dce_risr'), g('dce_rpsb')) if v), [cite('art18'), cite('art17a_p3')]))
    for field, label, column in (('spillway', 'extravasor', 'Confiabilidade das estruturas extravasoras'), ('percolation', 'percolação', 'Percolação'),
                                 ('deformation', 'deformações', 'Deformações e recalque'), ('slope_deterioration', 'taludes', 'Deterioração dos taludes / paramentos')):
        if g(field).startswith('6'):
            out.append(_sig(f'SEM_CORRECAO_{field.upper()}', f'Problema em {label} sem medida corretiva declarada', 2, column, g(field)[:140], [cite('art18')]))
    if g('pae_status').startswith('Não possui PAE (quando for exigido'):
        out.append(_sig('PAE_AUSENTE', 'PAE exigido e não declarado', 2, 'PAE', g('pae_status'), [cite('art4_iii')]))
    if 'sem processo de instalação' in g('instrumentation') or g('instrumentation').startswith('Barragem não instrumentada em desacordo'):
        out.append(_sig('INSTRUMENTACAO', 'Instrumentação em desacordo com o projeto, sem adequação', 1, 'Instrumentação', g('instrumentation')[:140], [cite('art18')]))
    if 'sem profissional' in g('safety_team'):
        out.append(_sig('SEM_EQUIPE', 'Sem profissional técnico qualificado declarado', 2, 'Equipe de segurança', g('safety_team')[:140], [cite('art4_iii')]))
    if snisb and rec.get('pnsb') == 'Sim':
        last = snisb.get('last_inspection')
        if not last:
            out.append(_sig('SEM_INSPECAO', 'Sem data de inspeção registrada no SNISB', 1, 'INS_DT_INSPECAO', '(vazio)', [cite('art17a_p3')], 'ANA_SNISB'))
        elif (today - date.fromisoformat(last)).days > 3 * 365:
            out.append(_sig('INSPECAO_ANTIGA', f'Última inspeção registrada há mais de 3 anos ({last})', 1, 'INS_DT_INSPECAO', last, [cite('art17a_p3')], 'ANA_SNISB'))
    if snisb and snisb.get('fined') == 'Sim':
        out.append(_sig('AUTUADA', 'Barragem autuada (registro no SNISB)', 1, 'BARRAGEM_AUTUADA', 'Sim', [cite('art17a_p3')], 'ANA_SNISB'))
    if owner['small'] and out:
        out.append(_sig('CONTEXTO_PORTE', f"Contexto: {owner['kind'].lower()} com {owner['dams_in_sigbm']} barragem(ns) no SIGBM — menor capacidade de absorver custos (não é irregularidade)",
                        1, 'CPF_CNPJ (contagem)', str(owner['dams_in_sigbm']), [cite('art17_p2')]))
    return out


def consequence(rec: dict) -> dict:
    pop = rec.get('downstream_population') or ''
    emerg = rec.get('emergency_level') or ''
    items = []
    if rec.get('dpa') == 'Alta':
        items.append('DPA oficial Alta')
    if pop.startswith('Existente'):
        items.append('População permanente a jusante')
    if rec.get('people_affected'):
        items.append(f"Pessoas possivelmente afetadas: {rec['people_affected']}")
    if emerg and emerg != 'Sem emergência':
        items.append(f'Nível declarado: {emerg}')
    if rec.get('cyanide') == 'Sim':
        items.append('Armazena rejeito com cianeto')
    high = rec.get('dpa') == 'Alta' or pop.startswith('Existente') or (emerg not in ('', 'Sem emergência'))
    return {'high': high, 'items': items or ['Sem agravante declarado']}


CORE = ('INATIVA_SEM_PROJETO', 'NAO_VOLTA_SEM_OBRA', 'DCE_NAO_ENVIADA', 'DCE_NAO_ATESTADA', 'SEM_CORRECAO_', 'SEM_EQUIPE', 'SEM_EMPREENDEDOR', 'FASE')


def is_core(sig: dict) -> bool:
    return sig['code'].startswith(CORE)


def attention(score: int, conseq_high: bool, core: bool = True) -> str:
    """Crítica/Alta exigem ao menos um sinal central de abandono (não basta somar sinais genéricos)."""
    if core and score >= 5 and conseq_high:
        return 'Crítica'
    if core and ((score >= 3 and conseq_high) or score >= 6):
        return 'Alta'
    if score >= 2:
        return 'Moderada'
    return 'Baixa' if score else 'Sem sinal'


LEVEL_ORDER = {'Crítica': 0, 'Alta': 1, 'Moderada': 2, 'Baixa': 3, 'Sem sinal': 4}


def assess_mining(records: list[dict], snisb_mining: dict, today: date) -> list[dict]:
    counts = Counter(r.get('owner_key') or r.get('owner_cnpj') or r.get('owner_name_norm') or r['id'] for r in records)
    out = []
    for r in records:
        own = owner_profile(r, counts)
        sn = snisb_mining.get(r['id'])
        sig = signals(r, sn, own, today)
        score = sum(s['weight'] for s in sig if s['code'] != 'CONTEXTO_PORTE') + (1 if any(s['code'] == 'CONTEXTO_PORTE' for s in sig) else 0)
        cq = consequence(r)
        out.append({'id': r['id'], 'kind': 'mineracao', 'name': r.get('name'), 'uf': r.get('uf'), 'municipio': r.get('municipio'),
                    'lat': r.get('lat'), 'lon': r.get('lon'), 'owner_label': r.get('owner_name') if own['kind'] != 'Pessoa física' else 'Pessoa física (nome não exibido)',
                    'owner': own, 'operational_status': r.get('operational_status'), 'dpa': r.get('dpa'), 'cri': r.get('cri'),
                    'emergency_level': r.get('emergency_level'), 'managing_unit': r.get('managing_unit'), 'containment': r.get('containment'),
                    'signals': sig, 'score': score, 'consequence': cq, 'attention': attention(score, cq['high'], any(map(is_core, sig))),
                    'snisb': sn, 'rule_version': RULE_VERSION, 'source_id': 'ANM_SIGBM', 'origin': 'DADO_OFICIAL'})
    out.sort(key=lambda x: (LEVEL_ORDER[x['attention']], -x['score']))
    return out


def assess_orphan(o: dict, today: date) -> dict:
    sig = [_sig('SEM_EMPREENDEDOR', 'Sem empreendedor identificado no cadastro nacional', 3, 'NM_EMPREENDEDOR', '(vazio)', [cite('art2_iv'), cite('art17a_p3')], 'ANA_SNISB')]
    if not o.get('last_inspection'):
        sig.append(_sig('SEM_INSPECAO', 'Sem data de inspeção registrada', 1, 'INS_DT_INSPECAO', '(vazio)', [cite('art17a_p3')], 'ANA_SNISB'))
    if o.get('has_pae') == 'Não' and o.get('damage_potential') == 'Alto':
        sig.append(_sig('PAE_AUSENTE', 'Sem PAE com DPA Alto', 2, 'POSSUI_PAE', 'Não', [cite('art4_iii')], 'ANA_SNISB'))
    if o.get('phase') in ('Desativada', 'Rompida'):
        sig.append(_sig('FASE', f"Fase de vida: {o['phase']}", 2, 'FASE_DE_VIDA', o['phase'], [cite('art18_p3')], 'ANA_SNISB'))
    score = sum(s['weight'] for s in sig)
    high = o.get('damage_potential') == 'Alto' or o.get('use') == 'Abastecimento humano'
    items = [x for x in (o.get('damage_potential') == 'Alto' and 'DPA Alto (SNISB)', o.get('use') == 'Abastecimento humano' and 'Uso: abastecimento humano',
                         o.get('risk_category') == 'Alto' and 'Categoria de risco Alta') if x]
    return {**o, 'kind': 'orfa', 'signals': sig, 'score': score, 'consequence': {'high': high, 'items': items or ['Sem agravante classificado']},
            'attention': attention(score, high), 'rule_version': RULE_VERSION}


def assess_orphans(orphans: list[dict], today: date) -> list[dict]:
    out = [assess_orphan(o, today) for o in orphans]
    out.sort(key=lambda x: (LEVEL_ORDER[x['attention']], -x['score']))
    return out


# ---------------------------------------------------------------- responsáveis e plano

def responsibles(item: dict) -> list[dict]:
    if item['kind'] == 'orfa':
        reg = item.get('regulator') or 'Órgão fiscalizador estadual/federal (como na fonte)'
        return [
            {'role': 'Empreendedor', 'who': 'Não identificado no SNISB', 'status': 'faltando', 'basis': [cite('art2_iv')],
             'how': 'Pedir ao órgão fiscalizador o histórico de outorga/cadastro da barragem.'},
            {'role': 'Proprietário do terreno (responsável subsidiário)', 'who': 'A identificar', 'status': 'faltando', 'basis': [cite('art2_iv')],
             'how': 'Cruzar a coordenada com bases fundiárias públicas (CAR/SICAR, SIGEF/INCRA) e cartório de imóveis. Não automatizado.'},
            {'role': 'Órgão fiscalizador', 'who': reg, 'status': 'identificado', 'basis': [cite('art17a_p3')], 'how': 'Destinatário da representação.'},
            {'role': 'Defesa Civil', 'who': f"Municipal de {item.get('municipio') or '—'} e estadual ({item.get('uf') or '—'})", 'status': 'identificado',
             'basis': [cite('art18_p2')], 'how': 'Informada pelo fiscalizador em caso de omissão; pode agir antes em risco iminente.'},
            {'role': 'Ministério Público', 'who': f"MP estadual ({item.get('uf') or '—'})", 'status': 'identificado', 'basis': [cite('cf129')],
             'how': 'Acionável se a apuração não ocorrer.'},
        ]
    own = item['owner']
    who = item.get('owner_label') or 'Não informado'
    return [
        {'role': 'Empreendedor (responsável legal)', 'who': who, 'status': 'identificado' if own['kind'] != 'Não informado' else 'faltando',
         'basis': [cite('art2_iv'), cite('art4_iii'), cite('art17_i')],
         'how': 'Verificar a situação cadastral do CNPJ na Receita Federal (consulta pública).' if own['kind'] in ('Pessoa jurídica', 'Cooperativa')
                else 'Pessoa física: contato apenas pelo órgão fiscalizador; a LexIA não exibe nem busca dados pessoais.'},
        {'role': 'Sucessor ou adquirente', 'who': 'A verificar (venda, incorporação, recuperação judicial)', 'status': 'a verificar', 'basis': [cite('art18_p3')],
         'how': 'Consultar processo minerário na ANM e Junta Comercial.'},
        {'role': 'Proprietário do terreno (subsidiário)', 'who': 'A verificar, só se ninguém explorar a barragem', 'status': 'condicional', 'basis': [cite('art2_iv')],
         'how': 'CAR/SICAR, SIGEF/INCRA, cartório. Não automatizado.'},
        {'role': 'Órgão fiscalizador', 'who': f"ANM — unidade gestora {item.get('managing_unit') or '(não informada)'} (sigla como na fonte)", 'status': 'identificado',
         'basis': [cite('art17a_p3'), cite('art18_p2')], 'how': 'Destinatário da representação; deve apurar e, se houver omissão, acionar a Defesa Civil.'},
        {'role': 'Defesa Civil', 'who': f"Municipal de {item.get('municipio') or '—'} e estadual ({item.get('uf') or '—'})", 'status': 'identificado',
         'basis': [cite('art18_p2')], 'how': 'Executa medidas em caso de omissão; custos ressarcidos pelo empreendedor.'},
        {'role': 'Ministério Público', 'who': f"MP estadual ({item.get('uf') or '—'}) e MPF", 'status': 'identificado', 'basis': [cite('cf129')],
         'how': 'Acionável se a apuração não ocorrer.'},
    ]


STEP_LIB = [
    # id, título, papel, base, complexidade, custo relativo, depende de, quando aplicar
    ('confirmar', 'Confirmar os sinais nos dados oficiais mais recentes', 'Curadoria / analista', [], 'Baixa', 'Baixo', [], 'sempre'),
    ('responsavel', 'Identificar o responsável legal e a situação cadastral', 'Jurídico', ['art2_iv', 'art4_iii'], 'Média', 'Baixo', ['confirmar'], 'sempre'),
    ('representacao', 'Revisar e enviar a representação ao órgão fiscalizador', 'Jurídico (aprovação humana)', ['art17a_p2', 'art17a_p3'], 'Baixa', 'Baixo', ['confirmar'], 'sempre'),
    ('defesa_civil', 'Comunicar Defesa Civil municipal e estadual', 'Gestor / Defesa Civil', ['art18_p2'], 'Baixa', 'Baixo', ['representacao'], 'consequencia'),
    ('zas', 'Verificar população na mancha de inundação e rotas de fuga (ZAS)', 'Defesa Civil / especialista', ['art18a'], 'Média', 'Médio', ['defesa_civil'], 'populacao'),
    ('garantia', 'Verificar se há caução, seguro ou fiança exigível', 'Jurídico / fiscalizador', ['art17_p2'], 'Média', 'Baixo', ['responsavel'], 'rejeitos'),
    ('inspecao', 'Inspeção de campo por profissional habilitado (com ART)', 'Fiscalizador ou empreendedor', ['art17a_p3'], 'Alta', 'Alto', ['representacao'], 'sempre'),
    ('monitoramento', 'Monitoramento mínimo provisório (nível, inspeção visual, drenagem)', 'Empreendedor/sucessor; Defesa Civil se houver omissão', ['art18_p3', 'art18_p2'], 'Média', 'Médio', ['inspecao'], 'sempre'),
    ('destino', 'Definir destino: recuperar ou descaracterizar', 'Empreendedor + fiscalizador', ['art18', 'art17_i'], 'Alta', 'Alto', ['inspecao', 'responsavel'], 'sempre'),
    ('mp', 'Acionar o Ministério Público se não houver apuração', 'Jurídico', ['cf129', 'art17a_p3'], 'Baixa', 'Baixo', ['representacao'], 'escalonamento'),
]


def plan(item: dict, progress: dict | None = None) -> dict:
    progress = progress or {}
    cq = item['consequence']
    pop = any('População' in x or 'Pessoas' in x or 'abastecimento' in x.lower() for x in cq['items'])
    rejeitos = item.get('containment') in ('Rejeitos', 'Mista') and (item.get('dpa') in ('Alta', 'Média') or item.get('cri') in ('Alta', 'Média'))
    cond = {'sempre': True, 'consequencia': cq['high'], 'populacao': pop, 'rejeitos': rejeitos, 'escalonamento': item['attention'] in ('Crítica', 'Alta')}
    steps = []
    for sid, title, role, basis, cx, cost, deps, when in STEP_LIB:
        if not cond[when]:
            continue
        p = progress.get(sid, {})
        steps.append({'id': sid, 'title': title, 'role': role, 'basis': [cite(b) for b in basis], 'complexity': cx, 'relative_cost': cost,
                      'depends_on': deps, 'status': p.get('status', 'pendente'), 'note': p.get('note'), 'by': p.get('actor'), 'at': p.get('at')})
    done = {s['id'] for s in steps if s['status'] == 'feito'}
    for s in steps:
        s['blocked'] = s['status'] != 'feito' and any(d not in done for d in s['depends_on'] if d in {x['id'] for x in steps})
    who = responsibles(item)
    owner_known = any(r['role'].startswith('Empreendedor') and r['status'] == 'identificado' for r in who)
    if item['kind'] == 'orfa':
        via = 'Baixa: sem empreendedor; depende de identificar o proprietário do terreno ou de ação do poder público.'
        path = 'Representação ao fiscalizador + Defesa Civil; em paralelo, pesquisa fundiária do terreno.'
    elif item['owner']['kind'] in ('Pessoa jurídica', 'Cooperativa') and owner_known:
        via = 'Alta: responsável identificado por CNPJ; cobrança direta via fiscalizador é o caminho mais rápido.'
        path = 'Representação à unidade gestora da ANM citando os sinais; pedir apuração e cronograma de recuperação ou descaracterização.'
    else:
        via = 'Média: responsável é pessoa física ou não informado; contato somente via órgão fiscalizador.'
        path = 'Representação à ANM; Defesa Civil informada se houver consequência alta.'
    return {'dam_id': item['id'], 'attention': item['attention'], 'steps': steps, 'progress': {'done': len(done), 'total': len(steps)},
            'viability': via, 'fastest_path': path, 'rule_version': RULE_VERSION,
            'disclaimer': 'Plano sugerido por regras versionadas. Não é parecer jurídico; requer validação de profissional competente.'}


def draft_representation(item: dict, today: date) -> str:
    sig = '\n'.join(f"  {i}. {s['label']} — campo \"{s['evidence']['field']}\": {s['evidence']['value']} (fonte: {s['evidence']['source']})"
                    for i, s in enumerate(item['signals'], 1))
    dest = next((r['who'] for r in responsibles(item) if r['role'] == 'Órgão fiscalizador'), 'Órgão fiscalizador')
    ident = (f"ID SIGBM {item['id'].split('-', 1)[1]}" if item['kind'] == 'mineracao' else f"código SNISB {item.get('snisb_id')}")
    return f"""RASCUNHO — REQUER REVISÃO E ASSINATURA HUMANA. NÃO FOI ENVIADO.

À {dest}

Assunto: Representação (Lei 12.334/2010, art. 17-A, §2º) — barragem "{item.get('name')}", {ident}, {item.get('municipio') or '—'}/{item.get('uf') or '—'}

Com base nos dados públicos consultados em {today.strftime('%d/%m/%Y')}, foram observados os seguintes sinais que podem indicar falta de manutenção ou abandono:
{sig}

Consequência declarada: {'; '.join(item['consequence']['items'])}.

Considerando que o empreendedor é o responsável legal pela segurança da barragem (art. 4º, III) até a completa descaracterização (art. 17, I), e que a autoridade que toma conhecimento de infração deve promover sua apuração imediata (art. 17-A, §3º), solicita-se:
  a) a verificação da situação da estrutura e do responsável atual;
  b) se confirmada a omissão, a comunicação à Defesa Civil, nos termos do art. 18, §2º;
  c) informação sobre o cronograma de recuperação, desativação ou descaracterização (art. 18).

Os sinais acima são leitura dos campos declarados e não constituem conclusão técnica.

[Local], [data]
[Nome, função e contato do remetente]
"""


def panorama(mining: list[dict], orphans_assessed: list[dict]) -> dict:
    lv = lambda xs: dict(Counter(x['attention'] for x in xs))
    by_uf = Counter(x['uf'] for x in orphans_assessed if x['attention'] in ('Crítica', 'Alta'))
    sig_count = Counter(s['code'] for x in mining for s in x['signals'])
    small = [x for x in mining if x['owner']['small']]
    flagged = [x for x in mining if x['attention'] in ('Crítica', 'Alta')]
    return {
        'mining': {'total': len(mining), 'levels': lv(mining), 'top_signals': sig_count.most_common(8),
                   'inactive': sum(1 for x in mining if x['operational_status'] == 'Inativa'),
                   'flagged_small_owner': sum(1 for x in flagged if x['owner']['small']), 'flagged': len(flagged),
                   'small_owner_share': round(100 * len(small) / len(mining)) if mining else 0},
        'orphans': {'total': len(orphans_assessed), 'levels': lv(orphans_assessed), 'dpa_alto': sum(1 for x in orphans_assessed if x.get('damage_potential') == 'Alto'),
                    'without_inspection': sum(1 for x in orphans_assessed if not x.get('last_inspection')), 'top_uf': by_uf.most_common(8),
                    'mining_orphans': sum(1 for x in orphans_assessed if 'Minera' in (x.get('regulator') or ''))},
        'rule_version': RULE_VERSION,
        'reading': 'Contagens sobre dados declarados nas fontes oficiais. Sinal de atenção não é conclusão nem acusação.',
    }
