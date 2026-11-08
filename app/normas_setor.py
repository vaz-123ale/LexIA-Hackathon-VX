"""Normas por SETOR, tipo de ativo e ÁREA — filtro antes de qualquer busca (regras, RAG ou IA).

Regra normas-setor-v1:
1. Toda norma do catálogo tem metadados: setores, tipos de ativo, áreas (jurídico, operacional, segurança, ambiental,
   trabalhista, radiológico, documental), órgão e nível de verificação (T/C/I, como no dossiê de fontes).
2. Antes de sugerir normas, o sistema filtra pelo setor e pelo tipo do ativo. Norma de outro setor nunca é sugerida;
   se uma regra ou a IA propuser, ela é RECUSADA e registrada (barreira na saída).
3. Norma sem metadados = "sem classificação": vai para a fila da curadoria; não some e não é usada.
4. Uma ocorrência pode pertencer a várias áreas ao mesmo tempo (multi-rótulo).

Novas entradas (verificadas em 07/11/2026; conferir o texto consolidado no órgão antes de uso oficial):
- REN ANEEL 1.064/2023 (alterada pela REN 1.129/2025): segurança de barragens de usinas hidrelétricas fiscalizadas pela ANEEL.
- Resolução ANA 236/2017 (alterada pela Res. ANA 121/2022): barragens de usos múltiplos em rios federais fiscalizadas pela ANA.
- Portaria GM/MS 888/2021: controle e vigilância da qualidade da água para consumo humano e padrão de potabilidade.
- NR-22 (mineração) e NR-10 (eletricidade): normas regulamentadoras do MTE.
"""
from __future__ import annotations

TODOS = 'todos'
SETORES = ['mineracao', 'energia', 'saneamento', 'industria', 'nuclear']
AREAS = ['juridico', 'operacional', 'seguranca', 'ambiental', 'trabalhista', 'radiologico', 'documental']

