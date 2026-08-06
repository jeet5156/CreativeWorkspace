import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication

from models.client import Client
from models.project import Project
from services.client_service import ClientService
from services.project_service import ProjectService
from ui.widgets.client_card import ClientCard
from ui.panels.client_workspace_panel import ClientWorkspacePanel
from ui.lab.nodes.image_node_item import ImageNodeItem
from ui.lab.nodes.node_definition import NodeDefinition

app = QApplication.instance() or QApplication([])


class FakeContext:
    def __init__(self, workspace_location):
        self.workspace_location = workspace_location
        self.client_service = ClientService(workspace_location=workspace_location)
        self.project_service = ProjectService()
        self.explorer_panel = None
        self.inspector_panel = None
        self.workspace_manager = None


class TestClientWorkspaceUX(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.context = FakeContext(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_client_card_rendering_and_signals(self):
        """Verify ClientCard displays status badge, metrics, pin placeholder, and emits signals."""
        client = Client(name="Epic Games", company="Epic Games Inc", status="Active", client_type="Game Studio")
        client.project_ids = ["proj-1", "proj-2"]

        card = ClientCard(client)
        self.assertEqual(card.title_lbl.text(), "Epic Games")
        self.assertEqual(card.status_badge.text(), "ACTIVE")
        self.assertIn("2 Projects", card.proj_lbl.text())

        emitted = []
        card.open_requested.connect(lambda c: emitted.append("open"))
        card.pin_toggled.connect(lambda c: emitted.append("pin"))

        card.open_btn.click()
        self.assertIn("open", emitted)

        card.pin_btn.click()
        self.assertIn("pin", emitted)

    def test_client_workspace_empty_and_populated_states(self):
        """Verify ClientWorkspacePanel switches between Empty State banner and Populated grid."""
        panel = ClientWorkspacePanel(self.context)
        self.assertEqual(panel.stack.currentWidget(), panel.empty_widget)

        # Add Client
        client = self.context.client_service.create_client(name="Nintendo", status="Active")
        panel.refresh()

        self.assertEqual(panel.stack.currentWidget(), panel.grid_scroll)
        self.assertEqual(panel.grid_layout.count(), 1)

    def test_client_workspace_live_search(self):
        """Verify Search Bar filters cards live by name, company, or type."""
        self.context.client_service.create_client(name="Ubisoft", company="Ubisoft Entertainment", client_type="Publisher")
        self.context.client_service.create_client(name="Blizzard", company="Activision Blizzard", client_type="Game Studio")

        panel = ClientWorkspacePanel(self.context)
        panel.refresh()
        self.assertEqual(panel.grid_layout.count(), 2)

        # Filter by name
        panel.search_edit.setText("Ubi")
        self.assertEqual(panel.grid_layout.count(), 1)

        # Filter by type
        panel.search_edit.setText("Publisher")
        self.assertEqual(panel.grid_layout.count(), 1)

        # Clear filter
        panel.search_edit.setText("")
        self.assertEqual(panel.grid_layout.count(), 2)

    def test_image_path_selective_normalization(self):
        """Verify image paths inside project normalize to relative paths; external paths stay absolute."""
        proj_dir = Path(self.temp_dir) / "MyProject"
        proj_dir.mkdir(parents=True, exist_ok=True)
        assets_dir = proj_dir / "Assets"
        assets_dir.mkdir(exist_ok=True)

        internal_img = assets_dir / "hero.png"
        internal_img.write_text("fake_image_data")

        external_dir = Path(self.temp_dir) / "ExternalDownloads"
        external_dir.mkdir(exist_ok=True)
        external_img = external_dir / "stock.png"
        external_img.write_text("fake_image_data")

        from ui.lab.nodes.node_registry import NodeRegistry
        node_def = NodeRegistry.get("image.reference")
        node = ImageNodeItem(node_def)
        node.set_context_services(project_location=str(proj_dir))

        # 1. Internal Image -> relative path
        node.set_image(str(internal_img))
        self.assertEqual(node.payload.get("image_path"), "Assets/hero.png")

        # 2. External Image -> absolute path retained
        node.set_image(str(external_img))
        self.assertEqual(node.payload.get("image_path"), str(external_img.resolve()))

    def test_client_deletion_lifecycle_refreshes_views(self):
        """Verify deleting a client closes open dashboard, clears grid if empty, and updates state."""
        client = self.context.client_service.create_client(name="Old Studio", status="Archived")
        panel = ClientWorkspacePanel(self.context)

        # Open client dashboard
        panel.show_client_dashboard(client)
        self.assertEqual(panel.stack.currentWidget(), panel.dashboard_panel)

        # Delete client
        self.context.client_service.delete_client(client.id)

        # Panel should return to empty state banner cleanly
        self.assertEqual(panel.stack.currentWidget(), panel.empty_widget)


if __name__ == "__main__":
    unittest.main()
