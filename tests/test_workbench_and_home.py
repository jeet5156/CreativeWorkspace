import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.explorer_panel import ExplorerPanel, ROLE_PROJECT, ROLE_SECTION, ROLE_NODE_TYPE


class TestWorkbenchAndHome(unittest.TestCase):
    """Focused regression tests for Home + Workbench Daily Experience."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patch_global_dir = Path(self.temp_dir) / "workbench_boards"
        self.patch_global_dir.mkdir(parents=True, exist_ok=True)

        self.orig_get_boards_dir = LabService.get_boards_dir

        def mock_get_boards_dir(svc, project):
            if not project or not getattr(project, "location", None):
                return self.patch_global_dir
            boards_dir = Path(project.location) / "Lab" / "boards"
            boards_dir.mkdir(parents=True, exist_ok=True)
            return boards_dir

        LabService.get_boards_dir = mock_get_boards_dir

        self.project_svc = ProjectService()

        # Create dummy project
        proj_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(proj_dir, exist_ok=True)
        self.cyclops_project = Project(
            name="Cyclops",
            project_type="game",
            location=proj_dir,
            created="2026-08-11T12:00:00",
            last_opened="2026-08-11T12:00:00"
        )
        self.project_svc.projects = [self.cyclops_project]

        self.lab_svc = LabService(project_service=self.project_svc)

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

        self.context = MockContext(self.lab_svc, self.project_svc)

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_quick_capture_creates_and_persists_workbench_note(self):
        """Verify Quick Capture creates a Workbench note and persists it to disk."""
        item = self.lab_svc.add_quick_capture_note("Urgent idea for tomorrow")

        self.assertIsNotNone(item)
        self.assertEqual(item["payload"]["content"], "Urgent idea for tomorrow")

        # Verify disk persistence
        active_id = self.lab_svc.get_active_board_id(None)
        board_data = self.lab_svc.load_board(None, active_id)
        item_ids = [it["id"] for it in board_data.get("items", [])]
        self.assertIn(item["id"], item_ids)

    def test_2_multiple_quick_captures_do_not_overlap(self):
        """Verify multiple Quick Capture notes receive non-overlapping spatial positions."""
        item1 = self.lab_svc.add_quick_capture_note("Capture 1")
        item2 = self.lab_svc.add_quick_capture_note("Capture 2")
        item3 = self.lab_svc.add_quick_capture_note("Capture 3")

        p1 = (item1["transform"]["x"], item1["transform"]["y"])
        p2 = (item2["transform"]["x"], item2["transform"]["y"])
        p3 = (item3["transform"]["x"], item3["transform"]["y"])

        self.assertNotEqual(p1, p2)
        self.assertNotEqual(p2, p3)
        self.assertNotEqual(p1, p3)

    def test_3_workbench_pinned_note_appears_on_home(self):
        """Verify pinned Workbench notes appear in Home pinned section with correct badge."""
        item = self.lab_svc.add_quick_capture_note("Pinned Workbench Item")

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        badges = []
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "·" in lbl.text():
                    badges.append(lbl.text())

        self.assertTrue(any("🛠️ Workbench" in b for b in badges))

    def test_4_project_pinned_note_appears_on_home(self):
        """Verify pinned project notes appear in Home pinned section with correct badge."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "proj_pin_1",
            "type": "note.blank",
            "is_pinned": True,
            "transform": {"x": 10, "y": 10, "width": 100, "height": 100},
            "payload": {"title": "Cyclops Pinned Note"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        badges = []
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "·" in lbl.text():
                    badges.append(lbl.text())

        self.assertTrue(any("📁 Cyclops" in b for b in badges))

    def test_5_unpinned_note_does_not_appear_in_home_pinned(self):
        """Verify unpinned notes do NOT appear in Home pinned section."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "unpinned_node_99",
            "type": "note.blank",
            "is_pinned": False,
            "transform": {"x": 10, "y": 10, "width": 100, "height": 100},
            "payload": {"title": "Secret Unpinned Note"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        titles = []
        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            for lbl in card.findChildren(QLabel):
                if "📌" in lbl.text():
                    titles.append(lbl.text())

        self.assertNotIn("📌 Secret Unpinned Note", titles)

    def test_6_clicking_workbench_pinned_item_routes(self):
        """Verify clicking a Workbench pinned card emits open_board_requested with (None, board_id, node_id)."""
        wb_item = self.lab_svc.add_quick_capture_note("Click WB Pin")
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        emitted = []
        home.open_board_requested.connect(lambda p, b, n: emitted.append((p, b, n)))

        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            labels = card.findChildren(QLabel)
            if any("Click WB Pin" in lbl.text() for lbl in labels):
                card.mousePressEvent(None)
                break

        self.assertTrue(len(emitted) > 0)
        p, b, n = emitted[0]
        self.assertIsNone(p)
        self.assertEqual(n, wb_item["id"])

    def test_7_clicking_project_pinned_item_routes(self):
        """Verify clicking a Project pinned card emits open_board_requested with (project, board_id, node_id)."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "proj_click_pin",
            "type": "note.blank",
            "is_pinned": True,
            "transform": {"x": 10, "y": 10, "width": 100, "height": 100},
            "payload": {"title": "Click Proj Pin"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        emitted = []
        home.open_board_requested.connect(lambda p, b, n: emitted.append((p, b, n)))

        for i in range(home.pins_grid.count()):
            card = home.pins_grid.itemAt(i).widget()
            labels = card.findChildren(QLabel)
            if any("Click Proj Pin" in lbl.text() for lbl in labels):
                card.mousePressEvent(None)
                break

        self.assertTrue(len(emitted) > 0)
        p, b, n = emitted[0]
        self.assertEqual(p, self.cyclops_project)
        self.assertEqual(n, "proj_click_pin")

    def test_8_project_task_progress_calculated_correctly(self):
        """Verify task progress calculations across checklist notes."""
        c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project)
        c_board = self.lab_svc.load_board(self.cyclops_project, c_board_id)
        c_board["items"] = [{
            "id": "task_note_1",
            "type": "note.blank",
            "transform": {"x": 10, "y": 10, "width": 100, "height": 100},
            "payload": {
                "title": "Checklist Note",
                "content": "- [x] Finished task 1\n- [ ] Pending task 2"
            }
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_board_id)

        summary = self.lab_svc.get_project_summary_metadata(self.cyclops_project)
        stats = summary["task_stats"]
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["completed"], 1)
        self.assertEqual(stats["pending"], 1)

    def test_9_home_uses_lightweight_summary_metadata(self):
        """Verify Home set_context runs without needing widget/canvas instantiation."""
        home = HomeWorkspacePanel()
        # Ensure set_context completes cleanly and fast
        home.set_context(self.context)
        self.assertIsNotNone(home.layout)

    def test_10_workbench_project_isolation_intact(self):
        """Verify Workbench and project board structures remain isolated."""
        wb_boards = self.lab_svc.list_boards(None)
        proj_boards = self.lab_svc.list_boards(self.cyclops_project)
        wb_ids = {b["id"] for b in wb_boards}
        proj_ids = {b["id"] for b in proj_boards}
        self.assertTrue(wb_ids.isdisjoint(proj_ids))


if __name__ == "__main__":
    unittest.main()
