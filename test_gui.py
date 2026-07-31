import unittest
from unittest.mock import patch

from app import StockManagerApp


class MouseWheelTest(unittest.TestCase):
    def test_mac_trackpad_delta_keeps_magnitude_and_reverses_direction(self):
        app = object.__new__(StockManagerApp)
        app._vertical_scroll_remainder = 0.0
        app._horizontal_scroll_remainder = 0.0
        with patch("app.sys.platform", "darwin"):
            self.assertEqual(app._wheel_steps(3), -3)
            self.assertEqual(app._wheel_steps(-2), 2)

    def test_zero_delta_does_not_scroll(self):
        app = object.__new__(StockManagerApp)
        self.assertEqual(app._wheel_steps(0), 0)

    def test_mac_trackpad_moves_canvas_fraction_directly(self):
        class FakeCanvas:
            moved_to = None

            def yview(self):
                return (0.2, 0.6)

            def yview_moveto(self, position):
                self.moved_to = position

        canvas = FakeCanvas()

        StockManagerApp._move_canvas_by_trackpad(canvas, -1)

        self.assertGreater(canvas.moved_to, 0.2)

    def test_tk9_touchpad_delta_is_split_into_x_and_y(self):
        class FakeTk:
            def call(self, command, delta):
                self.received = (command, delta)
                return (2.5, -4.0)

        holder = type("Holder", (), {"tk": FakeTk()})()
        event = type("Event", (), {"delta": 123})()

        result = StockManagerApp._precise_scroll_deltas(holder, event)

        self.assertEqual(result, (2.5, -4.0))
        self.assertEqual(holder.tk.received, ("tk::PreciseScrollDeltas", 123))


if __name__ == "__main__":
    unittest.main()
