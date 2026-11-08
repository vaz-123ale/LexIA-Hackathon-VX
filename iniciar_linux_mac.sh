#!/bin/sh
# LexIA - abre em http://localhost:8765
cd "$(dirname "$0")"
python3 -m app.server
