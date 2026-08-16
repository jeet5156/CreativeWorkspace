import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.workspace_manager import WorkspaceManager
from ui.panels.lab_panel import LabPanel
from ui.panels.workspace_panel import WorkspacePanel
from ui.panels.inspector_panel import InspectorPanel


class MockAppContext:
    def __init__(self, proj_svc, lab_svc):
        self.project_service = proj_svc
        self.lab_service = lab_svc
        self.current_project = None
        self.workspace_manager = None
        self.inspector_panel = None

    def set_current_project(self, project):
        self.current_project = project


def profile_detailed_breakdown():
    print("==================================================================")
    print("Lab Switching Performance Benchmark (Post-Optimization)")
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

        p1_dir = str(Path(temp_dir) / "Alpha")
        os.makedirs(p1_dir, exist_ok=True)
        alpha_proj = Project(name="Alpha", project_type="game", location=p1_dir)
        proj_svc.add_project(alpha_proj)

        p2_dir = str(Path(temp_dir) / "Beta")
        os.makedirs(p2_dir, exist_ok=True)
        beta_proj = Project(name="Beta", project_type="audio", location=p2_dir)
        proj_svc.add_project(beta_proj)

        lab_svc = LabService(project_service=proj_svc)

        alpha_b1 = lab_svc.get_active_board_id(alpha_proj) or "Main"
        alpha_b2 = lab_svc.create_board(alpha_proj, "Concepts")["id"]

        a_board1 = lab_svc.load_board(alpha_proj, alpha_b1)
        a_board1["items"] = [{"id": f"a1_n_{i}", "type": "note.blank", "transform": {"x": i*50, "y": i*50}, "payload": {"title": f"Alpha1 Note {i}"}} for i in range(15)]
        lab_svc.save_board(alpha_proj, a_board1, alpha_b1)

        a_board2 = lab_svc.load_board(alpha_proj, alpha_b2)
        a_board2["items"] = [{"id": f"a2_n_{i}", "type": "note.blank", "transform": {"x": i*50, "y": i*50}, "payload": {"title": f"Alpha2 Note {i}"}} for i in range(15)]
        lab_svc.save_board(alpha_proj, a_board2, alpha_b2)

        beta_b1 = lab_svc.get_active_board_id(beta_proj) or "Main"
        b_board1 = lab_svc.load_board(beta_proj, beta_b1)
        b_board1["items"] = [{"id": f"b1_n_{i}", "type": "note.blank", "transform": {"x": i*50, "y": i*50}, "payload": {"title": f"Beta1 Note {i}"}} for i in range(15)]
        lab_svc.save_board(beta_proj, b_board1, beta_b1)

        wb_id = lab_svc.get_active_board_id(None) or "Main"

        mock_ctx = MockAppContext(proj_svc, lab_svc)
        inspector = InspectorPanel()
        inspector._context = mock_ctx
        mock_ctx.inspector_panel = inspector

        ws_panel = WorkspacePanel()
        ws_panel._context = mock_ctx
        wm = WorkspaceManager(ws_panel, mock_ctx)
        mock_ctx.workspace_manager = wm
        lab_panel = wm.lab_panel

        print("--- Navigation Performance Timings ---")

        # 1. Workbench -> Project Alpha Board 1
        t0 = time.perf_counter()
        lab_panel.show_project(alpha_proj, board_id=alpha_b1)
        t1 = time.perf_counter()
        dur1 = (t1 - t0) * 1000.0
        print(f"1. Workbench -> Project Alpha Board 1: {dur1:.2f} ms")

        # 2. Alpha Board 1 -> Alpha Board 2 (Same project, board switch)
        t0 = time.perf_counter()
        lab_panel.show_project(alpha_proj, board_id=alpha_b2)
        t1 = time.perf_counter()
        dur2 = (t1 - t0) * 1000.0
        print(f"2. Alpha Board 1 -> Alpha Board 2:     {dur2:.2f} ms")

        # 3. Alpha Board 2 -> Alpha Board 2 (Re-selecting active board - Fast Path)
        t0 = time.perf_counter()
        lab_panel.show_project(alpha_proj, board_id=alpha_b2)
        t1 = time.perf_counter()
        dur3 = (t1 - t0) * 1000.0
        print(f"3. Re-selecting Active Board (Fast Path): {dur3:.2f} ms")

        # 4. Project Alpha -> Project Beta
        t0 = time.perf_counter()
        lab_panel.show_project(beta_proj, board_id=beta_b1)
        t1 = time.perf_counter()
        dur4 = (t1 - t0) * 1000.0
        print(f"4. Project Alpha -> Project Beta:      {dur4:.2f} ms")

        # 5. Project Beta -> Workbench
        t0 = time.perf_counter()
        lab_panel.show_project(None, board_id=wb_id)
        t1 = time.perf_counter()
        dur5 = (t1 - t0) * 1000.0
        print(f"5. Project Beta -> Workbench:           {dur5:.2f} ms")

        # 6. Full Explorer navigation path (No redundant load)
        t0 = time.perf_counter()
        wm.show_project(alpha_proj, section="lab")
        lab_panel.show_project(alpha_proj, board_id=alpha_b1)
        t1 = time.perf_counter()
        dur6 = (t1 - t0) * 1000.0
        print(f"6. Full Explorer Navigation Path:      {dur6:.2f} ms")

        print("==================================================================")

    finally:
        LabService.get_boards_dir = orig_get_boards_dir
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    profile_detailed_breakdown()
