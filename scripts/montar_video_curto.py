"""Monta o vídeo curto (≈40 s, sem áudio): quadros de var/video_frames_curto, com cortes secos onde a gravação pausou
(logins e carregamentos). Uso: python scripts/montar_video_curto.py → docs/video/LexIA_40s.mp4
"""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
FF = imageio_ffmpeg.get_ffmpeg_exe()
FR = ROOT / 'var' / 'video_frames_curto'
TL = json.loads((ROOT / 'var' / 'video_timeline_curto.json').read_text(encoding='utf8'))
frames, pausas, fim = TL['frames'], TL['pausas'], TL['fim']


def dur(t, prox):
    for p0, p1 in pausas:   # se a pausa começou entre este quadro e o próximo, o quadro dura só até a pausa
        if t <= p0 < prox:
            return max(p0 - t, 0.04)
    return max(prox - t, 0.001)


lst = FR / 'lista.txt'
total = 0.0
with lst.open('w', encoding='utf8') as f:
    for a, b in zip(frames, frames[1:] + [{'f': frames[-1]['f'], 't': fim}]):
        d = dur(a['t'], b['t']); total += d
        f.write(f"file '{a['f']}'\nduration {d:.4f}\n")
    f.write(f"file '{frames[-1]['f']}'\n")
out = ROOT / 'docs' / 'video' / 'LexIA_40s.mp4'
out.unlink(missing_ok=True)
subprocess.run([FF, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-vf', 'fps=30,scale=1920:1080:flags=lanczos,format=yuv420p',
                '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-an', '-movflags', '+faststart', str(out)], check=True)
print('ok', out, f'{total:.1f}s')
