import unittest

from services.formatting import format_brl
from ui.helpers import money_br


class FormatBrlTests(unittest.TestCase):
    def test_positive_and_thousands(self):
        self.assertEqual(format_brl(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(format_brl(0), "R$ 0,00")
        self.assertEqual(format_brl(None), "R$ 0,00")

    def test_sign_comes_before_currency(self):
        self.assertEqual(format_brl(-8140.36), "-R$ 8.140,36")

    def test_tiny_negative_rounds_to_zero_without_sign(self):
        self.assertEqual(format_brl(-0.004), "R$ 0,00")

    def test_money_br_keeps_dash_for_missing_value(self):
        self.assertEqual(money_br(None), "—")
        self.assertEqual(money_br(-5), "-R$ 5,00")


if __name__ == "__main__":
    unittest.main()
