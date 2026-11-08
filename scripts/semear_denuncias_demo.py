"""Cria denúncias de DEMONSTRAÇÃO pelo fluxo real da API (cidadã demo → empresas fictícias), e a empresa fictícia responde algumas.

Só ativos de empresas FICTÍCIAS (ATIVO:demo-*). Nenhuma denúncia é criada contra empresa real.
Uso (servidor rodando): python scripts/semear_denuncias_demo.py [http://localhost:8765]
"""
import http.cookiejar
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8765'
SENHA = 'LexIA2026demo'
CASOS = [
    ('ATIVO:demo-mineracao:B-01', 'Desde a última chuva apareceu uma trinca no talude da barragem e há água saindo na base, perto da estrada.', 'RESPONDIDA',
     'Vistoria feita em 48 h pela engenharia; trinca superficial tratada e piezômetros conferidos. Relatório anexado ao processo.'),
    ('ATIVO:demo-mineracao:R-01', 'O galpão de concentrado de monazita fica com o portão aberto e não tem placa de radiação nem controle de acesso.', 'EM_APURACAO', ''),
    ('ATIVO:demo-mineracao:B-02', 'A sirene da comunidade nunca foi testada e ninguém conhece a rota de fuga da barragem.', 'RESPONDIDA',
     'Teste de sirene agendado e simulado com a Defesa Civil; rotas de fuga sinalizadas e divulgadas na comunidade.'),
    ('ATIVO:demo-energia:UB-01', 'O vertedouro da usina está transbordando com a chuva forte e a água chegou na estrada de acesso.', 'RECEBIDA', ''),
    ('ATIVO:demo-saneamento:RS-01', 'O reservatório está com vazamento na base há semanas e a água está saindo para a rua.', 'RESPONDIDA',
     'Equipe de manutenção corrigiu a junta da base; inspeção registrada.'),
]


def session(email):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(path, body=None):
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json', 'Origin': BASE})
        return json.loads(op.open(req, timeout=60).read())
    call('/api/auth/login', {'email': email, 'password': SENHA, 'kind': 'cidadao' if email.startswith('joana') else 'empresa'})
    return call


cid = session('joana@demo.lexia.app')
empresa = session('bruno@demo.lexia.app')  # compliance da organização demo (raiz 11222333)
feitas = []
for alvo, relato, estado, resposta in CASOS:
    d = cid('/api/denuncia', {'dam_id': alvo, 'relato': relato, 'evidence_ids': []})
    r = cid('/api/denuncia', {'action': 'confirm', 'id': d['id'], 'identificar': False})
    feitas.append((d['id'], alvo, estado, resposta, r.get('empresa_destino')))
    print('denúncia', d['id'], alvo, '→', (r.get('empresa_destino') or {}).get('empresa'))
# respostas: só a organização demo de mineração tem contas de empresa; as demais ficam como recebidas
for did, alvo, estado, resposta, _ in feitas:
    if alvo.startswith('ATIVO:demo-mineracao') and estado != 'RECEBIDA':
        print(empresa('/api/denuncias/responder', {'id': did, 'state': estado, 'resposta': resposta}))
