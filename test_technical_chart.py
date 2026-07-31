import unittest

import pandas as pd

from analytics.technical_chart import create_technical_chart


class TechnicalChartTest(unittest.TestCase):
    def setUp(self):
        index = pd.bdate_range("2026-01-05", periods=5)
        self.price_data = pd.DataFrame(
            {
                "Open": [100, 102, 101, 104, 106],
                "High": [104, 105, 106, 108, 110],
                "Low": [99, 100, 100, 103, 105],
                "Close": [103, 101, 105, 107, 108],
                "Volume": [1000, 1200, 900, 1500, 1300],
                "MA25": [101, 102, 103, 104, 105],
                "MA75": [98, 99, 100, 101, 102],
            },
            index=index,
        )

    def test_contains_candlestick_moving_averages_and_volume(self):
        figure = create_technical_chart(self.price_data, "テスト株")

        self.assertEqual(len(figure.data), 5)
        self.assertEqual(
            [(trace.type, trace.name) for trace in figure.data],
            [
                ("candlestick", "テスト株"),
                ("scatter", "5日線"),
                ("scatter", "25日線"),
                ("scatter", "75日線"),
                ("bar", "出来高"),
            ],
        )
        self.assertEqual(figure.data[1].line.color, "crimson")
        self.assertEqual(figure.data[2].line.color, "orange")
        self.assertEqual(figure.data[3].line.color, "royalblue")
        self.assertEqual(figure.data[4].yaxis, "y2")
        self.assertEqual(figure.data[4].opacity, 0.35)
        self.assertEqual(
            tuple(figure.data[0].x),
            tuple(self.price_data.index.strftime("%Y-%m-%d")),
        )

    def test_preserves_main_chart_layout(self):
        figure = create_technical_chart(self.price_data, "テスト株")

        self.assertEqual(figure.layout.title.text, "テスト株 6か月チャート")
        self.assertEqual(figure.layout.height, 750)
        self.assertEqual(figure.layout.xaxis.title.text, "日付")
        self.assertEqual(figure.layout.xaxis.type, "category")
        self.assertEqual(figure.layout.xaxis.categoryorder, "array")
        self.assertEqual(
            tuple(figure.layout.xaxis.categoryarray),
            tuple(self.price_data.index.strftime("%Y-%m-%d")),
        )
        self.assertEqual(figure.layout.xaxis.tickmode, "array")
        self.assertEqual(
            tuple(figure.layout.xaxis.tickvals),
            tuple(self.price_data.index.strftime("%Y-%m-%d")),
        )
        self.assertEqual(
            tuple(figure.layout.xaxis.ticktext),
            tuple(self.price_data.index.strftime("%Y/%m/%d")),
        )
        self.assertEqual(figure.layout.xaxis.tickangle, 0)
        self.assertEqual(figure.layout.xaxis.tickfont.size, 10)
        self.assertTrue(figure.layout.xaxis.automargin)
        self.assertEqual(figure.layout.xaxis.hoverformat, "%Y/%m/%d")
        self.assertFalse(figure.layout.xaxis.rangeslider.visible)
        self.assertEqual(tuple(figure.layout.yaxis.domain), (0.28, 1.0))
        self.assertEqual(figure.layout.yaxis.title.text, "株価")
        self.assertEqual(tuple(figure.layout.yaxis2.domain), (0.0, 0.2))
        self.assertEqual(figure.layout.yaxis2.title.text, "出来高")
        self.assertEqual(figure.layout.yaxis2.anchor, "x")
        self.assertEqual(figure.layout.legend.orientation, "h")
        self.assertEqual(figure.layout.legend.y, 1.08)
        self.assertEqual(figure.layout.legend.x, 0)
        self.assertEqual(figure.layout.bargap, 0)

    def test_only_existing_trading_dates_are_axis_categories(self):
        price_data = self.price_data.drop(pd.Timestamp("2026-01-07"))

        figure = create_technical_chart(price_data, "テスト株")

        self.assertEqual(
            tuple(figure.layout.xaxis.categoryarray),
            tuple(price_data.index.strftime("%Y-%m-%d")),
        )
        self.assertNotIn("2026-01-07", figure.layout.xaxis.categoryarray)

    def test_date_ticks_adapt_to_the_selected_display_period(self):
        price_data = pd.concat([self.price_data] * 8, ignore_index=True)
        price_data.index = pd.bdate_range(
            "2026-01-05",
            periods=len(price_data),
        )

        figure = create_technical_chart(price_data, "テスト株")

        self.assertLessEqual(len(figure.layout.xaxis.tickvals), 6)
        self.assertEqual(
            figure.layout.xaxis.tickvals[0],
            price_data.index[0].strftime("%Y-%m-%d"),
        )
        self.assertEqual(
            figure.layout.xaxis.tickvals[-1],
            price_data.index[-1].strftime("%Y-%m-%d"),
        )


if __name__ == "__main__":
    unittest.main()
