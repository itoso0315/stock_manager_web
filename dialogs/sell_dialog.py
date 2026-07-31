import tkinter as tk
from tkinter import messagebox, ttk

from stock import normalize_input


class SellAllDialog(tk.Toplevel):
    def __init__(self, parent, stock):
        super().__init__(parent)
        self.result = None
        self.title(f"全売却 — {stock['name']}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        price = stock.get("current_price", stock.get("average_price", 0))
        self.price_var = tk.StringVar(value=f"{price:.2f}")
        frame = ttk.Frame(self, padding=18)
        frame.pack()
        ttk.Label(frame, text=f"{stock['name']} の {stock['shares']:,} 株をすべて売却します。").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(frame, text="売却単価（円）").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        entry = ttk.Entry(frame, textvariable=self.price_var, width=20)
        entry.grid(row=1, column=1, sticky="ew", pady=6)
        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=2, pady=(14, 0), sticky="e")
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="全売却", command=self._save).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda _event: self._save())
        entry.focus()
        entry.selection_range(0, "end")

    def _save(self):
        try:
            price = float(normalize_input(self.price_var.get()))
            if price <= 0: raise ValueError("売却単価は0より大きくしてください。")
        except ValueError as error:
            messagebox.showerror("入力エラー", str(error), parent=self)
            return
        self.result = {"price": price}
        self.destroy()

    def show(self):
        self.wait_window()
        return self.result
