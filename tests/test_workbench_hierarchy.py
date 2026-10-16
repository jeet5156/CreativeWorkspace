import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox
from PySide6.QtCore import Qt

from core.app_context import AppContext
from core.storage import atomic_write_json, safe_read_json
from models.project import Project
from services.lab_service import LabService
from services.project_service import ProjectService
from ui.panels.explorer_panel import ExplorerPanel, ROLE_NODE_TYPE, ROLE_PROJECT, ROLE_SECTION
from ui.panels.lab_panel import LabPanel
from ui.panels.workspace_panel import WorkspacePanel
from ui.workspace_manager import WorkspaceManager

_app = QApplication.instance() or QApplication([])


class TestWorkbenchHierarchy(unittest.TestCase):
    """Test suite for Workbench Two-Level Hierarchy (Collections & Working Boards)."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="cw_hierarchy_test_"))
        self.global_workbench_dir = self.tmp_dir / "workbench"
        self.wb_boards_dir = self.global_workbench_dir / "boards"
        self.wb_boards_dir.mkdir(parents=True, exist_ok=True)
        os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"] = str(self.tmp_dir)

        self.project_svc = ProjectService()
        self.lab_svc = LabService(project_service=self.project_svc, global_storage_dir=self.wb_boards_dir)

        proj_dir = self.tmp_dir / "projects" / "TestProject"
        proj_dir.mkdir(parents=True, exist_ok=True)
        self.project = Project(name="TestProject", project_type="general", location=str(proj_dir))
        self.project_svc.add_project(self.project)

        self.context = AppContext()
        self.context.lab_service = self.lab_svc
        self.context.project_service = self.project_svc

        self.ws_panel = WorkspacePanel()
        self.ws_panel._context = self.context
        self.wm = WorkspaceManager(self.ws_panel, self.context)
        self.context.workspace_manager = self.wm

        self.explorer = ExplorerPanel()
        self.explorer.set_context(self.context)
        self.explorer.add_project(self.project)

    def tearDown(self):
        if "CREATIVE_WORKSPACE_SHARED_DATA_DIR" in os.environ:
            del os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"]
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _find_board_item(self, board_id):
        def _search(item):
            for i in range(item.childCount()):
                child = item.child(i)
                if child.data(0, Qt.UserRole + 20) == board_id:
                    return child
                found = _search(child)
                if found:
                    return found
            return None
        return _search(self.explorer.lab_root)

    def _find_collection_item(self, collection_id):
        for i in range(self.explorer.lab_root.childCount()):
            child = self.explorer.lab_root.child(i)
            if child.data(0, Qt.UserRole + 21) == collection_id and child.data(0, ROLE_NODE_TYPE) == "collection":
                return child
        return None

    def test_1_create_and_rename_main_boards(self):
        """Users can create and rename Level 1 main boards/collections."""
        # Initial state has default "General" collection
        cols = self.lab_svc.list_collections(None)
        self.assertEqual(len(cols), 1)
        self.assertEqual(cols[0]["name"], "General")
        gen_id = cols[0]["id"]

        # Rename "General" to "AI"
        renamed = self.lab_svc.rename_collection(None, gen_id, "AI")
        self.assertTrue(renamed)
        ai_col = self.lab_svc.get_collection(None, gen_id)
        self.assertEqual(ai_col["name"], "AI")
        self.assertEqual(ai_col["id"], gen_id)  # ID remains stable

        # Create new main boards: "3D Art" and "Personal Projects"
        art_entry = self.lab_svc.create_collection(None, "3D Art")
        self.assertIsNotNone(art_entry)
        self.assertEqual(art_entry["name"], "3D Art")

        proj_entry = self.lab_svc.create_collection(None, "Personal Projects")
        self.assertIsNotNone(proj_entry)
        self.assertEqual(proj_entry["name"], "Personal Projects")

        # Verify listing
        all_cols = self.lab_svc.list_collections(None)
        self.assertEqual(len(all_cols), 3)
        col_names = [c["name"] for c in all_cols]
        self.assertEqual(col_names, ["AI", "3D Art", "Personal Projects"])

        # Rename "3D Art" to "Concept & 3D Art"
        self.lab_svc.rename_collection(None, art_entry["id"], "Concept & 3D Art")
        updated_art = self.lab_svc.get_collection(None, art_entry["id"])
        self.assertEqual(updated_art["name"], "Concept & 3D Art")
        self.assertEqual(updated_art["id"], art_entry["id"])

    def test_2_create_multiple_working_boards_in_different_main_boards(self):
        """Users can create multiple working boards inside different main boards, isolated per collection."""
        ai_col = self.lab_svc.list_collections(None)[0]  # Initial collection
        self.lab_svc.rename_collection(None, ai_col["id"], "AI")
        ai_id = ai_col["id"]

        art_col = self.lab_svc.create_collection(None, "3D Art")
        art_id = art_col["id"]

        # Create 3 working boards in AI
        b_ai1 = self.lab_svc.create_board(None, "3D Production Using AI", collection_id=ai_id)
        b_ai2 = self.lab_svc.create_board(None, "Video Production Using AI", collection_id=ai_id)
        b_ai3 = self.lab_svc.create_board(None, "AI Research & Experiments", collection_id=ai_id)

        # Create 2 working boards in 3D Art
        b_art1 = self.lab_svc.create_board(None, "Character Sculpting", collection_id=art_id)
        b_art2 = self.lab_svc.create_board(None, "Environment Modeling", collection_id=art_id)

        # Verify AI collection working boards
        ai_boards = self.lab_svc.list_boards(None, collection_id=ai_id)
        ai_board_names = [b["name"] for b in ai_boards]
        self.assertIn("3D Production Using AI", ai_board_names)
        self.assertIn("Video Production Using AI", ai_board_names)
        self.assertIn("AI Research & Experiments", ai_board_names)
        self.assertNotIn("Character Sculpting", ai_board_names)
        self.assertNotIn("Environment Modeling", ai_board_names)

        # Verify 3D Art collection working boards
        art_boards = self.lab_svc.list_boards(None, collection_id=art_id)
        art_board_names = [b["name"] for b in art_boards]
        self.assertIn("Character Sculpting", art_board_names)
        self.assertIn("Environment Modeling", art_board_names)
        self.assertNotIn("3D Production Using AI", art_board_names)
        self.assertNotIn("AI Research & Experiments", art_board_names)

    def test_3_collection_membership_after_restart(self):
        """Collection hierarchy, ordering, and board associations persist reliably across service restarts."""
        ai_col = self.lab_svc.list_collections(None)[0]
        self.lab_svc.rename_collection(None, ai_col["id"], "AI Collection")
        ai_id = ai_col["id"]

        b_ai = self.lab_svc.create_board(None, "Neural Canvas", collection_id=ai_id)
        ai_board_id = b_ai["id"]

        art_col = self.lab_svc.create_collection(None, "Art Collection")
        art_id = art_col["id"]
        b_art = self.lab_svc.create_board(None, "Shading Canvas", collection_id=art_id)
        art_board_id = b_art["id"]

        # Simulate fresh app startup with brand new service instance reading manifest from disk
        fresh_svc = LabService(project_service=self.project_svc, global_storage_dir=self.wb_boards_dir)
        fresh_cols = fresh_svc.list_collections(None)
        self.assertEqual(len(fresh_cols), 2)
        self.assertEqual(fresh_cols[0]["id"], ai_id)
        self.assertEqual(fresh_cols[0]["name"], "AI Collection")
        self.assertEqual(fresh_cols[1]["id"], art_id)
        self.assertEqual(fresh_cols[1]["name"], "Art Collection")

        ai_fresh_boards = fresh_svc.list_boards(None, collection_id=ai_id)
        ai_fresh_ids = [b["id"] for b in ai_fresh_boards]
        self.assertIn(ai_board_id, ai_fresh_ids)
        self.assertNotIn(art_board_id, ai_fresh_ids)

        art_fresh_boards = fresh_svc.list_boards(None, collection_id=art_id)
        art_fresh_ids = [b["id"] for b in art_fresh_boards]
        self.assertIn(art_board_id, art_fresh_ids)
        self.assertNotIn(ai_board_id, art_fresh_ids)

    def test_4_rename_duplicate_delete_child_boards_isolated(self):
        """Child boards can be renamed, duplicated, and deleted without affecting other collections."""
        col1 = self.lab_svc.list_collections(None)[0]
        col2 = self.lab_svc.create_collection(None, "Collection Two")

        b1 = self.lab_svc.create_board(None, "Board Alpha", collection_id=col1["id"])
        b2 = self.lab_svc.create_board(None, "Board Beta", collection_id=col2["id"])

        # Rename b1
        self.lab_svc.rename_board(None, b1["id"], "Board Alpha Renamed")
        self.assertEqual(self.lab_svc.get_board_entry(None, b1["id"])["name"], "Board Alpha Renamed")
        self.assertEqual(self.lab_svc.get_board_entry(None, b2["id"])["name"], "Board Beta")

        # Duplicate b1
        dup = self.lab_svc.duplicate_board(None, b1["id"])
        self.assertIsNotNone(dup)
        self.assertNotEqual(dup["id"], b1["id"])
        self.assertEqual(dup["collection_id"], col1["id"])
        # Duplicate is contained strictly in col1
        col1_ids = [b["id"] for b in self.lab_svc.list_boards(None, collection_id=col1["id"])]
        col2_ids = [b["id"] for b in self.lab_svc.list_boards(None, collection_id=col2["id"])]
        self.assertIn(dup["id"], col1_ids)
        self.assertNotIn(dup["id"], col2_ids)

        # Delete b1
        deleted = self.lab_svc.delete_board(None, b1["id"])
        self.assertTrue(deleted)
        self.assertIsNone(self.lab_svc.get_board_entry(None, b1["id"]))
        # col2 remains completely untouched
        self.assertIsNotNone(self.lab_svc.get_board_entry(None, b2["id"]))

    def test_5_delete_main_board_with_children_policy_and_fallback(self):
        """Deleting a main board removes it and its children, falling back safely to remaining main board."""
        col1 = self.lab_svc.list_collections(None)[0]
        self.lab_svc.rename_collection(None, col1["id"], "Col One")
        col2 = self.lab_svc.create_collection(None, "Col Two")

        child_board = self.lab_svc.create_board(None, "Child to Delete", collection_id=col2["id"])
        child_id = child_board["id"]
        child_file = self.wb_boards_dir / f"{child_id}.lab.json"
        self.assertTrue(child_file.exists())

        # Set active collection to col2
        self.lab_svc.set_active_collection_id(None, col2["id"])
        self.assertEqual(self.lab_svc.get_active_collection_id(None), col2["id"])

        # Delete col2
        res = self.lab_svc.delete_collection(None, col2["id"])
        self.assertTrue(res)

        # Col2 and its child board are gone
        self.assertIsNone(self.lab_svc.get_collection(None, col2["id"]))
        self.assertIsNone(self.lab_svc.get_board_entry(None, child_id))
        self.assertFalse(child_file.exists())

        # Fallback switched active collection back to col1
        self.assertEqual(self.lab_svc.get_active_collection_id(None), col1["id"])
        self.assertIsNotNone(self.lab_svc.get_active_board_id(None))

        # Attempting to delete the last remaining main board raises ValueError
        with self.assertRaises(ValueError):
            self.lab_svc.delete_collection(None, col1["id"])

    def test_6_preserve_existing_main_and_newboard_compatibility(self):
        """Legacy flat manifest with 'Main' and 'NewBoard' upgrades reversibly without deleting/renaming files."""
        # Construct a synthetic legacy v1.0 manifest
        legacy_main_id = "a17fdcc1-7b77-4911-ac16-6b4bf5fbc8b7"
        legacy_new_id = "f75012d0-d5db-4ebc-bfcd-95dd1667dc2a"
        manifest_path = self.wb_boards_dir / "board_manifest.json"

        # Create legacy Main board file with image item
        main_file_data = {
            "version": "1.0",
            "board_id": legacy_main_id,
            "name": "Main",
            "viewport": {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0},
            "items": [
                {
                    "id": "item-image-1",
                    "type": "image.reference",
                    "payload": {"image_path": "workbench/images/test.png", "filename": "test.png"}
                }
            ],
            "connectors": [],
            "groups": []
        }
        atomic_write_json(self.wb_boards_dir / f"{legacy_main_id}.lab.json", main_file_data)

        new_file_data = {
            "version": "1.0",
            "board_id": legacy_new_id,
            "name": "NewBoard",
            "viewport": {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0},
            "items": [],
            "connectors": [],
            "groups": []
        }
        atomic_write_json(self.wb_boards_dir / f"{legacy_new_id}.lab.json", new_file_data)

        legacy_manifest = {
            "version": "1.0",
            "active_board_id": legacy_main_id,
            "boards": [
                {"id": legacy_main_id, "name": "Main", "filename": f"{legacy_main_id}.lab.json"},
                {"id": legacy_new_id, "name": "NewBoard", "filename": f"{legacy_new_id}.lab.json"},
            ]
        }
        atomic_write_json(manifest_path, legacy_manifest)

        # Load through LabService
        manifest = self.lab_svc.get_manifest(None)

        # Verified: Default collection was synthesized non-destructively
        self.assertTrue(len(manifest["collections"]) >= 1)
        default_col = manifest["collections"][0]
        self.assertEqual(default_col["name"], "General")

        # Verified: Both original board entries preserved their IDs, names, and filenames
        board_ids = [b["id"] for b in manifest["boards"]]
        self.assertIn(legacy_main_id, board_ids)
        self.assertIn(legacy_new_id, board_ids)
        for b in manifest["boards"]:
            self.assertEqual(b["collection_id"], default_col["id"])

        # Verified: On-disk files were NOT renamed or overwritten
        self.assertTrue((self.wb_boards_dir / f"{legacy_main_id}.lab.json").exists())
        self.assertTrue((self.wb_boards_dir / f"{legacy_new_id}.lab.json").exists())
        loaded_main = self.lab_svc.load_board(None, legacy_main_id)
        self.assertEqual(len(loaded_main["items"]), 1)
        self.assertEqual(loaded_main["items"][0]["type"], "image.reference")

    def test_7_project_specific_boards_remain_separate(self):
        """Project Lab boards are stored in project locations and remain separate from Workbench collections."""
        # Create workbench collection & boards
        wb_col = self.lab_svc.create_collection(None, "Workbench AI")
        wb_board = self.lab_svc.create_board(None, "WB Board", collection_id=wb_col["id"])

        # Create project boards
        p_board1 = self.lab_svc.create_board(self.project, "Project Board 1")
        p_board2 = self.lab_svc.create_board(self.project, "Project Board 2")

        # Project boards directory check
        proj_boards_dir = Path(self.project.location) / "Lab" / "boards"
        self.assertTrue((proj_boards_dir / f"{p_board1['id']}.lab.json").exists())
        self.assertTrue((proj_boards_dir / f"{p_board2['id']}.lab.json").exists())

        # Workbench boards list must contain ONLY Workbench boards
        wb_all_ids = [b["id"] for b in self.lab_svc.list_boards(None)]
        self.assertIn(wb_board["id"], wb_all_ids)
        self.assertNotIn(p_board1["id"], wb_all_ids)
        self.assertNotIn(p_board2["id"], wb_all_ids)

        # Project boards list must contain ONLY Project boards
        p_all_ids = [b["id"] for b in self.lab_svc.list_boards(self.project)]
        self.assertIn(p_board1["id"], p_all_ids)
        self.assertIn(p_board2["id"], p_all_ids)
        self.assertNotIn(wb_board["id"], p_all_ids)

    def test_8_canvas_quiet_viewport_and_performance(self):
        """Saving viewport on board does not emit manifest_updated or cause reload storms."""
        emitted_signals = []
        self.lab_svc.manifest_updated.connect(lambda p: emitted_signals.append(("manifest_updated", p)))
        self.lab_svc.board_updated.connect(lambda p, b: emitted_signals.append(("board_updated", b)))

        viewport = {"zoom": 1.25, "pan_x": 100.0, "pan_y": -50.0}
        self.lab_svc.save_viewport(None, viewport)

        # Zero disruptive reload signals emitted during camera movements
        self.assertEqual(len(emitted_signals), 0)

        # Viewport persisted
        manifest = self.lab_svc.get_manifest(None)
        self.assertEqual(manifest["last_view"]["zoom"], 1.25)
        self.assertEqual(manifest["last_view"]["pan_x"], 100.0)

    def test_9_explorer_tree_and_lab_panel_ui_hierarchy(self):
        """Explorer tree displays 2-level hierarchy, and LabPanel collection combo switches boards correctly."""
        # Setup two collections
        col1 = self.lab_svc.list_collections(None)[0]
        self.lab_svc.rename_collection(None, col1["id"], "AI Tools")
        b_ai = self.lab_svc.create_board(None, "Diffusion Board", collection_id=col1["id"])

        col2 = self.lab_svc.create_collection(None, "Art Production")
        b_art = self.lab_svc.create_board(None, "Texture Board", collection_id=col2["id"])

        # Refresh explorer tree
        self.explorer.refresh_lab_node(None)

        # Verify Explorer tree structure
        wb_root = self.explorer.lab_root
        self.assertEqual(wb_root.childCount(), 2)
        col1_item = wb_root.child(0)
        col2_item = wb_root.child(1)
        self.assertEqual(col1_item.data(0, ROLE_NODE_TYPE), "collection")
        self.assertEqual(col2_item.data(0, ROLE_NODE_TYPE), "collection")
        self.assertIn("AI Tools", col1_item.text(0))
        self.assertIn("Art Production", col2_item.text(0))

        # Check child board under col1
        col1_board_names = [col1_item.child(i).text(0) for i in range(col1_item.childCount())]
        self.assertTrue(any("Diffusion Board" in name for name in col1_board_names))

        # Check LabPanel UI integration
        lp = LabPanel(self.context)
        lp.show_project(None, collection_id=col1["id"], board_id=b_ai["id"])
        self.assertEqual(lp._current_collection_id, col1["id"])
        self.assertEqual(lp._current_board_id, b_ai["id"])
        self.assertIn("AI Tools", lp.board_label.text())
        self.assertIn("Diffusion Board", lp.board_label.text())

        # Switch collection in LabPanel
        lp.show_project(None, collection_id=col2["id"], board_id=b_art["id"])
        self.assertEqual(lp._current_collection_id, col2["id"])
        self.assertEqual(lp._current_board_id, b_art["id"])
        self.assertIn("Art Production", lp.board_label.text())
        self.assertIn("Texture Board", lp.board_label.text())


if __name__ == "__main__":
    unittest.main()
