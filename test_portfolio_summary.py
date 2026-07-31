import unittest

from services.portfolio_service import (
    build_allocation_data,
    calculate_annual_dividend,
    calculate_asset_ratios,
    calculate_purchase_value,
    calculate_stock_value,
    calculate_total_assets,
    calculate_unrealized_profit,
    calculate_unrealized_profit_rate,
)
from stock import cash_balance


class PortfolioSummaryTest(unittest.TestCase):
    def setUp(self):
        self.initial_capital = 1_000_000
        self.stocks = [
            {
                "name": "テスト株A",
                "shares": 10,
                "average_price": 100,
                "current_price": 120,
                "dividend_yield": 2.0,
                "transactions": [
                    {"type": "buy", "shares": 10, "price": 100},
                ],
            },
            {
                "name": "テスト株B",
                "shares": 5,
                "average_price": 200,
                "current_price": 180,
                "dividend_yield": 4.0,
                "transactions": [
                    {"type": "buy", "shares": 5, "price": 200},
                ],
            },
        ]
        self.stock_value = calculate_stock_value(self.stocks)
        self.purchase_value = calculate_purchase_value(self.stocks)
        self.cash = cash_balance(self.stocks, self.initial_capital)
        self.total_assets = calculate_total_assets(self.cash, self.stock_value)
        self.evaluation_profit_loss = calculate_unrealized_profit(self.stocks)

    def test_total_assets(self):
        self.assertEqual(self.total_assets, 1_000_100)

    def test_stock_value(self):
        self.assertEqual(self.stock_value, 2_100)

    def test_evaluation_profit_loss(self):
        self.assertEqual(self.evaluation_profit_loss, 100)

    def test_profit_rate(self):
        profit_rate = calculate_unrealized_profit_rate(self.stocks)

        self.assertAlmostEqual(profit_rate, 5.0)

    def test_annual_dividend(self):
        dividend = calculate_annual_dividend(self.stocks)

        self.assertEqual(dividend, 60)

    def test_cash_ratio(self):
        cash_ratio, _ = calculate_asset_ratios(self.cash, self.stock_value)

        self.assertAlmostEqual(cash_ratio, 99.79002099790021)

    def test_stock_ratio(self):
        _, stock_ratio = calculate_asset_ratios(self.cash, self.stock_value)

        self.assertAlmostEqual(stock_ratio, 0.20997900209979003)

    def test_allocation_data_keeps_stock_order_and_adds_cash_last(self):
        allocation_data = build_allocation_data(self.stocks, self.cash)

        self.assertEqual(
            list(allocation_data.items()),
            [
                ("テスト株A", 1_200),
                ("テスト株B", 900),
                ("現金", 998_000),
            ],
        )

    def test_missing_current_price_uses_average_price(self):
        stock = {
            "name": "価格未更新株",
            "shares": 3,
            "average_price": 250,
            "dividend_yield": None,
            "transactions": [],
        }

        self.assertEqual(calculate_stock_value([stock]), 750)
        self.assertEqual(calculate_annual_dividend([stock]), 0)
        self.assertEqual(build_allocation_data([stock], 0), {"価格未更新株": 750})

    def test_zero_value_portfolio_ratios_and_profit_rate_are_zero(self):
        stock = {
            "name": "過去保有株",
            "shares": 0,
            "average_price": 0,
            "current_price": 500,
            "dividend_yield": 3.0,
            "transactions": [],
        }

        self.assertEqual(calculate_unrealized_profit_rate([stock]), 0)
        self.assertEqual(calculate_asset_ratios(0, 0), (0, 0))
        self.assertEqual(build_allocation_data([stock], 0), {})

    def test_service_matches_former_web_app_formulas(self):
        legacy_stock_value = sum(
            stock.get("current_price", stock["average_price"]) * stock["shares"]
            for stock in self.stocks
        )
        legacy_purchase_value = sum(
            stock["average_price"] * stock["shares"]
            for stock in self.stocks
        )
        legacy_total_assets = self.cash + legacy_stock_value
        legacy_profit = legacy_stock_value - legacy_purchase_value
        legacy_profit_rate = legacy_profit / legacy_purchase_value * 100
        legacy_dividend = sum(
            stock.get("current_price", stock["average_price"])
            * stock["shares"]
            * ((stock.get("dividend_yield") or 0) / 100)
            for stock in self.stocks
        )
        legacy_ratios = (
            self.cash / legacy_total_assets * 100,
            legacy_stock_value / legacy_total_assets * 100,
        )
        legacy_allocation = {
            stock["name"]: (
                stock.get("current_price", stock["average_price"])
                * stock["shares"]
            )
            for stock in self.stocks
            if (
                stock.get("current_price", stock["average_price"])
                * stock["shares"]
            ) > 0
        }
        if self.cash > 0:
            legacy_allocation["現金"] = self.cash

        self.assertEqual(calculate_stock_value(self.stocks), legacy_stock_value)
        self.assertEqual(
            calculate_purchase_value(self.stocks),
            legacy_purchase_value,
        )
        self.assertEqual(
            calculate_total_assets(self.cash, legacy_stock_value),
            legacy_total_assets,
        )
        self.assertEqual(calculate_unrealized_profit(self.stocks), legacy_profit)
        self.assertEqual(
            calculate_unrealized_profit_rate(self.stocks),
            legacy_profit_rate,
        )
        self.assertEqual(
            calculate_annual_dividend(self.stocks),
            legacy_dividend,
        )
        self.assertEqual(
            calculate_asset_ratios(self.cash, legacy_stock_value),
            legacy_ratios,
        )
        self.assertEqual(
            build_allocation_data(self.stocks, self.cash),
            legacy_allocation,
        )


if __name__ == "__main__":
    unittest.main()
