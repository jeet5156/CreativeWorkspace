import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication

from models.project import Project
from core.inspectable import InspectableObject, InspectableSection, InspectableField
from core.inspectable_adapters import ProjectInspectable, AssetInspectable, NodeInspectable
from ui.panels.inspector_panel import InspectorPanel
from ui.widgets.project_tree_card import ProjectTreeCard
from ui.lab.nodes.node_registry import NodeRegistry

app = QApplication.instance() or QApplication([])


class TestInspectableArchitecture(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project = Project(name="Cyberpunk Game", project_type="game", location=self.temp_dir)
        self.project.description = "Next-gen spatial RPG game project."

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_inspectable_sections_and_fields(self):
        """Verify ProjectInspectable generates General, Organization, Preview, and Metadata sections."""
        adapter = ProjectInspectable(self.project)
        self.assertEqual(adapter.get_display_name(), "Cyberpunk Game")
        self.assertEqual(adapter.get_display_icon(), "📁")

        sections = adapter.get_inspection_sections()
        self.assertEqual(len(sections), 4)

        section_titles = [s.title for s in sections]
        self.assertIn("General", section_titles)
        self.assertIn("Organization", section_titles)
        self.assertIn("Appearance", section_titles)
        self.assertIn("Metadata", section_titles)

    def test_project_inspectable_property_mutation(self):
        """Verify mutating properties via InspectableObject updates underlying Project model."""
        adapter = ProjectInspectable(self.project)

        # Mutate Name
        res = adapter.set_inspectable_property("name", "Cyberpunk 2099")
        self.assertTrue(res)
        self.assertEqual(self.project.name, "Cyberpunk 2099")

        # Mutate Priority
        res = adapter.set_inspectable_property("priority", "high")
        self.assertTrue(res)
        self.assertEqual(getattr(self.project, "priority"), "high")

        # Mutate Status
        res = adapter.set_inspectable_property("status", "in progress")
        self.assertTrue(res)
        self.assertEqual(getattr(self.project, "status"), "in progress")

    def test_universal_inspector_panel_renders_inspectable(self):
        """Verify InspectorPanel consumes InspectableObject dynamically."""
        panel = InspectorPanel()
        adapter = ProjectInspectable(self.project)

        panel.inspect(adapter)
        self.assertEqual(panel._current_inspectable, adapter)
        self.assertIn("Cyberpunk Game", panel.header_title.text())

        # Test inspecting None resets panel cleanly
        panel.inspect(None)
        self.assertIsNone(panel._current_inspectable)
        self.assertEqual(panel.header_title.text(), "Inspector")

    def test_project_tree_card_lightweight_geometry(self):
        """Verify ProjectTreeCard maintains fixed 38px height for clean IDE rows."""
        card = ProjectTreeCard(self.project)
        self.assertEqual(card.height(), 38)
        self.assertEqual(card.sizeHint().height(), 38)

        card.set_expanded(True)
        self.assertEqual(card.sizeHint().height(), 38)

    def test_node_inspectable_adapter(self):
        """Verify NodeInspectable wraps spatial Lab node."""
        node = NodeRegistry.create_node("note.goal")
        adapter = NodeInspectable(node)

        self.assertEqual(adapter.get_display_name(), "Goal Card")
        sections = adapter.get_inspection_sections()
        self.assertGreaterEqual(len(sections), 1)


if __name__ == "__main__":
    unittest.main()
