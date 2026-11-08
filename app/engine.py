"""Motor determinístico de triagem. NÃO emite parecer regulatório ou conformidade.

O resultado é triagem de hipóteses com dados sintéticos e referências catalogadas.
Nenhuma função deve atribuir multa, prazo não identificado ou decisão de segurança.
Este módulo é a camada "REGRA VERIFICA" da cadeia: a IA pode propor, mas o estado
de triagem sai daqui, de forma reprodutível e testável.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import date
from typing import Any
import re

AS_OF = date(2026, 11, 6)

STATES = {
    'REVIEW': 'Candidato à revisão',
    'INSUFFICIENT': 'Dados insuficientes',
    'OUT_OF_SCOPE': 'Fora do escopo',
    'NO_LINK': 'Sem vínculo demonstrado',
    'FUTURE_REVIEW': 'Transição futura',
    'MONITOR': 'Monitorar (sem obrigação vigente)',
}

ANM_PHASES = [
    (date(2027, 4, 22), 'ANM220-arts76-77', 'arts. 76–77'),
    (date(2027, 8, 2), 'ANM220-geral', 'regra geral'),
    (date(2029, 12, 26), 'ANM220-art7-p1', '§1º art. 7º'),
]

NR20_CONDITIONS = {
    'building': ('Tipo de edificação', lambda v: v is True),
    'generator': ('Presença de gerador', lambda v: v is True),
    'fuel': ('Combustível utilizado', lambda v: v in ('diesel', 'biodiesel')),
    'tank_config': ('Configuração do tanque', lambda v: v in ('separate', 'integrated')),
}


@dataclass(frozen=True)
class Finding:
    asset_id: str
    scenario: str
    state: str
    headline: str
    rationale: str
    missing: list[str]
    actions: list[str]
    source_ids: list[str]
    legal_deadline: str | None = None
    reviewer: str = "Profissional competente a definir"
    evidence_state: str = "Pendente de revisão humana"
    provisions: list[str] = field(default_factory=list)
    conditions: list[dict[str, Any]] = field(default_factory=list)
    as_of: str = AS_OF.isoformat()
    rule_id: str = ''

    def payload(self) -> dict[str, Any]:
        return asdict(self)


def _parse(d: date | str | None) -> date:
    if d is None:
        return AS_OF
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def nr20_conditions(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Avalia cada condição modelada: atendida, não atendida ou dado ausente."""
    out = []
    for key, (label, test) in NR20_CONDITIONS.items():
        value = facts.get(key)
        if value in (None, ''):
            status = 'MISSING'
        else:
            status = 'MET' if test(value) else 'NOT_MET'
        out.append({'key': key, 'label': label, 'value': value, 'status': status})
    return out


