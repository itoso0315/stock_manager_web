import json
from html import unescape
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from services import market_data_service
from stock import JAPANESE_STOCK_CODE_PATTERN, normalize_stock_code


SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

MINKABU_STOCK_URL = "https://minkabu.jp/stock/{code}"
MINKABU_DIVIDEND_URL = "https://minkabu.jp/stock/{code}/dividend"
YAHOO_JAPAN_STOCK_URL = "https://finance.yahoo.co.jp/quote/{symbol}"


def get_yahoo_symbol(code):
    """4文字の日本株コードには、Yahoo Finance用の .T を付ける。"""
    return market_data_service.get_yahoo_symbol(code)


def fetch_stock_info(code):
    symbol, meta, price = market_data_service.fetch_current_quote(code)
    yahoo_name = meta.get("longName") or meta.get("shortName") or symbol
    name = (
        fetch_japanese_stock_name(code)
        or fetch_yahoo_japan_stock_name(code)
        or yahoo_name
    )
    return {
        "name": name,
        "price": price,
        "dividend_yield": fetch_dividend_yield(symbol, price),
        "dividend_months": fetch_dividend_months(code),
    }


def parse_minkabu_stock_name(page_html, code):
    """みんかぶのページタイトルから日本語の銘柄名を取り出す。"""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", page_html, flags=re.IGNORECASE | re.DOTALL)
    if not title_match:
        return None
    title = " ".join(unescape(title_match.group(1)).split())
    name_match = re.match(rf"(.+?)\s*[（(]{re.escape(code)}[）)]", title, flags=re.IGNORECASE)
    return name_match.group(1).strip() if name_match else None


def fetch_japanese_stock_name(code):
    """みんかぶから日本語銘柄名を取得し、失敗時はNoneを返す。"""
    normalized_code = normalize_stock_code(code)
    if not JAPANESE_STOCK_CODE_PATTERN.fullmatch(normalized_code):
        return None
    request = Request(
        MINKABU_STOCK_URL.format(code=normalized_code),
        headers={"User-Agent": "Mozilla/5.0 (stock-manager/1.0)"},
    )
    try:
        with urlopen(request, timeout=10, context=SSL_CONTEXT) as response:
            page_html = response.read().decode("utf-8", errors="replace")
        return parse_minkabu_stock_name(page_html, normalized_code)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def parse_yahoo_japan_stock_name(page_html, code):
    """Yahoo!ファイナンスのページタイトルから日本語の銘柄名を取り出す。"""
    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not title_match:
        return None

    title = " ".join(unescape(title_match.group(1)).split())
    name_match = re.match(
        rf"(.+?)\s*[【〖]\s*{re.escape(code)}(?:\.T)?\s*[】〗]",
        title,
        flags=re.IGNORECASE,
    )
    if not name_match:
        return None

    name = name_match.group(1).strip()
    return re.sub(r"\s*[（(]株[）)]\s*$", "", name).strip() or None


def fetch_yahoo_japan_stock_name(code):
    """Yahoo!ファイナンス日本版から日本語銘柄名を取得する。"""
    normalized_code = normalize_stock_code(code)
    if not JAPANESE_STOCK_CODE_PATTERN.fullmatch(normalized_code):
        return None

    request = Request(
        YAHOO_JAPAN_STOCK_URL.format(symbol=get_yahoo_symbol(normalized_code)),
        headers={"User-Agent": "Mozilla/5.0 (stock-manager/1.0)"},
    )
    try:
        with urlopen(request, timeout=10, context=SSL_CONTEXT) as response:
            page_html = response.read().decode("utf-8", errors="replace")
        return parse_yahoo_japan_stock_name(page_html, normalized_code)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def parse_minkabu_dividend_months(page_html):
    """みんかぶ配当ページから配当権利確定月を取り出す。"""
    page_text = " ".join(unescape(re.sub(r"<[^>]+>", " ", page_html)).split())
    match = re.search(
        r"配当権利確定月\s*((?:1[0-2]|[1-9])月(?:\s*,\s*(?:1[0-2]|[1-9])月)*)",
        page_text,
    )
    if not match:
        return []
    return [int(month) for month in re.findall(r"(1[0-2]|[1-9])月", match.group(1))]


def fetch_dividend_months(code):
    """みんかぶから配当権利確定月を取得する。"""
    normalized_code = normalize_stock_code(code)
    if not JAPANESE_STOCK_CODE_PATTERN.fullmatch(normalized_code):
        return []
    request = Request(
        MINKABU_DIVIDEND_URL.format(code=normalized_code),
        headers={"User-Agent": "Mozilla/5.0 (stock-manager/1.0)"},
    )
    try:
        with urlopen(request, timeout=10, context=SSL_CONTEXT) as response:
            page_html = response.read().decode("utf-8", errors="replace")
        return parse_minkabu_dividend_months(page_html)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return []


def fetch_current_price(code):
    """現在株価だけを取得する。"""
    return market_data_service.fetch_current_price(code)


def fetch_dividend_yield(code, current_price):
    """過去1年の実績配当額を現在株価で割り、配当利回り（%）を返す。"""
    symbol = get_yahoo_symbol(code)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d&events=dividends"
    request = Request(url, headers={"User-Agent": "stock-manager/1.0"})

    try:
        with urlopen(request, timeout=10, context=SSL_CONTEXT) as response:
            data = json.load(response)
        dividends = data["chart"]["result"][0].get("events", {}).get("dividends", {})
        annual_dividend = sum(item["amount"] for item in dividends.values())
        return annual_dividend / current_price * 100
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, ValueError):
        return None
