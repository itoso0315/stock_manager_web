from datetime import datetime
from html import escape

import streamlit as st
import plotly.express as px

from api import (
    fetch_current_price,
    fetch_stock_info,
    get_yahoo_symbol,
)
from database import (
    load_initial_capital,
    load_stocks,
    save_initial_capital,
    save_stocks,
)
from services.portfolio_service import (
    build_allocation_data,
    calculate_annual_dividend,
    calculate_asset_ratios,
    calculate_stock_value,
    calculate_total_assets,
    calculate_unrealized_profit,
)
from stock import (
    JAPANESE_STOCK_CODE_PATTERN,
    cash_balance as calculate_cash_balance,
    create_candidate,
    normalize_stock_code,
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
            "Noto Sans Mono CJK JP", "Osaka-Mono", "MS Gothic",
            "SFMono-Regular", Consolas, monospace;
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
        placeholder_names = {
            stock["code"],
            get_yahoo_symbol(stock["code"]),
        }
        if not stock.get("name") or stock["name"] in placeholder_names:
            refreshed_info = fetch_stock_info(stock["code"])
            stock["name"] = refreshed_info["name"]
            stock["current_price"] = refreshed_info["price"]
            stock["dividend_yield"] = refreshed_info["dividend_yield"]
            stock["dividend_months"] = refreshed_info["dividend_months"]
        else:
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
stock_tab, allocation_tab, buying_power_tab, settings_tab = st.tabs(
    ["📋 銘柄管理", "🥧 資産配分", "💰 余力資金", "⚙️ 設定"]
)

# =========================
# 保有銘柄一覧
# =========================

with stock_tab:
    st.subheader("📋 銘柄管理")
    st.caption(
        "各銘柄の行にあるボタンから、購入・全売却・削除を操作できます。"
    )

    with st.expander("➕ 新しい銘柄を候補銘柄に追加", expanded=not stocks):
        with st.form("add_stock_form", clear_on_submit=True):
            stock_code_input = st.text_input(
                "日本株の銘柄コード",
                placeholder="例：7203、２８５ａ",
                max_chars=4,
                help="全角の数字・英字にも対応しています。4文字で入力してください。",
            )
            add_stock_submitted = st.form_submit_button(
                "候補銘柄に追加", type="primary", width="stretch"
            )

        if add_stock_submitted:
            normalized_code = normalize_stock_code(stock_code_input)
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
    st.warning("この銘柄を全売却し、候補銘柄へ移動します。")

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


@st.dialog("候補銘柄の削除")
def show_delete_candidate_dialog(stock):
    st.write(f"**{stock['name']}（{stock['code']}）**")
    st.warning(
        "この候補銘柄を一覧から削除します。"
        "過去の売買履歴も削除され、元に戻せません。"
    )

    cancel_col, delete_col = st.columns(2)
    with cancel_col:
        if st.button("キャンセル", key="cancel_candidate_delete", width="stretch"):
            st.session_state.pop("pending_delete_candidate_code", None)
            st.rerun()
    with delete_col:
        if st.button(
            "削除する",
            key="confirm_candidate_delete",
            type="primary",
            width="stretch",
        ):
            stocks[:] = [item for item in stocks if item["code"] != stock["code"]]
            save_stocks(stocks)
            st.session_state.pop("pending_delete_candidate_code", None)
            reset_stock_board()
            st.session_state["candidate_deleted_message"] = (
                f"{stock['name']}（{stock['code']}）を候補銘柄から削除しました。"
            )
            st.rerun()


for message_key in (
    "purchase_message",
    "sale_message",
    "candidate_deleted_message",
):
    message = st.session_state.pop(message_key, None)
    if message:
        stock_tab.success(message)


def render_stock_cell(text, *, header=False, numeric=False):
    classes = ["stock-grid-cell"]
    if header:
        classes.append("stock-grid-header")
    if numeric:
        classes.append("stock-grid-number")
    safe_text = escape(str(text))
    st.markdown(
        f'<div class="{" ".join(classes)}" title="{safe_text}">'
        f"{safe_text}</div>",
        unsafe_allow_html=True,
    )


held_stocks = [stock for stock in stocks if stock["shares"] > 0]
candidate_stocks = [stock for stock in stocks if stock["shares"] == 0]

with stock_tab:
    st.markdown(
        """
        <style>
        .stock-grid-cell {
            min-width: 0;
            padding: 0.45rem 0.2rem;
            color: inherit;
            font-size: 0.95rem;
            line-height: 1.35;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .stock-grid-header {
            color: #475569;
            font-weight: 750;
        }
        .stock-grid-number {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-cell) {
            align-items: center;
            border-bottom: 1px solid rgba(148, 163, 184, 0.35);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### 🟢 保有銘柄")
    held_widths = [3.2, 1, 1, 0.85, 1.15, 1.15, 0.85, 0.8]
    held_headers = [
        "銘柄名（コード）",
        "平均取得",
        "現在値",
        "保有数",
        "評価額",
        "評価損益",
        "損益率",
        "操作",
    ]
    held_header_columns = st.columns(held_widths)
    for column, label in zip(held_header_columns, held_headers):
        with column:
            render_stock_cell(label, header=True, numeric=label != "銘柄名（コード）")

    if held_stocks:
        for stock in held_stocks:
            current_price = stock.get("current_price", stock["average_price"])
            evaluation_value = current_price * stock["shares"]
            stock_profit = (current_price - stock["average_price"]) * stock["shares"]
            profit_rate = (
                (current_price - stock["average_price"])
                / stock["average_price"]
                * 100
                if stock["average_price"] > 0
                else 0
            )
            values = [
                f"{stock['name']}（{stock['code']}）",
                f"{stock['average_price']:,.0f}円",
                f"{current_price:,.0f}円",
                f"{stock['shares']:,}株",
                f"{evaluation_value:,.0f}円",
                f"{stock_profit:+,.0f}円",
                f"{profit_rate:+.1f}%",
            ]
            row_columns = st.columns(held_widths)
            for index, value in enumerate(values):
                with row_columns[index]:
                    render_stock_cell(value, numeric=index > 0)
            with row_columns[-1]:
                if st.button(
                    "全売却",
                    key=f"sell_all_{stock['code']}",
                    width="stretch",
                ):
                    st.session_state["pending_sale_code"] = stock["code"]
    else:
        st.info("保有銘柄はありません。")

    st.markdown("#### 🟠 候補銘柄")
    candidate_widths = [3.2, 1, 0.85, 0.8, 0.8]
    candidate_headers = [
        "銘柄名（コード）",
        "現在値",
        "保有数",
        "購入",
        "削除",
    ]
    candidate_header_columns = st.columns(candidate_widths)
    for column, label in zip(candidate_header_columns, candidate_headers):
        with column:
            render_stock_cell(label, header=True, numeric=label != "銘柄名（コード）")

    if candidate_stocks:
        for stock in candidate_stocks:
            current_price = stock.get("current_price", stock["average_price"])
            row_columns = st.columns(candidate_widths)
            with row_columns[0]:
                render_stock_cell(f"{stock['name']}（{stock['code']}）")
            with row_columns[1]:
                render_stock_cell(f"{current_price:,.0f}円", numeric=True)
            with row_columns[2]:
                render_stock_cell(f"{stock['shares']:,}株", numeric=True)
            with row_columns[3]:
                if st.button(
                    "購入",
                    key=f"purchase_{stock['code']}",
                    type="primary",
                    width="stretch",
                ):
                    st.session_state["pending_purchase_code"] = stock["code"]
            with row_columns[4]:
                if st.button(
                    "削除",
                    key=f"delete_{stock['code']}",
                    width="stretch",
                ):
                    st.session_state["pending_delete_candidate_code"] = stock["code"]
    else:
        st.info("候補銘柄はありません。")

    with st.expander("📈 Yahooチャートを開く"):
        for section_name, section_stocks in (
            ("保有銘柄", held_stocks),
            ("候補銘柄", candidate_stocks),
        ):
            st.markdown(f"**{section_name}**")
            if section_stocks:
                for stock in section_stocks:
                    yahoo_symbol = get_yahoo_symbol(stock["code"])
                    st.link_button(
                        f"📈 {stock['name']}（{stock['code']}）",
                        f"https://finance.yahoo.co.jp/quote/{yahoo_symbol}/chart",
                        width="stretch",
                    )
            else:
                st.caption(f"{section_name}はありません。")

pending_purchase_code = st.session_state.get("pending_purchase_code")
pending_sale_code = st.session_state.get("pending_sale_code")
pending_delete_candidate_code = st.session_state.get("pending_delete_candidate_code")

if pending_purchase_code:
    pending_stock = next(
        (stock for stock in stocks if stock["code"] == pending_purchase_code),
        None,
    )
    if pending_stock is not None and pending_stock["shares"] == 0:
        show_purchase_dialog(pending_stock)
    else:
        st.session_state.pop("pending_purchase_code", None)
elif pending_sale_code:
    pending_stock = next(
        (stock for stock in stocks if stock["code"] == pending_sale_code),
        None,
    )
    if pending_stock is not None and pending_stock["shares"] > 0:
        show_sell_all_dialog(pending_stock)
    else:
        st.session_state.pop("pending_sale_code", None)
elif pending_delete_candidate_code:
    pending_stock = next(
        (
            stock
            for stock in stocks
            if stock["code"] == pending_delete_candidate_code
            and stock["shares"] == 0
        ),
        None,
    )
    if pending_stock is not None:
        show_delete_candidate_dialog(pending_stock)
    else:
        st.session_state.pop("pending_delete_candidate_code", None)

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

with settings_tab:
    st.subheader("⚙️ 設定")
    st.markdown("### 総資産の基準額")
    st.caption(
        "運用開始時の資金を設定します。"
        "保有株の売買損益に応じて、現在の総資産はこの金額から変動します。"
    )

    setting_col, current_col = st.columns(2)
    with setting_col:
        st.metric("現在の基準額", f"{initial_capital:,.0f}円")
    with current_col:
        st.metric("現在の総資産", f"{total_assets:,.0f}円")

    settings_message = st.session_state.pop("settings_message", None)
    if settings_message:
        st.success(settings_message)

    with st.form("initial_capital_form"):
        new_initial_capital = st.number_input(
            "運用開始資金",
            min_value=1,
            value=int(initial_capital),
            step=100_000,
            format="%d",
            help="1円以上の金額を入力してください。",
        )
        save_settings = st.form_submit_button(
            "設定を保存", type="primary", width="stretch"
        )

    if save_settings:
        save_initial_capital(int(new_initial_capital))
        st.session_state["settings_message"] = (
            f"総資産の基準額を{int(new_initial_capital):,}円に変更しました。"
        )
        st.rerun()


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
