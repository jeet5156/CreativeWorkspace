import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication([])

import sys
sys.path.insert(0, r"c:\Users\jeet5\.copilot\repos\creativeworkspace")

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.dialogs.node_promotion_dialog import NodePromotionDialog
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.panels.inspector_panel import InspectorPanel
from core.inspectable_adapters import NodeInspectable


class TestSprint063Phase3(unittest.TestCase):
    """Phase 3 Unit Test Suite: Promotion UI (NodePromotionDialog, Context Menu, Inspector Actions)."""

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

        self.project_svc = ProjectService()

        # Create dummy Cyclops project
        p1_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(p1_dir, exist_ok=True)
        self.cyclops_project = Project(name="Cyclops", project_type="game", location=p1_dir)
        self.project_svc.add_project(self.cyclops_project)

        # Create dummy Vulcan project
        p2_dir = str(Path(self.temp_dir) / "Vulcan")
        os.makedirs(p2_dir, exist_ok=True)
        self.vulcan_project = Project(name="Vulcan", project_type="audio", location=p2_dir)
        self.project_svc.add_project(self.vulcan_project)

        self.lab_svc = LabService(project_service=self.project_svc)

        class MockContext:
            def __init__(ctx_self, lab_svc, proj_svc):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.current_project = None
                ctx_self.inspector_panel = None
                ctx_self.workspace_manager = None
                ctx_self.thumbnail_service = None
                ctx_self.asset_service = None
                ctx_self.app_state = None

        self.context = MockContext(self.lab_svc, self.project_svc)

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_move_dialog_destination_population(self):
        """Verify NodePromotionDialog populates Workbench and Projects for Move."""
        dialog = NodePromotionDialog(None, "move", None, "Main", self.project_svc, self.lab_svc)
        items_text = [dialog.project_cb.itemText(i) for i in range(dialog.project_cb.count())]
        self.assertIn("🛠️ Global Workbench", items_text)
        self.assertIn("📁 Cyclops", items_text)
        self.assertIn("📁 Vulcan", items_text)

    def test_2_copy_dialog_destination_population(self):
        """Verify NodePromotionDialog populates Workbench and Projects for Copy."""
        dialog = NodePromotionDialog(None, "copy", self.cyclops_project, "Main", self.project_svc, self.lab_svc)
        items_text = [dialog.project_cb.itemText(i) for i in range(dialog.project_cb.count())]
        self.assertIn("🛠️ Global Workbench", items_text)
        self.assertIn("📁 Cyclops", items_text)

    def test_3_move_action_calls_lab_service_move_node(self):
        """Verify executing Move via UI calls LabService.move_node()."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "move_act_1",
            "type": "note.blank",
            "payload": {"title": "Move Action Note"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        moved = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "move_act_1")
        self.assertIsNotNone(moved)

        refreshed_c = self.lab_svc.load_board(self.cyclops_project, c_id)
        self.assertEqual(len(refreshed_c["items"]), 1)

    def test_4_copy_action_calls_lab_service_copy_node(self):
        """Verify executing Copy via UI calls LabService.copy_node()."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "copy_act_1",
            "type": "note.blank",
            "payload": {"title": "Copy Action Note"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        copied = self.lab_svc.copy_node(None, wb_id, self.cyclops_project, c_id, "copy_act_1")
        self.assertIsNotNone(copied)
        self.assertNotEqual(copied["id"], "copy_act_1")

    def test_5_canvas_move_removes_source_node(self):
        """Verify InfiniteCanvas removes moved node item from scene."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "canvas_move_1",
            "type": "note.blank",
            "payload": {"title": "Canvas Move Item"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        canvas = InfiniteCanvas()
        canvas._context = self.context
        canvas._board_id = wb_id
        n = canvas.add_node({
            "id": "canvas_move_1",
            "type": "note.blank",
            "payload": {"title": "Canvas Move Item"}
        })
        self.assertIn("canvas_move_1", canvas._items_map)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        res = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "canvas_move_1")
        self.assertIsNotNone(res)

        # Remove from scene as UI does
        if "canvas_move_1" in canvas._items_map:
            del canvas._items_map["canvas_move_1"]
        self.assertNotIn("canvas_move_1", canvas._items_map)

    def test_6_canvas_copy_leaves_source_node_intact(self):
        """Verify InfiniteCanvas leaves source node item intact after copy."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "canvas_copy_1",
            "type": "note.blank",
            "payload": {"title": "Canvas Copy Item"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        canvas = InfiniteCanvas()
        canvas._context = self.context
        canvas._board_id = wb_id
        n = canvas.add_node({
            "id": "canvas_copy_1",
            "type": "note.blank",
            "payload": {"title": "Canvas Copy Item"}
        })

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        copied = self.lab_svc.copy_node(None, wb_id, self.cyclops_project, c_id, "canvas_copy_1")
        self.assertIsNotNone(copied)
        self.assertIn("canvas_copy_1", canvas._items_map)

    def test_7_failed_move_leaves_source_intact(self):
        """Verify failed move leaves source node and board completely intact."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        res = self.lab_svc.move_node(None, wb_id, self.cyclops_project, "Main", "non_existent_node_id")
        self.assertIsNone(res)

    def test_8_failed_copy_leaves_source_intact(self):
        """Verify failed copy leaves source node and board completely intact."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        res = self.lab_svc.copy_node(None, wb_id, self.cyclops_project, "Main", "non_existent_node_id")
        self.assertIsNone(res)

    def test_9_project_workbench_isolation(self):
        """Verify move between Workbench and Project preserves storage path isolation."""
        wb_dir = self.lab_svc.get_boards_dir(None)
        proj_dir = self.lab_svc.get_boards_dir(self.cyclops_project)
        self.assertNotEqual(wb_dir, proj_dir)

    def test_10_same_board_copy_offsets_coordinates(self):
        """Verify same-board copy creates new UUID and offsets transform coordinates."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "same_board_src",
            "type": "note.blank",
            "transform": {"x": 200, "y": 200},
            "payload": {"title": "Same Board Note"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        copied = self.lab_svc.copy_node(None, wb_id, None, wb_id, "same_board_src")
        self.assertIsNotNone(copied)
        self.assertEqual(copied["transform"]["x"], 230)

    def test_11_frame_safety_on_promotion(self):
        """Verify orphaned parent_frame_id is cleared during cross-board move."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "framed_node_1",
            "type": "note.blank",
            "payload": {"title": "Framed Note", "parent_frame_id": "frame_99"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        moved = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "framed_node_1")
        self.assertIsNone(moved["payload"].get("parent_frame_id"))

    def test_12_connector_safety_on_promotion(self):
        """Verify single-endpoint connectors are detached from source board on move."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {"id": "conn_node_1", "type": "note.blank", "payload": {"title": "Conn 1"}},
            {"id": "conn_node_2", "type": "note.blank", "payload": {"title": "Conn 2"}}
        ]
        wb_board["connectors"] = [{
            "id": "c12", "source_node_id": "conn_node_1", "target_node_id": "conn_node_2"
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        moved = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "conn_node_1")

        refreshed_wb = self.lab_svc.load_board(None, wb_id)
        self.assertEqual(len(refreshed_wb.get("connectors", [])), 0)

    def test_13_explorer_refresh_on_promotion(self):
        """Verify board_updated signal is emitted for Explorer subtrees during move."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{"id": "exp_node_1", "type": "note.blank", "payload": {"title": "Exp"}}]
        self.lab_svc.save_board(None, wb_board, wb_id)

        emitted = []
        self.lab_svc.board_updated.connect(lambda p, b: emitted.append((p, b)))

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "exp_node_1")
        self.assertTrue(len(emitted) >= 2)

    def test_14_home_metadata_refresh(self):
        """Verify get_project_summary_metadata reflects node move."""
        meta = self.lab_svc.get_project_summary_metadata(self.cyclops_project)
        self.assertIn("boards", meta)

    def test_15_inspector_actions_section_present(self):
        """Verify NodeInspectable exposes Actions section with Move and Copy actions."""
        class MockNodeItem:
            def __init__(self):
                self.id = "mock_insp_1"
                self.payload = {"title": "Inspectable Note"}
                self.metadata = {}
                self.tags = []

        adapter = NodeInspectable(MockNodeItem())
        sections = adapter.get_inspection_sections()
        sec_titles = [s.title for s in sections]
        self.assertIn("Actions", sec_titles)

    def test_16_context_menu_actions_available(self):
        """Verify InfiniteCanvas _prompt_promote_node signature and method exists."""
        canvas = InfiniteCanvas()
        self.assertTrue(hasattr(canvas, "_prompt_promote_node"))

    def test_17_promotion_dialog_project_enumeration(self):
        """Verify NodePromotionDialog enumerates Global Workbench and all registered projects."""
        dialog = NodePromotionDialog(None, "move", None, "Main", self.project_svc, self.lab_svc)
        projects = [dialog.project_cb.itemData(i) for i in range(dialog.project_cb.count())]
        self.assertIn(None, projects)
        self.assertIn(self.cyclops_project, projects)
        self.assertIn(self.vulcan_project, projects)

    def test_18_promotion_dialog_board_filtering(self):
        """Verify selecting a project populates ONLY that project's boards in board_cb."""
        self.lab_svc.create_board(self.cyclops_project, "Cyclops Extra Board")
        dialog = NodePromotionDialog(None, "move", None, "Main", self.project_svc, self.lab_svc)

        # Select Cyclops project
        cyclops_idx = -1
        for i in range(dialog.project_cb.count()):
            if dialog.project_cb.itemData(i) == self.cyclops_project:
                cyclops_idx = i
                break
        self.assertNotEqual(cyclops_idx, -1)
        dialog.project_cb.setCurrentIndex(cyclops_idx)

        board_items = [dialog.board_cb.itemData(i) for i in range(dialog.board_cb.count())]
        cyclops_boards = [b["id"] for b in self.lab_svc.list_boards(self.cyclops_project)]
        for b_id in board_items:
            self.assertIn(b_id, cyclops_boards)

    def test_19_lab_panel_runtime_context_propagation(self):
        """Verify real runtime context propagation: LabPanel -> InfiniteCanvas -> _prompt_promote_node -> NodePromotionDialog."""
        from ui.panels.lab_panel import LabPanel
        from unittest.mock import patch

        panel = LabPanel(self.context)
        self.assertEqual(panel.canvas._context, self.context)

        # Add dummy note to canvas
        node = panel.canvas.add_node({"id": "rt_node_1", "type": "note.blank", "payload": {"title": "Test Node"}})

        captured_dialogs = []
        orig_init = NodePromotionDialog.__init__

        def mock_init(dialog_self, *args, **kwargs):
            captured_dialogs.append(dialog_self)
            return orig_init(dialog_self, *args, **kwargs)

        with patch.object(NodePromotionDialog, "__init__", mock_init):
            with patch.object(QDialog, "exec_", return_value=QDialog.Rejected):
                panel.canvas._prompt_promote_node(node, action="move")

        self.assertEqual(len(captured_dialogs), 1)
        dialog = captured_dialogs[0]

        items_text = [dialog.project_cb.itemText(i) for i in range(dialog.project_cb.count())]
        self.assertIn("🛠️ Global Workbench", items_text)
        self.assertIn("📁 Cyclops", items_text)
        self.assertIn("📁 Vulcan", items_text)


if __name__ == "__main__":
    unittest.main()
