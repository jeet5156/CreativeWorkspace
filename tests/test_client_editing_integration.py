import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

from models.client import Client, CLIENT_STATUSES, CLIENT_TYPES, CLIENT_PRIORITIES
from models.project import Project
from services.client_service import ClientService
from services.project_service import ProjectService
from core.inspectable_adapters import ClientInspectable, ProjectInspectable
from ui.dialogs.client_dialog import ClientDialog
from ui.panels.explorer_panel import ExplorerPanel
from ui.panels.client_workspace_panel import ClientWorkspacePanel
from ui.panels.inspector_panel import InspectorPanel
from core.app_context import AppContext

app = QApplication.instance() or QApplication([])


class TestClientEditingIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.client_service = ClientService(workspace_location=self.temp_dir)
        self.project_service = ProjectService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_inspector_editing_and_autosave(self):
        """Verify editing fields in ClientInspectable immediately updates client and auto-saves to disk."""
        client = self.client_service.create_client(
            name="Ubisoft",
            company="Ubisoft Entertainment",
            status="Active",
            priority="High",
        )
        updated_signal_received = []
        self.client_service.client_updated.connect(lambda c: updated_signal_received.append(c))

        adapter = ClientInspectable(client, client_service=self.client_service)
        sections = adapter.get_inspection_sections()
        self.assertEqual(len(sections), 3)  # General, Projects & Metadata

        # Edit fields via Inspectable
        adapter.set_inspectable_property("name", "Ubisoft Montreal")
        adapter.set_inspectable_property("company", "Ubisoft Montreal Inc")
        adapter.set_inspectable_property("priority", "High")
        adapter.set_inspectable_property("status", "Active")
        adapter.set_inspectable_property("client_type", "Publisher")
        adapter.set_inspectable_property("industry", "AAA Gaming")
        adapter.set_inspectable_property("website", "https://ubisoft.com")
        adapter.set_inspectable_property("country", "Canada")
        adapter.set_inspectable_property("tags", "AAA, Console, PC")
        adapter.set_inspectable_property("notes", "Major publisher relationship")

        self.assertTrue(len(updated_signal_received) > 0)
        self.assertEqual(client.name, "Ubisoft Montreal")
        self.assertEqual(client.priority, "High")

        # Reload from disk to verify persistence
        reloaded_svc = ClientService(workspace_location=self.temp_dir)
        reloaded = reloaded_svc.get_client(client.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.name, "Ubisoft Montreal")
        self.assertEqual(reloaded.company, "Ubisoft Montreal Inc")
        self.assertEqual(reloaded.priority, "High")
        self.assertEqual(reloaded.client_type, "Publisher")
        self.assertEqual(reloaded.industry, "AAA Gaming")
        self.assertEqual(reloaded.website, "https://ubisoft.com")
        self.assertEqual(reloaded.country, "Canada")
        self.assertIn("AAA", reloaded.tags)
        self.assertEqual(reloaded.notes, "Major publisher relationship")

    def test_client_dialog_create_and_edit_reuse(self):
        """Verify ClientDialog reuses single dialog class for Create and Edit modes."""
        # Create mode
        dlg_create = ClientDialog()
        self.assertEqual(dlg_create.windowTitle(), "New Client")
        self.assertEqual(dlg_create.create_btn.text(), "Create Client")
        self.assertEqual(dlg_create.name_edit.text(), "")

        # Edit mode
        existing = Client(
            name="Epic Games",
            company="Epic Games Inc",
            priority="High",
            status="Active",
            client_type="Game Studio",
            industry="VFX & Games",
            website="https://epicgames.com",
            country="USA",
            tags=["Unreal", "Engine"],
            notes="Fortnite developer",
        )
        dlg_edit = ClientDialog(client=existing)
        self.assertEqual(dlg_edit.windowTitle(), "Edit Client")
        self.assertEqual(dlg_edit.create_btn.text(), "Save Changes")
        self.assertEqual(dlg_edit.name_edit.text(), "Epic Games")
        self.assertEqual(dlg_edit.company_edit.text(), "Epic Games Inc")
        self.assertEqual(dlg_edit.priority_combo.currentText(), "High")
        self.assertEqual(dlg_edit.website_edit.text(), "https://epicgames.com")
        self.assertIn("Unreal", dlg_edit.tags_edit.text())

        # Modify values in Edit Dialog
        dlg_edit.name_edit.setText("Epic Games International")
        dlg_edit.priority_combo.setCurrentText("High")
        data = dlg_edit.get_client_data()
        self.assertEqual(data["name"], "Epic Games International")
        self.assertEqual(data["priority"], "High")

    def test_explorer_immediate_rename_update(self):
        """Verify renaming a client updates the Explorer tree immediately without app restart."""
        client = self.client_service.create_client(name="Nintendo", status="Active")

        explorer = ExplorerPanel()
        context = AppContext()
        context.client_service = self.client_service
        context.inspector_panel = InspectorPanel()
        explorer.set_context(context)

        # Initial tree check
        active_group = explorer.clients_root.child(0)
        self.assertEqual(active_group.childCount(), 1)
        self.assertIn("Nintendo", active_group.child(0).text(0))

        # Rename client
        client.name = "Nintendo Co., Ltd."
        self.client_service.save_client(client)

        # Explorer tree must be updated automatically via signal
        active_group = explorer.clients_root.child(0)
        self.assertIn("Nintendo Co., Ltd.", active_group.child(0).text(0))

    def test_project_inspector_client_reassignment_sync(self):
        """Verify changing Client dropdown in ProjectInspectable updates client assignments instantly."""
        c1 = self.client_service.create_client(name="Studio Alpha")
        c2 = self.client_service.create_client(name="Studio Beta")

        project = self.project_service.create_project(
            name="Project Gamma",
            project_type="game",
            location=self.temp_dir,
            description="Test game project",
        )
        self.client_service.assign_project_to_client(project.name, c1.id, self.project_service)
        self.assertEqual(project.client_id, c1.id)

        # Reassign via ProjectInspectable dropdown
        p_adapter = ProjectInspectable(project, project_service=self.project_service, client_service=self.client_service)
        sections = p_adapter.get_inspection_sections()
        org_sec = sections[1]
        client_field = [f for f in org_sec.fields if f.key == "client"][0]
        self.assertIn("Studio Beta", client_field.options)

        # Change dropdown value to Studio Beta
        res = p_adapter.set_inspectable_property("client", "Studio Beta")
        self.assertTrue(res)
        self.assertEqual(project.client_id, c2.id)

        # Verify old client c1 removed, new client c2 assigned
        self.assertNotIn("Project Gamma", c1.project_ids)
        self.assertIn("Project Gamma", c2.project_ids)

    def test_client_activation_and_deletion_inspector_sync(self):
        """Verify selecting client activates Inspector and deleting client clears Inspector (Requirement 11)."""
        context = AppContext()
        context.client_service = self.client_service
        inspector = InspectorPanel()
        inspector.set_context(context)
        context.inspector_panel = inspector

        client = self.client_service.create_client(name="Sony PlayStation")
        inspector.show_client(client)

        # Inspector should display client title
        self.assertIn("Sony PlayStation", inspector.header_title.text())

        # Deleting client should clear Inspector
        self.client_service.delete_client(client.id)
        self.assertEqual(inspector.header_title.text(), "Inspector")

    def test_full_app_lifecycle_persistence_and_rename(self):
        """Item 10: Create Client -> Create Project -> Assign -> Rename -> Save/Close -> Reopen -> Verify persistence."""
        # 1. Create Client
        client = self.client_service.create_client(name="Ubisoft", company="Ubisoft Inc", status="Active")

        # 2. Create Project
        project = self.project_service.create_project(
            name="Rabbids",
            project_type="game",
            location=self.temp_dir,
            description="Party game",
        )

        # 3. Assign Client
        self.client_service.assign_project_to_client(project.name, client.id, self.project_service)
        project.client_id = client.id
        self.project_service.save_project(project)

        # 4. Rename Client
        client.name = "Ubisoft Montreal"
        self.client_service.save_client(client)

        # 5. Simulate App Shutdown and Reopen by reloading fresh services from disk
        new_client_svc = ClientService(workspace_location=self.temp_dir)
        new_proj_svc = ProjectService()
        reloaded_proj = new_proj_svc.load_project(project.location)
        reloaded_client = new_client_svc.get_client(client.id)

        # 6. Verify persistence
        self.assertIsNotNone(reloaded_client)
        self.assertEqual(reloaded_client.name, "Ubisoft Montreal")
        self.assertEqual(reloaded_proj.client_id, reloaded_client.id)

        # Explorer simulation check
        explorer = ExplorerPanel()
        explorer.load_clients(new_client_svc.list_clients())
        active_group = explorer.clients_root.child(0)
        self.assertIn("Ubisoft Montreal", active_group.child(0).text(0))


if __name__ == "__main__":
    unittest.main()
