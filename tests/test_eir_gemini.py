"""Caso EIR (aviso ANM de 16/04/2026) e provedor Gemini (sem rede: servidor local imita a API)."""
import os
os.environ['TORRE_LLM'] = '0'
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from app import cloud_aws
from app.engine import analyze

ASSETS = {a['id']: a for a in json.load(open('data/assets.json', encoding='utf8'))}


class EirScenario(unittest.TestCase):
    def test_same_publication_different_decisions_per_unit(self):
        a, b = analyze(ASSETS['B-01'], 'eir', '2026-04-17'), analyze(ASSETS['B-02'], 'eir', '2026-04-17')
        self.assertEqual(a.state, 'REVIEW')
        self.assertIn('15/04 → 23/04', a.headline)
        self.assertEqual(a.legal_deadline, '2026-04-23')
        self.assertEqual(b.state, 'INSUFFICIENT')
        self.assertIn('Data da inspeção regular do ciclo', b.missing)

    def test_before_publication_regular_rule(self):
        f = analyze(ASSETS['B-01'], 'eir', '2026-04-10')
        self.assertEqual(f.state, 'MONITOR')
        self.assertEqual(f.legal_deadline, '2026-04-15')
        self.assertEqual(f.provisions, ['ANM95-art21'])

    def test_after_deadline_requires_evidence(self):
        f = analyze(ASSETS['B-01'], 'eir', '2026-11-06')
        self.assertIn('protocolo', f.headline.lower())
        self.assertIn('Protocolo de envio do EIR no SIGBM.', f.missing)

    def test_out_of_cycle_and_non_dam(self):
        x = {**ASSETS['B-01'], 'facts': {**ASSETS['B-01']['facts'], 'inspection_date': '2026-05-10'}}
        self.assertEqual(analyze(x, 'eir', '2026-04-17').state, 'NO_LINK')
        self.assertEqual(analyze(ASSETS['A-01'], 'eir', '2026-04-17').state, 'OUT_OF_SCOPE')


REQS = []


class FakeGemini(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        REQS.append({'path': self.path, 'body': body, 'key': self.headers.get('x-goog-api-key')})
        if 'busy' in self.path:
            self.send_response(503); self.end_headers(); self.wfile.write(b'{}'); return
        gc = body.get('generationConfig') or {}
        if gc.get('responseMimeType') == 'application/json':
            parts = [{'text': json.dumps({'simple': 'Resumo.', 'technical': 'Confirmar com o fiscalizador.'})}]
        elif body.get('tools'):
            done = sum(1 for c in body['contents'] for p in c['parts'] if 'functionResponse' in p)
            seq = ['verificar_fontes', 'priorizar', 'propor_acoes']
            parts = [{'functionCall': {'name': seq[done], 'args': {}}}] if done < len(seq) else [{'text': 'Pronto.'}]
        else:
            parts = [{'text': 'ok'}]
        raw = json.dumps({'candidates': [{'content': {'role': 'model', 'parts': parts}, 'finishReason': 'STOP'}]}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)


class GeminiProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), FakeGemini)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.httpd.server_address[1]}/v1beta/models/{{model}}:generateContent'

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def env(self, **kw):
        return mock.patch.dict(os.environ, {'TORRE_LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'teste-local', 'TORRE_GEMINI_MODEL': 'modelo-a', **kw})

    def test_schema_conversion(self):
        s = cloud_aws._gemini_schema({'type': 'object', 'additionalProperties': False, 'properties': {'a': {'type': 'array', 'items': {'type': 'string', 'enum': ['x']}}}})
        self.assertEqual(s, {'type': 'OBJECT', 'properties': {'a': {'type': 'ARRAY', 'items': {'type': 'STRING', 'enum': ['x']}}}})

    def test_structured_call_and_key_header(self):
        with self.env(), mock.patch.object(cloud_aws, 'GEMINI_URL', self.url):
            out = json.loads(cloud_aws.structured_call('sys', 'user', {'type': 'object', 'properties': {'simple': {'type': 'string'}}}))
        self.assertEqual(out['simple'], 'Resumo.')
        self.assertEqual(REQS[-1]['key'], 'teste-local')
        self.assertEqual(REQS[-1]['body']['generationConfig']['responseSchema']['type'], 'OBJECT')

    def test_fallback_when_model_busy(self):
        with self.env(TORRE_GEMINI_MODEL='busy'), mock.patch.object(cloud_aws, 'GEMINI_URL', self.url):
            d = cloud_aws.gemini_request({'contents': [{'role': 'user', 'parts': [{'text': 'oi'}]}]})
        self.assertNotEqual(d['_model'], 'busy')

    def test_agent_planner_function_calling(self):
        from app.agent import gemini_planner_factory
        calls = []
        with self.env(), mock.patch.object(cloud_aws, 'GEMINI_URL', self.url):
            gemini_planner_factory()({'verificar_fontes': 'a', 'priorizar': 'b', 'propor_acoes': 'c'}, lambda n: calls.append(n) or {'ok': n}, [])
        self.assertEqual(calls, ['verificar_fontes', 'priorizar', 'propor_acoes'])

    def test_status_with_gemini(self):
        from app.ai import llm_status
        with self.env(TORRE_LLM='1'):
            st = llm_status()
        self.assertEqual((st['provider'], st['enabled']), ('gemini', True))


if __name__ == '__main__':
    unittest.main()
