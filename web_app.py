from datetime import datetime
import unicodedata

import streamlit as st
import plotly.express as px
from streamlit_sortables import sort_items

from api import (
    JAPANESE_STOCK_CODE_PATTERN,
    fetch_current_price,
    fetch_stock_info,
    get_yahoo_symbol,
)
from database import load_initial_capital, load_stocks, save_stocks
from services.portfolio_service import (
    build_allocation_data,
    calculate_annual_dividend,
    calculate_asset_ratios,
    calculate_stock_value,
    calculate_total_assets,
    calculate_unrealized_profit,
)
from stock import (
    cash_balance as calculate_cash_balance,
    create_candidate,
    normalize_input,
    set_share_count,
)
from web_navigation import render_sidebar_navigation


st.set_page_config(
    page_title="MyStocks",
    page_icon="📈",
    layout="wide",
)

render_sidebar_navigation()

st.markdown(
    """
    <style>
    html, body, [class*="css"], [data-testid="stAppViewContainer"] {
        font-family:
            Inter, "Noto Sans JP", "Helvetica Neue", Arial, sans-serif;
    }

    h1, h2, h3, [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {
        font-family:
            Inter, "Noto Sans JP", "Helvetica Neue", Arial, sans-serif;
        letter-spacing: -0.03em;
    }

    h1 {
        font-weight: 800;
    }

    .app-title {
        margin: 0.25rem 0 1.5rem;
        text-align: center;
        font-family:
            Inter, "Noto Sans JP", "Helvetica Neue", Arial, sans-serif;
        font-size: clamp(3rem, 6vw, 5rem);
        font-weight: 850;
        line-height: 1;
        letter-spacing: -0.06em;
        background: linear-gradient(120deg, #111827 20%, #2563eb 80%);
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
    }

    [data-testid="stMetricValue"] {
        font-size: clamp(1.5rem, 2vw, 2.4rem) !important;
        font-weight: 700;
        line-height: 1.2;
        white-space: nowrap;
    }

    [data-testid="stMetricLabel"],
    .dashboard-profit-label {
        font-size: 1rem;
        font-weight: 600;
    }

    .dashboard-profit-value {
        font-size: clamp(1.5rem, 2vw, 2.4rem);
        font-weight: 700;
        line-height: 1.2;
        margin: 0;
        white-space: nowrap;
    }

    .st-key-dashboard_metrics {
        container-name: dashboard-metrics;
        container-type: inline-size;
    }

    @container dashboard-metrics (max-width: 999px) {
        [data-testid="stMetricValue"],
        .dashboard-profit-value {
            font-size: 1.5rem !important;
        }
    }

    @container dashboard-metrics (min-width: 1000px) and (max-width: 1349px) {
        [data-testid="stMetricValue"],
        .dashboard-profit-value {
            font-size: 1.85rem !important;
        }
    }

    @container dashboard-metrics (min-width: 1350px) {
        [data-testid="stMetricValue"],
        .dashboard-profit-value {
            font-size: 2.3rem !important;
        }
    }

    [data-testid="stNumberInput"] input {
        font-size: 1.25rem;
        font-weight: 600;
    }

    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }

    [data-testid="stTabs"] [data-baseweb="tab"] {
        min-width: 10rem;
        height: 3rem;
        padding: 0 1.25rem;
        border-radius: 0.75rem 0.75rem 0 0;
        font-size: 1rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# ダッシュボード
# =========================

st.markdown('<div class="app-title">MyStocks</div>', unsafe_allow_html=True)
st.subheader("本日の資産状況")


# SQLiteからデータを読み込む
stocks = load_stocks()
initial_capital = load_initial_capital()

# ページのリフレッシュ時に現在株価を更新する
price_update_failures = []
prices_updated = False

for stock in stocks:
    try:
        stock["current_price"] = fetch_current_price(stock["code"])
        stock["price_updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        prices_updated = True
    except RuntimeError:
        price_update_failures.append(stock["name"])

if prices_updated:
    save_stocks(stocks)

if price_update_failures:
    st.warning(
        "現在値を更新できなかった銘柄: "
        + "、".join(price_update_failures)
        + "（保存済みの現在値を表示しています）"
    )


# 保有株の評価額
stock_value = calculate_stock_value(stocks)

# 現金残高
cash_balance = calculate_cash_balance(stocks, initial_capital)

# 総資産
total_assets = calculate_total_assets(cash_balance, stock_value)

# 評価損益
profit_loss = calculate_unrealized_profit(stocks)

# 年間配当見込み
annual_dividend = calculate_annual_dividend(stocks)


dashboard_metrics = st.container(key="dashboard_metrics")
col1, col2, col3, col4 = dashboard_metrics.columns(4)

with col1:
    st.metric("総資産", f"{total_assets:,.0f}円")

with col2:
    profit_loss_color = (
        "#16a34a" if profit_loss > 0
        else "#dc2626" if profit_loss < 0
        else "inherit"
    )
    st.markdown(
        f"""
        <div>
            <p class="dashboard-profit-label"
               style="margin-bottom: 0.25rem;">評価損益</p>
            <p class="dashboard-profit-value"
               style="color: {profit_loss_color};">{profit_loss:+,.0f}円</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.metric("現金残高", f"{cash_balance:,.0f}円")

with col4:
    st.metric("年間配当", f"{annual_dividend:,.0f}円")

st.divider()  
stock_tab, allocation_tab, buying_power_tab = st.tabs(
    ["📋 銘柄管理", "🥧 資産配分", "💰 余力資金"]
)

# =========================
# 保有銘柄一覧
# =========================

with stock_tab:
    st.subheader("📋 銘柄管理")
    st.caption(
        "過去保有銘柄を保有銘柄へ移すと購入。"
        "保有銘柄を過去保有銘柄へ移すと全売却。"
    )

    with st.expander("➕ 新しい銘柄を追加", expanded=not stocks):
        with st.form("add_stock_form", clear_on_submit=True):
            stock_code_input = st.text_input(
                "日本株の銘柄コード",
                placeholder="例：7203",
                max_chars=4,
                help="4文字の銘柄コードを入力してください。",
            )
            add_stock_submitted = st.form_submit_button(
                "銘柄を追加", type="primary", width="stretch"
            )

        if add_stock_submitted:
            normalized_code = normalize_input(stock_code_input).strip().upper()
            existing_codes = {stock["code"] for stock in stocks}

            if not JAPANESE_STOCK_CODE_PATTERN.fullmatch(normalized_code):
                st.error("銘柄コードを4文字で入力してください。")
            elif normalized_code in existing_codes:
                st.warning("この銘柄はすでに登録されています。")
            else:
                try:
                    with st.spinner("銘柄情報を取得中…"):
                        stock_info = fetch_stock_info(normalized_code)
                except RuntimeError as error:
                    st.error(f"銘柄情報を取得できませんでした。{error}")
                else:
                    stocks.append(create_candidate(normalized_code, stock_info))
                    save_stocks(stocks)
                    st.session_state["stock_board_version"] = (
                        st.session_state.get("stock_board_version", 0) + 1
                    )
                    st.session_state["stock_added_message"] = (
                        f"{stock_info['name']}（{normalized_code}）を追加しました。"
                    )
                    st.rerun()

    stock_added_message = st.session_state.pop("stock_added_message", None)
    if stock_added_message:
        st.success(stock_added_message)


def fit_text(text, width):
    """全角文字を考慮して、表示幅を揃えた文字列を返す。"""
    fitted_text = ""
    display_width = 0

    for character in text:
        character_width = (
            2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        )
        if display_width + character_width > width:
            break
        fitted_text += character
        display_width += character_width

    return fitted_text + " " * (width - display_width)


def stock_card_label(
    stock,
    include_average_price=True,
    include_shares=True,
    include_evaluation=True,
    name_width=22,
):
    current_price = stock.get("current_price", stock["average_price"])
    stock_name = fit_text(stock["name"], name_width)
    evaluation_value = current_price * stock["shares"]

    profit_loss = (current_price - stock["average_price"]) * stock["shares"]

    if stock["average_price"] > 0:
        profit_rate = (
            (current_price - stock["average_price"])
            / stock["average_price"]
            * 100
        )
    else:
        profit_rate = 0

    profit_marker = "🟢" if profit_loss >= 0 else "🔴"

    fields = [stock_name]
    if include_average_price:
        fields.append(f"{stock['average_price']:>7,.0f}円")
    fields.append(f"{current_price:>7,.0f}円")
    if include_shares:
        fields.append(f"{stock['shares']:>5,}株")
    if include_evaluation:
        fields.append(f"{evaluation_value:>9,.0f}円")
        fields.append(f"{profit_marker}{profit_loss:>+8,.0f}円")
        fields.append(f"{profit_rate:+5.1f}%")
    return "\t".join(fields)


def reset_stock_board():
    st.session_state["stock_board_version"] = (
        st.session_state.get("stock_board_version", 0) + 1
    )


@st.dialog("購入内容の確認")
def show_purchase_dialog(stock):
    current_price = stock.get("current_price", stock["average_price"])

    st.write(f"**{stock['name']}（{stock['code']}）**")
    st.write(f"購入単価：{current_price:,.0f}円")
    purchase_shares = st.number_input(
        "購入株数",
        min_value=1,
        value=100,
        step=1,
        format="%d",
    )
    st.caption(f"購入金額：{current_price * purchase_shares:,.0f}円")

    cancel_col, purchase_col = st.columns(2)
    with cancel_col:
        if st.button("キャンセル", width="stretch"):
            st.session_state.pop("pending_purchase_code", None)
            reset_stock_board()
            st.rerun()
    with purchase_col:
        if st.button("購入を確定", type="primary", width="stretch"):
            set_share_count(
                stock,
                stock["shares"] + int(purchase_shares),
                current_price,
            )
            save_stocks(stocks)
            st.session_state.pop("pending_purchase_code", None)
            reset_stock_board()
            st.session_state["purchase_message"] = (
                f"{stock['name']}を{int(purchase_shares):,}株購入しました。"
            )
            st.rerun()


@st.dialog("全売却の確認")
def show_sell_all_dialog(stock):
    current_price = stock.get("current_price", stock["average_price"])
    sale_value = current_price * stock["shares"]

    st.write(f"**{stock['name']}（{stock['code']}）**")
    st.write(f"保有数：{stock['shares']:,}株")
    st.write(f"売却単価：{current_price:,.0f}円")
    st.caption(f"売却予定額：{sale_value:,.0f}円")
    st.warning("この銘柄を全売却し、過去保有銘柄へ移動します。")

    cancel_col, sale_col = st.columns(2)
    with cancel_col:
        if st.button("キャンセル", key="cancel_sale", width="stretch"):
            st.session_state.pop("pending_sale_code", None)
            reset_stock_board()
            st.rerun()
    with sale_col:
        if st.button(
            "全売却を確定",
            key="confirm_sale",
            type="primary",
            width="stretch",
        ):
            sold_shares = stock["shares"]
            set_share_count(stock, 0, current_price)
            save_stocks(stocks)
            st.session_state.pop("pending_sale_code", None)
            reset_stock_board()
            st.session_state["sale_message"] = (
                f"{stock['name']}を{sold_shares:,}株すべて売却しました。"
            )
            st.rerun()


for message_key in ("purchase_message", "sale_message"):
    message = st.session_state.pop(message_key, None)
    if message:
        stock_tab.success(message)

held_stocks = [stock for stock in stocks if stock["shares"] > 0]
past_stocks = [stock for stock in stocks if stock["shares"] == 0]
held_labels = [stock_card_label(stock) for stock in held_stocks]
past_labels = [
    stock_card_label(
        stock,
        include_average_price=False,
        include_shares=True,
        include_evaluation=False,
        name_width=30,
    )
    for stock in past_stocks
]
label_to_code = {
    stock_card_label(stock): stock["code"]
    for stock in held_stocks
}
label_to_code.update({
    stock_card_label(
        stock,
        include_average_price=False,
        include_shares=True,
        include_evaluation=False,
        name_width=30,
    ): stock["code"]
    for stock in past_stocks
})
table_header = (
    "\t".join(
        [
            fit_text("銘柄名", 22),
            "平均取得",
            "現在値",
            "保有数",
            "評価額",
            "評価損益",
            "損益率",
        ]
    )
)
past_table_header = (
    "\t".join(
        [
            fit_text("銘柄名", 30),
            "現在値",
            "保有数",
        ]
    )
)

with stock_tab:
    sorted_stock_lists = sort_items(
        [
            {"header": "保有銘柄", "items": held_labels},
            {"header": "過去保有銘柄", "items": past_labels},
        ],
        multi_containers=True,
        direction="vertical",
        key=f"stock_board_{st.session_state.get('stock_board_version', 0)}",
        custom_style="""
    .sortable-component.vertical {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 1rem;
        align-items: stretch;
        width: 100%;
        overflow-x: hidden;
    }
    .sortable-component.vertical .sortable-container {
        display: flex;
        flex-direction: column;
        width: 100%;
        min-width: 0;
        height: 24rem;
        min-height: 24rem;
        padding: 0.75rem !important;
        border: 1px solid #d8dee9;
        border-radius: 12px;
        box-sizing: border-box;
        overflow: hidden;
    }
    .sortable-container:first-of-type {
        border-color: #bbdfc8;
        background: #edf8f1;
    }
    .sortable-container:nth-of-type(2) {
        border-color: #f1d2ae;
        background: #fff7ed;
    }
    .sortable-container-header {
        padding: 0.35rem 0.5rem 0.75rem;
        font-weight: 700;
        background: transparent;
    }
    .sortable-container-body {
        flex: 1;
        width: 100%;
        height: calc(100% - 3rem);
        min-height: 0;
        padding: 0;
        box-sizing: border-box;
        overflow-x: hidden;
        overflow-y: scroll !important;
        overscroll-behavior: contain;
        -webkit-overflow-scrolling: touch;
        scrollbar-gutter: stable;
    }
    .sortable-container-body::before {
        content: "__TABLE_HEADER__";
        position: sticky;
        top: 0;
        z-index: 2;
        display: block;
        width: 100%;
        min-width: 0;
        padding: 0.55rem 0.7rem;
        border-bottom: 2px solid #cbd5e1;
        box-sizing: border-box;
        background: #f8fafc;
        color: #475569;
        font-family:
            "Osaka-Mono", "Noto Sans Mono CJK JP", "MS Gothic",
            "SFMono-Regular", Consolas, monospace;
        font-size: 0.9rem;
        line-height: 1.35;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        letter-spacing: 0;
        text-align: left;
        tab-size: 12;
        white-space: pre;
    }
    .sortable-component.vertical
        .sortable-container:nth-of-type(2)
        .sortable-container-body::before {
        content: "__PAST_TABLE_HEADER__" !important;
    }
    .sortable-container:first-of-type .sortable-container-body {
        background: #e3f3e9;
    }
    .sortable-container:nth-of-type(2) .sortable-container-body {
        background: #fcebd8;
    }
    .sortable-container:nth-of-type(2) .sortable-container-body::before,
    .sortable-container:nth-of-type(2) .sortable-item {
        tab-size: 12 !important;
    }
    .sortable-item {
        width: 100%;
        min-width: 0;
        max-width: 100%;
        height: auto !important;
        min-height: 2.8rem;
        margin: 0;
        padding: 0.5rem 0.7rem !important;
        border: 0;
        border-bottom: 1px solid #dbe3ec;
        border-radius: 0;
        background-color: white !important;
        color: #172033 !important;
        box-sizing: border-box;
        cursor: grab;
        touch-action: pan-y;
        font-family:
            "Osaka-Mono", "Noto Sans Mono CJK JP", "MS Gothic",
            "SFMono-Regular", Consolas, monospace;
        font-size: 0.9rem;
        line-height: 1.35;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        letter-spacing: 0;
        text-align: left !important;
        tab-size: 12;
        white-space: pre;
        overflow: hidden;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
        transition:
            color 0.15s ease,
            background-color 0.15s ease,
            border-color 0.15s ease;
    }
    .sortable-item:hover {
        height: auto !important;
        min-height: 2.8rem;
        padding: 0.5rem 0.7rem !important;
        background-color: #2563eb !important;
        color: white !important;
        border-color: #2563eb;
        font-size: 0.9rem;
        line-height: 1.35;
    }
        """
        .replace("__TABLE_HEADER__", table_header)
        .replace("__PAST_TABLE_HEADER__", past_table_header),
    )

    with st.expander("📈 Yahooチャートを開く"):
        st.markdown("**保有銘柄**")
        if held_stocks:
            for stock in held_stocks:
                yahoo_symbol = get_yahoo_symbol(stock["code"])
                chart_url = (
                    f"https://finance.yahoo.co.jp/quote/{yahoo_symbol}/chart"
                )
                st.link_button(
                    f"📈 {stock['name']}（{stock['code']}）",
                    chart_url,
                    width="stretch",
                )
        else:
            st.caption("保有銘柄はありません。")

        st.divider()
        st.markdown("**過去保有銘柄**")
        if past_stocks:
            for stock in past_stocks:
                yahoo_symbol = get_yahoo_symbol(stock["code"])
                chart_url = (
                    f"https://finance.yahoo.co.jp/quote/{yahoo_symbol}/chart"
                )
                st.link_button(
                    f"📈 {stock['name']}（{stock['code']}）",
                    chart_url,
                    width="stretch",
                )
        else:
            st.caption("過去保有銘柄はありません。")

dropped_into_holdings = [
    label
    for label in sorted_stock_lists[0]["items"]
    if label not in held_labels
]
dropped_into_past = [
    label
    for label in sorted_stock_lists[1]["items"]
    if label not in past_labels
]

has_pending_trade = (
    "pending_purchase_code" in st.session_state
    or "pending_sale_code" in st.session_state
)

if dropped_into_holdings and not has_pending_trade:
    st.session_state["pending_purchase_code"] = label_to_code[dropped_into_holdings[0]]
elif dropped_into_past and not has_pending_trade:
    st.session_state["pending_sale_code"] = label_to_code[dropped_into_past[0]]

pending_purchase_code = st.session_state.get("pending_purchase_code")
pending_sale_code = st.session_state.get("pending_sale_code")

if pending_purchase_code:
    pending_stock = next(
        (stock for stock in stocks if stock["code"] == pending_purchase_code),
        None,
    )
    if pending_stock is not None:
        show_purchase_dialog(pending_stock)
    else:
        st.session_state.pop("pending_purchase_code", None)
elif pending_sale_code:
    pending_stock = next(
        (stock for stock in stocks if stock["code"] == pending_sale_code),
        None,
    )
    if pending_stock is not None:
        show_sell_all_dialog(pending_stock)
    else:
        st.session_state.pop("pending_sale_code", None)

# =========================
# 保有比率グラフ
# =========================

with allocation_tab:
    st.subheader("🥧 資産配分")

    allocation_held_stocks = [
        stock for stock in stocks if stock["shares"] > 0
    ]
    largest_holding = max(
        allocation_held_stocks,
        key=lambda stock: (
            stock["shares"]
            * stock.get("current_price", stock["average_price"])
        ),
        default=None,
    )

    investment_col, count_col, largest_col = st.columns(3)
    with investment_col:
        st.metric("投資中の資産", f"{stock_value:,.0f}円")
    with count_col:
        st.metric("保有銘柄数", f"{len(allocation_held_stocks)}銘柄")
    with largest_col:
        if largest_holding is not None:
            largest_holding_value = (
                largest_holding["shares"]
                * largest_holding.get(
                    "current_price",
                    largest_holding["average_price"],
                )
            )
            largest_holding_ratio = (
                largest_holding_value / stock_value * 100
                if stock_value > 0
                else 0
            )
            largest_holding_display = (
                f"{largest_holding['name']} "
                f"{largest_holding_ratio:.1f}%"
            )
        else:
            largest_holding_display = "該当なし"
        st.metric("最大保有銘柄", largest_holding_display)

    st.divider()

    chart_data = build_allocation_data(stocks, cash_balance)

    st.write("銘柄別の保有比率")

    if chart_data:
        chart_labels = [
            name if len(name) <= 8 else f"{name[:8]}…"
            for name in chart_data
        ]
        fig = px.pie(
            names=chart_data.keys(),
            values=chart_data.values(),
            hole=0.55,
        )

        fig.update_traces(
            customdata=chart_labels,
            textfont_size=14,
            textposition="outside",
            textinfo="none",
            texttemplate="%{customdata}<br>%{percent}",
            hovertemplate=(
                "%{label}<br>"
                "%{value:,.0f}円<br>"
                "%{percent}<extra></extra>"
            ),
            insidetextorientation="horizontal",
            automargin=True,
            domain={"x": [0.16, 0.84], "y": [0.16, 0.84]},
        )

        fig.update_layout(
            font={"size": 16},
            height=640,
            showlegend=False,
            margin={"t": 70, "r": 100, "b": 90, "l": 100},
            uniformtext={"minsize": 10, "mode": "show"},
            annotations=[
                {
                    "text": (
                        f"総資産<br>"
                        f"<b>{total_assets:,.0f}円</b>"
                    ),
                    "x": 0.5,
                    "y": 0.5,
                    "font": {
                        "size": 20,
                    },
                    "showarrow": False,
                }
            ],
        )

        st.plotly_chart(fig, width="stretch")


    else:
        st.info("表示できる資産データがありません。")

# =========================
# 余力資金
# =========================

with buying_power_tab:
    st.subheader("💰 余力資金")

    cash_ratio, _ = calculate_asset_ratios(
        cash_balance,
        stock_value,
    )

    st.metric(
        "買付余力",
        f"{cash_balance:,.0f}円",
    )
    st.caption(f"現金比率 {cash_ratio:.1f}%")

    st.divider()
    st.markdown("### この資金で買える株数")
    st.caption("現在の買付余力を、1銘柄だけに使った場合の目安です。")

    purchasable_stocks = [
        stock
        for stock in stocks
        if stock.get("current_price", 0) > 0
    ]

    if purchasable_stocks:
        for stock in purchasable_stocks:
            current_price = stock.get(
                "current_price",
                stock["average_price"],
            )
            purchasable_shares = int(cash_balance // current_price)

            stock_col, shares_col = st.columns([3, 1])
            with stock_col:
                st.write(f"**{stock['name']}（{stock['code']}）**")
                st.caption(f"現在値 {current_price:,.0f}円")
            with shares_col:
                st.metric("購入可能", f"{purchasable_shares:,}株")
    else:
        st.info("購入可能株数を計算できる銘柄がありません。")
