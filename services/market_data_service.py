"""Yahoo Financeから株価情報を取得するサービス。"""

import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
import yfinance as yf

from stock import JAPANESE_STOCK_CODE_PATTERN, normalize_stock_code


SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
YAHOO_CHART_URLS = (
    "https://query1.finance.yahoo.com/v8/finance/chart/"
    "{symbol}?range=1d&interval=1m",
    "https://query2.finance.yahoo.com/v8/finance/chart/"
    "{symbol}?range=1d&interval=1m",
)
YAHOO_USER_AGENT = "stock-manager/1.0"


def get_yahoo_symbol(code):
    """4文字の日本株コードにはYahoo Finance用の.Tを付ける。"""
    normalized_code = normalize_stock_code(code)
    if JAPANESE_STOCK_CODE_PATTERN.fullmatch(normalized_code):
        return f"{normalized_code}.T"
    return normalized_code


def _build_yahoo_chart_url(symbol, base_url=None):
    """Yahoo Financeの現在値取得URLを返す。"""
    return (base_url or YAHOO_CHART_URLS[0]).format(symbol=symbol)


def _fetch_yahoo_chart_meta(symbol):
    """Yahoo FinanceのチャートAPIからmeta情報を取得する。

    query1が一時的に拒否・失敗する場合に備え、query2へ切り替える。
    """
    last_error = None
    for chart_url in YAHOO_CHART_URLS:
        request = Request(
            _build_yahoo_chart_url(symbol, chart_url),
            headers={"User-Agent": YAHOO_USER_AGENT},
        )
        try:
            with urlopen(
                request,
                timeout=10,
                context=SSL_CONTEXT,
            ) as response:
                data = json.load(response)
            return data["chart"]["result"][0]["meta"]
        except (
            HTTPError,
            URLError,
            TimeoutError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as error:
            last_error = error

    if last_error is not None:
        raise last_error
    raise RuntimeError("Yahoo Financeの取得先が設定されていません。")


def _fetch_yfinance_price(symbol):
    """直接APIが利用できない環境ではyfinance経由で直近値を取得する。"""
    ticker = yf.Ticker(symbol)
    fast_info = ticker.fast_info
    for key in (
        "lastPrice",
        "last_price",
        "regularMarketPreviousClose",
        "previousClose",
        "previous_close",
    ):
        price = fast_info.get(key)
        if price is not None:
            return float(price)
    raise ValueError("yfinanceの応答に株価がありません。")


def fetch_current_quote(code):
    """銘柄コードからYahooシンボル、meta、現在値を返す。"""
    symbol = get_yahoo_symbol(code)

    try:
        meta = _fetch_yahoo_chart_meta(symbol)
        price = meta.get("regularMarketPrice")
        if price is None:
            price = meta.get("previousClose")
        if price is None:
            raise ValueError("Yahoo Financeの応答に株価がありません。")
        return symbol, meta, float(price)
    except (
        HTTPError,
        URLError,
        TimeoutError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as direct_error:
        try:
            price = _fetch_yfinance_price(symbol)
            return symbol, {"symbol": symbol, "regularMarketPrice": price}, price
        except Exception as fallback_error:
            raise RuntimeError(
                f"{symbol} の株価を取得できませんでした。"
            ) from fallback_error


def fetch_current_price(code):
    """銘柄コードから現在値を取得する。"""
    return fetch_current_quote(code)[2]


def fetch_price_history(symbol, period="1y", interval="1d"):
    """Yahoo Financeから指定銘柄の株価履歴を取得する。"""
    return yf.download(
        symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        multi_level_index=False,
    )
