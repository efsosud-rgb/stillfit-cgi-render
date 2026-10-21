"""Still Fit Xerém — interior CGI (Blender 5.2 / Cycles), layout real estimado a partir dos vídeos.
Uso:
  python scene.py --frames 1 432 1 --res 1280 720 --spp 16 --out /home/claude/blender/out
  python scene.py --frames 1 1 1 --res 640 360 --spp 8 --out /home/claude/blender/test   (teste)
Eixos: x ao longo da fachada (0 = parede da recepção), y para dentro (0 = vidro), z para cima. Metros.
"""
import bpy, bmesh, math, random, sys, os, time
from mathutils import Vector, Matrix

A = sys.argv[1:]
def arg(name, n=1, default=None):
    if name in A:
        i = A.index(name)
        v = A[i + 1:i + 1 + n]
        return v if n > 1 else v[0]
    return default
F0, F1, FS = (int(x) for x in arg('--frames', 3, ['1', '1', '1']))
RX, RY = (int(x) for x in arg('--res', 2, ['640', '360']))
SPP = int(arg('--spp', 1, '8'))
OUT = arg('--out', 1, '/home/claude/blender/test')
os.makedirs(OUT, exist_ok=True)
TEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tex') + os.sep
FONT_BS = os.path.dirname(os.path.abspath(__file__)) + '/fonts/big-shoulders-display-latin-900-normal.ttf'
FONT_AR = os.path.dirname(os.path.abspath(__file__)) + '/fonts/archivo-latin-700-normal.ttf'
BADGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logos', 'stillfit_badge.png')
random.seed(7)

L, D, H = 38.0, 24.0, 4.0          # salão estimado: fachada 38 m, profundidade 24 m, laje 4,0 m
COVE_Z = 3.55                        # fundo das sancas

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
root = sc.collection

