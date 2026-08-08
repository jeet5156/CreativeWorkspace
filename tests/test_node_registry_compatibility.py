import unittest
import tempfile
import shutil
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QPoint

from ui.lab.nodes.node_registry import NodeRegistry
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.frame_node_item import FrameNodeItem
from services.frame_service import FrameService

app = QApplication.instance() or QApplication([])


class TestNodeRegistryCompatibility(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()
        self.canvas.update_project_location(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_node_types_registered_and_instantiable(self):
        """Verify all 6 legacy v0.5.x note node types are registered and instantiate NoteNodeItem."""
        legacy_types = [
            "note.blank",
            "note.goal",
            "note.idea",
            "note.task",
            "note.problem",
            "note.decision",
        ]

        for type_id in legacy_types:
            defn = NodeRegistry.get(type_id)
            self.assertIsNotNone(defn, f"NodeDefinition for legacy type '{type_id}' is missing!")
            self.assertEqual(defn.category, "note")

            node = NodeRegistry.create_node(type_id)
            self.assertIsInstance(node, NoteNodeItem)
            self.assertEqual(node.definition.type_id, type_id)

    def test_new_06x_reference_node_types_registered_and_instantiable(self):
        """Verify all 0.6.x spatial reference and container node types remain registered and instantiable."""
        ref_types = [
            "image.reference",
            "document.pdf",
            "asset.3d",
            "file.reference",
            "folder.reference",
            "archive.reference",
            "frame.section",
        ]

        for type_id in ref_types:
            defn = NodeRegistry.get(type_id)
            self.assertIsNotNone(defn, f"NodeDefinition for 0.6.x type '{type_id}' is missing!")
            node = NodeRegistry.create_node(type_id)
            self.assertIsNotNone(node)

    def test_node_registry_compatibility_api_methods(self):
        """Verify list_all(), list_by_category(), and categories() compatibility API methods."""
        all_defs = NodeRegistry.list_all()
        self.assertGreaterEqual(len(all_defs), 13)

        note_defs = NodeRegistry.list_by_category("note")
        self.assertEqual(len(note_defs), 6)

        categories = NodeRegistry.categories()
        self.assertIn("note", categories)
        self.assertIn("media", categories)
        self.assertIn("document", categories)
        self.assertIn("asset", categories)
        self.assertIn("folder", categories)
        self.assertIn("archive", categories)
        self.assertIn("frame", categories)

    def test_legacy_lab_json_fixture_loading_and_preservation(self):
        """Verify an older .lab.json project containing legacy nodes loads without losing nodes or properties."""
        legacy_board_payload = {
            "version": "1.0",
            "board_id": "test_legacy",
            "items": [
                {
                    "id": "legacy_goal_1",
                    "type": "note.goal",
                    "transform": {"x": 100.0, "y": 150.0, "width": 240.0, "height": 180.0},
                    "payload": {"content": "Launch v1.0", "target_date": "2026-12-31"},
                    "metadata": {"pinned": True, "tags": ["milestone"]}
                },
                {
                    "id": "legacy_idea_1",
                    "type": "note.idea",
                    "transform": {"x": 400.0, "y": 150.0, "width": 240.0, "height": 180.0},
                    "payload": {"content": "Spatial Workspace Ideas"},
                    "metadata": {"pinned": False, "tags": ["brainstorm"]}
                },
                {
                    "id": "legacy_task_1",
                    "type": "note.task",
                    "transform": {"x": 700.0, "y": 150.0, "width": 240.0, "height": 180.0},
                    "payload": {"content": "Fix Node Registry", "completed": True},
                    "metadata": {"pinned": False}
                },
                {
                    "id": "frame_1",
                    "type": "frame.section",
                    "transform": {"x": 50.0, "y": 50.0, "width": 950.0, "height": 350.0},
                    "payload": {"title": "Legacy Tasks", "child_node_ids": ["legacy_goal_1", "legacy_idea_1", "legacy_task_1"]}
                }
            ],
            "connectors": [
                {
                    "id": "conn_1",
                    "source_id": "legacy_goal_1",
                    "target_id": "legacy_idea_1",
                    "relationship_type": "relates_to"
                }
            ]
        }

        # Load board into canvas
        for item_data in legacy_board_payload["items"]:
            self.canvas.add_node(item_data)

        for conn_data in legacy_board_payload["connectors"]:
            self.canvas.add_connector(conn_data)

        # Verify all 4 nodes were successfully instantiated
        self.assertIsNotNone(self.canvas.node("legacy_goal_1"))
        self.assertIsNotNone(self.canvas.node("legacy_idea_1"))
        self.assertIsNotNone(self.canvas.node("legacy_task_1"))
        self.assertIsNotNone(self.canvas.node("frame_1"))

        # Verify node types survived loading
        self.assertEqual(self.canvas.node("legacy_goal_1").definition.type_id, "note.goal")
        self.assertEqual(self.canvas.node("legacy_idea_1").definition.type_id, "note.idea")
        self.assertEqual(self.canvas.node("legacy_task_1").definition.type_id, "note.task")

        # Verify positions remained unchanged
        self.assertEqual(self.canvas.node("legacy_goal_1").pos().x(), 100.0)
        self.assertEqual(self.canvas.node("legacy_goal_1").pos().y(), 150.0)

        # Verify pinned state and tags survived
        self.assertTrue(getattr(self.canvas.node("legacy_goal_1"), "is_pinned", False))

        # Verify connectors survived
        self.assertIn("conn_1", self.canvas._connector_map)

    def test_unknown_node_type_fallback_preserves_serialized_data(self):
        """Verify genuinely unknown node types log a warning and fall back safely without silent deletion."""
        unknown_item_data = {
            "id": "unknown_node_99",
            "type": "custom.experimental_gadget",
            "transform": {"x": 200.0, "y": 200.0, "width": 200.0, "height": 150.0},
            "payload": {"custom_param": 42}
        }

        node = self.canvas.add_node(unknown_item_data)

        # Node must not be silently deleted or crash
        self.assertIsNotNone(node)
        self.assertEqual(node.id, "unknown_node_99")
        self.assertEqual(node.pos().x(), 200.0)

    def test_build_context_menu_contains_all_registered_node_definitions(self):
        """Verify NodeRegistry.build_context_menu constructs categories with complete node set."""
        menu = NodeRegistry.build_context_menu(self.canvas, QPointF(0, 0), lambda d, pos: None)
        self.assertIsNotNone(menu)
        self.assertFalse(menu.isEmpty())

        action_text_list = [act.text() for act in menu.actions()]
        # Check submenus for categories
        self.assertTrue(any("Note" in txt for txt in action_text_list))
        self.assertTrue(any("Media" in txt or "Document" in txt or "Asset" in txt or "Frame" in txt for txt in action_text_list))


if __name__ == "__main__":
    unittest.main()
