"""ポートフォリオの表示用集計を行う純粋関数。"""

from stock import total_cost


def _current_price(stock):
    return stock.get("current_price", stock["average_price"])


def calculate_stock_value(stocks):
    """保有株式の現在評価額合計を返す。"""
    return sum(
        _current_price(stock) * stock["shares"]
        for stock in stocks
    )


def calculate_purchase_value(stocks):
    """現在保有している株式の取得総額を返す。"""
    return sum(total_cost(stock) for stock in stocks)


def calculate_total_assets(cash_balance, stock_value):
    """現金と株式評価額を合算した総資産を返す。"""
    return cash_balance + stock_value


def calculate_unrealized_profit(stocks):
    """現在保有している株式の評価損益合計を返す。"""
    return calculate_stock_value(stocks) - calculate_purchase_value(stocks)


def calculate_unrealized_profit_rate(stocks):
    """現在保有している株式の取得総額に対する評価損益率を返す。"""
    purchase_value = calculate_purchase_value(stocks)
    if purchase_value > 0:
        return calculate_unrealized_profit(stocks) / purchase_value * 100
    return 0


def calculate_annual_dividend(stocks):
    """現在評価額と配当利回りから年間配当見込みを返す。"""
    return sum(
        _current_price(stock)
        * stock["shares"]
        * ((stock.get("dividend_yield") or 0) / 100)
        for stock in stocks
    )


def calculate_asset_ratios(cash_balance, stock_value):
    """総資産に対する現金比率と株式比率をパーセントで返す。"""
    total_assets = calculate_total_assets(cash_balance, stock_value)
    if total_assets > 0:
        return (
            cash_balance / total_assets * 100,
            stock_value / total_assets * 100,
        )
    return 0, 0


def build_allocation_data(stocks, cash_balance):
    """資産配分チャートで使用する銘柄別評価額と現金を返す。"""
    allocation_data = {}

    for stock in stocks:
        evaluation_value = _current_price(stock) * stock["shares"]
        if evaluation_value > 0:
            allocation_data[stock["name"]] = evaluation_value

    if cash_balance > 0:
        allocation_data["現金"] = cash_balance

    return allocation_data