NOVAS = {
    'aneel_1064': {'ref': 'REN ANEEL 1.064/2023 (alterada pela REN 1.129/2025)', 'text': 'Critérios e ações de segurança para barragens de usinas hidrelétricas fiscalizadas pela ANEEL: Formulário de Segurança de Barragem, Plano de Segurança, Revisão Periódica e PAE para classes A e B.',
                   'url': 'https://www.lex.com.br/resolucao-normativa-aneel-no-1-064-de-2-de-maio-de-2023'},
    'ana_236': {'ref': 'Resolução ANA 236/2017 (alterada pela Res. ANA 121/2022)', 'text': 'Segurança de barragens de usos múltiplos em rios federais fiscalizadas pela ANA: Plano de Segurança da Barragem, inspeções e revisão periódica. Em rios estaduais, o fiscalizador é o órgão estadual de recursos hídricos.',
                'url': 'https://www.snirh.gov.br/portal/snisb/Entenda_Mais/legislacao-aplicada/0236-2017_ato_normativo_20220601084300_alteracao.pdf'},
    'portaria_888': {'ref': 'Portaria GM/MS 888/2021', 'text': 'Procedimentos de controle e de vigilância da qualidade da água para consumo humano e seu padrão de potabilidade.',
                     'url': 'https://www.gov.br/saude/pt-br'},
    'nr22': {'ref': 'NR-22 (MTE) — mineração', 'text': 'Segurança e saúde ocupacional na mineração: gerenciamento de riscos, proteção dos trabalhadores e condições das frentes de lavra.',
             'url': 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes'},
    'cnen_nn301': {'ref': 'Norma CNEN NN 3.01 (Res. CNEN 323/2024)', 'text': 'Requisitos básicos de radioproteção e segurança radiológica de fontes de radiação: limites de dose, otimização e controle de exposições.',
                   'url': 'https://www.gov.br/cnen/pt-br/acesso-rapido/normas/grupo-3/NormaCNENNN3.01.pdf'},
    'ansn_302': {'ref': 'Norma ANSN 3.02 — Serviços de radioproteção (Res. ANSN 19/2026)', 'text': 'Requisitos para os serviços de radioproteção das instalações (origem: Res. CNEN 10/1988).',
                 'url': 'https://www.gov.br/cnen/pt-br/acesso-rapido/normas/grupo-3/ANSN3.02SERVICOSDERADIOPROTECAO.pdf'},
    'cnen_nn602': {'ref': 'Norma CNEN NN 6.02 (Res. CNEN 251/2019, alt. Res. 293/2022)', 'text': 'Licenciamento de instalações radiativas: autorizações de construção, operação, modificação e retirada de operação.',
                   'url': 'https://www.gov.br/cnen/pt-br/acesso-rapido/normas'},
    'cnen_nn801': {'ref': 'Norma CNEN NN 8.01 (Res. CNEN 167/2014, alt. Res. CNEN 343/2025)', 'text': 'Gerência de rejeitos radioativos de baixo e médio níveis de radiação: segregação, armazenamento, inventário e destinação.',
                   'url': 'https://www.gov.br/cnen/pt-br/acesso-rapido/normas'},
    'cnen_nn501': {'ref': 'Norma CNEN NN 5.01 (Res. CNEN 271/2021)', 'text': 'Regulamento para o transporte seguro de materiais radioativos.', 'url': 'https://www.gov.br/cnen/pt-br/acesso-rapido/normas'},
    'lei10308': {'ref': 'Lei 10.308/2001', 'text': 'Depósitos de rejeitos radioativos (iniciais, intermediários e finais): seleção de locais, construção, licenciamento, operação, fiscalização, custos e responsabilidade civil.',
                 'url': 'https://www2.camara.leg.br/legin/fed/lei/2001/lei-10308-20-novembro-2001-419960-normaatualizada-pl.html'},
    'lei6453': {'ref': 'Lei 6.453/1977', 'text': 'Responsabilidade civil por danos nucleares (independe de culpa do operador) e responsabilidade criminal por atos relacionados a atividades nucleares.',
                'url': 'https://www.planalto.gov.br/ccivil_03/leis/l6453.htm'},
    'nr1': {'ref': 'NR-1 (MTE) — GRO/PGR, com riscos psicossociais (Portaria MTE 1.419/2024; vigência desde 26/05/2026 pela Portaria MTE 765/2025)',
            'text': 'Gerenciamento de riscos ocupacionais: o PGR deve identificar, avaliar e controlar os riscos, incluindo os fatores de risco psicossociais relacionados ao trabalho.', 'url': 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes'},
    'nr7': {'ref': 'NR-7 (MTE) — PCMSO', 'text': 'Programa de Controle Médico de Saúde Ocupacional: exames ocupacionais e acompanhamento da saúde dos trabalhadores conforme os riscos do PGR (conferir periodicidades no texto da NR).', 'url': 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes'},
    'nr13': {'ref': 'NR-13 (MTE) — caldeiras, vasos de pressão e tubulações', 'text': 'Requisitos de instalação, inspeção de segurança inicial, periódica e extraordinária, prontuário e registro de segurança (conferir prazos por categoria no texto da NR).', 'url': 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes'},
    'nr17': {'ref': 'NR-17 (MTE) — ergonomia', 'text': 'Adaptação das condições de trabalho às características dos trabalhadores, incluindo organização do trabalho; base, com a NR-1, para a gestão de riscos psicossociais.', 'url': 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes'},
    'nr35': {'ref': 'NR-35 (MTE) — trabalho em altura', 'text': 'Trabalho acima de 2 metros com risco de queda: análise de risco, permissão de trabalho, capacitação e treinamento periódico (conferir periodicidade no texto da NR).', 'url': 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes'},
    'nr10': {'ref': 'NR-10 (MTE) — eletricidade', 'text': 'Segurança em instalações e serviços em eletricidade: medidas de controle, proteção coletiva e individual e capacitação.',
             'url': 'https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/participacao-social/conselhos-e-orgaos-colegiados/comissao-tripartite-partitaria-permanente/normas-regulamentadora/normas-regulamentadoras-vigentes'},
}

B = ['barragem']
META = {
    # Lei 12.334/2010 (PNSB) vale para toda barragem enquadrada, de qualquer setor
    'art2_iv': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'seguranca'], 'orgao': 'Fiscalizador da barragem', 'v': 'T'},
    'art4_iii': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'ambiental', 'seguranca'], 'orgao': 'Fiscalizador da barragem', 'v': 'T'},
    'art17_i': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'operacional', 'seguranca'], 'orgao': 'Fiscalizador da barragem', 'v': 'T'},
    'art17_p2': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'seguranca'], 'orgao': 'Fiscalizador da barragem', 'v': 'T'},
    'art17a_p2': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['juridico'], 'orgao': 'Fiscalizador', 'v': 'T'},
    'art17a_p3': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['juridico'], 'orgao': 'Fiscalizador', 'v': 'T'},
    'art18': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'operacional', 'seguranca'], 'orgao': 'Fiscalizador da barragem', 'v': 'T'},
    'art18_p2': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'seguranca'], 'orgao': 'Fiscalizador e Defesa Civil', 'v': 'T'},
    'art18_p3': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'operacional'], 'orgao': 'Fiscalizador da barragem', 'v': 'T'},
    'art18a': {'setores': [TODOS], 'tipos': B, 'areas': ['juridico', 'seguranca'], 'orgao': 'Fiscalizador e Defesa Civil', 'v': 'T'},
    'cf129': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['juridico'], 'orgao': 'Ministério Público', 'v': 'T'},
    # mineração
    'res95': {'setores': ['mineracao', 'nuclear'], 'tipos': B, 'areas': ['juridico', 'operacional', 'seguranca', 'documental'], 'orgao': 'ANM', 'v': 'T'},
    'res223': {'setores': ['mineracao', 'nuclear'], 'tipos': B, 'areas': ['juridico'], 'orgao': 'ANM', 'v': 'C'},
    'aviso_eir': {'setores': ['mineracao', 'nuclear'], 'tipos': B, 'areas': ['documental', 'juridico'], 'orgao': 'ANM', 'v': 'T'},
    'nr22': {'setores': ['mineracao', 'nuclear'], 'tipos': ['mina', 'barragem', 'equipamento', 'radiativo'], 'areas': ['trabalhista', 'seguranca', 'operacional'], 'orgao': 'MTE', 'v': 'C'},
    'cnen_nn401': {'setores': ['mineracao', 'industria', 'nuclear'], 'tipos': ['mina', 'radiativo', 'barragem', 'deposito'], 'areas': ['radiologico', 'seguranca', 'juridico'], 'orgao': 'CNEN/ANSN', 'v': 'C'},
    'lei14222': {'setores': [TODOS], 'tipos': ['radiativo', 'mina', 'deposito', 'equipamento', 'fonte'], 'areas': ['radiologico', 'juridico'], 'orgao': 'ANSN', 'v': 'T'},
    'cf_nuclear': {'setores': ['mineracao', 'energia', 'nuclear'], 'tipos': ['mina', 'radiativo', 'deposito'], 'areas': ['radiologico', 'juridico'], 'orgao': 'União', 'v': 'T'},
    # nuclear (fontes de radiação valem para qualquer setor que as tenha; o tipo do ativo filtra)
    'cnen_nn301': {'setores': [TODOS], 'tipos': ['radiativo', 'mina', 'deposito', 'equipamento', 'fonte'], 'areas': ['radiologico', 'seguranca', 'trabalhista'], 'orgao': 'ANSN/CNEN', 'v': 'C'},
    'ansn_302': {'setores': [TODOS], 'tipos': ['radiativo', 'mina', 'deposito'], 'areas': ['radiologico', 'seguranca', 'operacional'], 'orgao': 'ANSN', 'v': 'C'},
    'cnen_nn602': {'setores': [TODOS], 'tipos': ['radiativo', 'equipamento', 'deposito', 'fonte'], 'areas': ['radiologico', 'juridico', 'documental'], 'orgao': 'ANSN/CNEN', 'v': 'C'},
    'cnen_nn801': {'setores': [TODOS], 'tipos': ['deposito', 'radiativo', 'mina', 'barragem'], 'areas': ['radiologico', 'ambiental', 'operacional', 'documental'], 'orgao': 'ANSN/CNEN', 'v': 'C'},
    'cnen_nn501': {'setores': [TODOS], 'tipos': ['radiativo', 'deposito', 'equipamento', 'fonte'], 'areas': ['radiologico', 'seguranca', 'operacional'], 'orgao': 'ANSN/CNEN', 'v': 'C'},
    'lei10308': {'setores': ['nuclear', 'mineracao', 'industria'], 'tipos': ['deposito', 'radiativo'], 'areas': ['juridico', 'radiologico', 'ambiental'], 'orgao': 'ANSN', 'v': 'C'},
    'lei6453': {'setores': ['nuclear', 'energia'], 'tipos': ['radiativo', 'deposito', 'usina'], 'areas': ['juridico', 'radiologico'], 'orgao': 'ANSN / Judiciário', 'v': 'C'},
    # energia
    'aneel_1064': {'setores': ['energia'], 'tipos': B, 'areas': ['juridico', 'operacional', 'seguranca', 'documental'], 'orgao': 'ANEEL', 'v': 'C'},
    'nr10': {'setores': ['energia', 'industria', 'saneamento'], 'tipos': ['subestacao', 'usina', 'equipamento', 'eta'], 'areas': ['trabalhista', 'seguranca'], 'orgao': 'MTE', 'v': 'C'},
    # saneamento / recursos hídricos
    'ana_236': {'setores': ['saneamento'], 'tipos': B, 'areas': ['juridico', 'operacional', 'seguranca', 'documental'], 'orgao': 'ANA ou órgão estadual', 'v': 'C'},
    'portaria_888': {'setores': ['saneamento'], 'tipos': ['eta', 'reservatorio', TODOS], 'areas': ['juridico', 'operacional', 'ambiental'], 'orgao': 'Ministério da Saúde / vigilância sanitária', 'v': 'C'},
    # transversais
    'condicionante': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['ambiental', 'juridico', 'documental'], 'orgao': 'Órgão ambiental', 'v': 'T'},
    'nr1': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['trabalhista', 'seguranca', 'documental'], 'orgao': 'MTE', 'v': 'C'},
    'nr7': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['trabalhista', 'documental'], 'orgao': 'MTE', 'v': 'C'},
    'nr13': {'setores': [TODOS], 'tipos': ['equipamento', 'usina', 'eta', 'radiativo', 'unidade_sst'], 'areas': ['trabalhista', 'seguranca', 'operacional', 'documental'], 'orgao': 'MTE', 'v': 'C'},
    'nr17': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['trabalhista', 'seguranca'], 'orgao': 'MTE', 'v': 'C'},
    'nr35': {'setores': [TODOS], 'tipos': [TODOS], 'areas': ['trabalhista', 'seguranca', 'operacional'], 'orgao': 'MTE', 'v': 'C'},
    'nr20': {'setores': [TODOS], 'tipos': ['equipamento', 'tanque', TODOS], 'areas': ['trabalhista', 'seguranca'], 'orgao': 'MTE', 'v': 'T'},
}

