"""Genera la carpeta docs que GitHub Pages publica como catálogo de clientes."""

import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from html import escape
from pathlib import Path

from plataforma import ROOT, SAVED_INVENTORY, public_catalog

PUBLIC_URL = 'https://zhulgon.github.io/Ventas_Navidad/'
EXTENSIONS = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}


def export_catalog(database, output):
    database, output = Path(database).resolve(), Path(output).resolve()
    photos = {}
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        catalog = public_catalog(db)
        for product in catalog['products']:
            product['photo'] = product['studio_photo'] or product['photo']
            for key in ('photo', 'studio_photo'):
                digest = product[key]
                if not digest:
                    continue
                if digest not in photos:
                    row = db.execute('SELECT mime, data FROM photos WHERE id=?', (digest,)).fetchone()
                    if not row or row['mime'] not in EXTENSIONS:
                        raise ValueError(f'Falta una foto válida para {product["sku"]}.')
                    photos[digest] = (digest + EXTENSIONS[row['mime']], row['data'])
                product[key] = photos[digest][0]
        db.rollback()

    output.mkdir(parents=True, exist_ok=True)
    (output / 'fotos').mkdir(exist_ok=True)
    for filename, content in photos.values():
        (output / 'fotos' / filename).write_bytes(content)
    active_photos = {filename for filename, _ in photos.values()}
    for file in (output / 'fotos').iterdir():
        if file.is_file() and re.fullmatch(r'[a-f0-9]{64}\.(jpg|png|webp)', file.name) and file.name not in active_photos:
            file.unlink()

    versions = {}
    for filename in ('app.js', 'styles.css', 'marca.svg'):
        content = (ROOT / 'web' / filename).read_bytes()
        (output / filename).write_bytes(content)
        versions[filename] = hashlib.sha256(content).hexdigest()[:12]

    index = (ROOT / 'web/index.html').read_text('utf-8')
    for filename, version in versions.items():
        index = index.replace(f'"/{filename}"', f'"./{filename}?v={version}"')
    index = index.replace('<script src=', '<script>window.COSAS_NAVIDENAS = { publicCatalog: true };</script>\n  <script src=', 1)
    index = index.replace('Catálogo e inventario de reventa de Cosas Navideñas',
                          'Descubre nuestra colección navideña: muñecos, manteles, fundas y detalles para regalar. Precios en pesos colombianos.')
    social = f'<link rel="canonical" href="{PUBLIC_URL}">\n  <meta property="og:title" content="Cosas Navideñas · Catálogo">\n  <meta property="og:description" content="Fotos, precios y detalles para decorar y regalar esta Navidad.">\n  <meta property="og:type" content="website">\n  <meta property="og:url" content="{PUBLIC_URL}">'
    cover = next((p for p in catalog['products'] if p['sku'] == 'GN-TRIO'), None)
    if cover and (cover['studio_photo'] or cover['photo']):
        social += f'\n  <meta property="og:image" content="{PUBLIC_URL}fotos/{escape(cover["studio_photo"] or cover["photo"], quote=True)}">'
    index = index.replace('</head>', '  ' + social + '\n</head>')
    (output / 'index.html').write_text(index, encoding='utf-8')
    (output / 'catalogo.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / '.nojekyll').touch()
    return len(catalog['products']), len(photos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs')
    args = parser.parse_args()
    local = ROOT / '.datos/reventa.sqlite3'
    database = args.database or (local if local.is_file() else SAVED_INVENTORY)
    products, photos = export_catalog(database, args.output)
    print(f'Catálogo listo: {products} artículos y {photos} fotos en {args.output}.')


if __name__ == '__main__':
    main()
