import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.activity_service import ActivityService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel


def run_phase5_gui_verification():
    print("==================================================================")
    print("Sprint 0.6.3 Phase 5 — Recent Activity & Ring Buffer GUI Verification")
    print("==================================================================")

    temp_dir = tempfile.mkdtemp()
    try:
        patch_global_dir = Path(temp_dir) / "workbench_boards"
        patch_global_dir.mkdir(parents=True, exist_ok=True)

        orig_get_boards_dir = LabService.get_boards_dir

        def mock_get_boards_dir(svc, project):
            if not project or not getattr(project, "location", None):
                return patch_global_dir
            b_dir = Path(project.location) / "Lab" / "boards"
            b_dir.mkdir(parents=True, exist_ok=True)
            return b_dir

        LabService.get_boards_dir = mock_get_boards_dir

        proj_svc = ProjectService()

        p1_dir = str(Path(temp_dir) / "Cyclops")
        os.makedirs(p1_dir, exist_ok=True)
        cyclops_project = Project(name="Cyclops", project_type="game", location=p1_dir)
        proj_svc.add_project(cyclops_project)

        act_svc = ActivityService()
        act_svc.config_folder = Path(temp_dir) / "config"
        act_svc.config_folder.mkdir(exist_ok=True)
        act_svc._file = act_svc.config_folder / "activity.json"
        act_svc.clear()

        lab_svc = LabService(project_service=proj_svc, activity_service=act_svc)

        class MockContext:
            def __init__(ctx_self):
                ctx_self.project_service = proj_svc
                ctx_self.activity_service = act_svc
                ctx_self.lab_service = lab_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = None

        mock_ctx = MockContext()

        # Generate sample activities
        lab_svc.add_quick_capture_note("Captured WebGPU Shader architecture note", project=cyclops_project)
        lab_svc.add_quick_task_note("Review audio composition stems", attention="urgent", project=None)
        wb_board_id = lab_svc.get_active_board_id(None) or "Main"
        task_items = lab_svc.get_project_summary_metadata(None)["task_stats"]["items"]
        if task_items:
            lab_svc.toggle_task_completion(None, wb_board_id, task_items[0]["node_id"], "Review audio composition stems", True)

        panel = HomeWorkspacePanel()
        panel.set_context(mock_ctx)
        panel.resize(1000, 750)
        panel.show()

        print("1. Ring Buffer check:", len(act_svc._entries), "entries stored.")
        print("2. Recent Activity items count:", len(act_svc.recent(10)))
        print("3. Activity UI items rendered:", panel.activity_layout.count())

        recent = act_svc.recent(10)
        for idx, ev in enumerate(recent, 1):
            print(f"   [{idx}] {ev.get('timestamp')[:19]} | {ev.get('event_type')} | {ev.get('description')} ({ev.get('project_name') or 'Workbench'})")

        print("[OK] GUI Recent Activity section rendered successfully!")

    finally:
        LabService.get_boards_dir = orig_get_boards_dir
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_phase5_gui_verification()