# Tipo de ativo da LexIA → família usada nos metadados
TIPO_FAMILIA = {'barragem': 'barragem', 'barragem_usina': 'barragem', 'reservatorio': 'reservatorio', 'mina': 'mina', 'radiativo': 'radiativo',
                'equipamento': 'equipamento', 'usina': 'usina', 'subestacao': 'subestacao', 'eta': 'eta', 'elevatoria': 'equipamento',
                'unidade_sst': 'unidade_sst', 'mina_uranio': 'mina', 'instalacao_radiativa': 'radiativo', 'deposito_rejeitos': 'deposito', 'fonte_radioativa': 'fonte'}


def setor_do_alvo(dam: dict | None) -> tuple[str | None, str | None]:
    """(setor, tipo) do que está sendo denunciado/avaliado. None = desconhecido (não filtra por setor, só por tipo)."""
    if not dam:
        return None, None
    if dam.get('setor'):
        return dam['setor'], TIPO_FAMILIA.get(dam.get('tipo') or '', dam.get('tipo'))
    k = dam.get('kind')
    if k == 'mineracao':
        return 'mineracao', 'barragem'
    if k == 'mina':
        return 'mineracao', 'radiativo' if dam.get('radiologico') else 'mina'
    if k == 'orfa':
        return None, 'barragem'   # barragem sem empreendedor (SNISB): uso pode ser qualquer um → só normas gerais
    return None, None


