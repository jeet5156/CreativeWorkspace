import os
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize

from core.app_context import AppContext
from models.client import Client, ClientContact
from models.project import Project
from services.client_service import ClientService
from services.lab_service import LabService
from services.project_service import ProjectService
from ui.main_window import MainWindow
from ui.panels.business_panel import BusinessPanel
from ui.panels.explorer_panel import ExplorerPanel
from ui.panels.workspace_panel import WorkspacePanel
from ui.workspace_manager import WorkspaceManager

_app = QApplication.instance() or QApplication([])


class TestUIImprovements(unittest.TestCase):
    """Test suite for Workbench icon, Business Hub, and Splitter/Sidebar width stability."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="cw_ui_test_"))
        self.global_workbench_dir = self.tmp_dir / "workbench"
        self.wb_boards_dir = self.global_workbench_dir / "boards"
        self.wb_boards_dir.mkdir(parents=True, exist_ok=True)
        os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"] = str(self.tmp_dir)

        self.project_svc = ProjectService()
        self.lab_svc = LabService(project_service=self.project_svc, global_storage_dir=self.wb_boards_dir)
        self.client_svc = ClientService(storage_dir=self.tmp_dir / "clients")

        self.context = AppContext()
        self.context.project_service = self.project_svc
        self.context.lab_service = self.lab_svc
        self.context.client_service = self.client_svc

    def tearDown(self):
        if "CREATIVE_WORKSPACE_SHARED_DATA_DIR" in os.environ:
            del os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"]
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -------------------------------------------------------------
    # 1. Workbench Icon & Tree Distinction
    # -------------------------------------------------------------
    def test_1_workbench_root_icon_distinct(self):
        """Workbench root has a distinct tools-related icon distinct from projects and folders."""
        explorer = ExplorerPanel()
        explorer.set_context(self.context)

        # Workbench root has tools icon
        wb_text = explorer.lab_root.text(0)
        self.assertTrue(wb_text.startswith("🛠️"))
        self.assertIn("Workbench", wb_text)

        # Projects root has folder icon
        proj_text = explorer.projects_root.text(0)
        self.assertTrue(proj_text.startswith("📁"))
        self.assertIn("Projects", proj_text)

        # Workbench root icon is not identical to projects root icon
        self.assertNotEqual(wb_text[0], proj_text[0])

    def test_2_workbench_tree_expansion_and_refresh_preserves_icon(self):
        """Refreshing or expanding Workbench root preserves root icon and level distinctions."""
        explorer = ExplorerPanel()
        explorer.set_context(self.context)

        # Expand and refresh
        explorer.refresh_lab_node(None)
        self.assertTrue(explorer.lab_root.text(0).startswith("🛠️"))

        # Verify child collections use collection folder icon and boards use palette icon
        self.lab_svc.create_collection(None, "AI Concepts")
        explorer.refresh_lab_node(None)

        self.assertTrue(explorer.lab_root.text(0).startswith("🛠️"))
        col_item = explorer.lab_root.child(0)
        self.assertTrue(col_item.text(0).startswith("📁"))

        if col_item.childCount() > 0:
            board_item = col_item.child(0)
            self.assertTrue(board_item.text(0).startswith("🎨"))

    # -------------------------------------------------------------
    # 2. Business Hub Landing Page
    # -------------------------------------------------------------
    def test_3_business_panel_initialization_and_metrics(self):
        """BusinessPanel renders metrics and entry points reusing ClientService and ProjectService."""
        # Create test clients with contacts
        c1 = self.client_svc.create_client(
            name="Acme Animations",
            company="Acme Corp",
            role="Producer",
            status="Active",
        )
        c1.contacts = [ClientContact(name="Alice Smith", email="alice@acme.com")]

        c2 = self.client_svc.create_client(
            name="Beta Games",
            company="Beta Studios",
            role="Art Director",
            status="Lead",
        )
        c2.contacts = [
            ClientContact(name="Bob Jones", email="bob@beta.com"),
            ClientContact(name="Charlie Ray", email="charlie@beta.com"),
        ]

        # Create test project
        proj_dir = self.tmp_dir / "projects" / "CyberGame"
        proj_dir.mkdir(parents=True, exist_ok=True)
        self.project_svc.create_project("CyberGame", "games", str(self.tmp_dir / "projects"), "A cyberpunk adventure")

        panel = BusinessPanel(self.context)
        panel.refresh()

        # Metrics layout has 4 cards
        self.assertEqual(panel.metrics_layout.count(), 4)

        # Client preview populated
        self.assertTrue(panel.clients_preview_container.count() >= 2)

        # Project preview populated
        self.assertTrue(panel.projects_preview_container.count() >= 1)

        # Quotes and Finance roadmap cards exist with Coming Soon badges
        self.assertIsNotNone(panel.quotes_card)
        self.assertIsNotNone(panel.finance_card)

    def test_4_workspace_manager_registers_business_panel(self):
        """WorkspaceManager registers BusinessPanel and navigates to it."""
        ws_panel = WorkspacePanel()
        wm = WorkspaceManager(ws_panel, self.context)
        self.context.workspace_manager = wm

        self.assertIsInstance(wm.business_panel, BusinessPanel)
        wm.show_module("business")

        self.assertEqual(ws_panel.stack.currentWidget(), wm.business_panel)

    # -------------------------------------------------------------
    # 3. Sidebar / Splitter Width Stability
    # -------------------------------------------------------------
    def test_5_sidebar_minimum_width_enforced(self):
        """ExplorerPanel has a sensible minimum width preventing label clipping."""
        explorer = ExplorerPanel()
        self.assertGreaterEqual(explorer.minimumWidth(), 220)

    def test_6_workspace_panel_minimum_size_hint(self):
        """WorkspacePanel reports sensible minimumSizeHint avoiding background stack bloat."""
        ws_panel = WorkspacePanel()
        min_hint = ws_panel.minimumSizeHint()
        self.assertLessEqual(min_hint.width(), 400)
        self.assertGreaterEqual(min_hint.width(), 300)

    def test_7_category_navigation_preserves_sidebar_width(self):
        """Switching between Home, Business, Workbench, Clients, Assets, Knowledge preserves sidebar width."""
        w = MainWindow()
        w.resize(1400, 900)
        w.show()
        QApplication.processEvents()

        initial_explorer_w = w.explorer.width()
        self.assertGreaterEqual(initial_explorer_w, 220)

        # Navigate through all main sections
        sections = ["business", "workbench", "clients", "assets_lib", "knowledge", "home", "business"]
        for sec in sections:
            w.navigation_service.handle_navigation(sec)
            QApplication.processEvents()
            self.assertEqual(
                w.explorer.width(),
                initial_explorer_w,
                f"Explorer width changed unexpectedly when navigating to '{sec}'"
            )

    def test_8_user_manual_sidebar_resize_preserved(self):
        """User manual resize of the sidebar is preserved across category switches."""
        w = MainWindow()
        w.resize(1400, 900)
        w.show()
        QApplication.processEvents()

        # Simulate user dragging splitter to 340px
        current_sizes = w.splitter.sizes()
        desired_exp_w = 340
        remainder = sum(current_sizes) - desired_exp_w - current_sizes[2]
        w.splitter.setSizes([desired_exp_w, remainder, current_sizes[2]])
        QApplication.processEvents()

        self.assertEqual(w.explorer.width(), desired_exp_w)

        # Navigate across Home and Business
        w.navigation_service.handle_navigation("business")
        QApplication.processEvents()
        self.assertEqual(w.explorer.width(), desired_exp_w)

        w.navigation_service.handle_navigation("home")
        QApplication.processEvents()
        self.assertEqual(w.explorer.width(), desired_exp_w)

        w.navigation_service.handle_navigation("business")
        QApplication.processEvents()
        self.assertEqual(w.explorer.width(), desired_exp_w)


if __name__ == "__main__":
    unittest.main()
