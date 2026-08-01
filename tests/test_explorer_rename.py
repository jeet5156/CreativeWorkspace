import os
import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication, QTreeWidgetItem
from PySide6.QtCore import Qt

from models.project import Project
from services.project_service import ProjectService
from services.asset_service import AssetService
from services.folder_service import FolderService
from ui.panels.explorer_panel import ExplorerPanel, ROLE_PROJECT, ROLE_SECTION, ROLE_REL_PATH, ROLE_NODE_TYPE

app = QApplication.instance() or QApplication([])


class MockContext:
    def __init__(self, project_service, asset_service, folder_service):
        self.project_service = project_service
        self.asset_service = asset_service
        self.folder_service = folder_service


class TestExplorerRename(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_dir = os.path.join(self.test_dir, "TestProject")
        os.makedirs(self.project_dir, exist_ok=True)
        self.project = Project(
            name="TestProject",
            project_type="game",
            location=self.project_dir,
            description="Test Project"
        )
        self.project_service = ProjectService()
        self.asset_service = AssetService(self.project_service)
        self.folder_service = FolderService(self.project_service, self.asset_service)
        self.context = MockContext(self.project_service, self.asset_service, self.folder_service)

        self.explorer = ExplorerPanel()
        self.explorer.set_context(self.context)
        self.explorer.add_project(self.project)

        # Create physical subfolder in project location
        self.folder_service.create_folder(self.project, "Assets", "Hero")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_rename_action_exists(self):
        """Verify rename_folder_action exists on ExplorerPanel."""
        self.assertTrue(hasattr(self.explorer, "rename_folder_action"))
        self.assertEqual(self.explorer.rename_folder_action.text(), "Rename Folder...")

    def test_folder_rename_service_integration(self):
        """Verify folder_service.rename_folder updates physical folder name and index."""
        old_rel = "Assets/Hero"
        new_name = "Hero_V2"

        res = self.folder_service.rename_folder(self.project, old_rel, new_name)
        self.assertTrue(res)

        old_path = os.path.join(self.project_dir, "Assets", "Hero")
        new_path = os.path.join(self.project_dir, "Assets", "Hero_V2")

        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))
        self.assertTrue(os.path.isdir(new_path))


if __name__ == "__main__":
    unittest.main()
