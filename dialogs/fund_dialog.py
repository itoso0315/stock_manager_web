import tkinter as tk
from tkinter import messagebox, ttk

from stock import normalize_input


class FundSettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_amount):
        super().__init__(parent)
        self.result = None
        self.title("資金設定")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.amount_var = tk.StringVar(value=f"{current_amount:,}")
        frame = ttk.Frame(self, padding=18)
        frame.pack()
        ttk.Label(frame, text="仮想資金（円）").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        entry = ttk.Entry(frame, textvariable=self.amount_var, width=24)
        entry.grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="設定額を変更すると、売買履歴を維持したまま現金残高を再計算します。", foreground="#52657a").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 14))
        ttk.Button(frame, text="現金資金をリセット", command=self._request_reset).grid(row=2, column=0, sticky="w")
        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=1, sticky="e")
        ttk.Button(buttons, text="キャンセル", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="設定を保存", command=self._save).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda _event: self._save())
        entry.focus()
        entry.selection_range(0, "end")

    def _save(self):
        try:
            amount = int(normalize_input(self.amount_var.get()).replace(",", "").strip())
            if amount <= 0:
                raise ValueError("仮想資金は1円以上で設定してください。")
        except ValueError as error:
            messagebox.showerror("入力エラー", str(error), parent=self)
            return
        self.result = {"action": "save", "amount": amount}
        self.destroy()

    def _request_reset(self):
        self.result = {"action": "reset"}
        self.destroy()

    def show(self):
        self.wait_window()
        return self.result
