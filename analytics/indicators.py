"""株価データへテクニカル指標を追加し、表示期間を選択する。"""

import pandas as pd


def add_moving_averages(price_data, windows=(25, 75)):
    """終値を基に指定日数の単純移動平均列を追加したコピーを返す。"""
    calculated = price_data.copy()
    for window in windows:
        calculated[f"MA{window}"] = (
            calculated["Close"]
            .rolling(window=window)
            .mean()
        )
    return calculated


def select_display_period(price_data, months=6):
    """データの最新日を基準に、直近の暦月数に該当する行を返す。"""
    if price_data.empty:
        return price_data.copy()

    cutoff = price_data.index.max() - pd.DateOffset(months=months)
    return price_data.loc[price_data.index >= cutoff].copy()
