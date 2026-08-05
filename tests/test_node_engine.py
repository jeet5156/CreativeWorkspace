import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication

from models.project import Project
from services.lab_service import LabService
from ui.lab.nodes.node_capability import NodeCapability
from ui.lab.nodes.node_definition import NodeDefinition
from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.node_registry import NodeRegistry
from ui.widgets.infinite_canvas import InfiniteCanvas

app = QApplication.instance() or QApplication([])


class TestNodeEngineArchitecture(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project = Project(name="Studio Project", project_type="game", location=self.temp_dir)
        self.lab_service = LabService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_node_registry_single_source_of_truth(self):
        """Verify NodeRegistry registers definitions and builds context menus dynamically."""
        all_defs = NodeRegistry.list_all()
        self.assertGreaterEqual(len(all_defs), 6)

        # Check goal node registration
        goal_def = NodeRegistry.get("note.goal")
        self.assertIsNotNone(goal_def)
        self.assertEqual(goal_def.title, "Goal Card")
        self.assertEqual(goal_def.icon, "🎯")
        self.assertTrue(goal_def.has_capability(NodeCapability.CAN_EDIT_TEXT))

    def test_node_lifecycle_hooks(self):
        """Verify NodeItem lifecycle hooks (on_created, on_loaded, on_selected, on_deselected, on_property_changed)."""
        events = []

        class LifecycleNode(NodeItem):
            def on_created(self):
                events.append("created")
            def on_loaded(self):
                events.append("loaded")
            def on_selected(self):
                events.append("selected")
            def on_deselected(self):
                events.append("deselected")
            def on_property_changed(self, key, value):
                super().on_property_changed(key, value)
                events.append(f"prop_{key}:{value}")

        # Create new node
        node = LifecycleNode(definition=NodeRegistry.get("note.goal"))
        node.on_created()
        self.assertIn("created", events)

        # Mutate property
        node.on_property_changed("target_date", "2026-09-01")
        self.assertEqual(node.payload["target_date"], "2026-09-01")
        self.assertIn("prop_target_date:2026-09-01", events)

        # Selection hooks
        node.setSelected(True)
        self.assertIn("selected", events)

        node.setSelected(False)
        self.assertIn("deselected", events)

    def test_capability_system_without_type_checks(self):
        """Verify capability flags work without type checks or isinstance branching."""
        node = NodeRegistry.create_node("note.goal")
        self.assertTrue(node.has_capability(NodeCapability.CAN_EDIT_TEXT))
        self.assertTrue(node.has_capability(NodeCapability.CAN_LOCK))
        self.assertTrue(node.has_capability(NodeCapability.CAN_DUPLICATE))
        self.assertFalse(node.has_capability(NodeCapability.CAN_RESIZE))

    def test_generic_node_serialization_and_metadata(self):
        """Verify generic node serialization to_dict and restoration from_dict."""
        node = NodeRegistry.create_node("note.idea")
        node.setPos(200.0, 450.0)
        node.payload["content"] = "Procedural audio generation architecture"
        node.is_favorite = True

        data = node.to_dict()

        # Check generic serialization schema fields
        self.assertIn("id", data)
        self.assertEqual(data["type"], "note.idea")
        self.assertEqual(data["transform"]["x"], 200.0)
        self.assertEqual(data["transform"]["y"], 450.0)
        self.assertIn("created_at", data["metadata"])
        self.assertEqual(data["metadata"]["favorite"], True)
        self.assertEqual(data["payload"]["content"], "Procedural audio generation architecture")

        # Test generic restoring via NodeRegistry
        restored = NodeRegistry.create_node(data["type"], data)
        self.assertEqual(restored.id, node.id)
        self.assertEqual(restored.pos().x(), 200.0)
        self.assertEqual(restored.pos().y(), 450.0)
        self.assertEqual(restored.is_favorite, True)
        self.assertEqual(restored.payload["content"], "Procedural audio generation architecture")

    def test_infinite_canvas_generic_loader_no_switches(self):
        """Verify InfiniteCanvas loads any registered node type without switch statements."""
        canvas = InfiniteCanvas()
        item_data = {
            "id": "node_task_001",
            "type": "note.task",
            "transform": {"x": 300.0, "y": 150.0, "z": 1},
            "metadata": {"version": 1, "favorite": True},
            "payload": {"content": "Finalize node architecture"},
        }

        node = canvas.add_node(item_data)
        self.assertIsNotNone(node)
        self.assertIsInstance(node, NodeItem)
        self.assertEqual(node.definition.type_id, "note.task")
        self.assertTrue(node.has_capability(NodeCapability.CAN_EDIT_TEXT))

        found = canvas.find_node("node_task_001")
        self.assertEqual(found, node)

        canvas.remove_node("node_task_001")
        self.assertIsNone(canvas.find_node("node_task_001"))

    def test_lab_service_generic_node_persistence(self):
        """Verify LabService persists generic node dictionaries into .lab.json."""
        node_data = {
            "id": "node_problem_001",
            "type": "note.problem",
            "transform": {"x": 100.0, "y": 100.0, "z": 1},
            "metadata": {"version": 1, "locked": False},
            "payload": {"content": "Memory usage on 4K renders"},
        }

        self.assertTrue(self.lab_service.save_item(self.project, node_data))

        loaded_items = self.lab_service.load_items(self.project)
        self.assertEqual(len(loaded_items), 1)
        self.assertEqual(loaded_items[0]["id"], "node_problem_001")
        self.assertEqual(loaded_items[0]["type"], "note.problem")


if __name__ == "__main__":
    unittest.main()
