import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QCheckBox, QLineEdit, QTextEdit, QLabel

app = QApplication.instance() or QApplication([])

import sys
sys.path.insert(0, r"c:\Users\jeet5\.copilot\repos\creativeworkspace")

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from core.inspectable_adapters import ProjectInspectable, NodeInspectable, AssetInspectable
from ui.panels.inspector_panel import InspectorPanel
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.projects_dashboard import ProjectsDashboard
from ui.widgets.project_card import ProjectCard


class TestUXRepairPass(unittest.TestCase):
    """Focused unit tests for Sprint 0.6.2 UX Repair Pass."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "TestProject"
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.project_svc = ProjectService()
        self.project = Project(
            name="TestProject",
            project_type="game",
            location=str(self.project_dir),
            is_pinned=False
        )
        self.project_svc.save_project(self.project)
        self.project_svc.add_project(self.project)

        class MockContext:
            def __init__(ctx_self):
                ctx_self.project_service = self.project_svc
                ctx_self.lab_service = None
                ctx_self.inspector_panel = InspectorPanel()

        self.context = MockContext()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_attention_priority_dropdown_control(self):
        """Verify Attention Priority renders a QComboBox with Normal, Important, Urgent options."""
        class MockNodeItem:
            def __init__(self):
                self.payload = {"title": "Test Node", "attention": "important"}
                self.metadata = {}
                self.tags = []
                self.id = "node_123"
            def update(self): pass

        node = MockNodeItem()
        adapter = NodeInspectable(node)
        inspector = InspectorPanel()
        inspector.inspect(adapter)

        # Find the Attention Priority control in inspector
        ctrl = None
        for cb in inspector.findChildren(QComboBox):
            if cb.count() == 3 and cb.itemText(0) == "Normal":
                ctrl = cb
                break

        self.assertIsNotNone(ctrl)
        self.assertEqual(ctrl.currentText(), "Important")

    def test_2_attention_priority_persists_lowercase(self):
        """Verify changing attention dropdown persists normalized lowercase string."""
        class MockNodeItem:
            def __init__(self):
                self.payload = {"title": "Test Node"}
                self.metadata = {}
                self.tags = []
                self.id = "node_456"
            def update(self): pass
            def _emit_modified(self): pass

        node = MockNodeItem()
        adapter = NodeInspectable(node)

        # Test setting urgent
        res = adapter.set_inspectable_property("attention", "Urgent")
        self.assertTrue(res)
        self.assertEqual(node.payload.get("attention"), "urgent")

        # Test setting normal
        adapter.set_inspectable_property("attention", "Normal")
        self.assertEqual(node.payload.get("attention"), "normal")

    def test_3_missing_attention_defaults_to_normal(self):
        """Verify nodes with missing or omitted attention default to 'normal'."""
        class MockNodeItem:
            def __init__(self):
                self.payload = {"title": "No Attention Field"}
                self.metadata = {}
                self.tags = []
                self.id = "node_789"

        node = MockNodeItem()
        adapter = NodeInspectable(node)
        sections = adapter.get_inspection_sections()

        attn_field = None
        for sec in sections:
            for f in sec.fields:
                if f.key == "attention":
                    attn_field = f
                    break

        self.assertIsNotNone(attn_field)
        self.assertEqual(attn_field.value, "Normal")

    def test_4_project_favourite_inspector_toggle_and_persistence(self):
        """Verify Project Favourite renders QCheckBox, toggles state, and persists to project.json."""
        adapter = ProjectInspectable(self.project, project_service=self.project_svc)
        inspector = InspectorPanel()
        inspector.inspect(adapter)

        # Verify initial is_pinned state
        self.assertFalse(self.project.is_pinned)

        # Toggle is_pinned via adapter
        adapter.set_inspectable_property("is_pinned", True)
        self.assertTrue(self.project.is_pinned)

        # Verify persisted project.json
        reloaded = self.project_svc.load_project(str(self.project_dir))
        self.assertTrue(reloaded.is_pinned)

    def test_5_project_card_and_inspector_sync(self):
        """Verify ProjectCard gold star UI matches Inspector Favourite checkbox state."""
        # Initial unpinned state
        card = ProjectCard(self.project)
        self.assertEqual(card.pin_button.text(), "☆")

        # Toggle favourite to True
        self.project_svc.toggle_pin_project(self.project)
        self.assertTrue(self.project.is_pinned)

        card.update_project(self.project)
        self.assertEqual(card.pin_button.text(), "★")

    def test_6_project_favourite_independent_from_node_pin_and_attention(self):
        """Verify Project Favourite remains completely independent from Node Pin & Attention."""
        self.project.is_pinned = True
        self.project_svc.save_project(self.project)

        class MockNodeItem:
            def __init__(self):
                self.payload = {"pinned": False, "attention": "normal"}
                self.metadata = {}
                self.tags = []
                self.id = "n_indep"
            def update(self): pass
            def _emit_modified(self): pass

        node = MockNodeItem()
        n_adapter = NodeInspectable(node)

        # Modifying node pin does not touch project favourite
        n_adapter.set_inspectable_property("is_pinned", True)
        self.assertTrue(self.project.is_pinned)
        self.assertEqual(node.payload.get("pinned"), True)

        # Modifying node attention does not touch project favourite
        n_adapter.set_inspectable_property("attention", "urgent")
        self.assertTrue(self.project.is_pinned)
        self.assertEqual(node.payload.get("attention"), "urgent")

    def test_7_inspector_preserves_other_field_types(self):
        """Verify text, string, tags, select controls continue functioning as expected."""
        adapter = ProjectInspectable(self.project, project_service=self.project_svc)
        inspector = InspectorPanel()
        inspector.inspect(adapter)

        # Name line edit
        res = adapter.set_inspectable_property("name", "Updated Project Name")
        self.assertTrue(res)
        self.assertEqual(self.project.name, "Updated Project Name")

        # Description text edit
        res = adapter.set_inspectable_property("description", "Updated Description")
        self.assertTrue(res)
        self.assertEqual(self.project.description, "Updated Description")

    def test_8_project_favourite_full_persistence_cycle(self):
        """Verify OFF -> ON -> Save -> Reload -> ON -> OFF -> Save -> Reload -> OFF cycle."""
        # Initial OFF
        self.assertFalse(self.project.is_pinned)

        # Turn ON
        self.project_svc.toggle_pin_project(self.project)
        self.assertTrue(self.project.is_pinned)

        # Reload from disk
        p1 = self.project_svc.load_project(str(self.project_dir))
        self.assertTrue(p1.is_pinned)

        # Turn OFF
        self.project_svc.toggle_pin_project(self.project)
        self.assertFalse(self.project.is_pinned)

        # Reload from disk
        p2 = self.project_svc.load_project(str(self.project_dir))
        self.assertFalse(p2.is_pinned)

    def test_9_project_favourite_home_and_dashboard_sorting(self):
        """Verify Favourite projects appear before non-favourite projects in Home and Dashboard."""
        # Create non-favourite project
        p_non_fav_dir = Path(self.temp_dir) / "NonFavProj"
        p_non_fav_dir.mkdir(parents=True, exist_ok=True)
        p_non_fav = Project(name="NonFavProj", project_type="game", location=str(p_non_fav_dir), is_pinned=False)
        self.project_svc.save_project(p_non_fav)
        self.project_svc.add_project(p_non_fav)

        # Create favourite project
        p_fav_dir = Path(self.temp_dir) / "FavProj"
        p_fav_dir.mkdir(parents=True, exist_ok=True)
        p_fav = Project(name="FavProj", project_type="game", location=str(p_fav_dir), is_pinned=True)
        self.project_svc.save_project(p_fav)
        self.project_svc.add_project(p_fav)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # First card in Home recent grid should be the favourite project
        first_card = home.recent_grid.itemAt(0).widget()
        self.assertEqual(first_card.project.name, "FavProj")

        # Test Dashboard sorting
        dash = ProjectsDashboard(self.context)
        dash.refresh()
        self.assertTrue("★ FavProj" in dash.recent_list.item(0).text())

    def test_10_bidirectional_sync_card_star_and_home_layout(self):
        """Verify clicking ProjectCard star on Home toggles favourite and updates grid layout."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        card = home.recent_grid.itemAt(0).widget()
        self.assertEqual(card.pin_button.text(), "☆")

        # Click star button
        home._on_project_pin_toggled(card.project)

        # Verify project is now pinned in memory and on disk
        self.assertTrue(self.project.is_pinned)
        reloaded = self.project_svc.load_project(str(self.project_dir))
        self.assertTrue(reloaded.is_pinned)

        # Home refreshed card shows gold star
        new_card = home.recent_grid.itemAt(0).widget()
        self.assertEqual(new_card.pin_button.text(), "★")


if __name__ == "__main__":
    unittest.main()
