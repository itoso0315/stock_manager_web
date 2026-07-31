import sqlite3
import tempfile
import unittest
from pathlib import Path

from repositories.stock_repository import StockRepository


DEFAULT_INITIAL_CAPITAL = 10_000_000


class TrackingConnection:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self.connection.__exit__(exc_type, exc_value, traceback)

    def close(self):
        self.closed = True
        self.connection.close()

    def commit(self):
        self.committed = True
        self.connection.commit()

    def rollback(self):
        self.rolled_back = True
        self.connection.rollback()


class FailingReadConnection(TrackingConnection):
    def execute(self, sql, parameters=()):
        if "SELECT * FROM stocks" in sql:
            raise sqlite3.OperationalError("forced read failure")
        return self.connection.execute(sql, parameters)


class FailingSettingConnection(TrackingConnection):
    def execute(self, sql, parameters=()):
        if "app_settings" in sql:
            raise sqlite3.OperationalError("forced setting failure")
        return self.connection.execute(sql, parameters)


class FailingInitializationConnection(TrackingConnection):
    def execute(self, sql, parameters=()):
        if "PRAGMA table_info(stocks)" in sql:
            raise sqlite3.OperationalError("forced initialization failure")
        return self.connection.execute(sql, parameters)


def stock_record(name, code, shares=1, price=100, transactions=None):
    return {
        "name": name,
        "code": code,
        "shares": shares,
        "average_price": price,
        "transactions": transactions if transactions is not None else [
            {"type": "buy", "shares": shares, "price": price}
        ],
    }


class StockRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_file = (
            Path(self.temporary_directory.name) / "repository-test.db"
        )
        self.repository = StockRepository(self.database_file)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_uses_injected_database_path(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        self.assertTrue(self.database_file.is_file())
        connection = sqlite3.connect(self.database_file)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'table'
                    """
                )
            }
        finally:
            connection.close()
        self.assertEqual(
            tables,
            {"stocks", "purchases", "transactions", "app_settings"},
        )

    def test_two_repositories_use_separate_databases(self):
        second_file = (
            Path(self.temporary_directory.name) / "second-repository-test.db"
        )
        second_repository = StockRepository(second_file)

        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        second_repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        first_connection = self.repository.get_connection()
        second_connection = second_repository.get_connection()
        try:
            first_connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price
                ) VALUES ('銘柄A', '1111', 0, 0)
                """
            )
            first_connection.commit()
            first_count = first_connection.execute(
                "SELECT COUNT(*) FROM stocks"
            ).fetchone()[0]
            second_count = second_connection.execute(
                "SELECT COUNT(*) FROM stocks"
            ).fetchone()[0]
        finally:
            first_connection.close()
            second_connection.close()

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)

    def test_connection_enables_foreign_keys_and_row_factory(self):
        connection = self.repository.get_connection()
        try:
            foreign_keys = connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(foreign_keys, 1)
        self.assertIs(connection.row_factory, sqlite3.Row)

    def test_initialization_is_idempotent_and_migration_is_not_duplicated(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        connection = self.repository.get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price
                ) VALUES ('旧形式銘柄', '1111', 10, 500)
                """
            )
            connection.execute(
                """
                INSERT INTO purchases (stock_id, shares, price)
                VALUES (?, 10, 500)
                """,
                (cursor.lastrowid,),
            )
            connection.commit()
        finally:
            connection.close()

        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        connection = self.repository.get_connection()
        try:
            transaction_count = connection.execute(
                "SELECT COUNT(*) FROM transactions"
            ).fetchone()[0]
            purchase_count = connection.execute(
                "SELECT COUNT(*) FROM purchases"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(transaction_count, 1)
        self.assertEqual(purchase_count, 1)

    def test_initialization_closes_its_internal_connection(self):
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        tracking_connection = TrackingConnection(raw_connection)
        self.repository.get_connection = lambda: tracking_connection

        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        self.assertTrue(tracking_connection.closed)
        with self.assertRaises(sqlite3.ProgrammingError):
            raw_connection.execute("SELECT 1")

    def test_initialization_closes_connection_and_reraises_failure(self):
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        failing_connection = FailingInitializationConnection(raw_connection)
        self.repository.get_connection = lambda: failing_connection

        with self.assertRaisesRegex(
            sqlite3.OperationalError,
            "forced initialization failure",
        ):
            self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        self.assertTrue(failing_connection.closed)

    def test_initialization_rolls_back_partial_purchase_migration(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        connection = self.repository.get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price
                ) VALUES ('旧形式銘柄', '1111', 3, 100)
                """
            )
            connection.execute(
                """
                INSERT INTO purchases (stock_id, shares, price)
                VALUES (?, 1, 100)
                """,
                (cursor.lastrowid,),
            )
            connection.execute(
                """
                INSERT INTO purchases (stock_id, shares, price)
                VALUES (?, 2, 100)
                """,
                (cursor.lastrowid,),
            )
            connection.execute(
                """
                CREATE TRIGGER fail_second_purchase_migration
                BEFORE INSERT ON transactions
                WHEN NEW.shares = 2
                BEGIN
                    SELECT RAISE(ABORT, 'forced migration failure');
                END
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError,
            "forced migration failure",
        ):
            self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        connection = self.repository.get_connection()
        try:
            transaction_count = connection.execute(
                "SELECT COUNT(*) FROM transactions"
            ).fetchone()[0]
            purchase_count = connection.execute(
                "SELECT COUNT(*) FROM purchases"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(transaction_count, 0)
        self.assertEqual(purchase_count, 2)

    def test_load_returns_empty_list_for_empty_database(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        self.assertEqual(self.repository.load_stocks(), [])

    def test_loads_stocks_and_transactions_in_id_order(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        connection = self.repository.get_connection()
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
                ) VALUES (10, '先の銘柄', '1111', 3, 200, '[]')
                """
            )
            connection.execute(
                """
                INSERT INTO transactions (
                    id, stock_id, transaction_type, shares, price
                ) VALUES (20, 10, 'buy', 2, 300)
                """
            )
            connection.execute(
                """
                INSERT INTO transactions (
                    id, stock_id, transaction_type, shares, price
                ) VALUES (10, 10, 'buy', 1, 100)
                """
            )
            connection.commit()
        finally:
            connection.close()

        stocks = self.repository.load_stocks()

        self.assertEqual([stock["code"] for stock in stocks], ["1111", "2222"])
        self.assertEqual(
            stocks[0]["transactions"],
            [
                {"type": "buy", "shares": 1, "price": 100},
                {"type": "buy", "shares": 2, "price": 300},
            ],
        )

    def test_load_restores_json_and_optional_values(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        connection = self.repository.get_connection()
        try:
            connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price,
                    current_price, dividend_yield, price_updated_at,
                    dividend_months
                ) VALUES (
                    '配当銘柄', '1111', 1, 100,
                    120, 2.5, '2026-07-31T12:00:00+09:00',
                    '[3, 9]'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price,
                    current_price, dividend_yield, price_updated_at,
                    dividend_months
                ) VALUES (
                    '未更新銘柄', '2222', 0, 0,
                    NULL, NULL, NULL, NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

        stocks = self.repository.load_stocks()

        self.assertEqual(stocks[0]["dividend_months"], [3, 9])
        self.assertEqual(stocks[0]["current_price"], 120)
        self.assertEqual(
            stocks[0]["price_updated_at"],
            "2026-07-31T12:00:00+09:00",
        )
        self.assertEqual(stocks[1]["dividend_months"], [])
        self.assertNotIn("current_price", stocks[1])
        self.assertNotIn("price_updated_at", stocks[1])

    def test_load_returns_multiple_stocks(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        connection = self.repository.get_connection()
        try:
            for code in ("1111", "2222", "3333"):
                connection.execute(
                    """
                    INSERT INTO stocks (
                        name, code, shares, average_price, dividend_months
                    ) VALUES (?, ?, 0, 0, '[]')
                    """,
                    (f"銘柄{code}", code),
                )
            connection.commit()
        finally:
            connection.close()

        self.assertEqual(len(self.repository.load_stocks()), 3)

    def test_repository_does_not_recalculate_position(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        connection = self.repository.get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT INTO stocks (
                    name, code, shares, average_price, dividend_months
                ) VALUES ('未計算銘柄', '1111', 999, 999, '[]')
                """
            )
            connection.execute(
                """
                INSERT INTO transactions (
                    stock_id, transaction_type, shares, price
                ) VALUES (?, 'buy', 10, 100)
                """,
                (cursor.lastrowid,),
            )
            connection.commit()
        finally:
            connection.close()

        stock = self.repository.load_stocks()[0]

        self.assertEqual(stock["shares"], 999)
        self.assertEqual(stock["average_price"], 999)
        self.assertNotIn("realized_profit", stock)

    def test_load_closes_internal_connection_after_success(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        tracking_connection = TrackingConnection(raw_connection)
        self.repository.get_connection = lambda: tracking_connection

        self.repository.load_stocks()

        self.assertTrue(tracking_connection.closed)

    def test_load_closes_internal_connection_after_failure(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        failing_connection = FailingReadConnection(raw_connection)
        self.repository.get_connection = lambda: failing_connection

        with self.assertRaisesRegex(
            sqlite3.OperationalError,
            "forced read failure",
        ):
            self.repository.load_stocks()

        self.assertTrue(failing_connection.closed)

    def test_save_empty_portfolio(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        self.repository.save_stocks([stock_record("削除対象", "1111")])

        self.repository.save_stocks([])

        self.assertEqual(self.repository.load_stocks(), [])

    def test_save_single_stock_with_json_and_nullable_values(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        stock = stock_record("配当銘柄", "1111", 10, 500)
        stock["dividend_months"] = [3, 9]
        stock["current_price"] = None
        stock["price_updated_at"] = None

        self.repository.save_stocks([stock])

        connection = self.repository.get_connection()
        try:
            row = connection.execute(
                """
                SELECT dividend_months, current_price, price_updated_at
                FROM stocks
                """
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(row["dividend_months"], "[3, 9]")
        self.assertIsNone(row["current_price"])
        self.assertIsNone(row["price_updated_at"])

    def test_save_multiple_stocks_and_their_transactions(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        stocks = [
            stock_record(
                "売買銘柄",
                "1111",
                6,
                100,
                [
                    {"type": "buy", "shares": 10, "price": 100},
                    {"type": "sell", "shares": 4, "price": 150},
                ],
            ),
            stock_record("別銘柄", "2222", 2, 200),
        ]

        self.repository.save_stocks(stocks)

        loaded = self.repository.load_stocks()
        self.assertEqual([stock["code"] for stock in loaded], ["1111", "2222"])
        self.assertEqual(loaded[0]["transactions"], stocks[0]["transactions"])
        connection = self.repository.get_connection()
        try:
            relationships = connection.execute(
                """
                SELECT stocks.code, transactions.transaction_type
                FROM transactions
                JOIN stocks ON stocks.id = transactions.stock_id
                ORDER BY transactions.id
                """
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(
            [(row["code"], row["transaction_type"]) for row in relationships],
            [("1111", "buy"), ("1111", "sell"), ("2222", "buy")],
        )

    def test_save_replaces_existing_data_and_clears_purchases(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        self.repository.save_stocks([stock_record("古い銘柄", "1111")])
        connection = self.repository.get_connection()
        try:
            stock_id = connection.execute(
                "SELECT id FROM stocks WHERE code = '1111'"
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO purchases (stock_id, shares, price)
                VALUES (?, 1, 100)
                """,
                (stock_id,),
            )
            connection.commit()
        finally:
            connection.close()

        self.repository.save_stocks([stock_record("新しい銘柄", "2222")])

        connection = self.repository.get_connection()
        try:
            codes = [
                row[0]
                for row in connection.execute(
                    "SELECT code FROM stocks ORDER BY id"
                )
            ]
            purchase_count = connection.execute(
                "SELECT COUNT(*) FROM purchases"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(codes, ["2222"])
        self.assertEqual(purchase_count, 0)

    def test_save_rolls_back_all_changes_on_constraint_failure(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        self.repository.save_stocks([stock_record("保存済み", "1111")])

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_stocks([
                stock_record("重複A", "2222"),
                stock_record("重複B", "2222"),
            ])

        self.assertEqual(
            [stock["code"] for stock in self.repository.load_stocks()],
            ["1111"],
        )

    def test_save_closes_internal_connection_after_success(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        tracking_connection = TrackingConnection(raw_connection)
        self.repository.get_connection = lambda: tracking_connection

        result = self.repository.save_stocks([
            stock_record("保存銘柄", "1111")
        ])

        self.assertIsNone(result)
        self.assertTrue(tracking_connection.closed)

    def test_save_rolls_back_and_closes_after_failure(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        self.repository.save_stocks([stock_record("保存済み", "1111")])
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        tracking_connection = TrackingConnection(raw_connection)
        self.repository.get_connection = lambda: tracking_connection

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_stocks([
                stock_record("重複A", "2222"),
                stock_record("重複B", "2222"),
            ])

        self.assertTrue(tracking_connection.closed)
        verification_connection = sqlite3.connect(self.database_file)
        try:
            codes = [
                row[0]
                for row in verification_connection.execute(
                    "SELECT code FROM stocks"
                )
            ]
        finally:
            verification_connection.close()
        self.assertEqual(codes, ["1111"])

    def test_load_initial_capital_returns_none_when_unset(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        connection = self.repository.get_connection()
        try:
            connection.execute(
                """
                DELETE FROM app_settings
                WHERE setting_key = 'initial_capital'
                """
            )
            connection.commit()
        finally:
            connection.close()

        self.assertIsNone(self.repository.load_initial_capital())

    def test_initial_capital_can_be_saved_loaded_and_overwritten(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        self.repository.save_initial_capital(2_500_000)
        self.assertEqual(self.repository.load_initial_capital(), 2_500_000)

        self.repository.save_initial_capital(3_000_000)
        self.assertEqual(self.repository.load_initial_capital(), 3_000_000)

    def test_initial_capital_supports_decimal_values(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)

        self.repository.save_initial_capital(1_234.5)

        self.assertEqual(self.repository.load_initial_capital(), 1_234.5)

    def test_load_initial_capital_closes_connection_after_success(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        tracking_connection = TrackingConnection(raw_connection)
        self.repository.get_connection = lambda: tracking_connection

        self.repository.load_initial_capital()

        self.assertTrue(tracking_connection.closed)

    def test_load_initial_capital_closes_connection_after_failure(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        failing_connection = FailingSettingConnection(raw_connection)
        self.repository.get_connection = lambda: failing_connection

        with self.assertRaisesRegex(
            sqlite3.OperationalError,
            "forced setting failure",
        ):
            self.repository.load_initial_capital()

        self.assertTrue(failing_connection.closed)

    def test_save_initial_capital_commits_and_closes_connection(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        tracking_connection = TrackingConnection(raw_connection)
        self.repository.get_connection = lambda: tracking_connection

        result = self.repository.save_initial_capital(2_500_000)

        self.assertIsNone(result)
        self.assertTrue(tracking_connection.committed)
        self.assertFalse(tracking_connection.rolled_back)
        self.assertTrue(tracking_connection.closed)

    def test_save_initial_capital_rolls_back_and_closes_after_failure(self):
        self.repository.initialize_database(DEFAULT_INITIAL_CAPITAL)
        raw_connection = sqlite3.connect(self.database_file)
        raw_connection.row_factory = sqlite3.Row
        failing_connection = FailingSettingConnection(raw_connection)
        self.repository.get_connection = lambda: failing_connection

        with self.assertRaisesRegex(
            sqlite3.OperationalError,
            "forced setting failure",
        ):
            self.repository.save_initial_capital(2_500_000)

        self.assertFalse(failing_connection.committed)
        self.assertTrue(failing_connection.rolled_back)
        self.assertTrue(failing_connection.closed)


if __name__ == "__main__":
    unittest.main()
