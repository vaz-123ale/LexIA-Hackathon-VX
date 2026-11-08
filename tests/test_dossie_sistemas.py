import os as _os
_os.environ['TORRE_LLM'] = '0'
import json
import unittest
from datetime import date

from app import denuncia, sistemas
from app.denuncia_dossie import verifica_formal, implicacoes, caminhos
from app.store import Store, WorkflowError

HOJE = date(2026, 11, 8)
ALVO = {'id': 'ATIVO:demo-energia:S-01', 'kind': 'empresa_ativo', 'name': 'Subestação Exemplo 230 kV', 'setor': 'energia', 'tipo': 'subestacao', 'municipio': '(ilustrativo)', 'uf': 'PR'}
RELATO = 'Semana passada vi um cabo energizado caído perto da cerca da subestação, soltando faísca. As crianças da escola passam ali todo dia.'


class DossieTests(unittest.TestCase):
    def test_dossie_completo_sem_ia(self):
        out = denuncia.build(RELATO, ALVO, [], HOJE, categoria='energia')
        d = out['dossie']
        self.assertEqual(d['motor_redacao'], 'regras')
        self.assertIn('Nas palavras dela', d['relato_formal'])          # sem IA, a fala original vai citada
        self.assertIn('nr10', [n['key'] for n in d['normas_descumpridas']])
        self.assertIn('caído', d['normas_descumpridas'][0]['trecho'])   # trecho do relato com acento
        self.assertEqual({i['familia'] for i in d['implicacoes']}, {'trabalho', 'energia'})
        self.assertEqual(d['caminhos'][0]['prazo'], 'imediato')
        self.assertEqual(out['gravidade'], 'alta')                      # cabo energizado com faísca

    def test_ia_redige_e_verificador_aceita(self):
        boa = lambda s, u, sch: json.dumps({'relato_formal': 'A pessoa denunciante relata que, por volta de 01/11/2026, observou um cabo energizado caído perto da cerca da Subestação Exemplo 230 kV.'})
        d = denuncia.build(RELATO, ALVO, [], HOJE, categoria='energia', llm_redacao=boa)['dossie']
        self.assertEqual(d['motor_redacao'], 'ia')

    def test_verificador_recusa_numero_ou_nome_inventado(self):
        ruim = lambda s, u, sch: json.dumps({'relato_formal': 'A pessoa relata que 40 crianças ficaram feridas e a Cemig foi avisada.'})
        d = denuncia.build(RELATO, ALVO, [], HOJE, categoria='energia', llm_redacao=ruim)['dossie']
        self.assertTrue(d['motor_redacao'].startswith('regras'))
        self.assertFalse(verifica_formal('Relata que a Copel foi avisada.', RELATO, 'Subestação Exemplo'))

    def test_normas_escolhidas_pelas_regras_mesmo_com_redacao_ia(self):
        chamadas = []
        fake = lambda s, u, sch: (chamadas.append(sch), json.dumps({'relato_formal': 'x', 'normas': ['INVENTADA']}))[1]
        out = denuncia.build('trinca no talude da barragem', None, [], HOJE, llm=fake, llm_redacao=fake)
        self.assertNotIn('INVENTADA', [n['key'] for n in out['normas']])
        self.assertTrue(all('relato_formal' in sch['properties'] for sch in chamadas))   # só a redação chamou a IA

    def test_sem_tema_reconhecido_tem_passo_padrao(self):
        self.assertEqual(caminhos([])[0]['papel'], 'Operação')
        self.assertEqual(implicacoes([], None), [])

    def test_empresa_marca_passo(self):
        st = Store(':memory:')
        desk = denuncia.DenunciaDesk(st)
        x = desk.save('usuario:1', ALVO['id'], denuncia.build(RELATO, ALVO, [], HOJE, categoria='energia'), [])
        desk.confirm(x['id'], 'usuario:1')
        denuncia.route_to_company(st, x['id'], '99888777', 'Energia Exemplo', 'Subestação', False)
        denuncia.marcar_passo(st, x['id'], '99888777', 0, True, 'Ana')
        item = denuncia.inbox(st, '99888777')[0]
        self.assertIn('0', item['passos'])
        self.assertTrue(item['dossie']['caminhos'])
        with self.assertRaises(WorkflowError):
            denuncia.marcar_passo(st, x['id'], 'outraorg', 0, True, 'X')


