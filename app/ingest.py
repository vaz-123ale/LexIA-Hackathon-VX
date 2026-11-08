"""Ingestão curada: verifica emissor, licença, marcação interna, redirecionamento e
injeção de instruções ANTES de qualquer indexação. Não faz download: recebe o
conteúdo já coletado por um humano autorizado. Nunca declara 'vigência verificada'.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .store import now, sha256

ALLOWED_SUFFIXES = ('gov.br', 'leg.br', 'jus.br', 'mp.br')
LICENSE_BLOCKED = ('abnt.org.br', 'iso.org', 'abntcatalogo.com.br')
INTERNAL_MARKS = re.compile(r'\b(INTERNA|CONFIDENCIAL|USO\s+INTERNO|RESTRITO)\b', re.I)
INJECTION = re.compile(r'(ignore (as|todas as) instru|ignore (all |the )?previous|desconsidere as regras|system prompt|aja como)', re.I)


def _host(url: str) -> str:
    return (urlparse(url).hostname or '').lower()


def _allowed(host: str) -> bool:
    return any(host == s or host.endswith('.' + s) for s in ALLOWED_SUFFIXES)


def check(doc: dict[str, Any]) -> dict[str, Any]:
    title = str(doc.get('title', '')).strip()[:300]
    issuer = str(doc.get('issuer', '')).strip()[:200]
    url = str(doc.get('url', '')).strip()[:1000]
    final_url = str(doc.get('final_url') or url).strip()[:1000]
    content = str(doc.get('content', ''))[:200000]
    checks = []

    def add(cid, ok, msg, severity='info'):
        checks.append({'id': cid, 'ok': ok, 'message': msg, 'severity': severity})

    host, final_host = _host(url), _host(final_url)
    add('url_https', url.startswith('https://'), 'URL usa HTTPS.' if url.startswith('https://') else 'URL sem HTTPS.', 'block')
    add('emissor_oficial', _allowed(host), f'Domínio {host or "?"} ' + ('está na lista de emissores oficiais.' if _allowed(host) else 'não está na lista de emissores oficiais autorizados.'), 'quarantine')
    lic = any(host.endswith(b) or final_host.endswith(b) for b in LICENSE_BLOCKED)
    add('licenca', not lic, 'Norma técnica protegida: não ingerir texto integral.' if lic else 'Sem indicação de licença restritiva conhecida (confirmar).', 'block')
    redirected = bool(final_host) and final_host != host
    add('redirecionamento', not redirected, f'URL final ({final_host}) difere do emissor declarado ({host}).' if redirected else 'URL final coincide com a declarada.', 'quarantine')
    internal = bool(INTERNAL_MARKS.search(content))
    add('marcacao_interna', not internal, 'Documento contém marcação INTERNA/CONFIDENCIAL: bloqueado.' if internal else 'Sem marcação de documento interno.', 'block')
    inj = bool(INJECTION.search(content))
    add('injecao_instrucoes', not inj, 'Texto contém instruções dirigidas à IA (possível prompt injection): isolar.' if inj else 'Sem padrões de injeção de instruções.', 'quarantine')
    add('conteudo', len(content.strip()) >= 40, 'Conteúdo suficiente para registro.' if len(content.strip()) >= 40 else 'Conteúdo vazio ou curto demais.', 'block')
    add('vigencia', True, 'Abrir a página NÃO verifica vigência: vigência fica A_CONFERIR até revisão humana.', 'info')

    failed = {c['severity'] for c in checks if not c['ok']}
    status = 'BLOQUEADO' if 'block' in failed else 'QUARENTENA' if 'quarantine' in failed else 'ACEITO_PENDENTE_REVISAO'
    return {'title': title or '(sem título)', 'issuer': issuer or '(não informado)', 'url': url, 'final_url': final_url,
            'sha256': sha256(content), 'status': status, 'checks': checks, 'collected_at': now(),
            'validity_status': 'A_CONFERIR'}
