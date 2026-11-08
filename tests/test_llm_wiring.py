"""Ligação com a Claude API verificada SEM rede: um servidor local imita /v1/messages e o SDK oficial (anthropic 2.x)
fala com ele via ANTHROPIC_BASE_URL. Garante que os três usos generativos montam requisições aceitas e tratam a resposta:
1) resposta com citação verificada (ai.call_llm), 2) português → filtros (ai_tools.parse_llm), 3) agente com tool use."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import anthropic  # noqa: F401
    HAVE_SDK = True
except ImportError:
    HAVE_SDK = False

REQUESTS = []


def message(content, stop='end_turn'):
    return {'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'claude-opus-5-5', 'content': content,
            'stop_reason': stop, 'stop_sequence': None, 'usage': {'input_tokens': 10, 'output_tokens': 10}}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        REQUESTS.append({'path': self.path, 'body': body, 'beta': self.headers.get('anthropic-beta')})
        fmt = (body.get('output_config') or {}).get('format')
        if fmt and 'simple' in fmt['schema']['properties']:
            out = message([{'type': 'text', 'text': json.dumps({'simple': 'Resumo simples.', 'technical': 'Resumo técnico: confirmar com o fiscalizador.'})}])
        elif fmt and 'dataset' in fmt['schema']['properties']:
            out = message([{'type': 'text', 'text': json.dumps({'dataset': 'orfas', 'uf': ['RN', 'ZZ'], 'attention': ['Crítica'], 'owner_kind': [],
                                                                'operational_status': [], 'signals': [], 'text': ''})}])
        elif fmt:
            ctx = body['messages'][0]['content']
            chunk = ctx.split('chunk_id="')[1].split('"')[0]
            quote = ctx.split('>', 1)[1].split('</trecho>')[0][:40]
            out = message([{'type': 'text', 'text': json.dumps({'status': 'ANSWER', 'answer_simple': 'Resposta simples.', 'answer_technical': 'Resposta técnica.',
                                                                'citations': [{'chunk_id': chunk, 'quote': quote}], 'missing': [], 'caveats': []})}])
        elif body.get('tools'):
            used = [b for m in body['messages'] if m['role'] == 'user' and isinstance(m['content'], list) for b in m['content'] if b.get('type') == 'tool_result']
            seq = ['verificar_fontes', 'monitorar_modelos', 'priorizar', 'propor_acoes']
            if len(used) < len(seq):
                out = message([{'type': 'tool_use', 'id': f'tu_{len(used)}', 'name': seq[len(used)], 'input': {}}], 'tool_use')
            else:
                out = message([{'type': 'text', 'text': 'Ciclo concluído.'}])
        else:
            out = message([{'type': 'text', 'text': 'ok'}])
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@unittest.skipUnless(HAVE_SDK, 'pacote anthropic não instalado')
class LlmWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Fake)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.env = {k: os.environ.get(k) for k in ('ANTHROPIC_BASE_URL', 'ANTHROPIC_API_KEY')}
        os.environ['ANTHROPIC_BASE_URL'] = f'http://127.0.0.1:{cls.httpd.server_address[1]}'
        os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-teste-local'

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()
        for k, v in cls.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_rag_answer_with_verified_citation(self):
        from app import ai
        passages = [{'chunk_id': 'P1', 'title': 'Res. ANM', 'version': 'v1', 'text': 'O empreendedor deve enviar a declaração de estabilidade em março e setembro.',
                     'source_ids': ['F09'], 'provision_id': 'P1'}]
        prop = ai.call_llm('Quando enviar a DCE?', passages)
        ver = ai.verify(prop, passages)
        self.assertEqual(ver['verdict'], 'VERIFIED')
        req = REQUESTS[-1]
        self.assertEqual(req['body']['model'], ai.MODEL)
        self.assertEqual(req['body']['fallbacks'], 'default')
        self.assertIn('server-side-fallback-2026-07-01', req['beta'] or '')
        self.assertNotIn('temperature', req['body'])

    def test_portuguese_to_filters_is_verified(self):
        from app import ai_tools
        it = ai_tools.interpret('órfãs críticas no RN', use_llm=True)
        self.assertEqual(it['engine'], 'ia')
        self.assertEqual(it['filters']['uf'], ['RN'])          # 'ZZ' inventado foi descartado
        self.assertIn('uf=ZZ', it['dropped'])

    def test_dam_brief_via_sdk(self):
        from app import ai_tools, abandono
        from datetime import date
        x = abandono.assess_mining([{'id': 'SIGBM-1', 'name': 'Teste', 'uf': 'MG', 'municipio': 'X', 'owner_cnpj': '1', 'operational_status': 'Inativa', 'pnsb': 'Sim'}], {}, date(2026, 11, 6))[0]
        b = ai_tools.dam_brief(x, use_llm=True)
        self.assertEqual(b['engine'], 'ia')

    def test_agent_planner_tool_use_loop(self):
        from app.agent import claude_planner_factory
        calls = []
        planner = claude_planner_factory()
        planner({'verificar_fontes': 'a', 'monitorar_modelos': 'b', 'priorizar': 'c', 'propor_acoes': 'd'},
                lambda name: calls.append(name) or {'ok': name}, [])
        self.assertEqual(calls, ['verificar_fontes', 'monitorar_modelos', 'priorizar', 'propor_acoes'])
        last = REQUESTS[-1]['body']
        self.assertTrue(any(b.get('type') == 'tool_result' for m in last['messages'] if m['role'] == 'user' and isinstance(m['content'], list) for b in m['content']))


if __name__ == '__main__':
    unittest.main()
