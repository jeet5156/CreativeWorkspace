"""UI and Integration tests for Project DashboardPanel (Phase 5A)."""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.app_context import AppContext
from models.project import Project
from models.project_context import ProjectContext
from models.library_models import AssetAvailability
from ui.panels.dashboard_panel import DashboardPanel

# Ensure single global QApplication
app = QApplication.instance() or QApplication([])


class TestProjectDashboard(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_proj_dash_")
        self.proj_dir = Path(self.temp_dir) / "CyberRacer"
        self.proj_dir.mkdir(parents=True, exist_ok=True)

        self.context = AppContext()
        # Ensure test isolation for knowledge & library services
        from services.knowledge_service import KnowledgeService
        from services.library_service import LibraryService
        self.context.knowledge_service = KnowledgeService(storage_dir=Path(self.temp_dir) / "know")
        self.context.library_service = LibraryService(storage_dir=Path(self.temp_dir) / "lib")
        from services.project_context_service import ProjectContextService
        self.context.project_context_service = ProjectContextService(
            context=self.context,
            project_service=self.context.project_service,
            asset_service=self.context.asset_service,
            library_service=self.context.library_service,
            knowledge_service=self.context.knowledge_service,
            lab_service=self.context.lab_service,
        )

        self.project = self.context.project_service.create_project(
            name="CyberRacer",
            project_type="game",
            location=str(self.temp_dir),
            description="Futuristic Cyber Racer game.",
        )

        self.panel = DashboardPanel()
        self.panel.set_context(self.context)

    def tearDown(self):
        self.panel.clear()
        self.panel.deleteLater()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Dashboard Creation & Initial State
    # -------------------------------------------------------------------------

    def test_01_dashboard_creation_and_title(self):
        """Test dashboard panel creates cleanly and displays project title and metadata."""
        self.panel.show_project(self.project)
        self.assertEqual(self.panel.name_value.text(), "CyberRacer")
        self.assertIn("Game", self.panel.type_value.text())
        self.assertEqual(self.panel.status_badge.text(), "Active")
        self.assertEqual(self.panel.priority_badge.text(), "Medium")

    # -------------------------------------------------------------------------
    # 2. Metric Summary Counts
    # -------------------------------------------------------------------------

    def test_02_summary_counts_rendered(self):
        """Test high-level metric cards render accurate counts."""
        self.panel.show_project(self.project)

        # Add assets
        (self.proj_dir / "Assets" / "model.fbx").write_text("model")
        (self.proj_dir / "Assets" / "texture.png").write_text("tex")
        self.context.asset_service.rebuild_index(self.project, force=True)

        # Add knowledge note
        doc = self.context.knowledge_service.create_document(title="Lore Bible", content="Cyberpunk city lore")
        self.context.knowledge_service.add_project_relationship(doc.id, "CyberRacer")

        # Add lab board
        self.context.lab_service.create_board(self.project, "Level Design")

        self.panel.refresh()

        self.assertEqual(self.panel.card_assets.count_lbl.text(), "2")
        self.assertEqual(self.panel.card_knowledge.count_lbl.text(), "1")
        self.assertGreaterEqual(int(self.panel.card_lab.count_lbl.text()), 1)

    # -------------------------------------------------------------------------
    # 3. Library Availability Breakdown Cards
    # -------------------------------------------------------------------------

    def test_03_library_availability_cards(self):
        """Test library availability cards render status counts correctly."""
        self.panel.show_project(self.project)

        ref_entry = {
            "id": "lib_ref_1",
            "filename": "Hero_Vehicle.fbx",
            "category": "References",
            "is_library_reference": True,
            "library_asset_id": "asset_hero_veh",
            "drive_id": "portable_drive_1",
            "drive_relative_path": "assets/Hero_Vehicle.fbx",
        }
        self.context.asset_service._indices[self.project.location] = [ref_entry]
        self.context.asset_service._save_index(self.project)

        # Mock library availability as offline
        if self.context.library_service:
            self.context.library_service.get_asset = MagicMock(return_value=MagicMock(id="asset_hero_veh", drive_id="portable_drive_1"))
            self.context.library_service.get_asset_availability = MagicMock(return_value=AssetAvailability.OFFLINE)

        self.panel.refresh()

        self.assertEqual(self.panel.availability_card.item_offline.badge_lbl.text(), "1")
        self.assertEqual(self.panel.availability_card.item_available.badge_lbl.text(), "0")

    # -------------------------------------------------------------------------
    # 4. Recent Knowledge and Lab Sections
    # -------------------------------------------------------------------------

    def test_04_recent_knowledge_and_lab_sections(self):
        """Test recent knowledge documents and lab boards are rendered in their sections."""
        self.panel.show_project(self.project)

        doc = self.context.knowledge_service.create_document(title="Character Concept", content="Hero backstory")
        self.context.knowledge_service.add_project_relationship(doc.id, "CyberRacer")
        self.context.lab_service.create_board(self.project, "Art Direction")

        self.panel.refresh()

        # Knowledge list has child widgets
        self.assertGreaterEqual(self.panel.knowledge_list_layout.count(), 1)
        # Lab list has child widgets
        self.assertGreaterEqual(self.panel.lab_list_layout.count(), 1)

    # -------------------------------------------------------------------------
    # 5. Empty States
    # -------------------------------------------------------------------------

    def test_05_empty_states_handled(self):
        """Test empty project renders safe placeholders without error."""
        empty_p = self.context.project_service.create_project(
            name="EmptyP",
            project_type="general",
            location=str(self.temp_dir),
            description="",
        )
        self.panel.show_project(empty_p)

        self.assertEqual(self.panel.card_assets.count_lbl.text(), "0")
        self.assertEqual(self.panel.card_knowledge.count_lbl.text(), "0")
        self.assertEqual(self.panel.card_library.count_lbl.text(), "0")

    # -------------------------------------------------------------------------
    # 6. Manual Refresh
    # -------------------------------------------------------------------------

    def test_06_manual_refresh(self):
        """Test manual ↻ Refresh button triggers context re-aggregation."""
        self.panel.show_project(self.project)
        self.assertEqual(self.panel.card_knowledge.count_lbl.text(), "0")

        # Create note while dashboard is open
        doc = self.context.knowledge_service.create_document(title="New Post-Open Note", content="Test")
        self.context.knowledge_service.add_project_relationship(doc.id, "CyberRacer")

        # Trigger manual refresh
        self.panel.refresh_btn.click()
        self.assertEqual(self.panel.card_knowledge.count_lbl.text(), "1")

    # -------------------------------------------------------------------------
    # 7. Project Switching & Clean State Reset
    # -------------------------------------------------------------------------

    def test_07_project_switching_leaves_no_stale_state(self):
        """Test switching projects cleanly resets all counts and prevents stale metadata."""
        # CyberRacer has 1 note
        doc = self.context.knowledge_service.create_document(title="Cyber Note", content="Test")
        self.context.knowledge_service.add_project_relationship(doc.id, "CyberRacer")
        self.panel.show_project(self.project)
        self.assertEqual(self.panel.card_knowledge.count_lbl.text(), "1")

        # Second project has 0 notes
        second_p = self.context.project_service.create_project(
            name="SecondProject",
            project_type="portfolio",
            location=str(self.temp_dir),
            description="Second project description",
        )
        self.panel.show_project(second_p)

        self.assertEqual(self.panel.name_value.text(), "SecondProject")
        self.assertEqual(self.panel.card_knowledge.count_lbl.text(), "0")
        self.assertEqual(self.panel.desc_edit.toPlainText(), "Second project description")

    # -------------------------------------------------------------------------
    # 8. Navigation Signals
    # -------------------------------------------------------------------------

    def test_08_navigation_signals_emitted(self):
        """Test clicking buttons and cards emits appropriate navigation signals."""
        self.panel.show_project(self.project)

        lab_signal_mock = MagicMock()
        self.panel.open_lab_requested.connect(lab_signal_mock)
        self.panel.open_lab_btn.click()
        lab_signal_mock.assert_called_once()

        nav_signal_mock = MagicMock()
        self.panel.navigate_section_requested.connect(nav_signal_mock)
        self.panel.card_assets.clicked.emit()
        nav_signal_mock.assert_called_with(self.project, "assets", "")


if __name__ == "__main__":
    unittest.main()
