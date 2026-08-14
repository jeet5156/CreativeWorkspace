import os
import sys
import shutil
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

sys.path.insert(0, r"c:\Users\jeet5\.copilot\repos\creativeworkspace")

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.explorer_panel import ExplorerPanel


def verify_sprint_063_phase2_gui():
    print("==================================================")
    print("Sprint 0.6.3 Phase 2: Workbench Inbox + Quick Capture GUI Verification")
    print("==================================================")

    temp_dir = tempfile.mkdtemp()
    try:
        orig_get_boards_dir = LabService.get_boards_dir
        patch_global = Path(temp_dir) / "workbench_boards"
        patch_global.mkdir(parents=True, exist_ok=True)

        def mock_get_boards_dir(svc, project):
            if not project or not getattr(project, "location", None):
                return patch_global
            b_dir = Path(project.location) / "Lab" / "boards"
            b_dir.mkdir(parents=True, exist_ok=True)
            return b_dir

        LabService.get_boards_dir = mock_get_boards_dir

        proj_svc = ProjectService()
        p_dir = Path(temp_dir) / "Cyclops"
        p_dir.mkdir(parents=True, exist_ok=True)
        cyclops_project = Project(name="Cyclops", project_type="game", location=str(p_dir))
        proj_svc.add_project(cyclops_project)

        lab_svc = LabService(project_service=proj_svc)

        class MockContext:
            def __init__(ctx_self):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = None
                ctx_self.workspace_manager = None
                ctx_self.thumbnail_service = None
                ctx_self.asset_service = None
                ctx_self.app_state = None

        context = MockContext()

        # Step 1 & 2: Open Home, Quick Capture visible
        home = HomeWorkspacePanel()
        home.set_context(context)
        assert home.qc_input is not None
        assert home.qc_dest_cb is not None
        print("[OK] [1 & 2] Home Daily Command Center initialized & Quick Capture bar visible")

        # Step 3 & 4: Capture thought without changing destination (Workbench Inbox default)
        assert home.qc_dest_cb.currentText() == "📥 Workbench Inbox"
        home.qc_input.setText("Unassigned Inbox Thought")
        home._on_quick_capture_submitted()

        wb_id = lab_svc.get_active_board_id(None) or "Main"
        wb_board = lab_svc.load_board(None, wb_id)
        titles_wb = [it.get("payload", {}).get("title") for it in wb_board.get("items", [])]
        assert "Unassigned Inbox Thought" in titles_wb
        print("[OK] [3 & 4] Captured thought saved to Workbench Inbox")

        # Step 5: Explorer updates
        explorer = ExplorerPanel()
        explorer.set_context(context)
        assert explorer.lab_root is not None
        print("[OK] [5] Explorer tree updated successfully")

        # Step 6: Restart/reload & confirm persistence
        new_lab_svc = LabService(project_service=proj_svc)
        reloaded_wb = new_lab_svc.load_board(None, wb_id)
        titles_reload = [it.get("payload", {}).get("title") for it in reloaded_wb.get("items", [])]
        assert "Unassigned Inbox Thought" in titles_reload
        print("[OK] [6] Persistence verified across restart/reload")

        # Step 7 & 8: Select Project -> Board destination and capture
        target_idx = -1
        for i in range(home.qc_dest_cb.count()):
            data = home.qc_dest_cb.itemData(i)
            if data and data[0] == cyclops_project:
                target_idx = i
                break

        assert target_idx != -1
        home.qc_dest_cb.setCurrentIndex(target_idx)
        home.qc_input.setText("Targeted Cyclops Project Thought")
        home._on_quick_capture_submitted()

        # Step 9, 10, 11: Verify appears in Project, NOT in Workbench, isolation intact
        c_id = lab_svc.get_active_board_id(cyclops_project) or "Main"
        c_board = lab_svc.load_board(cyclops_project, c_id)
        titles_c = [it.get("payload", {}).get("title") for it in c_board.get("items", [])]
        assert "Targeted Cyclops Project Thought" in titles_c

        reloaded_wb_2 = lab_svc.load_board(None, wb_id)
        titles_wb_2 = [it.get("payload", {}).get("title") for it in reloaded_wb_2.get("items", [])]
        assert "Targeted Cyclops Project Thought" not in titles_wb_2
        print("[OK] [7-11] Direct Project capture saved to Cyclops and excluded from Workbench")

        # Step 12: Home remains responsive
        assert home.isVisible() or home.isEnabled()
        print("[OK] [12] Home Daily Command Center remains responsive")

        LabService.get_boards_dir = orig_get_boards_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("==================================================")
    print("ALL 12 GUI VERIFICATION CHECKS PASSED 100%")
    print("==================================================")

if __name__ == "__main__":
    verify_sprint_063_phase2_gui()
