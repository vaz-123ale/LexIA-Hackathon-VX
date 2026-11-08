"""Monitor de fontes oficiais (source_monitor) — quase em tempo real, por verificação periódica.

O que faz:
- SIGBM/ANM: compara a listagem oficial (data e tamanho) com o snapshot atual; se mudou, coleta
  e valida um novo snapshot automaticamente (dados, não normas) e notifica.
- Páginas e PDFs oficiais do catálogo + textos oficiais dos dispositivos: baixa com limite de tamanho,
  normaliza o texto e compara o SHA-256 com a última verificação. Mudou → notificação
  "requer curadoria". NUNCA altera regra, vigência ou triagem sozinho.
Etiqueta:
- Respeita robots.txt de cada host (urllib.robotparser), só hosts oficiais da lista,
  uma requisição por vez com intervalo, User-Agent identificado e timeout.
- Canais que proíbem robôs ou exigem credencial ficam registrados como BLOQUEADO, sem tentativa.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
import urllib.request
import urllib.robotparser
from typing import Any, Callable
from urllib.parse import urlparse

USER_AGENT = 'Torre360-monitor/0.4 (hackathon; monitoramento de fontes publicas)'
ALLOWED_HOSTS = ('gov.br', 'leg.br', 'anm.gov.br', 'anmlegis.datalegis.net')
MAX_BYTES = 8 * 1024 * 1024
BLOCKED_CHANNELS = [
    {'id': 'DOU_SITE', 'name': 'Diário Oficial da União (site in.gov.br)', 'url': 'https://www.in.gov.br/',
     'reason': 'robots.txt do site proíbe qualquer robô (Disallow: /). Caminho oficial: serviço INLABS da Imprensa Nacional, que exige cadastro e credenciais.'},
    {'id': 'LEXML', 'name': 'LexML Brasil (Senado)', 'url': 'https://www.lexml.gov.br/',
     'reason': 'Responde com verificação de segurança anti-robô. Não contornamos; requer acordo de acesso ou API autorizada.'},
]


def _allowed_host(url: str) -> bool:
    h = (urlparse(url).hostname or '').lower()
    return any(h == a or h.endswith('.' + a) for a in ALLOWED_HOSTS)


def normalize(body: bytes, ctype: str) -> bytes:
    """PDF: bytes como estão. HTML: só o texto visível, sem scripts/estilos/espaços repetidos."""
    if 'pdf' in ctype or body[:4] == b'%PDF':
        return body
    t = body.decode('utf-8', errors='replace')
    t = re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>', ' ', t)
    t = re.sub(r'(?s)<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip().encode('utf8')


class Monitor:
    def __init__(self, accounts, sources: list[dict], provisions: list[dict], sigbm_module, on_sigbm: Callable[[], None],
                 delay: float = 1.0, fetch: Callable | None = None):
        self.acc = accounts
        self.sigbm = sigbm_module
        self.on_sigbm = on_sigbm
        self.delay = delay
        self.fetch = fetch or self._fetch
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.running = False
        self.last_run: dict[str, Any] | None = None
        self.targets = []
        for s in sources:
            if _allowed_host(s['url']) and s.get('verification') in ('T', 'C'):
                self.targets.append({'id': s['id'], 'name': s['title'], 'url': s['url'], 'kind': 'fonte'})
        seen = {t['url'] for t in self.targets}
        for p in provisions:
            u = p.get('official_text_url')
            if u and u not in seen and _allowed_host(u):
                seen.add(u)
                self.targets.append({'id': 'TXT-' + p['id'].split('-')[0], 'name': f"Texto oficial · {p['document']}", 'url': u, 'kind': 'texto'})

    def _fetch(self, url: str, timeout: int = 20) -> tuple[int, bytes, str]:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(MAX_BYTES), r.headers.get('Content-Type', '')

    def robots_ok(self, url: str) -> bool:
        p = urlparse(url)
        base = f'{p.scheme}://{p.netloc}'
        if base not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                st, body, _ = self.fetch(base + '/robots.txt')
                rp.parse(body.decode('utf-8', errors='replace').splitlines() if st == 200 else [])
            except Exception:
                rp.parse([])  # sem robots acessível: segue a regra padrão (permitido)
            self.robots[base] = rp
        return self.robots[base].can_fetch(USER_AGENT, url)

    def check_sigbm(self, current_manifest: dict | None) -> dict[str, Any]:
        try:
            listing = self.sigbm.fetch_listing()
        except Exception as exc:
            self.acc.save_check('ANM_SIGBM', self.sigbm.load_schema()['listing_url'], 'ERRO', None, None, False, f'{type(exc).__name__}: {exc}')
            return {'status': 'ERRO'}
        entry = next((x for x in listing if x['name'] == 'Barragens.csv'), None)
        sig = hashlib.sha256(f"{entry and entry['listed_at']}|{entry and entry['bytes']}".encode()).hexdigest()
        prev = (current_manifest or {}).get('listing_entry')
        changed = bool(entry and prev and (entry['listed_at'], entry['bytes']) != (prev.get('listed_at'), prev.get('bytes')))
        detail = f"listagem oficial: {entry and entry['listed_at']} · {entry and entry['bytes']} bytes"
        if changed:
            try:
                m = self.sigbm.fetch()
                self.on_sigbm()
                detail += f" → novo snapshot {m['snapshot_id']} ({m['quality']['accepted']} aceitas, {m['quality']['rejected']} rejeitadas)"
                self.acc.notify('todos', 'dados', 'ANM publicou nova versão do SIGBM',
                                f"Snapshot {m['snapshot_id']} coletado e validado automaticamente: {m['quality']['accepted']} estruturas aceitas, {m['quality']['rejected']} rejeitadas.",
                                '#/gov', 'ANM_SIGBM')
            except Exception as exc:
                detail += f' → coleta falhou ({type(exc).__name__}); snapshot anterior mantido'
                self.acc.notify('empresa', 'alerta', 'Falha ao atualizar o SIGBM', detail, '#/gov', 'ANM_SIGBM')
        self.acc.save_check('ANM_SIGBM', self.sigbm.load_schema()['listing_url'], 'OK', 200, sig, changed, detail)
        return {'status': 'OK', 'changed': changed}

    def check_target(self, t: dict[str, Any]) -> dict[str, Any]:
        if not self.robots_ok(t['url']):
            self.acc.save_check(t['id'], t['url'], 'BLOQUEADO_ROBOTS', None, None, False, 'robots.txt não permite este caminho')
            return {'status': 'BLOQUEADO_ROBOTS'}
        try:
            st, body, ctype = self.fetch(t['url'])
        except Exception as exc:
            self.acc.save_check(t['id'], t['url'], 'ERRO', None, None, False, f'{type(exc).__name__}: {str(exc)[:160]}')
            return {'status': 'ERRO'}
        if st != 200:
            self.acc.save_check(t['id'], t['url'], 'ERRO', st, None, False, f'HTTP {st}')
            return {'status': 'ERRO'}
        sha = hashlib.sha256(normalize(body, ctype)).hexdigest()
        prev = self.acc.last_ok_hash(t['id'])
        changed = prev is not None and prev != sha
        self.acc.save_check(t['id'], t['url'], 'OK', st, sha, changed, ('conteúdo mudou desde a última verificação' if changed else 'linha de base registrada' if prev is None else 'sem mudança') + f' · {len(body)} bytes')
        if changed:
            self.acc.notify('empresa', 'norma', f"Mudança detectada: {t['name']}",
                            'O conteúdo da fonte oficial mudou. Requer curadoria: pode ser alteração normativa ou apenas editorial. Nenhuma regra foi alterada automaticamente.',
                            '#/gov', t['id'])
        return {'status': 'OK', 'changed': changed}

    def run_once(self, current_manifest: dict | None) -> dict[str, Any]:
        if self.running:
            return {'status': 'JA_EM_EXECUCAO'}
        self.running = True
        started = time.time()
        res = {'sigbm': None, 'checked': 0, 'changed': 0, 'errors': 0, 'blocked': 0}
        try:
            r = self.check_sigbm(current_manifest)
            res['sigbm'] = r
            for t in self.targets:
                time.sleep(self.delay)
                r = self.check_target(t)
                res['checked'] += 1
                res['changed'] += 1 if r.get('changed') else 0
                res['errors'] += 1 if r['status'] == 'ERRO' else 0
                res['blocked'] += 1 if r['status'] == 'BLOQUEADO_ROBOTS' else 0
        finally:
            self.running = False
        res['seconds'] = round(time.time() - started, 1)
        self.last_run = {**res, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        return res

    def start_background(self, interval_min: float, get_manifest: Callable[[], dict | None], first_delay: float = 30) -> threading.Thread:
        def loop():
            time.sleep(first_delay)
            while True:
                try:
                    self.run_once(get_manifest())
                except Exception:
                    pass
                time.sleep(max(60, interval_min * 60))
        th = threading.Thread(target=loop, daemon=True, name='torre-monitor')
        th.start()
        return th
