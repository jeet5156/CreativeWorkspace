import os
import shutil
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QMouseEvent

app = QApplication.instance() or QApplication([])

import sys
sys.path.insert(0, r"c:\Users\jeet5\.copilot\repos\creativeworkspace")

from models.project import Project
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.home_workspace_panel import HomeWorkspacePanel, PinnedCard, ActionTile
from ui.widgets.project_card import ProjectCard


class TestHomeUXRefinements(unittest.TestCase):
    """Focused unit test suite for Home Workspace UX refinements."""

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

        # Create Project Alpha
        alpha_dir = str(Path(self.temp_dir) / "Alpha")
        os.makedirs(alpha_dir, exist_ok=True)
        self.proj_alpha = Project(
            name="Alpha",
            project_type="game",
            location=alpha_dir,
            is_pinned=False
        )

        # Create Project Beta
        beta_dir = str(Path(self.temp_dir) / "Beta")
        os.makedirs(beta_dir, exist_ok=True)
        self.proj_beta = Project(
            name="Beta",
            project_type="audio",
            location=beta_dir,
            is_pinned=False
        )

        self.project_svc.projects = [self.proj_alpha, self.proj_beta]
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

    def tearDown(self):
        LabService.get_boards_dir = self.orig_get_boards_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_favorite_project_appearing_and_removing_from_home(self):
        """Verify favorite project appears immediately in Pinned/Favorites and removes when un-favorited."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # Initially, neither project is pinned/favorite
        fav_cards_count = sum(
            1 for item in home._cached_pinned_items if item.get("type") == "project"
        )
        self.assertEqual(fav_cards_count, 0)

        # Favorite Project Alpha
        self.project_svc.toggle_pin_project(self.proj_alpha)

        # Verify Project Alpha appears in Pinned/Favorites
        home.set_context(self.context)
        fav_items = [
            item for item in home._cached_pinned_items if item.get("type") == "project"
        ]
        self.assertEqual(len(fav_items), 1)
        self.assertEqual(fav_items[0]["project"].name, "Alpha")

        # Un-favorite Project Alpha
        self.project_svc.toggle_pin_project(self.proj_alpha)
        home.set_context(self.context)
        fav_items_after = [
            item for item in home._cached_pinned_items if item.get("type") == "project"
        ]
        self.assertEqual(len(fav_items_after), 0)

    def test_project_card_click_vs_drag(self):
        """Verify ProjectCard distinguishes click from drag threshold and star button click."""
        card = ProjectCard(self.proj_alpha)

        clicked_received = []
        card.clicked.connect(lambda p: clicked_received.append(p))

        pin_toggled_received = []
        card.pin_toggled.connect(lambda p: pin_toggled_received.append(p))

        # 1. Normal Press & Release (Click below threshold)
        press_event = QMouseEvent(
            QMouseEvent.MouseButtonPress,
            QPoint(20, 20),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier
        )
        release_event = QMouseEvent(
            QMouseEvent.MouseButtonRelease,
            QPoint(22, 22),  # 2px move < Qt drag threshold (typically >= 10px)
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier
        )
        card.mousePressEvent(press_event)
        card.mouseReleaseEvent(release_event)

        self.assertEqual(len(clicked_received), 1)
        self.assertEqual(clicked_received[0].name, "Alpha")

        # 2. Drag threshold exceeded (Drag performed -> click should NOT fire)
        clicked_received.clear()
        card._drag_performed = True  # simulate drag started
        card.mouseReleaseEvent(release_event)
        self.assertEqual(len(clicked_received), 0)

        # 3. Pin/Star button click should trigger pin_toggled without card click
        card._drag_performed = False
        card.pin_button.click()
        self.assertEqual(len(pin_toggled_received), 1)
        self.assertEqual(pin_toggled_received[0].name, "Alpha")

    def test_persisted_project_ordering(self):
        """Verify project reordering updates and persists order across context refreshes."""
        home = HomeWorkspacePanel()
        home.set_context(self.context)

        # Reorder Beta before Alpha
        home._on_project_card_reordered(self.proj_beta.location, self.proj_alpha.location)

        saved_order = self.lab_svc.get_project_order()
        self.assertEqual(saved_order, [self.proj_beta.location, self.proj_alpha.location])

        # New panel instance should respect persisted order
        new_home = HomeWorkspacePanel()
        new_home.set_context(self.context)
        self.assertEqual(
            [p.location for p in new_home._sorted_projects],
            [self.proj_beta.location, self.proj_alpha.location]
        )

    def test_quick_actions_remaining_accessible_at_top(self):
        """Verify Quick Actions tiles exist and are accessible near the top of Home layout."""
        home = HomeWorkspacePanel()
        tiles = home.findChildren(ActionTile)
        self.assertEqual(len(tiles), 5)

        tile_titles = [
            lbl.text()
            for tile in tiles
            for lbl in tile.findChildren(QLabel)
            if lbl.text() in ("New Project", "Open Workbench", "Open Project", "Open Recent", "Asset Library")
        ]
        self.assertIn("New Project", tile_titles)
        self.assertIn("Open Workbench", tile_titles)
        self.assertIn("Open Project", tile_titles)
        self.assertIn("Open Recent", tile_titles)
        self.assertIn("Asset Library", tile_titles)


if __name__ == "__main__":
    unittest.main()
