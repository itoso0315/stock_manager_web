import tkinter as tk
from tkinter import ttk


class AllocationView(ttk.Frame):
    """資産配分チャートの表示領域。"""

    def __init__(self, parent, draw_command):
        super().__init__(parent)
        tk.Label(self, text="資産配分", foreground="#172b4d", font=("Hiragino Sans", 16, "bold")).pack(anchor="w", padx=20, pady=(18, 2))
        tk.Label(self, text="現在評価額に対する銘柄ごとの構成比", foreground="#52657a", font=("Hiragino Sans", 11)).pack(anchor="w", padx=20, pady=(0, 8))
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.canvas.bind("<Configure>", lambda _event: draw_command())