def analyze(asset: dict[str, Any], scenario: str, as_of: date | str | None = None) -> Finding:
    """Avalia somente os casos sintéticos e as condições modeladas, na data informada."""
    aid = asset['id']
    facts = asset.get('facts', {})
    when = _parse(as_of)
    iso = when.isoformat()
    if scenario == 'nr20':
        refs = ['F02', 'F41', 'F42']
        provs = ['NR20-AIII-2.1.1@2025', 'NR20-20.2.2a']
        if facts.get('offshore_excluded') is True:
            return Finding(aid, scenario, 'OUT_OF_SCOPE', 'Exclusão de escopo no cenário',
                'A hipótese de plataforma marítima foi cadastrada na exclusão de NR-20, item 20.2.2(a); não aplicar automaticamente esta regra ao ativo.',
                ['Analisar regime apropriado à atividade marítima.'],
                ['Encaminhar dúvida de escopo para revisão setorial.'], refs,
                provisions=['NR20-20.2.2a'], conditions=[{'key': 'offshore_excluded', 'label': 'Exclusão 20.2.2(a)', 'value': True, 'status': 'MET'}],
                as_of=iso, rule_id='NR20-R1-exclusao')
        if facts.get('nr20_scope') == 'no_documentary_link' or asset.get('kind') == 'dam':
            return Finding(aid, scenario, 'NO_LINK', 'Sem vínculo demonstrado',
                'A presença do ativo no mesmo portfólio não prova incidência da alteração.',
                ['Documento ou atributo que conecte este ativo ao requisito, se existir.'],
                ['Não criar obrigação apenas por associação empresarial.'], refs,
                provisions=provs, as_of=iso, rule_id='NR20-R2-vinculo')
        conds = nr20_conditions(facts)
        missing = [c['label'] for c in conds if c['status'] == 'MISSING']
        if missing:
            return Finding(aid, scenario, 'INSUFFICIENT', 'Dados insuficientes para triagem',
                'A comparação textual é conhecida, mas faltam atributos indispensáveis para examinar a condição da exceção.',
                missing, ['Solicitar somente os atributos ausentes.', 'Não emitir declaração de aplicabilidade.'], refs,
                provisions=provs, conditions=conds, as_of=iso, rule_id='NR20-R3-dados')
        if all(c['status'] == 'MET' for c in conds):
            if when < date(2025, 1, 22):
                return Finding(aid, scenario, 'FUTURE_REVIEW', 'Alteração ainda não vigente na data simulada',
                    'Na data simulada, a Portaria MTE 60/2025 ainda não produzia efeitos; vale a redação anterior do item 2.1.1 (F42) para comparação.',
                    ['Classificação completa da instalação e demais condições do Anexo III.'],
                    ['Preparar comparação de texto anterior e novo.', 'Submeter ao especialista quando a alteração vigorar.'], refs,
                    provisions=['NR20-AIII-2.1.1@2024', 'NR20-AIII-2.1.1@2025'], conditions=conds, as_of=iso, rule_id='NR20-R4-temporal')
            return Finding(aid, scenario, 'REVIEW', 'Candidato a avaliação de impacto',
                'O cenário contém os atributos ilustrativos descritos na alteração do item 2.1.1 do Anexo III; confirmar o contexto normativo integral antes de qualquer conclusão.',
                ['Classificação completa da instalação e demais condições do Anexo III.'],
                ['Comparar texto anterior e atual.', 'Submeter a avaliação ao especialista.', 'Registrar decisão, justificativa e evidência.'], refs,
                provisions=provs, conditions=conds, as_of=iso, rule_id='NR20-R5-candidato')
        return Finding(aid, scenario, 'NO_LINK', 'Condição demonstrativa não satisfeita',
            'O cadastro não corresponde às condições escolhidas para esta demonstração, sem concluir que nenhuma outra regra se aplica.',
            ['Outros regimes potencialmente relevantes.'], ['Documentar o motivo da triagem.'], refs,
            provisions=provs, conditions=conds, as_of=iso, rule_id='NR20-R6-condicao')
    if scenario == 'eir':
        refs = ['F43', 'F44']
        provs = ['ANM95-art21', 'ANM-EIR-PRORROG-2026']
        insp = facts.get('inspection_date')
        cond = [{'key': 'dam', 'label': 'Cadastrada como barragem', 'value': facts.get('dam'), 'status': 'MET' if facts.get('dam') is True else 'NOT_MET'},
                {'key': 'pnsb', 'label': 'Inserida na PNSB', 'value': facts.get('pnsb'), 'status': 'MISSING' if facts.get('pnsb') is None else 'MET' if facts.get('pnsb') else 'NOT_MET'},
                {'key': 'inspection_date', 'label': 'Data da inspeção regular do ciclo', 'value': insp, 'status': 'MISSING' if not insp else 'MET' if '2026-03-16' <= insp <= '2026-03-31' else 'NOT_MET'}]
        if facts.get('dam') is not True:
            return Finding(aid, scenario, 'OUT_OF_SCOPE', 'Não cadastrado como barragem',
                'O aviso trata do EIR de barragens de mineração; este ativo não é barragem no cadastro.',
                [], ['Não gerar tarefa.'], refs, provisions=[], conditions=cond, as_of=iso, rule_id='EIR-R0-escopo')
        if when < date(2026, 4, 16):
            return Finding(aid, scenario, 'MONITOR', 'Aviso ainda não publicado na data simulada',
                'Antes de 16/04/2026 vale o prazo regular do ciclo (15/04/2026 para inspeções de 16 a 31/03), conforme o art. 21 da Res. ANM 95/2022.',
                [], ['Manter a obrigação regular do ciclo.'], refs, legal_deadline='2026-04-15', provisions=['ANM95-art21'], conditions=cond, as_of=iso, rule_id='EIR-R1-antes')
        missing = [c['label'] for c in cond[1:] if c['status'] == 'MISSING']
        if missing:
            return Finding(aid, scenario, 'INSUFFICIENT', 'Perfil incompleto: não dá para saber se o aviso muda esta unidade',
                'O aviso só altera o prazo das inspeções realizadas de 16 a 31/03/2026. Sem a data da inspeção (ou o enquadramento), a LexIA não decide e sinaliza o campo pendente.',
                missing, ['Pedir à área interna somente os campos faltantes.', 'Não alterar a obrigação até completar o perfil.'], refs,
                provisions=provs, conditions=cond, as_of=iso, rule_id='EIR-R2-dados')
        if cond[1]['status'] == 'NOT_MET' or cond[2]['status'] == 'NOT_MET':
            return Finding(aid, scenario, 'NO_LINK', 'O aviso não altera o ciclo desta unidade',
                'A inspeção desta unidade está fora de 16–31/03/2026 (ou a estrutura não está na PNSB): segue a regra recorrente do art. 21, sem prazo excepcional.',
                [], ['Registrar o descarte justificado do aviso para esta unidade.'], refs, provisions=['ANM95-art21'], conditions=cond, as_of=iso, rule_id='EIR-R3-fora')
        if when <= date(2026, 4, 23):
            return Finding(aid, scenario, 'REVIEW', 'Atualizar prazo do EIR: 15/04 → 23/04/2026',
                'A publicação oficial de 16/04/2026 prorrogou, excepcionalmente, o prazo do EIR das inspeções de 16 a 31/03/2026. Esta unidade fez a inspeção nesse período. A data anterior (15/04) fica no histórico; a regra recorrente do art. 21 não muda.',
                ['Confirmação de quem envia o EIR (responsável técnico).'],
                ['Atualizar a obrigação do ciclo com o novo prazo, mantendo a data anterior no histórico.', 'Atribuir à geotecnia (sugestão; aprovação humana).', 'Anexar o protocolo do SIGBM como evidência.'],
                refs, legal_deadline='2026-04-23', provisions=provs, conditions=cond, as_of=iso, rule_id='EIR-R4-atualizar')
        return Finding(aid, scenario, 'REVIEW', 'Conferir o protocolo do EIR (prazo excepcional encerrado em 23/04/2026)',
            'O prazo excepcional terminou. A tarefa só deve ser marcada como concluída depois de conferir o protocolo de envio no SIGBM; sem protocolo, escalar para o responsável.',
            ['Protocolo de envio do EIR no SIGBM.'],
            ['Localizar e anexar o protocolo.', 'Se não houver protocolo, escalar ao responsável e registrar a pendência.'],
            refs, legal_deadline='2026-04-23', provisions=provs, conditions=cond, as_of=iso, rule_id='EIR-R5-evidencia')
    if scenario == 'anm':
        refs = ['F09', 'F10', 'F40']
        cond = [{'key': 'dam', 'label': 'Cadastrado como barragem', 'value': facts.get('dam'), 'status': 'MET' if facts.get('dam') is True else 'NOT_MET'}]
        if facts.get('dam') is True:
            active = [(d, pid, label) for d, pid, label in ANM_PHASES if d <= when]
            pending = [(d, pid, label) for d, pid, label in ANM_PHASES if d > when]
            if not active:
                return Finding(aid, scenario, 'FUTURE_REVIEW', 'Preparar análise de transição normativa',
                    'A Resolução ANM 220/2025, alterada pela ANM 245/2026, contém vigência escalonada: arts. 76–77 em 22/04/2027, regra geral em 02/08/2027 e §1º art. 7º em 26/12/2029. São fases futuras na data-base de novembro de 2026.',
                    ['Enquadramento legal da estrutura.', 'Classificação técnica e competência fiscalizatória.'],
                    ['Planejar revisão por dispositivo e fase.', 'Submeter eventual obrigação ao especialista responsável.'], refs,
                    provisions=[p for _, p, _ in ANM_PHASES], conditions=cond, as_of=iso, rule_id='ANM-R1-futuro')
            act = ', '.join(f"{label} ({d.strftime('%d/%m/%Y')})" for d, _, label in active)
            pend = ', '.join(f"{label} ({d.strftime('%d/%m/%Y')})" for d, _, label in pending) or 'nenhuma'
            return Finding(aid, scenario, 'REVIEW', 'Fases em vigor na data simulada',
                f'Na data simulada {when.strftime("%d/%m/%Y")}, segundo o escalonamento catalogado, estariam em vigor: {act}. Fases ainda futuras: {pend}. Simulação temporal sobre o texto catalogado; alterações posteriores a 05/11/2026 não são conhecidas.',
                ['Enquadramento legal da estrutura.', 'Classificação técnica e competência fiscalizatória.', 'Conferir se houve nova alteração normativa até a data simulada.'],
                ['Revisar somente os dispositivos em vigor na data.', 'Submeter eventual obrigação ao especialista responsável.'], refs,
                provisions=[p for _, p, _ in active], conditions=cond, as_of=iso, rule_id='ANM-R2-fase-ativa')
        return Finding(aid, scenario, 'OUT_OF_SCOPE', 'Não cadastrado como barragem',
            'O cenário não classifica este ativo como barragem; uma organização atuar em mineração não é prova de incidência.',
            ['Vínculo e enquadramento, se houver.'], ['Não gerar tarefa normativa automática.'], refs,
            provisions=[], conditions=cond, as_of=iso, rule_id='ANM-R3-escopo')
    if scenario == 'anp_cp21':
        refs = ['F04', 'F03']
        cond = [{'key': 'anp_regulated', 'label': 'Atividade cadastrada como regulada pela ANP', 'value': facts.get('anp_regulated'), 'status': 'MET' if facts.get('anp_regulated') is True else 'NOT_MET'}]
        if facts.get('anp_regulated') is True:
            closed = when > date(2027, 1, 5)
            return Finding(aid, scenario, 'MONITOR',
                'Consulta encerrada: aguardar ato final' if closed else 'Texto em consulta pública: monitorar',
                ('Na data simulada a consulta já terminou (05/01/2027), mas não há ato final na base; nenhuma obrigação pode ser derivada da minuta.' if closed else
                 'A Consulta Pública ANP 21/2026 está aberta de 07/10/2026 a 05/01/2027. Texto em consulta não cria obrigação vigente; o conteúdo da minuta não foi auditado.'),
                ['Conteúdo auditado da minuta.', 'Eventual ato final e sua vigência.'],
                ['Acompanhar a consulta e decidir internamente sobre contribuição.', 'Não criar tarefa de cumprimento a partir de minuta.'], refs,
                provisions=['ANP-CP21-2026'], conditions=cond, as_of=iso, rule_id='ANP-R1-consulta')
        return Finding(aid, scenario, 'OUT_OF_SCOPE', 'Atividade não cadastrada como regulada pela ANP',
            'O cadastro sintético não indica atividade regulada pela ANP; não inferir pelo nome ou setor da organização.',
            ['Vínculo regulatório, se houver.'], ['Não gerar tarefa normativa automática.'], refs,
            provisions=[], conditions=cond, as_of=iso, rule_id='ANP-R2-escopo')
    if scenario == 'ansn':
        refs = ['F18', 'F19', 'F20', 'F21']
        cond = [{'key': 'radiative', 'label': 'Instalação radiativa cadastrada', 'value': facts.get('radiative'), 'status': 'MET' if facts.get('radiative') is True else 'NOT_MET'},
                {'key': 'cites_cnen_designation', 'label': 'Documentos citam designação CNEN', 'value': facts.get('cites_cnen_designation'), 'status': 'MET' if facts.get('cites_cnen_designation') is True else ('MISSING' if facts.get('cites_cnen_designation') is None else 'NOT_MET')}]
        if facts.get('radiative') is True:
            if facts.get('cites_cnen_designation') is None:
                return Finding(aid, scenario, 'INSUFFICIENT', 'Não se sabe quais designações os documentos citam',
                    'A redesignação CNEN → ANSN afeta referências documentais; sem inventário de citações não é possível triar.',
                    ['Inventário de normas citadas nos procedimentos.'], ['Solicitar inventário documental.'], refs,
                    provisions=['ANSN-RES1-2025'], conditions=cond, as_of=iso, rule_id='ANSN-R1-dados')
            return Finding(aid, scenario, 'REVIEW', 'Atualizar referências documentais CNEN → ANSN',
                'O catálogo da ANSN registra redesignação pela Resolução ANSN 1/2025, preservando número e título. Procedimentos que citam a designação antiga devem ter edição e órgão conferidos.',
                ['Edição vigente de cada norma citada.', 'Atividade e instalação licenciada.'],
                ['Conferir catálogo oficial e edição antes de concluir.', 'Submeter alteração documental ao responsável técnico.'], refs,
                provisions=['ANSN-RES1-2025'], conditions=cond, as_of=iso, rule_id='ANSN-R2-alias')
        return Finding(aid, scenario, 'OUT_OF_SCOPE', 'Sem instalação radiativa cadastrada',
            'O cenário não registra instalação nuclear ou radiativa para este ativo.',
            ['Vínculo, se houver.'], ['Não gerar tarefa normativa automática.'], refs,
            provisions=[], conditions=cond, as_of=iso, rule_id='ANSN-R3-escopo')
    raise ValueError('Cenário desconhecido')


