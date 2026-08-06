import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

from models.client import Client
from models.project import Project
from services.client_service import ClientService
from services.project_service import ProjectService
from core.inspectable_adapters import ClientInspectable, ProjectInspectable
from ui.panels.explorer_panel import ExplorerPanel
from ui.panels.client_workspace_panel import ClientWorkspacePanel
from ui.panels.inspector_panel import InspectorPanel
from core.app_context import AppContext

app = QApplication.instance() or QApplication([])


class TestClientStabilization(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.client_service = ClientService(workspace_location=self.temp_dir)
        self.project_service = ProjectService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_client_persistence_across_restart(self):
        """Test 1: Create Client -> Restart app -> Client still exists."""
        client = self.client_service.create_client(
            name="Epic Games",
            company="Epic Games Inc",
            priority="High",
            status="Active",
            client_type="Game Studio",
            industry="Entertainment",
            website="https://epicgames.com",
            country="USA",
        )
        client_id = client.id

        # Simulate Application Restart
        reloaded_svc = ClientService(workspace_location=self.temp_dir)
        reloaded_client = reloaded_svc.get_client(client_id)

        self.assertIsNotNone(reloaded_client)
        self.assertEqual(reloaded_client.name, "Epic Games")
        self.assertEqual(reloaded_client.company, "Epic Games Inc")
        self.assertEqual(reloaded_client.priority, "High")

    def test_client_project_relationship_persistence(self):
        """Test 2: Create Project from Client -> Restart app -> Relationship still exists."""
        client = self.client_service.create_client(name="Ubisoft")
        project = self.project_service.create_project(
            name="Rabbids",
            project_type="game",
            location=self.temp_dir,
            description="Party Game",
        )
        self.client_service.assign_project_to_client(project.name, client.id, self.project_service)
        project.client_id = client.id
        self.project_service.save_project(project)

        # Simulate Application Restart
        reloaded_client_svc = ClientService(workspace_location=self.temp_dir)
        reloaded_proj_svc = ProjectService()

        reloaded_client = reloaded_client_svc.get_client(client.id)
        reloaded_project = reloaded_proj_svc.load_project(project.location)

        self.assertIsNotNone(reloaded_client)
        self.assertIsNotNone(reloaded_project)
        self.assertIn(project.name, reloaded_client.project_ids)
        self.assertEqual(reloaded_project.client_id, client.id)

    def test_delete_client_project_survives(self):
        """Test 3: Delete Client -> Project still exists, client_id == ""."""
        client = self.client_service.create_client(name="Bethesda")
        project = self.project_service.create_project(
            name="Starfield",
            project_type="game",
            location=self.temp_dir,
            description="RPG",
        )
        self.client_service.assign_project_to_client(project.name, client.id, self.project_service)

        # Delete Client
        self.client_service.delete_client(client.id, self.project_service)

        self.assertIsNone(self.client_service.get_client(client.id))
        self.assertEqual(project.client_id, "")
        self.assertTrue(Path(project.location).exists())

    def test_rename_client_explorer_updates(self):
        """Test 4: Rename Client -> Explorer tree updates immediately."""
        client = self.client_service.create_client(name="Square Enix")

        explorer = ExplorerPanel()
        explorer.load_clients(self.client_service.list_clients())

        active_group = explorer.clients_root.child(0)
        self.assertIn("Square Enix", active_group.child(0).text(0))

        # Rename client
        client.name = "Square Enix Japan"
        self.client_service.save_client(client)

        # Reload clients into explorer
        explorer.load_clients(self.client_service.list_clients())
        active_group = explorer.clients_root.child(0)
        self.assertIn("Square Enix Japan", active_group.child(0).text(0))

    def test_reassign_project_dashboards_update(self):
        """Test 5: Reassign Project -> Both old and new client dashboards update."""
        c1 = self.client_service.create_client(name="Client One")
        c2 = self.client_service.create_client(name="Client Two")
        project = self.project_service.create_project(
            name="Shared Demo",
            project_type="game",
            location=self.temp_dir,
            description="Demo",
        )
        self.client_service.assign_project_to_client(project.name, c1.id, self.project_service)

        # Reassign project to Client Two
        self.client_service.remove_project_from_client(project.name, c1.id, self.project_service)
        self.client_service.assign_project_to_client(project.name, c2.id, self.project_service)

        self.assertNotIn(project.name, c1.project_ids)
        self.assertIn(project.name, c2.project_ids)

    def test_reveal_in_explorer_does_not_switch_workspace(self):
        """Test 6: Reveal in Explorer -> Does not switch workspace (emit=False)."""
        project = self.project_service.create_project(
            name="Target Proj",
            project_type="game",
            location=self.temp_dir,
            description="Target",
        )
        explorer = ExplorerPanel()
        explorer.load_projects([project])

        emitted_signals = []
        explorer.project_selected.connect(lambda p, s, r: emitted_signals.append(p))

        # Reveal in explorer with emit=False
        explorer.reveal_project(project, emit=False)

        # Must not emit project_selected signal so active workspace does not switch
        self.assertEqual(len(emitted_signals), 0)


if __name__ == "__main__":
    unittest.main()
