"""Yahoo Financeから株価情報を取得するサービス。"""

import json
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
import yfinance as yf

from stock import normalize_input


SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
JAPANESE_STOCK_CODE_PATTERN = re.compile(
    r"^[0-9][0-9A-Z][0-9][0-9A-Z]$"
)
YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/"
    "{symbol}?range=1d&interval=1m"
)
YAHOO_USER_AGENT = "stock-manager/1.0"


def get_yahoo_symbol(code):
    """4文字の日本株コードにはYahoo Finance用の.Tを付ける。"""
    normalized_code = normalize_input(code).strip().upper()
    if JAPANESE_STOCK_CODE_PATTERN.fullmatch(normalized_code):
        return f"{normalized_code}.T"
    return normalized_code


def _build_yahoo_chart_url(symbol):
    """Yahoo Financeの現在値取得URLを返す。"""
    return YAHOO_CHART_URL.format(symbol=symbol)


def _fetch_yahoo_chart_meta(symbol):
    """Yahoo FinanceのチャートAPIからmeta情報を取得する。"""
    request = Request(
        _build_yahoo_chart_url(symbol),
        headers={"User-Agent": YAHOO_USER_AGENT},
    )
    with urlopen(
        request,
        timeout=10,
        context=SSL_CONTEXT,
    ) as response:
        data = json.load(response)
    return data["chart"]["result"][0]["meta"]


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
    ) as error:
        raise RuntimeError(
            f"{symbol} の株価を取得できませんでした。"
        ) from error


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
