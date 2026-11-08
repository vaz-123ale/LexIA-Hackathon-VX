import os as _os
_os.environ['TORRE_LLM'] = '0'  # testes nunca chamam provedor externo
import unittest
import json
from pathlib import Path
from app.engine import analyze, answer

DATA=Path(__file__).resolve().parents[1]/'data'
ASSETS={a['id']:a for a in json.loads((DATA/'assets.json').read_text(encoding='utf8'))}
SOURCES=json.loads((DATA/'sources.json').read_text(encoding='utf8'))

class EngineTests(unittest.TestCase):
    def test_nr20_case(self):
        self.assertEqual(analyze(ASSETS['A-01'],'nr20').state,'REVIEW')
        self.assertIsNone(analyze(ASSETS['A-01'],'nr20').legal_deadline)
    def test_missing_info(self):
        x=analyze(ASSETS['A-02'],'nr20')
        self.assertEqual(x.state,'INSUFFICIENT')
        self.assertIn('Combustível utilizado',x.missing)
    def test_offshore_excluded(self):
        self.assertEqual(analyze(ASSETS['A-03'],'nr20').state,'OUT_OF_SCOPE')
    def test_no_link(self):
        self.assertEqual(analyze(ASSETS['A-04'],'nr20').state,'NO_LINK')
    def test_anm_future(self):
        x=analyze(ASSETS['B-01'],'anm')
        self.assertEqual(x.state,'FUTURE_REVIEW')
        self.assertIn('26/12/2029',x.rationale)
    def test_anm_other_assets(self):
        for name in ('A-01','A-02','A-03','A-04'):
            self.assertEqual(analyze(ASSETS[name],'anm').state,'OUT_OF_SCOPE')
    def test_non_observed_question_abstains(self):
        self.assertEqual(answer('Qual multa devo pagar?', 'simples', SOURCES)['state'],'ABSTAIN')
    def test_two_profiles_preserve_sources(self):
        p=answer('O que mudou na NR-20?', 'simples', SOURCES)
        t=answer('O que mudou na NR-20?', 'tecnico', SOURCES)
        self.assertEqual(p['source_ids'],t['source_ids'])
        self.assertNotEqual(p['answer'],t['answer'])
    def test_catalog_42(self):
        self.assertEqual(len(SOURCES),45)  # 42 do dossiê + F43/F44 (caso EIR) + F45 (NR-1, riscos psicossociais)
        self.assertEqual(len(set(s['id'] for s in SOURCES)),45)
        self.assertTrue(all(s['url'].startswith('https://') for s in SOURCES))
    def test_all_scenarios_no_wrong_state(self):
        allowed={'REVIEW','INSUFFICIENT','OUT_OF_SCOPE','NO_LINK','FUTURE_REVIEW'}
        for asset in ASSETS.values():
            for scenario in ('nr20','anm'):
                self.assertIn(analyze(asset,scenario).state,allowed)

if __name__=='__main__':unittest.main()
