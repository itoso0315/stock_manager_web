from pathlib import Path

from repositories.stock_repository import StockRepository
from stock import update_position


DATABASE_FILE = Path(__file__).with_name("stocks.db")
DEFAULT_INITIAL_CAPITAL = 10_000_000


def _get_repository():
    return StockRepository(DATABASE_FILE)


def get_connection():
    return _get_repository().get_connection()


def initialize_database():
    _get_repository().initialize_database(DEFAULT_INITIAL_CAPITAL)


def load_stocks():
    initialize_database()
    stocks = _get_repository().load_stocks()
    for stock in stocks:
        update_position(stock)
    return stocks


def save_stocks(stocks):
    initialize_database()
    return _get_repository().save_stocks(stocks)


def load_initial_capital():
    initialize_database()
    value = _get_repository().load_initial_capital()
    if value is None:
        return DEFAULT_INITIAL_CAPITAL
    return int(str(value))


def save_initial_capital(amount):
    if amount <= 0:
        raise ValueError("仮想資金は1円以上で設定してください。")
    initialize_database()
    return _get_repository().save_initial_capital(amount)
