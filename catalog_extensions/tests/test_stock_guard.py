from unittest import TestCase

from catalog_extensions.stock_guard import _build_stock_guard_metadata


class StockGuardTestCase(TestCase):
	def test_out_of_stock_blocks_add_and_increase(self):
		result = _build_stock_guard_metadata(
			available_qty=0, current_qty=0, on_backorder=False, is_stock_item=True
		)

		self.assertEqual(result["stock_state"], "out_of_stock")
		self.assertEqual(result["stock_message"], "Out of stock")
		self.assertFalse(result["can_add_to_cart"])
		self.assertFalse(result["can_increase_qty"])

	def test_out_of_stock_preserves_existing_cart_qty_without_increase(self):
		result = _build_stock_guard_metadata(
			available_qty=0, current_qty=2, on_backorder=False, is_stock_item=True
		)

		self.assertEqual(result["max_orderable_qty"], 2)
		self.assertTrue(result["can_add_to_cart"])
		self.assertFalse(result["can_increase_qty"])

	def test_low_stock_uses_amazon_style_message(self):
		result = _build_stock_guard_metadata(
			available_qty=3, current_qty=1, on_backorder=False, is_stock_item=True
		)

		self.assertEqual(result["stock_state"], "low_stock")
		self.assertEqual(result["stock_message"], "Only 3 left in stock")
		self.assertTrue(result["can_add_to_cart"])
		self.assertTrue(result["can_increase_qty"])

	def test_backorder_stays_purchasable(self):
		result = _build_stock_guard_metadata(
			available_qty=0, current_qty=0, on_backorder=True, is_stock_item=True
		)

		self.assertEqual(result["stock_state"], "backorder")
		self.assertEqual(result["stock_message"], "Available on backorder")
		self.assertTrue(result["can_add_to_cart"])
		self.assertTrue(result["can_increase_qty"])
