import os as _os
_os.environ['TORRE_LLM'] = '0'
import unittest
from datetime import date

from app.denuncia import build
from app.denuncia_organiza import organizar, quando, verificar_fatos
from app.transparencia import proximos_categoria

HOJE = date(2026, 11, 7)  # sábado


class OrganizaTests(unittest.TestCase):
    def test_endereco_informado_entra_no_resumo_sem_inventar_coordenadas(self):
        r = organizar('Vi água barrenta perto da ponte.\n(Endereço informado: Rua das Flores, 42, Centro, Cidade/MG)', HOJE)
        self.assertEqual(r['onde'], 'Rua das Flores, 42, Centro, Cidade/MG')
        self.assertNotIn('lat', r)

    def test_endereco_nao_vira_data_da_ocorrencia(self):
        r = organizar('Vi um fio caído na calçada.\n(Endereço informado: Rua 12/10, Centro)', HOJE)
        self.assertIsNone(r['quando'])

    def test_endereco_preserva_estrutura_escolhida(self):
        r = organizar('Vi vazamento no local.\n(Endereço informado: Perto da ponte)', HOJE,
                      {'id': 'DEMO-1', 'name': 'Estrutura fictícia', 'municipio': 'Cidade', 'uf': 'MG'})
        self.assertIn('Perto da ponte', r['onde'])
        self.assertIn('DEMO-1', r['onde'])

    def test_datas_relativas(self):
        self.assertEqual(quando('Ontem vi uma trinca', HOJE)['data'], '2026-11-06')
        self.assertEqual(quando('Anteontem passei lá', HOJE)['data'], '2026-11-05')
        self.assertEqual(quando('Na sexta passada a água veio suja', HOJE)['data'], '2026-11-06')
        self.assertEqual(quando('Há 3 dias tem cheiro forte', HOJE)['data'], '2026-11-04')
        self.assertEqual(quando('12/10 vi lama', HOJE)['data'], '2026-10-12')

    def test_data_vaga_pede_complemento(self):
        q = quando('Outro dia vi fio solto', HOJE)
        self.assertIsNone(q['data'])
        self.assertEqual(q['precisao'], 'vaga')
        self.assertIn('quando aconteceu', organizar('Outro dia vi fio solto no poste da rua', HOJE)['faltando'])

    def test_sem_data_nao_inventa(self):
        self.assertIsNone(quando('Tem um cabo caído no chão perto da escola', HOJE))

    def test_data_futura_rejeitada(self):
        q = quando('dia 30 vi a sirene tocar', HOJE)  # dia 30 deste mês ainda não chegou: vira o mês anterior, nunca data futura
        self.assertEqual(q['data'], '2026-10-30')

    def test_desde_e_afetados(self):
        o = organizar('Desde março a água sai turva e as crianças da escola reclamam, acontece de novo toda semana.', HOJE)
        self.assertEqual(o['desde']['texto'], 'desde março/2026')
        self.assertIn('crianças / escola', o['afetados'])
        self.assertTrue(o['recorrente'])

    def test_verificador_barra_numero_inventado(self):
        rel = 'Ontem vi água saindo na base da barragem.'
        self.assertEqual(verificar_fatos(['Vazamento de 300 litros por hora.', 'Água saindo na base.'], rel), ['Água saindo na base.'])


class DenunciaSetorTests(unittest.TestCase):
    def test_energia_sem_lei_de_barragens(self):
        out = build('Ontem à noite vi fio solto e faísca no poste da rua.', None, [], HOJE, categoria='energia')
        refs = [n['key'] for n in out['normas']]
        self.assertIn('nr10', refs)
        self.assertNotIn('art17a_p2', refs)
        self.assertIn('direito de petição', out['body'])
        self.assertEqual(out['resumo']['quando']['data'], '2026-11-06')

    def test_barragem_mantem_lei_12334(self):
        out = build('Ontem vi uma trinca no talude da barragem.', None, [], HOJE, categoria='barragem')
        self.assertIn('art17a_p2', [n['key'] for n in out['normas']])
        self.assertIn('Lei 12.334/2010', out['body'])


class ProximosCategoriaTests(unittest.TestCase):
    def setUp(self):
        self.kw = dict(
            radar_items=[{'id': 'SIGBM-1', 'kind': 'mineracao', 'name': 'B1', 'municipio': 'X', 'uf': 'MG', 'lat': -20.0, 'lon': -43.9}],
            records_by_id={}, minas=[{'id': 'ANM-1', 'processo': '1/2000', 'substancia': 'FERRO', 'categoria_label': 'Metálico', 'uf': 'MG', 'titular': 'MINERADORA X LTDA', 'lat': -20.01, 'lon': -43.9}],
            ativos_demo=[{'id': 'ATIVO:demo-energia:S-01', 'tipo': 'Subestacao', 'tipo_raw': 'subestacao', 'nome': 'Sub', 'local': 'PR', 'empresa': 'Energia Exemplo (fictícia)', 'lat': -25.5, 'lon': -52.0, 'setor': 'energia'}],
            snisb_setores={'energia': [{'id': 'SNISB-9', 'name': 'PCH Y\t\t', 'municipio': 'Z', 'uf': 'MG', 'lat': -20.02, 'lon': -43.9, 'use': 'Hidroelétrica', 'owner': 'ENERGIA Y LTDA'}], 'abastecimento': []},
            usinas=[{'id': 'CEG-1', 'ceg': 'X.1', 'nome': 'Sol', 'tipo': 'UFV', 'tipo_rotulo': 'Usina fotovoltaica', 'uf': 'MG', 'municipios': 'Z - MG', 'proprietarios': '100% para JOAO DA SILVA', 'lat': -20.03, 'lon': -43.9}],
            recebe=lambda r: False)

    def test_energia_so_mostra_energia(self):
        r = proximos_categoria(-20.0, -43.9, 'energia', **self.kw)
        ids = [x['id'] for x in r['items']]
        self.assertIn('SNISB-9', ids)
        self.assertIn('CEG-1', ids)
        self.assertNotIn('SIGBM-1', ids)
        self.assertNotIn('ANM-1', ids)
        self.assertEqual([x['n'] for x in r['items']], list(range(1, len(ids) + 1)))

    def test_pessoa_fisica_oculta_e_nome_limpo(self):
        r = proximos_categoria(-20.0, -43.9, 'energia', **self.kw)
        usina = next(x for x in r['items'] if x['id'] == 'CEG-1')
        self.assertNotIn('JOAO', usina['empresa'])
        self.assertEqual(next(x for x in r['items'] if x['id'] == 'SNISB-9')['nome'], 'PCH Y')

    def test_ativo_ficticio_marcado_e_longe(self):
        r = proximos_categoria(-20.0, -43.9, 'energia', **self.kw)
        demo = [x for x in r['items'] if not x['real']]
        self.assertEqual(len(demo), 1)
        self.assertTrue(demo[0]['longe'] and demo[0]['recebe_direto'])
        self.assertIn('fictícia', demo[0]['fonte'])

    def test_categoria_sem_nada_perto(self):
        r = proximos_categoria(-3.0, -60.0, 'saneamento', **{**self.kw, 'ativos_demo': []})
        self.assertEqual(r['items'], [])
        self.assertTrue(r['vazio'])


if __name__ == '__main__':
    unittest.main()
