"""Triagem conservadora compartilhada pelos dois canais do assistente (v1)."""
import re
from .ai import norm


def guard(question):
    t = norm(question)
    # Sinais de ocorrência atual têm prioridade sobre busca normativa e filtros.
    if not re.search(r'\b(nao|nunca)\b.{0,18}(rompeu|tocando|vazando)', t) and re.search(
        r'lama.{0,12}descendo|barragem.{0,15}rompeu|sirene.{0,30}tocando|'
        r'fios?.{0,40}(caido|faisca)|vazando.{0,40}(agora|socorro)|'
        r'cheiro.{0,15}gas|objeto.{0,35}(radiacao|radioativ)|rachadura.{0,70}agua barrenta', t):
        return ('EMERGENCY', 'Ligue 199 (Defesa Civil) ou 193 (Bombeiros) se estiver no Brasil. '
                'Afaste-se do perigo sem se aproximar para investigar e siga as orientações das autoridades. '
                'Não toque em fios, objetos suspeitos ou materiais desconhecidos. A LexIA não monitora nem confirma emergências.')
    if re.search(r'ignore.{0,30}instru|esquec.{0,25}regras|invente|declare que|culpad|'
                 r'vai romper|mais perigosa|em conformidade|cumpre todas|esta regular', t):
        return ('ABSTAIN', 'Não afirmo conformidade, culpa, regularidade ou previsão de rompimento de uma empresa ou estrutura. '
                'Não invento normas. É necessária evidência específica, atualizada e revisão por profissional competente.')
    if re.search(r'\b(what|which|where|is the|can you|quels|que cambio|hay represas)\b', t):
        return ('ABSTAIN', 'Atendo em português do Brasil. Reformule sua pergunta em português, indicando o tema e o contexto. '
                'Não tenho dados para afirmar se uma barragem próxima é segura.')
    platform = [
        (r'anonim|dados.{0,30}(aparecem|empresa)|denunci', 'Use “Denúncia anônima” para registrar sem conta, revise o relato antes de enviar e guarde o protocolo para acompanhar. Não inclua dados pessoais no texto se quiser preservar sua identidade. Este chat não envia denúncias.'),
        (r'voces sao do governo', 'A LexIA é uma plataforma demonstrativa de inteligência regulatória; não é órgão do governo nem canal oficial de emergência.'),
        (r'de onde.{0,15}dados|origem dos dados', 'Os radares usam snapshots de cadastros públicos, como SIGBM/ANM e SNISB/ANA. Consulte a fonte e a data de coleta em cada registro; cadastro público não é diagnóstico atual de segurança.'),
        (r'parecer juridico', 'As respostas da LexIA são apoio preliminar à revisão humana e não constituem parecer jurídico nem certificação de conformidade.'),
    ]
    for pattern, answer in platform:
        if re.search(pattern, t):
            return ('PLATFORM', answer)
    if re.search(r'\b(multa|sancao|penalidade|aliquota|icms|dose|nr[ -]?35|nr[ -]?12)\b|1000/2021|1\.064|999/2030|universalizacao', t):
        return ('ABSTAIN', 'Não há base curada suficiente para responder ao dispositivo ou valor solicitado. '
                'Informe a fonte oficial, versão, jurisdição e contexto; não vou substituir sua pergunta por outro assunto.')
    # Uma norma desconhecida não pode cair na resposta genérica do mesmo órgão.
    for number in re.findall(r'\b\d{1,4}/20\d{2}\b', t):
        if number not in {'220/2025', '245/2026', '95/2022', '60/2025', '21/2026', '1/2025'}:
            return ('ABSTAIN', 'Não tenho o dispositivo solicitado validado na base curada. Envie a fonte oficial e a versão para revisão.')
    if 'nova lei' in t and not re.search(r'\d|\banm\b', t):
        return ('ABSTAIN', 'Qual lei e dispositivo você quer consultar? Informe o número ou a fonte oficial; não posso assumir que se trata de uma resolução da ANM.')
    return None


def normative(question):
    t = norm(question)
    return bool(re.search(r'\bnr[ -]?\d|\bnorma|resolu|portaria|\blei\b|artigo|\bart[. ]|vigen|mudou|obrigac|\bprazo|\beir\b|extrato de inspecao|\bcnen\b|\bansn\b|\baneel\b|\banp\b|regra|saude mental|psicossocia', t))


def curated_fallback_allowed(question):
    """Só perguntas de síntese já cobertas podem usar resposta controlada após recusa."""
    t = norm(question)
    return bool(
        (re.search(r'\banm\b|220/2025|245/2026', t) and re.search(r'vigen|quando|mudou|regra|exigive', t)) or
        (re.search(r'\bcnen\b|\bansn\b', t) and re.search(r'mud|nome|redesign|citar|designa|fez', t)) or
        (re.search(r'\beir\b', t) and re.search(r'prazo|prorrog|quem|o que e', t)) or
        (re.search(r'\bnr[ -]?20\b', t) and re.search(r'mudou|dispens|excec', t)) or
        re.search(r'psicossocia|saude mental', t))


def quick(question, items):
    """Retorna resposta direta ou None para encaminhar a pergunta normativa."""
    from . import ai_tools
    g = guard(question)
    if g:
        state, answer = g
        return dict(kind='help', state=state, answer=answer, sources=[], chips=[], results=[], engine='regras')
    if normative(question):
        return None
    t = norm(question)
    if re.search(r'barrage|orfas|pessoa fisica|cooperativa', t):
        municipalities = sorted({x.get('municipio') for x in items if x.get('municipio')}, key=len, reverse=True)
        city = next((m for m in municipalities if re.search(r'(?<!\w)' + re.escape(norm(m)) + r'(?!\w)', t)), None)
        if city:
            subset = [x for x in items if norm(x.get('municipio', '')) == norm(city)]
            out = ai_tools.quick(question, subset, use_llm=False)
            if out['kind'] != 'filter':
                out = ai_tools.quick('mostre barragens', subset, use_llm=False)
                out['results'] = [dict(id=x['id'], name=x.get('name'), municipio=x.get('municipio'), uf=x.get('uf'), attention=x['attention'], kind=x['kind']) for x in subset[:6]]
                out['total'] = len(subset)
            out['kind'] = 'filter'
            out['answer'] = f"Em {city}: {out.get('total', 0)} barragem(ns) atendem ao pedido no cadastro consultado. Isso não prevê rompimento nem confirma segurança; confira fonte e data dos registros."
            return out
        return ai_tools.quick(question, items, use_llm=False)
    return dict(kind='help', state='ABSTAIN', answer='Não há contexto suficiente para responder com segurança. Posso ajudar com normas catalogadas, dados de barragens ou uso da LexIA. Especifique o assunto e o local quando necessário.', sources=[], chips=[], results=[], engine='regras')
