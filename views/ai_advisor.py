from stock import annual_dividend, cash_balance, market_value, total_cost


class AiAdvisorView:
    """AI相談文に渡すポートフォリオ情報を組み立てる。"""

    @staticmethod
    def portfolio_snapshot(stocks, initial_capital):
        holdings = [stock for stock in stocks if stock.get("shares", 0) > 0]
        candidates = [stock for stock in stocks if stock.get("shares", 0) == 0]
        priced = [stock for stock in holdings if stock.get("current_price") is not None]
        return {
            "holdings": holdings,
            "candidates": candidates,
            "cost": sum(total_cost(stock) for stock in holdings),
            "value": sum(market_value(stock) for stock in priced),
            "dividend": sum(annual_dividend(stock) or 0 for stock in priced),
            "cash": cash_balance(stocks, initial_capital),
        }