class SistemasTests(unittest.TestCase):
    def test_portfolio_em_escala_e_deterministico(self):
        a, b = sistemas.portfolio()['apps'], sistemas.portfolio()['apps']
        self.assertEqual(len(a), 2140)
        self.assertEqual([x['id'] for x in a[:50]], [x['id'] for x in b[:50]])

    def test_vigencia_escalonada_aponta_codigo(self):
        r = sistemas.mapear('ANM220-vigencia')
        sgb = next(x for x in r['afetados'] if x['id'] == 'sgb-inspecoes')
        diffs = '\n'.join(x['diff'] for x in sgb['achados'])
        self.assertIn("+    'arts_76_77': date(2027, 4, 22),", diffs)
        self.assertIn('+    \'art_7_par_1\': date(2029, 12, 26),', diffs)
        self.assertEqual(r['afetados'][0]['criticidade'], 'A')
        self.assertLess(r['ms'], 2000)

    def test_nr1_psicossocial(self):
        r = sistemas.mapear('NR1-psicossocial')
        sst = next(x for x in r['afetados'] if x['id'] == 'portal-sst')
        self.assertTrue(any("'psicossocial'" in x.get('diff', '') for x in sst['achados']))

    def test_revisar_sem_valor_inventado(self):
        r = sistemas.mapear('NR20-tanques')
        ger = next(x for x in r['afetados'] if x['id'] == 'app-geradores')
        self.assertEqual(ger['achados'][0]['tipo'], 'revisar')
        self.assertNotIn('diff', ger['achados'][0])

    def test_sistema_fora_do_dominio_nao_entra(self):
        r = sistemas.mapear('EIR-prazo-excepcional')
        self.assertNotIn('portal-sst', [x['id'] for x in r['afetados']])

    def test_mudanca_inexistente(self):
        with self.assertRaises(WorkflowError):
            sistemas.mapear('nao-existe')

    def test_aprovacao_humana_e_descarte_com_motivo(self):
        st = Store(':memory:')
        item = {'mudanca': 'ANM220-vigencia', 'sistema': 'SGB', 'arquivo': 'sgb/prazos.py', 'linha': 5, 'diff': '-a\n+b', 'equipe': 'Eng'}
        self.assertEqual(sistemas.decidir(st, 'org', item, 'APROVADA', '', 'Ana')['state'], 'APROVADA')
        with self.assertRaises(WorkflowError):
            sistemas.decidir(st, 'org', item, 'DESCARTADA', '', 'Ana')
        self.assertEqual(len(sistemas.tarefas(st, 'org')), 1)
        self.assertEqual(sistemas.tarefas(st, 'outra'), [])

    def test_ia_sugestao_so_com_trecho_existente(self):
        fake = lambda s, u, sch: json.dumps({'sugestoes': [
            {'arquivo': 'sgb/prazos.py', 'trecho_atual': 'PRAZO_EIR_DIA = 15                      # dia do mês seguinte ao fim do ciclo de inspeção', 'o_que_mudar': 'conferir'},
            {'arquivo': 'sgb/prazos.py', 'trecho_atual': 'linha que não existe', 'o_que_mudar': 'x'}]})
        r = sistemas.sugerir_ia('sgb-inspecoes', 'EIR-prazo-excepcional', fake)
        self.assertEqual(len(r['aceitas']), 1)
        self.assertEqual(len(r['recusadas']), 1)


if __name__ == '__main__':
    unittest.main()
