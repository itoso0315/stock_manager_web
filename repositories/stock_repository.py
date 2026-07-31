"""SQLite接続と株式管理DBの初期化を担当するRepository。"""

import json
import sqlite3


class StockRepository:
    def __init__(self, db_path):
        self.db_path = db_path

    def get_connection(self):
        """外部キー制約を有効にしたSQLite接続を返す。"""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize_database(self, default_initial_capital):
        """現行スキーマを初期化し、旧購入履歴を取引履歴へ移行する。"""
        connection = self.get_connection()
        try:
            with connection:
                connection.executescript("""
                    CREATE TABLE IF NOT EXISTS stocks (
                        id INTEGER PRIMARY KEY, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE,
                        shares INTEGER NOT NULL, average_price REAL NOT NULL, current_price REAL,
                        dividend_yield REAL, price_updated_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS purchases (
                        id INTEGER PRIMARY KEY, stock_id INTEGER NOT NULL, shares INTEGER NOT NULL, price REAL NOT NULL,
                        FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY,
                        stock_id INTEGER NOT NULL,
                        transaction_type TEXT NOT NULL CHECK(transaction_type IN ('buy', 'sell')),
                        shares INTEGER NOT NULL,
                        price REAL NOT NULL,
                        FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
                    );
                    CREATE TABLE IF NOT EXISTS app_settings (
                        setting_key TEXT PRIMARY KEY,
                        setting_value TEXT NOT NULL
                    );
                """)
                connection.execute(
                    "INSERT OR IGNORE INTO app_settings (setting_key, setting_value) VALUES ('initial_capital', ?)",
                    (str(default_initial_capital),),
                )
                stock_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(stocks)")
                }
                if "dividend_months" not in stock_columns:
                    connection.execute(
                        "ALTER TABLE stocks ADD COLUMN dividend_months TEXT"
                    )
                stock_rows = connection.execute(
                    "SELECT id FROM stocks"
                ).fetchall()
                for row in stock_rows:
                    transaction_count = connection.execute(
                        """
                        SELECT COUNT(*) FROM transactions
                        WHERE stock_id = ?
                        """,
                        (row["id"],),
                    ).fetchone()[0]
                    if transaction_count:
                        continue
                    purchases = connection.execute(
                        """
                        SELECT shares, price FROM purchases
                        WHERE stock_id = ? ORDER BY id
                        """,
                        (row["id"],),
                    ).fetchall()
                    for purchase in purchases:
                        connection.execute(
                            """
                            INSERT INTO transactions (
                                stock_id, transaction_type, shares, price
                            ) VALUES (?, 'buy', ?, ?)
                            """,
                            (
                                row["id"],
                                purchase["shares"],
                                purchase["price"],
                            ),
                        )
        finally:
            connection.close()

    def load_stocks(self):
        """銘柄と取引履歴をID順に読み込み、辞書のリストで返す。"""
        connection = self.get_connection()
        try:
            rows = connection.execute(
                "SELECT * FROM stocks ORDER BY id"
            ).fetchall()
            stocks = []
            for row in rows:
                transaction_rows = connection.execute(
                    """
                    SELECT transaction_type, shares, price
                    FROM transactions
                    WHERE stock_id = ? ORDER BY id
                    """,
                    (row["id"],),
                ).fetchall()
                stock = {
                    "name": row["name"],
                    "code": row["code"],
                    "shares": row["shares"],
                    "average_price": row["average_price"],
                    "dividend_yield": row["dividend_yield"],
                    "dividend_months": json.loads(
                        row["dividend_months"] or "[]"
                    ),
                    "transactions": [
                        {
                            "type": transaction["transaction_type"],
                            "shares": transaction["shares"],
                            "price": transaction["price"],
                        }
                        for transaction in transaction_rows
                    ],
                }
                if row["current_price"] is not None:
                    stock["current_price"] = row["current_price"]
                if row["price_updated_at"] is not None:
                    stock["price_updated_at"] = row["price_updated_at"]
                stocks.append(stock)
            return stocks
        finally:
            connection.close()

    def save_stocks(self, stocks):
        """銘柄と取引履歴を、従来どおり全置換方式で保存する。"""
        connection = self.get_connection()
        try:
            connection.execute("DELETE FROM transactions")
            connection.execute("DELETE FROM purchases")
            connection.execute("DELETE FROM stocks")
            for stock in stocks:
                cursor = connection.execute(
                    """
                    INSERT INTO stocks (
                        name, code, shares, average_price, current_price,
                        dividend_yield, price_updated_at, dividend_months
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stock["name"],
                        stock["code"],
                        stock["shares"],
                        stock["average_price"],
                        stock.get("current_price"),
                        stock.get("dividend_yield"),
                        stock.get("price_updated_at"),
                        json.dumps(stock.get("dividend_months", [])),
                    ),
                )
                for transaction in stock.get("transactions", []):
                    connection.execute(
                        """
                        INSERT INTO transactions (
                            stock_id, transaction_type, shares, price
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            cursor.lastrowid,
                            transaction["type"],
                            transaction["shares"],
                            transaction["price"],
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def load_initial_capital(self):
        """保存された初期資金を数値で返し、未設定ならNoneを返す。"""
        connection = self.get_connection()
        try:
            row = connection.execute(
                """
                SELECT setting_value FROM app_settings
                WHERE setting_key = 'initial_capital'
                """
            ).fetchone()
            if row is None:
                return None
            value = row["setting_value"]
            try:
                return int(value)
            except ValueError:
                return float(value)
        finally:
            connection.close()

    def save_initial_capital(self, amount):
        """初期資金を保存し、接続とトランザクションを管理する。"""
        connection = self.get_connection()
        try:
            connection.execute(
                """
                INSERT INTO app_settings (
                    setting_key, setting_value
                ) VALUES ('initial_capital', ?)
                ON CONFLICT(setting_key) DO UPDATE
                SET setting_value = excluded.setting_value
                """,
                (str(amount),),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
