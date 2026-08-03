import unittest
from datetime import datetime, timedelta, timezone

from stock import (
    INITIAL_CAPITAL,
    cash_balance,
    create_candidate,
    JAPANESE_STOCK_CODE_PATTERN,
    normalize_input,
    normalize_stock_code,
    reset_portfolio,
    set_share_count,
    should_refresh_dividend,
)


class NormalizeInputTest(unittest.TestCase):
    def test_normalizes_full_width_alphanumeric_stock_code(self):
        self.assertEqual(normalize_input("２８５ａ").strip().upper(), "285A")

    def test_normalizes_stock_code_to_half_width_uppercase(self):
        self.assertEqual(normalize_stock_code(" ９ａ７ａ "), "9A7A")

    def test_accepts_all_jpx_alphanumeric_code_positions(self):
        for code in ("130A", "987A", "9A76", "9A7A", "285A", "7203"):
            with self.subTest(code=code):
                self.assertIsNotNone(JAPANESE_STOCK_CODE_PATTERN.fullmatch(code))

    def test_rejects_letters_in_invalid_positions_or_excluded_letters(self):
        for code in ("A123", "12A3", "1B23", "123E", "AAPL"):
            with self.subTest(code=code):
                self.assertIsNone(JAPANESE_STOCK_CODE_PATTERN.fullmatch(code))


class CashBalanceTest(unittest.TestCase):
    def test_initial_balance_without_transactions(self):
        self.assertEqual(cash_balance([]), INITIAL_CAPITAL)

    def test_purchases_and_sales_change_cash_balance(self):
        stocks = [
            {
                "transactions": [
                    {"type": "buy", "shares": 100, "price": 1_000},
                    {"type": "sell", "shares": 20, "price": 1_200},
                ]
            },
            {"transactions": [{"type": "buy", "shares": 10, "price": 2_000}]},
        ]

        self.assertEqual(cash_balance(stocks), INITIAL_CAPITAL - 100_000 + 24_000 - 20_000)


class DividendRefreshTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)

    def test_refreshes_when_yield_was_not_obtained(self):
        self.assertTrue(
            should_refresh_dividend({"dividend_yield": None}, now=self.now)
        )

    def test_refreshes_when_last_update_is_old(self):
        stock = {
            "dividend_yield": 2.5,
            "dividend_updated_at": (self.now - timedelta(hours=25)).isoformat(),
        }

        self.assertTrue(should_refresh_dividend(stock, now=self.now))

    def test_keeps_recently_obtained_yield(self):
        stock = {
            "dividend_yield": 0.0,
            "dividend_updated_at": (self.now - timedelta(hours=2)).isoformat(),
        }

        self.assertFalse(should_refresh_dividend(stock, now=self.now))


class SetShareCountTest(unittest.TestCase):
    def setUp(self):
        self.stock = {
            "shares": 100,
            "average_price": 1_000,
            "transactions": [{"type": "buy", "shares": 100, "price": 1_000}],
        }

    def test_increase_records_purchase(self):
        difference = set_share_count(self.stock, 300, 1_200)

        self.assertEqual(difference, 200)
        self.assertEqual(self.stock["shares"], 300)
        self.assertEqual(self.stock["transactions"][-1], {"type": "buy", "shares": 200, "price": 1_200})

    def test_decrease_records_sale(self):
        difference = set_share_count(self.stock, 40, 1_100)

        self.assertEqual(difference, -60)
        self.assertEqual(self.stock["shares"], 40)
        self.assertEqual(self.stock["transactions"][-1], {"type": "sell", "shares": 60, "price": 1_100})

    def test_same_count_does_not_add_transaction(self):
        difference = set_share_count(self.stock, 100, 1_100)

        self.assertEqual(difference, 0)
        self.assertEqual(len(self.stock["transactions"]), 1)

    def test_zero_count_records_full_sale(self):
        difference = set_share_count(self.stock, 0, 1_250)

        self.assertEqual(difference, -100)
        self.assertEqual(self.stock["shares"], 0)
        self.assertEqual(self.stock["transactions"][-1], {"type": "sell", "shares": 100, "price": 1_250})
        self.assertEqual(cash_balance([self.stock]), INITIAL_CAPITAL + 25_000)


class CandidateTest(unittest.TestCase):
    def test_candidate_starts_with_zero_shares_and_no_transactions(self):
        candidate = create_candidate(
            "7203",
            {"name": "テスト自動車", "price": 2_500, "dividend_yield": 2.1},
        )

        self.assertEqual(candidate["shares"], 0)
        self.assertEqual(candidate["average_price"], 0)
        self.assertEqual(candidate["transactions"], [])
        self.assertEqual(cash_balance([candidate]), INITIAL_CAPITAL)


class ResetPortfolioTest(unittest.TestCase):
    def test_reset_keeps_stock_but_clears_position_and_history(self):
        stocks = [{
            "name": "テスト株",
            "code": "1234",
            "shares": 10,
            "average_price": 500,
            "transactions": [{"type": "buy", "shares": 10, "price": 500}],
        }]

        reset_portfolio(stocks)

        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0]["shares"], 0)
        self.assertEqual(stocks[0]["average_price"], 0)
        self.assertEqual(stocks[0]["transactions"], [])
        self.assertEqual(cash_balance(stocks), INITIAL_CAPITAL)


if __name__ == "__main__":
    unittest.main()
