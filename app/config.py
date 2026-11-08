"""Carrega configuração local de um arquivo .env na raiz do projeto (fora da pasta publicada pelo servidor).

- Só define variáveis que ainda não existem no ambiente (o ambiente sempre vence).
- Nunca imprime valores. O .env está no .gitignore.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path | None = None) -> list[str]:
    path = path or ROOT / '.env'
    loaded = []
    if os.environ.get('TORRE_LLM') == '0':  # IA desligada (testes/offline): nem carrega chaves
        return loaded
    if not path.exists():
        return loaded
    for line in path.read_text(encoding='utf8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v
            loaded.append(k)
    return loaded
