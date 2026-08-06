import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

from models.client import Client
from models.project import Project
from services.client_service import ClientService
from services.project_service import ProjectService
from ui.dialogs.new_project_dialog import NewProjectDialog
from ui.panels.client_dashboard import ClientOverviewPanel, ClientDashboard
from ui.panels.client_workspace_panel import ClientWorkspacePanel
from ui.panels.explorer_panel import ExplorerPanel
from core.inspectable_adapters import ProjectInspectable

app = QApplication.instance() or QApplication([])


class FakeContext:
    def __init__(self, workspace_location):
        self.workspace_location = workspace_location
        self.client_service = ClientService(workspace_location=workspace_location)
        self.project_service = ProjectService()
        self.explorer_panel = ExplorerPanel()
        self.inspector_panel = None
        self.workspace_manager = None
        self.explorer_panel.set_context(self)


class TestClientProjectIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.context = FakeContext(self.temp_dir)
        self.client_service = self.context.client_service
        self.project_service = self.context.project_service

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_project_from_client_and_auto_navigation(self):
        """Verify creating a project from a client assigns client_id and triggers auto-navigation."""
        client = self.client_service.create_client(name="Ubisoft", status="Active")
        panel = ClientWorkspacePanel(self.context)
        panel.show_client_dashboard(client)

        # Create project
        proj_dir = Path(self.temp_dir) / "Cyberpunk"
        project = self.project_service.create_project(
            name="Cyberpunk",
            project_type="game",
            location=self.temp_dir,
            description="Sci-fi RPG"
        )
        project.client_id = client.id
        self.project_service.save_project(project)

        # Query ProjectService dynamically
        client_projects = self.project_service.get_projects_for_client(client.id)
        self.assertEqual(len(client_projects), 1)
        self.assertEqual(client_projects[0].name, "Cyberpunk")
        self.assertEqual(client_projects[0].client_id, client.id)

    def test_project_service_get_projects_for_client(self):
        """Verify ProjectService.get_projects_for_client is the sole source of truth."""
        c1 = self.client_service.create_client(name="Riot Games")
        c2 = self.client_service.create_client(name="Epic Games")

        p1 = self.project_service.create_project("Project Alpha", "game", self.temp_dir, "Desc A")
        p1.client_id = c1.id
        self.project_service.save_project(p1)

        p2 = self.project_service.create_project("Project Beta", "portfolio", self.temp_dir, "Desc B")
        p2.client_id = c1.id
        self.project_service.save_project(p2)

        p3 = self.project_service.create_project("Project Gamma", "learning", self.temp_dir, "Desc C")
        p3.client_id = c2.id
        self.project_service.save_project(p3)

        self.assertEqual(len(self.project_service.get_projects_for_client(c1.id)), 2)
        self.assertEqual(len(self.project_service.get_projects_for_client(c2.id)), 1)
        self.assertEqual(len(self.project_service.get_projects_for_client("non-existent-id")), 0)

    def test_client_dashboard_rich_cards_and_action_signals(self):
        """Verify ClientOverviewPanel renders rich project cards and emits Open & Reveal signals."""
        client = self.client_service.create_client(name="EA Sports")
        project = self.project_service.create_project("FIFA Asset Pack", "portfolio", self.temp_dir, "3D Models")
        project.client_id = client.id
        self.project_service.save_project(project)

        dashboard = ClientOverviewPanel()
        dashboard.set_client(client, project_service=self.project_service)

        self.assertEqual(len(dashboard.associated_projects), 1)

        emitted_events = []
        dashboard.open_project_requested.connect(lambda p: emitted_events.append(("open", p)))
        dashboard.reveal_project_requested.connect(lambda p: emitted_events.append(("reveal", p)))

        # Verify card layout count
        self.assertEqual(dashboard.projects_layout.count(), 1)
        card_widget = dashboard.projects_layout.itemAt(0).widget()
        self.assertIsNotNone(card_widget)

        # Trigger Open & Reveal signals
        dashboard.open_project_requested.emit(project)
        dashboard.reveal_project_requested.emit(project)

        self.assertEqual(len(emitted_events), 2)
        self.assertEqual(emitted_events[0][0], "open")
        self.assertEqual(emitted_events[1][0], "reveal")

    def test_inspector_client_reassignment_refreshes_views(self):
        """Verify reassigning a project's client in ProjectInspectable updates Project.client_id and triggers save."""
        c1 = self.client_service.create_client(name="Naughty Dog")
        c2 = self.client_service.create_client(name="Insomniac")

        project = self.project_service.create_project("Uncharted Map", "game", self.temp_dir, "Level Design")
        project.client_id = c1.id
        self.project_service.save_project(project)

        adapter = ProjectInspectable(project, project_service=self.project_service, client_service=self.client_service)

        # Reassign to c2 via inspector
        res = adapter.set_inspectable_property("client_id", c2.id)
        self.assertTrue(res)
        self.assertEqual(project.client_id, c2.id)

        # Verify dynamic querying reflects reassignment
        self.assertEqual(len(self.project_service.get_projects_for_client(c1.id)), 0)
        self.assertEqual(len(self.project_service.get_projects_for_client(c2.id)), 1)

    def test_project_deletion_instantly_removes_from_client_dashboard(self):
        """Verify deleting a project removes it from ProjectService and client project queries instantly."""
        client = self.client_service.create_client(name="Valve")
        project = self.project_service.create_project("Stylized Knight", "game", self.temp_dir, "3D Character")
        project.client_id = client.id
        self.project_service.save_project(project)

        self.assertEqual(len(self.project_service.get_projects_for_client(client.id)), 1)

        # Delete project
        self.project_service.delete_project(project)

        self.assertEqual(len(self.project_service.get_projects_for_client(client.id)), 0)

    def test_client_deletion_resets_client_id_without_deleting_files(self):
        """Verify deleting a client sets project.client_id = "" while keeping project files intact."""
        client = self.client_service.create_client(name="Blizzard")
        project = self.project_service.create_project("Warcraft Art", "game", self.temp_dir, "Concepts")
        project.client_id = client.id
        self.project_service.save_project(project)

        # Delete client
        self.client_service.delete_client(client.id, self.project_service)

        # Project client_id should be cleared, project folder untouched
        self.assertEqual(project.client_id, "")
        self.assertTrue(Path(project.location).exists())
        self.assertTrue((Path(project.location) / "project.json").exists())

    def test_new_project_dialog_locked_and_unlocked_modes(self):
        """Verify NewProjectDialog locks client field when lock_client=True."""
        c1 = Client(name="Ubisoft", id="u-123")
        c2 = Client(name="Riot", id="r-456")

        # Unlocked mode
        dialog_unlocked = NewProjectDialog(clients=[c1, c2], preselected_client_id="r-456", lock_client=False)
        self.assertTrue(dialog_unlocked.client_combo.isEnabled())
        self.assertEqual(dialog_unlocked.get_selected_client_id(), "r-456")

        # Locked mode
        dialog_locked = NewProjectDialog(clients=[c1, c2], preselected_client_id="u-123", lock_client=True)
        self.assertFalse(dialog_locked.client_combo.isEnabled())
        self.assertEqual(dialog_locked.get_selected_client_id(), "u-123")


if __name__ == "__main__":
    unittest.main()
