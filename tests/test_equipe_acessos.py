import os as _os
_os.environ['TORRE_LLM'] = '0'
import base64
import io
import unittest

from app.accounts import Accounts, MODULOS
from app.equipe_import import ler
from app.store import Store, WorkflowError

CNPJ = '11222333000181'


def _org(acc):
    adm = acc.register({'kind': 'empresa', 'name': 'Gestora', 'email': 'gestora@empresa.com.br', 'password': 'Senha1234', 'consent': True,
                        'function': 'compliance', 'org_name': 'Mineradora X', 'cnpj': CNPJ})
    return adm


class AcessosTests(unittest.TestCase):
    def setUp(self):
        self.acc = Accounts(Store(':memory:'))
        self.adm = _org(self.acc)

    def _convidar(self, email='tec@empresa.com.br', **kw):
        inv = self.acc.invite(self.adm, kw.get('nome', ''), email, kw.get('funcao', 'operacao'), kw.get('cargo', 'Técnico'), kw.get('empresa', 'demo-mineracao'), kw.get('modulos'))
        return inv, self.acc.accept_invite(inv['token'], 'Senha1234', True)

    def test_so_email_vira_nome_provisorio(self):
        inv, u = self._convidar('maria.souza@empresa.com.br')
        self.assertEqual(u['name'], 'Maria Souza')

    def test_frente_e_modulos_padrao_da_funcao(self):
        _, u = self._convidar()
        self.assertEqual(u['empresa_id'], 'demo-mineracao')
        self.assertEqual(u['modulos'], ['visao', 'operacao', 'ia'])
        self.assertEqual(u['cargo'], 'Técnico')

    def test_checklist_muda_na_hora(self):
        _, u = self._convidar()
        self.acc.set_access(self.adm, 'pessoa', u['id'], ['visao', 'relatorio', 'inexistente'])
        self.assertEqual(self.acc.user(u['id'])['modulos'], ['visao', 'relatorio'])   # módulo desconhecido é descartado

    def test_revogar_derruba_sessao(self):
        _, u = self._convidar()
        tok, _ = self.acc.login('tec@empresa.com.br', 'Senha1234', 'empresa')
        self.acc.change_member(self.adm, u['id'], status='suspenso', motivo='Acesso revogado pela gestão')
        self.assertIsNone(self.acc.session_user(tok))
        with self.assertRaises(WorkflowError):
            self.acc.login('tec@empresa.com.br', 'Senha1234', 'empresa')

    def test_quem_nao_e_gestao_nao_da_acesso(self):
        _, u = self._convidar()
        with self.assertRaises(WorkflowError):
            self.acc.set_access(u, 'pessoa', self.adm['id'], list(MODULOS))
        with self.assertRaises(WorkflowError):
            self.acc.invite(u, '', 'outra@empresa.com.br', 'operacao')

    def test_outra_organizacao_nao_mexe(self):
        _, u = self._convidar()
        outro = self.acc.register({'kind': 'empresa', 'name': 'Outra', 'email': 'g@outra.com.br', 'password': 'Senha1234', 'consent': True,
                                   'function': 'compliance', 'org_name': 'Outra SA', 'cnpj': '11444777000161'})
        with self.assertRaises(WorkflowError):
            self.acc.set_access(outro, 'pessoa', u['id'], [])

    def test_convite_duplicado_bloqueado(self):
        self.acc.invite(self.adm, '', 'dup@empresa.com.br', 'operacao')
        with self.assertRaises(WorkflowError):
            self.acc.invite(self.adm, '', 'dup@empresa.com.br', 'operacao')

    def test_checklist_do_convite_pendente(self):
        inv = self.acc.invite(self.adm, 'Ana', 'pend@empresa.com.br', 'juridico', empresa_id='demo-energia')
        self.acc.set_access(self.adm, 'convite', inv['id'], ['denuncias'])
        u = self.acc.accept_invite(inv['token'], 'Senha1234', True)
        self.assertEqual((u['modulos'], u['empresa_id']), (['denuncias'], 'demo-energia'))


class ImportarListaTests(unittest.TestCase):
    def test_texto_colado(self):
        r = ler('lista.txt', texto='Nome;Cargo;Email\nMaria Souza; Técnica de segurança; maria@x.com.br\nJoão Lima  Operador  joao@x.com.br\nlinha sem email\nMaria Souza; dup; maria@x.com.br')
        self.assertEqual([x['email'] for x in r['linhas']], ['maria@x.com.br', 'joao@x.com.br'])
        self.assertEqual(r['linhas'][1], {'nome': 'João Lima', 'cargo': 'Operador', 'email': 'joao@x.com.br'})

    def test_csv(self):
        raw = 'nome,cargo,email\nPedro Alves,Eletricista,pedro@x.com.br\n'.encode('utf-8')
        r = ler('equipe.csv', base64.b64encode(raw).decode())
        self.assertEqual(r['linhas'], [{'nome': 'Pedro Alves', 'cargo': 'Eletricista', 'email': 'pedro@x.com.br'}])

    def test_xlsx(self):
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active
        ws.append(['Nome', 'Cargo', 'E-mail']); ws.append(['Rita Dias', 'Engenheira', 'rita@x.com.br'])
        buf = io.BytesIO(); wb.save(buf)
        r = ler('equipe.xlsx', base64.b64encode(buf.getvalue()).decode())
        self.assertEqual(r['linhas'], [{'nome': 'Rita Dias', 'cargo': 'Engenheira', 'email': 'rita@x.com.br'}])

    def test_formato_nao_aceito(self):
        r = ler('foto.png', base64.b64encode(b'x').decode())
        self.assertEqual(r['linhas'], [])
        self.assertTrue(r['aviso'])


if __name__ == '__main__':
    unittest.main()
