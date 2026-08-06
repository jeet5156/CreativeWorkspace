import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication

from models.project import Project
from services.lab_service import LabService
from ui.panels.lab_panel import LabPanel
from core.app_context import AppContext

app = QApplication.instance() or QApplication([])


class TestLabBoardsFoundation(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.proj_path = Path(self.tmp_dir) / "TestProject"
        self.proj_path.mkdir(parents=True, exist_ok=True)
        self.project = Project(name="TestProject", project_type="general", location=str(self.proj_path))

        self.lab_service = LabService()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_board_manifest_initialization(self):
        """Verify board_manifest.json is created on first access with a default Main board."""
        manifest = self.lab_service.get_manifest(self.project)
        self.assertIsNotNone(manifest)
        self.assertIn("active_board_id", manifest)
        self.assertIn("boards", manifest)

        boards = self.lab_service.list_boards(self.project)
        self.assertEqual(len(boards), 1)
        main_board = boards[0]
        self.assertEqual(main_board["name"], "Main")
        self.assertTrue(main_board["id"].strip())
        self.assertEqual(manifest["active_board_id"], main_board["id"])

        # Verify disk file exists with UUID filename
        board_file = self.proj_path / "Lab" / "boards" / f"{main_board['id']}.lab.json"
        self.assertTrue(board_file.exists())

    def test_create_and_list_boards(self):
        """Verify creating multiple boards registers them in the manifest."""
        b1 = self.lab_service.create_board(self.project, "Gameplay")
        b2 = self.lab_service.create_board(self.project, "Level Design")

        boards = self.lab_service.list_boards(self.project)
        self.assertEqual(len(boards), 3)  # Main, Gameplay, Level Design
        board_names = [b["name"] for b in boards]
        self.assertIn("Gameplay", board_names)
        self.assertIn("Level Design", board_names)

        # Active board should be latest created board (Level Design)
        active_id = self.lab_service.get_active_board_id(self.project)
        self.assertEqual(active_id, b2["id"])

    def test_rename_board(self):
        """Verify renaming updates manifest display name without modifying disk filename/id."""
        b = self.lab_service.create_board(self.project, "Old Name")
        board_id = b["id"]

        success = self.lab_service.rename_board(self.project, board_id, "New Name")
        self.assertTrue(success)

        entry = self.lab_service.get_board_entry(self.project, board_id)
        self.assertEqual(entry["name"], "New Name")
        self.assertEqual(entry["id"], board_id)  # ID remains unchanged

        # File on disk remains <board_id>.lab.json
        board_file = self.proj_path / "Lab" / "boards" / f"{board_id}.lab.json"
        self.assertTrue(board_file.exists())

    def test_duplicate_board(self):
        """Verify board duplication deep-copies items, generates new item IDs, and uses (Copy) suffix."""
        b = self.lab_service.create_board(self.project, "Gameplay")
        board_id = b["id"]

        # Add dummy items to original board
        item_data = {"id": "node_100", "type": "note", "title": "Player Health", "x": 10, "y": 20}
        self.lab_service.save_items(self.project, [item_data], board_id_or_name=board_id)

        # Duplicate
        dup_entry = self.lab_service.duplicate_board(self.project, board_id)
        self.assertIsNotNone(dup_entry)
        self.assertEqual(dup_entry["name"], "Gameplay (Copy)")
        self.assertNotEqual(dup_entry["id"], board_id)

        # Verify duplicated board items have fresh item IDs
        dup_items = self.lab_service.load_items(self.project, dup_entry["id"])
        self.assertEqual(len(dup_items), 1)
        self.assertNotEqual(dup_items[0]["id"], "node_100")
        self.assertEqual(dup_items[0]["title"], "Player Health")

        # Second duplicate should get (Copy 2)
        dup2_entry = self.lab_service.duplicate_board(self.project, board_id)
        self.assertEqual(dup2_entry["name"], "Gameplay (Copy 2)")

    def test_delete_board_protection_and_fallback(self):
        """Verify deleting final board raises ValueError, and deleting active board falls back safely."""
        manifest = self.lab_service.get_manifest(self.project)
        main_id = manifest["active_board_id"]

        # Attempt to delete sole board -> raises ValueError
        with self.assertRaises(ValueError):
            self.lab_service.delete_board(self.project, main_id)

        # Add second board
        b2 = self.lab_service.create_board(self.project, "Second Board")
        b2_id = b2["id"]

        # Active board is now b2_id. Delete active board -> should switch active board back to main_id
        success = self.lab_service.delete_board(self.project, b2_id)
        self.assertTrue(success)

        # Verify b2 file deleted and active board falls back to main_id
        remaining_boards = self.lab_service.list_boards(self.project)
        self.assertEqual(len(remaining_boards), 1)
        self.assertEqual(self.lab_service.get_active_board_id(self.project), main_id)

    def test_active_board_and_viewport_persistence(self):
        """Verify active board selection and viewport persist in manifest across app restart."""
        b = self.lab_service.create_board(self.project, "Persistent Board")
        board_id = b["id"]

        self.lab_service.set_active_board_id(self.project, board_id)
        self.lab_service.save_viewport(self.project, {"zoom": 1.5, "pan_x": 300, "pan_y": -150}, board_id)

        # Re-instantiate service (simulating app restart)
        new_lab_service = LabService()
        self.assertEqual(new_lab_service.get_active_board_id(self.project), board_id)

        manifest = new_lab_service.get_manifest(self.project)
        self.assertEqual(manifest["last_view"]["zoom"], 1.5)
        self.assertEqual(manifest["last_view"]["pan_x"], 300)

    def test_lab_panel_canonical_board_switching(self):
        """Integration test: LabPanel board switching flushes saves, clears canvas, and loads target board."""
        context = AppContext()
        context.lab_service = self.lab_service

        panel = LabPanel(context)
        panel.show_project(self.project)

        main_id = panel._current_board_id
        self.assertIsNotNone(main_id)

        # Create second board
        b2 = self.lab_service.create_board(self.project, "UI Design")
        b2_id = b2["id"]

        # Add note to main board
        panel.canvas.add_node({"id": "note_main", "type": "note", "content": "Main note"})
        panel.flush_pending_saves()

        # Switch to b2
        panel._switch_to_board(b2_id)
        self.assertEqual(panel._current_board_id, b2_id)
        self.assertEqual(len(panel.canvas._items_map), 0)  # b2 is empty

        # Add note to b2
        panel.canvas.add_node({"id": "note_b2", "type": "note", "content": "B2 note"})
        panel.flush_pending_saves()

        # Switch back to Main board
        panel._switch_to_board(main_id)
        self.assertEqual(panel._current_board_id, main_id)
        self.assertEqual(len(panel.canvas._items_map), 1)
        self.assertIn("note_main", panel.canvas._items_map)


if __name__ == "__main__":
    unittest.main()
