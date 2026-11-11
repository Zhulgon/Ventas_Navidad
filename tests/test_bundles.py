import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import plataforma


class SharedBundleStockTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.previous_database = plataforma.DATABASE
        plataforma.DATABASE = Path(self.directory.name) / 'inventory.sqlite3'
        with plataforma.database() as db:
            db.executescript('BEGIN IMMEDIATE;\n' + plataforma.SCHEMA + '\nCOMMIT;')
        with plataforma.database(True) as db:
            for sku, qty, cost in [('GOLD', 4, 1000.5), ('GRAY', 3, 2000), ('RED', 3, 3000)]:
                self.add_product(db, sku, qty, cost)
            self.add_product(db, 'TRIO', 0, None, pieces=3, price=25000)
            db.executemany('INSERT INTO bundle_components VALUES (?,?,?)',
                           [('TRIO', sku, 1) for sku in ('GOLD', 'GRAY', 'RED')])

    def tearDown(self):
        plataforma.DATABASE = self.previous_database
        self.directory.cleanup()

    @staticmethod
    def add_product(db, sku, qty, cost, pieces=1, price=10000):
        plataforma.save_product(db, dict(sku=sku, editing=False, name=sku, category='Muñecos', total=qty,
                                        pieces=pieces, dimensions='', variant='', price=price, cost=cost,
                                        photo='', published=True))

    @staticmethod
    def sell(sku, qty):
        with plataforma.database(True) as db:
            plataforma.record_sale(db, dict(sku=sku, qty=qty, price=25000 if sku == 'TRIO' else 10000,
                                           buyer='', note=''))
            return db.execute('SELECT MAX(id) FROM sales').fetchone()[0]

    @staticmethod
    def stocks():
        with plataforma.database() as db:
            return {row['sku']: row['stock'] for row in db.execute('SELECT sku, stock FROM inventory')}

    def test_bundle_sale_consumes_each_unit_and_snapshots_cost(self):
        sale_id = self.sell('TRIO', 1)
        self.assertEqual(self.stocks(), {'GOLD': 3, 'GRAY': 2, 'RED': 2, 'TRIO': 2})
        with plataforma.database() as db:
            sale = db.execute('SELECT * FROM sales WHERE id=?', (sale_id,)).fetchone()
            self.assertEqual(sale['cost'], 6000.5)
            self.assertEqual(sale['price'], 25000)
            self.assertEqual(db.execute('SELECT SUM(qty) FROM sale_components WHERE sale_id=?', (sale_id,)).fetchone()[0], 3)

    def test_single_sale_limits_bundle_availability_and_prevents_overselling(self):
        self.sell('RED', 1)
        self.assertEqual(self.stocks()['TRIO'], 2)
        with self.assertRaises(ValueError):
            self.sell('TRIO', 3)
        self.sell('TRIO', 2)
        self.assertEqual(self.stocks(), {'GOLD': 2, 'GRAY': 1, 'RED': 0, 'TRIO': 0})
        with self.assertRaises(ValueError):
            self.sell('RED', 1)

    def test_void_restores_original_components_after_composition_changes(self):
        sale_id = self.sell('TRIO', 1)
        with plataforma.database(True) as db:
            db.execute("UPDATE bundle_components SET quantity=2 WHERE bundle_sku='TRIO' AND component_sku='GOLD'")
            db.execute('UPDATE sales SET voided=? WHERE id=?', (plataforma.timestamp(), sale_id))
        self.assertEqual(self.stocks(), {'GOLD': 4, 'GRAY': 3, 'RED': 3, 'TRIO': 2})

    def test_concurrent_bundle_and_single_sales_share_one_limit(self):
        start = threading.Barrier(2)

        def try_sale(sku, qty):
            start.wait(timeout=5)
            try:
                self.sell(sku, qty)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(try_sale, 'TRIO', 3), pool.submit(try_sale, 'RED', 1)]
            self.assertEqual(sum(future.result() for future in futures), 1)
        self.assertTrue(all(stock >= 0 for stock in self.stocks().values()))

    def test_existing_individual_sales_survive_schema_refresh(self):
        self.sell('GOLD', 1)
        with plataforma.database() as db:
            db.executescript('BEGIN IMMEDIATE;\n' + plataforma.SCHEMA + '\nCOMMIT;')
        self.assertEqual(self.stocks(), {'GOLD': 3, 'GRAY': 3, 'RED': 3, 'TRIO': 3})

    def test_bundle_quantity_cannot_be_overridden_in_product_editor(self):
        with plataforma.database(True) as db:
            product = dict(db.execute("SELECT * FROM inventory WHERE sku='TRIO'").fetchone())
            product.update(editing=True, total=100, photo='')
            with self.assertRaises(ValueError):
                plataforma.save_product(db, product)


if __name__ == '__main__':
    unittest.main()
