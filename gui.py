"""株式管理GUIの起動エントリーポイント。"""

from app import StockManagerApp


def main():
    StockManagerApp().mainloop()


if __name__ == "__main__":
    main()
