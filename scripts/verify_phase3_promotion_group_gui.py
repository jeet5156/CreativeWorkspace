import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])

from models.project import Project

from services.project_service import ProjectService
from services.lab_service import LabService
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.panels.inspector_panel import InspectorPanel
from ui.dialogs.node_promotion_dialog import NodePromotionDialog
from core.inspectable_adapters import MultiNodeInspectable, NodeInspectable


def run_manual_gui_verification():
    print("==================================================================")
    print("Phase 3 Promotion Group Manual GUI Verification")
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

        lab_svc = LabService(project_service=proj_svc)

        wb_id = lab_svc.get_active_board_id(None) or "Main"
        c_id = lab_svc.get_active_board_id(cyclops_project) or "Main"

        print(f"[OK] Workbench Board ID: {wb_id}")
        print(f"[OK] Target Cyclops Board ID: {c_id}")

        # ---------------------------------------------------------------------
        # Step 1: Multi-selection Move (3 independent notes)
        # ---------------------------------------------------------------------
        print("\n--- Step 1: Move 3 Independent Notes ---")
        wb_board = lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "note_1", "type": "note.blank", "transform": {"x": 100, "y": 100}, "payload": {"title": "Note 1"}},
            {"id": "note_2", "type": "note.blank", "transform": {"x": 200, "y": 200}, "payload": {"title": "Note 2"}},
            {"id": "note_3", "type": "note.blank", "transform": {"x": 300, "y": 300}, "payload": {"title": "Note 3"}}
        ]
        lab_svc.save_board(None, wb_board, wb_id)

        moved_notes = lab_svc.move_nodes(None, wb_id, cyclops_project, c_id, ["note_1", "note_2", "note_3"])
        assert len(moved_notes) == 3, f"Expected 3 moved notes, got {len(moved_notes)}"
        print("[OK] Verified 3 independent notes moved together.")

        # ---------------------------------------------------------------------
        # Step 2: Multi-selection Copy (2 independent notes)
        # ---------------------------------------------------------------------
        print("\n--- Step 2: Copy 2 Independent Notes ---")
        wb_board = lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "copy_n1", "type": "note.blank", "transform": {"x": 50, "y": 50}, "payload": {"title": "Copy Note 1"}},
            {"id": "copy_n2", "type": "note.blank", "transform": {"x": 150, "y": 150}, "payload": {"title": "Copy Note 2"}}
        ]
        lab_svc.save_board(None, wb_board, wb_id)

        copied_notes = lab_svc.copy_nodes(None, wb_id, cyclops_project, c_id, ["copy_n1", "copy_n2"])
        assert len(copied_notes) == 2, f"Expected 2 copied notes, got {len(copied_notes)}"
        assert copied_notes[0]["id"] not in ("copy_n1", "copy_n2"), "Expected fresh UUID"
        print("[OK] Verified 2 independent notes copied with fresh UUIDs.")

        # ---------------------------------------------------------------------
        # Step 3: Frame Move (Frame + contained nodes)
        # ---------------------------------------------------------------------
        print("\n--- Step 3: Move Frame + Contained Nodes ---")
        wb_board = lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "frame_1", "type": "frame", "transform": {"x": 0, "y": 0}, "payload": {"title": "Design Frame", "child_node_ids": ["f_child_1", "f_child_2"]}},
            {"id": "f_child_1", "type": "note.blank", "transform": {"x": 20, "y": 20}, "payload": {"title": "Child 1", "parent_frame_id": "frame_1"}},
            {"id": "f_child_2", "type": "note.blank", "transform": {"x": 60, "y": 60}, "payload": {"title": "Child 2", "parent_frame_id": "frame_1"}}
        ]
        lab_svc.save_board(None, wb_board, wb_id)

        moved_frame_group = lab_svc.move_nodes(None, wb_id, cyclops_project, c_id, ["frame_1"])
        assert len(moved_frame_group) == 3, f"Expected Frame + 2 children (3 items), got {len(moved_frame_group)}"
        print("[OK] Verified Frame + contained child nodes move together.")

        # ---------------------------------------------------------------------
        # Step 4: Frame Copy with parent_frame_id Remapping
        # ---------------------------------------------------------------------
        print("\n--- Step 4: Copy Frame + Children with Parent ID Remapping ---")
        wb_board = lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "frame_src", "type": "frame", "transform": {"x": 10, "y": 10}, "payload": {"title": "Source Frame", "child_node_ids": ["c_src"]}},
            {"id": "c_src", "type": "note.blank", "transform": {"x": 30, "y": 30}, "payload": {"title": "Child Node", "parent_frame_id": "frame_src"}}
        ]
        lab_svc.save_board(None, wb_board, wb_id)

        copied_frame_group = lab_svc.copy_nodes(None, wb_id, cyclops_project, c_id, ["frame_src"])
        copied_frame = next(it for it in copied_frame_group if it["type"] == "frame")
        copied_child = next(it for it in copied_frame_group if it["type"] != "frame")
        assert copied_child["payload"]["parent_frame_id"] == copied_frame["id"], "Parent frame ID not remapped!"
        assert copied_frame["payload"]["child_node_ids"] == [copied_child["id"]], "Child node IDs not remapped!"
        print("[OK] Verified Frame + child copied with correctly remapped parent_frame_id.")

        # ---------------------------------------------------------------------
        # Step 5: Mixed Selection Deduplication
        # ---------------------------------------------------------------------
        print("\n--- Step 5: Mixed Selection Deduplication ---")
        wb_board = lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "mf1", "type": "frame", "transform": {"x": 0, "y": 0}, "payload": {"child_node_ids": ["mc1"]}},
            {"id": "mc1", "type": "note.blank", "transform": {"x": 20, "y": 20}, "payload": {"parent_frame_id": "mf1"}}
        ]
        lab_svc.save_board(None, wb_board, wb_id)

        resolved_mixed = lab_svc.resolve_promotion_group(None, wb_id, ["mf1", "mc1"])
        assert len(resolved_mixed) == 2, f"Expected deduplicated 2 items, got {len(resolved_mixed)}"
        print("[OK] Verified mixed selection resolves without duplicate items.")

        # ---------------------------------------------------------------------
        # Step 6: Connectors (Internal Preservation & External Detachment)
        # ---------------------------------------------------------------------
        print("\n--- Step 6: Connectors Safety (Internal vs External) ---")
        wb_board = lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "conn_a", "type": "note.blank", "payload": {"title": "Node A"}},
            {"id": "conn_b", "type": "note.blank", "payload": {"title": "Node B"}},
            {"id": "conn_c", "type": "note.blank", "payload": {"title": "Node C"}}
        ]
        wb_board["connectors"] = [
            {"id": "ab_conn", "source_node_id": "conn_a", "target_node_id": "conn_b"},
            {"id": "bc_conn", "source_node_id": "conn_b", "target_node_id": "conn_c"}
        ]
        lab_svc.save_board(None, wb_board, wb_id)

        # Move conn_a and conn_b (ab_conn is internal, bc_conn is external)
        lab_svc.move_nodes(None, wb_id, cyclops_project, c_id, ["conn_a", "conn_b"])

        c_board = lab_svc.load_board(cyclops_project, c_id)
        c_conns = c_board.get("connectors", [])
        assert any(c.get("source_node_id") == "conn_a" and c.get("target_node_id") == "conn_b" for c in c_conns), "Internal connector missing!"
        assert not any(c.get("source_node_id") == "conn_b" and c.get("target_node_id") == "conn_c" for c in c_conns), "External connector incorrectly transferred!"

        refreshed_wb = lab_svc.load_board(None, wb_id)
        wb_conns = refreshed_wb.get("connectors", [])
        assert len(wb_conns) == 0, "External connector was not safely detached from source board!"
        print("[OK] Verified internal connector preserved in target, external connector safely detached from source.")

        # ---------------------------------------------------------------------
        # Step 7: Inspector Integration
        # ---------------------------------------------------------------------
        print("\n--- Step 7: Inspector MultiNodeInspectable Actions ---")
        class MockContext:
            def __init__(ctx_self):
                ctx_self.project_service = proj_svc
                ctx_self.lab_service = lab_svc
                ctx_self.current_project = None

        mock_ctx = MockContext()
        inspector = InspectorPanel()
        inspector._context = mock_ctx
        canvas = InfiniteCanvas()

        canvas._context = mock_ctx
        canvas.project = None
        canvas._board_id = wb_id

        n1 = canvas.add_node({"id": "insp_n1", "type": "note.blank", "payload": {"title": "Insp 1"}})
        n2 = canvas.add_node({"id": "insp_n2", "type": "note.blank", "payload": {"title": "Insp 2"}})
        canvas.set_selected_nodes([n1, n2])

        multi_insp = MultiNodeInspectable(canvas.selected_nodes())
        inspector.inspect(multi_insp)

        sections = multi_insp.get_inspection_sections()
        act_section = next((s for s in sections if s.title == "Actions"), None)
        assert act_section is not None, "Actions section missing in MultiNodeInspectable!"
        act_keys = [f.key for f in act_section.fields]
        assert "action_move_project" in act_keys, "action_move_project missing!"
        assert "action_copy_project" in act_keys, "action_copy_project missing!"
        print("[OK] Verified MultiNodeInspectable provides Move and Copy actions to Inspector.")

        print("\n==================================================================")
        print("ALL MANUAL GUI VERIFICATION STEPS PASSED SUCCESSFULLY!")
        print("==================================================================")

    finally:
        LabService.get_boards_dir = orig_get_boards_dir
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_manual_gui_verification()
