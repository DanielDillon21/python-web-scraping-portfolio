"""
Tests for parsing and alert logic, using a saved HTML fixture so they run
offline and prove the alerts fire even when the live site's prices don't move.

Run:
    python -m unittest -v
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import price_monitor as pm

PAGE = """
<div class="product_main">
  <h1>Test Book</h1>
  <p class="price_color">£{price}</p>
  <p class="instock availability">{stock_text}</p>
</div>
"""


def page(price, stock):
    stock_text = f"In stock ({stock} available)" if stock else "Out of stock"
    return PAGE.format(price=price, stock_text=stock_text)


def events(previous, current, target=None):
    return [name for name, _ in pm.detect_events(previous, current, target)]


class ParseProductTests(unittest.TestCase):
    def test_parses_price_and_stock(self):
        self.assertEqual(pm.parse_product(page("51.77", 22)), {"title": "Test Book", "price": 51.77, "stock": 22})

    def test_out_of_stock_is_zero(self):
        self.assertEqual(pm.parse_product(page("10.00", 0))["stock"], 0)

    def test_missing_fields_do_not_crash(self):
        self.assertEqual(pm.parse_product("<html></html>"), {"title": None, "price": None, "stock": 0})


class DetectEventsTests(unittest.TestCase):
    def test_first_check_has_no_change_events(self):
        self.assertEqual(events(None, {"price": 20.0, "stock": 10}), [])

    def test_price_drop_and_increase(self):
        self.assertEqual(events({"price": 20.0, "stock": 10}, {"price": 18.5, "stock": 10}), ["PRICE_DROP"])
        self.assertEqual(events({"price": 20.0, "stock": 10}, {"price": 21.0, "stock": 10}), ["PRICE_INCREASE"])

    def test_unchanged_price_is_quiet(self):
        self.assertEqual(events({"price": 20.0, "stock": 10}, {"price": 20.0, "stock": 10}), [])

    def test_below_target(self):
        self.assertIn("BELOW_TARGET", events(None, {"price": 15.0, "stock": 10}, target=15.0))
        self.assertNotIn("BELOW_TARGET", events(None, {"price": 15.01, "stock": 10}, target=15.0))

    def test_stock_transitions(self):
        self.assertIn("BACK_IN_STOCK", events({"price": 20.0, "stock": 0}, {"price": 20.0, "stock": 4}))
        self.assertIn("OUT_OF_STOCK", events({"price": 20.0, "stock": 4}, {"price": 20.0, "stock": 0}))
        self.assertIn("LOW_STOCK", events(None, {"price": 20.0, "stock": 2}))


class HistoryTests(unittest.TestCase):
    def test_last_snapshot_returns_most_recent(self):
        with TemporaryDirectory() as tmp:
            conn = pm.connect(Path(tmp) / "test.db")
            pm.save_snapshot(conn, "2026-10-01T00:00:00+00:00", "u", {"title": "t", "price": 20.0, "stock": 5})
            pm.save_snapshot(conn, "2026-10-02T00:00:00+00:00", "u", {"title": "t", "price": 17.0, "stock": 0})
            self.assertEqual(pm.last_snapshot(conn, "u"), {"price": 17.0, "stock": 0})
            self.assertIsNone(pm.last_snapshot(conn, "other"))
            conn.close()


if __name__ == "__main__":
    unittest.main()
