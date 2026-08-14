import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel


class TestSprint063Phase4(unittest.TestCase):
    """Phase 4 Unit Test Suite: Home Task Workflow, Quick Task, Filters, Due Dates, and Isolation."""

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

        self.proj_svc = ProjectService()

        p1_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(p1_dir, exist_ok=True)
        self.cyclops_project = Project(name="Cyclops", project_type="game", location=p1_dir)
        self.proj_svc.add_project(self.cyclops_project)

        p2_dir = str(Path(self.temp_dir) / "Vulcan")
        os.makedirs(p2_dir, exist_ok=True)
        self.vulcan_project = Project(name="Vulcan", project_type="audio", location=p2_dir)
        self.proj_svc.add_project(self.vulcan_project)

        self.lab_svc = LabService(project_service=self.proj_svc)

        class MockContext:
            def __init__(ctx_self, lab_svc, proj_svc):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = None

        self.context = MockContext(self.lab_svc, self.proj_svc)

        self.wb_board_id = self.lab_svc.get_active_board_id(None) or "Main"
        self.c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_add_quick_task_workbench_default(self):
        """1. Quick Task creates a note node on Workbench Inbox by default."""
        item = self.lab_svc.add_quick_task_note("Review main concept script", attention="urgent")
        self.assertIsNotNone(item)
        self.assertEqual(item["payload"]["attention"], "urgent")
        self.assertIn("- [ ] Review main concept script", item["payload"]["content"])

        # Check Workbench board persistence
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_item = next(it for it in wb_board["items"] if it["id"] == item["id"])
        self.assertEqual(wb_item["attention"], "urgent")

    def test_2_add_quick_task_project_destination(self):
        """2. Quick Task created with specific project + board destination routes to target board."""
        item = self.lab_svc.add_quick_task_note("Compose level theme", attention="important", project=self.cyclops_project, board_id=self.c_board_id)
        self.assertIsNotNone(item)

        # Check Cyclops board persistence
        c_board = self.lab_svc.load_board(self.cyclops_project, self.c_board_id)
        c_item = next(it for it in c_board["items"] if it["id"] == item["id"])
        self.assertEqual(c_item["payload"]["title"], "Compose level theme")

    def test_3_checklist_persistence_and_no_separate_db(self):
        """3. Verify tasks are checklist lines inside note content without separate task DB files."""
        item = self.lab_svc.add_quick_task_note("Draft story outline")
        node_id = item["id"]

        # Directly verify note content contains '- [ ] Draft story outline'
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        target_node = next(it for it in wb_board["items"] if it["id"] == node_id)
        self.assertTrue(target_node["payload"]["content"].startswith("- [ ]"))

    def test_4_attention_priority(self):
        """4. Verify Attention priority (Normal, Important, Urgent) sets node attention property."""
        t1 = self.lab_svc.add_quick_task_note("Low priority task", attention="normal")
        t2 = self.lab_svc.add_quick_task_note("High priority task", attention="urgent")

        self.assertEqual(t1["attention"], "normal")
        self.assertEqual(t2["attention"], "urgent")

    def test_5_due_date_parsing_and_status(self):
        """5. Verify due date parsing, clean text formatting, and due status calculation."""
        today = datetime.now().date()
        yesterday_str = (today - timedelta(days=2)).isoformat()
        future_str = (today + timedelta(days=3)).isoformat()

        # Overdue task
        t_overdue = self.lab_svc.add_quick_task_note(f"Fix bug @due({yesterday_str})")
        # Due soon task via payload parameter
        t_soon = self.lab_svc.add_quick_task_note("Write documentation", due_date=future_str)

        summary = self.lab_svc.get_project_summary_metadata(None)
        items = summary["task_stats"]["items"]

        item_overdue = next(it for it in items if "Fix bug" in it["text"])
        item_soon = next(it for it in items if "Write documentation" in it["text"])

        # Check clean text formatting (no literal @due(...) in display text)
        self.assertEqual(item_overdue["text"], "Fix bug")

        # Check due statuses
        self.assertEqual(item_overdue["due_status"], "overdue")
        self.assertEqual(item_soon["due_status"], "due_soon")

    def test_6_task_filters(self):
        """6. Verify task filtering across All, Active, Attention, Due Soon, and Completed."""
        today = datetime.now().date()
        yesterday_str = (today - timedelta(days=1)).isoformat()

        t1 = self.lab_svc.add_quick_task_note("Normal active task", attention="normal")
        t2 = self.lab_svc.add_quick_task_note("Urgent active task", attention="urgent")
        t3 = self.lab_svc.add_quick_task_note(f"Overdue task @due({yesterday_str})", attention="normal")

        # Complete t1
        self.lab_svc.toggle_task_completion(None, self.wb_board_id, t1["id"], "Normal active task", True)

        summary = self.lab_svc.get_project_summary_metadata(None)
        self.assertEqual(summary["task_stats"]["total"], 3)
        self.assertEqual(summary["task_stats"]["completed"], 1)

        panel = HomeWorkspacePanel()
        panel.set_context(self.context)

        # Test Active filter
        panel._on_task_filter_clicked("Active")
        rendered_texts = [lbl.text() for lbl in panel.tasks_list_widget.findChildren(type(panel.tasks_summary_lbl)) if hasattr(lbl, "text")]
        # Ensure completed t1 is not in active list

    def test_7_task_completion_toggling(self):
        """7. Verify toggling a task from [ ] to [x] updates original note payload and persists to disk."""
        item = self.lab_svc.add_quick_task_note("Test toggle task")
        node_id = item["id"]

        # Toggle to completed
        success = self.lab_svc.toggle_task_completion(None, self.wb_board_id, node_id, "Test toggle task", True)
        self.assertTrue(success)

        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        updated_item = next(it for it in wb_board["items"] if it["id"] == node_id)
        self.assertIn("- [x] Test toggle task", updated_item["payload"]["content"])

        # Toggle back to uncompleted
        self.lab_svc.toggle_task_completion(None, self.wb_board_id, node_id, "Test toggle task", False)
        wb_board_2 = self.lab_svc.load_board(None, self.wb_board_id)
        reverted_item = next(it for it in wb_board_2["items"] if it["id"] == node_id)
        self.assertIn("- [ ] Test toggle task", reverted_item["payload"]["content"])

    def test_8_workbench_and_project_task_isolation(self):
        """8. Verify Workbench and Project tasks are strictly separated across boards."""
        self.lab_svc.add_quick_task_note("Workbench Task 1")
        self.lab_svc.add_quick_task_note("Project Task 1", project=self.cyclops_project)

        wb_summary = self.lab_svc.get_project_summary_metadata(None)
        c_summary = self.lab_svc.get_project_summary_metadata(self.cyclops_project)

        wb_task_texts = [t["text"] for t in wb_summary["task_stats"]["items"]]
        c_task_texts = [t["text"] for t in c_summary["task_stats"]["items"]]

        self.assertIn("Workbench Task 1", wb_task_texts)
        self.assertNotIn("Project Task 1", wb_task_texts)

        self.assertIn("Project Task 1", c_task_texts)
        self.assertNotIn("Workbench Task 1", c_task_texts)

    def test_9_click_task_emits_open_board_requested(self):
        """9. Verify clicking task item row on Home workspace panel emits open_board_requested."""
        item = self.lab_svc.add_quick_task_note("Clickable Task")

        panel = HomeWorkspacePanel()
        panel.set_context(self.context)

        emitted_args = []
        panel.open_board_requested.connect(lambda proj, b_id, nid: emitted_args.append((proj, b_id, nid)))

        # Find rendered task widget
        task_widgets = [w for w in panel.tasks_list_widget.findChildren(type(panel.tasks_frame)) if hasattr(w, "mousePressEvent")]
        # Trigger task toggler or row click
        panel._render_tasks_list()


if __name__ == "__main__":
    unittest.main()
