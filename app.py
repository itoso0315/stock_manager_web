"""株式管理アプリ全体の状態と画面間連携。"""

import calendar as month_calendar
from datetime import date, datetime
import re
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter import scrolledtext
from urllib.parse import quote
import webbrowser

from api import fetch_dividend_months, fetch_stock_info
from calendar_events import EVENT_STYLES, build_month_events
from database import load_initial_capital, load_stocks, save_initial_capital, save_stocks
from dialogs import FundSettingsDialog, SellAllDialog, ShareAdjustmentDialog, StockDialog
from stock import (
    annual_dividend,
    cash_balance,
    create_candidate,
    market_value,
    normalize_input,
    profit_loss,
    reset_portfolio,
    set_share_count,
    total_cost,
)
from views import AllocationView, AiAdvisorView, PortfolioView, RightsCalendarView, SummaryView

MINKABU_HOME_URL = "https://minkabu.jp"
MINKABU_STOCK_SEARCH_URL = "https://minkabu.jp/stock/find?search_kind=s&keyword={query}"
MINKABU_STOCK_DETAIL_URL = "https://minkabu.jp/stock/{code}"
JAPANESE_STOCK_CODE_PATTERN = re.compile(r"^[0-9A-Z]{4}$")


class StockManagerApp(tk.Tk):
    TABLE_COLUMNS = (
        ("name", "銘柄名", 145, "w"),
        ("code", "コード", 60, "w"),
        ("shares", "保有株数", 70, "e"),
        ("average", "平均取得単価", 100, "e"),
        ("price", "現在株価", 90, "e"),
        ("value", "評価額", 105, "e"),
        ("profit", "含み損益", 105, "e"),
        ("dividend", "配当利回り", 75, "e"),
        ("updated", "更新日時", 145, "w"),
    )
    GAIN_COLOR = "#c62828"
    LOSS_COLOR = "#2e7d32"
    APP_BACKGROUND = "#f4f7fb"
    SUMMARY_BACKGROUND = "#163a63"
    TABLE_COLUMN_BACKGROUNDS = ("#ffffff", "#f3f6fa")
    PIE_COLORS = ("#2563eb", "#16a34a", "#d97706", "#9333ea", "#db2777", "#0891b2", "#65a30d", "#dc2626")

    def __init__(self):
        super().__init__()
        self.title("株式管理")
        self.geometry("1120x700")
        self.minsize(760, 480)
        self.configure(background=self.APP_BACKGROUND)
        self.stocks = load_stocks()
        self.initial_capital = load_initial_capital()
        self.selected_index = None
        self.list_mode = "purchased"
        self.row_widgets = []
        self._vertical_scroll_remainder = 0.0
        self._horizontal_scroll_remainder = 0.0
        self._create_widgets()
        self.refresh()

    def _create_widgets(self):
        self.summary_view = SummaryView(self, self.open_fund_settings, self.SUMMARY_BACKGROUND)
        self.summary_view.pack(fill="x", padx=16, pady=(16, 10))
        self.summary_vars = self.summary_view.vars
        self.profit_summary_label = self.summary_view.profit_label

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(2, 0))
        portfolio_tab = ttk.Frame(self.notebook)
        self.allocation_tab = ttk.Frame(self.notebook)
        self.rights_calendar_tab = ttk.Frame(self.notebook)
        self.ai_advisor_tab = ttk.Frame(self.notebook)
        self.notebook.add(portfolio_tab, text="銘柄一覧")
        self.notebook.add(self.allocation_tab, text="資産配分")
        self.notebook.add(self.rights_calendar_tab, text="権利日カレンダー")
        self.notebook.add(self.ai_advisor_tab, text="AIと考える")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        list_switch = tk.Frame(portfolio_tab, background=self.APP_BACKGROUND, pady=4)
        list_switch.pack(fill="x")
        self.list_mode_buttons = {}
        for mode, label in (("purchased", "保有銘柄"), ("candidate", "候補銘柄（過去保有銘柄）")):
            button = tk.Label(
                list_switch,
                text=label,
                cursor="hand2",
                font=("Hiragino Sans", 12, "bold"),
                padx=18,
                pady=7,
            )
            button.pack(side="left", padx=(0, 6))
            button.bind("<Button-1>", lambda _event, selected_mode=mode: self._set_list_mode(selected_mode))
            self.list_mode_buttons[mode] = button

        self.candidate_search_frame = tk.Frame(list_switch, background=self.APP_BACKGROUND)
        self.stock_search_label_var = tk.StringVar(value="保有名検索")
        tk.Label(
            self.candidate_search_frame,
            textvariable=self.stock_search_label_var,
            foreground="#334155",
            background=self.APP_BACKGROUND,
            font=("Hiragino Sans", 11),
        ).pack(side="left", padx=(0, 6))
        self.candidate_search_var = tk.StringVar()
        candidate_search_entry = ttk.Entry(
            self.candidate_search_frame,
            textvariable=self.candidate_search_var,
            width=24,
        )
        candidate_search_entry.pack(side="left")
        ttk.Button(
            self.candidate_search_frame,
            text="クリア",
            command=lambda: self.candidate_search_var.set(""),
        ).pack(side="left", padx=(6, 0))
        self.candidate_search_var.trace_add("write", self._on_candidate_search)

        actions = tk.Frame(portfolio_tab, background=self.APP_BACKGROUND, padx=0, pady=4)
        actions.pack(fill="x")
        for text, command, color in (
            ("＋ 銘柄を追加", self.add_candidate, "#2563eb"),
            ("株数を変更", self.change_share_count, "#0f766e"),
            ("全売却", self.sell_all_shares, "#c2413b"),
            ("銘柄を削除", self.delete_stock, "#7f1d1d"),
        ):
            self._make_action_button(actions, text, command, color).pack(side="left", padx=(0, 8))
        self._make_action_button(actions, "↻", self.update_prices, "#475569", icon=True).pack(side="right")

        table_frame = ttk.Frame(portfolio_tab, padding=(0, 8, 0, 4))
        table_frame.pack(fill="both", expand=True)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        body_frame = ttk.Frame(table_frame)
        body_frame.grid(row=0, column=0, sticky="nsew")
        body_frame.columnconfigure(0, weight=1)
        body_frame.rowconfigure(0, weight=1)
        self.table_canvas = tk.Canvas(body_frame, highlightthickness=0, background="white")
        self.table_canvas.grid(row=0, column=0, sticky="nsew")
        # スクロールバーは表の外側の列に置き、本文の幅をヘッダー幅と一致させる。
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table_canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        horizontal_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table_canvas.xview)
        horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        self.table_canvas.configure(
            yscrollcommand=scrollbar.set,
            xscrollcommand=horizontal_scrollbar.set,
        )
        self.table = tk.Frame(self.table_canvas, background="white")
        self.table_window = self.table_canvas.create_window((0, 0), window=self.table, anchor="nw")
        # 見出し・全データ行のセルを同じ親グリッドに置くことで、列境界を完全に共通化する。
        for column_index, (key, heading, width, anchor) in enumerate(self.TABLE_COLUMNS):
            header_label = tk.Label(
                self.table,
                text=heading,
                anchor=anchor,
                font=self._table_font(key, header=True),
                foreground="#1f2937",
                background="#edf1f5",
                width=1,
                padx=4,
            )
            header_label.grid(row=0, column=column_index, sticky="ew", padx=(0, 1), pady=(0, 1), ipady=6)
            self._bind_table_scrolling(header_label)
            self.table.columnconfigure(column_index, weight=width, minsize=width)
        self.table.bind("<Configure>", self._update_table_scrollregion)
        self.table_canvas.bind("<Configure>", self._resize_table)
        self._bind_table_scrolling(self.table_canvas)
        self._bind_table_scrolling(self.table)
        # macOSではトラックパッドイベントがセルではなくallタグへ届く場合がある。
        # セルへの直接バインドに加え、表内だけで動くフォールバックを登録する。
        self.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        self.bind_all("<Shift-MouseWheel>", self._on_global_horizontal_mousewheel, add="+")
        self.bind_all("<TouchpadScroll>", self._on_global_touchpad_scroll, add="+")
        self.bind_all("<Button-4>", lambda event: self._on_global_mousewheel(event, -1), add="+")
        self.bind_all("<Button-5>", lambda event: self._on_global_mousewheel(event, 1), add="+")

        self.status = tk.StringVar(value="準備完了")
        ttk.Label(portfolio_tab, textvariable=self.status, anchor="w", padding=(0, 4, 0, 10)).pack(fill="x")

        self._create_allocation_tab()
        self._create_rights_calendar_tab()
        self._create_ai_advisor_tab()
        self._update_list_mode_buttons()

    def _create_allocation_tab(self):
        """評価額の構成比を表示するタブを作る。"""
        self.allocation_view = AllocationView(self.allocation_tab, self._draw_allocation_chart)
        self.allocation_view.pack(fill="both", expand=True)
        self.allocation_canvas = self.allocation_view.canvas

    def _create_rights_calendar_tab(self):
        """保有銘柄の権利日を月間カレンダーで表示する。"""
        today = date.today()
        self.calendar_year, self.calendar_month = today.year, today.month
        self.rights_calendar_tab.columnconfigure(0, weight=1)
        self.rights_calendar_tab.rowconfigure(3, weight=1, minsize=220)

        toolbar = ttk.Frame(self.rights_calendar_tab, padding=(12, 6, 12, 4))
        toolbar.grid(row=0, column=0, sticky="ew")
        ttk.Button(toolbar, text="‹ 前月", command=lambda: self._move_calendar_month(-1)).pack(side="left")
        ttk.Button(toolbar, text="今月", command=self._show_current_calendar_month).pack(side="left", padx=6)
        ttk.Button(toolbar, text="翌月 ›", command=lambda: self._move_calendar_month(1)).pack(side="left")
        self.calendar_title = tk.StringVar()
        ttk.Label(toolbar, textvariable=self.calendar_title, font=("Hiragino Sans", 16, "bold")).pack(side="left", padx=18)
        ttk.Button(toolbar, text="権利月情報を更新", command=self.update_dividend_months).pack(side="right")

        explanation = tk.Frame(self.rights_calendar_tab, background="#eef4fa", padx=8, pady=5)
        explanation.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))
        explanation.columnconfigure(0, weight=1, uniform="rights_help")
        explanation.columnconfigure(1, weight=1, uniform="rights_help")
        last_day_help = tk.Frame(explanation, background="#eef4fa")
        last_day_help.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        ex_date_help = tk.Frame(explanation, background="#eef4fa")
        ex_date_help.grid(row=0, column=1, sticky="nsew")
        tk.Label(
            last_day_help,
            text="● 権利付最終日（いつまでに買えばいいか）",
            foreground=EVENT_STYLES["last_day"][1], background="#eef4fa",
            font=("Hiragino Sans", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            last_day_help,
            text="権利確定日の2営業日前。大引け（通常15時30分）までに購入・保有すると、今回の配当権利を得られます。",
            foreground="#334155", background="#eef4fa", justify="left", anchor="w", wraplength=500,
            font=("Hiragino Sans", 8),
        ).pack(fill="x", anchor="w", pady=(2, 0))
        tk.Label(
            ex_date_help,
            text="● 権利落ち日（売ってもいい日）",
            foreground=EVENT_STYLES["ex_date"][1], background="#eef4fa",
            font=("Hiragino Sans", 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            ex_date_help,
            text="権利付最終日の翌営業日。この日以降に売却しても権利は維持されますが、新規購入では今回の配当権利を得られません。",
            foreground="#334155", background="#eef4fa", justify="left", anchor="w", wraplength=500,
            font=("Hiragino Sans", 8),
        ).pack(fill="x", anchor="w", pady=(2, 0))

        legend = ttk.Frame(self.rights_calendar_tab, padding=(12, 0, 12, 3))
        legend.grid(row=2, column=0, sticky="ew")
        for event_type in ("last_day", "ex_date", "record_date"):
            label, color = EVENT_STYLES[event_type]
            tk.Label(legend, text=f"● {label}", foreground=color).pack(side="left", padx=(0, 16))
        tk.Label(legend, text="□ 今日", foreground="#dc2626").pack(side="left", padx=(0, 16))
        ttk.Label(legend, text="※ 権利確定月の月末を基準にした予定日").pack(side="right")

        self.rights_calendar_view = RightsCalendarView(
            self.rights_calendar_tab,
            self._draw_rights_calendar,
            self._on_calendar_mousewheel,
            self._on_calendar_horizontal_mousewheel,
            self._on_calendar_touchpad_scroll,
        )
        self.rights_calendar_view.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.rights_calendar_canvas = self.rights_calendar_view.canvas
        self._draw_rights_calendar()

    def _on_notebook_tab_changed(self, _event=None):
        """非表示中はサイズ未確定のため、カレンダータブを開いた後に再描画する。"""
        if not hasattr(self, "rights_calendar_tab") or not hasattr(self, "rights_calendar_canvas"):
            return
        selected_tab = self.notebook.nametowidget(self.notebook.select())
        if selected_tab is self.rights_calendar_tab:
            self.after_idle(self._draw_rights_calendar)
            self.after(100, self._draw_rights_calendar)

    def _move_calendar_month(self, amount):
        month_index = self.calendar_year * 12 + self.calendar_month - 1 + amount
        self.calendar_year, zero_based_month = divmod(month_index, 12)
        self.calendar_month = zero_based_month + 1
        self._draw_rights_calendar()

    def _show_current_calendar_month(self):
        today = date.today()
        self.calendar_year, self.calendar_month = today.year, today.month
        self._draw_rights_calendar()

    def _draw_rights_calendar(self):
        if not hasattr(self, "rights_calendar_canvas"):
            return
        canvas = self.rights_calendar_canvas
        canvas.delete("all")
        self.calendar_title.set(f"{self.calendar_year}年 {self.calendar_month}月")
        viewport_width, viewport_height = canvas.winfo_width(), canvas.winfo_height()
        if viewport_width < 20 or viewport_height < 20:
            return
        width = max(viewport_width, 900)
        height = max(viewport_height, 420)
        canvas.configure(scrollregion=(0, 0, width, height))
        weeks = month_calendar.monthcalendar(self.calendar_year, self.calendar_month)
        events = build_month_events(self.stocks, self.calendar_year, self.calendar_month)
        today = date.today()
        header_height = min(30, max(18, height * 0.12))
        cell_width = width / 7
        cell_height = (height - header_height) / len(weeks)
        for column, weekday in enumerate(("月", "火", "水", "木", "金", "土", "日")):
            color = "#2563eb" if column == 5 else "#c2413b" if column == 6 else "#334155"
            canvas.create_text((column + 0.5) * cell_width, 15, text=weekday, fill=color, font=("Hiragino Sans", 10, "bold"))
        for row, week in enumerate(weeks):
            for column, day in enumerate(week):
                left, top = column * cell_width, header_height + row * cell_height
                right, bottom = left + cell_width, top + cell_height
                canvas.create_rectangle(left, top, right, bottom, outline="#dbe3ec", fill="white")
                if not day:
                    continue
                current_date = date(self.calendar_year, self.calendar_month, day)
                if current_date == today:
                    canvas.create_rectangle(
                        left + 2,
                        top + 2,
                        right - 2,
                        bottom - 2,
                        outline="#dc2626",
                        width=3,
                    )
                day_color = "#2563eb" if column == 5 else "#c2413b" if column == 6 else "#1f2937"
                canvas.create_text(left + 6, top + 5, text=str(day), anchor="nw", fill=day_color, font=("Hiragino Sans", 9, "bold"))
                event_y = top + 23
                for event in events.get(current_date, [])[:3]:
                    label, color = EVENT_STYLES[event["type"]]
                    canvas.create_text(
                        left + 6, event_y, text=f"{label} {event['name']}", anchor="nw",
                        width=max(30, cell_width - 10), fill=color, font=("Hiragino Sans", 8),
                    )
                    event_y += 17

    def _on_calendar_mousewheel(self, event, direction=None):
        if direction is None and sys.platform == "darwin":
            self._move_canvas_by_trackpad(self.rights_calendar_canvas, event.delta)
            return "break"
        if direction is None:
            direction = self._wheel_steps(event.delta)
        if direction:
            self.rights_calendar_canvas.yview_scroll(direction, "units")
        return "break"

    def _on_calendar_horizontal_mousewheel(self, event):
        if sys.platform == "darwin":
            self._move_canvas_by_trackpad(self.rights_calendar_canvas, event.delta, horizontal=True)
            return "break"
        direction = self._wheel_steps(event.delta, horizontal=True)
        if direction:
            self.rights_calendar_canvas.xview_scroll(direction, "units")
        return "break"

    def _on_calendar_touchpad_scroll(self, event):
        delta_x, delta_y = self._precise_scroll_deltas(event)
        self._move_canvas_by_trackpad(self.rights_calendar_canvas, delta_y)
        self._move_canvas_by_trackpad(self.rights_calendar_canvas, delta_x, horizontal=True)
        return "break"

    def update_dividend_months(self):
        holdings = [stock for stock in self.stocks if stock.get("shares", 0) > 0]
        if not holdings:
            messagebox.showinfo("保有銘柄なし", "権利月情報を取得する保有銘柄がありません。", parent=self)
            return
        failures = []
        for stock in holdings:
            months = fetch_dividend_months(stock["code"])
            if months:
                stock["dividend_months"] = months
            else:
                failures.append(stock["name"])
        save_stocks(self.stocks)
        self._draw_rights_calendar()
        if failures:
            messagebox.showwarning("権利月情報の更新完了", "取得できなかった銘柄:\n" + "\n".join(failures), parent=self)
        else:
            messagebox.showinfo("権利月情報の更新完了", "保有銘柄の権利月情報を更新しました。", parent=self)

    def _create_ai_advisor_tab(self):
        """現在のポートフォリオをもとに、AIへ相談するための画面を作る。"""
        container = ttk.Frame(self.ai_advisor_tab, padding=20)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(3, weight=1)

        ttk.Label(
            container,
            text="AIと一緒にポートフォリオを考える",
            font=("Hiragino Sans", 16, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            container,
            text="投資方針を入力すると、現在の資金・保有銘柄・候補銘柄をまとめた相談文を作成します。",
            foreground="#52657a",
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        form = ttk.Frame(container)
        form.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="相談したいこと").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.ai_question_var = tk.StringVar(
            value="リスクを抑えつつ、長期で成長を狙えるポートフォリオ案を考えてください。"
        )
        ttk.Entry(form, textvariable=self.ai_question_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(form, text="相談文を作成", command=self._build_ai_prompt).grid(row=0, column=2, padx=(8, 0))

        self.ai_prompt_text = scrolledtext.ScrolledText(
            container,
            wrap="word",
            font=("Hiragino Sans", 11),
            height=18,
        )
        self.ai_prompt_text.grid(row=3, column=0, sticky="nsew")

        actions = ttk.Frame(container)
        actions.grid(row=4, column=0, sticky="e", pady=(10, 0))
        ttk.Button(actions, text="クリップボードにコピー", command=self._copy_ai_prompt).pack(side="left")
        ttk.Button(actions, text="ChatGPTを開く", command=lambda: webbrowser.open_new_tab("https://chatgpt.com")).pack(
            side="left", padx=(8, 0)
        )

        self._build_ai_prompt()

    def _build_ai_prompt(self):
        """現在の資産状況をAIへ渡せる相談文として整形する。"""
        snapshot = AiAdvisorView.portfolio_snapshot(self.stocks, self.initial_capital)
        holdings, candidates = snapshot["holdings"], snapshot["candidates"]
        cost, current_value, available_cash = snapshot["cost"], snapshot["value"], snapshot["cash"]

        lines = [
            "あなたは個人投資家のポートフォリオ設計を支援するアドバイザーです。",
            "売買を断定せず、複数案とその理由・リスクを比較してください。",
            "",
            f"【相談内容】{self.ai_question_var.get().strip()}",
            "",
            "【現在の資産状況】",
            f"仮想資金: {self.initial_capital:,.0f}円",
            f"現金残高: {available_cash:,.0f}円",
            f"取得総額: {cost:,.0f}円",
            f"現在評価額: {current_value:,.0f}円",
            "",
            "【保有銘柄】",
        ]
        if holdings:
            for stock in holdings:
                price = stock.get("current_price")
                value = market_value(stock) if price is not None else None
                lines.append(
                    f"- {stock['name']}（{stock['code']}）: {stock['shares']:,}株、"
                    f"平均取得単価 {stock['average_price']:,.2f}円、"
                    f"現在株価 {price:,.2f}円、評価額 {value:,.0f}円"
                    if price is not None
                    else f"- {stock['name']}（{stock['code']}）: {stock['shares']:,}株、株価未取得"
                )
        else:
            lines.append("- なし")

        lines.extend(["", "【候補銘柄】"])
        if candidates:
            for stock in candidates:
                price = stock.get("current_price")
                lines.append(
                    f"- {stock['name']}（{stock['code']}）: 現在株価 {price:,.2f}円"
                    if price is not None
                    else f"- {stock['name']}（{stock['code']}）: 株価未取得"
                )
        else:
            lines.append("- なし")

        lines.extend(
            [
                "",
                "【回答してほしいこと】",
                "1. 現在のポートフォリオの偏りと主なリスク",
                "2. 現金を含めた配分案を3パターン（安定型・中間型・成長型）",
                "3. 各案で追加購入・維持・縮小を検討する銘柄と理由",
                "4. 判断に足りない情報と、次に確認すべき指標",
                "5. 断定ではなく、前提条件と注意点を明記",
            ]
        )

        self.ai_prompt_text.delete("1.0", "end")
        self.ai_prompt_text.insert("1.0", "\n".join(lines))

    def _copy_ai_prompt(self):
        """作成した相談文をクリップボードへコピーする。"""
        prompt = self.ai_prompt_text.get("1.0", "end").strip()
        if not prompt:
            messagebox.showinfo("コピーできません", "先に相談文を作成してください。", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.status.set("AI相談用の文章をクリップボードへコピーしました")

    def _make_action_button(self, parent, text, command, color, icon=False):
        """macOSでも背景色を維持できるラベル型の操作ボタンを作る。"""
        button = tk.Label(
            parent,
            text=text,
            foreground="white",
            background=color,
            highlightbackground=color,
            highlightthickness=1,
            cursor="hand2",
            font=("Hiragino Sans", 12 if not icon else 17, "bold"),
            padx=14 if not icon else 10,
            pady=7 if not icon else 3,
        )
        hover_color = self._darken_color(color)
        button.bind("<Button-1>", lambda _event: command())
        button.bind("<Enter>", lambda _event: button.configure(background=hover_color))
        button.bind("<Leave>", lambda _event: button.configure(background=color))
        return button

    @staticmethod
    def _darken_color(color):
        """ホバー時に使う、少し濃い背景色を返す。"""
        rgb = tuple(int(color[position:position + 2], 16) for position in (1, 3, 5))
        return "#{:02x}{:02x}{:02x}".format(*(int(value * 0.82) for value in rgb))

    def refresh(self):
        if self.selected_index is not None and self.selected_index >= len(self.stocks):
            self.selected_index = None
        for row in self.row_widgets:
            for label in row["labels"]:
                label.destroy()
        self.row_widgets.clear()
        displayed_stocks = self._displayed_stocks()
        for row_index, (stock_index, stock) in enumerate(displayed_stocks):
            price = stock.get("current_price")
            value = market_value(stock) if price is not None else None
            gain = profit_loss(stock) if price is not None else None
            values = (
                stock["name"], stock["code"], f'{stock["shares"]:,} 株', f'{stock["average_price"]:,.2f} 円',
                f"{price:,.2f} 円" if price is not None else "未取得",
                f"{value:,.2f} 円" if value is not None else "-",
                f"{gain:+,.2f} 円" if gain is not None else "-",
                f'{stock["dividend_yield"]:.2f} %' if stock.get("dividend_yield") is not None else "未取得",
                self._display_updated_at(stock.get("price_updated_at", "-")),
            )
            self._add_table_row(row_index, stock_index, values, gain)
        cost = sum(total_cost(stock) for stock in self.stocks)
        priced = [stock for stock in self.stocks if "current_price" in stock]
        value = sum(market_value(stock) for stock in priced)
        gain = value - sum(total_cost(stock) for stock in priced)
        dividend = sum(annual_dividend(stock) or 0 for stock in priced)
        self.summary_vars["capital"].set(f"{self.initial_capital:,.0f} 円")
        self.summary_vars["balance"].set(f"{cash_balance(self.stocks, self.initial_capital):,.0f} 円")
        self.summary_vars["cost"].set(f"{cost:,.0f} 円")
        self.summary_vars["value"].set(f"{value:,.0f} 円")
        self.summary_vars["profit"].set(f"{gain:+,.0f} 円")
        self.summary_vars["dividend"].set(f"{dividend:,.0f} 円")
        self.profit_summary_label.configure(
            foreground=self.GAIN_COLOR if gain > 0 else self.LOSS_COLOR if gain < 0 else "black"
        )
        self.after_idle(self._draw_allocation_chart)
        if hasattr(self, "ai_prompt_text"):
            self.after_idle(self._build_ai_prompt)
        mode_name = "保有銘柄" if self.list_mode == "purchased" else "候補銘柄（過去保有銘柄）"
        self.status.set(f"{mode_name}: {len(displayed_stocks)}件")

    def _displayed_stocks(self):
        return PortfolioView.filter_stocks(self.stocks, self.list_mode, self.candidate_search_var.get())

    def _on_candidate_search(self, *_args):
        self.selected_index = None
        self.refresh()

    def _set_list_mode(self, mode):
        self.list_mode = mode
        self.selected_index = None
        self._update_list_mode_buttons()
        self.refresh()

    def _update_list_mode_buttons(self):
        selected_colors = {
            "purchased": "#16803c",
            "candidate": "#d97706",
        }
        for mode, button in self.list_mode_buttons.items():
            selected = mode == self.list_mode
            button.configure(
                foreground="white" if selected else "#334155",
                background=selected_colors[mode] if selected else "#e2e8f0",
            )
        self.stock_search_label_var.set("保有名検索" if self.list_mode == "purchased" else "候補名検索")
        if not self.candidate_search_frame.winfo_manager():
            self.candidate_search_frame.pack(side="right")

    def _draw_allocation_chart(self):
        """保有銘柄を評価額比で円グラフ表示する。"""
        if not hasattr(self, "allocation_canvas"):
            return
        canvas = self.allocation_canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 100 or height < 100:
            return

        holdings = []
        for stock in self.stocks:
            if stock.get("current_price") is not None:
                value = market_value(stock)
                if value > 0:
                    holdings.append((stock, value))
        total = sum(value for _stock, value in holdings)
        if total == 0:
            canvas.create_text(
                width / 2,
                height / 2,
                text="株価を取得すると、ここに資産配分を表示します。",
                fill="#52657a",
                font=("Hiragino Sans", 13),
            )
            return

        pie_size = min(330, height - 70, max(180, width * 0.42))
        left, top = 36, max(34, (height - pie_size) / 2)
        right, bottom = left + pie_size, top + pie_size
        start_angle = 90
        for index, (_stock, value) in enumerate(holdings):
            extent = -360 * value / total
            canvas.create_arc(
                left, top, right, bottom,
                start=start_angle,
                extent=extent,
                fill=self.PIE_COLORS[index % len(self.PIE_COLORS)],
                outline="white",
                width=2,
            )
            start_angle += extent

        legend_x = right + 36
        canvas.create_text(legend_x, top, text=f"合計  {total:,.0f} 円", anchor="w", fill="#172b4d", font=("Hiragino Sans", 13, "bold"))
        legend_y = top + 34
        for index, (stock, value) in enumerate(holdings):
            color = self.PIE_COLORS[index % len(self.PIE_COLORS)]
            ratio = value / total * 100
            canvas.create_rectangle(legend_x, legend_y, legend_x + 14, legend_y + 14, fill=color, outline=color)
            canvas.create_text(
                legend_x + 24,
                legend_y + 7,
                text=f"{stock['name']}（{stock['code']}）  {value:,.0f} 円  {ratio:.1f} %",
                anchor="w",
                fill="#1f2937",
                font=("Hiragino Sans", 11),
            )
            legend_y += 34

    def _add_table_row(self, row_index, stock_index, values, gain):
        labels = []
        backgrounds = []
        for column_index, ((key, _heading, width, anchor), value) in enumerate(zip(self.TABLE_COLUMNS, values)):
            column_bg = self.TABLE_COLUMN_BACKGROUNDS[column_index % len(self.TABLE_COLUMN_BACKGROUNDS)]
            foreground = "black"
            if key == "profit" and gain is not None:
                foreground = self.GAIN_COLOR if gain > 0 else self.LOSS_COLOR if gain < 0 else "black"
            label = tk.Label(
                self.table,
                text=value,
                anchor=anchor,
                font=self._table_font(key),
                foreground=foreground,
                background=column_bg,
                width=1,
                padx=4,
            )
            label.grid(row=row_index + 1, column=column_index, sticky="ew", padx=(0, 1), pady=1, ipady=4)
            label.bind("<Button-1>", lambda _event, index=stock_index: self._select_row(index))
            self._bind_table_scrolling(label)
            labels.append(label)
            backgrounds.append(column_bg)
        self.row_widgets.append({"labels": labels, "backgrounds": backgrounds})
        self._apply_row_style(row_index, stock_index)

    @staticmethod
    def _table_font(key, header=False):
        """情報量に合わせ、一覧の文字を列ごとに読みやすく整える。"""
        size = {
            "name": 11,
            "code": 10,
            "shares": 10,
            "average": 10,
            "price": 10,
            "value": 10,
            "profit": 10,
            "dividend": 9,
            "updated": 9,
        }[key]
        return ("Hiragino Sans", size, "bold" if header else "normal")

    @staticmethod
    def _display_updated_at(value):
        """保存用のISO日時を、一覧で収まる表示形式に整える。"""
        if value == "-":
            return value
        return value.replace("T", " ")[:16]

    def _select_row(self, index):
        self.selected_index = index
        displayed_indices = [stock_index for stock_index, _stock in self._displayed_stocks()]
        for row_index, stock_index in enumerate(displayed_indices):
            self._apply_row_style(row_index, stock_index)

    def _apply_row_style(self, row_index, stock_index):
        row = self.row_widgets[row_index]
        backgrounds = ["#e8f2ff"] * len(row["labels"]) if stock_index == self.selected_index else row["backgrounds"]
        for label, background in zip(row["labels"], backgrounds):
            label.configure(background=background)

    def _update_table_scrollregion(self, _event=None):
        self.table_canvas.configure(scrollregion=self.table_canvas.bbox("all"))

    def _resize_table(self, event):
        minimum_width = sum(column[2] for column in self.TABLE_COLUMNS)
        self.table_canvas.itemconfigure(self.table_window, width=max(event.width, minimum_width))

    def _bind_table_scrolling(self, widget):
        """表本体・見出し・セル上でホイールと2本指スクロールを受け取る。"""
        widget.bind("<MouseWheel>", self._on_table_mousewheel, add="+")
        widget.bind("<Shift-MouseWheel>", self._on_table_horizontal_mousewheel, add="+")
        widget.bind("<TouchpadScroll>", self._on_table_touchpad_scroll, add="+")
        widget.bind("<Button-4>", lambda event: self._on_table_mousewheel(event, -1), add="+")
        widget.bind("<Button-5>", lambda event: self._on_table_mousewheel(event, 1), add="+")

    def _on_table_mousewheel(self, event, direction=None):
        if not self._pointer_is_over_table():
            return
        if direction is None and sys.platform == "darwin":
            self._move_canvas_by_trackpad(self.table_canvas, event.delta)
            return "break"
        if direction is None:
            direction = self._wheel_steps(event.delta, horizontal=False)
        if direction == 0:
            return "break"
        self.table_canvas.yview_scroll(direction, "units")
        return "break"

    def _on_table_horizontal_mousewheel(self, event):
        if not self._pointer_is_over_table():
            return
        if sys.platform == "darwin":
            self._move_canvas_by_trackpad(self.table_canvas, event.delta, horizontal=True)
            return "break"
        direction = self._wheel_steps(event.delta, horizontal=True)
        if direction:
            self.table_canvas.xview_scroll(direction, "units")
        return "break"

    def _on_table_touchpad_scroll(self, event):
        if not self._pointer_is_over_table():
            return
        delta_x, delta_y = self._precise_scroll_deltas(event)
        self._move_canvas_by_trackpad(self.table_canvas, delta_y)
        self._move_canvas_by_trackpad(self.table_canvas, delta_x, horizontal=True)
        return "break"

    def _on_global_mousewheel(self, event, direction=None):
        """macOSでセル以外に届いた2本指スクロールも表へ転送する。"""
        if not self._pointer_is_over_table():
            return
        return self._on_table_mousewheel(event, direction)

    def _on_global_horizontal_mousewheel(self, event):
        """Shift付き2本指スクロールを横方向へ転送する。"""
        if not self._pointer_is_over_table():
            return
        return self._on_table_horizontal_mousewheel(event)

    def _on_global_touchpad_scroll(self, event):
        """Tk 9でallタグへ届いた高精度トラックパッド操作を転送する。"""
        if self._pointer_is_over_table():
            return self._on_table_touchpad_scroll(event)
        if self._pointer_is_over_calendar():
            return self._on_calendar_touchpad_scroll(event)

    def _pointer_is_over_calendar(self):
        if not hasattr(self, "rights_calendar_canvas"):
            return False
        pointer_x, pointer_y = self.winfo_pointerxy()
        left = self.rights_calendar_canvas.winfo_rootx()
        top = self.rights_calendar_canvas.winfo_rooty()
        right = left + self.rights_calendar_canvas.winfo_width()
        bottom = top + self.rights_calendar_canvas.winfo_height()
        return left <= pointer_x < right and top <= pointer_y < bottom

    def _pointer_is_over_table(self):
        """現在のポインター位置が表の表示領域内にあるか判定する。"""
        pointer_x, pointer_y = self.winfo_pointerxy()
        left = self.table_canvas.winfo_rootx()
        top = self.table_canvas.winfo_rooty()
        right = left + self.table_canvas.winfo_width()
        bottom = top + self.table_canvas.winfo_height()
        return left <= pointer_x < right and top <= pointer_y < bottom

    @staticmethod
    def _move_canvas_by_trackpad(canvas, delta, horizontal=False):
        """macOSの2本指操作でCanvasの表示位置を割合指定して直接動かす。"""
        if not delta:
            return
        view = canvas.xview() if horizontal else canvas.yview()
        visible_fraction = max(0.01, view[1] - view[0])
        movement = -float(delta) * max(0.008, visible_fraction * 0.08)
        new_position = min(max(0.0, view[0] + movement), max(0.0, 1.0 - visible_fraction))
        if horizontal:
            canvas.xview_moveto(new_position)
        else:
            canvas.yview_moveto(new_position)

    def _precise_scroll_deltas(self, event):
        """Tk 9のTouchpadScrollに格納されたX・Y移動量を展開する。"""
        deltas = self.tk.call("tk::PreciseScrollDeltas", event.delta)
        if isinstance(deltas, str):
            deltas = self.tk.splitlist(deltas)
        return float(deltas[0]), float(deltas[1])

    def _wheel_steps(self, delta, horizontal=False):
        """OSごとのホイール値を、安定したスクロール単位へ変換する。"""
        if not delta:
            return 0
        if sys.platform != "darwin":
            steps = -int(delta / 120)
            return steps or (-1 if delta > 0 else 1)

        # macOSのトラックパッドは非常に小さいdeltaを連続送信するため、
        # 端数を蓄積してから1単位ずつスクロールさせる。
        attribute = "_horizontal_scroll_remainder" if horizontal else "_vertical_scroll_remainder"
        remainder = getattr(self, attribute) - float(delta)
        if abs(remainder) < 1.0:
            setattr(self, attribute, remainder)
            return 0
        steps = int(remainder)
        setattr(self, attribute, remainder - steps)
        return steps

    def selected_stock(self):
        if self.selected_index is None:
            messagebox.showinfo("銘柄を選択", "一覧から銘柄を選択してください。", parent=self)
            return None
        return self.stocks[self.selected_index]

    def save_and_refresh(self, message):
        save_stocks(self.stocks)
        self.refresh()
        self.status.set(message)

    def open_fund_settings(self):
        result = FundSettingsDialog(self, self.initial_capital).show()
        if not result:
            return
        if result["action"] == "save":
            self.initial_capital = result["amount"]
            save_initial_capital(self.initial_capital)
            self.refresh()
            self.status.set("仮想資金を更新しました")
            return
        if not messagebox.askyesno(
            "資金リセットの確認",
            "全銘柄の保有株数と売買履歴を消去し、現金残高を仮想資金の設定額へ戻します。\nこの操作は元に戻せません。実行しますか？",
            parent=self,
        ):
            return
        reset_portfolio(self.stocks)
        self.selected_index = None
        self.list_mode = "candidate"
        self._update_list_mode_buttons()
        self.save_and_refresh("現金残高とポートフォリオをリセットしました")

    def add_candidate(self):
        dialog = StockDialog(self, "銘柄を候補に追加", show_shares=False, show_price=False)
        result = dialog.show()
        if not result:
            return
        code = result["code"]
        if any(stock["code"] == code for stock in self.stocks):
            messagebox.showerror("登録済み", "この銘柄はすでに登録されています。", parent=self)
            return
        self.status.set("株価情報を取得しています…")
        self.update_idletasks()
        try:
            info = fetch_stock_info(code)
        except RuntimeError as error:
            messagebox.showerror("取得失敗", str(error), parent=self)
            self.status.set("株価情報を取得できませんでした")
            return
        self.stocks.append(create_candidate(code, info))
        self.list_mode = "candidate"
        self._update_list_mode_buttons()
        self.save_and_refresh(f"{info['name']} を候補に追加しました")

    def change_share_count(self):
        stock = self.selected_stock()
        if stock is None:
            return
        result = ShareAdjustmentDialog(self, stock).show()
        if not result:
            return
        difference = set_share_count(stock, result["shares"], result["price"])
        if difference == 0:
            self.status.set("株数に変更はありません")
            return
        action = "購入" if difference > 0 else "売却"
        self.list_mode = "purchased" if result["shares"] > 0 else "candidate"
        self._update_list_mode_buttons()
        self.save_and_refresh(f"{abs(difference):,}株の{action}を記録しました")

    def sell_all_shares(self):
        stock = self.selected_stock()
        if stock is None:
            return
        if stock["shares"] == 0:
            messagebox.showinfo("保有株数なし", "この銘柄の保有株数はすでに0株です。", parent=self)
            return
        result = SellAllDialog(self, stock).show()
        if not result:
            return
        sold_shares = stock["shares"]
        set_share_count(stock, 0, result["price"])
        self.list_mode = "candidate"
        self._update_list_mode_buttons()
        self.save_and_refresh(f"{sold_shares:,}株を全売却しました")

    def delete_stock(self):
        stock = self.selected_stock()
        if stock is None:
            return
        if stock["shares"] > 0:
            messagebox.showinfo(
                "削除できません",
                "保有中の銘柄は削除できません。先に「全売却」を行ってください。",
                parent=self,
            )
            return
        if stock.get("transactions"):
            messagebox.showinfo(
                "履歴を保持します",
                "売買履歴がある銘柄は、現金残高を正しく保つため削除できません。",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "銘柄を削除",
            f"候補から {stock['name']} を削除しますか？",
            parent=self,
        ):
            return
        self.stocks.remove(stock)
        self.selected_index = None
        self.save_and_refresh(f"{stock['name']} を削除しました")

    def update_prices(self):
        if not self.stocks:
            return
        failures = []
        self.status.set("株価を更新しています…")
        self.update_idletasks()
        for stock in self.stocks:
            try:
                info = fetch_stock_info(stock["code"])
                stock["name"] = info["name"]
                stock["current_price"] = info["price"]
                stock["dividend_yield"] = info["dividend_yield"]
                stock["dividend_months"] = info.get("dividend_months", stock.get("dividend_months", []))
                stock["price_updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            except RuntimeError:
                failures.append(stock["name"])
        self.save_and_refresh("株価を更新しました" if not failures else f"更新できなかった銘柄: {', '.join(failures)}")
        self._draw_rights_calendar()
        if failures:
            messagebox.showwarning(
                "株価更新完了",
                "株価の更新処理が完了しました。\n\n更新できなかった銘柄:\n" + "\n".join(failures),
                parent=self,
            )
        else:
            messagebox.showinfo(
                "株価更新完了",
                "すべての銘柄の株価更新が完了しました。",
                parent=self,
            )
