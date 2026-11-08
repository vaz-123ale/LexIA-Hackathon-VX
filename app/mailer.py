"""Caixa de saída de e-mails (Amazon SES opcional).

Usada para avisar a EMPRESA responsável quando uma denúncia sobre um ativo dela é confirmada por quem denunciou.
- Só envia depois de confirmação humana (quem denuncia revisa e confirma o texto).
- Envio real somente com Amazon SES configurado (TORRE_SES_FROM + credenciais AWS padrão). Sem isso, a mensagem fica
  registrada na caixa de saída como "na fila (SES não configurado)" — nada é enviado escondido.
- Destinatários: e-mails CADASTRADOS na plataforma pelas pessoas da própria empresa (compliance/jurídico).
"""
from __future__ import annotations

import os

from .store import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS email_outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT, to_email TEXT, to_org TEXT, subject TEXT, body TEXT, state TEXT, provider TEXT,
  ref TEXT, created_at TEXT, sent_at TEXT, error TEXT);
"""


class Mailer:
    def __init__(self, store):
        self.store = store
        with store.lock:
            store.db.executescript(SCHEMA)
            store.db.commit()

    @staticmethod
    def configured() -> bool:
        return bool(os.environ.get('TORRE_SES_FROM'))

    def queue(self, to_email: str, to_org: str, subject: str, body: str, ref: str) -> dict:
        state, provider, err, sent = 'NA_FILA (SES não configurado)', 'local', None, None
        if self.configured():
            try:
                import boto3
                ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'sa-east-1')
                ses.send_email(Source=os.environ['TORRE_SES_FROM'], Destination={'ToAddresses': [to_email]},
                               Message={'Subject': {'Data': subject[:200], 'Charset': 'UTF-8'}, 'Body': {'Text': {'Data': body, 'Charset': 'UTF-8'}}})
                state, provider, sent = 'ENVIADO', 'amazon-ses', now()
            except Exception as exc:  # falha de envio: registra e mantém na fila
                state, provider, err = 'FALHOU', 'amazon-ses', f'{type(exc).__name__}: {str(exc)[:200]}'
        with self.store.lock:
            cur = self.store.db.execute('INSERT INTO email_outbox(to_email,to_org,subject,body,state,provider,ref,created_at,sent_at,error) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                        (to_email, to_org, subject[:200], body, state, provider, ref, now(), sent, err))
            self.store.db.commit()
        self.store.audit('mailer', 'email.queue', ref, {'to_org': to_org, 'state': state, 'provider': provider})
        return {'id': cur.lastrowid, 'to': to_email, 'state': state, 'provider': provider}

    def list(self, org: str | None = None, limit: int = 50) -> list[dict]:
        q, a = ('SELECT * FROM email_outbox WHERE to_org=? ORDER BY id DESC LIMIT ?', (org, limit)) if org else ('SELECT * FROM email_outbox ORDER BY id DESC LIMIT ?', (limit,))
        with self.store.lock:
            return [dict(r) for r in self.store.db.execute(q, a)]
