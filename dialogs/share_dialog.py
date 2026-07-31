import tkinter as tk
from tkinter import messagebox, ttk

from stock import normalize_input


class ShareAdjustmentDialog(tk.Toplevel):
    SHARE_STEP = 1

    def __init__(self, parent, stock):
        super().__init__(parent)
        self.result = None
        self.title(f"株数を変更 — {stock['name']}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        price = stock.get("current_price", stock.get("average_price", 0))
        self.shares_var = tk.StringVar(value=str(stock["shares"]))
        self.price_var = tk.StringVar(value=f"{price:.2f}")
        frame = ttk.Frame(self, padding=18)
        frame.pack()
        ttk.Label(frame, text=f"現在の保有株数：{stock['shares']:,} 株").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(frame, text="変更後の株数").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        shares_input = ttk.Spinbox(frame, from_=0, to=10_000_000, increment=1, textvariable=self.shares_var, width=18)
        shares_input.grid(row=1, column=1, sticky="ew", pady=6)
        quick = ttk.Frame(frame)
        quick.grid(row=1, column=2, padx=(8, 0))
        ttk.Button(quick, text="−1", width=6, command=lambda: self._adjust(-1)).pack(side="left")
        ttk.Button(quick, text="＋1", width=6, command=lambda: self._adjust(1)).pack(side="left", padx=(4, 0))
        ttk.Label(frame, text="売買単価（円）").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Entry(frame, textvariable=self.price_var, width=20).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="増減した株数だけを、この単価で売買記録します。", foreground="#52657a").grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=3, pady=(10, 0), sticky="e")
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="変更", command=self._save).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda _event: self._save())
        shares_input.focus()
        shares_input.selection_range(0, "end")

    def _adjust(self, amount):
        try: current = int(normalize_input(self.shares_var.get()))
        except ValueError: current = 0
        self.shares_var.set(str(max(0, current + amount)))

    def _save(self):
        try:
            shares = int(normalize_input(self.shares_var.get()))
            price = float(normalize_input(self.price_var.get()))
            if shares < 0: raise ValueError("株数は0以上で入力してください。")
            if price <= 0: raise ValueError("単価は0より大きくしてください。")
        except ValueError as error:
            messagebox.showerror("入力エラー", str(error), parent=self)
            return
        self.result = {"shares": shares, "price": price}
        self.destroy()

    def show(self):
        self.wait_window()
        return self.result
