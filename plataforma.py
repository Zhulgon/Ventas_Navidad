import argparse
import errno
import hashlib
import json
import mimetypes
import re
import sqlite3
import webbrowser
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from inventario_xlsx import MAX_UPLOAD, image_type, number, read_inventory

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
DATABASE = ROOT / '.datos' / 'reventa.sqlite3'
DEFAULT_EXCEL = Path.home() / 'Desktop' / 'Inventario_Temu_Precios_Colombia.xlsx'
SAVED_INVENTORY = ROOT / 'datos' / 'inventario-inicial.sqlite3'
if not DEFAULT_EXCEL.is_file():
    DEFAULT_EXCEL = ROOT / 'datos' / 'fuentes' / 'Inventario_Temu_Precios_Colombia.xlsx'
STUDIO_DIR = ROOT / 'fotos-estudio'
EDITABLE = ('name', 'category', 'pieces', 'dimensions', 'variant', 'price', 'cost', 'photo')
FIELDS = ', '.join(EDITABLE)
ARCHIVED_CATEGORIES = ('manualidades', 'empaque')
ACTIVE_CATEGORY = 'lower(trim(i.category)) NOT IN (?, ?)'
ACTIVE_PRODUCT = ACTIVE_CATEGORY + ' AND i.sku NOT IN (SELECT sku FROM retired_products)'
STUDIO_INVENTORY = (' FROM inventory i LEFT JOIN studio_photos s '
                    'ON s.sku=i.sku AND s.original=i.photo')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS photos (id TEXT PRIMARY KEY, mime TEXT NOT NULL, data BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
    bought INTEGER NOT NULL DEFAULT 0, adjustment INTEGER NOT NULL DEFAULT 0,
    pieces INTEGER NOT NULL CHECK (pieces > 0), dimensions TEXT NOT NULL, variant TEXT NOT NULL,
    price INTEGER, cost INTEGER, photo TEXT REFERENCES photos(id),
    published INTEGER NOT NULL DEFAULT 0, source TEXT
);
CREATE TABLE IF NOT EXISTS studio_photos (
    sku TEXT NOT NULL REFERENCES products(sku),
    original TEXT NOT NULL REFERENCES photos(id),
    photo TEXT NOT NULL REFERENCES photos(id),
    PRIMARY KEY (sku, original)
);
CREATE TABLE IF NOT EXISTS retired_products (
    sku TEXT PRIMARY KEY REFERENCES products(sku), note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY, sku TEXT NOT NULL REFERENCES products(sku), name TEXT NOT NULL,
    qty INTEGER NOT NULL CHECK (qty > 0), price INTEGER NOT NULL CHECK (price > 0),
    cost INTEGER, buyer TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL, voided TEXT
);
CREATE TABLE IF NOT EXISTS bundle_components (
    bundle_sku TEXT NOT NULL REFERENCES products(sku),
    component_sku TEXT NOT NULL REFERENCES products(sku),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (bundle_sku, component_sku),
    CHECK (bundle_sku <> component_sku)
);
CREATE TABLE IF NOT EXISTS sale_components (
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    sku TEXT NOT NULL REFERENCES products(sku),
    qty INTEGER NOT NULL CHECK (qty > 0),
    cost REAL,
    PRIMARY KEY (sale_id, sku)
);
CREATE INDEX IF NOT EXISTS sales_sku ON sales(sku, voided);
CREATE INDEX IF NOT EXISTS sale_components_sku ON sale_components(sku);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
DROP VIEW IF EXISTS inventory;
DROP VIEW IF EXISTS inventory_units;
CREATE VIEW inventory_units AS
    WITH movements AS (
        SELECT sku, qty FROM sales WHERE voided IS NULL
        UNION ALL
        SELECT c.sku, c.qty FROM sale_components c JOIN sales s ON s.id=c.sale_id WHERE s.voided IS NULL
    ), sold AS (
        SELECT sku, SUM(qty) AS qty FROM movements GROUP BY sku
    )
    SELECT p.*, bought + adjustment AS total, COALESCE(s.qty, 0) AS sold,
           bought + adjustment - COALESCE(s.qty, 0) AS stock
    FROM products p LEFT JOIN sold s ON s.sku=p.sku;
