"""A IA fala de acordo com a conta (regra perspectiva-v1).

AGENTS.md: perfis de linguagem alteram TEXTO, nunca fontes, condições, vigência ou certeza. Por isso a perspectiva só ACRESCENTA
um bloco “para você” (foco da função + próximo passo + o que falta), montado a partir dos campos que a resposta já tem
(fontes, dados faltantes, ações). A resposta, as fontes e o estado (vigente, abstenção…) ficam exatamente iguais para todos.
Cidadão recebe a versão em linguagem simples por padrão; empresa recebe a técnica (a pessoa pode trocar).
"""
from __future__ import annotations

RULE_VERSION = 'perspectiva-v1'
FOCO = {
    'juridico': ('Jurídico', 'Base legal, vigência do dispositivo, prazo legal e consequência', 'Confirmar a vigência do dispositivo citado e registrar a decisão com a fundamentação.'),
    'compliance': ('Compliance', 'Obrigação, dono, prazo e evidência', 'Atribuir a obrigação a um responsável com prazo e definir a evidência que comprova o cumprimento.'),
    'engenharia': ('Engenharia', 'Condição técnica do ativo e dados que faltam para enquadrar', 'Conferir os atributos técnicos do ativo listados como faltantes antes da decisão.'),
    'operacao': ('Operação', 'O que fazer no campo e o que registrar', 'Executar a ação atribuída e anexar foto ou registro como evidência.'),
    'financas': ('Gestão', 'Prioridade, exposição e quem decide', 'Priorizar os itens críticos e garantir dono e recurso para cada um.'),
    'auditoria': ('Auditoria', 'Trilha: fonte, versão usada, decisão e prova', 'Verificar se a decisão citou a versão vigente e se há evidência com hash.'),
    'regulatorio': ('Curadoria regulatória', 'Fonte oficial, versão e cobertura do catálogo', 'Conferir a fonte oficial e a versão vigente; registrar lacuna se faltar norma.'),
    'curadoria': ('Curadoria regulatória', 'Fonte oficial, versão e cobertura do catálogo', 'Conferir a fonte oficial e a versão vigente; registrar lacuna se faltar norma.'),
    'meio_ambiente': ('Meio ambiente', 'Licença, condicionantes e monitoramento ambiental', 'Conferir as condicionantes da licença ligadas ao tema e o prazo de cada uma.'),
    'radioprotecao': ('Proteção radiológica', 'Dose, autorização da autoridade nuclear e plano de radioproteção', 'Conferir a autorização ANSN/CNEN vigente e as leituras de dose do ativo.'),
    'seguranca_trabalho': ('Segurança do trabalho (SESMT)', 'PGR, riscos (inclusive psicossociais), treinamentos e saúde ocupacional', 'Conferir se o PGR e os treinamentos cobrem o risco citado e registrar a evidência.'),
    'cidadao': ('Cidadão', 'O que isso significa para você, em linguagem simples', 'Se houver risco imediato à vida, ligue 199 (Defesa Civil). Para registrar algo, use “Fazer denúncia”.'),
}
ROLE_TO_FUNC = {'especialista': 'engenharia', 'gestor': 'financas', 'auditor': 'auditoria', 'curador': 'curadoria'}


def funcao(user: dict | None) -> str | None:
    if not user:
        return None
    if user.get('kind') == 'cidadao':
        return 'cidadao'
    f = user.get('function') or ROLE_TO_FUNC.get(user.get('role') or '', user.get('role'))
    return f if f in FOCO else ('compliance' if user.get('kind') == 'empresa' else None)


def perfil_padrao(user: dict | None, pedido: str | None) -> str:
    if not user or user.get('kind') == 'cidadao':
        return 'simples'   # cidadão (e visitante) sempre recebe a versão em linguagem simples
    if pedido in ('simples', 'tecnico'):
        return pedido
    return 'simples' if (not user or user.get('kind') == 'cidadao') else 'tecnico'


LEI_SIMPLES = ('Quem cuida da segurança da barragem é a empresa que a explora — mesmo que não tenha culpa — até a barragem ser desativada de vez. '
               'Se não houver empresa, responde o dono do terreno. Qualquer pessoa pode avisar as autoridades: Fala.BR (gov.br), ANM ou, em risco imediato, a Defesa Civil pelo 199. '
               'Na LexIA, use “Fazer denúncia”: ela organiza o relato e as normas para você.')


def simplificar_lei(out: dict, user: dict | None) -> dict:
    """Resposta sobre lei para o cidadão: mesmo conteúdo, em linguagem simples; os artigos ficam na linha de fonte."""
    if out.get('kind') == 'law' and (not user or user.get('kind') == 'cidadao'):
        return {**out, 'answer': LEI_SIMPLES, 'sources': (out.get('sources') or []) + ['Lei 12.334/2010, arts. 2º IV, 4º III, 17 I e 17-A §2º']}
    return out


def aplicar(res: dict, user: dict | None) -> dict:
    f = funcao(user)
    if not f or res.get('state') == 'ABSTAIN':
        return res
    rot, foco, passo = FOCO[f]
    falta = list(res.get('missing') or [])
    pontos = []
    if f in ('juridico', 'auditoria', 'regulatorio', 'curadoria') and res.get('source_ids'):
        pontos.append('Fontes citadas: ' + ', '.join(res['source_ids'][:4]))
    if f in ('engenharia', 'compliance', 'operacao', 'meio_ambiente', 'radioprotecao', 'seguranca_trabalho') and falta:
        pontos.append('Dados que faltam: ' + '; '.join(falta[:3]))
    if f in ('compliance', 'operacao', 'financas') and res.get('actions'):
        pontos.append('Ação sugerida: ' + res['actions'][0])
    return {**res, 'perspectiva': {'funcao': f, 'rotulo': rot, 'foco': foco, 'pontos': pontos, 'proximo_passo': passo, 'rule_version': RULE_VERSION,
                                   'nota': 'Muda só a ênfase para a sua função; fontes, condições e certeza são as mesmas para todos.'}}
