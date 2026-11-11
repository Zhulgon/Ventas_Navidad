import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import plataforma
from exportar_catalogo import export_catalog


class PublicCatalogTests(unittest.TestCase):
    def test_export_only_includes_customer_data_and_visible_products(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / 'inventory.sqlite3'
            output = Path(folder) / 'website'
            with closing(sqlite3.connect(database)) as db:
                db.executescript(plataforma.SCHEMA)
                photo = hashlib.sha256(b'photo').hexdigest()
                db.execute('INSERT INTO photos VALUES (?,?,?)', (photo, 'image/webp', b'photo'))
                studio = hashlib.sha256(b'studio').hexdigest()
                db.execute('INSERT INTO photos VALUES (?,?,?)', (studio, 'image/webp', b'studio'))
                for sku, category, published, price in [('PUBLIC', 'Muñecos', 1, 10000),
                                                        ('DRAFT', 'Muñecos', 0, 10000),
                                                        ('ARCHIVED', 'Empaque', 1, 10000),
                                                        ('RETIRED', 'Muñecos', 1, 10000),
                                                        ('NO-PRICE', 'Muñecos', 1, None)]:
                    db.execute('INSERT INTO products (sku,name,category,bought,pieces,dimensions,variant,price,cost,photo,published,source) '
                               'VALUES (?,?,?,1,1,?,?,?,1234,?,?,?)',
                               (sku, sku, category, '', '', price, photo, published, 'private-import-data'))
                db.execute("INSERT INTO retired_products VALUES ('RETIRED','replaced')")
                db.execute("INSERT INTO studio_photos VALUES ('PUBLIC',?,?)", (photo, studio))
                db.execute("INSERT INTO sales (sku,name,qty,price,cost,buyer,note,created) VALUES ('PUBLIC','PUBLIC',1,10000,1234,'private-buyer','private-note','2026-11-11')")
                db.commit()
            before = database.read_bytes()
            self.assertEqual(export_catalog(database, output), (1, 1))
            catalog = json.loads((output / 'catalogo.json').read_text('utf-8'))
            self.assertEqual([p['sku'] for p in catalog['products']], ['PUBLIC'])
            product = catalog['products'][0]
            self.assertEqual(product['stock'], 0)
            self.assertEqual((output / 'fotos' / product['photo']).read_bytes(), b'studio')
            self.assertFalse((output / 'fotos' / (photo + '.webp')).exists())
            self.assertTrue({'cost', 'source', 'buyer', 'note', 'sales', 'bought', 'adjustment'}.isdisjoint(product))
            self.assertEqual(database.read_bytes(), before)
            self.assertFalse(list(output.rglob('*.sqlite3')))
            html = (output / 'index.html').read_text('utf-8')
            self.assertIn('publicCatalog: true', html)
            self.assertIn('src="./app.js?v=', html)
            self.assertNotIn('src="/app.js"', html)


if __name__ == '__main__':
    unittest.main()
