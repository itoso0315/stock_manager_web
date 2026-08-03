import unittest
from unittest.mock import patch

import api
from api import (
    parse_minkabu_dividend_months,
    parse_minkabu_stock_name,
    parse_yahoo_japan_search_results,
    parse_yahoo_japan_stock_name,
)


class MinkabuStockNameTest(unittest.TestCase):
    def test_extracts_japanese_name_from_title(self):
        page_html = "<html><head><title>三菱商事 (8058) : 株価 - みんかぶ</title></head></html>"

        self.assertEqual(parse_minkabu_stock_name(page_html, "8058"), "三菱商事")

    def test_extracts_name_for_alphanumeric_code(self):
        page_html = "<title>キオクシアホールディングス (285A) : 株価 - みんかぶ</title>"

        self.assertEqual(parse_minkabu_stock_name(page_html, "285A"), "キオクシアホールディングス")

    def test_returns_none_without_matching_title(self):
        self.assertIsNone(parse_minkabu_stock_name("<html>not found</html>", "8058"))

    def test_extracts_dividend_record_months(self):
        page_html = "<div>配当権利確定月 <strong>3月, 9月</strong></div>"

        self.assertEqual(parse_minkabu_dividend_months(page_html), [3, 9])


class YahooJapanStockNameTest(unittest.TestCase):
    def test_extracts_japanese_name_and_removes_company_marker(self):
        page_html = "<title>トヨタ自動車(株)【7203】：株価 - Yahoo!ファイナンス</title>"

        self.assertEqual(parse_yahoo_japan_stock_name(page_html, "7203"), "トヨタ自動車")

    def test_extracts_name_for_alphanumeric_code(self):
        page_html = "<title>キオクシアホールディングス(株)【285A】：株価</title>"

        self.assertEqual(
            parse_yahoo_japan_stock_name(page_html, "285A"),
            "キオクシアホールディングス",
        )

    def test_search_results_extract_japanese_company_names(self):
        page_html = """
        <a href="https://finance.yahoo.co.jp/quote/7203.T">
          <h2><strong>トヨタ自動車</strong>(株)</h2>
        </a>
        <a href="https://finance.yahoo.co.jp/quote/285A.T">
          <h2>キオクシアホールディングス(株)</h2>
        </a>
        <a href="https://finance.yahoo.co.jp/quote/AAPL">
          <h2>Apple Inc.</h2>
        </a>
        """

        self.assertEqual(
            parse_yahoo_japan_search_results(page_html),
            [
                {"code": "7203", "name": "トヨタ自動車"},
                {"code": "285A", "name": "キオクシアホールディングス"},
            ],
        )


class ApiCompatibilityTest(unittest.TestCase):
    @patch("api.market_data_service.get_yahoo_symbol", return_value="8058.T")
    def test_get_yahoo_symbol_keeps_public_wrapper(self, service_function):
        self.assertEqual(api.get_yahoo_symbol("8058"), "8058.T")
        service_function.assert_called_once_with("8058")

    @patch("api.market_data_service.fetch_current_price", return_value=4_500.0)
    def test_fetch_current_price_keeps_value_contract(self, service_function):
        self.assertEqual(api.fetch_current_price("8058"), 4_500.0)
        service_function.assert_called_once_with("8058")

    @patch(
        "api.market_data_service.fetch_current_price",
        side_effect=RuntimeError("8058.T の株価を取得できませんでした。"),
    )
    def test_fetch_current_price_keeps_runtime_error_message(
        self,
        service_function,
    ):
        with self.assertRaisesRegex(
            RuntimeError,
            r"^8058\.T の株価を取得できませんでした。$",
        ):
            api.fetch_current_price("8058")

    @patch(
        "api.market_data_service.fetch_current_quote",
        side_effect=RuntimeError("8058.T の株価を取得できませんでした。"),
    )
    def test_fetch_stock_info_keeps_runtime_error_message(
        self,
        service_function,
    ):
        with self.assertRaisesRegex(
            RuntimeError,
            r"^8058\.T の株価を取得できませんでした。$",
        ):
            api.fetch_stock_info("8058")

    @patch("api.fetch_dividend_months", return_value=[3, 9])
    @patch("api.fetch_dividend_yield", return_value=2.5)
    @patch("api.fetch_japanese_stock_name", return_value="三菱商事")
    @patch(
        "api.market_data_service.fetch_current_quote",
        return_value=(
            "8058.T",
            {"longName": "Mitsubishi Corporation"},
            4_500.0,
        ),
    )
    def test_fetch_stock_info_keeps_dictionary_contract(
        self,
        quote,
        japanese_name,
        dividend_yield,
        dividend_months,
    ):
        self.assertEqual(
            api.fetch_stock_info("8058"),
            {
                "name": "三菱商事",
                "price": 4_500.0,
                "dividend_yield": 2.5,
                "dividend_months": [3, 9],
            },
        )
        quote.assert_called_once_with("8058")
        japanese_name.assert_called_once_with("8058")
        dividend_yield.assert_called_once_with("8058.T", 4_500.0)
        dividend_months.assert_called_once_with("8058")

    @patch("api.fetch_dividend_months", return_value=[])
    @patch("api.fetch_dividend_yield", return_value=None)
    @patch("api.fetch_yahoo_japan_stock_name", return_value=None)
    @patch("api.fetch_japanese_stock_name", return_value=None)
    @patch(
        "api.market_data_service.fetch_current_quote",
        return_value=("AAPL", {"shortName": "Apple"}, 200.0),
    )
    def test_fetch_stock_info_keeps_fallbacks(
        self,
        _quote,
        _japanese_name,
        _yahoo_japan_name,
        _dividend_yield,
        _dividend_months,
    ):
        self.assertEqual(
            api.fetch_stock_info("AAPL"),
            {
                "name": "Apple",
                "price": 200.0,
                "dividend_yield": None,
                "dividend_months": [],
            },
        )
