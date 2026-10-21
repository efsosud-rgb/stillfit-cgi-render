"""Texturas 2D da cena (PIL): mural 'O seu estilo de vida', telas de TV, monitores da recepção."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, random

import os; T = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tex') + os.sep; os.makedirs(T, exist_ok=True)
F = os.path.dirname(os.path.abspath(__file__)) + '/fonts/'
BS = F + 'big-shoulders-display-latin-900-normal.ttf'
AR7 = F + 'archivo-latin-700-normal.ttf'
AR5 = F + 'archivo-latin-500-normal.ttf'

# ---------- mural (parede roxa com halter em traço amarelo) ----------
W, H = 3072, 1536
im = Image.new('RGB', (W, H), (78, 66, 168))
g = Image.new('L', (W, H), 0)
gd = ImageDraw.Draw(g)
for r in range(0, 900, 6):  # leve vinheta/gradiente de luz
    gd.ellipse([W * 0.55 - r * 2, H * 0.35 - r, W * 0.55 + r * 2, H * 0.35 + r], fill=max(0, 70 - r // 13))
g = g.filter(ImageFilter.GaussianBlur(60))
im = Image.composite(Image.new('RGB', (W, H), (122, 108, 222)), im, g)
d = ImageDraw.Draw(im)
Y = (236, 206, 92)
WH = (246, 246, 250)
lw = 16
# halter inclinado em traço (estilo line-art do mural real)
cx, cy, ang = 980, 860, math.radians(-28)
def rot(x, y):
    return (cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang))
def rrect(x0, y0, x1, y1):
    pts = [rot(x0, y0), rot(x1, y0), rot(x1, y1), rot(x0, y1), rot(x0, y0)]
    d.line(pts, fill=Y, width=lw, joint='curve')
rrect(-520, -26, 520, 26)                    # barra
for s in (-1, 1):
    for k, (w, h) in enumerate([(60, 300), (55, 250), (50, 190)]):
        x = s * (330 + k * 66)
        rrect(x - w / 2, -h / 2, x + w / 2, h / 2)  # anilhas
# corda/linha ondulada saindo do halter
pts = []
for t in range(0, 101):
    u = t / 100
    x = 1380 + u * 900
    y = 520 - 260 * u + 90 * math.sin(u * 9)
    pts.append((x, y))
d.line(pts, fill=WH, width=10, joint='curve')
# textos
f1 = ImageFont.truetype(AR7, 230)
f2 = ImageFont.truetype(AR5, 150)
d.text((1720, 560), 'Still Fit', font=f1, fill=WH, stroke_width=6, stroke_fill=(40, 30, 90))
d.text((1600, 830), 'O seu estilo de vida', font=f2, fill=WH)
d.rounded_rectangle([1600, 1030, 2950, 1056], radius=12, fill=Y)
im.save(T + 'mural.png')

# ---------- silhueta line-art (ginasta) para a parede das aulas ----------
im2 = Image.new('RGBA', (600, 2000), (0, 0, 0, 0))
d2 = ImageDraw.Draw(im2)
path = [(300, 60), (290, 300), (330, 520), (250, 700), (360, 900), (230, 1100), (330, 1300), (260, 1500), (320, 1700), (280, 1950)]
d2.line(path, fill=(235, 235, 245, 255), width=14, joint='curve')
d2.ellipse([250, 400, 350, 500], outline=(235, 235, 245, 255), width=12)
im2.save(T + 'lineart.png')

# ---------- telas de TV (conteúdo genérico de treino, desfocado) ----------
random.seed(3)
for i in range(4):
    tv = Image.new('RGB', (640, 360))
    td = ImageDraw.Draw(tv)
    c1 = [(20, 40, 110), (90, 20, 60), (10, 70, 90), (60, 50, 20)][i]
    for y in range(360):
        k = y / 360
        td.line([(0, y), (640, y)], fill=tuple(int(c * (1.4 - k * 0.8)) for c in c1))
    for _ in range(14):
        x, y = random.randint(0, 640), random.randint(0, 360)
        r = random.randint(30, 120)
        col = tuple(min(255, int(v * 2.6)) for v in c1)
        td.ellipse([x - r, y - r, x + r, y + r], fill=col)
    tv = tv.filter(ImageFilter.GaussianBlur(18))
    td = ImageDraw.Draw(tv)
    td.text((40, 280), 'STILL FIT', font=ImageFont.truetype(BS, 60), fill=(255, 210, 60))
    tv.save(T + f'tv{i}.png')

# ---------- monitor da recepção ----------
mon = Image.new('RGB', (480, 300), (235, 238, 245))
md = ImageDraw.Draw(mon)
md.rectangle([0, 0, 480, 40], fill=(31, 63, 174))
for k in range(6):
    md.rectangle([20, 60 + k * 38, 300, 80 + k * 38], fill=(200, 206, 220))
md.rectangle([320, 60, 460, 260], fill=(255, 194, 26))
mon.save(T + 'monitor.png')
print('tex ok')
