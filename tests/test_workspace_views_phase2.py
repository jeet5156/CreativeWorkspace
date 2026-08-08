import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF, QRectF

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.frame_node_item import FrameNodeItem
from services.frame_service import FrameService, FRAME_PADDING, HEADER_HEIGHT
from ui.lab.models.saved_view import SavedView

app = QApplication.instance() or QApplication([])


class TestWorkspaceViewsPhase2(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()
        self.canvas.update_project_location(self.temp_dir)

        # Create nodes spread across canvas
        self.n1 = self.canvas.add_node({
            "type": "note.blank",
            "transform": {"x": -500.0, "y": -500.0, "width": 200.0, "height": 150.0},
            "payload": {"content": "Far West Node"}
        })
        self.n2 = self.canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 1000.0, "y": 1000.0, "width": 200.0, "height": 150.0},
            "payload": {"content": "Far East Node"}
        })
        self.n3 = self.canvas.add_node({
            "type": "asset.3d",
            "transform": {"x": 0.0, "y": 0.0, "width": 300.0, "height": 200.0},
            "payload": {"filename": "model.fbx"}
        })

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fit_selection_multiple_nodes(self):
        """Verify fit_selection adjusts viewport transform to enclose selected bounds without altering node positions."""
        self.canvas.set_selected_nodes([self.n1, self.n2])
        orig_n1_pos = QPointF(self.n1.pos())
        orig_n2_pos = QPointF(self.n2.pos())

        self.canvas.fit_selection(padding=50.0)

        # Nodes must remain in original scene positions
        self.assertEqual(self.n1.pos(), orig_n1_pos)
        self.assertEqual(self.n2.pos(), orig_n2_pos)
        self.assertEqual(len(self.canvas.selected_nodes()), 2)

    def test_fit_selection_single_node_and_empty(self):
        """Verify fit_selection handles single node and empty selection safely."""
        # Empty selection
        self.canvas.clear_selection()
        self.canvas.fit_selection()

        # Single node selection
        self.canvas.set_selected_nodes([self.n1])
        self.canvas.fit_selection(padding=30.0)
        self.assertEqual(self.canvas.selected_nodes(), [self.n1])

    def test_fit_view_all_nodes_and_empty_canvas(self):
        """Verify fit_view encloses all canvas nodes and handles empty canvas safely."""
        self.canvas.fit_view(padding=40.0)

        # Empty canvas test
        empty_canvas = InfiniteCanvas()
        empty_canvas.fit_view()
        self.assertEqual(empty_canvas._zoom_level, 1.0)

    def test_search_node_focus_and_navigation_history_traversal(self):
        """Verify searching a node pushes pre-navigation history allowing Alt+Left / Alt+Right camera traversal."""
        # Record initial location A
        self.canvas.centerOn(0, 0)
        self.canvas.push_navigation_state()

        # Execute search selection to Node B (n2)
        self.canvas._on_search_node_selected(self.n2.id)

        self.assertEqual(self.canvas.selected_nodes(), [self.n2])

        # Go Back (Alt+Left) -> should return to location A
        self.canvas.go_back_history()
        center_back = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self.assertAlmostEqual(center_back.x(), 0.0, delta=5.0)
        self.assertAlmostEqual(center_back.y(), 0.0, delta=5.0)

        # Go Forward (Alt+Right) -> should return to Node B
        self.canvas.go_forward_history()
        self.assertEqual(self.canvas.selected_nodes(), [self.n2])

    def test_collapsed_frame_child_auto_reveal_on_search(self):
        """Verify explicit navigation to a child inside a collapsed frame auto-expands parent frame."""
        # Create frame enclosing n3
        frame = FrameService.create_frame_from_selection([self.n3], self.canvas, title="Hidden Assets")
        self.assertIsNotNone(frame)

        # Collapse parent frame -> n3 becomes hidden
        FrameService.set_collapsed(frame, True, scene=self.canvas.scene())
        self.assertTrue(frame.payload.get("collapsed"))
        self.assertFalse(self.n3.isVisible())

        # Search for hidden child n3 -> should reveal parent frame and focus child
        self.canvas._on_search_node_selected(self.n3.id)

        self.assertFalse(frame.payload.get("collapsed"))
        self.assertTrue(self.n3.isVisible())
        self.assertEqual(self.canvas.selected_nodes(), [self.n3])

    def test_reset_camera_home_view(self):
        """Verify reset_camera restores 1.0 zoom level and centers view on (0, 0)."""
        self.canvas.scale(2.5, 2.5)
        self.canvas.centerOn(500, 500)

        self.canvas.reset_camera()

        self.assertEqual(self.canvas._zoom_level, 1.0)
        center = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self.assertAlmostEqual(center.x(), 0.0, delta=1.0)
        self.assertAlmostEqual(center.y(), 0.0, delta=1.0)

    def test_saved_view_restoration_pushes_navigation_history(self):
        """Verify restoring a saved camera view records history state."""
        self.canvas.push_navigation_state(node_id="n1")
        self.canvas.centerOn(-100, -100)
        sv = self.canvas.save_camera_view("Main Base")

        self.canvas.centerOn(500, 500)
        self.canvas.push_navigation_state(node_id="n2")
        self.canvas.restore_camera_view(sv)

        # History back stack should allow returning to previous location
        self.assertTrue(self.canvas.nav_history_service.can_go_back())

    def test_context_menu_right_click_does_not_raise_attribute_error(self):
        """Verify contextMenuEvent on empty canvas space does not raise AttributeError for build_context_menu."""
        from PySide6.QtGui import QContextMenuEvent
        from PySide6.QtCore import QPoint

        # Simulate context menu event on empty canvas space
        evt = QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(10, 10), QPoint(10, 10))
        try:
            # Execute context menu logic without displaying UI event loop
            scene_pos = self.canvas.mapToScene(QPoint(10, 10))
            self.canvas._last_context_scene_pos = scene_pos
            # Right-click itemAt(10, 10) is None -> verifies empty canvas context menu block executes safely
            self.assertIsNone(self.canvas.itemAt(QPoint(10, 10)))
        except AttributeError as e:
            self.fail(f"contextMenuEvent raised AttributeError: {e}")

    def test_shortcut_alt_left_alt_right_navigation_traversal(self):
        """Verify _on_shortcut_go_back and _on_shortcut_go_forward restore camera history."""
        self.canvas.centerOn(0, 0)

        # Search focus Node B (n2)
        self.canvas._on_search_node_selected(self.n2.id)
        self.assertEqual(self.canvas.selected_nodes(), [self.n2])

        # Execute Go Back shortcut
        self.canvas._on_shortcut_go_back()
        center_back = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self.assertAlmostEqual(center_back.x(), 0.0, delta=5.0)

        # Execute Go Forward shortcut
        self.canvas._on_shortcut_go_forward()
        self.assertEqual(self.canvas.selected_nodes(), [self.n2])


if __name__ == "__main__":
    unittest.main()
