import re
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import quote
import webbrowser

from stock import normalize_input

MINKABU_HOME_URL = "https://minkabu.jp"
MINKABU_STOCK_SEARCH_URL = "https://minkabu.jp/stock/find?search_kind=s&keyword={query}"
MINKABU_STOCK_DETAIL_URL = "https://minkabu.jp/stock/{code}"
JAPANESE_STOCK_CODE_PATTERN = re.compile(r"^[0-9A-Z]{4}$")


class StockDialog(tk.Toplevel):
    def __init__(self, parent, title, show_code=True, show_shares=True, show_price=True, show_name=False, stock=None):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.vars = {"name": tk.StringVar(value=stock["name"] if stock else ""), "code": tk.StringVar(value=stock["code"] if stock else ""), "shares": tk.StringVar(), "price": tk.StringVar()}
        fields = []
        if show_name: fields.append(("銘柄名", "name"))
        if show_code: fields.append(("日本株コード", "code"))
        if show_shares: fields.append(("株数", "shares"))
        if show_price: fields.append(("単価（円）", "price"))
        frame = ttk.Frame(self, padding=18)
        frame.pack()
        for row, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, padx=(0, 12), pady=6, sticky="w")
            input_frame = ttk.Frame(frame)
            input_frame.grid(row=row, column=1, pady=6, sticky="ew")
            entry = ttk.Entry(input_frame, textvariable=self.vars[key], width=28)
            entry.pack(side="left", fill="x", expand=True)
            if key == "code":
                ttk.Button(input_frame, text="🔍", width=3, command=self._open_code_search).pack(side="left", padx=(6, 0))
            if row == 0: entry.focus()
        buttons = ttk.Frame(frame)
        buttons.grid(row=len(fields), column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="保存", command=lambda: self._save(show_name, show_code, show_shares, show_price)).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda _event: self._save(show_name, show_code, show_shares, show_price))

    def _open_code_search(self):
        query = normalize_input(self.vars["code"].get()).strip()
        if not query:
            webbrowser.open_new_tab(MINKABU_HOME_URL)
        elif JAPANESE_STOCK_CODE_PATTERN.fullmatch(query.upper()):
            webbrowser.open_new_tab(MINKABU_STOCK_DETAIL_URL.format(code=query))
        else:
            webbrowser.open_new_tab(MINKABU_STOCK_SEARCH_URL.format(query=quote(query)))

    def _save(self, show_name, show_code, show_shares, show_price):
        try:
            result = {}
            if show_name:
                result["name"] = self.vars["name"].get().strip()
                if not result["name"]: raise ValueError("銘柄名を入力してください。")
            if show_code:
                result["code"] = normalize_input(self.vars["code"].get()).strip().upper()
                if not result["code"]: raise ValueError("銘柄コードを入力してください。")
            if show_shares:
                result["shares"] = int(normalize_input(self.vars["shares"].get()))
                if result["shares"] <= 0: raise ValueError("株数は1以上で入力してください。")
            if show_price:
                result["price"] = float(normalize_input(self.vars["price"].get()))
                if result["price"] <= 0: raise ValueError("単価は0より大きくしてください。")
        except ValueError as error:
            messagebox.showerror("入力エラー", str(error), parent=self)
            return
        self.result = result
        self.destroy()

    def show(self):
        self.wait_window()
        return self.result
