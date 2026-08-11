import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication

from core.app_context import AppContext
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.dashboard_panel import DashboardPanel

app = QApplication.instance() or QApplication(sys.argv)


class TestProjectLabCohesion(unittest.TestCase):
    """Test suite for Sprint 0.6.2 Project & Lab Cohesion derived metadata & Dashboard integration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.context = AppContext()
        self.ps = ProjectService()
        self.lab_svc = LabService(project_service=self.ps)
        self.context.project_service = self.ps
        self.context.lab_service = self.lab_svc

        proj_dir = str(Path(self.temp_dir) / "CohesionProj")
        self.project = self.ps.create_project(
            name="CohesionProj",
            project_type="game",
            location=proj_dir,
            description="Sprint 0.6.2 Test Project",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_project_summary_metadata_derives_boards_tags_pins_tasks(self):
        """Verify get_project_summary_metadata aggregates derived data cleanly without mutating persistence."""
        # 1. Create a second board 'References'
        self.lab_svc.create_board(self.project, "References")

        # 2. Add nodes to Main board
        main_board = self.lab_svc.load_board(self.project, "Main")
        main_board["items"].append({
            "id": "node_1",
            "type": "note.blank",
            "tags": ["sculpt", "hero"],
            "is_pinned": True,
            "payload": {
                "title": "Sculpt Tasks",
                "content": "- [ ] Block out head\n- [x] Gather reference images\n- [ ] Bake high poly map"
            }
        })
        self.lab_svc.save_board(self.project, main_board, "Main")

        # 3. Add nodes to References board
        ref_board = self.lab_svc.load_board(self.project, "References")
        ref_board["items"].append({
            "id": "node_2",
            "type": "image",
            "tags": ["hero", "lighting"],
            "is_pinned": True,
            "payload": {
                "title": "Lighting Keyart",
                "image_path": "References/art.png"
            }
        })
        self.lab_svc.save_board(self.project, ref_board, "References")

        # 4. Query derived summary metadata
        summary = self.lab_svc.get_project_summary_metadata(self.project)

        # Assert boards count
        self.assertEqual(len(summary["boards"]), 2)
        b_names = [b["name"] for b in summary["boards"]]
        self.assertIn("Main", b_names)
        self.assertIn("References", b_names)

        # Assert total node count
        self.assertEqual(summary["total_nodes"], 2)

        # Assert unique tags aggregation
        self.assertEqual(summary["all_tags"], ["hero", "lighting", "sculpt"])

        # Assert pinned nodes
        self.assertEqual(len(summary["pinned_nodes"]), 2)

        # Assert task statistics
        task_stats = summary["task_stats"]
        self.assertEqual(task_stats["total"], 3)
        self.assertEqual(task_stats["completed"], 1)
        self.assertEqual(task_stats["pending"], 2)

    def test_dashboard_panel_updates_live_from_project_summary(self):
        """Verify DashboardPanel updates board gallery, pinned items, and tasks when show_project is called."""
        dashboard = DashboardPanel()
        dashboard.set_context(self.context)

        # Create board item with task note
        board_data = self.lab_svc.load_board(self.project, "Main")
        board_data["items"].append({
            "id": "dash_node",
            "type": "note.blank",
            "tags": ["ui"],
            "is_pinned": True,
            "payload": {
                "title": "Dashboard Note",
                "content": "- [x] Initial design\n- [ ] Integration test"
            }
        })
        self.lab_svc.save_board(self.project, board_data, "Main")

        # Call show_project
        dashboard.show_project(self.project)

        # Verify task summary text updated
        self.assertIn("1 / 2 Tasks Completed", dashboard.task_summary_lbl.text())
        self.assertEqual(dashboard.task_progress_bar.value(), 50)
        self.assertTrue(dashboard.open_lab_btn.isEnabled())


    def test_get_project_summary_metadata_fault_tolerance_with_corrupt_files(self):
        """Verify get_project_summary_metadata handles missing/corrupt board files gracefully without crashing."""
        # Corrupt a board file on disk
        boards_dir = self.lab_svc.get_boards_dir(self.project)
        corrupt_file = boards_dir / "corrupt_board.lab.json"
        with open(corrupt_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json payload ... }")

        # Inject corrupt board entry into manifest
        manifest = self.lab_svc.get_manifest(self.project)
        manifest["boards"].append({"id": "corrupt_board", "name": "Corrupt Board"})
        self.lab_svc.save_manifest(self.project, manifest)

        # Query summary — should complete safely without raising an exception
        summary = self.lab_svc.get_project_summary_metadata(self.project)
        self.assertIsNotNone(summary)
        self.assertIn("boards", summary)

    def test_dashboard_panel_reacts_to_board_updated_signal(self):
        """Verify DashboardPanel updates automatically when LabService emits board_updated."""
        dashboard = DashboardPanel()
        dashboard.set_context(self.context)
        dashboard.show_project(self.project)

        # Add node and save via LabService (triggers board_updated signal)
        main_board = self.lab_svc.load_board(self.project, "Main")
        main_board["items"].append({
            "id": "sig_node",
            "type": "note.blank",
            "payload": {"title": "Signal Note", "content": "- [x] Reactive check\n- [ ] Signal test"}
        })
        self.lab_svc.save_board(self.project, main_board, "Main")

        # Verify dashboard live UI updated via signal connection
        self.assertIn("1 / 2 Tasks Completed", dashboard.task_summary_lbl.text())
        self.assertEqual(dashboard.task_progress_bar.value(), 50)

    def test_task_checklist_parsing_variations(self):
        """Verify task statistics correctly parse bullet variations (* [ ], + [ ], - [X], [x])."""
        main_board = self.lab_svc.load_board(self.project, "Main")
        main_board["items"].append({
            "id": "var_node",
            "type": "note.blank",
            "payload": {
                "title": "Variations",
                "content": "* [ ] Bullet star pending\n+ [x] Bullet plus done\n- [X] Uppercase X done\n[ ] Bracket pending"
            }
        })
        self.lab_svc.save_board(self.project, main_board, "Main")

        summary = self.lab_svc.get_project_summary_metadata(self.project)
        stats = summary["task_stats"]

        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["completed"], 2)
        self.assertEqual(stats["pending"], 2)


if __name__ == "__main__":
    unittest.main()

