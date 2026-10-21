"""Baixa as fontes abertas (pacotes Fontsource no npm, licença OFL) e converte woff2 -> ttf para o Blender."""
import os, io, json, tarfile, urllib.request
from fontTools.ttLib import TTFont

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts'); os.makedirs(D, exist_ok=True)
WANT = {
    '@fontsource/big-shoulders-display': ['big-shoulders-display-latin-900-normal'],
    '@fontsource/archivo': ['archivo-latin-700-normal', 'archivo-latin-500-normal'],
}
for pkg, names in WANT.items():
    if all(os.path.exists(os.path.join(D, n + '.ttf')) for n in names):
        continue
    meta = json.load(urllib.request.urlopen('https://registry.npmjs.org/' + pkg.replace('/', '%2f')))
    ver = meta['dist-tags']['latest']
    tgz = urllib.request.urlopen(meta['versions'][ver]['dist']['tarball']).read()
    with tarfile.open(fileobj=io.BytesIO(tgz), mode='r:gz') as tf:
        for n in names:
            data = tf.extractfile('package/files/' + n + '.woff2').read()
            w = os.path.join(D, n + '.woff2'); t = os.path.join(D, n + '.ttf')
            open(w, 'wb').write(data)
            f = TTFont(w); f.flavor = None; f.save(t)
            print('font', pkg, ver, n, os.path.getsize(t))
