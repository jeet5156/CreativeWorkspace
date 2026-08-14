import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

app = QApplication.instance() or QApplication(sys.argv)

from models.project import Project
from services.project_service import ProjectService
from services.activity_service import ActivityService
from services.lab_service import LabService
from core.app_context import AppContext
from ui.dialogs.node_promotion_dialog import NodePromotionDialog
from ui.panels.inspector_panel import InspectorPanel
from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable


class TestPromotionRegressionPhase5(unittest.TestCase):
    """Comprehensive regression test suite for Move/Copy Node promotion workflows."""

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

        self.context = AppContext()
        self.project_svc = ProjectService()
        self.context.project_service = self.project_svc

        # Create two test projects
        p1_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(p1_dir, exist_ok=True)
        self.cyclops_project = Project(name="Cyclops", project_type="game", location=p1_dir)
        self.project_svc.add_project(self.cyclops_project)

        p2_dir = str(Path(self.temp_dir) / "Vulcan")
        os.makedirs(p2_dir, exist_ok=True)
        self.vulcan_project = Project(name="Vulcan", project_type="audio", location=p2_dir)
        self.project_svc.add_project(self.vulcan_project)

        self.activity_svc = ActivityService()
        self.activity_svc.config_folder = Path(self.temp_dir) / "config"
        self.activity_svc.config_folder.mkdir(exist_ok=True)
        self.activity_svc._file = self.activity_svc.config_folder / "activity.json"
        self.context.activity_service = self.activity_svc

        self.lab_svc = LabService(project_service=self.project_svc, activity_service=self.activity_svc)
        self.context.lab_service = self.lab_svc

        self.wb_board_id = self.lab_svc.get_active_board_id(None) or "Main"
        self.c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        self.v_board_id = self.lab_svc.get_active_board_id(self.vulcan_project) or "Main"

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_single_node_move_workbench_to_project(self):
        """Verify single node move from Workbench to Project using canonical UUID resolution."""
        wb_note = self.lab_svc.add_quick_capture_note("WB Move Note", project=None, board_id=self.wb_board_id)

        # Move using 'Main' as source alias and UUID as target board ID
        res = self.lab_svc.move_nodes(None, "Main", self.cyclops_project, self.c_board_id, [wb_note["id"]])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], wb_note["id"])

        # Check source items removed
        wb_items = self.lab_svc.load_items(None, self.wb_board_id)
        self.assertNotIn(wb_note["id"], {it["id"] for it in wb_items})

        # Check target items present
        c_items = self.lab_svc.load_items(self.cyclops_project, self.c_board_id)
        self.assertIn(wb_note["id"], {it["id"] for it in c_items})

    def test_2_single_node_copy_project_to_project(self):
        """Verify single node copy from Cyclops project to Vulcan project."""
        c_note = self.lab_svc.add_quick_capture_note("Cyclops Copy Note", project=self.cyclops_project, board_id=self.c_board_id)

        res = self.lab_svc.copy_nodes(self.cyclops_project, self.c_board_id, self.vulcan_project, self.v_board_id, [c_note["id"]])
        self.assertEqual(len(res), 1)
        copied_id = res[0]["id"]
        self.assertNotEqual(copied_id, c_note["id"])

        # Source note remains in Cyclops
        c_items = self.lab_svc.load_items(self.cyclops_project, self.c_board_id)
        self.assertIn(c_note["id"], {it["id"] for it in c_items})

        # Copied note exists in Vulcan
        v_items = self.lab_svc.load_items(self.vulcan_project, self.v_board_id)
        self.assertIn(copied_id, {it["id"] for it in v_items})

    def test_3_single_node_move_project_to_workbench(self):
        """Verify single node move from Project to Workbench."""
        c_note = self.lab_svc.add_quick_capture_note("Proj to WB Note", project=self.cyclops_project, board_id=self.c_board_id)

        res = self.lab_svc.move_nodes(self.cyclops_project, self.c_board_id, None, self.wb_board_id, [c_note["id"]])
        self.assertEqual(len(res), 1)

        wb_items = self.lab_svc.load_items(None, self.wb_board_id)
        self.assertIn(c_note["id"], {it["id"] for it in wb_items})

    def test_4_multi_node_and_frame_children_move(self):
        """Verify moving a Frame with nested child nodes moves frame and children together."""
        frame_node = {
            "id": "frame_1",
            "type": "frame",
            "transform": {"x": 0, "y": 0, "width": 400, "height": 300},
            "payload": {"title": "Test Frame", "child_node_ids": ["child_1", "child_2"]}
        }
        child1 = {
            "id": "child_1",
            "type": "note.blank",
            "transform": {"x": 20, "y": 20, "width": 100, "height": 100},
            "payload": {"title": "Child 1", "parent_frame_id": "frame_1"}
        }
        child2 = {
            "id": "child_2",
            "type": "note.blank",
            "transform": {"x": 150, "y": 20, "width": 100, "height": 100},
            "payload": {"title": "Child 2", "parent_frame_id": "frame_1"}
        }

        self.lab_svc.save_items(None, [frame_node, child1, child2], board_id_or_name=self.wb_board_id)

        # Move frame_1 to Cyclops
        res = self.lab_svc.move_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["frame_1"])
        self.assertEqual(len(res), 3)

        c_items = self.lab_svc.load_items(self.cyclops_project, self.c_board_id)
        c_ids = {it["id"] for it in c_items}
        self.assertTrue({"frame_1", "child_1", "child_2"}.issubset(c_ids))

    def test_5_same_board_move_no_op_protection(self):
        """Verify moving a node to its current board is a safe no-op that preserves items."""
        wb_note = self.lab_svc.add_quick_capture_note("Same Board Note", project=None, board_id=self.wb_board_id)

        # Move to same board using 'Main' as source alias and UUID as target
        res = self.lab_svc.move_nodes(None, "Main", None, self.wb_board_id, [wb_note["id"]])
        self.assertEqual(len(res), 1)

        wb_items = self.lab_svc.load_items(None, self.wb_board_id)
        self.assertIn(wb_note["id"], {it["id"] for it in wb_items})

    def test_6_dialog_board_dropdown_canonical_filtering(self):
        """Verify NodePromotionDialog filters out current source board even if source_board_id is passed as 'Main'."""
        dialog = NodePromotionDialog(None, "move", None, "Main", self.project_svc, self.lab_svc)

        # Workbench selected by default (index 0)
        dialog.project_cb.setCurrentIndex(0)
        board_ids_in_combo = [dialog.board_cb.itemData(i) for i in range(dialog.board_cb.count())]

        # Source board UUID must NOT be in target board choices for same-workbench Move
        self.assertNotIn(self.wb_board_id, board_ids_in_combo)

    def test_7_inspector_panel_runtime_promotion_action(self):
        """Verify runtime promotion action triggered via InspectorPanel."""
        c_note = self.lab_svc.add_quick_capture_note("Inspector Move Note", project=self.cyclops_project, board_id=self.c_board_id)

        insp_panel = InspectorPanel()
        insp_panel.set_context(self.context)

        node_inspectable = NodeInspectable(None)

        class MockNodeItem:
            def __init__(self, nid, p_obj, b_id):
                self.id = nid
                self.project = p_obj
                self._board_id = b_id
                self.payload = {"title": "Inspector Move Note"}
                self.metadata = {}

        mock_item = MockNodeItem(c_note["id"], self.cyclops_project, self.c_board_id)
        node_inspectable.node_item = mock_item

        class MockField:
            def __init__(self, key):
                self.key = key

        from PySide6.QtWidgets import QMessageBox
        with patch.object(NodePromotionDialog, "exec_", return_value=QDialog.Accepted):
            with patch.object(NodePromotionDialog, "get_selected_destination", return_value=(self.vulcan_project, self.v_board_id)):
                with patch.object(QMessageBox, "information"):
                    with patch.object(QMessageBox, "critical"):
                        insp_panel._on_action_triggered(node_inspectable, MockField("action_move_project"))

        # Verify item moved to Vulcan
        v_items = self.lab_svc.load_items(self.vulcan_project, self.v_board_id)
        self.assertIn(c_note["id"], {it["id"] for it in v_items})

    def test_8_activity_service_failure_does_not_abort_move(self):
        """Verify move_nodes completes successfully even if ActivityService throws an exception."""
        wb_note = self.lab_svc.add_quick_capture_note("Fault Tolerance Note", project=None, board_id=self.wb_board_id)

        # Mock activity_service.record to raise Exception
        with patch.object(self.activity_svc, "record", side_effect=RuntimeError("Telemetry store unavailable")):
            res = self.lab_svc.move_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, [wb_note["id"]])

        # Move operation must still succeed!
        self.assertEqual(len(res), 1)
        c_items = self.lab_svc.load_items(self.cyclops_project, self.c_board_id)
        self.assertIn(wb_note["id"], {it["id"] for it in c_items})


    def test_9_canvas_promotion_dialog_triggering(self):
        """Verify canvas context-menu promotion invocation path via InfiniteCanvas._prompt_promote_nodes."""
        canvas = InfiniteCanvas()
        canvas._context = self.context
        canvas.project = self.cyclops_project
        canvas._board_id = self.c_board_id

        node_item = canvas.add_node({
            "id": "canvas_promote_node_1",
            "type": "note.blank",
            "transform": {"x": 10, "y": 10, "width": 200, "height": 100},
            "payload": {"title": "Canvas Context Note"}
        })

        self.lab_svc.save_items(self.cyclops_project, [{
            "id": "canvas_promote_node_1",
            "type": "note.blank",
            "transform": {"x": 10, "y": 10, "width": 200, "height": 100},
            "payload": {"title": "Canvas Context Note"}
        }], board_id_or_name=self.c_board_id)

        from PySide6.QtWidgets import QMessageBox
        with patch.object(NodePromotionDialog, "exec_", return_value=QDialog.Accepted):
            with patch.object(NodePromotionDialog, "get_selected_destination", return_value=(self.vulcan_project, self.v_board_id)):
                with patch.object(QMessageBox, "information"):
                    with patch.object(QMessageBox, "critical"):
                        canvas._prompt_promote_nodes(item=node_item, action="move")

        # Verify node removed from source canvas and present in target Vulcan board
        self.assertNotIn("canvas_promote_node_1", canvas._items_map)
        v_items = self.lab_svc.load_items(self.vulcan_project, self.v_board_id)
        self.assertIn("canvas_promote_node_1", {it["id"] for it in v_items})


if __name__ == "__main__":
    unittest.main()
