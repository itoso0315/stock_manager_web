import unittest

import pandas as pd

from analytics.indicators import add_moving_averages, select_display_period


class TechnicalIndicatorTest(unittest.TestCase):
    def setUp(self):
        self.price_data = pd.DataFrame(
            {"Close": range(1, 301)},
            index=pd.bdate_range("2025-01-01", periods=300),
        )

    def test_25_day_moving_average(self):
        calculated = add_moving_averages(self.price_data)

        self.assertTrue(pd.isna(calculated["MA25"].iloc[23]))
        self.assertEqual(calculated["MA25"].iloc[24], 13)
        self.assertEqual(calculated["MA25"].iloc[-1], 288)

    def test_75_day_moving_average(self):
        calculated = add_moving_averages(self.price_data)

        self.assertTrue(pd.isna(calculated["MA75"].iloc[73]))
        self.assertEqual(calculated["MA75"].iloc[74], 38)
        self.assertEqual(calculated["MA75"].iloc[-1], 263)

    def test_fewer_than_75_trading_days_keeps_ma75_nan(self):
        short_data = self.price_data.iloc[:74]

        calculated = add_moving_averages(short_data)

        self.assertTrue(calculated["MA75"].isna().all())

    def test_calculates_with_history_before_slicing_display_period(self):
        calculated = add_moving_averages(self.price_data)
        displayed = select_display_period(calculated, months=6)
        first_position = calculated.index.get_loc(displayed.index[0])
        expected_ma75 = (
            calculated["Close"]
            .iloc[first_position - 74:first_position + 1]
            .mean()
        )

        self.assertGreater(first_position, 74)
        self.assertFalse(pd.isna(displayed["MA75"].iloc[0]))
        self.assertEqual(displayed["MA75"].iloc[0], expected_ma75)

    def test_selects_six_calendar_months_from_latest_data_date(self):
        calculated = add_moving_averages(self.price_data)

        displayed = select_display_period(calculated, months=6)

        expected_cutoff = calculated.index.max() - pd.DateOffset(months=6)
        self.assertTrue((displayed.index >= expected_cutoff).all())
        self.assertLess(displayed.index[0] - expected_cutoff, pd.Timedelta(days=4))
        self.assertEqual(displayed.index[-1], calculated.index[-1])

    def test_empty_display_period_returns_an_independent_empty_frame(self):
        empty = self.price_data.iloc[:0]

        displayed = select_display_period(empty, months=6)

        self.assertTrue(displayed.empty)
        self.assertIsNot(displayed, empty)


if __name__ == "__main__":
    unittest.main()
