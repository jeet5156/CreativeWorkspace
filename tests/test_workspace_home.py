import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from PySide6.QtWidgets import QApplication

from models.project import Project
from services.project_service import ProjectService
from ui.widgets.project_card import ProjectCard
from ui.panels.home_workspace_panel import HomeWorkspacePanel

app = QApplication.instance() or QApplication([])


class TestWorkspaceHome(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.service = ProjectService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_pinning_and_last_opened_persistence(self):
        """Verify project is_pinned and last_opened persistence in project.json."""
        project = self.service.create_project(
            name="Project One",
            project_type="game",
            location=self.temp_dir,
            description="Test project",
        )

        self.assertFalse(project.is_pinned)
        self.service.toggle_pin_project(project)
        self.assertTrue(project.is_pinned)

        # Reload from disk
        loaded = self.service.load_project(project.location)
        self.assertTrue(loaded.is_pinned)

    def test_open_project_updates_last_opened_timestamp(self):
        """Verify opening a project updates last_opened timestamp."""
        project = self.service.create_project(
            name="Project Two",
            project_type="portfolio",
            location=self.temp_dir,
            description="Test project 2",
        )
        old_time = datetime.now() - timedelta(days=2)
        project.last_opened = old_time
        self.service.save_project(project)

        self.service.open_project(project)
        self.assertGreater(project.last_opened, old_time)

    def test_project_card_widget(self):
        """Verify ProjectCard initialization and pin toggle signal."""
        project = Project(
            name="Cyberpunk 2099",
            project_type="game",
            location=self.temp_dir,
            is_pinned=True,
        )
        card = ProjectCard(project, compact=False)
        self.assertEqual(card.title_label.text(), "Cyberpunk 2099")
        self.assertEqual(card.pin_button.text(), "★")

        received = []
        card.pin_toggled.connect(lambda p: received.append(p))
        card._on_pin_clicked()
        self.assertEqual(len(received), 1)

    def test_home_workspace_panel_sorting_and_pinning(self):
        """Verify HomeWorkspacePanel renders projects sorted by last_opened descending."""
        p1 = self.service.create_project("Alpha", "game", self.temp_dir, "A")
        p2 = self.service.create_project("Beta", "portfolio", self.temp_dir, "B")

        p1.last_opened = datetime.now() - timedelta(hours=5)
        p2.last_opened = datetime.now()
        p2.is_pinned = True

        self.service.save_project(p1)
        self.service.save_project(p2)

        context = type('Context', (), {'project_service': self.service})()

        panel = HomeWorkspacePanel()
        panel.set_context(context)

        self.assertEqual(panel.recent_grid.count(), 2)
        first_card = panel.recent_grid.itemAt(0).widget()
        self.assertEqual(first_card.project.name, "Beta")


if __name__ == "__main__":
    unittest.main()
