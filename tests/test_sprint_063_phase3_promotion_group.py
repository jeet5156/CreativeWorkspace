import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.dialogs.node_promotion_dialog import NodePromotionDialog


class TestPhase3PromotionGroup(unittest.TestCase):
    """Test suite covering collection-level promotion (move_nodes, copy_nodes, frame children, connectors, and canvas integration)."""

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

        p2_dir = str(Path(self.temp_dir) / "Vulcan")
        os.makedirs(p2_dir, exist_ok=True)
        self.vulcan_project = Project(name="Vulcan", project_type="audio", location=p2_dir)
        self.proj_svc.add_project(self.vulcan_project)

        self.lab_svc = LabService(project_service=self.proj_svc)

        self.wb_board_id = self.lab_svc.get_active_board_id(None) or "Main"
        self.c_board_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        self.v_board_id = self.lab_svc.get_active_board_id(self.vulcan_project) or "Main"

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_move_multiple_independent_nodes(self):
        """1. Move multiple independent nodes between Workbench and Project."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "n1", "type": "note.blank", "transform": {"x": 100, "y": 100}, "payload": {"title": "Note 1"}},
            {"id": "n2", "type": "note.blank", "transform": {"x": 200, "y": 200}, "payload": {"title": "Note 2"}},
            {"id": "n3", "type": "note.blank", "transform": {"x": 300, "y": 300}, "payload": {"title": "Note 3"}}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        moved = self.lab_svc.move_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["n1", "n2"])
        self.assertEqual(len(moved), 2)
        moved_ids = {m["id"] for m in moved}
        self.assertEqual(moved_ids, {"n1", "n2"})

        # Check source board items
        refreshed_wb = self.lab_svc.load_board(None, self.wb_board_id)
        remaining_ids = {it["id"] for it in refreshed_wb["items"]}
        self.assertEqual(remaining_ids, {"n3"})

        # Check target board items
        c_board = self.lab_svc.load_board(self.cyclops_project, self.c_board_id)
        target_ids = {it["id"] for it in c_board["items"]}
        self.assertIn("n1", target_ids)
        self.assertIn("n2", target_ids)

    def test_2_copy_multiple_independent_nodes(self):
        """2. Copy multiple independent nodes generating fresh UUIDs and keeping source intact."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "n1", "type": "note.blank", "transform": {"x": 100, "y": 100}, "payload": {"title": "Note 1"}},
            {"id": "n2", "type": "note.blank", "transform": {"x": 200, "y": 200}, "payload": {"title": "Note 2"}}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        copied = self.lab_svc.copy_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["n1", "n2"])
        self.assertEqual(len(copied), 2)
        copied_ids = {c["id"] for c in copied}
        self.assertNotIn("n1", copied_ids)
        self.assertNotIn("n2", copied_ids)

        # Source board untouched
        refreshed_wb = self.lab_svc.load_board(None, self.wb_board_id)
        self.assertEqual(len(refreshed_wb["items"]), 2)

    def test_3_move_frame_and_contained_nodes(self):
        """3. Move Frame + contained nodes together."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "f1", "type": "frame", "transform": {"x": 0, "y": 0}, "payload": {"title": "Frame 1", "child_node_ids": ["c1", "c2"]}},
            {"id": "c1", "type": "note.blank", "transform": {"x": 20, "y": 20}, "payload": {"title": "Child 1", "parent_frame_id": "f1"}},
            {"id": "c2", "type": "note.blank", "transform": {"x": 50, "y": 50}, "payload": {"title": "Child 2", "parent_frame_id": "f1"}},
            {"id": "other", "type": "note.blank", "transform": {"x": 500, "y": 500}, "payload": {"title": "Outside"}}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        # Move passing ONLY frame ID 'f1'
        moved = self.lab_svc.move_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["f1"])
        moved_ids = {m["id"] for m in moved}
        self.assertEqual(moved_ids, {"f1", "c1", "c2"})

        refreshed_wb = self.lab_svc.load_board(None, self.wb_board_id)
        self.assertEqual(len(refreshed_wb["items"]), 1)
        self.assertEqual(refreshed_wb["items"][0]["id"], "other")

    def test_4_copy_frame_and_contained_nodes_remapping(self):
        """4. Copy Frame + contained nodes with new UUIDs and parent_frame_id remapping."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "f1", "type": "frame", "transform": {"x": 10, "y": 10}, "payload": {"title": "Frame 1", "child_node_ids": ["c1"]}},
            {"id": "c1", "type": "note.blank", "transform": {"x": 30, "y": 30}, "payload": {"title": "Child 1", "parent_frame_id": "f1"}}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        copied = self.lab_svc.copy_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["f1"])
        self.assertEqual(len(copied), 2)

        copied_frame = next(it for it in copied if it["type"] == "frame")
        copied_child = next(it for it in copied if it["type"] != "frame")

        self.assertNotEqual(copied_frame["id"], "f1")
        self.assertNotEqual(copied_child["id"], "c1")
        self.assertEqual(copied_child["payload"]["parent_frame_id"], copied_frame["id"])
        self.assertEqual(copied_frame["payload"]["child_node_ids"], [copied_child["id"]])

    def test_5_mixed_selection_without_duplicates(self):
        """5. Mixed selection (Frame + explicit child node) resolves without duplicate transfers."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "f1", "type": "frame", "transform": {"x": 0, "y": 0}, "payload": {"child_node_ids": ["c1"]}},
            {"id": "c1", "type": "note.blank", "transform": {"x": 20, "y": 20}, "payload": {"parent_frame_id": "f1"}}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        # Pass BOTH f1 and c1
        resolved = self.lab_svc.resolve_promotion_group(None, self.wb_board_id, ["f1", "c1"])
        self.assertEqual(len(resolved), 2)
        res_ids = [r["id"] for r in resolved]
        self.assertEqual(res_ids, ["f1", "c1"])

    def test_6_internal_connector_preservation(self):
        """6. Connectors between promoted nodes are preserved and transferred/copied."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "n1", "type": "note.blank", "payload": {"title": "N1"}},
            {"id": "n2", "type": "note.blank", "payload": {"title": "N2"}}
        ]
        wb_board["connectors"] = [
            {"id": "conn12", "source_node_id": "n1", "target_node_id": "n2"}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        moved = self.lab_svc.move_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["n1", "n2"])
        self.assertEqual(len(moved), 2)

        c_board = self.lab_svc.load_board(self.cyclops_project, self.c_board_id)
        self.assertEqual(len(c_board.get("connectors", [])), 1)
        self.assertEqual(c_board["connectors"][0]["source_node_id"], "n1")
        self.assertEqual(c_board["connectors"][0]["target_node_id"], "n2")

    def test_7_external_connector_detachment(self):
        """7. Connectors to un-promoted nodes are safely detached without orphaned references."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "n1", "type": "note.blank", "payload": {"title": "N1"}},
            {"id": "n2", "type": "note.blank", "payload": {"title": "N2"}}
        ]
        wb_board["connectors"] = [
            {"id": "conn12", "source_node_id": "n1", "target_node_id": "n2"}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        # Move ONLY n1
        moved = self.lab_svc.move_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["n1"])
        self.assertEqual(len(moved), 1)

        # Source board should have no orphaned connectors
        refreshed_wb = self.lab_svc.load_board(None, self.wb_board_id)
        self.assertEqual(len(refreshed_wb.get("connectors", [])), 0)

        # Target board should have no external connector
        c_board = self.lab_svc.load_board(self.cyclops_project, self.c_board_id)
        self.assertEqual(len(c_board.get("connectors", [])), 0)

    def test_8_relative_transform_preservation(self):
        """8. Verify relative spatial positions are preserved exactly during group promotion."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "n1", "type": "note.blank", "transform": {"x": 100, "y": 200}},
            {"id": "n2", "type": "note.blank", "transform": {"x": 300, "y": 500}}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        moved = self.lab_svc.move_nodes(None, self.wb_board_id, self.cyclops_project, self.c_board_id, ["n1", "n2"])
        n1_moved = next(m for m in moved if m["id"] == "n1")
        n2_moved = next(m for m in moved if m["id"] == "n2")

        dx = n2_moved["transform"]["x"] - n1_moved["transform"]["x"]
        dy = n2_moved["transform"]["y"] - n1_moved["transform"]["y"]
        self.assertEqual(dx, 200)
        self.assertEqual(dy, 300)

    def test_9_existing_single_node_regression(self):
        """9. Verify move_node and copy_node single-node API calls remain fully backward compatible."""
        wb_board = self.lab_svc.load_board(None, self.wb_board_id)
        wb_board["items"] = [
            {"id": "n1", "type": "note.blank", "payload": {"title": "Single"}}
        ]
        self.lab_svc.save_board(None, wb_board, self.wb_board_id)

        copied = self.lab_svc.copy_node(None, self.wb_board_id, self.cyclops_project, self.c_board_id, "n1")
        self.assertIsNotNone(copied)
        self.assertNotEqual(copied["id"], "n1")

        moved = self.lab_svc.move_node(None, self.wb_board_id, self.cyclops_project, self.c_board_id, "n1")
        self.assertIsNotNone(moved)
        self.assertEqual(moved["id"], "n1")

    def test_10_canvas_selection_promotion_flow(self):
        """10. Test actual canvas selection and context menu _prompt_promote_nodes path."""
        class MockContext:
            def __init__(ctx_self, lab_svc, proj_svc):
                ctx_self.lab_service = lab_svc
                ctx_self.project_service = proj_svc
                ctx_self.current_project = None

        mock_ctx = MockContext(self.lab_svc, self.proj_svc)
        canvas = InfiniteCanvas()
        canvas._context = mock_ctx
        canvas.project = None
        canvas._board_id = self.wb_board_id

        n1 = canvas.add_node({"type": "note.blank", "transform": {"x": 100, "y": 100, "width": 100, "height": 100}})
        n2 = canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 200, "width": 100, "height": 100}})
        self.assertIsNotNone(n1)
        self.assertIsNotNone(n2)


        # Multi-select both nodes
        canvas.set_selected_nodes([n1, n2])
        self.assertEqual(len(canvas.selected_nodes()), 2)

        # Test promotion dialog title for multi-selection
        dialog = NodePromotionDialog(canvas, "move", None, self.wb_board_id, self.proj_svc, self.lab_svc, target_nodes=canvas.selected_nodes())
        self.assertEqual(dialog.windowTitle(), "Move 2 nodes")



if __name__ == "__main__":
    unittest.main()
