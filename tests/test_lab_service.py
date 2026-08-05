import os
import shutil
import tempfile
import unittest
from pathlib import Path

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService


class TestLabService(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_dir = os.path.join(self.test_dir, "TestProject")
        os.makedirs(self.project_dir, exist_ok=True)
        self.project = Project(
            name="TestProject",
            project_type="game",
            location=self.project_dir,
            description="Test Project",
        )
        self.project_service = ProjectService()
        self.lab_service = LabService(self.project_service)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_board_creation(self):
        """Verify that loading a board creates the Lab/boards/Main.lab.json file with valid schema."""
        board_data = self.lab_service.load_board(self.project, board_name="Main")

        expected_file = Path(self.project_dir) / "Lab" / "boards" / "Main.lab.json"
        self.assertTrue(expected_file.exists())

        self.assertEqual(board_data["version"], "1.0")
        self.assertEqual(board_data["name"], "Main")
        self.assertIn("viewport", board_data)
        self.assertEqual(board_data["viewport"]["zoom"], 1.0)
        self.assertEqual(board_data["items"], [])

    def test_save_and_load_viewport(self):
        """Verify updating viewport camera position and zoom persists correctly."""
        self.lab_service.load_board(self.project, board_name="Main")

        new_viewport = {
            "zoom": 1.5,
            "pan_x": 120.5,
            "pan_y": -450.0,
            "grid_visible": False,
            "snap_to_grid": True,
        }
        success = self.lab_service.save_viewport(self.project, new_viewport, board_name="Main")
        self.assertTrue(success)

        reloaded = self.lab_service.load_board(self.project, board_name="Main")
        self.assertEqual(reloaded["viewport"]["zoom"], 1.5)
        self.assertEqual(reloaded["viewport"]["pan_x"], 120.5)
        self.assertEqual(reloaded["viewport"]["pan_y"], -450.0)
        self.assertFalse(reloaded["viewport"]["grid_visible"])
        self.assertTrue(reloaded["viewport"]["snap_to_grid"])

    def test_custom_board_name(self):
        """Verify creating a custom board name under Lab/boards/."""
        data = self.lab_service.load_board(self.project, board_name="Moodboard")
        expected_file = Path(self.project_dir) / "Lab" / "boards" / "Moodboard.lab.json"
        self.assertTrue(expected_file.exists())
        self.assertEqual(data["name"], "Moodboard")


if __name__ == "__main__":
    unittest.main()
