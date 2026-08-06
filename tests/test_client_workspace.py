import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

from models.project import Project
from models.client import Client, ClientContact, ClientActivity
from services.client_service import ClientService
from services.project_service import ProjectService
from core.inspectable_adapters import ClientInspectable
from ui.panels.explorer_panel import ExplorerPanel

app = QApplication.instance() or QApplication([])


class TestClientWorkspace(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.client_service = ClientService(workspace_location=self.temp_dir)
        self.project_service = ProjectService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_client_crud_operations(self):
        """Verify Client Create, Edit, Archive, and Delete operations."""
        client = self.client_service.create_client(
            name="Epic Games",
            company="Epic Games Entertainment",
            client_type="Game Studio",
            status="Active"
        )
        self.assertIsNotNone(client)
        self.assertEqual(client.name, "Epic Games")
        self.assertEqual(client.status, "Active")

        # Edit Client
        client.website = "https://epicgames.com"
        client.notes = "Senior Character Artist Contract"
        self.client_service.save_client(client)

        reloaded = self.client_service.get_client(client.id)
        self.assertEqual(reloaded.website, "https://epicgames.com")
        self.assertEqual(reloaded.notes, "Senior Character Artist Contract")

        # Archive Client
        self.client_service.archive_client(client.id)
        self.assertEqual(self.client_service.get_client(client.id).status, "Archived")

        # Delete Client
        self.client_service.delete_client(client.id)
        self.assertIsNone(self.client_service.get_client(client.id))

    def test_project_survives_client_deletion(self):
        """Verify deleting a Client sets project.client_id = "" while Project remains intact."""
        client = self.client_service.create_client(name="Ubisoft", status="Active")

        proj_folder = Path(self.temp_dir) / "Cyclops"
        project = self.project_service.create_project(
            name="Cyclops",
            project_type="game",
            location=self.temp_dir,
            description="Stylized Knight"
        )
        project.client_id = client.id

        self.client_service.assign_project_to_client(project.name, client.id, self.project_service)
        self.assertIn(project.name, client.project_ids)

        # Delete Client
        self.client_service.delete_client(client.id, self.project_service)

        # Project MUST survive
        self.assertEqual(project.client_id, "")
        self.assertTrue(Path(project.location).exists())

    def test_project_assignment_save_reload_persistence(self):
        """Verify assigning a Project to a Client survives save and workspace reload cycle."""
        client = self.client_service.create_client(name="Nintendo", status="Active")
        project = self.project_service.create_project(
            name="ZeldaReference",
            project_type="game",
            location=self.temp_dir,
            description="Environment moodboard"
        )

        self.client_service.assign_project_to_client("ZeldaReference", client.id, self.project_service)

        # Reload client service from disk
        reloaded_svc = ClientService(workspace_location=self.temp_dir)
        reloaded_client = reloaded_svc.get_client(client.id)

        self.assertIsNotNone(reloaded_client)
        self.assertIn("ZeldaReference", reloaded_client.project_ids)

    def test_client_inspectable_autosave(self):
        """Verify property changes in ClientInspectable auto-save directly to Client data store."""
        client = self.client_service.create_client(name="Riot Games", status="Prospect")
        adapter = ClientInspectable(client, client_service=self.client_service)

        sections = adapter.get_inspection_sections()
        self.assertEqual(len(sections), 3)

        # Live property edit in Inspector
        res = adapter.set_inspectable_property("website", "https://riotgames.com")
        self.assertTrue(res)

        adapter.set_inspectable_property("status", "Active")
        adapter.set_inspectable_property("industry", "Interactive Media")

        # Verify auto-save persistence
        reloaded_svc = ClientService(workspace_location=self.temp_dir)
        reloaded_client = reloaded_svc.get_client(client.id)
        self.assertEqual(reloaded_client.website, "https://riotgames.com")
        self.assertEqual(reloaded_client.status, "Active")
        self.assertEqual(reloaded_client.industry, "Interactive Media")

    def test_client_signals_emission(self):
        """Verify PySide6 signals are emitted during lifecycle operations."""
        emitted_signals = []

        self.client_service.client_created.connect(lambda c: emitted_signals.append("created"))
        self.client_service.client_updated.connect(lambda c: emitted_signals.append("updated"))
        self.client_service.client_deleted.connect(lambda cid: emitted_signals.append("deleted"))

        client = self.client_service.create_client(name="Valve", status="Active")
        self.assertIn("created", emitted_signals)

        self.client_service.save_client(client)
        self.assertIn("updated", emitted_signals)

        self.client_service.delete_client(client.id)
        self.assertIn("deleted", emitted_signals)

    def test_explorer_client_grouping(self):
        """Verify ExplorerPanel groups Clients under Active Clients, Prospects, and Archived."""
        c_active = Client(name="Active Client", status="Active")
        c_prospect = Client(name="Prospect Client", status="Prospect")
        c_archived = Client(name="Archived Client", status="Archived")

        explorer = ExplorerPanel()
        explorer.load_clients([c_active, c_prospect, c_archived])

        self.assertEqual(explorer.clients_root.childCount(), 3)
        self.assertEqual(explorer.clients_root.child(0).text(0), "🟢 Active Clients")
        self.assertEqual(explorer.clients_root.child(1).text(0), "🟡 Prospects")
        self.assertEqual(explorer.clients_root.child(2).text(0), "🔴 Archived")


if __name__ == "__main__":
    unittest.main()
