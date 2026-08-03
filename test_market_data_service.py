import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock, patch

import pandas as pd

from services import market_data_service


def yahoo_chart_data(meta):
    return {"chart": {"result": [{"meta": meta}]}}


class YahooSymbolTest(unittest.TestCase):
    def test_adds_t_suffix_to_japanese_stock_code(self):
        self.assertEqual(market_data_service.get_yahoo_symbol("8058"), "8058.T")
        self.assertEqual(market_data_service.get_yahoo_symbol("285A"), "285A.T")

    def test_keeps_overseas_ticker_unchanged(self):
        self.assertEqual(market_data_service.get_yahoo_symbol("AAPL"), "AAPL")

    def test_normalizes_full_width_input(self):
        self.assertEqual(
            market_data_service.get_yahoo_symbol(" ２８５ａ "),
            "285A.T",
        )


class YahooCurrentPriceTest(unittest.TestCase):
    def setUp(self):
        self.response = MagicMock()
        self.response.__enter__.return_value = self.response
        self.response.__exit__.return_value = False

    def fetch_with_meta(self, meta):
        with (
            patch(
                "services.market_data_service.urlopen",
                return_value=self.response,
            ) as urlopen,
            patch(
                "services.market_data_service.json.load",
                return_value=yahoo_chart_data(meta),
            ),
        ):
            value = market_data_service.fetch_current_price("8058")
        return value, urlopen

    def test_uses_regular_market_price_and_converts_to_float(self):
        value, _ = self.fetch_with_meta(
            {"regularMarketPrice": "4.25", "previousClose": 3.5}
        )

        self.assertEqual(value, 4.25)
        self.assertIsInstance(value, float)

    def test_falls_back_to_previous_close(self):
        value, _ = self.fetch_with_meta(
            {"regularMarketPrice": None, "previousClose": "3.75"}
        )

        self.assertEqual(value, 3.75)

    def test_uses_expected_url_headers_timeout_and_ssl_context(self):
        _, urlopen = self.fetch_with_meta({"regularMarketPrice": 4_500})

        request = urlopen.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            "8058.T?range=1d&interval=1m",
        )
        self.assertEqual(
            request.get_header("User-agent"),
            "stock-manager/1.0",
        )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)
        self.assertIs(
            urlopen.call_args.kwargs["context"],
            market_data_service.SSL_CONTEXT,
        )

    def test_retries_alphanumeric_code_on_query2(self):
        second_response = MagicMock()
        second_response.__enter__.return_value = second_response
        second_response.__exit__.return_value = False
        temporary_error = URLError("query1 temporarily unavailable")

        with (
            patch(
                "services.market_data_service.urlopen",
                side_effect=[temporary_error, second_response],
            ) as urlopen,
            patch(
                "services.market_data_service.json.load",
                return_value=yahoo_chart_data({"regularMarketPrice": 2_850}),
            ),
        ):
            symbol, _, price = market_data_service.fetch_current_quote("285A")

        self.assertEqual(symbol, "285A.T")
        self.assertEqual(price, 2_850.0)
        self.assertEqual(urlopen.call_count, 2)
        self.assertIn("query1.finance.yahoo.com", urlopen.call_args_list[0].args[0].full_url)
        self.assertIn("query2.finance.yahoo.com", urlopen.call_args_list[1].args[0].full_url)

    def assert_fetch_error(self, side_effect=None, data=None):
        with (
            patch(
                "services.market_data_service.urlopen",
                return_value=self.response,
                side_effect=side_effect,
            ),
            patch(
                "services.market_data_service.json.load",
                return_value=data,
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"^8058\.T の株価を取得できませんでした。$",
            ):
                market_data_service.fetch_current_price("8058")

    def test_converts_http_error_to_runtime_error(self):
        error = HTTPError(
            url="https://example.invalid",
            code=500,
            msg="server error",
            hdrs=None,
            fp=None,
        )
        self.addCleanup(error.close)
        self.assert_fetch_error(side_effect=error)

    def test_converts_url_error_to_runtime_error(self):
        self.assert_fetch_error(side_effect=URLError("offline"))

    def test_converts_timeout_to_runtime_error(self):
        self.assert_fetch_error(side_effect=TimeoutError())

    def test_converts_invalid_json_to_runtime_error(self):
        with (
            patch(
                "services.market_data_service.urlopen",
                return_value=self.response,
            ),
            patch(
                "services.market_data_service.json.load",
                side_effect=ValueError("invalid json"),
            ),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"^8058\.T の株価を取得できませんでした。$",
            ):
                market_data_service.fetch_current_price("8058")

    def test_converts_empty_result_to_runtime_error(self):
        self.assert_fetch_error(data={"chart": {"result": []}})

    def test_converts_missing_meta_to_runtime_error(self):
        self.assert_fetch_error(data={"chart": {"result": [{}]}})

    def test_converts_missing_price_to_runtime_error(self):
        self.assert_fetch_error(data=yahoo_chart_data({}))

    def test_does_not_cache_current_price(self):
        with (
            patch(
                "services.market_data_service.urlopen",
                return_value=self.response,
            ) as urlopen,
            patch(
                "services.market_data_service.json.load",
                return_value=yahoo_chart_data({"regularMarketPrice": 4_500}),
            ),
        ):
            market_data_service.fetch_current_price("8058")
            market_data_service.fetch_current_price("8058")

        self.assertEqual(urlopen.call_count, 2)


class PriceHistoryTest(unittest.TestCase):
    @patch("services.market_data_service.yf.download")
    def test_fetches_one_year_of_unadjusted_daily_history(self, download):
        expected = pd.DataFrame({"Close": [100]})
        download.return_value = expected

        result = market_data_service.fetch_price_history("8306.T")

        self.assertIs(result, expected)
        download.assert_called_once_with(
            "8306.T",
            period="1y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            multi_level_index=False,
        )


if __name__ == "__main__":
    unittest.main()
