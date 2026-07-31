import tkinter as tk


class SummaryView(tk.Frame):
    """資産サマリーカードを構築するビュー。"""

    KEYS = ("capital", "balance", "cost", "value", "profit", "dividend")
    LABELS = (
        ("仮想資金", "capital"), ("現金残高", "balance"), ("取得総額", "cost"),
        ("現在評価額", "value"), ("含み損益", "profit"), ("年間配当金（実績）", "dividend"),
    )

    def __init__(self, parent, settings_command, background="#163a63"):
        super().__init__(parent, background=background, padx=18, pady=14)
        tk.Label(self, text="資産サマリー", foreground="white", background=background, font=("Hiragino Sans", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        settings = tk.Label(self, text="⚙ 資金設定", foreground="white", background="#315a85", cursor="hand2", font=("Hiragino Sans", 11, "bold"), padx=12, pady=5)
        settings.grid(row=0, column=2, sticky="e", pady=(0, 10))
        settings.bind("<Button-1>", lambda _event: settings_command())
        self.vars = {key: tk.StringVar(value="-") for key in self.KEYS}
        self.profit_label = None
        for index, (label, key) in enumerate(self.LABELS):
            row, column = divmod(index, 3)
            card = tk.Frame(self, background="white", padx=14, pady=10)
            card.grid(row=row + 1, column=column, padx=(0, 10) if column < 2 else 0, pady=(0, 8) if row == 0 else 0, sticky="nsew")
            tk.Label(card, text=label, foreground="#52657a", background="white", font=("Hiragino Sans", 11)).pack(anchor="w")
            value = tk.Label(card, textvariable=self.vars[key], foreground="#172b4d", background="white", font=("Hiragino Sans", 18, "bold"))
            value.pack(anchor="w", pady=(3, 0))
            if key == "profit": self.profit_label = value
            self.columnconfigure(column, weight=1)
