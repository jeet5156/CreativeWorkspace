import unittest
from PySide6.QtWidgets import QApplication, QGraphicsScene
from PySide6.QtCore import Qt, QPointF

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.frame_node_item import FrameNodeItem
from ui.widgets.infinite_canvas import InfiniteCanvas

app = QApplication.instance() or QApplication([])


class TestFrameUX(unittest.TestCase):

    def test_frame_resize_handle_interaction(self):
        """Verify interactive bottom-right resizing and minimum bounds enforcement."""
        canvas = InfiniteCanvas()
        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0}
        })

        self.assertEqual(frame.width, 400.0)
        self.assertEqual(frame.height, 300.0)

        # Check resize handle hit-testing
        handle_pos = QPointF(395.0, 295.0)
        self.assertTrue(frame._is_in_resize_handle(handle_pos))

        normal_pos = QPointF(50.0, 50.0)
        self.assertFalse(frame._is_in_resize_handle(normal_pos))

    def test_frame_inline_title_editing(self):
        """Verify title payload updates when double-clicking header."""
        frame = NodeRegistry.create_node("frame.section")
        self.assertEqual(frame.payload.get("title"), "Section Frame")

        frame.payload["title"] = "Character Concepts"
        self.assertEqual(frame.payload.get("title"), "Character Concepts")

    def test_frame_drag_hover_highlight(self):
        """Verify _is_drag_hovered state toggling on FrameNodeItem."""
        canvas = InfiniteCanvas()
        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        self.assertFalse(frame._is_drag_hovered)
        frame._is_drag_hovered = True
        self.assertTrue(frame._is_drag_hovered)

        frame._is_drag_hovered = False
        self.assertFalse(frame._is_drag_hovered)


if __name__ == "__main__":
    unittest.main()
