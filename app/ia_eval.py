"""Avaliação contínua da IA da LexIA (eval-v1) — custo zero: mede regras, verificadores e isolamento, sem chamar IA paga.

Categorias (data/eval/ia_eval.json, gabarito anotado pela equipe — ver campo "aviso"):
- relevancia_filtros: a pergunta vira os filtros certos; pergunta fora do tema não vira filtro.
- normas_denuncia: normas esperadas presentes (recall), normas proibidas ausentes (precisão), gravidade correta.
- versao_vigente: estado por dispositivo na data e resolução para a versão vigente (segue superseded_by).
- roteamento: alerta vai para os papéis certos e não vai para quem não precisa.
- perguntas: responde com fonte esperada ou se abstém fora da base.
- alucinacao: verificador reprova frases proibidas e números que não estão nos fatos; norma inventada pela IA é descartada.
- isolamento: documento, caixa de denúncias, e-mails e notificações de uma empresa não aparecem para outra.
- setor_normas: a mesma denúncia cita normas do setor certo (usina → ANEEL, mineração → ANM, saneamento → ANA/Portaria 888) e recusa as de outro setor; lacuna vai para a curadoria.
- extracao: texto normativo → obrigação com prazo, papel e condição presos a trecho literal; trecho inventado pela IA é recusado.
- donos: nenhum alerta fica sem dono (papel sem pessoa escala para compliance, gestão ou curadoria).
"""
from __future__ import annotations

import base64
import json
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_FILE = ROOT / 'data' / 'eval' / 'ia_eval.json'


def _case(cat, name, ok, detail=''):
    return {'categoria': cat, 'caso': name, 'ok': bool(ok), 'detalhe': detail}


def current_version(provisions: list[dict], pid: str, when: date) -> str:
    from .temporal import status_at
    by = {p['id']: p for p in provisions}
    cur, seen = pid, set()
    while cur in by and cur not in seen and status_at(by[cur], when) == 'HISTORICA' and by[cur].get('superseded_by'):
        seen.add(cur)
        cur = by[cur]['superseded_by']
    return cur


