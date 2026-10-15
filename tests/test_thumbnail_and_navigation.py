import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication, QTreeWidgetItem
from PySide6.QtGui import QImage

from models.project import Project
from services.project_service import ProjectService
from services.thumbnail_service import ThumbnailService
from services.asset_service import AssetService
from services.navigation_service import NavigationService
from ui.panels.explorer_panel import ExplorerPanel
from ui.panels.workspace_panel import WorkspacePanel
from ui.workspace_manager import WorkspaceManager

app = QApplication.instance() or QApplication([])


class TestThumbnailAndNavigation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_service = ProjectService()
        self.asset_service = AssetService(self.project_service)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complete_navigation_chain_to_lab(self):
        """Verify navigation chain from tree itemClicked to QStackedWidget setCurrentWidget."""
        workspace = WorkspacePanel()
        explorer = ExplorerPanel()

        context = type('Context', (), {
            'project_service': self.project_service,
            'asset_service': self.asset_service,
            'app_state': None,
            'current_project': None,
            'workspace_manager': None,
        })()

        navigation = NavigationService(None, explorer, context)
        manager = WorkspaceManager(workspace, context, navigation_service=navigation)
        navigation.workspace_manager = manager
        context.workspace_manager = manager

        workspace.set_context(context)
        explorer.set_search_services(manager.find_service, navigation, None)

        # Wire navigation requested
        explorer.navigation_requested.connect(navigation.handle_navigation)

        # Simulate clicking top-level Lab item
        lab_item = explorer.lab_root
        explorer._on_tree_item_clicked(lab_item, 0)

        # Verify stacked widget switched to Lab panel
        self.assertEqual(workspace.stack.currentWidget(), manager.lab_panel)

    def test_thumbnail_service_threadpool_and_failed_caching(self):
        """Verify ThumbnailService max thread count is 2 and failed thumbnails are cached."""
        thumb_svc = ThumbnailService()
        self.assertEqual(thumb_svc.pool.maxThreadCount(), 2)

        proj_loc = self.temp_dir
        rel_path = "Assets/corrupt.xyz"

        # Mark thumbnail as failed
        thumb_svc._mark_failed(proj_loc, rel_path)

        cached = thumb_svc.get_cached(proj_loc, rel_path, str(Path(proj_loc) / rel_path))
        self.assertEqual(cached, "FAILED")

    def test_top_level_project_collapse(self):
        """Verify expanding a top-level project collapses only other top-level projects."""
        explorer = ExplorerPanel()
        p1 = self.project_service.create_project("Project Alpha", "game", self.temp_dir + "/p1", "A")
        p2 = self.project_service.create_project("Project Beta", "portfolio", self.temp_dir + "/p2", "B")

        explorer.add_project(p1)
        explorer.add_project(p2)

        item1 = explorer._project_items[str(p1.location)]
        item2 = explorer._project_items[str(p2.location)]

        item1.setExpanded(True)
        explorer._on_item_expanded(item1)
        self.assertTrue(item1.isExpanded())

        # Expand item2 -> item1 should automatically collapse
        item2.setExpanded(True)
        explorer._on_item_expanded(item2)
        self.assertTrue(item2.isExpanded())
        self.assertFalse(item1.isExpanded())

    def test_import_paths_preserve_hierarchy_option(self):
        """Verify import_paths preserves subfolder structure when preserve_hierarchy is True."""
        project = self.project_service.create_project("Import Proj", "game", self.temp_dir + "/imp", "I")

        # Create source directory structure: src_dir/sub/test.txt
        src_dir = Path(self.temp_dir) / "source_folder"
        sub_dir = src_dir / "sub"
        sub_dir.mkdir(parents=True, exist_ok=True)
        test_file = sub_dir / "test.txt"
        test_file.write_text("sample content")

        report = self.asset_service.import_paths(project, "assets", [str(src_dir)], preserve_hierarchy=True)
        self.assertGreater(len(report.get("imported", [])), 0)

        imported_rel = report["imported"][0]
        self.assertIn("sub", imported_rel)


if __name__ == "__main__":
    unittest.main()
