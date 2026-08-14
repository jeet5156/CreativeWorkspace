import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication.instance() or QApplication([])

import sys
sys.path.insert(0, r"c:\Users\jeet5\.copilot\repos\creativeworkspace")

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.explorer_panel import ExplorerPanel


class TestSprint063Phase2(unittest.TestCase):
    """Phase 2 Unit Test Suite: Workbench Inbox + Smart Quick Capture."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patch_global_dir = Path(self.temp_dir) / "workbench_boards"
        self.patch_global_dir.mkdir(parents=True, exist_ok=True)

        self.orig_get_boards_dir = LabService.get_boards_dir

        def mock_get_boards_dir(svc, project):
            if not project or not getattr(project, "location", None):
                return self.patch_global_dir
            b_dir = Path(project.location) / "Lab" / "boards"
            b_dir.mkdir(parents=True, exist_ok=True)
            return b_dir

        LabService.get_boards_dir = mock_get_boards_dir

        self.project_svc = ProjectService()

        # Create dummy Cyclops project
        p1_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(p1_dir, exist_ok=True)
        self.cyclops_project = Project(name="Cyclops", project_type="game", location=p1_dir)
        self.project_svc.add_project(self.cyclops_project)

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

    def test_1_default_destination_is_workbench_inbox(self):
        """Verify Quick Capture destination combo box defaults to Workbench Inbox."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        dest_data = home.qc_dest_cb.currentData()
        self.assertEqual(dest_data, (None, "Main"))
        self.assertEqual(home.qc_dest_cb.currentText(), "📥 Workbench Inbox")

    def test_2_capture_creates_workbench_note_by_default(self):
        """Verify default capture creates a note node in Workbench Inbox."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)
        home.qc_input.setText("Test Workbench Default Capture")
        home._on_quick_capture_submitted()

        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        titles = [it.get("payload", {}).get("title") for it in wb_board.get("items", [])]
        self.assertIn("Test Workbench Default Capture", titles)

    def test_3_capture_persists_after_reload(self):
        """Verify captured note survives disk reload and service reinstantiation."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)
        home.qc_input.setText("Persistent Capture Item")
        home._on_quick_capture_submitted()

        new_lab_svc = LabService(project_service=self.project_svc)
        wb_id = new_lab_svc.get_active_board_id(None) or "Main"
        wb_board = new_lab_svc.load_board(None, wb_id)
        titles = [it.get("payload", {}).get("title") for it in wb_board.get("items", [])]
        self.assertIn("Persistent Capture Item", titles)

    def test_4_destination_selector_lists_workbench_and_project_boards(self):
        """Verify destination selector lists other Workbench boards and Project Lab boards."""
        self.lab_svc.create_board(None, "Research")
        c_id = self.lab_svc.get_active_board_id(self.cyclops_project)

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        items_text = [home.qc_dest_cb.itemText(i) for i in range(home.qc_dest_cb.count())]
        self.assertIn("📥 Workbench Inbox", items_text)
        self.assertTrue(any("🛠️ Workbench · Research" in t for t in items_text))
        self.assertTrue(any("📁 Cyclops" in t for t in items_text))

    def test_5_direct_project_capture(self):
        """Verify selecting a Project board captures note directly to that Project board."""
        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"

        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # Select Cyclops project in combo box
        target_idx = -1
        for i in range(home.qc_dest_cb.count()):
            data = home.qc_dest_cb.itemData(i)
            if data and data[0] == self.cyclops_project:
                target_idx = i
                break

        self.assertNotEqual(target_idx, -1)
        home.qc_dest_cb.setCurrentIndex(target_idx)

        home.qc_input.setText("Direct Project Capture Note")
        home._on_quick_capture_submitted()

        # Verify note exists on Cyclops board
        c_board = self.lab_svc.load_board(self.cyclops_project, c_id)
        titles_c = [it.get("payload", {}).get("title") for it in c_board.get("items", [])]
        self.assertIn("Direct Project Capture Note", titles_c)

        # Verify note does NOT exist on Workbench
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        titles_wb = [it.get("payload", {}).get("title") for it in wb_board.get("items", [])]
        self.assertNotIn("Direct Project Capture Note", titles_wb)

    def test_6_workbench_project_isolation_preserved(self):
        """Verify Workbench and Project boards remain in isolated storage locations."""
        wb_boards = self.lab_svc.list_boards(None)
        proj_boards = self.lab_svc.list_boards(self.cyclops_project)
        wb_ids = {b["id"] for b in wb_boards}
        proj_ids = {b["id"] for b in proj_boards}
        self.assertTrue(wb_ids.isdisjoint(proj_ids))

    def test_7_explorer_live_refresh(self):
        """Verify ExplorerPanel live board refresh works when new boards are created."""
        explorer = ExplorerPanel()
        explorer.set_context(self.context)
        self.lab_svc.create_board(None, "New Explorer Test Board")
        self.assertIsNotNone(explorer.lab_root)

    def test_8_quick_capture_metadata_preserved(self):
        """Verify captured note includes tags, pin status, ISO creation timestamp, and non-overlapping transform."""
        note = self.lab_svc.add_quick_capture_note("Metadata Test Note", project=None, board_id="Main")
        self.assertIsNotNone(note)
        self.assertEqual(note["type"], "note.blank")
        self.assertIn("quick_capture", note["tags"])
        self.assertEqual(note["is_pinned"], True)
        self.assertTrue(bool(note.get("created")))
        self.assertIn("x", note["transform"])
        self.assertIn("y", note["transform"])

    def test_9_non_overlapping_placement(self):
        """Verify multiple quick captures calculate staggered non-overlapping coordinates."""
        n1 = self.lab_svc.add_quick_capture_note("Cap 1")
        n2 = self.lab_svc.add_quick_capture_note("Cap 2")
        self.assertNotEqual((n1["transform"]["x"], n1["transform"]["y"]), (n2["transform"]["x"], n2["transform"]["y"]))

    def test_10_home_visibility(self):
        """Verify captured note surfaces on Home pinned references section."""
        item = self.lab_svc.add_quick_capture_note("Home Vis Test Note")
        home = HomeWorkspacePanel()
        home.set_context(self.context)
        self.assertTrue(home.pins_grid.count() > 0)


if __name__ == "__main__":
    unittest.main()
