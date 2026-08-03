import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analytics.indicators import add_moving_averages, select_display_period
from analytics.technical_chart import create_technical_chart
from database import load_stocks
from services.market_data_service import fetch_price_history, get_yahoo_symbol
from web_navigation import render_sidebar_navigation


PERIOD_OPTIONS = {
    "1か月": 1,
    "3か月": 3,
    "6か月": 6,
    "1年": 12,
}
DEFAULT_PERIOD = "6か月"
HISTORY_PERIOD = "1y"
PRICE_INTERVAL = "1d"


st.set_page_config(
    page_title="MyStocks",
    page_icon="📈",
    layout="wide",
)

render_sidebar_navigation()

st.markdown(
    """
    <style>
    .technical-title {
        margin: 0.5rem 0 2rem;
        text-align: center;
        font-size: clamp(2.75rem, 5vw, 4.5rem);
        font-weight: 800;
        line-height: 1.1;
        letter-spacing: -0.04em;
    }
    </style>
    <div class="technical-title">📈 Technical Analysis</div>
    """,
    unsafe_allow_html=True,
)

portfolio_stocks = sorted(
    load_stocks(),
    key=lambda stock: stock["shares"] == 0,
)

if not portfolio_stocks:
    st.info(
        "チャートを表示できる銘柄がまだ登録されていません。"
    )
else:
    stock_options = {
        f"{stock['name']}（{stock['code']}）": stock
        for stock in portfolio_stocks
    }
    selected_label = st.selectbox(
        "銘柄を選択",
        list(stock_options),
    )
    selected_stock = stock_options[selected_label]
    selected_symbol = get_yahoo_symbol(selected_stock["code"])

    st.markdown("**期間**")
    selected_period = st.radio(
        "期間",
        list(PERIOD_OPTIONS),
        index=list(PERIOD_OPTIONS).index(DEFAULT_PERIOD),
        horizontal=True,
        label_visibility="collapsed",
    )

    st.markdown("**表示**")
    ma_col, volume_col, rsi_col, bollinger_col = st.columns(4)
    with ma_col:
        show_ma = st.checkbox("移動平均線", value=True)
    with volume_col:
        show_volume = st.checkbox("出来高", value=True)
    with rsi_col:
        show_rsi = st.checkbox("RSI", value=False)
    with bollinger_col:
        show_bollinger = st.checkbox(
            "ボリンジャーバンド",
            value=False,
        )

    price_history = fetch_price_history(
        selected_symbol,
        period=HISTORY_PERIOD,
        interval=PRICE_INTERVAL,
    )

    if price_history.empty:
        st.error("株価データを取得できませんでした。")
    else:
        price_history = add_moving_averages(price_history)
        display_data = select_display_period(
            price_history,
            months=PERIOD_OPTIONS[selected_period],
        )
        figure = create_technical_chart(
            display_data,
            selected_stock["name"],
            show_ma=show_ma,
            show_volume=show_volume,
            show_rsi=show_rsi,
            show_bollinger=show_bollinger,
        )
        figure.update_layout(title=None)
        st.plotly_chart(
            figure,
            width="stretch",
        )
