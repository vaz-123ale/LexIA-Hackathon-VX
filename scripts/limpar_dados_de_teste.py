"""Remove do banco da demonstração o que os testes automáticos de navegador deixam (contas "Teste E2E", convites e e-mails de teste).

Uso: python scripts/limpar_dados_de_teste.py [caminho do banco]   (padrão: var/torre.db). Rode com o servidor parado.
Não toca nas contas de demonstração (@demo.lexia.app) nem em denúncias reais de quem testou a plataforma.
"""
import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else 'var/torre.db'
c = sqlite3.connect(db)
TESTE = "(email LIKE 'e2e%@ex.com' OR email LIKE '%@exemplo.invalid' OR name = 'Teste E2E')"
ids = [r[0] for r in c.execute(f'SELECT id FROM users WHERE {TESTE}')]
n_users = c.execute(f'DELETE FROM users WHERE {TESTE}').rowcount
n_inv = c.execute("DELETE FROM invites WHERE email LIKE '%@exemplo.invalid' OR email LIKE 'e2e%@ex.com'").rowcount
n_mail = c.execute("DELETE FROM email_outbox WHERE to_email LIKE '%@exemplo.invalid' OR to_email LIKE 'e2e%@ex.com'").rowcount
if ids:
    q = ','.join('?' * len(ids))
    c.execute(f'DELETE FROM sessions WHERE user_id IN ({q})', ids)
c.commit()
print(f'contas de teste: {n_users} · convites: {n_inv} · e-mails: {n_mail}')