def answer(question: str, profile: str, sources: list[dict]) -> dict[str, Any]:
    """Respostas controladas verificáveis (modo sem LLM)."""
    import unicodedata
    q = ''.join(c for c in unicodedata.normalize('NFKD', question.lower().strip()) if not unicodedata.combining(c))
    profile = profile if profile in ('simples', 'tecnico') else 'simples'
    source_lookup = {s['id']: s for s in sources}

    def build(refs, simple, technical, missing, actions, disclaimer):
        return {'state': 'GROUNDED_DEMO', 'profile': profile, 'answer': simple if profile == 'simples' else technical,
                'answer_simple': simple, 'answer_technical': technical,
                'source_ids': refs, 'sources': [source_lookup[i] for i in refs if i in source_lookup],
                'missing': missing, 'actions': actions, 'disclaimer': disclaimer, 'mode': 'controlado'}

    if any(k in q for k in ('multa', 'sanção', 'sancao', 'penalidade', 'autuação', 'autuacao')):
        return _abstain(profile, 'A base não contém fonte curada que permita calcular multa, sanção ou penalidade. Não estimamos valores nem prevemos autuações.')
    if re.search(r'\beir\b|extrato de inspecao|95/2022', q):
        recurring = 'O empreendedor envia pelo SIGBM o Extrato de Inspeção Regular (EIR) de cada barragem, conforme o ciclo do art. 21 da Resolução ANM 95/2022. A base não contém prazo numérico geral validado para todos os ciclos.'
        exceptional = ' Para inspeções de 16 a 31/03/2026, o aviso ANM de 16/04/2026 prorrogou excepcionalmente o envio de 15/04/2026 para 23/04/2026. Esse prazo já terminou na data-base de novembro de 2026 e não altera os demais ciclos.'
        return build(['F43', 'F44'], recurring + exceptional, recurring + exceptional,
                     ['Data da inspeção, ciclo e protocolo de envio'], ['Conferir o ciclo e o protocolo com o responsável técnico.'],
                     'Resumo curado, sujeito a conferência da fonte original e revisão humana; não é parecer jurídico.')
    if any(k in q for k in ('psicossocia', 'saude mental', 'nr-1 ', 'nr-1?', 'pgr')):
        text = 'O resumo curado da NR-1 inclui fatores de risco psicossociais relacionados ao trabalho no PGR. Isso não permite concluir a situação de uma empresa nem substitui a avaliação do SESMT. Confira a versão e o dispositivo na fonte oficial.'
        return build(['F45'], text, text, ['Atividade, contexto e versão aplicável'], ['Solicitar revisão do SESMT.'], 'Síntese curada, não parecer jurídico.')
    if any(k in q for k in ('anm', 'barragem', '220/2025', '245/2026')):
        return build(['F09', 'F10', 'F40'],
            'A Resolução ANM 220/2025, alterada pela ANM 245/2026, começa em etapas: arts. 76 e 77 em 22/04/2027; regra geral em 02/08/2027; §1º do art. 7º em 26/12/2029. Não é correto tratar todos os dispositivos como exigíveis em novembro de 2026. Precisamos confirmar o tipo de estrutura e a versão da norma.',
            'Para a Resolução ANM 220/2025, com art. 87 modificado pela Resolução ANM 245/2026, a vigência é escalonada: arts. 76 e 77 (22/04/2027), demais artigos ressalvadas exceções (02/08/2027) e §1º do art. 7º (26/12/2029). Aplicabilidade depende de enquadramento técnico-jurídico.',
            ['Dados de enquadramento da estrutura e dispositivos pertinentes'], ['Agendar análise documental da transição; decisão humana obrigatória.'],
            'Síntese demonstrativa baseada no dossiê, não parecer jurídico nem consulta à norma em tempo real.')
    if any(k in q for k in ('nr-20', 'nr 20', 'nr20', 'tanque', 'gerador', '60/2025')):
        return build(['F02', 'F41', 'F42'],
            'A NR-20 teve uma mudança em janeiro de 2025 sobre uma exceção para certos tanques de consumo ligados a geradores a diesel ou biodiesel. É preciso confirmar características da instalação antes de dizer se a exceção vale.',
            'A Portaria MTE 60/2025 alterou o item 2.1.1 do Anexo III da NR-20. A alteração abrange as alíneas d e f do item 2.1 para tanques de consumo separados ou integrados à base do grupo gerador a diesel/biodiesel, sem dispensa geral. Conferir escopo 20.2 e condições do Anexo III.',
            ['Tipo de instalação, combustível, configuração do tanque, escopo'], ['Realizar triagem do ativo sintético e solicitar revisão.'],
            'Síntese demonstrativa baseada no dossiê, não parecer jurídico nem consulta à norma em tempo real.')
    if any(k in q for k in ('cnen', 'ansn', 'radioproteção', 'radioprotecao', 'nuclear')):
        return build(['F18', 'F19', 'F20', 'F21'],
            'Algumas normas antes identificadas como CNEN passaram a ser identificadas como ANSN. É importante conferir o número, a edição e o órgão responsável antes de usar o documento.',
            'O catálogo da ANSN registra redesignação pela Resolução ANSN 1/2025, preservando número e título; atos posteriores podem alterar edição e conteúdo. Recuperar aliases CNEN/ANSN e confirmar versão específica conforme a atividade.',
            ['Número e edição da norma procurada, atividade/instalação'], ['Conferir catálogo oficial e edição antes de concluir.'],
            'Síntese documental; não autoriza operação nem decisão de segurança.')
    if any(k in q for k in ('anp', 'consulta pública', 'consulta publica', '21/2026')):
        return build(['F04', 'F03'],
            'A ANP está com uma consulta pública aberta (nº 21/2026) até 05/01/2027. Texto em consulta ainda não é regra: dá para acompanhar e contribuir, mas não para cobrar cumprimento.',
            'Consulta e Audiência Públicas ANP nº 21/2026: período 07/10/2026–05/01/2027 (F04). O conteúdo da minuta não foi auditado no dossiê; nenhuma obrigação vigente pode ser derivada. Status do dispositivo: EM CONSULTA.',
            ['Conteúdo auditado da minuta', 'Ato final e vigência'], ['Monitorar; decidir sobre contribuição; não criar tarefa de cumprimento.'],
            'Síntese demonstrativa baseada no dossiê.')
    return _abstain(profile, 'A base demonstrativa não contém evidência suficiente para responder com segurança a essa pergunta. Informe o dispositivo, órgão, atividade e contexto, ou encaminhe ao profissional competente.')


def _abstain(profile: str, text: str) -> dict[str, Any]:
    return {'state': 'ABSTAIN', 'profile': profile, 'answer': text, 'answer_simple': text, 'answer_technical': text,
            'source_ids': [], 'sources': [],
            'missing': ['Fonte oficial curada diretamente relacionada à pergunta', 'Contexto mínimo de aplicabilidade'],
            'actions': ['Não inventar obrigação, sanção, prazo ou canal.', 'Encaminhar ao profissional competente.'],
            'disclaimer': 'Abstenção: sem base curada suficiente.', 'mode': 'controlado'}