def aplica(key: str, setor: str | None, tipo: str | None) -> tuple[bool, str]:
    m = META.get(key)
    if not m:
        return False, 'norma sem classificação (fila da curadoria)'
    if setor and TODOS not in m['setores'] and setor not in m['setores']:
        return False, f"norma do setor {', '.join(m['setores'])}, não de {setor}"
    if setor is None and TODOS not in m['setores']:
        return False, 'setor do alvo desconhecido: só normas gerais'
    if tipo and TODOS not in m['tipos'] and tipo not in m['tipos']:
        return False, f"norma para {', '.join(m['tipos'])}, não para {tipo}"
    return True, ''


def filtrar(keys: list[str], setor: str | None, tipo: str | None) -> tuple[list[str], list[dict]]:
    ok, recusadas = [], []
    for k in dict.fromkeys(keys):
        a, why = aplica(k, setor, tipo)
        (ok.append(k) if a else recusadas.append({'norma': k, 'motivo': why}))
    return ok, recusadas


def areas(keys: list[str]) -> list[str]:
    return sorted({a for k in keys for a in META.get(k, {}).get('areas', [])}, key=AREAS.index)


def cobertura(catalog: dict) -> dict:
    """Matriz setor × área → normas; e o que está sem classificação."""
    mat = {s: {a: [] for a in AREAS} for s in SETORES}
    for k, m in META.items():
        for s in SETORES:
            if TODOS in m['setores'] or s in m['setores']:
                for a in m['areas']:
                    mat[s][a].append({'key': k, 'ref': catalog.get(k, {}).get('ref', k), 'v': m['v']})
    lacunas = [{'setor': s, 'area': a} for s in SETORES for a in AREAS if not mat[s][a]]
    return {'rule_version': 'normas-setor-v1', 'setores': SETORES, 'areas': AREAS, 'matriz': mat, 'lacunas': lacunas,
            'sem_classificacao': sorted(k for k in catalog if k not in META), 'total_normas': len(catalog)}


# provisões do corpus da Central de IA (data/provisions.json) → setor pelo órgão
ORGAO_SETOR = {'ANM': ['mineracao', 'nuclear'], 'ANEEL': ['energia'], 'ANP': ['energia', 'industria'], 'ANA': ['saneamento'], 'MTE': [TODOS], 'ANSN': [TODOS], 'CNEN': [TODOS]}


def aviso_fora_do_setor(texto: str, setor: str | None) -> str | None:
    """Pergunta cita órgão de outro setor? Responde, mas avisa que não se aplica ao perfil."""
    import re as _re
    if not setor:
        return None
    for org, sets in ORGAO_SETOR.items():
        if TODOS not in sets and setor not in sets and _re.search(r'\b' + org + r'\b', texto or '', _re.I):
            return f"A pergunta cita {org}, órgão do setor {', '.join(sets)}. A resposta vale para esse setor e não se aplica automaticamente ao perfil {setor}."
    return None


def provisao_aplica(p: dict, setor: str | None) -> bool:
    if not setor:
        return True
    reg = (p.get('regulator') or '').upper()
    s = next((v for k, v in ORGAO_SETOR.items() if k in reg), [TODOS])
    return TODOS in s or setor in s
