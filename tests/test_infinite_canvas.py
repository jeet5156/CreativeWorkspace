import unittest
from PySide6.QtWidgets import QApplication
from ui.widgets.infinite_canvas import InfiniteCanvas

app = QApplication.instance() or QApplication([])


class TestInfiniteCanvas(unittest.TestCase):

    def setUp(self):
        self.canvas = InfiniteCanvas()

    def test_initial_viewport_state(self):
        state = self.canvas.get_viewport_state()
        self.assertEqual(state["zoom"], 1.0)
        self.assertTrue(state["grid_visible"])
        self.assertEqual(state["active_tool"], "select")

    def test_set_viewport_state(self):
        state = {
            "zoom": 2.0,
            "pan_x": 100.0,
            "pan_y": -200.0,
            "grid_visible": False,
            "grid_size": 25,
            "snap_to_grid": True,
        }
        self.canvas.set_viewport_state(state)

        new_state = self.canvas.get_viewport_state()
        self.assertEqual(new_state["zoom"], 2.0)
        self.assertFalse(new_state["grid_visible"])
        self.assertTrue(new_state["snap_to_grid"])

    def test_zoom_clamping(self):
        # Test zooming beyond MAX_ZOOM
        for _ in range(30):
            self.canvas.zoom_in()
        state = self.canvas.get_viewport_state()
        self.assertLessEqual(state["zoom"], self.canvas.MAX_ZOOM)

        # Test zooming below MIN_ZOOM
        for _ in range(50):
            self.canvas.zoom_out()
        state = self.canvas.get_viewport_state()
        self.assertGreaterEqual(state["zoom"], self.canvas.MIN_ZOOM)

    def test_reset_camera(self):
        self.canvas.zoom_in()
        self.canvas.zoom_in()
        self.canvas.reset_camera()
        state = self.canvas.get_viewport_state()
        self.assertEqual(state["zoom"], 1.0)


if __name__ == "__main__":
    unittest.main()
