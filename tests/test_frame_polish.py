import unittest
from PySide6.QtWidgets import QApplication, QGraphicsScene

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.frame_node_item import FrameNodeItem
from core.inspectable_adapters import NodeInspectable
from services.frame_service import HEADER_HEIGHT

app = QApplication.instance() or QApplication([])


class TestFramePolish(unittest.TestCase):

    def setUp(self):
        self.scene = QGraphicsScene()

    def test_frame_header_plus_minus_button(self):
        """Verify set_collapsed() toggles collapse state and height without direct payload manipulation."""
        frame = NodeRegistry.create_node("frame.section")
        self.scene.addItem(frame)
        expanded_h = frame.height

        # Collapse frame
        frame.set_collapsed(True)
        self.assertTrue(frame.payload["collapsed"])
        self.assertEqual(frame.height, HEADER_HEIGHT)

        # Expand frame
        frame.set_collapsed(False)
        self.assertFalse(frame.payload["collapsed"])
        self.assertEqual(frame.height, expanded_h)

    def test_independent_pin_and_collapse_hit_targets(self):
        """Verify pin and collapse hit target regions operate independently without interfering."""
        frame = NodeRegistry.create_node("frame.section")
        self.scene.addItem(frame)

        self.assertFalse(frame.is_pinned)
        self.assertFalse(frame.payload["collapsed"])

        # Toggle pin independently
        frame.toggle_pinned()
        self.assertTrue(frame.is_pinned)
        self.assertFalse(frame.payload["collapsed"])

        # Toggle collapse independently
        frame.toggle_collapsed()
        self.assertTrue(frame.payload["collapsed"])
        self.assertTrue(frame.is_pinned)

    def test_inspector_collapsed_sync(self):
        """Verify Inspector property mutations call set_collapsed() and update UI, height, and payload."""
        frame = NodeRegistry.create_node("frame.section")
        self.scene.addItem(frame)
        adapter = NodeInspectable(frame)

        # Toggle via Inspector adapter
        updated = adapter.set_inspectable_property("payload.collapsed", True)
        self.assertTrue(updated)
        self.assertTrue(frame.payload["collapsed"])
        self.assertEqual(frame.height, HEADER_HEIGHT)

        # Expand via Inspector adapter
        updated = adapter.set_inspectable_property("payload.collapsed", False)
        self.assertTrue(updated)
        self.assertFalse(frame.payload["collapsed"])
        self.assertGreater(frame.height, HEADER_HEIGHT)

    def test_persistence_sync(self):
        """Verify collapsed and pinned states restore accurately from .lab.json dictionaries."""
        frame = NodeRegistry.create_node("frame.section")
        frame.set_pinned(True)
        frame.set_collapsed(True)

        data = frame.to_dict()
        self.assertTrue(data["metadata"]["pinned"])
        self.assertTrue(data["payload"]["collapsed"])

        reloaded = NodeRegistry.create_node("frame.section")
        reloaded.from_dict(data)
        self.assertTrue(reloaded.is_pinned)
        self.assertTrue(reloaded.payload["collapsed"])


if __name__ == "__main__":
    unittest.main()
