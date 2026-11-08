"""Gera a narração do vídeo de demonstração com voz neural (edge-tts) e mede a duração de cada cena.

Uso: python scripts/gerar_narracao.py   →  docs/video/audio/<cena>.mp3 e docs/video/duracoes.json
A gravação (scripts/gravar_video_demo.mjs) usa as durações para sincronizar a tela com a fala.
"""
import asyncio
import json
import re
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
VID = ROOT / 'docs' / 'video'
FF = imageio_ffmpeg.get_ffmpeg_exe()


def duracao(p: Path) -> float:
    err = subprocess.run([FF, '-i', str(p)], capture_output=True, text=True).stderr
    h, m, s = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


async def main():
    R = json.loads((VID / 'roteiro.json').read_text(encoding='utf8'))
    (VID / 'audio').mkdir(parents=True, exist_ok=True)
    out = {}
    for c in R['cenas']:
        p = VID / 'audio' / f"{c['id']}.mp3"
        await edge_tts.Communicate(c['fala'], R['voz'], rate=R['velocidade']).save(str(p))
        out[c['id']] = round(duracao(p), 2)
        print(c['id'], out[c['id']])
    (VID / 'duracoes.json').write_text(json.dumps(out, indent=1), encoding='utf8')
    print('total', round(sum(out.values()), 1), 's')


asyncio.run(main())
