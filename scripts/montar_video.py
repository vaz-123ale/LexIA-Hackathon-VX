"""Monta o MP4 do vídeo de demonstração: quadros gravados (var/video_frames) + narração por cena no instante em que a cena começou.

Uso: python scripts/montar_video.py  →  docs/video/LexIA_demo.mp4
"""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
FF = imageio_ffmpeg.get_ffmpeg_exe()
FR = ROOT / 'var' / 'video_frames'
TL = json.loads((ROOT / 'var' / 'video_timeline.json').read_text(encoding='utf8'))
VID = ROOT / 'docs' / 'video'

frames, cenas, fim = TL['frames'], TL['cenas'], TL['fim']
t0 = frames[0]['t']
# 1) vídeo: cada quadro fica na tela até o próximo (screencast só manda quadro quando a tela muda)
lst = FR / 'lista.txt'
with lst.open('w', encoding='utf8') as f:
    for a, b in zip(frames, frames[1:] + [{'f': frames[-1]['f'], 't': fim}]):
        f.write(f"file '{a['f']}'\nduration {max(b['t'] - a['t'], 0.001):.4f}\n")
    f.write(f"file '{frames[-1]['f']}'\n")
mudo = ROOT / 'var' / 'video_mudo.mp4'
mudo.unlink(missing_ok=True)   # sobrescrever no lugar já gerou arquivo corrompido
subprocess.run([FF, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst), '-vf', 'fps=30,scale=1920:1080:flags=lanczos,format=yuv420p',
                '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', str(mudo)], check=True)
# 2) áudio: cada fala começa 0,3 s depois do início da cena
ins, filt = [], []
for i, c in enumerate(cenas):
    ins += ['-i', str(VID / 'audio' / f"{c['id']}.mp3")]
    ms = max(int((c['t'] - t0 + 0.3) * 1000), 0)
    filt.append(f'[{i + 1}:a]adelay={ms}|{ms},aformat=channel_layouts=stereo[a{i}]')
mix = ''.join(f'[a{i}]' for i in range(len(cenas))) + f'amix=inputs={len(cenas)}:normalize=0,loudnorm=I=-16:TP=-1.5[aout]'
out = VID / 'LexIA_demo.mp4'
subprocess.run([FF, '-y', '-loglevel', 'error', '-i', str(mudo), *ins, '-filter_complex', ';'.join(filt) + ';' + mix,
                '-map', '0:v', '-map', '[aout]', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-b:a', '160k', '-shortest', '-movflags', '+faststart', str(out)], check=True)
print('ok', out, f'{fim - t0:.1f}s')
