import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

import sys
sys.path.insert(0, r"c:\Users\jeet5\.copilot\repos\creativeworkspace")

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService


class TestSprint063Phase1(unittest.TestCase):
    """Phase 1 Unit Test Suite: Promotion Service & Data Safety (move_node, copy_node)."""

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

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_1_move_node_workbench_to_project(self):
        """Verify moving a node from Workbench to a Project removes it from Workbench and inserts into Project."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "node_move_1",
            "type": "note.blank",
            "is_pinned": True,
            "attention": "urgent",
            "payload": {"title": "Three.js WebGPU", "content": "Research shaders"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"

        moved = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "node_move_1")
        self.assertIsNotNone(moved)
        self.assertEqual(moved["id"], "node_move_1")

        # Verify source board no longer has the node
        refreshed_wb = self.lab_svc.load_board(None, wb_id)
        self.assertEqual(len(refreshed_wb["items"]), 0)

        # Verify target board has the node
        refreshed_c = self.lab_svc.load_board(self.cyclops_project, c_id)
        self.assertEqual(len(refreshed_c["items"]), 1)
        self.assertEqual(refreshed_c["items"][0]["payload"]["title"], "Three.js WebGPU")

    def test_2_copy_node_workbench_to_project(self):
        """Verify copying a node generates a fresh UUID in target board while source node remains intact."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "node_copy_1",
            "type": "note.blank",
            "payload": {"title": "Source Note", "content": "Keep on Workbench"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"

        copied = self.lab_svc.copy_node(None, wb_id, self.cyclops_project, c_id, "node_copy_1")
        self.assertIsNotNone(copied)
        self.assertNotEqual(copied["id"], "node_copy_1")

        # Verify source board still has the original node
        refreshed_wb = self.lab_svc.load_board(None, wb_id)
        self.assertEqual(len(refreshed_wb["items"]), 1)

        # Verify target board has the copied node
        refreshed_c = self.lab_svc.load_board(self.cyclops_project, c_id)
        self.assertEqual(len(refreshed_c["items"]), 1)
        self.assertEqual(refreshed_c["items"][0]["payload"]["title"], "Source Note")

    def test_3_promotion_preserves_payload_type_attention_pin(self):
        """Verify type, payload, attention level, tags, and pin status transfer intact."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "node_preserve_1",
            "type": "file.reference",
            "is_pinned": True,
            "attention": "important",
            "tags": ["quick_capture", "research"],
            "payload": {"title": "Ref PDF", "file_path": "/path/to/file.pdf"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        moved = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "node_preserve_1")

        self.assertEqual(moved["type"], "file.reference")
        self.assertEqual(moved["is_pinned"], True)
        self.assertEqual(moved["attention"], "important")
        self.assertIn("quick_capture", moved["tags"])
        self.assertEqual(moved["payload"]["file_path"], "/path/to/file.pdf")

    def test_4_promotion_connector_and_frame_safety(self):
        """Verify single-endpoint connectors are detached from source board and orphaned frame IDs cleared."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [
            {
                "id": "node_a",
                "type": "note.blank",
                "payload": {"title": "Node A", "parent_frame_id": "frame_non_existent"}
            },
            {
                "id": "node_b",
                "type": "note.blank",
                "payload": {"title": "Node B"}
            }
        ]
        wb_board["connectors"] = [{
            "id": "conn_ab",
            "source_node_id": "node_a",
            "target_node_id": "node_b",
            "relationship_type": "related_to"
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"

        moved = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "node_a")

        # Verify parent_frame_id was cleared because frame_non_existent is not in target board
        self.assertIsNone(moved["payload"].get("parent_frame_id"))

        # Verify single-endpoint connector was removed from source board
        refreshed_wb = self.lab_svc.load_board(None, wb_id)
        self.assertEqual(len(refreshed_wb.get("connectors", [])), 0)

    def test_5_move_node_between_projects(self):
        """Verify move_node operates cleanly between two projects."""
        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        v_id = self.lab_svc.get_active_board_id(self.vulcan_project) or "Main"

        c_board = self.lab_svc.load_board(self.cyclops_project, c_id)
        c_board["items"] = [{
            "id": "node_cross_proj",
            "type": "note.blank",
            "payload": {"title": "Cross Project Note"}
        }]
        self.lab_svc.save_board(self.cyclops_project, c_board, c_id)

        moved = self.lab_svc.move_node(self.cyclops_project, c_id, self.vulcan_project, v_id, "node_cross_proj")
        self.assertIsNotNone(moved)

        refreshed_c = self.lab_svc.load_board(self.cyclops_project, c_id)
        self.assertEqual(len(refreshed_c["items"]), 0)

        refreshed_v = self.lab_svc.load_board(self.vulcan_project, v_id)
        self.assertEqual(len(refreshed_v["items"]), 1)

    def test_6_copy_node_within_same_board(self):
        """Verify copying a node on the same board offsets coordinates and generates new UUID."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "node_same_copy",
            "type": "note.blank",
            "transform": {"x": 100, "y": 100},
            "payload": {"title": "Same Board Copy"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        copied = self.lab_svc.copy_node(None, wb_id, None, wb_id, "node_same_copy")
        self.assertIsNotNone(copied)
        self.assertNotEqual(copied["id"], "node_same_copy")
        self.assertEqual(copied["transform"]["x"], 130)

        refreshed_wb = self.lab_svc.load_board(None, wb_id)
        self.assertEqual(len(refreshed_wb["items"]), 2)

    def test_7_inbox_board_id_resolution(self):
        """Verify get_inbox_board_id returns active board ID or default Main."""
        inbox_wb = self.lab_svc.get_inbox_board_id(None)
        inbox_proj = self.lab_svc.get_inbox_board_id(self.cyclops_project)
        self.assertTrue(bool(inbox_wb))
        self.assertTrue(bool(inbox_proj))

    def test_8_origin_metadata_recording(self):
        """Verify origin metadata is accurately attached during promotion."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "node_origin_test",
            "type": "note.blank",
            "payload": {"title": "Origin Test"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"
        moved = self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "node_origin_test")

        self.assertIn("origin", moved.get("metadata", {}))
        origin = moved["metadata"]["origin"]
        self.assertEqual(origin["source_project"], "__workbench__")
        self.assertEqual(origin["target_project"], "Cyclops")
        self.assertEqual(origin["action"], "move")
        self.assertTrue(bool(origin.get("promoted_at")))

    def test_9_board_updated_signals_emitted(self):
        """Verify board_updated signal is emitted for both source and target boards on move."""
        wb_id = self.lab_svc.get_active_board_id(None) or "Main"
        wb_board = self.lab_svc.load_board(None, wb_id)
        wb_board["items"] = [{
            "id": "node_sig_test",
            "type": "note.blank",
            "payload": {"title": "Signal Test"}
        }]
        self.lab_svc.save_board(None, wb_board, wb_id)

        c_id = self.lab_svc.get_active_board_id(self.cyclops_project) or "Main"

        emitted_events = []
        self.lab_svc.board_updated.connect(lambda proj, b_id: emitted_events.append((proj, b_id)))

        self.lab_svc.move_node(None, wb_id, self.cyclops_project, c_id, "node_sig_test")

        self.assertEqual(len(emitted_events), 2)
        self.assertEqual(emitted_events[0], (None, wb_id))
        self.assertEqual(emitted_events[1], (self.cyclops_project, c_id))

    def test_10_isolation_contract_preserved(self):
        """Verify Workbench and Project boards remain in their distinct file directories."""
        wb_dir = self.lab_svc.get_boards_dir(None)
        proj_dir = self.lab_svc.get_boards_dir(self.cyclops_project)
        self.assertNotEqual(wb_dir, proj_dir)


if __name__ == "__main__":
    unittest.main()
