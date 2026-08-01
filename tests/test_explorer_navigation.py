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

# Ensure QApplication exists for Qt widget tests
app = QApplication.instance() or QApplication([])


class MockContext:
    def __init__(self, project_service, asset_service, folder_service):
        self.project_service = project_service
        self.asset_service = asset_service
        self.folder_service = folder_service


class TestExplorerNavigation(unittest.TestCase):

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

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_on_item_clicked_emits_rel_path(self):
        """Verify on_item_clicked extracts ROLE_REL_PATH and emits (project, section, rel_path)."""
        received = []
        self.explorer.project_selected.connect(lambda p, s, r: received.append((p, s, r)))

        # Create a mock tree node for a subfolder
        item = QTreeWidgetItem()
        item.setData(0, ROLE_PROJECT, self.project)
        item.setData(0, ROLE_SECTION, "assets")
        item.setData(0, ROLE_REL_PATH, "Assets/Hero")
        item.setData(0, ROLE_NODE_TYPE, "folder")

        self.explorer.on_item_clicked(item, 0)

        self.assertEqual(len(received), 1)
        proj, section, rel_path = received[0]
        self.assertEqual(proj, self.project)
        self.assertEqual(section, "assets")
        self.assertEqual(rel_path, "Assets/Hero")

    def test_nested_folder_creation(self):
        """Verify FolderService creates a nested folder under parent_rel (Assets/Hero -> Assets/Hero/Sculpt)."""
        res = self.folder_service.create_folder(self.project, "Assets/Hero", "Sculpt")
        self.assertTrue(res)

        created_path = os.path.join(self.project_dir, "Assets", "Hero", "Sculpt")
        self.assertTrue(os.path.exists(created_path))
        self.assertTrue(os.path.isdir(created_path))

    def test_list_subfolders_nested(self):
        """Verify FolderService.list_subfolders lists nested folders accurately."""
        self.folder_service.create_folder(self.project, "Assets/Hero", "Sculpt")
        self.folder_service.create_folder(self.project, "Assets/Hero", "Textures")

        subfolders = self.folder_service.list_subfolders(self.project, "Assets/Hero")
        self.assertEqual(subfolders, ["Sculpt", "Textures"])


if __name__ == "__main__":
    unittest.main()
