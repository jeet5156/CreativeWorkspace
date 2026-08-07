import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QRectF

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.connectors.connector_item import ConnectorItem
from core.inspectable_adapters import ConnectorInspectable

app = QApplication.instance() or QApplication([])


class TestConnectorFoundation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_connector_creation_and_serialization(self):
        """Verify ConnectorItem creation, properties, and zero geometry serialization."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})

        conn = self.canvas.connect_nodes(n1.id, n2.id, label="Connection", style="bezier", color="#FF0000", width=3)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.source_id, n1.id)
        self.assertEqual(conn.target_id, n2.id)
        self.assertEqual(conn.label, "Connection")
        self.assertEqual(conn.style, "bezier")
        self.assertEqual(conn.color, "#FF0000")
        self.assertEqual(conn.width, 3)

        # Zero geometry serialization check
        conn_dict = conn.to_dict()
        self.assertIn("id", conn_dict)
        self.assertIn("source_id", conn_dict)
        self.assertIn("target_id", conn_dict)
        self.assertIn("metadata", conn_dict)
        self.assertNotIn("path", conn_dict)
        self.assertNotIn("points", conn_dict)

    def test_connector_node_movement_updates_path(self):
        """Verify moving a node reactively updates connected ConnectorItem path geometry."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})
        conn = self.canvas.connect_nodes(n1.id, n2.id)

        initial_rect = conn.boundingRect()

        # Shift node 2
        n2.setPos(QPointF(500.0, 300.0))
        n2._emit_modified()

        updated_rect = conn.boundingRect()
        self.assertNotEqual(initial_rect, updated_rect)

    def test_node_deletion_cleanup_prevents_orphans(self):
        """Verify deleting a node automatically removes all attached connectors (no orphan connectors)."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})
        conn = self.canvas.connect_nodes(n1.id, n2.id)

        self.assertIn(conn.id, self.canvas._connector_map)

        # Delete node 1
        self.canvas.remove_node(n1.id)

        self.assertNotIn(conn.id, self.canvas._connector_map)
        self.assertNotIn(conn, self.canvas._scene.items())

    def test_clipboard_copy_and_paste_with_remapping(self):
        """Verify copying connected nodes copies line and remaps node IDs to fresh connector UUID."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})
        conn = self.canvas.connect_nodes(n1.id, n2.id)

        # Case 1: Select only n1 -> connector is NOT copied
        self.canvas.set_selected_nodes([n1])
        self.canvas.copy_selection()
        self.assertEqual(len(self.canvas.clipboard.get_connectors()), 0)

        # Case 2: Select n1 + n2 together -> connector IS copied
        self.canvas.set_selected_nodes([n1, n2])
        self.canvas.copy_selection()
        self.assertEqual(len(self.canvas.clipboard.get_connectors()), 1)

        # Paste selection
        pasted_nodes = self.canvas.paste()
        self.assertEqual(len(pasted_nodes), 2)
        self.assertEqual(len(self.canvas.connectors()), 2)

        p_n1 = next(n for n in pasted_nodes if n.id != n1.id and n.id != n2.id)
        p_n2 = next(n for n in pasted_nodes if n.id != n1.id and n.id != n2.id and n.id != p_n1.id)

        p_conn = next(c for c in self.canvas.connectors() if c.id != conn.id)
        self.assertIn(p_conn.source_id, [p_n1.id, p_n2.id])
        self.assertIn(p_conn.target_id, [p_n1.id, p_n2.id])

    def test_backward_compatibility_zero_connectors(self):
        """Verify loading board JSON with missing connectors key defaults to empty connectors list."""
        from services.lab_service import LabService
        svc = LabService()

        # Dummy project mock
        class DummyProj:
            location = self.temp_dir

        proj = DummyProj()
        board_data = svc.load_board(proj, "Main")
        self.assertIn("connectors", board_data)
        self.assertEqual(board_data["connectors"], [])

    def test_connector_inspectable_adapter(self):
        """Verify ConnectorInspectable exposes and updates properties via InspectableObject interface."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})
        conn = self.canvas.connect_nodes(n1.id, n2.id, label="Old Label")

        adapter = ConnectorInspectable(conn)
        self.assertEqual(adapter.get_display_name(), "Line: Old Label")

        sections = adapter.get_inspection_sections()
        self.assertEqual(len(sections), 2)

        # Modify label via adapter
        adapter.set_inspectable_property("label", "New Label")
        self.assertEqual(conn.label, "New Label")

        # Modify width via adapter
        adapter.set_inspectable_property("width", 5)
        self.assertEqual(conn.width, 5)

    def test_connection_manager_decoupling(self):
        """Verify ConnectionManager owns connector lifecycle and node index lookup cleanly."""
        from services.connection_manager import ConnectionManager
        cm = ConnectionManager(self.canvas)

        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})

        conn = cm.connect_nodes(n1.id, n2.id, source_anchor="top", target_anchor="bottom")
        self.assertIsNotNone(conn)
        self.assertEqual(conn.source_anchor, "top")
        self.assertEqual(conn.target_anchor, "bottom")

        # Verify node attachment index lookup
        attached = cm.get_connectors_for_node(n1.id)
        self.assertEqual(len(attached), 1)
        self.assertEqual(attached[0].id, conn.id)

        # Remove connectors for node
        removed_ids = cm.remove_connectors_for_node(n1.id)
        self.assertEqual(removed_ids, [conn.id])
        self.assertEqual(len(cm.connectors()), 0)

    def test_node_anchor_system(self):
        """Verify NodeItem anchor port resolution and closest anchor matching."""
        n = self.canvas.add_node({"type": "note.blank", "transform": {"x": 100, "y": 100, "width": 200, "height": 100}})
        anchors = n.get_connection_anchors()

        self.assertIn("center", anchors)
        self.assertIn("top", anchors)
        self.assertIn("bottom", anchors)
        self.assertIn("left", anchors)
        self.assertIn("right", anchors)

        # Center in scene coords should be (200, 150)
        center_pos = n.get_anchor_scene_pos("center")
        self.assertEqual(center_pos.x(), 200.0)
        self.assertEqual(center_pos.y(), 150.0)

        # Closest anchor test
        best_id, _ = n.get_closest_anchor(QPointF(200.0, 90.0))
        self.assertEqual(best_id, "top")

    def test_connection_drag_preview_lifecycle(self):
        """Verify interactive connection preview drag creation, updates, and cancellation."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})

        self.canvas.start_connection_drag(n1, source_anchor="right", mouse_scene_pos=QPointF(100, 50))
        self.assertIsNotNone(self.canvas._drag_connection_preview_item)

        self.canvas.update_connection_drag(QPointF(150, 50))
        self.assertIsNotNone(self.canvas._drag_connection_preview_item)

        # Cancel preview check
        self.canvas.cancel_connection_drag()
        self.assertIsNone(self.canvas._drag_connection_preview_item)

        # Finish preview check
        self.canvas.start_connection_drag(n1, source_anchor="right", mouse_scene_pos=QPointF(100, 50))
        created = self.canvas.finish_connection_drag(n2, target_anchor="left")
        self.assertTrue(created)
        self.assertEqual(len(self.canvas.connectors()), 1)


if __name__ == "__main__":
    unittest.main()

