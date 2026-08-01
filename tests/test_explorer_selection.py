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


class TestExplorerSelection(unittest.TestCase):

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

        # Create physical subfolders in project location
        self.folder_service.create_folder(self.project, "Assets", "Hero")
        self.folder_service.create_folder(self.project, "Assets/Hero", "Sculpt")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_reveal_project_with_rel_path_selects_subfolder(self):
        """Verify reveal_project with rel_path selects the target subfolder node, not project node."""
        self.explorer.reveal_project(self.project, "assets", rel_path="Assets/Hero", emit=False)

        current = self.explorer.tree.currentItem()
        self.assertIsNotNone(current)
        self.assertEqual(current.data(0, ROLE_REL_PATH), "Assets/Hero")
        self.assertEqual(current.data(0, ROLE_NODE_TYPE), "folder")

    def test_selection_preserved_during_refresh(self):
        """Verify selection on subfolder node is retained after _refresh_expanded_node rebuilds children."""
        self.explorer.reveal_project(self.project, "assets", rel_path="Assets/Hero", emit=False)
        current_before = self.explorer.tree.currentItem()
        self.assertEqual(current_before.data(0, ROLE_REL_PATH), "Assets/Hero")

        # Re-create a folder and trigger assets_changed refresh
        self.folder_service.create_folder(self.project, "Assets/Hero", "Textures")

        current_after = self.explorer.tree.currentItem()
        self.assertIsNotNone(current_after)
        self.assertEqual(current_after.data(0, ROLE_REL_PATH), "Assets/Hero")

    def test_context_menu_uses_stored_item(self):
        """Verify context menu action handlers fallback to stored item if available."""
        subfolder_node = QTreeWidgetItem()
        subfolder_node.setData(0, ROLE_PROJECT, self.project)
        subfolder_node.setData(0, ROLE_SECTION, "assets")
        subfolder_node.setData(0, ROLE_REL_PATH, "Assets/Hero")
        subfolder_node.setData(0, ROLE_NODE_TYPE, "folder")

        self.explorer._context_menu_item = subfolder_node
        active_item = self.explorer._get_active_context_item()
        self.assertEqual(active_item, subfolder_node)


if __name__ == "__main__":
    unittest.main()
