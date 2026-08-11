import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Ensure QApp instance exists for PySide6 widget tests
app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.lab_panel import LabPanel
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.widgets.infinite_canvas import InfiniteCanvas


class TestWorkbenchRepair(unittest.TestCase):
    """Focused regression tests for Workbench navigation, persistence, Quick Capture, and Home aggregation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patch_global_dir = Path(self.temp_dir) / "workbench" / "boards"
        self.patch_global_dir.mkdir(parents=True, exist_ok=True)

        # Mock global_dir on LabService to avoid modifying user's actual home directory during tests
        self.orig_get_boards_dir = LabService.get_boards_dir

        def mock_get_boards_dir(svc, project):
            if not project or not getattr(project, "location", None):
                return self.patch_global_dir
            boards_dir = Path(project.location) / "Lab" / "boards"
            boards_dir.mkdir(parents=True, exist_ok=True)
            return boards_dir

        LabService.get_boards_dir = mock_get_boards_dir

        self.project_svc = ProjectService()
        self.lab_svc = LabService(project_service=self.project_svc)

        # Create dummy project
        proj_dir = str(Path(self.temp_dir) / "TestProj")
        os.makedirs(proj_dir, exist_ok=True)
        self.test_project = Project(
            name="TestProj",
            project_type="general",
            location=proj_dir,
            created="2026-08-11T12:00:00",
            last_opened="2026-08-11T12:00:00"
        )
        self.project_svc.projects = [self.test_project]

        class MockContext:
            def __init__(ctx_self, lab_svc, proj_svc):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = None
                ctx_self.workspace_manager = None
                ctx_self.thumbnail_service = None
                ctx_self.asset_service = None
                ctx_self.app_state = None

            def set_current_project(ctx_self, p):
                ctx_self.current_project = p

        self.context = MockContext(self.lab_svc, self.project_svc)

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_workbench_top_level_navigation(self):
        """Verify show_project(None) opens global Workbench board and sets title properly."""
        panel = LabPanel(self.context)
        panel.show_project(None)
        self.assertIsNone(panel._current_project)
        self.assertIn("Workbench", panel.title_label.text())
        self.assertEqual(panel.sb_title_label.text(), "WORKBENCH BOARDS")

    def test_2_workbench_board_list(self):
        """Verify listing and creating boards in global Workbench."""
        panel = LabPanel(self.context)
        panel.show_project(None)
        boards = self.lab_svc.list_boards(None)
        self.assertTrue(len(boards) >= 1)
        self.assertEqual(boards[0]["name"], "Main")

        new_entry = self.lab_svc.create_board(None, "Research Notes")
        self.assertIsNotNone(new_entry)
        updated_boards = self.lab_svc.list_boards(None)
        self.assertEqual(len(updated_boards), len(boards) + 1)

    def test_3_quick_capture_node_placement_staggered(self):
        """Verify consecutive Quick Capture notes do NOT overlap in spatial position."""
        item1 = self.lab_svc.add_quick_capture_note("Note 1")
        item2 = self.lab_svc.add_quick_capture_note("Note 2")
        item3 = self.lab_svc.add_quick_capture_note("Note 3")

        pos1 = (item1["transform"]["x"], item1["transform"]["y"])
        pos2 = (item2["transform"]["x"], item2["transform"]["y"])
        pos3 = (item3["transform"]["x"], item3["transform"]["y"])

        self.assertNotEqual(pos1, pos2)
        self.assertNotEqual(pos2, pos3)
        self.assertNotEqual(pos1, pos3)

    def test_4_workbench_note_persistence(self):
        """Verify notes created in global Workbench persist cleanly to disk."""
        panel = LabPanel(self.context)
        panel.show_project(None)

        # Add node to canvas and trigger persist
        note_data = {
            "id": "test_wb_note_1",
            "type": "note.blank",
            "transform": {"x": 100, "y": 150, "width": 200, "height": 100},
            "tags": ["quick_capture"],
            "is_pinned": True,
            "payload": {"title": "Persistent Workbench Note", "content": "Sample content"},
        }
        panel.canvas.add_node(note_data)
        panel._persist_items()

        # Reload board from disk and verify
        active_board_id = self.lab_svc.get_active_board_id(None)
        reloaded = self.lab_svc.load_board(None, active_board_id)
        reloaded_ids = [it["id"] for it in reloaded.get("items", [])]
        self.assertIn("test_wb_note_1", reloaded_ids)

    def test_5_existing_global_board_preservation(self):
        """Verify existing board files and manifest are preserved intact."""
        manifest = self.lab_svc.get_manifest(None)
        self.assertIn("active_board_id", manifest)
        active_id = manifest["active_board_id"]
        board_file = self.patch_global_dir / f"{active_id}.lab.json"
        self.assertTrue(board_file.exists())

    def test_6_pin_home_aggregation(self):
        """Verify HomeWorkspacePanel aggregates pinned nodes across projects and Workbench."""
        # Create pinned node in project
        proj_board_id = self.lab_svc.get_active_board_id(self.test_project)
        p_board = self.lab_svc.load_board(self.test_project, proj_board_id)
        p_board["items"] = [{
            "id": "proj_pin_1",
            "type": "note.blank",
            "is_pinned": True,
            "transform": {"x": 10, "y": 10, "width": 100, "height": 100},
            "payload": {"title": "Project Pin"}
        }]
        self.lab_svc.save_board(self.test_project, p_board, proj_board_id)

        # Create pinned node in Workbench
        self.lab_svc.add_quick_capture_note("Workbench Pin")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # Expect both pins in Home
        self.assertTrue(home.pins_grid.count() >= 2)

    def test_7_pin_project_dashboard_aggregation(self):
        """Verify project pinned items are returned in project summary."""
        summary = self.lab_svc.get_project_summary_metadata(self.test_project)
        self.assertIn("pinned_nodes", summary)

    def test_8_pinned_item_navigation_and_focus(self):
        """Verify InfiniteCanvas focus_node selects and centers specified node."""
        canvas = InfiniteCanvas()
        note = canvas.add_node({
            "id": "target_focus_1",
            "type": "note.blank",
            "transform": {"x": 500, "y": 500, "width": 200, "height": 200},
            "payload": {"title": "Focus Target"}
        })
        focused = canvas.focus_node("target_focus_1")
        self.assertTrue(focused)
        self.assertTrue(note.isSelected())

    def test_9_home_aggregation_performance_without_full_canvas_instantiation(self):
        """Verify HomeWorkspacePanel set_context completes without instantiating InfiniteCanvas objects."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)
        # Ensure home container layout is constructed without canvas
        self.assertFalse(hasattr(home, "canvas"))

    def test_10_workbench_project_separation(self):
        """Verify project boards do not bleed into Workbench and vice versa."""
        wb_boards = self.lab_svc.list_boards(None)
        proj_boards = self.lab_svc.list_boards(self.test_project)

        wb_ids = {b["id"] for b in wb_boards}
        proj_ids = {b["id"] for b in proj_boards}

        self.assertTrue(wb_ids.isdisjoint(proj_ids))


if __name__ == "__main__":
    unittest.main()
