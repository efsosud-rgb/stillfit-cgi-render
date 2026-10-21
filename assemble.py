"""Monta o filme final: fachada (clipe aprovado) + interior (render Cycles) + cartela com logos + trilha.
Uso: python3 assemble.py <dir_frames_interior> <fachada.mp4> <badge.png> <wings.png> <trilha.wav> <saida.mp4>
Precisa de ffmpeg no PATH.
"""
import os, subprocess, sys, glob, shutil

FR, FAC, BADGE, WINGS, MUSIC, OUT = sys.argv[1:7]
W, H, FPS = 1280, 720, 24
tmp = os.path.join(os.path.dirname(os.path.abspath(OUT)) or '.', '_asm'); os.makedirs(tmp, exist_ok=True)

frames = sorted(glob.glob(os.path.join(FR, 'f_*.png')))
assert len(frames) >= 300, f'poucos quadros: {len(frames)}'
seq = os.path.join(tmp, 'seq'); os.makedirs(seq, exist_ok=True)
for i, f in enumerate(frames, 1):
    dst = os.path.join(seq, f'i_{i:04d}.png')
    if not os.path.exists(dst): os.symlink(os.path.abspath(f), dst)
n_int = len(frames)
dur_int = n_int / FPS

def run(cmd):
    print(' '.join(cmd), flush=True); subprocess.run(cmd, check=True)

# 1) interior em ProRes-like intermediário (h264 crf baixo), com leve grade cinematográfica e vinheta
interior = os.path.join(tmp, 'interior.mp4')
run(['ffmpeg', '-y', '-v', 'error', '-framerate', str(FPS), '-i', os.path.join(seq, 'i_%04d.png'),
     '-vf', f'scale={W}:{H}:flags=lanczos,eq=contrast=1.04:saturation=1.05,vignette=PI/5,format=yuv420p',
     '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', interior])

# 2) fachada normalizada para 1280x720 24 fps (sem áudio)
facade = os.path.join(tmp, 'facade.mp4')
run(['ffmpeg', '-y', '-v', 'error', '-i', FAC, '-an', '-vf', f'scale={W}:{H}:flags=lanczos,fps={FPS},format=yuv420p',
     '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', facade])
fac_dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', facade]).decode().strip())

# 3) cartela final: fundo escuro, selo Still Fit grande, logo Wings pequena, 3 s
card_dur = 3.0
card = os.path.join(tmp, 'card.mp4')
run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=0x0A0E1A:s={W}x{H}:r={FPS}:d={card_dur}',
     '-i', BADGE, '-i', WINGS,
     '-filter_complex',
     f"[1:v]scale=-1:300:flags=lanczos,format=rgba,fade=t=in:st=0.2:d=0.6:alpha=1[b];"
     f"[2:v]scale=200:-1:flags=lanczos,format=rgba,colorchannelmixer=aa=0.9,fade=t=in:st=0.8:d=0.6:alpha=1[w];"
     f"[0:v][b]overlay=x=(W-w)/2:y=(H-h)/2-40:format=auto[v1];[v1][w]overlay=x=(W-w)/2:y=H-h-70:format=auto,format=yuv420p[v]",
     '-map', '[v]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', card])

# 4) concatenação com dissolve de 0,5 s fachada→interior e 0,6 s interior→cartela; selo no canto a partir do interior
xf1 = 0.5; xf2 = 0.6
off1 = fac_dur - xf1
off2 = off1 + dur_int - xf2
total = off2 + card_dur
run(['ffmpeg', '-y', '-v', 'error', '-i', facade, '-i', interior, '-i', card, '-i', MUSIC, '-i', BADGE, '-i', WINGS,
     '-filter_complex',
     f"[0:v][1:v]xfade=transition=fade:duration={xf1}:offset={off1:.3f}[a];"
     f"[a][2:v]xfade=transition=fade:duration={xf2}:offset={off2:.3f}[b];"
     f"[4:v]scale=-1:96:flags=lanczos,format=rgba,colorchannelmixer=aa=0.92,fade=t=in:st={fac_dur:.2f}:d=0.6:alpha=1,fade=t=out:st={off2 - 0.3:.2f}:d=0.3:alpha=1[bug];"
     f"[5:v]scale=170:-1:flags=lanczos,format=rgba,colorchannelmixer=aa=0.85,fade=t=in:st={fac_dur:.2f}:d=0.6:alpha=1,fade=t=out:st={off2 - 0.3:.2f}:d=0.3:alpha=1[wl];"
     f"[b][bug]overlay=x=40:y=32:format=auto[c];[c][wl]overlay=x=W-w-44:y=H-h-36:format=auto,format=yuv420p[v];"
     f"[3:a]atrim=0:{total:.3f},afade=t=out:st={total - 1.2:.3f}:d=1.2[aud]",
     '-map', '[v]', '-map', '[aud]', '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
     '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-t', f'{total:.3f}', OUT])
# versão para o slide (≤ 20 MB): 2 passes com bitrate alvo
deck = OUT.replace('.mp4', '_deck.mp4')
vb = int((18.0e6 * 8) / total - 110_000)
run(['ffmpeg', '-y', '-v', 'error', '-i', OUT, '-c:v', 'libx264', '-preset', 'slow', '-b:v', str(vb), '-maxrate', str(int(vb * 1.4)), '-bufsize', str(vb * 2),
     '-pass', '1', '-passlogfile', os.path.join(tmp, 'x264'), '-an', '-f', 'null', '/dev/null'])
run(['ffmpeg', '-y', '-v', 'error', '-i', OUT, '-c:v', 'libx264', '-preset', 'slow', '-b:v', str(vb), '-maxrate', str(int(vb * 1.4)), '-bufsize', str(vb * 2),
     '-pass', '2', '-passlogfile', os.path.join(tmp, 'x264'), '-c:a', 'aac', '-b:a', '112k', '-movflags', '+faststart', deck])
print('OK', OUT, os.path.getsize(OUT), deck, os.path.getsize(deck), 'dur', round(total, 2))
