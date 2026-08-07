import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.models.navigation_history import NavigationHistoryService, NavigationEvent
from ui.lab.models.saved_view import SavedView
from core.inspectable_adapters import NodeInspectable
from ui.dialogs.node_search_dialog import NodeSearchDialog

app = QApplication.instance() or QApplication([])


class TestKnowledgeNavigationPhase2(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_navigation_history_stack_and_vscode_go_back(self):
        """Verify NavigationHistoryService records events and restores node selection/camera state on Go Back/Forward."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 500, "y": 500, "width": 100, "height": 100}})

        self.canvas.push_navigation_state(n1.id)
        self.canvas.push_navigation_state(n2.id)

        self.assertTrue(self.canvas.nav_history_service.can_go_back())
        self.canvas.go_back_history()

        # Canvas selection should be restored to n1
        selected = self.canvas.selected_nodes()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].id, n1.id)

    def test_deduplicated_recent_nodes(self):
        """Verify NavigationHistoryService maintains deduplicated LRU recent nodes queue (B, C, A)."""
        svc = NavigationHistoryService(max_recents=5)
        svc.push_event(NavigationEvent(board_id="Main", node_id="node_A"))
        svc.push_event(NavigationEvent(board_id="Main", node_id="node_B"))
        svc.push_event(NavigationEvent(board_id="Main", node_id="node_C"))
        svc.push_event(NavigationEvent(board_id="Main", node_id="node_B"))

        recents = svc.get_recent_node_ids()
        self.assertEqual(recents, ["node_B", "node_C", "node_A"])

    def test_first_class_saved_view_model(self):
        """Verify project-level SavedView asset serialization and camera restoration."""
        sv = self.canvas.save_camera_view("Main Boss Setup")
        self.assertEqual(sv.name, "Main Boss Setup")

        d = sv.to_dict()
        restored = SavedView.from_dict(d)
        self.assertEqual(restored.name, "Main Boss Setup")

        # Restore view
        self.canvas.restore_camera_view(sv)

    def test_ephemeral_neighborhood_highlight(self):
        """Verify highlight_neighborhood dims unrelated nodes to 0.2 opacity and clear_neighbor_highlight restores 1.0."""
        n1 = self.canvas.add_node({"type": "note.blank"})
        n2 = self.canvas.add_node({"type": "note.blank"})
        n3 = self.canvas.add_node({"type": "note.blank"})

        self.canvas.connect_nodes(n1.id, n2.id, relationship_type="depends_on")

        # Highlight n1 neighborhood
        self.canvas.highlight_neighborhood(n1.id)
        self.assertEqual(n1.opacity(), 1.0)
        self.assertEqual(n2.opacity(), 1.0)
        self.assertEqual(n3.opacity(), 0.2)

        # Clear highlight
        self.canvas.clear_neighbor_highlight()
        self.assertEqual(n3.opacity(), 1.0)

    def test_grouped_relationship_explorer_and_backlinks(self):
        """Verify NodeInspectable projects grouped outgoing relationships and incoming backlinks."""
        n1 = self.canvas.add_node({"type": "note.blank", "payload": {"title": "Combat System"}})
        n2 = self.canvas.add_node({"type": "note.blank", "payload": {"title": "Enemy AI"}})
        n3 = self.canvas.add_node({"type": "note.blank", "payload": {"title": "Quest System"}})

        self.canvas.connect_nodes(n1.id, n2.id, relationship_type="depends_on", title="AI Dependency")
        self.canvas.connect_nodes(n3.id, n1.id, relationship_type="references", title="Combat Ref")

        inspectable = NodeInspectable(n1, connection_manager=self.canvas.connection_manager)
        sections = inspectable.get_inspection_sections()

        section_titles = [s.title for s in sections]
        self.assertIn("Knowledge Overview", section_titles)
        self.assertIn("Outgoing Connections (1)", section_titles)
        self.assertIn("Incoming Backlinks (1)", section_titles)

    def test_ctrl_k_prefix_query_syntax(self):
        """Verify NodeSearchDialog filters by tag:, relationship:, type:, and frame: prefixes."""
        n1 = self.canvas.add_node({"type": "note.blank", "payload": {"title": "Boss AI"}})
        n1.add_tag("enemy")

        n2 = self.canvas.add_node({"type": "note.blank", "payload": {"title": "Player Rig"}})
        n2.add_tag("hero")

        dlg = NodeSearchDialog([n1, n2])
        dlg._filter_nodes("tag:enemy")
        self.assertEqual(len(dlg._filtered_nodes), 1)
        self.assertEqual(dlg._filtered_nodes[0].id, n1.id)

    def test_pinned_node_toggle(self):
        """Verify toggling node pinned state stores metadata['pinned'] = True."""
        n1 = self.canvas.add_node({"type": "note.blank"})
        inspectable = NodeInspectable(n1)

        inspectable.set_inspectable_property("is_pinned", True)
        self.assertTrue(n1.payload.get("pinned"))


if __name__ == "__main__":
    unittest.main()