CREATE VIEW inventory AS
    WITH bundles AS (
        SELECT c.bundle_sku,
               MIN(CASE WHEN i.sku IN (SELECT sku FROM retired_products) THEN 0
                        ELSE MAX(0, CAST(i.stock / c.quantity AS INTEGER)) END) AS stock,
               CASE WHEN COUNT(i.cost)=COUNT(*) THEN SUM(i.cost*c.quantity) END AS cost
        FROM bundle_components c JOIN inventory_units i ON i.sku=c.component_sku
        GROUP BY c.bundle_sku
    )
    SELECT i.sku, i.name, i.category, i.bought, i.adjustment, i.pieces, i.dimensions, i.variant, i.price,
           CASE WHEN b.bundle_sku IS NULL THEN i.cost ELSE b.cost END AS cost,
           i.photo, i.published, i.source,
           CASE WHEN b.bundle_sku IS NULL THEN i.total ELSE b.stock+i.sold END AS total,
           i.sold, COALESCE(b.stock, i.stock) AS stock,
           b.bundle_sku IS NOT NULL AS is_bundle
    FROM inventory_units i LEFT JOIN bundles b ON b.bundle_sku=i.sku;
'''


@contextmanager
def database(write=False):
    db = sqlite3.connect(DATABASE, timeout=12)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def photo_id(db, photo, write):
    if photo is None:
        return None
    mime = image_type(photo)
    if not mime:
        raise ValueError('Usa una foto JPG, PNG o WebP de hasta 2 MB.')
    digest = hashlib.sha256(photo).hexdigest()
    if write:
        db.execute('INSERT OR IGNORE INTO photos VALUES (?, ?, ?)', (digest, mime, photo))
    return digest


def restore_saved_inventory(db):
    if not SAVED_INVENTORY.is_file() or db.execute('SELECT 1 FROM products LIMIT 1').fetchone():
        return False
    db.execute('ATTACH DATABASE ? AS saved', (str(SAVED_INVENTORY),))
    for table in ('photos', 'products', 'studio_photos', 'retired_products', 'sales',
                  'bundle_components', 'sale_components', 'settings'):
        db.execute(f'INSERT INTO main.{table} SELECT * FROM saved.{table}')
    return True


def install_studio(db):
    entries = json.loads((STUDIO_DIR / 'manifest.json').read_text(encoding='utf-8'))['photos']
    applied = 0
    for entry in entries:
        sku = entry['sku']
        current = db.execute('SELECT photo FROM products WHERE sku=?', (sku,)).fetchone()
        if not current or current['photo'] != entry['original']:
            continue
        digest = photo_id(db, (STUDIO_DIR / f'{sku}.webp').read_bytes(), True)
        db.execute('INSERT INTO studio_photos VALUES (?,?,?) '
                   'ON CONFLICT(sku, original) DO UPDATE SET photo=excluded.photo',
                   (sku, current['photo'], digest))
        applied += 1
    return applied, len(entries) - applied


def import_products(db, data, write=False):
    results = dict(added=0, updated=0, unchanged=0, rows=[])
    for row in read_inventory(data):
        sku = row.pop('sku')
        row['photo'] = photo_id(db, row['photo'], write)
        old = db.execute('SELECT * FROM inventory WHERE sku=?', (sku,)).fetchone()
        previous = json.loads(old['source']) if old and old['source'] else None
        if old and previous is None:
            raise ValueError(f'El ID {sku} ya existe como artículo manual. Usa otro ID en el Excel para esa fila.')
        if previous == row:
            results['unchanged'] += 1
            continue
        label = 'updated' if old else 'added'
        results[label] += 1
        results['rows'].append(dict(sku=sku, name=row['name'], status=label))
        if not old:
            if write:
                db.execute(f'INSERT INTO products (sku, bought, source, {FIELDS}) VALUES (?,?,?,{",".join("?" for _ in EDITABLE)})',
                           (sku, row['bought'], json.dumps(row), *(row[k] for k in EDITABLE)))
            continue
        if row['bought'] + old['adjustment'] < old['sold']:
            raise ValueError(f'La cantidad de {sku} dejaría el stock negativo. Revisa los juegos comprados y las ventas.')
        merged = {key: row[key] if row[key] != previous[key] else old[key] for key in EDITABLE}
        published = bool(old['published'] and merged['price'])
        if write:
            db.execute(f'UPDATE products SET bought=?, source=?, published=?, {", ".join(k + "=?" for k in EDITABLE)} WHERE sku=?',
                       (row['bought'], json.dumps(row), published, *merged.values(), sku))
    return results


def field(data, key, label, limit=200, required=False):
    value = data.get(key, '')
    if not isinstance(value, str) or len(value.strip()) > limit or (required and not value.strip()):
        raise ValueError(f'{label}: escribe un texto válido de hasta {limit} caracteres.')
    return value.strip()


def save_product(db, data):
    sku = field(data, 'sku', 'Código', 40, True).upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9_.-]{0,39}', sku):
        raise ValueError('Usa letras, números, guion, punto o guion bajo en el código.')
    old = db.execute('SELECT * FROM inventory WHERE sku=?', (sku,)).fetchone()
    if bool(old) != (data.get('editing') is True):
        raise ValueError('El código ya existe o el artículo cambió. Actualiza la página e inténtalo de nuevo.')
    total = number(data.get('total'), 'Juegos registrados')
    pieces = number(data.get('pieces'), 'Piezas por juego', minimum=1)
    bundle = bool(old and old['is_bundle'])
    if bundle and (total != old['total'] or pieces != old['pieces']):
        raise ValueError('Las cantidades del juego se calculan a partir de sus unidades individuales.')
    if old and total < old['sold']:
        raise ValueError('Los juegos registrados deben cubrir los que ya vendiste.')
    price = number(data.get('price'), 'Precio por juego', minimum=1, optional=True)
    published = data.get('published') is True
    if published and price is None:
        raise ValueError('Define el precio de venta para mostrar el artículo en el catálogo.')
    photo = field(data, 'photo', 'Foto', 64) or None
    if photo and not db.execute('SELECT 1 FROM photos WHERE id=?', (photo,)).fetchone():
        raise ValueError('Vuelve a cargar la foto.')
    category = field(data, 'category', 'Categoría', 60, True)
    if category.lower() in ARCHIVED_CATEGORIES:
        raise ValueError('Esta categoría está archivada. Elige una categoría activa.')
    cost = None if bundle else number(data.get('cost'), 'Costo por juego', optional=True, integer=False)
    fields = (field(data, 'name', 'Nombre', 200, True), category, pieces, field(data, 'dimensions', 'Medidas'),
              field(data, 'variant', 'Variante'), price, cost, photo)
    adjustment = old['adjustment'] if bundle else total - (old['bought'] if old else 0)
    if old:
        db.execute(f'UPDATE products SET adjustment=?, published=?, {", ".join(k + "=?" for k in EDITABLE)} WHERE sku=?',
                   (adjustment, published, *fields, sku))
    else:
        db.execute(f'INSERT INTO products (sku, adjustment, published, {FIELDS}) VALUES (?,?,?,{",".join("?" for _ in EDITABLE)})',
                   (sku, adjustment, published, *fields))


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def record_sale(db, data):
    product = db.execute('SELECT * FROM inventory i WHERE sku=? AND ' + ACTIVE_PRODUCT,
                         (field(data, 'sku', 'Código'), *ARCHIVED_CATEGORIES)).fetchone()
    qty = number(data.get('qty'), 'Cantidad', minimum=1)
    if not product or qty > product['stock']:
        raise ValueError('La cantidad supera las existencias actuales.')
    price = number(data.get('price'), 'Precio de la venta', minimum=1)
    sale = db.execute('INSERT INTO sales (sku,name,qty,price,cost,buyer,note,created) VALUES (?,?,?,?,?,?,?,?)',
                      (product['sku'], product['name'], qty, price, product['cost'],
                       field(data, 'buyer', 'Cliente', 100), field(data, 'note', 'Nota', 400), timestamp()))
    components = db.execute('SELECT c.component_sku, c.quantity, i.cost FROM bundle_components c '
                            'JOIN inventory_units i ON i.sku=c.component_sku WHERE c.bundle_sku=?',
                            (product['sku'],)).fetchall()
    db.executemany('INSERT INTO sale_components (sale_id,sku,qty,cost) VALUES (?,?,?,?)',
                   [(sale.lastrowid, c['component_sku'], qty*c['quantity'], c['cost']) for c in components])


def product_components(db, products):
    components = {}
    for row in db.execute('SELECT c.bundle_sku, c.component_sku, c.quantity, MAX(0,i.stock) AS stock '
                          'FROM bundle_components c JOIN inventory_units i ON i.sku=c.component_sku '
                          'ORDER BY c.component_sku'):
        components.setdefault(row['bundle_sku'], []).append(dict(sku=row['component_sku'], quantity=row['quantity'], stock=row['stock']))
    return [dict(product, components=components.get(product['sku'], [])) for product in products]


class Server(ThreadingHTTPServer):
    request_queue_size = 64


class App(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'CosasNavidenas/1.0'

    def send_data(self, status, data, mime, cache='no-store'):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def send_json(self, data, status=200):
        self.send_data(status, json.dumps(data, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def allowed_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.allowed_host():
            self.send_json(dict(error='Abre la dirección local que muestra la plataforma.'), 403)
            return
        url = urlsplit(self.path)
        if url.path in ('/', '/catalogo', '/app.js', '/styles.css', '/marca.svg'):
            name = 'index.html' if url.path in ('/', '/catalogo') else url.path[1:]
            mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            self.send_data(200, (WEB / name).read_bytes(), mime)
            return
        if url.path in ('/api/admin', '/api/catalogo'):
            with database() as db:
                contact = db.execute("SELECT value FROM settings WHERE key='whatsapp'").fetchone()
                if url.path == '/api/admin':
                    products = db.execute('SELECT i.sku, total, stock, sold, published, is_bundle, ' +
                                          ', '.join('i.' + key for key in EDITABLE) + ', s.photo AS studio_photo' +
                                          STUDIO_INVENTORY + ' WHERE ' + ACTIVE_PRODUCT + ' ORDER BY i.sku',
                                          ARCHIVED_CATEGORIES)
                    sales = db.execute('SELECT * FROM sales ORDER BY id DESC')
                    result = dict(products=product_components(db, products.fetchall()), sales=[dict(row) for row in sales])
                else:
                    products = db.execute('SELECT i.sku, name, category, pieces, dimensions, variant, price, '
                                          'i.photo, s.photo AS studio_photo, stock, is_bundle' + STUDIO_INVENTORY +
                                          ' WHERE published=1 AND price>0 AND ' + ACTIVE_PRODUCT + ' ORDER BY i.sku',
                                          ARCHIVED_CATEGORIES)
                    result = dict(products=product_components(db, products.fetchall()))
            self.send_json(dict(**result, whatsapp=contact['value'] if contact else ''))
            return
        if re.fullmatch(r'/foto/[a-f0-9]{64}', url.path):
            with database() as db:
                photo = db.execute('SELECT mime, data FROM photos WHERE id=?', (url.path[6:],)).fetchone()
            if photo:
                self.send_data(200, photo['data'], photo['mime'], 'private, max-age=604800, immutable')
                return
        self.send_json(dict(error='Página no encontrada.'), 404)

    def do_POST(self):
        origin = f'http://127.0.0.1:{self.server.server_port}'
        if not self.allowed_host() or self.headers.get('Origin') != origin:
            self.close_connection = True
            self.send_json(dict(error='Solicitud fuera de la aplicación local.'), 403)
            return
        url = urlsplit(self.path)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_UPLOAD:
                self.close_connection = True
                raise ValueError('El archivo o la solicitud está vacío o supera los 16 MB.')
            raw = self.rfile.read(length)
            if url.path == '/api/importar':
                write = parse_qs(url.query).get('aplicar') == ['1']
                with database(write) as db:
                    result = import_products(db, raw, write)
                self.send_json(result)
                return
            if url.path == '/api/foto':
                with database(True) as db:
                    digest = photo_id(db, raw, True)
                self.send_json(dict(photo=digest))
                return
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('La solicitud debe contener los datos del formulario.')
            with database(True) as db:
                if url.path == '/api/producto':
                    save_product(db, data)
                elif url.path == '/api/venta':
                    record_sale(db, data)
                elif url.path == '/api/anular':
                    changed = db.execute('UPDATE sales SET voided=? WHERE id=? AND voided IS NULL',
                                         (timestamp(), number(data.get('id'), 'Venta', minimum=1)))
                    if not changed.rowcount:
                        raise ValueError('La venta ya se anuló o no existe.')
                elif url.path == '/api/contacto':
                    value = field(data, 'whatsapp', 'WhatsApp', 15)
                    if value and not re.fullmatch(r'[1-9]\d{7,14}', value):
                        raise ValueError('Escribe el código de país y el número, solo con dígitos.')
                    db.execute("INSERT OR REPLACE INTO settings VALUES ('whatsapp', ?)", (value,))
                else:
                    self.send_json(dict(error='Acción no encontrada.'), 404)
                    return
            self.send_json(dict(ok=True))
        except (ValueError, UnicodeError) as error:
            self.send_json(dict(error=str(error)), 400)
        except sqlite3.Error as error:
            self.log_error('SQLite: %s', error)
            self.send_json(dict(error='La base de datos está ocupada o no pudo guardar. Inténtalo de nuevo.'), 503)


def main():
    global DATABASE
    parser = argparse.ArgumentParser(description='Cosas Navideñas · plataforma local de reventa')
    parser.add_argument('--port', type=int, default=8131)
    parser.add_argument('--database', type=Path, default=DATABASE)
    parser.add_argument('--excel', type=Path)
    parser.add_argument('--importar', action='store_true', help='Importa el Excel indicado y termina.')
    parser.add_argument('--fotos', action='store_true', help='Aplica el lote de fotos de estudio y termina.')
    parser.add_argument('--abrir', action='store_true', help='Abre la plataforma en el navegador.')
    args = parser.parse_args()
    DATABASE = args.database
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.executescript('BEGIN IMMEDIATE;\n' + SCHEMA + '\nCOMMIT;')
    with database(True) as db:
        restored = restore_saved_inventory(db) if args.excel is None else False
        empty = not db.execute('SELECT 1 FROM products LIMIT 1').fetchone()
    if restored:
        print('Inventario guardado del proyecto restaurado en la base local.', flush=True)
    excel = args.excel or DEFAULT_EXCEL
    if args.importar or (empty and excel.is_file()):
        try:
            with database(True) as db:
                with excel.open('rb') as workbook:
                    results = import_products(db, workbook.read(MAX_UPLOAD + 1), True)
            print('Excel:', {key: results[key] for key in ('added', 'updated', 'unchanged')}, flush=True)
        except (ValueError, OSError) as error:
            if args.importar:
                parser.exit(1, f'{error}\n')
            print(f'Importación inicial: {error}', flush=True)
    if args.fotos or (empty and (STUDIO_DIR / 'manifest.json').is_file()):
        try:
            with database(True) as db:
                applied, skipped = install_studio(db)
            print(f'Estudio: {applied} aplicadas, {skipped} sin coincidencia de referencia.', flush=True)
        except (ValueError, OSError, KeyError) as error:
            if args.fotos:
                parser.exit(1, f'{error}\n')
            print(f'Fotos de estudio: {error}', flush=True)
    if args.importar or args.fotos:
        return
    try:
        server = Server(('127.0.0.1', args.port), App)
    except OSError as error:
        if not args.abrir or error.errno not in (errno.EADDRINUSE, 10048):
            raise
        url = f'http://127.0.0.1:{args.port}'
        with urlopen(url, timeout=3) as running:
            if not running.headers.get('Server', '').startswith(App.server_version):
                raise error
        webbrowser.open(url)
        return
    with server:
        url = f'http://127.0.0.1:{server.server_port}'
        print(f'Cosas Navideñas está disponible en {url}', flush=True)
        if args.abrir:
            Timer(.3, webbrowser.open, args=[url]).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
