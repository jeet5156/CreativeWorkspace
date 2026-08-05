import unittest
from PySide6.QtWidgets import QApplication, QGraphicsScene
from PySide6.QtCore import QPointF

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.frame_node_item import FrameNodeItem
from ui.lab.nodes.image_node_item import ImageNodeItem
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable

app = QApplication.instance() or QApplication([])


class TestFrameNode(unittest.TestCase):

    def test_frame_registry_and_instantiation(self):
        """Verify frame.section node definition is registered and instantiates FrameNodeItem."""
        defn = NodeRegistry.get("frame.section")
        self.assertIsNotNone(defn)
        self.assertEqual(defn.category, "frame")

        frame = NodeRegistry.create_node("frame.section")
        self.assertIsInstance(frame, FrameNodeItem)
        self.assertEqual(frame.zValue(), -10)
        self.assertEqual(frame.payload.get("color_theme"), "purple")

    def test_frame_geometric_containment(self):
        """Verify contained_nodes() returns items whose center falls inside frame bounds."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        note_inside = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        note_outside = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 800.0, "y": 800.0, "width": 100.0, "height": 100.0}
        })

        members = frame.contained_nodes()
        self.assertIn(note_inside, members)
        self.assertNotIn(note_outside, members)
        self.assertNotIn(frame, members)

    def test_frame_movement_moves_contained_nodes(self):
        """Verify dragging/moving Frame moves contained member nodes by matching position delta."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        note_inside = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        # Select frame and move
        frame.setSelected(True)
        frame.setPos(QPointF(100.0, 100.0))

        # Member node position should shift by (+100, +100) -> (150, 150)
        self.assertEqual(note_inside.pos().x(), 150.0)
        self.assertEqual(note_inside.pos().y(), 150.0)

    def test_frame_deletion_preserves_contained_nodes(self):
        """Verify deleting Frame removes only Frame object, leaving member nodes in scene."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        note_inside = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        canvas.remove_node(frame.id)

        self.assertNotIn(frame.id, canvas._items_map)
        self.assertIn(note_inside.id, canvas._items_map)
        self.assertIn(note_inside, canvas.items())

    def test_frame_color_themes_and_collapse(self):
        """Verify color theme switching and collapse/expand toggling."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        note_inside = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        frame.set_color_theme("green")
        self.assertEqual(frame.payload.get("color_theme"), "green")

        # Collapse frame
        frame.set_collapsed(True)
        self.assertTrue(frame.payload.get("collapsed"))
        self.assertFalse(note_inside.isVisible())

        # Expand frame
        frame.set_collapsed(False)
        self.assertFalse(frame.payload.get("collapsed"))
        self.assertTrue(note_inside.isVisible())

    def test_frame_inspector_integration(self):
        """Verify NodeInspectable returns Frame Properties section for FrameNodeItem."""
        frame = NodeRegistry.create_node("frame.section")
        frame.payload["title"] = "Environment References"
        frame.set_color_theme("amber")

        adapter = NodeInspectable(frame)
        sections = adapter.get_inspection_sections()

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, "Frame Properties")

        adapter.set_inspectable_property("payload.color_theme", "blue")
        self.assertEqual(frame.payload.get("color_theme"), "blue")


if __name__ == "__main__":
    unittest.main()
