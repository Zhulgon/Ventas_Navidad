import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import plataforma


class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(plataforma.SCHEMA)
        self.product = dict(sku='BLUE', editing=False, name='Conjunto azul', category='Figuras',
                            total=0, pieces=2, dimensions='', variant='', price=45000, cost=None,
                            photo='', published=True, availability_status='in_production',
                            incoming=3, expected_on='2026-11-29')

    def tearDown(self):
        self.db.close()

    def test_incoming_products_are_public_but_cannot_be_sold_as_stock(self):
        plataforma.save_product(self.db, self.product)
        product, = plataforma.public_catalog(self.db)['products']
        self.assertEqual(product['stock'], 0)
        self.assertEqual(product['availability'], dict(status='in_production', incoming=3, expected_on='2026-11-29'))
        with self.assertRaises(ValueError):
            plataforma.record_sale(self.db, dict(sku='BLUE', qty=1, price=45000))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM sales').fetchone()[0], 0)

        plataforma.save_product(self.db, dict(self.product, editing=True, total=3, availability_status=''))
        product, = plataforma.public_catalog(self.db)['products']
        self.assertEqual(product['stock'], 3)
        self.assertNotIn('availability', product)

    def test_invalid_availability_does_not_create_an_article(self):
        for changes in (dict(incoming=-1), dict(expected_on='2026-02-30'), dict(availability_status='unknown')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                plataforma.save_product(self.db, dict(self.product, **changes))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_saved_inventory_restores_production_details(self):
        plataforma.save_product(self.db, self.product)
        with tempfile.TemporaryDirectory() as folder:
            saved_path = Path(folder) / 'saved.sqlite3'
            with closing(sqlite3.connect(saved_path)) as saved:
                self.db.commit()
                self.db.backup(saved)
            previous = plataforma.SAVED_INVENTORY
            plataforma.SAVED_INVENTORY = saved_path
            try:
                with closing(sqlite3.connect(':memory:')) as restored:
                    restored.row_factory = sqlite3.Row
                    restored.executescript(plataforma.SCHEMA)
                    self.assertTrue(plataforma.restore_saved_inventory(restored))
                    product, = plataforma.public_catalog(restored)['products']
                    self.assertEqual(product['availability']['incoming'], 3)
                    self.assertEqual(product['stock'], 0)
            finally:
                plataforma.SAVED_INVENTORY = previous


if __name__ == '__main__':
    unittest.main()
