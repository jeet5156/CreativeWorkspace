import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

from models.project import Project
from services.project_service import ProjectService
from core.inspectable_adapters import ProjectInspectable

app = QApplication.instance() or QApplication([])


class TestProjectLifecycle(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.service = ProjectService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_model_default_fields(self):
        """Verify strongly defined default fields on Project model."""
        p = Project(name="Cyclops", project_type="portfolio", location=self.temp_dir)
        self.assertEqual(p.name, "Cyclops")
        self.assertEqual(p.project_type, "portfolio")
        self.assertEqual(p.priority, "medium")
        self.assertEqual(p.status, "active")
        self.assertEqual(p.tags, [])
        self.assertEqual(p.client, "")
        self.assertEqual(p.repository, "")
        self.assertEqual(p.deadline, "")
        self.assertIsNotNone(p.created)
        self.assertIsNotNone(p.modified)

    def test_project_service_save_and_load_persistence(self):
        """Verify saving and loading project preserves all fields in project.json."""
        project = self.service.create_project(
            name="Alpha Game",
            project_type="game",
            location=self.temp_dir,
            description="High priority AAA game",
        )

        project.priority = "high"
        project.status = "in progress"
        project.tags = ["unreal", "game", "3d"]
        project.client = "Epic Games"
        project.repository = "https://github.com/org/alpha"
        project.deadline = "2026-12-31"

        # Track signals
        events_received = []
        self.service.project_updated.connect(lambda p: events_received.append(p))

        self.service.save_project(project)

        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0].name, "Alpha Game")

        # Load fresh instance from disk
        proj_dir = Path(project.location)
        loaded = self.service.load_project(proj_dir)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Alpha Game")
        self.assertEqual(loaded.priority, "high")
        self.assertEqual(loaded.status, "in progress")
        self.assertEqual(loaded.tags, ["unreal", "game", "3d"])
        self.assertEqual(loaded.client, "Epic Games")
        self.assertEqual(loaded.repository, "https://github.com/org/alpha")
        self.assertEqual(loaded.deadline, "2026-12-31")

    def test_project_inspectable_mutation(self):
        """Verify ProjectInspectable updates model and triggers save_project."""
        project = self.service.create_project(
            name="Beta Suite",
            project_type="audio",
            location=self.temp_dir,
            description="Audio suite",
        )

        adapter = ProjectInspectable(project, project_service=self.service)

        # Mutate Name
        adapter.set_inspectable_property("name", "Beta Suite Pro")
        self.assertEqual(project.name, "Beta Suite Pro")

        # Mutate Organization fields
        adapter.set_inspectable_property("client", "Warner Music")
        adapter.set_inspectable_property("repository", "git@github.com:audio/beta.git")
        adapter.set_inspectable_property("deadline", "15 Nov 2026")
        adapter.set_inspectable_property("tags", "vst, audio, synth")

        self.assertEqual(project.client, "Warner Music")
        self.assertEqual(project.repository, "git@github.com:audio/beta.git")
        self.assertEqual(project.deadline, "15 Nov 2026")
        self.assertEqual(project.tags, ["vst", "audio", "synth"])

        # Reload and verify disk persistence
        loaded = self.service.load_project(Path(project.location))
        self.assertEqual(loaded.name, "Beta Suite Pro")
        self.assertEqual(loaded.client, "Warner Music")
        self.assertEqual(loaded.repository, "git@github.com:audio/beta.git")
        self.assertEqual(loaded.deadline, "15 Nov 2026")
        self.assertEqual(loaded.tags, ["vst", "audio", "synth"])

    def test_project_event_signals(self):
        """Verify project_opened and project_deleted events emit properly."""
        opened_events = []
        deleted_events = []

        self.service.project_opened.connect(lambda p: opened_events.append(p))
        self.service.project_deleted.connect(lambda p: deleted_events.append(p))

        project = self.service.create_project(
            name="Gamma Project",
            project_type="r&d",
            location=self.temp_dir,
            description="Experimental R&D",
        )

        self.service.open_project(project)
        self.assertEqual(len(opened_events), 1)
        self.assertEqual(opened_events[0].name, "Gamma Project")

        self.service.delete_project(project)
        self.assertEqual(len(deleted_events), 1)


if __name__ == "__main__":
    unittest.main()
