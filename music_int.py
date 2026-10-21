"""Trilha sintetizada para o filme completo (fachada 8 s + interior 16 s + logo 3 s ≈ 27 s).
Tudo gerado por código (sem amostras). Uso: python3 music_int.py saida.wav
"""
import sys
import numpy as np

SR = 48000
DUR = 27.0
N = int(SR * DUR)
rng = np.random.default_rng(5)
L = np.zeros(N); R = np.zeros(N)

def idx(t): return int(round(t * SR))

def env(n, a, d, s, r, hold):
    out = np.zeros(n)
    ia, id_, ih, ir = int(a * SR), int(d * SR), int(hold * SR), int(r * SR)
    i = 0
    out[i:i + ia] = np.linspace(0, 1, ia)[:max(0, n - i)]; i += ia
    out[i:i + id_] = np.linspace(1, s, id_)[:max(0, n - i)]; i += id_
    out[i:i + ih] = s; i += ih
    m = min(ir, n - i)
    if m > 0: out[i:i + m] = np.linspace(s, 0, ir)[:m]
    return out[:n]

def add(sig, t, gain=1.0, pan=0.0):
    i = idx(t)
    if i >= N: return
    n = min(len(sig), N - i)
    gl = np.cos((pan + 1) * np.pi / 4); gr = np.sin((pan + 1) * np.pi / 4)
    L[i:i + n] += sig[:n] * gain * gl; R[i:i + n] += sig[:n] * gain * gr

def pad(freq, dur, detune=0.4):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.zeros(n)
    for k, dt in enumerate((-detune, 0, detune)):
        f = freq * (1 + dt / 100)
        s += np.sin(2 * np.pi * f * t + 0.3 * k) * (0.5 if k == 1 else 0.3)
        s += 0.15 * np.sin(2 * np.pi * f * 2 * t)
    lfo = 1 + 0.08 * np.sin(2 * np.pi * 0.35 * t)
    return s * lfo * env(n, 1.2, 0.5, 0.8, 1.5, max(0, dur - 3.2))

def bass(freq, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 0.5 * t)
    return s * env(n, 0.02, 0.1, 0.7, 0.2, max(0, dur - 0.32))

def kick(dur=0.35):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 55 + 120 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)

def hat(dur=0.08):
    n = int(dur * SR)
    return rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 90) * 0.35

def whoosh(t0, dur=2.0, gain=0.5):
    n = int(dur * SR); t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    # filtro passa-banda simples via média móvel (grave) + modulação
    k = 40
    low = np.convolve(noise, np.ones(k) / k, mode='same')
    e = np.sin(np.pi * t / dur) ** 2
    add(low * e * 3.0, t0, gain, pan=-0.3)

# harmonia: Dm – Bb – F – C (A=440), progressão cinematográfica
chords = [(146.83, 174.61, 220.0), (116.54, 146.83, 174.61), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0)]
bar = 2.0
# 0–8 s (fachada): pad suave crescendo
for i in range(4):
    for f in chords[i % 4]:
        add(pad(f, bar + 1.5), i * bar, 0.08, pan=rng.uniform(-0.5, 0.5))
# 8 s: transição (porta) — whoosh + bumbo
whoosh(7.2, 2.2, 0.6)
# 8–24 s (interior): pad + baixo + batida leve
for i in range(4, 12):
    ch = chords[i % 4]
    for f in ch:
        add(pad(f, bar + 1.0), i * bar, 0.11, pan=rng.uniform(-0.6, 0.6))
    add(bass(ch[0] / 2, bar), i * bar, 0.22)
    for b in range(4):
        add(kick(), i * bar + b * 0.5, 0.5 if b % 2 == 0 else 0.3)
        add(hat(), i * bar + b * 0.5 + 0.25, 0.18, pan=0.4)
# 24–27 s (logo): acorde final sustentado
for f in (146.83, 220.0, 293.66, 440.0):
    add(pad(f, 3.5), 24.0, 0.12)
add(kick(0.6), 24.0, 0.6)

mix = np.stack([L, R], 1)
# fades
fade = int(0.8 * SR)
mix[:fade] *= np.linspace(0, 1, fade)[:, None]
mix[-int(1.5 * SR):] *= np.linspace(1, 0, int(1.5 * SR))[:, None]
mix = np.tanh(mix * 1.4) * 0.8
mix /= max(1e-6, np.abs(mix).max()) / 0.85
import wave
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok', sys.argv[1])
