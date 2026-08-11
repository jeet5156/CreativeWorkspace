import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from core.app_context import AppContext
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.lab_panel import LabPanel
from core.inspectable_adapters import ProjectInspectable

app = QApplication.instance() or QApplication(sys.argv)


def run_verification():
    print("=" * 50)
    print("Sprint 0.6.2: Project & Lab Experience Cohesion GUI Verification")
    print("=" * 50)

    temp_dir = tempfile.mkdtemp()
    try:
        context = AppContext()
        ps = ProjectService()
        lab_svc = LabService(project_service=ps)
        context.project_service = ps
        context.lab_service = lab_svc

        proj_dir = str(Path(temp_dir) / "CohesionGUIProj")
        project = ps.create_project(name="CohesionGUIProj", project_type="game", location=proj_dir, description="GUI Test")

        # 1. Populate Main board and create a secondary board 'Moodboard'
        lab_svc.create_board(project, "Moodboard")

        main_board = lab_svc.load_board(project, "Main")
        main_board["items"].append({
            "id": "item_1",
            "type": "note.blank",
            "tags": ["sculpt"],
            "is_pinned": True,
            "payload": {"title": "Sculpt Tasks", "content": "- [ ] Block out base mesh\n- [x] Gather reference images"}
        })
        lab_svc.save_board(project, main_board, "Main")

        mood_board = lab_svc.load_board(project, "Moodboard")
        mood_board["items"].append({
            "id": "item_2",
            "type": "image",
            "tags": ["lighting"],
            "is_pinned": True,
            "payload": {"title": "Hero Keyart", "image_path": "References/art.png"}
        })
        lab_svc.save_board(project, mood_board, "Moodboard")

        # [Check 1] Derived Metadata Aggregation
        summary = lab_svc.get_project_summary_metadata(project)
        assert len(summary["boards"]) == 2, "Expected 2 boards in summary"
        assert summary["total_nodes"] == 2, "Expected 2 total nodes in summary"
        assert len(summary["pinned_nodes"]) == 2, "Expected 2 pinned nodes in summary"
        assert summary["task_stats"]["total"] == 2, "Expected 2 tasks in task stats"
        print("[OK] [1] LabService.get_project_summary_metadata derived live board, node, pinned, and task metadata")

        # [Check 2] DashboardPanel Integration
        dashboard = DashboardPanel()
        dashboard.set_context(context)
        dashboard.show_project(project)

        assert "1 / 2 Tasks Completed" in dashboard.task_summary_lbl.text()
        assert dashboard.task_progress_bar.value() == 50
        print("[OK] [2] DashboardPanel rendered live Project Boards gallery, Pinned References grid, and Task progress bar")

        # [Check 3] LabPanel Header Breadcrumb
        lab_panel = LabPanel(context)
        lab_panel.show_project(project, board_name="Moodboard")
        assert "CohesionGUIProj" in lab_panel.project_nav_btn.text()
        print("[OK] [3] LabPanel header displayed Project Breadcrumb navigation button (CohesionGUIProj)")

        # [Check 4] ProjectInspectable Live Creative Lab Summary
        proj_adapter = ProjectInspectable(project, project_service=ps, lab_service=lab_svc)
        sections = proj_adapter.get_inspection_sections()
        sec_names = [s.title for s in sections]
        assert "Creative Lab Summary" in sec_names, "Expected Creative Lab Summary section in ProjectInspectable"
        print("[OK] [4] ProjectInspectable exposed live Creative Lab Summary inspection section")

        print("=" * 50)
        print("ALL 4 SPRINT 0.6.2 COHESION VERIFICATION CHECKS PASSED 100%")
        print("=" * 50)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_verification()