def run(eval_file: Path = EVAL_FILE) -> dict:
    from . import ai, ai_tools, ativos, denuncia
    from .accounts import Accounts
    from .cloud_aws import EvidenceVault
    from .compliance import CATALOG
    from .mailer import Mailer
    from .store import Store, WorkflowError
    from .temporal import status_at
    from .tenant import TenantDocs

    E = json.loads(eval_file.read_text(encoding='utf8'))
    out, tp, fp, fn = [], 0, 0, 0

    for c in E['relevancia_filtros']:
        r = ai_tools.interpret(c['q'], use_llm=False)
        if c.get('espera_sem_filtro'):
            out.append(_case('relevancia_filtros', c['q'], not r['chips'], 'sem filtro (abstenção)' if not r['chips'] else f"filtrou {r['chips']}"))
        else:
            bad = {k: r['filters'].get(k) for k, v in c['espera'].items() if r['filters'].get(k) != v}
            out.append(_case('relevancia_filtros', c['q'], not bad, f'divergências: {bad}' if bad else 'filtros corretos'))

    for c in E['normas_denuncia']:
        a = denuncia.analyze(c['relato'], c.get('alvo'))
        got = set(a['normas']) - set(denuncia.ALWAYS)
        exp, forb = set(c['espera']), set(c['proibidas'])
        tp += len(got & exp); fn += len(exp - got); fp += len(got & forb)
        ok = exp <= got and not (got & forb) and a['gravidade'] == c['gravidade']
        out.append(_case('normas_denuncia', c['relato'][:60], ok,
                         f"faltou {sorted(exp - got)}; indevidas {sorted(got & forb)}; gravidade {a['gravidade']} (esperada {c['gravidade']})" if not ok else 'normas e gravidade corretas'))

    for c in E.get('setor_normas', []):
        a = denuncia.analyze(c['relato'], c['alvo'])
        got = set(a['normas'])
        exp, forb = set(c['espera']), set(c['proibidas'])
        tp += len(got & exp); fn += len(exp - got); fp += len(got & forb)
        ok = exp <= got and not (got & forb) and (not c.get('lacuna') or a['lacuna'])
        out.append(_case('setor_normas', c['caso'], ok, f"setor {a['setor']}; normas {sorted(got - set(denuncia.ALWAYS))}; recusadas {[r['norma'] for r in a['recusadas']]}" + ('; lacuna → curadoria' if a['lacuna'] else '')))

    provs = json.loads((ROOT / 'data' / 'provisions.json').read_text(encoding='utf8'))
    by = {p['id']: p for p in provs}
    for c in E['versao_vigente']:
        when = date.fromisoformat(c['data'])
        st, cur = status_at(by[c['pid']], when), current_version(provs, c['pid'], when)
        ok = st == c['status'] and cur == c['vigente_esperada']
        out.append(_case('versao_vigente', f"{c['pid']} em {c['data']}", ok, f'estado {st}; versão usada {cur}'))

    cfg, emp = ativos.load()
    comp = {x['id']: x for x in emp['empresas']}
    for c in E['roteamento']:
        roles = [r['papel'] for r in ativos.recipients(comp[c['empresa']], cfg, c['ocorrencia'])]
        ok = set(c['papeis']) == set(roles) and not (set(c['nao_recebe']) & set(roles))
        out.append(_case('roteamento', f"{c['empresa']} · {c['ocorrencia']}", ok, f'destinatários {roles}'))

    for c in E.get('donos', []):
        rs = ativos.recipients(comp[c['empresa']], cfg, c['ocorrencia'], set(c['pessoas']))
        esc = [r for r in rs if r.get('escalado')]
        dono = any(not r['sem_pessoa'] for r in rs)
        ok = dono and bool(esc) == c['escalado'] and (not c.get('para') or (esc and esc[0]['papel'] == c['para'])) and (not c.get('sem_pessoa') or any(r['sem_pessoa'] for r in rs))
        out.append(_case('donos', c['caso'], ok, 'destinatários ' + ', '.join(r['rotulo'] + (' [sem pessoa]' if r['sem_pessoa'] else '') for r in rs)))

    from . import extrator as _ex
    for c in E.get('extracao', []):
        if c.get('ia_falsa'):
            fake = (lambda o: (lambda *a: json.dumps({'obrigacoes': [o]})))(c['ia_falsa'])
            r = _ex.extrair(c['texto'], llm=fake, forcar_ia=True)
            ok = any(x.get('origem') == 'ia' for x in r['recusadas']) and not any(x.get('origem') == 'ia' for x in r['obrigacoes'])
            out.append(_case('extracao', c['caso'], ok, f"recusadas: {[x['motivo'] for x in r['recusadas']]}"))
            continue
        r = _ex.extrair(c['texto'])
        obs = r['obrigacoes']
        ok = len(obs) == c['espera_n']
        if ok and obs:
            o = obs[0]
            ok = (not c.get('prazo_contem') or c['prazo_contem'] in (o.get('prazo') or '')) and (not c.get('papel') or o['papel'] == c['papel']) and (not c.get('condicao') or bool(o.get('condicao')))
        out.append(_case('extracao', c['caso'], ok, '; '.join(f"{o['papel']} · prazo {o.get('prazo') or '—'} · condição {o.get('condicao') or '—'}" for o in obs) or 'nenhuma obrigação (correto se esperado)'))

    sources = json.loads((ROOT / 'data' / 'sources.json').read_text(encoding='utf8'))
    for c in E['perguntas']:
        r = ai.ask(c['q'], 'simples', provs, sources, llm=None) if not ai.llm_status()['enabled'] else ai.ask(c['q'], 'simples', provs, sources, llm=lambda *a: (_ for _ in ()).throw(RuntimeError('eval sem IA paga')))
        ok = r['state'] == c['estado'] and (not c.get('fonte_esperada') or c['fonte_esperada'] in r.get('source_ids', []))
        out.append(_case('perguntas', c['q'], ok, f"estado {r['state']}; fontes {r.get('source_ids', [])}"))

    facts = {'nome': 'Barragem Exemplo', 'altura_m': '15', 'local': 'Município/UF'}
    for c in E['alucinacao']:
        if c['tipo'] == 'resumo':
            probs = ai_tools.verify_brief(c['texto'], facts)
            out.append(_case('alucinacao', c['texto'][:60], bool(probs) == c['deve_reprovar'], '; '.join(probs) or 'aprovado'))
        else:
            fake = lambda *a: json.dumps({'fatos': ['fato'], 'normas': c['normas_propostas'], 'pedidos': []})
            d = denuncia.build('texto que as regras não reconhecem', None, [], date.today(), llm=fake)
            kept = [n['key'] for n in d['normas'] if n['key'] not in denuncia.ALWAYS]
            ok = set(kept) == set(c['aceitas_esperadas']) and all(k in CATALOG for k in kept)
            out.append(_case('alucinacao', 'IA propõe normas inexistentes', ok, f'mantidas {kept}'))

    # isolamento entre empresas (cenário sintético, em memória)
    s = Store(':memory:')
    with tempfile.TemporaryDirectory() as tmp:
        t = TenantDocs(s, EvidenceVault(bucket='', local_root=Path(tmp)), var_dir=Path(tmp))
        A = {'id': 1, 'kind': 'empresa', 'cnpj': '11222333000181'}
        B = {'id': 2, 'kind': 'empresa', 'cnpj': '99888777000100'}
        up = t.upload(A, 'laudo.pdf', 'application/pdf', base64.b64encode(b'%PDF eval').decode())
        try:
            t.read(B, up['id']); leak = True
        except WorkflowError:
            leak = False
        out.append(_case('isolamento', 'documento da empresa A lido pela empresa B', not leak and not t.list(B)['docs'], 'bloqueado' if not leak else 'VAZOU'))
    dd = denuncia.DenunciaDesk(s)
    x = dd.save('usuario:9', 'ATIVO:demo-mineracao:B-01', denuncia.build('trinca no talude', None, [], date.today()), [])
    dd.confirm(x['id'], 'usuario:9')
    denuncia.route_to_company(s, x['id'], '11222333', 'Empresa fictícia', 'B-01', False)
    out.append(_case('isolamento', 'denúncia destinada à empresa A aparece para B', not denuncia.inbox(s, '99888777') and len(denuncia.inbox(s, '11222333')) == 1, 'só a empresa destino vê'))
    m = Mailer(s)
    m.queue('compliance@exemplo.invalid', '11222333', 'x', 'y', 'eval')
    out.append(_case('isolamento', 'e-mails da empresa A listados para B', not m.list('99888777'), 'fila separada por organização'))
    acc = Accounts(s)
    acc.notify('org:11222333', 'eval', 'Notificação A', 'x')
    seen_b = [n for n in acc.notifications({'id': 2, 'kind': 'empresa', 'cnpj': '99888777000100', 'function': 'compliance', 'role': 'gestor'})['items'] if n['title'] == 'Notificação A']
    out.append(_case('isolamento', 'notificação da empresa A chega para B', not seen_b, 'não chegou' if not seen_b else 'VAZOU'))

    cats = {}
    for c in out:
        k = cats.setdefault(c['categoria'], {'total': 0, 'ok': 0})
        k['total'] += 1; k['ok'] += c['ok']
    for k in cats.values():
        k['taxa'] = round(k['ok'] / k['total'], 3)
    prec = round(tp / (tp + fp), 3) if tp + fp else None
    rec = round(tp / (tp + fn), 3) if tp + fn else None
    return {'versao': E['versao'], 'aviso': E['aviso'], 'executado_em': date.today().isoformat(), 'custo_ia': 'zero (nenhuma chamada paga)',
            'total': len(out), 'aprovados': sum(c['ok'] for c in out), 'por_categoria': cats,
            'normas': {'precisao': prec, 'recall': rec, 'verdadeiros': tp, 'indevidas': fp, 'faltantes': fn},
            'casos': out}


if __name__ == '__main__':
    import sys
    r = run()
    for c in r['casos']:
        print(('OK  ' if c['ok'] else 'FALHA ') + f"[{c['categoria']}] {c['caso']} — {c['detalhe']}")
    print(json.dumps({k: r[k] for k in ('total', 'aprovados', 'por_categoria', 'normas')}, ensure_ascii=False, indent=1))
    sys.exit(0 if r['aprovados'] == r['total'] else 1)
