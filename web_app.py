from datetime import datetime
from html import escape

import streamlit as st
import plotly.express as px

from api import (
    fetch_current_price,
    fetch_dividend_yield,
    fetch_stock_info,
    get_yahoo_symbol,
    search_japanese_stocks,
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
    normalize_input,
    normalize_stock_code,
    set_share_count,
    should_refresh_dividend,
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
        margin: 0.1rem 0 0.8rem;
        text-align: left;
        font-family:
            Inter, "Noto Sans JP", "Helvetica Neue", Arial, sans-serif;
        font-size: 1.7rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -0.06em;
        background: none;
        color: #152238;
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
        gap: 1rem;
        border-bottom: 1px solid #e2e8f0;
    }

    [data-testid="stTabs"] [data-baseweb="tab"] {
        min-width: 8rem;
        height: 3rem;
        padding: 0 1rem;
        border-radius: 0;
        font-size: 1rem;
        font-weight: 700;
    }

    .stock-page-hero {
        display: grid;
        grid-template-columns: minmax(18rem, 1fr) minmax(34rem, 1.2fr);
        gap: 2rem;
        align-items: center;
        margin: 2.2rem 0 1.8rem;
    }

    .stock-page-heading {
        display: flex;
        gap: 1.25rem;
        align-items: center;
    }

    .stock-page-icon {
        display: grid;
        place-items: center;
        width: 5rem;
        height: 5rem;
        flex: 0 0 5rem;
        border-radius: 1.25rem;
        background: #e8f7ef;
        font-size: 2.35rem;
    }

    .stock-page-heading h2 {
        margin: 0 0 0.65rem;
        color: #152238;
        font-size: 2rem;
        font-weight: 850;
    }

    .stock-page-heading p {
        margin: 0;
        color: #526078;
        font-size: 1rem;
        font-weight: 550;
    }

    .stock-page-summary {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        padding: 1.25rem 1rem;
        border: 1px solid #e2e8f0;
        border-radius: 1rem;
        background: white;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.07);
    }

    .stock-page-summary > div {
        display: flex;
        min-width: 0;
        padding: 0.15rem 1.25rem;
        flex-direction: column;
        border-right: 1px solid #e2e8f0;
    }

    .stock-page-summary > div:last-child {
        border-right: 0;
    }

    .stock-page-summary span {
        color: #526078;
        font-size: 0.9rem;
        font-weight: 650;
    }

    .stock-page-summary strong {
        margin-top: 0.35rem;
        color: #22a866;
        font-size: 1.45rem;
        white-space: nowrap;
    }

    @media (max-width: 900px) {
        .stock-page-hero {
            grid-template-columns: 1fr;
        }
        .stock-page-summary {
            grid-template-columns: 1fr;
            gap: 0.75rem;
        }
        .stock-page-summary > div {
            border-right: 0;
            border-bottom: 1px solid #e2e8f0;
        }
        .stock-page-summary > div:last-child {
            border-bottom: 0;
        }
    }

    [data-testid="stExpander"] {
        border-color: #dbe3ea !important;
        border-radius: 0.9rem !important;
        background: #ffffff;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
    }

    [data-testid="stExpander"] summary {
        min-height: 4.4rem;
        font-weight: 750;
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
        refreshed_at = datetime.now().astimezone().isoformat(timespec="seconds")
        placeholder_names = {
            stock["code"],
            get_yahoo_symbol(stock["code"]),
        }
        current_name = stock.get("name", "")
        if not current_name or current_name in placeholder_names or current_name.isascii():
            refreshed_info = fetch_stock_info(stock["code"])
            stock["name"] = refreshed_info["name"]
            stock["current_price"] = refreshed_info["price"]
            if refreshed_info["dividend_yield"] is not None:
                stock["dividend_yield"] = refreshed_info["dividend_yield"]
                stock["dividend_updated_at"] = refreshed_at
            stock["dividend_months"] = refreshed_info["dividend_months"]
        else:
            stock["current_price"] = fetch_current_price(stock["code"])
            if should_refresh_dividend(stock):
                refreshed_yield = fetch_dividend_yield(
                    stock["code"], stock["current_price"]
                )
                if refreshed_yield is not None:
                    stock["dividend_yield"] = refreshed_yield
                    stock["dividend_updated_at"] = refreshed_at
        stock["price_updated_at"] = refreshed_at
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
    hero_held_count = sum(stock["shares"] > 0 for stock in stocks)
    st.markdown(
        f"""
        <div class="stock-page-hero">
            <div class="stock-page-heading">
                <div class="stock-page-icon">📋</div>
                <div>
                    <h2>銘柄管理</h2>
                    <p>各銘柄の行にあるボタンから、購入・全売却・削除を操作できます。</p>
                </div>
            </div>
            <div class="stock-page-summary">
                <div><span>保有銘柄数</span><strong>{hero_held_count} 銘柄</strong></div>
                <div><span>評価額合計</span><strong>{stock_value:,.0f} 円</strong></div>
                <div><span>評価損益</span><strong>{profit_loss:+,.0f} 円</strong></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("➕ 新しい銘柄を候補銘柄に追加", expanded=not stocks):
        st.caption("日本株の銘柄コードまたは会社名で検索して、候補リストへ追加できます。")
        with st.form("add_stock_form", clear_on_submit=True):
            stock_query_input = st.text_input(
                "銘柄コード・会社名",
                placeholder="例：7203、285A、トヨタ自動車",
                help="銘柄コードは全角の数字・英字にも対応しています。会社名は一部だけでも検索できます。",
            )
            add_stock_submitted = st.form_submit_button(
                "検索／コードで追加", type="primary", width="stretch"
            )

        if add_stock_submitted:
            normalized_query = normalize_input(stock_query_input).strip()
            normalized_code = normalize_stock_code(normalized_query)
            existing_codes = {stock["code"] for stock in stocks}

            if not normalized_query:
                st.error("銘柄コードまたは会社名を入力してください。")
            elif JAPANESE_STOCK_CODE_PATTERN.fullmatch(normalized_code):
                if normalized_code in existing_codes:
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
                        st.session_state.pop("stock_search_results", None)
                        st.session_state["stock_board_version"] = (
                            st.session_state.get("stock_board_version", 0) + 1
                        )
                        st.session_state["stock_added_message"] = (
                            f"{stock_info['name']}（{normalized_code}）を追加しました。"
                        )
                        st.rerun()
            else:
                with st.spinner("Yahooで会社名を検索中…"):
                    search_results = search_japanese_stocks(normalized_query)
                if search_results:
                    st.session_state["stock_search_results"] = search_results
                    st.rerun()
                else:
                    st.error("該当する日本株が見つかりませんでした。会社名を変えてお試しください。")

        search_results = st.session_state.get("stock_search_results", [])
        if search_results:
            result_options = {
                f"{result['name']}（{result['code']}）": result["code"]
                for result in search_results
            }
            selected_result = st.selectbox("検索結果", list(result_options))
            selected_code = result_options[selected_result]
            if selected_code in {stock["code"] for stock in stocks}:
                st.warning("この銘柄はすでに登録されています。")
            elif st.button(
                "選択した銘柄を候補銘柄に追加",
                type="primary",
                width="stretch",
            ):
                try:
                    with st.spinner("銘柄情報を取得中…"):
                        stock_info = fetch_stock_info(selected_code)
                except RuntimeError as error:
                    st.error(f"銘柄情報を取得できませんでした。{error}")
                else:
                    stocks.append(create_candidate(selected_code, stock_info))
                    save_stocks(stocks)
                    st.session_state.pop("stock_search_results", None)
                    st.session_state["stock_board_version"] = (
                        st.session_state.get("stock_board_version", 0) + 1
                    )
                    st.session_state["stock_added_message"] = (
                        f"{stock_info['name']}（{selected_code}）を追加しました。"
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
        value=1,
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


@st.dialog("一部売却の確認")
def show_partial_sale_dialog(stock):
    current_price = stock.get("current_price", stock["average_price"])

    st.write(f"**{stock['name']}（{stock['code']}）**")
    st.write(f"現在の保有数：{stock['shares']:,}株")
    st.write(f"売却単価：{current_price:,.0f}円")
    sale_shares = st.number_input(
        "売却株数",
        min_value=1,
        max_value=int(stock["shares"]) - 1,
        value=1,
        step=1,
        format="%d",
    )
    st.caption(f"売却予定額：{current_price * sale_shares:,.0f}円")

    cancel_col, sale_col = st.columns(2)
    with cancel_col:
        if st.button("キャンセル", key="cancel_partial_sale", width="stretch"):
            st.session_state.pop("pending_partial_sale_code", None)
            reset_stock_board()
            st.rerun()
    with sale_col:
        if st.button(
            "売却を確定",
            key="confirm_partial_sale",
            type="primary",
            width="stretch",
        ):
            set_share_count(
                stock,
                stock["shares"] - int(sale_shares),
                current_price,
            )
            save_stocks(stocks)
            st.session_state.pop("pending_partial_sale_code", None)
            reset_stock_board()
            st.session_state["sale_message"] = (
                f"{stock['name']}を{int(sale_shares):,}株売却しました。"
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
            "一覧から削除",
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


def render_stock_cell(text, *, header=False, numeric=False, tone=None):
    classes = ["stock-grid-cell"]
    if header:
        classes.append("stock-grid-header")
    if numeric:
        classes.append("stock-grid-number")
    if tone:
        classes.append(f"stock-grid-{tone}")
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
            padding: 0.65rem 0.35rem;
            color: var(--text-color);
            font-size: 0.95rem;
            line-height: 1.35;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .stock-grid-header {
            font-weight: 800;
        }
        .stock-grid-number {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
        .st-key-held_section {
            margin: 1.35rem 0 1.5rem;
            padding: 1rem 1.1rem 0.9rem;
            border-color: #bfe8d0 !important;
            border-radius: 1rem !important;
            background: #effaf4;
            box-shadow: 0 5px 16px rgba(22, 134, 83, 0.06);
        }
        .st-key-candidate_section {
            margin: 1.35rem 0 1.5rem;
            padding: 1rem 1.1rem 0.9rem;
            border-color: #fed1b2 !important;
            border-radius: 1rem !important;
            background: #fff6ed;
            box-shadow: 0 5px 16px rgba(194, 65, 12, 0.05);
        }
        .portfolio-section-title {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 1.35rem 0 0.85rem;
            padding: 0.2rem 0.1rem;
        }
        .portfolio-section-title > div {
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }
        .portfolio-section-title > div > span {
            width: 1.15rem;
            height: 1.15rem;
            flex: 0 0 1.15rem;
            border-radius: 999px;
        }
        .held-title > div > span { background: #31b56f; }
        .candidate-title > div > span { background: #f97316; }
        .portfolio-section-title h3 {
            margin: 0;
            color: #152238;
            font-size: 1.4rem;
            font-weight: 850;
        }
        .portfolio-section-title p {
            margin: 0.2rem 0 0;
            color: #64748b;
            font-size: 0.9rem;
        }
        .portfolio-section-title > strong {
            padding: 0.45rem 0.8rem;
            border-radius: 0.55rem;
            font-size: 0.9rem;
        }
        .held-title > strong {
            color: #168653;
            background: #e8f7ef;
        }
        .candidate-title > strong {
            color: #ea580c;
            background: #fff0e5;
        }
        .held-total-bar {
            display: grid;
            grid-template-columns: 1.5fr 1fr 1fr 1fr;
            align-items: center;
            gap: 0.75rem;
            margin: 0.6rem 0 1.4rem;
            padding: 0.9rem 1.15rem;
            border: 1px solid #ccebd9;
            border-radius: 0.75rem;
            background: linear-gradient(90deg, #f0faf5, #eaf8f1);
            color: #274238;
        }
        .held-total-bar span {
            font-weight: 700;
        }
        .held-total-bar strong {
            color: #168653;
            text-align: right;
            font-size: 1.05rem;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-cell) {
            align-items: center;
            margin-bottom: 0.35rem;
            padding: 0.25rem 0.6rem;
            border: 1px solid transparent;
            border-radius: 0.65rem;
            transition: background-color 0.15s ease, border-color 0.15s ease;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-held.stock-grid-header) {
            border-color: #ccebd9;
            background: #eaf8f1;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-held):not(:has(.stock-grid-header)) {
            border-color: #dce7e1;
            background: #f0faf5;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-candidate.stock-grid-header) {
            border-color: #fed7ba;
            background: #fff1e7;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-candidate):not(:has(.stock-grid-header)) {
            border-color: #f5dfd0;
            background: #fff7ed;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-held):not(:has(.stock-grid-header)):hover {
            border-color: #8bd5ad;
            background: #e5f7ed;
        }
        [data-testid="stHorizontalBlock"]:has(.stock-grid-candidate):not(:has(.stock-grid-header)):hover {
            border-color: #fdba8c;
            background: #ffeddc;
        }
        .stock-empty-state {
            margin: 0.4rem 0 0.8rem;
            padding: 1.1rem 1.25rem;
            border: 1px solid;
            border-radius: 0.75rem;
            font-weight: 650;
        }
        .stock-empty-held {
            border-color: #ccebd9;
            color: #168653;
            background: #f0faf5;
        }
        .stock-empty-candidate {
            border-color: #fed7ba;
            color: #c2410c;
            background: #fff7ed;
        }
        [class*="st-key-sell_all_"] button {
            border-color: #71c99a !important;
            color: #168653 !important;
            background: #ffffff !important;
        }
        [class*="st-key-purchase_"] button {
            border-color: #ef4444 !important;
            color: white !important;
            background: #ef4444 !important;
        }
        [class*="st-key-delete_"] button {
            border-color: #cbd5e1 !important;
            color: #475569 !important;
            background: #ffffff !important;
        }
        @media (max-width: 900px) {
            .held-total-bar {
                grid-template-columns: 1fr 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    held_section = st.container(border=True, key="held_section")
    with held_section:
        st.markdown(
            f"""
            <div class="portfolio-section-title held-title">
                <div><span></span><div><h3>保有銘柄</h3><p>現在保有している銘柄の一覧です。</p></div></div>
                <strong>{len(held_stocks)} 銘柄</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        held_widths = [3.2, 1, 1, 0.85, 1.15, 1.15, 0.85, 0.8]
        held_headers = [
            "銘柄名（コード）",
            "平均取得",
            "現在値",
            "保有数",
            "評価額",
            "評価損益",
            "損益率",
            "売買",
        ]
        held_header_columns = st.columns(held_widths)
        for column, label in zip(held_header_columns, held_headers):
            with column:
                render_stock_cell(
                    label,
                    header=True,
                    numeric=label != "銘柄名（コード）",
                    tone="held",
                )

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
                        render_stock_cell(value, numeric=index > 0, tone="held")
                with row_columns[-1]:
                    with st.popover("売買", width="stretch"):
                        if st.button(
                            "追加購入",
                            key=f"add_purchase_{stock['code']}",
                            width="stretch",
                        ):
                            st.session_state["pending_purchase_code"] = stock["code"]
                            st.rerun()
                        if st.button(
                            "一部売却",
                            key=f"partial_sale_{stock['code']}",
                            disabled=stock["shares"] <= 1,
                            width="stretch",
                        ):
                            st.session_state["pending_partial_sale_code"] = stock["code"]
                            st.rerun()
                        if st.button(
                            "全売却",
                            key=f"sell_all_{stock['code']}",
                            width="stretch",
                        ):
                            st.session_state["pending_sale_code"] = stock["code"]
                            st.rerun()
        else:
            st.markdown(
                '<div class="stock-empty-state stock-empty-held">'
                "保有銘柄はありません。</div>",
                unsafe_allow_html=True,
            )

        held_evaluation_total = sum(
            stock.get("current_price", stock["average_price"]) * stock["shares"]
            for stock in held_stocks
        )
        held_profit_total = sum(
            (
                stock.get("current_price", stock["average_price"])
                - stock["average_price"]
            )
            * stock["shares"]
            for stock in held_stocks
        )
        held_profit_rate = (
            held_profit_total
            / sum(stock["average_price"] * stock["shares"] for stock in held_stocks)
            * 100
            if sum(stock["average_price"] * stock["shares"] for stock in held_stocks) > 0
            else 0
        )
        st.markdown(
            f"""
            <div class="held-total-bar">
                <span>📈 保有銘柄評価額合計</span><strong>{held_evaluation_total:,.0f} 円</strong>
                <span>評価損益合計</span><strong>{held_profit_total:+,.0f} 円 ({held_profit_rate:+.1f}%)</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    candidate_section = st.container(border=True, key="candidate_section")
    with candidate_section:
        st.markdown(
            f"""
            <div class="portfolio-section-title candidate-title">
                <div><span></span><div><h3>候補銘柄</h3><p>購入を検討している銘柄の一覧です。</p></div></div>
                <strong>{len(candidate_stocks)} 銘柄</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )
        candidate_widths = [3.2, 1, 0.9, 1.3]
        candidate_headers = [
            "銘柄名（コード）",
            "現在値",
            "購入",
            "一覧から削除",
        ]
        candidate_header_columns = st.columns(candidate_widths)
        for column, label in zip(candidate_header_columns, candidate_headers):
            with column:
                render_stock_cell(
                    label,
                    header=True,
                    numeric=label != "銘柄名（コード）",
                    tone="candidate",
                )

        if candidate_stocks:
            for stock in candidate_stocks:
                current_price = stock.get("current_price", stock["average_price"])
                row_columns = st.columns(candidate_widths)
                with row_columns[0]:
                    render_stock_cell(
                        f"{stock['name']}（{stock['code']}）",
                        tone="candidate",
                    )
                with row_columns[1]:
                    render_stock_cell(
                        f"{current_price:,.0f}円",
                        numeric=True,
                        tone="candidate",
                    )
                with row_columns[2]:
                    if st.button(
                        "購入",
                        key=f"purchase_{stock['code']}",
                        type="primary",
                        width="stretch",
                    ):
                        st.session_state["pending_purchase_code"] = stock["code"]
                with row_columns[3]:
                    if st.button(
                        "一覧から削除",
                        key=f"delete_{stock['code']}",
                        width="stretch",
                    ):
                        st.session_state["pending_delete_candidate_code"] = stock["code"]
        else:
            st.markdown(
                '<div class="stock-empty-state stock-empty-candidate">'
                "候補銘柄はありません。</div>",
                unsafe_allow_html=True,
            )

pending_purchase_code = st.session_state.get("pending_purchase_code")
pending_partial_sale_code = st.session_state.get("pending_partial_sale_code")
pending_sale_code = st.session_state.get("pending_sale_code")
pending_delete_candidate_code = st.session_state.get("pending_delete_candidate_code")

if pending_purchase_code:
    pending_stock = next(
        (stock for stock in stocks if stock["code"] == pending_purchase_code),
        None,
    )
    if pending_stock is not None:
        show_purchase_dialog(pending_stock)
    else:
        st.session_state.pop("pending_purchase_code", None)
elif pending_partial_sale_code:
    pending_stock = next(
        (stock for stock in stocks if stock["code"] == pending_partial_sale_code),
        None,
    )
    if pending_stock is not None and pending_stock["shares"] > 1:
        show_partial_sale_dialog(pending_stock)
    else:
        st.session_state.pop("pending_partial_sale_code", None)
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
    investment_col, count_col = st.columns(2)
    with investment_col:
        st.metric("投資中の資産", f"{stock_value:,.0f}円")
    with count_col:
        st.metric("保有銘柄数", f"{len(allocation_held_stocks)}銘柄")

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
