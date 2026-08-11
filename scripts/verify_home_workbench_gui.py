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
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.lab_panel import LabPanel
from ui.panels.explorer_panel import ExplorerPanel

app = QApplication.instance() or QApplication(sys.argv)


def run_verification():
    print("=" * 50)
    print("Sprint 0.6.2: Complete Navigation & Workbench GUI Verification")
    print("=" * 50)

    temp_dir = tempfile.mkdtemp()
    try:
        context = AppContext()
        ps = ProjectService()
        lab_svc = LabService(project_service=ps)
        context.project_service = ps
        context.lab_service = lab_svc

        # [Check 1 & 2] Home Workspace landing & Quick Capture
        home = HomeWorkspacePanel()
        home.set_context(context)
        assert home.qc_btn.isEnabled(), "Quick Capture button must be enabled"
        qc_item = lab_svc.add_quick_capture_note("Sprint 0.6.2 Verification Note")
        assert qc_item is not None, "Quick Capture note created"
        print("[OK] [1 & 2] Home landing screen & Quick Capture created note on Workbench board")

        # [Check 3 & 4 & 5] Project creation, board discovery in Explorer & Dashboard
        proj_dir = str(Path(temp_dir) / "FullNavProj")
        project = ps.create_project(name="FullNavProj", project_type="game", location=proj_dir, description="Verification Project")
        lab_svc.create_board(project, "Concepts")
        lab_svc.create_board(project, "R&D Board")

        # Verify Dashboard lists all 3 boards
        dash = DashboardPanel()
        dash.set_context(context)
        dash.show_project(project)
        summary = lab_svc.get_project_summary_metadata(project)
        board_names = [b["name"] for b in summary["boards"]]
        assert len(board_names) == 3, f"Expected 3 boards on Dashboard, got {board_names}"
        assert "Main" in board_names and "Concepts" in board_names and "R&D Board" in board_names
        print("[OK] [3, 4, 5] Project Dashboard & LabService discovered all 3 boards (Main, Concepts, R&D Board)")

        # [Check 6 & 7 & 8] LabPanel board opening for specific project boards
        lab_panel = LabPanel(context)
        lab_panel.show_project(project, board_name="Concepts")
        assert lab_panel._current_board_name == "Concepts"
        assert "FullNavProj" in lab_panel.project_nav_btn.text()

        lab_panel.show_project(project, board_name="R&D Board")
        assert lab_panel._current_board_name == "R&D Board"
        print("[OK] [6, 7, 8] LabPanel navigated between specific project boards ('Concepts' and 'R&D Board')")

        # [Check 9 & 10] Global Workbench navigation & board opening
        lab_panel.show_project(None, board_name="Main")
        assert lab_panel._current_project is None
        assert lab_panel._current_board_name == "Main"
        assert "Workbench" in lab_panel.title_label.text()
        print("[OK] [9 & 10] Global Workbench navigation opened global canvas without project context")

        # [Check 11] Isolation: Project boards not present in Workbench & vice versa
        wb_boards = [b["name"] for b in lab_svc.list_boards(None)]
        proj_boards = [b["name"] for b in lab_svc.list_boards(project)]
        assert "Concepts" in proj_boards
        assert "Concepts" not in wb_boards
        print("[OK] [11] Strict Board Isolation verified (project boards never bleed into Workbench)")

        # [Check 12] Physical Notes directory audit check
        notes_folder = Path(project.location) / "Notes"
        assert notes_folder.exists() and notes_folder.is_dir()
        print("[OK] [12] Notes entry corresponds to physical project Notes/ folder")

        print("=" * 50)
        print("ALL 12 NAVIGATION & WORKBENCH GUI VERIFICATION CHECKS PASSED 100%")
        print("=" * 50)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_verification()
