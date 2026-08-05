import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QSize

from models.project import Project
from services.project_service import ProjectService
from services.thumbnail_service import ThumbnailService
from services.performance_logger import PerformanceLogger
from ui.widgets.project_tree_card import ProjectTreeCard
from ui.panels.home_workspace_panel import HomeWorkspacePanel
from ui.panels.workspace_panel import WorkspacePanel
from ui.workspace_manager import WorkspaceManager

app = QApplication.instance() or QApplication([])


class TestStabilityPass(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.service = ProjectService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_performance_logger_measurement(self):
        """Verify PerformanceLogger tracks execution duration."""
        measured_val = PerformanceLogger.measure("Test Action", lambda: 42)
        self.assertEqual(measured_val, 42)

    def test_project_tree_card_geometry_ownership(self):
        """Verify ProjectTreeCard sizeHint owns 38px row height."""
        project = Project("Test Proj", "game", self.temp_dir)
        card = ProjectTreeCard(project)
        self.assertEqual(card.FIXED_HEIGHT, 38)
        self.assertEqual(card.sizeHint().height(), 38)

    def test_3_level_thumbnail_caching(self):
        """Verify 3-level thumbnail caching (index cache, QPixmap cache)."""
        thumb_svc = ThumbnailService()
        project_loc = self.temp_dir

        # Create dummy thumbnail image on disk
        thumb_dir = Path(project_loc) / ".creativeworkspace" / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        img_path = thumb_dir / "sample.png"

        img = QImage(64, 64, QImage.Format_ARGB32)
        img.fill(0xFFFF0000)
        img.save(str(img_path), "PNG")

        # Level 3 Pixmap Cache test
        pix1 = thumb_svc.get_cached_pixmap(str(img_path))
        self.assertIsNotNone(pix1)
        self.assertFalse(pix1.isNull())

        # Second lookup should come directly from in-memory pixmap cache
        self.assertIn(str(img_path), thumb_svc._pixmap_cache)
        pix2 = thumb_svc.get_cached_pixmap(str(img_path))
        self.assertEqual(pix1, pix2)

    def test_responsive_home_card_columns(self):
        """Verify HomeWorkspacePanel calculates columns dynamically."""
        panel = HomeWorkspacePanel()
        panel.resize(1000, 600)
        cols = panel._calc_columns()
        self.assertGreaterEqual(cols, 3)
        self.assertLessEqual(cols, 5)

    def test_navigation_stack_switching(self):
        """Verify central navigation switching across workspace views."""
        workspace = WorkspacePanel()
        context = type('Context', (), {
            'project_service': self.service,
            'app_state': None,
            'current_project': None,
            'workspace_manager': None,
        })()
        manager = WorkspaceManager(workspace, context)
        context.workspace_manager = manager
        workspace.set_context(context)

        # Switch to Home
        manager.show_home()
        self.assertEqual(workspace.stack.currentWidget(), workspace.home)

        # Create project and switch to Lab
        project = self.service.create_project("Lab Proj", "game", self.temp_dir, "Lab test")
        workspace.show_section(project, "lab")
        self.assertEqual(workspace.stack.currentWidget(), manager.lab_panel)


if __name__ == "__main__":
    unittest.main()
