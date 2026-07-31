import json
import sqlite3
from pathlib import Path

from stock import update_purchase_summary


DATABASE_FILE = Path(__file__).with_name("stocks.db")
LEGACY_JSON_FILE = Path(__file__).with_name("stocks.json")


def get_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                shares INTEGER NOT NULL,
                average_price REAL NOT NULL,
                current_price REAL,
                dividend_yield REAL,
                price_updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY,
                stock_id INTEGER NOT NULL,
                shares INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            );
            """
        )


def migrate_json_to_sqlite():
    """既存のJSONデータを、データベースが空のときだけ取り込む。"""
    if not LEGACY_JSON_FILE.exists():
        return

    with get_connection() as connection:
        existing_count = connection.execute("SELECT COUNT(*) FROM stocks").fetchone()[0]
        if existing_count:
            return

        with LEGACY_JSON_FILE.open("r", encoding="utf-8") as file:
            legacy_stocks = json.load(file)

        for stock in legacy_stocks:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price, current_price,
                    dividend_yield, price_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stock["name"],
                    stock["code"],
                    stock["shares"],
                    stock["average_price"],
                    stock.get("current_price"),
                    stock.get("dividend_yield"),
                    stock.get("price_updated_at"),
                ),
            )
            purchases = stock.get(
                "purchases",
                [{"shares": stock["shares"], "price": stock["average_price"]}],
            )
            for purchase in purchases:
                connection.execute(
                    "INSERT INTO purchases (stock_id, shares, price) VALUES (?, ?, ?)",
                    (cursor.lastrowid, purchase["shares"], purchase["price"]),
                )


def load_stocks():
    initialize_database()
    migrate_json_to_sqlite()

    with get_connection() as connection:
        stock_rows = connection.execute("SELECT * FROM stocks ORDER BY id").fetchall()
        stocks = []
        for row in stock_rows:
            purchases = connection.execute(
                "SELECT shares, price FROM purchases WHERE stock_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            stock = {
                "name": row["name"],
                "code": row["code"],
                "shares": row["shares"],
                "average_price": row["average_price"],
                "purchases": [dict(purchase) for purchase in purchases],
                "dividend_yield": row["dividend_yield"],
            }
            if row["current_price"] is not None:
                stock["current_price"] = row["current_price"]
            if row["price_updated_at"] is not None:
                stock["price_updated_at"] = row["price_updated_at"]
            update_purchase_summary(stock)
            stocks.append(stock)
    return stocks


def save_stocks(stocks):
    initialize_database()

    with get_connection() as connection:
        connection.execute("DELETE FROM purchases")
        connection.execute("DELETE FROM stocks")

        for stock in stocks:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price, current_price,
                    dividend_yield, price_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stock["name"],
                    stock["code"],
                    stock["shares"],
                    stock["average_price"],
                    stock.get("current_price"),
                    stock.get("dividend_yield"),
                    stock.get("price_updated_at"),
                ),
            )
            for purchase in stock.get("purchases", []):
                connection.execute(
                    "INSERT INTO purchases (stock_id, shares, price) VALUES (?, ?, ?)",
                    (cursor.lastrowid, purchase["shares"], purchase["price"]),
                )
