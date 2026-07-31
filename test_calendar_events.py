import unittest
from datetime import date

from calendar_events import build_month_events, rights_dates


class RightsCalendarTest(unittest.TestCase):
    def test_calculates_last_and_ex_dates_using_business_days(self):
        dates = rights_dates(2026, 3)

        self.assertEqual(dates["record_date"], date(2026, 3, 31))
        self.assertEqual(dates["ex_date"], date(2026, 3, 30))
        self.assertEqual(dates["last_day"], date(2026, 3, 27))

    def test_only_includes_held_stocks_for_matching_month(self):
        stocks = [
            {"name": "三菱商事", "code": "8058", "shares": 10, "dividend_months": [3, 9]},
            {"name": "候補株", "code": "1234", "shares": 0, "dividend_months": [3]},
        ]

        events = build_month_events(stocks, 2026, 3)

        self.assertEqual(events[date(2026, 3, 27)][0]["name"], "三菱商事")
        self.assertTrue(all(event["name"] != "候補株" for items in events.values() for event in items))


if __name__ == "__main__":
    unittest.main()
