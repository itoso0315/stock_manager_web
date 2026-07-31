"""テクニカル分析用Plotlyチャートを生成する。"""

import math

import plotly.graph_objects as go


TARGET_DATE_TICK_COUNT = 6


def _adaptive_date_ticks(chart_dates):
    """表示期間に応じて、均等に配置する日付目盛りを返す。"""
    if len(chart_dates) <= TARGET_DATE_TICK_COUNT:
        return list(chart_dates)

    tick_step = math.ceil(
        (len(chart_dates) - 1) / (TARGET_DATE_TICK_COUNT - 1)
    )
    tick_dates = list(chart_dates[::tick_step])
    if tick_dates[-1] != chart_dates[-1]:
        tick_dates.append(chart_dates[-1])
    return tick_dates


def create_technical_chart(
    price_data,
    stock_name,
    show_ma=True,
    show_volume=True,
    show_rsi=False,
    show_bollinger=False,
):
    """ローソク足、移動平均線、出来高を含むチャートを返す。"""
    figure = go.Figure()

    required_ma_windows = (5, 25, 75)
    missing_ma_windows = [
        window
        for window in required_ma_windows
        if f"MA{window}" not in price_data.columns
    ]
    if show_ma and missing_ma_windows:
        price_data = price_data.copy()
        for window in missing_ma_windows:
            price_data[f"MA{window}"] = (
                price_data["Close"].rolling(window=window).mean()
            )

    chart_dates = [timestamp.strftime("%Y-%m-%d") for timestamp in price_data.index]
    tick_dates = _adaptive_date_ticks(price_data.index)
    tick_values = [timestamp.strftime("%Y-%m-%d") for timestamp in tick_dates]

    figure.add_trace(
        go.Candlestick(
            x=chart_dates,
            open=price_data["Open"],
            high=price_data["High"],
            low=price_data["Low"],
            close=price_data["Close"],
            name=stock_name,
            yaxis="y",
        )
    )

    if show_ma:
        figure.add_trace(
            go.Scatter(
                x=chart_dates,
                y=price_data["MA5"],
                mode="lines",
                name="5日線",
                line=dict(
                    color="crimson",
                    width=2,
                ),
                yaxis="y",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=chart_dates,
                y=price_data["MA25"],
                mode="lines",
                name="25日線",
                line=dict(
                    color="orange",
                    width=2,
                ),
                yaxis="y",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=chart_dates,
                y=price_data["MA75"],
                mode="lines",
                name="75日線",
                line=dict(
                    color="royalblue",
                    width=2,
                ),
                yaxis="y",
            )
        )

    if show_bollinger:
        bollinger_middle = price_data["Close"].rolling(window=20).mean()
        bollinger_std = price_data["Close"].rolling(window=20).std()
        for values, name, dash in (
            (bollinger_middle, "ボリンジャー中央線（20日）", "solid"),
            (bollinger_middle + 2 * bollinger_std, "ボリンジャー上限", "dot"),
            (bollinger_middle - 2 * bollinger_std, "ボリンジャー下限", "dot"),
        ):
            figure.add_trace(
                go.Scatter(
                    x=chart_dates,
                    y=values,
                    mode="lines",
                    name=name,
                    line=dict(width=1.5, dash=dash),
                    yaxis="y",
                )
            )

    lower_panel_count = int(show_volume) + int(show_rsi)
    if lower_panel_count == 0:
        price_domain = [0.0, 1.0]
    elif lower_panel_count == 1:
        price_domain = [0.28, 1.0]
    else:
        price_domain = [0.42, 1.0]

    next_yaxis_number = 2
    extra_yaxes = {}

    if show_volume:
        volume_axis = f"y{next_yaxis_number}"
        volume_domain = [0.0, 0.20] if not show_rsi else [0.22, 0.36]
        next_yaxis_number += 1
        volume_colors = []
        previous_close = None
        for close in price_data["Close"]:
            if previous_close is None:
                volume_colors.append("#9CA3AF")
            elif close >= previous_close:
                volume_colors.append("#EF4444")
            else:
                volume_colors.append("#3B82F6")
            previous_close = close

        figure.add_trace(
            go.Bar(
                x=chart_dates,
                y=price_data["Volume"],
                name="出来高",
                opacity=0.35,
                marker=dict(
                    color=volume_colors,
                    line=dict(width=0),
                ),
                yaxis=volume_axis,
            )
        )
        extra_yaxes[f"yaxis{volume_axis[1:]}"] = dict(
            title="出来高",
            domain=volume_domain,
            anchor="x",
        )

    if show_rsi:
        rsi_axis = f"y{next_yaxis_number}"
        rsi_domain = [0.0, 0.20] if not show_volume else [0.0, 0.16]
        close_delta = price_data["Close"].diff()
        average_gain = close_delta.clip(lower=0).rolling(window=14).mean()
        average_loss = (-close_delta.clip(upper=0)).rolling(window=14).mean()
        relative_strength = average_gain / average_loss
        rsi = 100 - (100 / (1 + relative_strength))

        figure.add_trace(
            go.Scatter(
                x=chart_dates,
                y=rsi,
                mode="lines",
                name="RSI",
                yaxis=rsi_axis,
            )
        )
        for level in (70, 30):
            figure.add_trace(
                go.Scatter(
                    x=chart_dates,
                    y=[level] * len(chart_dates),
                    mode="lines",
                    name=f"RSI {level}",
                    line=dict(color="#9CA3AF", width=1, dash="dash"),
                    showlegend=False,
                    hoverinfo="skip",
                    yaxis=rsi_axis,
                )
            )
        extra_yaxes[f"yaxis{rsi_axis[1:]}"] = dict(
            title="RSI",
            domain=rsi_domain,
            range=[0, 100],
            anchor="x",
        )

    figure.update_layout(
        title=f"{stock_name} 6か月チャート",
        height=750,
        xaxis=dict(
            title="日付",
            type="category",
            categoryorder="array",
            categoryarray=chart_dates,
            tickmode="array",
            tickvals=tick_values,
            ticktext=[date.strftime("%Y/%m/%d") for date in tick_dates],
            tickangle=0,
            tickfont=dict(size=10),
            automargin=True,
            hoverformat="%Y/%m/%d",
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            title="株価",
            domain=price_domain,
        ),
        legend=dict(
            orientation="h",
            y=1.08,
            x=0,
        ),
        bargap=0,
        **extra_yaxes,
    )

    return figure
