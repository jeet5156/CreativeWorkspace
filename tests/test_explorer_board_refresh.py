import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.explorer_panel import ExplorerPanel, ROLE_PROJECT, ROLE_SECTION, ROLE_NODE_TYPE


class TestExplorerBoardRefresh(unittest.TestCase):
    """Focused regression tests for real-time Explorer tree updates across all board lifecycle events."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patch_global_dir = Path(self.temp_dir) / "workbench_boards"
        self.patch_global_dir.mkdir(parents=True, exist_ok=True)

        self.orig_get_boards_dir = LabService.get_boards_dir

        def mock_get_boards_dir(svc, project):
            if not project or not getattr(project, "location", None):
                return self.patch_global_dir
            boards_dir = Path(project.location) / "Lab" / "boards"
            boards_dir.mkdir(parents=True, exist_ok=True)
            return boards_dir

        LabService.get_boards_dir = mock_get_boards_dir

        self.project_svc = ProjectService()

        # Create dummy project
        proj_dir = str(Path(self.temp_dir) / "Cyclops")
        os.makedirs(proj_dir, exist_ok=True)
        self.test_project = Project(
            name="Cyclops",
            project_type="game",
            location=proj_dir,
            created="2026-08-11T12:00:00",
            last_opened="2026-08-11T12:00:00"
        )
        self.project_svc.projects = [self.test_project]

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

        self.explorer = ExplorerPanel()
        self.explorer.set_context(self.context)
        self.explorer.add_project(self.test_project)

        # Expand both nodes
        self.explorer._on_item_expanded(self.explorer.lab_root)

        cyclops_item = self.explorer._project_items[str(self.test_project.location)]
        for i in range(cyclops_item.childCount()):
            c = cyclops_item.child(i)
            if c.data(0, ROLE_SECTION) == "lab":
                self.proj_lab_node = c
                break
        self.explorer._on_item_expanded(self.proj_lab_node)

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _get_node_board_names(self, tree_node):
        return [tree_node.child(i).text(0).replace("🎨 ", "") for i in range(tree_node.childCount())]

    def test_1_create_project_board_refreshes_explorer(self):
        """Verify creating a project board updates Explorer immediately."""
        self.lab_svc.create_board(self.test_project, "Character Concepts")

        proj_boards = self._get_node_board_names(self.proj_lab_node)
        wb_boards = self._get_node_board_names(self.explorer.lab_root)

        self.assertIn("Character Concepts", proj_boards)
        self.assertNotIn("Character Concepts", wb_boards)

    def test_2_create_workbench_board_refreshes_explorer(self):
        """Verify creating a Workbench board updates Explorer immediately."""
        self.lab_svc.create_board(None, "Research Shader Nodes")

        wb_boards = self._get_node_board_names(self.explorer.lab_root)
        proj_boards = self._get_node_board_names(self.proj_lab_node)

        self.assertIn("Research Shader Nodes", wb_boards)
        self.assertNotIn("Research Shader Nodes", proj_boards)

    def test_3_rename_project_board_refreshes_explorer(self):
        """Verify renaming a project board updates Explorer immediately."""
        entry = self.lab_svc.create_board(self.test_project, "Old Name")
        self.lab_svc.rename_board(self.test_project, entry["id"], "New Renamed Name")

        proj_boards = self._get_node_board_names(self.proj_lab_node)
        self.assertIn("New Renamed Name", proj_boards)
        self.assertNotIn("Old Name", proj_boards)

    def test_4_rename_workbench_board_refreshes_explorer(self):
        """Verify renaming a Workbench board updates Explorer immediately."""
        entry = self.lab_svc.create_board(None, "WB Old Name")
        self.lab_svc.rename_board(None, entry["id"], "WB New Renamed Name")

        wb_boards = self._get_node_board_names(self.explorer.lab_root)
        self.assertIn("WB New Renamed Name", wb_boards)
        self.assertNotIn("WB Old Name", wb_boards)

    def test_5_duplicate_project_board_refreshes_explorer(self):
        """Verify duplicating a project board updates Explorer immediately."""
        entry = self.lab_svc.create_board(self.test_project, "Base Board")
        dup_entry = self.lab_svc.duplicate_board(self.test_project, entry["id"])

        proj_boards = self._get_node_board_names(self.proj_lab_node)
        self.assertIn("Base Board", proj_boards)
        self.assertIn(dup_entry["name"], proj_boards)

    def test_6_duplicate_workbench_board_refreshes_explorer(self):
        """Verify duplicating a Workbench board updates Explorer immediately."""
        entry = self.lab_svc.create_board(None, "WB Base Board")
        dup_entry = self.lab_svc.duplicate_board(None, entry["id"])

        wb_boards = self._get_node_board_names(self.explorer.lab_root)
        self.assertIn("WB Base Board", wb_boards)
        self.assertIn(dup_entry["name"], wb_boards)

    def test_7_delete_project_board_refreshes_explorer(self):
        """Verify deleting a project board updates Explorer immediately."""
        entry = self.lab_svc.create_board(self.test_project, "Board to Delete")
        self.assertIn("Board to Delete", self._get_node_board_names(self.proj_lab_node))

        self.lab_svc.delete_board(self.test_project, entry["id"])
        self.assertNotIn("Board to Delete", self._get_node_board_names(self.proj_lab_node))

    def test_8_delete_workbench_board_refreshes_explorer(self):
        """Verify deleting a Workbench board updates Explorer immediately."""
        entry = self.lab_svc.create_board(None, "WB Board to Delete")
        self.assertIn("WB Board to Delete", self._get_node_board_names(self.explorer.lab_root))

        self.lab_svc.delete_board(None, entry["id"])
        self.assertNotIn("WB Board to Delete", self._get_node_board_names(self.explorer.lab_root))

    def test_9_project_workbench_isolation(self):
        """Verify project and Workbench boards never bleed into each other during lifecycle refreshes."""
        wb_entry = self.lab_svc.create_board(None, "Unique WB Board")
        proj_entry = self.lab_svc.create_board(self.test_project, "Unique Proj Board")

        wb_boards = self._get_node_board_names(self.explorer.lab_root)
        proj_boards = self._get_node_board_names(self.proj_lab_node)

        self.assertIn("Unique WB Board", wb_boards)
        self.assertNotIn("Unique WB Board", proj_boards)

        self.assertIn("Unique Proj Board", proj_boards)
        self.assertNotIn("Unique Proj Board", wb_boards)

    def test_10_selection_preserved_on_refresh(self):
        """Verify tree selection is preserved during targeted subtree refresh."""
        entry = self.lab_svc.create_board(self.test_project, "Selected Board")

        # Select item in tree
        target_item = None
        for i in range(self.proj_lab_node.childCount()):
            c = self.proj_lab_node.child(i)
            if c.data(0, Qt.UserRole + 20) == entry["id"]:
                target_item = c
                break

        self.explorer.tree.setCurrentItem(target_item)
        self.assertEqual(self.explorer.tree.currentItem(), target_item)

        # Trigger another board creation which causes refresh
        self.lab_svc.create_board(self.test_project, "Other Board")

        # Check selection was preserved
        current = self.explorer.tree.currentItem()
        self.assertIsNotNone(current)
        self.assertEqual(current.data(0, Qt.UserRole + 20), entry["id"])


if __name__ == "__main__":
    unittest.main()