# ------------------------------------------------------------------ materiais
M = {}
def principled(name, color=(0.5, 0.5, 0.5), rough=0.5, metal=0.0, emit=None, es=0.0, alpha=1.0, trans=0.0, ior=1.45, coat=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['IOR'].default_value = ior
    if trans: b.inputs['Transmission Weight'].default_value = trans
    if coat: b.inputs['Coat Weight'].default_value = coat
    if alpha < 1: b.inputs['Alpha'].default_value = alpha
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = es
    M[name] = m
    return m

def emission(name, color, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs['Color'].default_value = (*color, 1); e.inputs['Strength'].default_value = strength
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(e.outputs[0], o.inputs['Surface'])
    M[name] = m
    return m

def image_mat(name, path, emit=0.0, rough=0.5, alpha=False, box_proj=False):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(path, check_existing=True)
    t.extension = 'CLIP'
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    if emit:
        nt.links.new(t.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = emit
    if alpha:
        nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
    M[name] = m
    return m

def wood_floor():
    m = bpy.data.materials.new('wood'); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; Ln = nt.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1 / 1.357, 1 / 0.197, 1)          # tábua 1357 x 197 mm
    Ln.new(tc.outputs['Object'], mp.inputs['Vector'])
    br = N.new('ShaderNodeTexBrick'); br.offset = 0.37; br.offset_frequency = 1
    br.inputs['Scale'].default_value = 1.0; br.inputs['Mortar Size'].default_value = 0.004
    br.inputs['Brick Width'].default_value = 1.0; br.inputs['Row Height'].default_value = 1.0
    br.inputs['Color1'].default_value = (0.42, 0.27, 0.15, 1); br.inputs['Color2'].default_value = (0.58, 0.40, 0.24, 1)
    br.inputs['Mortar'].default_value = (0.16, 0.10, 0.06, 1); br.inputs['Bias'].default_value = 0.0
    Ln.new(mp.outputs['Vector'], br.inputs['Vector'])
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.0; nz.inputs['Detail'].default_value = 6
    m2 = N.new('ShaderNodeMapping'); m2.inputs['Scale'].default_value = (0.25, 6.0, 1)
    Ln.new(mp.outputs['Vector'], m2.inputs['Vector']); Ln.new(m2.outputs['Vector'], nz.inputs['Vector'])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 0.35
    Ln.new(br.outputs['Color'], mix.inputs[6]); Ln.new(nz.outputs['Color'], mix.inputs[7])
    Ln.new(mix.outputs[2], b.inputs['Base Color'])
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.18; rr.inputs['To Max'].default_value = 0.34
    Ln.new(nz.outputs['Fac'], rr.inputs['Value']); Ln.new(rr.outputs['Result'], b.inputs['Roughness'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.15; bp.inputs['Distance'].default_value = 0.002
    Ln.new(br.outputs['Fac'], bp.inputs['Height']); Ln.new(bp.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Coat Weight'].default_value = 0.25; b.inputs['Coat Roughness'].default_value = 0.08
    M['wood'] = m

def grid_mat(name, base, line, cell, rough=0.8, mortar=0.012):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; Ln = nt.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1 / cell, 1 / cell, 1)
    Ln.new(tc.outputs['Object'], mp.inputs['Vector'])
    br = N.new('ShaderNodeTexBrick'); br.offset = 0.0
    br.inputs['Scale'].default_value = 1.0; br.inputs['Mortar Size'].default_value = mortar
    br.inputs['Brick Width'].default_value = 1.0; br.inputs['Row Height'].default_value = 1.0
    br.inputs['Color1'].default_value = (*base, 1); br.inputs['Color2'].default_value = tuple(c * 1.12 for c in base) + (1,)
    br.inputs['Mortar'].default_value = (*line, 1)
    Ln.new(mp.outputs['Vector'], br.inputs['Vector']); Ln.new(br.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    M[name] = m

def speckle(name, base, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; Ln = nt.links; b = N['Principled BSDF']
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 90; nz.inputs['Detail'].default_value = 2
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].position = 0.55; cr.color_ramp.elements[0].color = (*base, 1)
    cr.color_ramp.elements[1].position = 0.62; cr.color_ramp.elements[1].color = tuple(min(1, c * 2.4 + 0.02) for c in base) + (1,)
    Ln.new(nz.outputs['Fac'], cr.inputs['Fac']); Ln.new(cr.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    M[name] = m

def green_wall():
    m = bpy.data.materials.new('greenwall'); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; Ln = nt.links; b = N['Principled BSDF']
    vo = N.new('ShaderNodeTexVoronoi'); vo.inputs['Scale'].default_value = 26
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 9; nz.inputs['Detail'].default_value = 8
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (0.02, 0.07, 0.015, 1); cr.color_ramp.elements[1].color = (0.16, 0.34, 0.06, 1)
    Ln.new(nz.outputs['Fac'], cr.inputs['Fac']); Ln.new(cr.outputs['Color'], b.inputs['Base Color'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.9; bp.inputs['Distance'].default_value = 0.03
    mx = N.new('ShaderNodeMath'); mx.operation = 'MULTIPLY'
    Ln.new(vo.outputs['Distance'], mx.inputs[0]); Ln.new(nz.outputs['Fac'], mx.inputs[1])
    Ln.new(mx.outputs[0], bp.inputs['Height']); Ln.new(bp.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Roughness'].default_value = 0.6
    b.inputs['Subsurface Weight'].default_value = 0.1
    M['greenwall'] = m

def wood_panel():
    m = bpy.data.materials.new('woodpanel'); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; Ln = nt.links; b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord'); mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1, 1, 1)
    Ln.new(tc.outputs['Object'], mp.inputs['Vector'])
    wv = N.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'
    wv.inputs['Scale'].default_value = 2.5; wv.inputs['Distortion'].default_value = 6; wv.inputs['Detail'].default_value = 3
    Ln.new(mp.outputs['Vector'], wv.inputs['Vector'])
    cr = N.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color = (0.50, 0.33, 0.18, 1); cr.color_ramp.elements[1].color = (0.70, 0.50, 0.30, 1)
    Ln.new(wv.outputs['Fac'], cr.inputs['Fac']); Ln.new(cr.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.45
    M['woodpanel'] = m

wood_floor(); wood_panel(); green_wall()
grid_mat('ceil', (0.028, 0.030, 0.036), (0.075, 0.08, 0.09), 0.625, rough=0.85, mortar=0.01)
speckle('rubber', (0.018, 0.018, 0.02), 0.9)
principled('greywall', (0.58, 0.59, 0.63), 0.8)
principled('purple', (0.20, 0.15, 0.55), 0.75)
principled('blackwall', (0.035, 0.035, 0.04), 0.7)
principled('metal', (0.025, 0.025, 0.028), 0.33, 0.6)
principled('chrome', (0.85, 0.86, 0.88), 0.12, 1.0)
principled('alu', (0.55, 0.56, 0.58), 0.3, 1.0)
principled('pad', (0.03, 0.03, 0.035), 0.55)
principled('yellow', (0.95, 0.70, 0.02), 0.28, coat=0.4)
principled('plate', (0.02, 0.02, 0.022), 0.6)
principled('glass', (0.9, 0.95, 0.97), 0.0, trans=1.0, ior=1.5)
principled('mirror', (0.95, 0.95, 0.96), 0.02, 1.0)
principled('smoked', (0.01, 0.01, 0.012), 0.06, coat=1.0)
principled('whiteplastic', (0.85, 0.86, 0.88), 0.4)
principled('quartz', (0.86, 0.86, 0.84), 0.2)
principled('teal', (0.05, 0.16, 0.16), 0.85)
principled('asphalt', (0.03, 0.03, 0.035), 0.12)
principled('glassdark', (0.02, 0.03, 0.05), 0.02, coat=1.0)
emission('ledw', (1.0, 0.93, 0.85), 22)
emission('ledb', (0.05, 0.22, 1.0), 14)
emission('ledbup', (0.05, 0.22, 1.0), 30)
emission('ledwarm', (1.0, 0.72, 0.42), 12)
emission('consoleglow', (0.25, 0.55, 1.0), 1.2)
emission('tvscreen', (0.2, 0.45, 1.0), 0.5)
emission('streetlamp', (1.0, 0.62, 0.3), 40)
emission('gcroom', (0.55, 0.45, 1.0), 0.6)
emission('txtwhite', (0.95, 0.95, 1.0), 4)
emission('txtyellow', (1.0, 0.72, 0.12), 5)
image_mat('badge', BADGE, emit=1.6, rough=0.4, alpha=True)
image_mat('mural', TEX + 'mural.png', emit=0.25, rough=0.8)
image_mat('lineart', TEX + 'lineart.png', emit=2.0, rough=0.8, alpha=True)
image_mat('monitor', TEX + 'monitor.png', emit=2.5, rough=0.2)
for i in range(4):
    image_mat(f'tv{i}', TEX + f'tv{i}.png', emit=3.0, rough=0.15)

# ------------------------------------------------------------------ geometria
def link(o, coll):
    (coll or root).objects.link(o)
    return o

def mesh_obj(name, bm, mat, coll=None, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); me.materials.append(M[mat] if isinstance(mat, str) else mat)
    return link(o, coll)

def box(c, s, mat, coll=None, bevel=0.0, name='box', rz=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(s), verts=bm.verts)
    if rz: bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=Matrix.Rotation(rz, 3, 'Z'), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    o = mesh_obj(name, bm, mat, coll)
    if bevel:
        md = o.modifiers.new('bv', 'BEVEL'); md.width = bevel; md.segments = 2; md.limit_method = 'ANGLE'
    return o

def cyl(p0, p1, r, mat, coll=None, seg=14, name='cyl', r2=None):
    p0, p1 = Vector(p0), Vector(p1); v = p1 - p0; h = v.length
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h)
    q = Vector((0, 0, 1)).rotation_difference(v.normalized())
    bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=q.to_matrix(), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(p0 + p1) / 2, verts=bm.verts)
    return mesh_obj(name, bm, mat, coll, smooth=True)

def plane(c, w, h, mat, axis='Y', coll=None, name='pl', flip=False):
    """retângulo vertical: axis 'Y' -> plano XZ (normal +-y); 'X' -> plano YZ; 'Z' -> horizontal"""
    cx, cy, cz = c; hw, hh = w / 2, h / 2
    if axis == 'Y': vs = [(cx - hw, cy, cz - hh), (cx + hw, cy, cz - hh), (cx + hw, cy, cz + hh), (cx - hw, cy, cz + hh)]
    elif axis == 'X': vs = [(cx, cy + hw, cz - hh), (cx, cy - hw, cz - hh), (cx, cy - hw, cz + hh), (cx, cy + hw, cz + hh)]
    else: vs = [(cx - hw, cy - hh, cz), (cx + hw, cy - hh, cz), (cx + hw, cy + hh, cz), (cx - hw, cy + hh, cz)]
    if flip: vs = vs[::-1]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], [(0, 1, 2, 3)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, (u, w_) in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)] if not flip else [(0, 1), (1, 1), (1, 0), (0, 0)][::-1]):
        uv[i].uv = (u, w_)
    o = bpy.data.objects.new(name, me); me.materials.append(M[mat]); return link(o, coll)

def text(s, c, size, mat, rot=(math.pi / 2, 0, 0), coll=None, font=FONT_AR, extrude=0.004, align='CENTER'):
    cu = bpy.data.curves.new('txt', 'FONT'); cu.body = s; cu.size = size; cu.extrude = extrude
    cu.font = bpy.data.fonts.load(font, check_existing=True); cu.align_x = align; cu.align_y = 'CENTER'
    o = bpy.data.objects.new('txt', cu); o.location = c; o.rotation_euler = rot; o.data.materials.append(M[mat])
    return link(o, coll)

def disc(c, r, mat, normal_axis='X', sign=1, coll=None):
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=r)
    me = bpy.data.meshes.new('disc'); bm.to_mesh(me); bm.free()
    me.uv_layers.new()
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            me.uv_layers[0].data[li].uv = (v.x / (2 * r) + 0.5, v.y / (2 * r) + 0.5)
    o = bpy.data.objects.new('disc', me); me.materials.append(M[mat]); o.location = c
    if normal_axis == 'X': o.rotation_euler = (math.pi / 2, 0, math.pi / 2 if sign > 0 else -math.pi / 2)
    elif normal_axis == 'Y': o.rotation_euler = (math.pi / 2, 0, 0 if sign < 0 else math.pi)
    return link(o, coll)

# ------------------------------------------------------------------ equipamentos (coleções instanciáveis)
def new_coll(name):
    return bpy.data.collections.new(name)

def make_treadmill():
    c = new_coll('treadmill')
    box((0, 0.15, 0.13), (0.86, 2.0, 0.2), 'metal', c, 0.02)                 # base
    box((0, 0.35, 0.235), (0.56, 1.5, 0.02), 'pad', c)                          # lona
    for s in (-1, 1):
        box((s * 0.36, 0.3, 0.245), (0.12, 1.6, 0.03), 'alu', c, 0.008)         # estribos
    box((0, -0.78, 0.33), (0.86, 0.46, 0.4), 'metal', c, 0.04)                  # capô do motor
    for s in (-1, 1):
        cyl((s * 0.33, -0.72, 0.4), (s * 0.30, -0.55, 1.25), 0.035, 'metal', c)  # montantes
        cyl((s * 0.30, -0.55, 1.07), (s * 0.30, 0.05, 1.05), 0.022, 'alu', c)    # corrimão
    box((0, -0.58, 1.33), (0.80, 0.26, 0.09), 'metal', c, 0.03)                 # console
    box((0, -0.445, 1.36), (0.30, 0.006, 0.11), 'tvscreen', c)                  # tela pequena
    box((0, -0.70, 1.33), (0.22, 0.05, 0.05), 'alu', c, 0.01)
    return c

def make_bike():
    c = new_coll('bike')
    box((0, 0, 0.04), (0.55, 1.2, 0.06), 'metal', c, 0.01)
    box((0, -0.32, 0.36), (0.14, 0.42, 0.55), 'metal', c, 0.03)                 # carenagem do volante
    cyl((0, -0.3, 0.36), (0, -0.3, 0.36), 0.01, 'metal', c)
    cyl((0, 0.15, 0.08), (0, 0.22, 0.78), 0.03, 'metal', c)                     # canote
    box((0, 0.24, 0.82), (0.18, 0.28, 0.06), 'pad', c, 0.02)                    # selim
    cyl((0, -0.4, 0.6), (0, -0.42, 1.02), 0.03, 'metal', c)
    cyl((-0.22, -0.46, 1.02), (0.22, -0.46, 1.02), 0.02, 'alu', c)              # guidão
    box((0, -0.45, 1.12), (0.26, 0.04, 0.16), 'consoleglow', c)
    return c

def make_elliptical():
    c = new_coll('elliptical')
    box((0, 0.2, 0.06), (0.7, 1.9, 0.1), 'metal', c, 0.015)
    box((0, -0.62, 0.45), (0.5, 0.5, 0.8), 'metal', c, 0.05)
    for s in (-1, 1):
        cyl((s * 0.2, -0.45, 0.6), (s * 0.28, 0.1, 1.55), 0.025, 'alu', c)
        box((s * 0.16, 0.35, 0.3), (0.16, 0.38, 0.04), 'pad', c, 0.01)
    box((0, -0.62, 1.3), (0.34, 0.06, 0.22), 'consoleglow', c)
    return c

def make_stair():
    c = new_coll('stair')
    box((0, 0.1, 0.1), (0.85, 1.5, 0.18), 'metal', c, 0.02)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((0.8, 1.2, 1.2)), verts=bm.verts)
    bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=Matrix.Rotation(math.radians(38), 3, 'X'), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((0, -0.05, 0.75)), verts=bm.verts)
    mesh_obj('steps', bm, 'metal', c)
    for s in (-1, 1):
        cyl((s * 0.38, -0.5, 0.3), (s * 0.38, -0.4, 1.6), 0.025, 'alu', c)
    box((0, -0.55, 1.55), (0.5, 0.08, 0.3), 'metal', c, 0.02)
    box((0, -0.5, 1.58), (0.36, 0.01, 0.2), 'consoleglow', c)
    return c

def make_selector(v):
    c = new_coll(f'selector{v}')
    for sx in (-0.5, 0.5): box((sx, 0.0, 0.04), (0.09, 1.45, 0.08), 'metal', c, 0.01)   # trilhos da base
    box((0, -0.62, 0.04), (1.1, 0.12, 0.08), 'metal', c, 0.01)
    box((0, -0.62, 2.1), (0.66, 0.38, 0.08), 'metal', c, 0.02)                   # tampa
    for sx in (-0.12, 0.12): cyl((sx, -0.52, 0.1), (sx, -0.52, 2.05), 0.012, 'chrome', c)
    box((0, -0.62, 1.05), (0.62, 0.34, 2.05), 'metal', c, 0.02)                # torre
    box((0, -0.44, 1.05), (0.56, 0.02, 1.9), 'smoked', c)                      # acrílico fumê
    for k in range(14):
        box((0, -0.62, 0.15 + k * 0.05), (0.42, 0.2, 0.04), 'plate', c)       # pilha de peso
    text('MOVEMENT', (0.315, -0.62, 1.15), 0.12, 'txtwhite', rot=(math.pi / 2, -math.pi / 2, math.pi / 2), coll=c, font=FONT_AR)
    if v == 0:      # cadeira extensora / flexora
        box((0, 0.2, 0.5), (0.5, 0.6, 0.12), 'pad', c, 0.04)
        box((0, 0.5, 0.95), (0.48, 0.12, 0.75), 'pad', c, 0.04)
        cyl((-0.3, -0.1, 0.45), (0.3, -0.1, 0.45), 0.06, 'pad', c)
    elif v == 1:    # supino / remada sentada
        box((0, 0.35, 0.48), (0.42, 0.42, 0.1), 'pad', c, 0.04)
        box((0, 0.6, 0.95), (0.4, 0.1, 0.85), 'pad', c, 0.04)
        for s in (-1, 1):
            cyl((s * 0.35, -0.2, 1.6), (s * 0.45, 0.25, 1.15), 0.03, 'metal', c)
    else:           # puxador alto
        box((0, 0.35, 0.5), (0.42, 0.42, 0.1), 'pad', c, 0.04)
        cyl((0, -0.4, 2.1), (0, 0.4, 2.1), 0.04, 'metal', c)
        cyl((-0.45, 0.35, 1.7), (0.45, 0.35, 1.7), 0.02, 'chrome', c)
        cyl((0, 0.4, 2.1), (0, 0.35, 1.7), 0.006, 'metal', c)
    return c

def make_plateload(v):
    c = new_coll(f'plate{v}')
    box((0, 0, 0.05), (1.1, 1.7, 0.08), 'yellow', c, 0.015)
    for s in (-1, 1):
        cyl((s * 0.5, -0.6, 0.05), (s * 0.5, -0.5, 1.6 if v != 1 else 1.1), 0.05, 'yellow', c)
    if v == 0:      # leg press inclinado
        cyl((-0.5, -0.5, 1.6), (0.5, -0.5, 1.6), 0.05, 'yellow', c)
        box((0, 0.45, 0.55), (0.55, 0.6, 0.12), 'pad', c, 0.04)
        box((0, 0.8, 0.9), (0.55, 0.12, 0.7), 'pad', c, 0.04)
        for s in (-1, 1):
            cyl((s * 0.65, -0.3, 0.9), (s * 0.95, -0.3, 0.9), 0.025, 'chrome', c)
            for k in range(3): cyl((s * (0.7 + k * 0.06), -0.3, 0.9), (s * (0.74 + k * 0.06), -0.3, 0.9), 0.22 - k * 0.03, 'plate', c, seg=24)
    elif v == 1:    # hack / agachamento
        box((0, 0.1, 0.9), (0.6, 0.15, 1.0), 'pad', c, 0.04)
        for s in (-1, 1):
            cyl((s * 0.5, -0.55, 1.15), (s * 0.85, -0.55, 1.15), 0.025, 'chrome', c)
            for k in range(2): cyl((s * (0.58 + k * 0.07), -0.55, 1.15), (s * (0.63 + k * 0.07), -0.55, 1.15), 0.23, 'plate', c, seg=24)
    else:           # remada / peito convergente
        cyl((-0.5, -0.5, 1.6), (0.5, -0.5, 1.6), 0.05, 'yellow', c)
        box((0, 0.35, 0.5), (0.42, 0.42, 0.1), 'pad', c, 0.04)
        box((0, 0.65, 0.95), (0.42, 0.1, 0.8), 'pad', c, 0.04)
        for s in (-1, 1):
            cyl((s * 0.5, -0.5, 1.5), (s * 0.7, 0.2, 1.1), 0.045, 'yellow', c)
            cyl((s * 0.7, 0.2, 1.1), (s * 0.95, 0.2, 1.1), 0.025, 'chrome', c)
            cyl((s * 0.78, 0.2, 1.1), (s * 0.83, 0.2, 1.1), 0.22, 'plate', c, seg=24)
    return c

def make_bench():
    c = new_coll('bench')
    cyl((0, -0.55, 0.05), (0, 0.55, 0.05), 0.04, 'metal', c)
    for y in (-0.5, 0.5): cyl((-0.25, y, 0.03), (0.25, y, 0.03), 0.03, 'metal', c)
    cyl((0, -0.3, 0.05), (0, -0.25, 0.42), 0.035, 'metal', c); cyl((0, 0.3, 0.05), (0, 0.25, 0.42), 0.035, 'metal', c)
    box((0, 0.0, 0.46), (0.3, 1.2, 0.08), 'pad', c, 0.03)
    return c

def make_dbrack():
    c = new_coll('dbrack')
    for s in (-1, 1): box((s * 1.2, 0, 0.45), (0.06, 0.5, 0.9), 'metal', c, 0.01)
    for z, y in ((0.35, 0.12), (0.75, -0.08)):
        box((0, y, z), (2.4, 0.3, 0.04), 'metal', c, 0.005)
        for k in range(10):
            x = -1.08 + k * 0.24; r = 0.06 + k * 0.004
            cyl((x - 0.09, y, z + 0.08), (x + 0.09, y, z + 0.08), 0.017, 'chrome', c)
            for s in (-1, 1): cyl((x + s * 0.09, y, z + 0.08), (x + s * 0.13, y, z + 0.08), r, 'plate', c, seg=6)
    return c

def make_crossover():
    c = new_coll('crossover')
    for s in (-1, 1):
        box((s * 1.6, 0, 1.15), (0.5, 0.45, 2.3), 'metal', c, 0.02)
        box((s * 1.6, -0.24, 1.15), (0.42, 0.02, 2.0), 'smoked', c)
    box((0, 0, 2.33), (3.7, 0.12, 0.12), 'metal', c, 0.01)
    for x in (-0.6, 0, 0.6): cyl((x, -0.06, 2.25), (x, 0.06, 2.25), 0.05, 'alu', c)
    return c

def make_rack():
    c = new_coll('rack')
    for x in (-0.6, 0.6):
        for y in (-0.6, 0.6): box((x, y, 1.15), (0.08, 0.08, 2.3), 'metal', c, 0.006)
    for z in (2.3, 0.05):
        for x in (-0.6, 0.6): box((x, 0, z), (0.08, 1.28, 0.08), 'metal', c, 0.006)
        for y in (-0.6, 0.6): box((0, y, z), (1.28, 0.08, 0.08), 'metal', c, 0.006)
    cyl((-1.1, -0.6, 1.4), (1.1, -0.6, 1.4), 0.016, 'chrome', c)
    for s in (-1, 1): cyl((s * 0.85, -0.6, 1.4), (s * 0.95, -0.6, 1.4), 0.225, 'plate', c, seg=24)
    return c

def make_turnstile():
    c = new_coll('turnstile')
    box((0, 0, 0.5), (0.22, 1.1, 1.0), 'chrome', c, 0.03)
    box((0.0, 0, 1.005), (0.24, 1.12, 0.02), 'glassdark', c)
    box((0.35, 0.0, 0.75), (0.5, 0.02, 0.8), 'glass', c)
    box((-0.35, 0.0, 0.75), (0.5, 0.02, 0.8), 'glass', c)
    box((0, -0.45, 1.02), (0.12, 0.08, 0.02), 'consoleglow', c)
    return c

def make_sofa():
    c = new_coll('sofa')
    box((0, 0, 0.22), (2.2, 0.9, 0.36), 'teal', c, 0.06)
    box((0, 0.36, 0.6), (2.2, 0.2, 0.5), 'teal', c, 0.06)
    for s in (-1, 1): box((s * 1.05, 0, 0.42), (0.16, 0.9, 0.42), 'teal', c, 0.05)
    return c

def make_ac():
    c = new_coll('ac')
    box((0, 0, 0), (1.05, 0.24, 0.32), 'whiteplastic', c, 0.04)
    box((0, -0.121, -0.1), (0.9, 0.01, 0.06), 'pad', c)
    return c

COL = {k: f() for k, f in [('treadmill', make_treadmill), ('bike', make_bike), ('elliptical', make_elliptical), ('stair', make_stair),
                           ('bench', make_bench), ('dbrack', make_dbrack), ('crossover', make_crossover), ('rack', make_rack),
                           ('turnstile', make_turnstile), ('sofa', make_sofa), ('ac', make_ac)]}
for v in range(3):
    COL[f'sel{v}'] = make_selector(v); COL[f'pl{v}'] = make_plateload(v)

def put(kind, x, y, rz_deg=0.0, z=0.0):
    o = bpy.data.objects.new(kind, None); o.instance_type = 'COLLECTION'; o.instance_collection = COL[kind]
    o.location = (x, y, z); o.rotation_euler = (0, 0, math.radians(rz_deg)); root.objects.link(o); return o

# ------------------------------------------------------------------ arquitetura
box((L / 2, D / 2, -0.05), (L, D, 0.1), 'wood', name='floor')
box((31.5, 10.5, 0.008), (12.0, 11.8, 0.016), 'rubber', name='rubber')               # área de anilhas
box((L / 2, D / 2, H + 0.05), (L, D, 0.1), 'ceil', name='ceiling')
# paredes (internas)
box((-0.1, D / 2, H / 2), (0.2, D, H), 'greywall', name='wallA')
box((L + 0.1, D / 2, H / 2), (0.2, D, H), 'greywall', name='wallB')
box((L / 2, D + 0.1, H / 2), (L, 0.2, H), 'greywall', name='wallBack')
box((L / 2, 0.06, 3.6), (L, 0.12, 0.8), 'purple', name='fascia')                    # faixa roxa acima do vidro
# fachada de vidro com montantes a cada 1,5 m
box((L / 2, 0.0, 1.6), (L, 0.02, 3.2), 'glass', name='facade_glass')
for i in range(int(L / 1.5) + 1):
    box((i * 1.5, 0.0, 1.6), (0.06, 0.1, 3.2), 'metal', name='mullion')
box((L / 2, 0.0, 0.03), (L, 0.12, 0.06), 'metal', name='sill')
# pilares
for x in (10.5, 22.5, 34.5):
    for y in (3.4, 12.5):
        box((x, y, H / 2), (0.45, 0.45, H), 'blackwall', bevel=0.01, name='pillar')
# exterior noturno: asfalto molhado, meio-fio, postes
box((L / 2, -15, -0.06), (80, 30, 0.1), 'asphalt', name='asphalt')
box((L / 2, -1.2, 0.05), (L + 6, 2.2, 0.12), 'greywall', name='sidewalk')
for x in (4, 16, 28, 40):
    cyl((x, -9, 0), (x, -9, 5.2), 0.07, 'metal')
    cyl((x, -9, 5.2), (x, -8.2, 5.3), 0.05, 'metal')
    box((x, -8.1, 5.25), (0.4, 0.25, 0.08), 'streetlamp')
    lt = bpy.data.lights.new('street', 'POINT'); lt.energy = 900; lt.color = (1.0, 0.65, 0.35); lt.shadow_soft_size = 0.3
    lo = bpy.data.objects.new('street', lt); lo.location = (x, -8.1, 5.0); root.objects.link(lo)

# --- recepção (canto fachada x parede A)
box((0.03, 3.6, 1.6), (0.06, 5.8, 3.2), 'woodpanel', bevel=0.005, name='woodwall')
disc((0.08, 2.6, 2.15), 0.62, 'badge', 'X', +1)
for k in range(4):                                                                   # prateleiras iluminadas
    z = 0.55 + k * 0.55
    box((0.25, 5.4, z), (0.42, 1.7, 0.03), 'woodpanel', bevel=0.003)
    box((0.22, 5.4, z - 0.02), (0.3, 1.6, 0.008), 'ledwarm')
    for j in range(7):
        col = random.choice(['yellow', 'pad', 'whiteplastic', 'purple', 'teal'])
        hh = random.uniform(0.18, 0.3)
        cyl((0.25, 4.7 + j * 0.23, z + 0.015), (0.25, 4.7 + j * 0.23, z + 0.015 + hh), random.uniform(0.05, 0.07), col, seg=12)
box((3.3, 3.45, 0.55), (4.4, 0.7, 1.1), 'blackwall', bevel=0.01, name='counter')
box((3.3, 3.45, 1.11), (4.5, 0.78, 0.04), 'quartz', bevel=0.008, name='countertop')
box((3.3, 3.08, 0.08), (4.3, 0.02, 0.05), 'ledwarm', name='counterled')
for x in (2.4, 4.2):
    box((x, 3.55, 1.38), (0.55, 0.03, 0.34), 'metal', bevel=0.005)
    box((x, 3.535, 1.38), (0.5, 0.01, 0.3), 'monitor')
put('turnstile', 6.4, 1.05); put('turnstile', 6.4, 2.35)
box((6.4, 0.25, 0.5), (0.22, 0.5, 1.0), 'chrome', bevel=0.02)
put('rack', 8.0, 1.5)                                                               # gaiola perto do vidro (vista na recepção)
# porta de entrada (vidro com puxador)
box((2.2, 0.0, 1.1), (2.0, 0.03, 2.2), 'glassdark', name='door')
cyl((2.0, -0.05, 0.6), (2.0, -0.05, 1.6), 0.015, 'chrome')

# --- espelhos com moldura de LED quente
def mirror_x(xw, y0, y1, nrm):
    yc, w = (y0 + y1) / 2, y1 - y0
    box((xw + nrm * 0.01, yc, 1.35), (0.02, w, 2.0), 'mirror')
    box((xw + nrm * 0.025, yc, 2.37), (0.02, w + 0.04, 0.03), 'ledwarm')
    box((xw + nrm * 0.025, yc, 0.33), (0.02, w + 0.04, 0.03), 'ledwarm')
    for y in (y0 - 0.02, y1 + 0.02): box((xw + nrm * 0.025, y, 1.35), (0.02, 0.03, 2.07), 'ledwarm')
for y0, y1 in ((7.4, 11.6), (12.4, 16.6), (17.4, 21.6)): mirror_x(0.0, y0, y1, +1)
for y0, y1 in ((4.2, 8.2), (8.6, 12.6), (13.0, 16.4)): mirror_x(L, y0, y1, -1)
box((31.0, 16.98, 1.35), (10.0, 0.02, 2.0), 'mirror')
box((31.0, 16.96, 2.37), (10.04, 0.02, 0.03), 'ledwarm')

# --- fundo: jardim vertical, lounge roxo com selo, spinning, group classes
box((5.5, D - 0.05, 1.5), (2.0, 0.1, 3.0), 'greenwall', name='greenwall')
box((9.65, D - 0.03, 2.0), (6.3, 0.06, 4.0), 'purple', name='lounge_wall')
disc((9.65, D - 0.07, 2.05), 0.8, 'badge', 'Y', -1)
box((9.65, D - 0.08, 3.2), (3.4, 0.02, 0.03), 'ledwarm')
put('sofa', 8.4, D - 0.75, 180); put('sofa', 10.9, D - 0.75, 180)
box((9.65, D - 1.8, 0.2), (1.2, 0.6, 0.4), 'woodpanel', bevel=0.02, name='coffee')
box((9.65, D - 1.3, 0.006), (5.0, 2.4, 0.012), 'pad', name='rug')
box((14.1, D - 0.04, 1.05), (1.0, 0.06, 2.1), 'blackwall', name='spin_door')
text('SPINNING', (14.1, D - 0.1, 2.5), 0.22, 'txtwhite', rot=(math.pi / 2, 0, 0), font=FONT_AR)
text('<<<', (13.05, D - 0.1, 2.5), 0.2, 'txtwhite', rot=(math.pi / 2, 0, 0), font=FONT_AR)
box((19.5, D - 0.06, 2.0), (8.6, 0.12, 4.0), 'blackwall', name='gc_wall')
box((18.3, D - 0.13, 1.65), (5.0, 0.02, 1.5), 'gcroom', name='gc_window')
box((22.1, D - 0.13, 1.05), (1.0, 0.02, 2.1), 'metal', name='gc_door')
text('GROUP CLASSES', (18.3, D - 0.14, 2.85), 0.34, 'txtyellow', rot=(math.pi / 2, 0, 0), font=FONT_BS)
text('AULAS COLETIVAS', (18.3, D - 0.14, 2.55), 0.13, 'txtwhite', rot=(math.pi / 2, 0, 0), font=FONT_AR)
plane((23.2, D - 0.14, 1.6), 0.5, 1.7, 'lineart', 'Y', flip=True)
text('<<', (16.0, D - 0.14, 3.45), 0.3, 'txtyellow', rot=(math.pi / 2, 0, 0), font=FONT_BS)
# bloco dos vestiários/sala (x 24-38, y 17-24) com mural na face oeste
box((31.0, 20.5, H / 2), (14.0, 7.0, H), 'greywall', name='block')
plane((23.995, 20.5, 2.0), 7.0, 3.5, 'mural', 'X', flip=False)
# ar-condicionado
for y in (6.0, 12.0, 18.0): put('ac', 0.13, y, 90, 3.25)
for y in (6.0, 12.0): put('ac', L - 0.13, y, -90, 3.25)
for x in (3.0, 27.5): put('ac', x, D - 0.13 if x < 24 else 16.87, 180, 3.25)
# TVs sobre o cardio, presas no vidro, viradas para dentro
for i, x in enumerate((8.0, 13.5, 24.0, 29.5, 35.0)):
    box((x, 0.16, 2.55), (1.25, 0.06, 0.72), 'metal', bevel=0.01)
    box((x, 0.195, 2.55), (1.18, 0.01, 0.66), f'tv{i % 4}')

# --- teto: sancas (fundo branco + LED azul na borda e no topo) e lâmpadas lineares
for cx in (5.5, 14.5, 23.5, 32.5):
    for cy in (7.0, 15.5):
        w, d_ = 6.2, 4.6
        box((cx, cy, COVE_Z + 0.11), (w, d_, 0.22), 'whiteplastic', name='cove')
        for (dx, dy, sw, sd) in ((0, d_ / 2 + 0.006, w, 0.012), (0, -d_ / 2 - 0.006, w, 0.012), (w / 2 + 0.006, 0, 0.012, d_), (-w / 2 - 0.006, 0, 0.012, d_)):
            box((cx + dx, cy + dy, COVE_Z + 0.11), (sw, sd, 0.2), 'ledb')               # borda azul
        box((cx, cy, COVE_Z + 0.23), (w + 0.1, d_ + 0.1, 0.01), 'ledbup', name='cove_up')  # luz azul lavando o teto
        for k in range(4):                                                                # chevrons brancos
            yy = cy - 1.5 + k * 1.0
            for s in (-1, 1):
                box((cx + s * 0.95, yy + 0.32, COVE_Z - 0.006), (1.95, 0.05, 0.012), 'ledw', rz=s * math.radians(-18))
        lt = bpy.data.lights.new('fill', 'AREA'); lt.shape = 'RECTANGLE'; lt.size = w - 0.4; lt.size_y = d_ - 0.4
        lt.energy = 900; lt.color = (1.0, 0.96, 0.92)
        lo = bpy.data.objects.new('fill', lt); lo.location = (cx, cy, COVE_Z - 0.05); root.objects.link(lo)
        lo.visible_camera = False; lo.visible_glossy = False
for (x0, y0, x1, y1) in ((1.0, 2.0, 9.0, 4.2), (10.0, 2.2, 19.0, 4.4), (20.0, 2.2, 28.0, 4.2), (29.0, 2.0, 37.0, 4.0),
                         (1.5, 11.0, 9.0, 11.6), (10.5, 11.4, 19.0, 11.8), (19.5, 11.2, 28.0, 11.8), (28.5, 11.2, 37.0, 11.6),
                         (2.0, 19.6, 22.0, 19.9)):
    dx, dy = x1 - x0, y1 - y0
    box(((x0 + x1) / 2, (y0 + y1) / 2, H - 0.015), (math.hypot(dx, dy), 0.045, 0.012), 'ledw', rz=math.atan2(dy, dx))

# ------------------------------------------------------------------ equipamentos no layout real
# cardio colado no vidro (frente para a rua): escadas perto da recepção, esteiras, elípticos, bikes
xs = 9.0
for k in range(2): put('stair', xs + k * 1.15, 1.35, 180)
xs += 2 * 1.15
for k in range(13):
    if abs(xs - 10.5) < 0.5 or abs(xs - 22.5) < 0.5: xs += 0.6
    put('treadmill', xs, 1.6, 180); xs += 1.12
for k in range(3): put('elliptical', xs + k * 1.0, 1.5, 180)
xs += 3.1
for k in range(4): put('bike', xs + k * 0.85, 1.2, 180)
for k in range(6): put('bike', 11.5 + k * 0.9, 3.6, 180)                                 # segunda fileira de bikes
# Movement: fileiras com corredor central livre (x 12.6-15.4)
rows = [(6.8, 0), (9.9, 180), (14.2, 0), (17.4, 180)]
for ry, rot in rows:
    for x in (5.0, 7.3, 9.6, 11.8, 16.3, 18.6, 20.9):
        if abs(x - 10.5) < 1.1 and abs(ry - 12.5) < 1.6: continue
        put(f'sel{random.randrange(3)}', x, ry, rot + random.choice((0, 0, 180)))
for y in (9.5, 14.5, 19.5): put('crossover', 1.0, y, 90)
# área de anilhas (amarelos) na borracha
for i, (x, y, r) in enumerate([(27.0, 6.4, 0), (29.6, 6.4, 0), (32.2, 6.4, 0), (34.8, 6.6, 0), (27.0, 10.2, 180), (29.8, 10.2, 180),
                               (32.6, 10.4, 180), (27.4, 14.2, 0), (30.2, 14.0, 0), (33.4, 13.8, 15)]):
    put(f'pl{i % 3}', x, y, r)
put('dbrack', L - 0.5, 10.4, 90)
for y in (6.0, 8.5, 12.5, 15.0): put('bench', 36.0, y, 90)
put('rack', 25.6, 15.4)

# ------------------------------------------------------------------ câmera (continua o clipe da fachada)
cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 22; cam_d.sensor_width = 36; cam_d.clip_start = 0.05
cam = bpy.data.objects.new('cam', cam_d); root.objects.link(cam); sc.camera = cam
KEYS = [  # frame, x, y, z, yaw (graus; + = gira para a esquerda), pitch (graus; + = olha para cima)
    (1, 18.75, -3.0, 2.05, 0, 0),
    (40, 18.75, 0.3, 1.98, 3, -3),
    (78, 18.2, 2.6, 1.75, 34, -4),
    (130, 15.4, 4.7, 1.52, 80, -3),
    (186, 12.9, 5.1, 1.45, 90, -2),
    (240, 13.4, 6.6, 1.45, 40, -1),
    (312, 14.0, 11.6, 1.45, 6, 0),
    (384, 14.0, 15.6, 1.5, 8, 1),
]
for f, x, y, z, yaw, pitch in KEYS:
    cam.location = (x, y, z); cam.rotation_euler = (math.radians(90 + pitch), 0, math.radians(yaw))
    cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)

# mundo: céu noturno azul escuro (reflexos no vidro)
w = bpy.data.worlds.new('night'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (0.006, 0.012, 0.035, 1); bg.inputs['Strength'].default_value = 1.0

# ------------------------------------------------------------------ render
sc.render.engine = 'CYCLES'
cy = sc.cycles
cy.device = 'CPU'; cy.samples = SPP; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.05
cy.use_denoising = True
try:
    cy.denoiser = 'OPENIMAGEDENOISE'; cy.denoising_input_passes = 'RGB_ALBEDO_NORMAL'; cy.denoising_prefilter = 'ACCURATE'
except Exception as e:
    print('denoise opt', e)
cy.use_light_tree = True
try:
    cy.use_fast_gi = True; cy.fast_gi_method = 'ADD'; cy.ao_bounces_render = 1
except Exception as e:
    print('fastgi', e)
cy.max_bounces = 5; cy.diffuse_bounces = 2; cy.glossy_bounces = 2; cy.transmission_bounces = 4; cy.transparent_max_bounces = 6
cy.caustics_reflective = False; cy.caustics_refractive = False; cy.sample_clamp_indirect = 4.0; cy.blur_glossy = 0.6
sc.render.resolution_x, sc.render.resolution_y = RX, RY; sc.render.resolution_percentage = 100
sc.render.threads_mode = 'FIXED'; sc.render.threads = os.cpu_count() or 2
sc.render.use_persistent_data = True
sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'; sc.render.image_settings.compression = 15
sc.view_settings.view_transform = 'AgX'
for lk in ('AgX - Punchy', 'Punchy', 'AgX - Medium High Contrast', 'Medium High Contrast'):
    try:
        sc.view_settings.look = lk; break
    except Exception:
        pass
sc.view_settings.exposure = float(arg('--exposure', 1, '0.0'))
sc.frame_start, sc.frame_end = 1, 384
print('SCENE_READY objects', len(bpy.data.objects), flush=True)
FR = [int(x) for x in arg('--list', 1, '').split(',') if x] or list(range(F0, F1 + 1, FS))
if arg('--chunk'):
    ci, cn = int(arg('--chunk')), int(arg('--nchunks', 1, '20'))
    FR = [f for f in range(1, 385) if (f - 1) % cn == ci]
for f in FR:
    p = os.path.join(OUT, f'f_{f:04d}.png')
    if os.path.exists(p):
        continue
    sc.frame_set(f); sc.render.filepath = p
    t = time.time(); bpy.ops.render.render(write_still=True)
    print(f'FRAME {f} {time.time() - t:.1f}s', flush=True)
print('DONE', flush=True)
