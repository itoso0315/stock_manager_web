import tkinter as tk
from tkinter import ttk


class RightsCalendarView(ttk.Frame):
    """権利日カレンダー用のスクロール可能な描画領域。"""

    def __init__(self, parent, draw_command, vertical_command, horizontal_command, touchpad_command):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0, height=260)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.bind("<Configure>", lambda _event: draw_command())
        self.canvas.bind("<MouseWheel>", vertical_command)
        self.canvas.bind("<Shift-MouseWheel>", horizontal_command)
        self.canvas.bind("<TouchpadScroll>", touchpad_command)
        self.canvas.bind("<Button-4>", lambda event: vertical_command(event, -1))
        self.canvas.bind("<Button-5>", lambda event: vertical_command(event, 1))
