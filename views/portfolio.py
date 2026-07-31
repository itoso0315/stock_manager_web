from stock import normalize_input


class PortfolioView:
    """保有・候補一覧の表示条件を担当するビュー部品。"""

    @staticmethod
    def filter_stocks(stocks, mode, search_value):
        query = normalize_input(search_value).strip().casefold()
        return [
            (index, stock)
            for index, stock in enumerate(stocks)
            if (stock["shares"] > 0) == (mode == "purchased")
            and (not query or query in stock["name"].casefold())
        ]
