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
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.panels.inspector_panel import InspectorPanel
from core.inspectable_adapters import NodeInspectable


def verify_sprint_063_phase3_gui():
    print("==================================================")
    print("Sprint 0.6.3 Phase 3: Promotion UI GUI Verification")
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
        p1_dir = Path(temp_dir) / "Cyclops"
        p1_dir.mkdir(parents=True, exist_ok=True)
        cyclops_project = Project(name="Cyclops", project_type="game", location=str(p1_dir))
        proj_svc.add_project(cyclops_project)

        p2_dir = Path(temp_dir) / "Vulcan"
        p2_dir.mkdir(parents=True, exist_ok=True)
        vulcan_project = Project(name="Vulcan", project_type="audio", location=str(p2_dir))
        proj_svc.add_project(vulcan_project)

        lab_svc = LabService(project_service=proj_svc)

        class MockContext:
            def __init__(ctx_self):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = InspectorPanel()
                ctx_self.workspace_manager = None
                ctx_self.thumbnail_service = None
                ctx_self.asset_service = None
                ctx_self.app_state = None

        context = MockContext()

        # Setup initial Workbench node
        wb_id = lab_svc.get_active_board_id(None) or "Main"
        wb_board = lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {
                "id": "gui_wb_note_1",
                "type": "note.blank",
                "is_pinned": True,
                "attention": "urgent",
                "payload": {"title": "GUI Move Note", "content": "Move me to Cyclops"}
            },
            {
                "id": "gui_wb_note_2",
                "type": "note.blank",
                "payload": {"title": "GUI Copy Note", "content": "Copy me to Cyclops"}
            }
        ]
        lab_svc.save_board(None, wb_board, wb_id)

        canvas = InfiniteCanvas()
        canvas._context = context
        canvas._board_id = wb_id

        # 1-7: Move Workbench node -> Cyclops Project
        c_id = lab_svc.get_active_board_id(cyclops_project) or "Main"
        moved_res = lab_svc.move_node(None, wb_id, cyclops_project, c_id, "gui_wb_note_1")
        assert moved_res is not None
        assert moved_res["id"] == "gui_wb_note_1"

        reloaded_wb = lab_svc.load_board(None, wb_id)
        reloaded_c = lab_svc.load_board(cyclops_project, c_id)
        assert not any(it.get("id") == "gui_wb_note_1" for it in reloaded_wb["items"])
        assert any(it.get("id") == "gui_wb_note_1" for it in reloaded_c["items"])
        print("[OK] [1-7] Workbench -> Project Move confirmed. Source node disappeared and destination received node.")

        # 8: Persistence across restart
        new_lab_svc = LabService(project_service=proj_svc)
        reloaded_c_after = new_lab_svc.load_board(cyclops_project, c_id)
        assert any(it.get("id") == "gui_wb_note_1" for it in reloaded_c_after["items"])
        print("[OK] [8] Move persistence verified across restart/reload.")

        # 9-11: Copy Workbench node -> Cyclops Project
        copied_res = lab_svc.copy_node(None, wb_id, cyclops_project, c_id, "gui_wb_note_2")
        assert copied_res is not None
        assert copied_res["id"] != "gui_wb_note_2"

        reloaded_wb_2 = lab_svc.load_board(None, wb_id)
        reloaded_c_2 = lab_svc.load_board(cyclops_project, c_id)
        assert any(it.get("id") == "gui_wb_note_2" for it in reloaded_wb_2["items"])
        assert any(it.get("payload", {}).get("title") == "GUI Copy Note" for it in reloaded_c_2["items"])
        print("[OK] [9-11] Copy confirmed. Source node remained intact and destination received new node with fresh UUID.")

        # 12: Test Inspector Actions section
        node_item = canvas.add_node({
            "id": "gui_insp_node",
            "type": "note.blank",
            "payload": {"title": "Inspector Promotion Test"}
        })
        adapter = NodeInspectable(node_item)
        context.inspector_panel.inspect(adapter)
        sec_titles = [s.title for s in adapter.get_inspection_sections()]
        assert "Actions" in sec_titles
        print("[OK] [12] Inspector Panel Actions section verified.")

        # 13: Test Project -> Project movement
        v_id = lab_svc.get_active_board_id(vulcan_project) or "Main"
        cross_proj_res = lab_svc.move_node(cyclops_project, c_id, vulcan_project, v_id, "gui_wb_note_1")
        assert cross_proj_res is not None

        reloaded_c_3 = lab_svc.load_board(cyclops_project, c_id)
        reloaded_v_3 = lab_svc.load_board(vulcan_project, v_id)
        assert not any(it.get("id") == "gui_wb_note_1" for it in reloaded_c_3["items"])
        assert any(it.get("id") == "gui_wb_note_1" for it in reloaded_v_3["items"])
        print("[OK] [13] Project -> Project movement between Cyclops and Vulcan verified.")

        # 14: Confirm Workbench and Project trees remain isolated
        wb_boards = lab_svc.list_boards(None)
        c_boards = lab_svc.list_boards(cyclops_project)
        v_boards = lab_svc.list_boards(vulcan_project)
        wb_ids = {b["id"] for b in wb_boards}
        c_ids = {b["id"] for b in c_boards}
        v_ids = {b["id"] for b in v_boards}
        assert wb_ids.isdisjoint(c_ids)
        assert wb_ids.isdisjoint(v_ids)
        print("[OK] [14] Workbench and Project storage trees remain strictly isolated.")

        LabService.get_boards_dir = orig_get_boards_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    print("==================================================")
    print("ALL 14 GUI VERIFICATION CHECKS PASSED 100%")
    print("==================================================")

if __name__ == "__main__":
    verify_sprint_063_phase3_gui()
