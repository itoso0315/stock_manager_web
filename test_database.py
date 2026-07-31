import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database


def stock_record(name, code, shares=1, price=100, transactions=None):
    return {
        "name": name,
        "code": code,
        "shares": shares,
        "average_price": price,
        "transactions": (
            transactions
            if transactions is not None
            else [{"type": "buy", "shares": shares, "price": price}]
        ),
    }


class TemporaryDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database_file = database.DATABASE_FILE
        self.database_file = (
            Path(self.temporary_directory.name) / "stocks-test.db"
        )
        database.DATABASE_FILE = self.database_file

    def tearDown(self):
        database.DATABASE_FILE = self.original_database_file
        gc.collect()
        self.temporary_directory.cleanup()

    def connect(self):
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def execute(self, sql, parameters=()):
        connection = self.connect()
        try:
            cursor = connection.execute(sql, parameters)
            rows = cursor.fetchall()
            connection.commit()
            return rows
        finally:
            connection.close()

    def seed_legacy_purchase(self, code="1111"):
        database.initialize_database()
        connection = self.connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price,
                    current_price, dividend_yield, price_updated_at,
                    dividend_months
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("旧形式銘柄", code, 10, 500, None, None, None, "[]"),
            )
            connection.execute(
                """
                INSERT INTO purchases (stock_id, shares, price)
                VALUES (?, ?, ?)
                """,
                (cursor.lastrowid, 10, 500),
            )
            connection.commit()
            return cursor.lastrowid
        finally:
            connection.close()

    # Schema and connection contracts

    def test_creates_four_application_tables(self):
        database.initialize_database()

        rows = self.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        )

        self.assertEqual(
            [row["name"] for row in rows],
            ["app_settings", "purchases", "stocks", "transactions"],
        )

    def test_stocks_contains_dividend_months_column(self):
        database.initialize_database()

        columns = self.execute("PRAGMA table_info(stocks)")

        self.assertIn("dividend_months", {row["name"] for row in columns})

    def test_stock_code_is_unique(self):
        database.initialize_database()
        connection = self.connect()
        try:
            values = ("銘柄A", "1111", 0, 0)
            connection.execute(
                """
                INSERT INTO stocks (name, code, shares, average_price)
                VALUES (?, ?, ?, ?)
                """,
                values,
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO stocks (name, code, shares, average_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("銘柄B", "1111", 0, 0),
                )
        finally:
            connection.rollback()
            connection.close()

    def test_transaction_type_check_accepts_only_buy_or_sell(self):
        database.initialize_database()
        connection = self.connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO stocks (name, code, shares, average_price)
                VALUES ('銘柄A', '1111', 0, 0)
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO transactions (
                        stock_id, transaction_type, shares, price
                    ) VALUES (?, 'hold', 1, 100)
                    """,
                    (cursor.lastrowid,),
                )
        finally:
            connection.rollback()
            connection.close()

    def test_purchase_and_transaction_foreign_keys_cascade(self):
        database.initialize_database()

        purchases = self.execute("PRAGMA foreign_key_list(purchases)")
        transactions = self.execute("PRAGMA foreign_key_list(transactions)")

        for foreign_keys in (purchases, transactions):
            self.assertEqual(len(foreign_keys), 1)
            self.assertEqual(foreign_keys[0]["table"], "stocks")
            self.assertEqual(foreign_keys[0]["from"], "stock_id")
            self.assertEqual(foreign_keys[0]["to"], "id")
            self.assertEqual(foreign_keys[0]["on_delete"], "CASCADE")

    def test_database_connection_enables_foreign_keys(self):
        connection = database.get_connection()
        try:
            enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(enabled, 1)

    # Legacy migration contracts

    def test_migrates_purchases_to_buy_transactions(self):
        stock_id = self.seed_legacy_purchase()

        database.initialize_database()

        rows = self.execute(
            """
            SELECT stock_id, transaction_type, shares, price
            FROM transactions
            """
        )
        self.assertEqual(
            [tuple(row) for row in rows],
            [(stock_id, "buy", 10, 500)],
        )

    def test_existing_transaction_prevents_duplicate_purchase_migration(self):
        stock_id = self.seed_legacy_purchase()
        self.execute(
            """
            INSERT INTO transactions (
                stock_id, transaction_type, shares, price
            ) VALUES (?, 'buy', 10, 500)
            """,
            (stock_id,),
        )

        database.initialize_database()

        count = self.execute(
            "SELECT COUNT(*) AS count FROM transactions"
        )[0]["count"]
        self.assertEqual(count, 1)

    def test_repeated_initialization_does_not_duplicate_migration(self):
        self.seed_legacy_purchase()

        database.initialize_database()
        database.initialize_database()

        count = self.execute(
            "SELECT COUNT(*) AS count FROM transactions"
        )[0]["count"]
        self.assertEqual(count, 1)

    def test_initialization_does_not_delete_legacy_purchases(self):
        self.seed_legacy_purchase()

        database.initialize_database()

        count = self.execute(
            "SELECT COUNT(*) AS count FROM purchases"
        )[0]["count"]
        self.assertEqual(count, 1)

    # Loading contracts

    def test_loads_stocks_in_id_order(self):
        database.initialize_database()
        connection = self.connect()
        try:
            connection.execute(
                """
                INSERT INTO stocks (
                    id, name, code, shares, average_price, dividend_months
                ) VALUES (20, '後の銘柄', '2222', 0, 0, '[]')
                """
            )
            connection.execute(
                """
                INSERT INTO stocks (
                    id, name, code, shares, average_price, dividend_months
                ) VALUES (10, '先の銘柄', '1111', 0, 0, '[]')
                """
            )
            connection.commit()
        finally:
            connection.close()

        loaded = database.load_stocks()

        self.assertEqual([stock["code"] for stock in loaded], ["1111", "2222"])

    def test_loads_transactions_in_id_order(self):
        database.initialize_database()
        connection = self.connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price, dividend_months
                ) VALUES ('順序テスト', '1111', 3, 200, '[]')
                """
            )
            connection.execute(
                """
                INSERT INTO transactions (
                    id, stock_id, transaction_type, shares, price
                ) VALUES (20, ?, 'buy', 2, 300)
                """,
                (cursor.lastrowid,),
            )
            connection.execute(
                """
                INSERT INTO transactions (
                    id, stock_id, transaction_type, shares, price
                ) VALUES (10, ?, 'buy', 1, 100)
                """,
                (cursor.lastrowid,),
            )
            connection.commit()
        finally:
            connection.close()

        loaded = database.load_stocks()

        self.assertEqual(
            loaded[0]["transactions"],
            [
                {"type": "buy", "shares": 1, "price": 100},
                {"type": "buy", "shares": 2, "price": 300},
            ],
        )

    def test_restores_dividend_months_from_json(self):
        database.save_stocks([
            {
                **stock_record("配当銘柄", "1111"),
                "dividend_months": [3, 9],
            }
        ])

        loaded = database.load_stocks()

        self.assertEqual(loaded[0]["dividend_months"], [3, 9])

    def test_handles_nullable_current_price_and_updated_at(self):
        database.save_stocks([stock_record("未更新銘柄", "1111")])

        loaded = database.load_stocks()

        self.assertNotIn("current_price", loaded[0])
        self.assertNotIn("price_updated_at", loaded[0])

    def test_recalculates_position_from_transactions(self):
        database.initialize_database()
        connection = self.connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price, dividend_months
                ) VALUES ('再計算銘柄', '1111', 999, 999, '[]')
                """
            )
            connection.execute(
                """
                INSERT INTO transactions (
                    stock_id, transaction_type, shares, price
                ) VALUES (?, 'buy', 100, 100)
                """,
                (cursor.lastrowid,),
            )
            connection.execute(
                """
                INSERT INTO transactions (
                    stock_id, transaction_type, shares, price
                ) VALUES (?, 'sell', 25, 140)
                """,
                (cursor.lastrowid,),
            )
            connection.commit()
        finally:
            connection.close()

        loaded = database.load_stocks()[0]

        self.assertEqual(loaded["shares"], 75)
        self.assertEqual(loaded["average_price"], 100)
        self.assertEqual(loaded["realized_profit"], 1_000)

    # Saving contracts

    def test_save_and_load_stocks_round_trip(self):
        stocks = [
            {
                "name": "テスト商事",
                "code": "9999",
                "shares": 8,
                "average_price": 1_025,
                "current_price": 1_200,
                "dividend_yield": 2.5,
                "dividend_months": [3, 9],
                "price_updated_at": "2026-07-29T12:00:00+09:00",
                "transactions": [
                    {"type": "buy", "shares": 10, "price": 1_000},
                    {"type": "sell", "shares": 2, "price": 1_100},
                ],
            }
        ]

        database.save_stocks(stocks)
        loaded_stocks = database.load_stocks()

        self.assertEqual(len(loaded_stocks), 1)
        self.assertEqual(loaded_stocks[0]["name"], "テスト商事")
        self.assertEqual(loaded_stocks[0]["code"], "9999")
        self.assertEqual(loaded_stocks[0]["shares"], 8)
        self.assertEqual(loaded_stocks[0]["average_price"], 1_000)
        self.assertEqual(loaded_stocks[0]["current_price"], 1_200)
        self.assertEqual(loaded_stocks[0]["dividend_yield"], 2.5)
        self.assertEqual(loaded_stocks[0]["dividend_months"], [3, 9])
        self.assertEqual(
            loaded_stocks[0]["price_updated_at"],
            "2026-07-29T12:00:00+09:00",
        )
        self.assertEqual(
            loaded_stocks[0]["transactions"],
            stocks[0]["transactions"],
        )

    def test_save_replaces_previous_stocks(self):
        database.save_stocks([stock_record("古い銘柄", "1111")])

        database.save_stocks([stock_record("新しい銘柄", "2222", 2, 200)])

        loaded_stocks = database.load_stocks()
        self.assertEqual([stock["code"] for stock in loaded_stocks], ["2222"])

    def test_saves_buy_and_sell_transactions(self):
        transactions = [
            {"type": "buy", "shares": 10, "price": 100},
            {"type": "sell", "shares": 4, "price": 150},
        ]

        database.save_stocks([
            stock_record(
                "売買銘柄",
                "1111",
                shares=6,
                price=100,
                transactions=transactions,
            )
        ])

        self.assertEqual(database.load_stocks()[0]["transactions"], transactions)

    def test_save_clears_legacy_purchases(self):
        self.seed_legacy_purchase()

        database.save_stocks([stock_record("新銘柄", "2222")])

        count = self.execute(
            "SELECT COUNT(*) AS count FROM purchases"
        )[0]["count"]
        self.assertEqual(count, 0)

    def test_save_rolls_back_all_changes_on_constraint_failure(self):
        database.save_stocks([stock_record("保存済み", "1111")])
        invalid_stocks = [
            stock_record("重複A", "2222"),
            stock_record("重複B", "2222"),
        ]

        with self.assertRaises(sqlite3.IntegrityError):
            database.save_stocks(invalid_stocks)

        loaded = database.load_stocks()
        self.assertEqual([stock["code"] for stock in loaded], ["1111"])

    def test_saves_empty_portfolio(self):
        database.save_stocks([stock_record("削除対象", "1111")])

        database.save_stocks([])

        self.assertEqual(database.load_stocks(), [])
        counts = {
            table: self.execute(
                f"SELECT COUNT(*) AS count FROM {table}"
            )[0]["count"]
            for table in ("stocks", "purchases", "transactions")
        }
        self.assertEqual(
            counts,
            {"stocks": 0, "purchases": 0, "transactions": 0},
        )

    def test_saves_multiple_stocks(self):
        database.save_stocks([
            stock_record("銘柄A", "1111"),
            stock_record("銘柄B", "2222", 2, 200),
            stock_record("銘柄C", "3333", 3, 300),
        ])

        loaded = database.load_stocks()

        self.assertEqual(
            [stock["code"] for stock in loaded],
            ["1111", "2222", "3333"],
        )

    def test_save_stocks_keeps_none_return_value(self):
        result = database.save_stocks([stock_record("保存銘柄", "1111")])

        self.assertIsNone(result)

    # Application settings and path contracts

    def test_initial_capital_defaults_to_configured_value(self):
        self.assertEqual(
            database.load_initial_capital(),
            database.DEFAULT_INITIAL_CAPITAL,
        )

    def test_initial_capital_can_be_saved_and_updated(self):
        database.save_initial_capital(2_500_000)
        self.assertEqual(database.load_initial_capital(), 2_500_000)

        database.save_initial_capital(3_000_000)
        self.assertEqual(database.load_initial_capital(), 3_000_000)

    def test_save_initial_capital_keeps_none_return_value(self):
        result = database.save_initial_capital(2_500_000)

        self.assertIsNone(result)

    def test_initial_capital_rejects_zero_and_negative_values(self):
        for amount in (0, -1):
            with self.subTest(amount=amount):
                with self.assertRaisesRegex(
                    ValueError,
                    "^仮想資金は1円以上で設定してください。$",
                ):
                    database.save_initial_capital(amount)

    def test_initial_capital_keeps_invalid_type_errors(self):
        for amount in (None, "1000000"):
            with self.subTest(amount=amount):
                with self.assertRaises(TypeError):
                    database.save_initial_capital(amount)

    def test_database_file_is_resolved_at_call_time(self):
        first_database = self.database_file
        database.initialize_database()
        second_database = (
            Path(self.temporary_directory.name) / "second-stocks-test.db"
        )

        database.DATABASE_FILE = second_database
        database.initialize_database()

        self.assertTrue(first_database.is_file())
        self.assertTrue(second_database.is_file())
        self.assertNotEqual(first_database, self.original_database_file)
        self.assertNotEqual(second_database, self.original_database_file)

    def test_all_database_operations_use_only_temporary_path(self):
        database.save_stocks([stock_record("一時DB銘柄", "1111")])
        database.save_initial_capital(2_000_000)

        self.assertTrue(self.database_file.is_relative_to(
            Path(self.temporary_directory.name)
        ))
        self.assertNotEqual(self.database_file, self.original_database_file)
        self.assertTrue(self.database_file.is_file())


if __name__ == "__main__":
    unittest.main()
