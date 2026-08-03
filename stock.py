from datetime import datetime
import unicodedata


INITIAL_CAPITAL = 10_000_000


def normalize_input(value):
    """全角の数字・英字を含む入力を半角へ正規化する。"""
    return unicodedata.normalize("NFKC", value)


def create_stock(code, stock_info, shares, average_price):
    stock = {
        "name": stock_info["name"],
        "code": code,
        "transactions": [],
        "current_price": stock_info["price"],
        "dividend_yield": stock_info["dividend_yield"],
        "dividend_months": stock_info.get("dividend_months", []),
        "price_updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    add_purchase(stock, shares, average_price)
    return stock


def create_candidate(code, stock_info):
    """売買履歴を持たない候補銘柄を作る。"""
    return {
        "name": stock_info["name"],
        "code": code,
        "shares": 0,
        "average_price": 0,
        "transactions": [],
        "current_price": stock_info["price"],
        "dividend_yield": stock_info["dividend_yield"],
        "dividend_months": stock_info.get("dividend_months", []),
        "price_updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def add_purchase(stock, shares, price):
    stock.setdefault("transactions", []).append({"type": "buy", "shares": shares, "price": price})
    update_position(stock)


def sell_shares(stock, shares, price):
    update_position(stock)
    if shares > stock["shares"]:
        raise ValueError("保有株数を超える株数は売却できません。")
    stock.setdefault("transactions", []).append({"type": "sell", "shares": shares, "price": price})
    update_position(stock)


def set_share_count(stock, target_shares, price):
    """指定株数との差分を購入または売却として記録する。"""
    update_position(stock)
    if target_shares < 0:
        raise ValueError("株数は0以上で入力してください。")
    if price <= 0:
        raise ValueError("単価は0より大きくしてください。")
    difference = target_shares - stock["shares"]
    if difference > 0:
        add_purchase(stock, difference, price)
    elif difference < 0:
        sell_shares(stock, -difference, price)
    return difference


def update_position(stock):
    shares = 0
    cost = 0
    realized_profit = 0
    for transaction in stock.get("transactions", []):
        quantity = transaction["shares"]
        price = transaction["price"]
        if transaction["type"] == "buy":
            shares += quantity
            cost += quantity * price
        elif transaction["type"] == "sell":
            average_price = cost / shares if shares else 0
            shares -= quantity
            cost -= quantity * average_price
            realized_profit += quantity * (price - average_price)
    stock["shares"] = shares
    stock["average_price"] = cost / shares if shares else 0
    stock["realized_profit"] = realized_profit


def purchase_count(stock):
    return sum(transaction["type"] == "buy" for transaction in stock.get("transactions", []))


def sale_count(stock):
    return sum(transaction["type"] == "sell" for transaction in stock.get("transactions", []))


def total_cost(stock):
    return stock["shares"] * stock["average_price"]


def cash_balance(stocks, initial_capital=INITIAL_CAPITAL):
    """購入代金を差し引き、売却代金を加えた仮想資金の現金残高を返す。"""
    balance = initial_capital
    for stock in stocks:
        for transaction in stock.get("transactions", []):
            amount = transaction["shares"] * transaction["price"]
            balance += amount if transaction["type"] == "sell" else -amount
    return balance


def reset_portfolio(stocks):
    """登録銘柄を残し、全売買履歴と保有株数を初期状態へ戻す。"""
    for stock in stocks:
        stock["transactions"] = []
        update_position(stock)


def market_value(stock):
    return stock["shares"] * stock["current_price"]


def profit_loss(stock):
    return market_value(stock) - total_cost(stock)


def annual_dividend(stock):
    """過去1年実績ベースの配当利回りから年間配当金を計算する。"""
    dividend_yield = stock.get("dividend_yield")
    if dividend_yield is None or "current_price" not in stock:
        return None
    return market_value(stock) * dividend_yield / 100
