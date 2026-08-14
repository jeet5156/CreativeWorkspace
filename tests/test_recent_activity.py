import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.activity_service import ActivityService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel


class TestRecentActivity(unittest.TestCase):
    """Phase 5 Unit Test Suite: Persistent Activity Ring Buffer & Home Recent Activity Section."""

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

        self.act_svc = ActivityService()
        self.act_svc.config_folder = Path(self.temp_dir) / "config"
        self.act_svc.config_folder.mkdir(exist_ok=True)
        self.act_svc._file = self.act_svc.config_folder / "activity.json"
        self.act_svc.clear()

        self.lab_svc = LabService(project_service=self.proj_svc, activity_service=self.act_svc)

        class MockContext:
            def __init__(ctx_self, lab_svc, proj_svc, act_svc):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.activity_service = act_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = None

        self.context = MockContext(self.lab_svc, self.proj_svc, self.act_svc)

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_ring_buffer_capped_at_100_events(self):
        """1. Verify ActivityService ring buffer is capped at 100 entries and returns newest-first."""
        for idx in range(120):
            self.act_svc.record(action=f"action_{idx}", description=f"Event {idx}")

        entries = self.act_svc._entries
        self.assertEqual(len(entries), 100)
        self.assertEqual(entries[0]["action"], "action_20")
        self.assertEqual(entries[-1]["action"], "action_119")

        recent = self.act_svc.recent(limit=10)
        self.assertEqual(len(recent), 10)
        self.assertEqual(recent[0]["action"], "action_119")
        self.assertEqual(recent[-1]["action"], "action_110")

    def test_2_structured_event_payload(self):
        """2. Verify internal activity event metadata schema."""
        self.act_svc.record(
            action="quick_capture",
            event_type="quick_capture",
            description="Captured shader idea",
            project=self.cyclops_project,
            board_id="Main",
            node_id="node_abc123",
            details={"tags": ["shader", "webgl"]},
        )

        recent = self.act_svc.recent(limit=1)
        self.assertEqual(len(recent), 1)
        ev = recent[0]

        self.assertEqual(ev["event_type"], "quick_capture")
        self.assertEqual(ev["description"], "Captured shader idea")
        self.assertEqual(ev["project_name"], "Cyclops")
        self.assertEqual(ev["project_location"], self.cyclops_project.location)
        self.assertEqual(ev["board_id"], "Main")
        self.assertEqual(ev["node_id"], "node_abc123")
        self.assertIn("timestamp", ev)

    def test_3_lab_service_action_logging(self):
        """3. Verify LabService logs Quick Capture, Quick Task, Task Completion, Move, and Copy."""
        # 1. Quick Capture
        qc_item = self.lab_svc.add_quick_capture_note("Research PBR Materials", project=self.cyclops_project)
        self.assertIsNotNone(qc_item)

        # 2. Quick Task
        qt_item = self.lab_svc.add_quick_task_note("Bake lightmaps", project=None)
        self.assertIsNotNone(qt_item)

        # 3. Task Completion
        wb_board_id = self.lab_svc.get_active_board_id(None) or "Main"
        self.lab_svc.toggle_task_completion(None, wb_board_id, qt_item["id"], "Bake lightmaps", True)

        # 4. Move Node
        moved = self.lab_svc.move_node(None, wb_board_id, self.cyclops_project, "Main", qt_item["id"])
        self.assertIsNotNone(moved)

        # 5. Copy Node
        copied = self.lab_svc.copy_node(self.cyclops_project, "Main", None, wb_board_id, qc_item["id"])
        self.assertIsNotNone(copied)

        # Inspect logged activities
        recent = self.act_svc.recent(limit=10)
        event_types = [ev["event_type"] for ev in recent]

        self.assertIn("quick_capture", event_types)
        self.assertIn("quick_task", event_types)
        self.assertIn("task_complete", event_types)
        self.assertIn("move_nodes", event_types)
        self.assertIn("copy_nodes", event_types)

    def test_4_home_panel_recent_activity_rendering_and_clicks(self):
        """4. Verify HomeWorkspacePanel renders Recent Activity newest-first and clicking emits open_board_requested."""
        self.act_svc.record(
            action="quick_task",
            event_type="quick_task",
            description="Created task 'Review UI'",
            project=self.cyclops_project,
            board_id="Main",
            node_id="target_node_99",
        )

        panel = HomeWorkspacePanel()
        panel.set_context(self.context)

        emitted_signals = []
        panel.open_board_requested.connect(lambda proj, b_id, nid: emitted_signals.append((proj, b_id, nid)))

        # Find rendered activity widgets inside activity_layout
        act_widgets = [panel.activity_layout.itemAt(i).widget() for i in range(panel.activity_layout.count()) if panel.activity_layout.itemAt(i).widget()]
        self.assertGreater(len(act_widgets), 0)

        # Click top activity row
        top_widget = act_widgets[0]
        top_widget.mousePressEvent(None)

        self.assertEqual(len(emitted_signals), 1)
        proj_arg, b_arg, nid_arg = emitted_signals[0]
        self.assertEqual(proj_arg.name, "Cyclops")
        self.assertEqual(b_arg, "Main")
        self.assertEqual(nid_arg, "target_node_99")


if __name__ == "__main__":
    unittest.main()
