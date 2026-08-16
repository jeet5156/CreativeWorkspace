"""UI and Integration tests for ProjectAIAssistantWidget and Dashboard integration (Phase 5B)."""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from core.app_context import AppContext
from models.project import Project
from models.project_context import (
    ProjectContext,
    ProjectAssetSummary,
    ProjectLibrarySummary,
    ProjectKnowledgeSummary,
    ProjectLabSummary,
    ProjectAvailabilitySummary,
)
from models.project_assistant import (
    ProjectSourceType,
    TraceableSourceItem,
    ProjectAssistantResponse,
)
from services.ai_service import AIService
from services.project_assistant_service import ProjectAssistantService
from services.project_context_service import ProjectContextService
from ui.widgets.project_ai_assistant_widget import (
    ProjectAIAssistantWidget,
    ClickableSourceChip,
)
from ui.panels.dashboard_panel import DashboardPanel

# Ensure single global QApplication
app = QApplication.instance() or QApplication([])


class TestProjectAssistantUI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_proj_asst_ui_")

        # Context & Services setup
        self.context = AppContext()
        self.ai_service = AIService(config_dir=Path(self.temp_dir) / "ai_cfg")
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")
        self.context.ai_service = self.ai_service

        self.project_context_service = MagicMock(spec=ProjectContextService)
        self.context.project_context_service = self.project_context_service

        self.sample_context = ProjectContext(
            project_name="CyberRacer",
            project_path=str(Path(self.temp_dir) / "CyberRacer"),
            project_type="game",
            metadata={
                "status": "active",
                "priority": "high",
                "description": "Futuristic Cyber Racer game.",
            },
            asset_summary=ProjectAssetSummary(
                total_assets=3,
                version_groups=[{"logical_name": "Hero_Car", "latest": "v002", "versions": ["v001", "v002"]}],
            ),
            library_summary=ProjectLibrarySummary(
                total_linked_assets=2,
                available_assets=1,
                offline_assets=1,
                linked_assets=[{
                    "id": "off_1",
                    "filename": "City_Signs.fbx",
                    "drive_id": "DRIVE_X",
                    "is_online": False,
                    "availability_status": "offline",
                }],
            ),
            availability_summary=ProjectAvailabilitySummary(
                online_library_assets=1,
                offline_library_assets=1,
                missing_library_assets=0,
                possibly_changed_assets=0,
            ),
            knowledge_summary=ProjectKnowledgeSummary(
                total_notes=1,
                recent_notes=[{"id": "doc_1", "title": "Game Lore", "is_favorite": True}],
            ),
            lab_summary=ProjectLabSummary(
                total_boards=1,
                recent_boards=[{"id": "b_1", "name": "Level Design", "node_count": 3}],
                task_status={"total": 2, "completed": 1, "pending": 1},
            ),
        )
        self.project_context_service.get_project_context.return_value = self.sample_context

        self.assistant_service = ProjectAssistantService(
            ai_service=self.ai_service,
            project_context_service=self.project_context_service,
        )
        self.context.project_assistant_service = self.assistant_service

        self.widget = ProjectAIAssistantWidget(assistant_service=self.assistant_service)
        self.widget.set_project(self.sample_context)

    def tearDown(self):
        self.widget.deleteLater()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Widget Creation & Status
    # -------------------------------------------------------------------------

    def test_01_widget_creation_and_status(self):
        """Test widget initializes cleanly with ready status and quick suggestions."""
        self.assertEqual(self.widget.status_badge.text(), "🟢 AI Ready")
        self.assertTrue(self.widget.ask_btn.isEnabled())
        self.assertGreaterEqual(self.widget.suggestions_layout.count(), 1)

    # -------------------------------------------------------------------------
    # 2. Synchronous/Simulated Response & Message Bubbles
    # -------------------------------------------------------------------------

    def test_02_rendering_messages_and_traceable_sources(self):
        """Test rendering message bubble with traceable source chips."""
        sources = [
            TraceableSourceItem(
                source_type=ProjectSourceType.PROJECT.value,
                title="Project: CyberRacer",
                target_path="/projects/CyberRacer",
                badge="Game",
            ),
            TraceableSourceItem(
                source_type=ProjectSourceType.LIBRARY_ASSET.value,
                title="City_Signs.fbx",
                target_id="off_1",
                status="offline",
                badge="Offline (DRIVE_X)",
            ),
        ]

        self.widget._render_message_bubble(
            role="assistant",
            content="The project has 1 offline asset City_Signs.fbx.",
            sources=sources,
        )

        # Bubble was added to chat layout
        self.assertGreaterEqual(self.widget.chat_layout.count(), 2)

    # -------------------------------------------------------------------------
    # 3. Source Chip Click Navigation Signal
    # -------------------------------------------------------------------------

    def test_03_source_chip_click_emits_signal(self):
        """Test clicking a source chip triggers source_clicked signal with metadata."""
        source = TraceableSourceItem(
            source_type=ProjectSourceType.KNOWLEDGE.value,
            title="Game Lore",
            target_id="doc_1",
            badge="⭐ Favorite",
            metadata={"tags": ["lore"]},
        )
        chip = ClickableSourceChip(source)

        signal_mock = MagicMock()
        self.widget.source_clicked.connect(signal_mock)
        chip.clicked.connect(self.widget._on_source_chip_clicked)

        # Simulate left click
        chip.clicked.emit(source.source_type, source.target_id, source.metadata)
        signal_mock.assert_called_once_with("knowledge", "doc_1", {"tags": ["lore"]})

    # -------------------------------------------------------------------------
    # 4. Quick Suggestion Button Interaction
    # -------------------------------------------------------------------------

    def test_04_quick_suggestion_populates_question(self):
        """Test clicking a suggestion chip initiates question asking."""
        with patch.object(self.widget, "ask_question") as mock_ask:
            # First item in suggestions_layout
            first_item = self.widget.suggestions_layout.itemAt(0)
            if first_item and first_item.widget():
                btn = first_item.widget()
                btn.click()
                mock_ask.assert_called_once()

    # -------------------------------------------------------------------------
    # 5. Clear History Button
    # -------------------------------------------------------------------------

    def test_05_clear_history(self):
        """Test clear button resets messages and service history."""
        self.assistant_service.add_history_message("user", "Hello")
        self.assertEqual(len(self.assistant_service.get_history()), 1)

        self.widget.clear_btn.click()
        self.assertEqual(len(self.assistant_service.get_history()), 0)

    # -------------------------------------------------------------------------
    # 6. DashboardPanel Integration
    # -------------------------------------------------------------------------

    def test_06_dashboard_panel_embeds_assistant(self):
        """Test DashboardPanel contains ProjectAIAssistantWidget and forwards navigation."""
        panel = DashboardPanel()
        panel.set_context(self.context)
        panel.show_project(self.sample_context)

        self.assertTrue(hasattr(panel, "ai_assistant_widget"))
        self.assertIsNotNone(panel.ai_assistant_widget)

        # Test source click routing to knowledge
        with patch.object(panel, "_on_knowledge_item_clicked") as mock_k:
            panel._on_assistant_source_clicked("knowledge", "doc_1", {})
            mock_k.assert_called_with("doc_1")

        # Test source click routing to lab board
        with patch.object(panel, "_on_lab_board_clicked") as mock_l:
            panel._on_assistant_source_clicked("lab_board", "Level Design", {})
            mock_l.assert_called_with("Level Design")

        panel.deleteLater()

    # -------------------------------------------------------------------------
    # 7. Quick Action Buttons
    # -------------------------------------------------------------------------

    def test_07_quick_action_buttons(self):
        """Test quick action buttons trigger structured question asking."""
        with patch.object(self.widget, "ask_question") as mock_ask:
            self.widget.btn_act_summary.click()
            mock_ask.assert_called()

        with patch.object(self.widget, "ask_question") as mock_ask:
            self.widget.btn_act_status.click()
            mock_ask.assert_called()

        with patch.object(self.widget, "ask_question") as mock_ask:
            self.widget.btn_act_attention.click()
            mock_ask.assert_called()

        with patch.object(self.widget, "ask_question") as mock_ask:
            self.widget.btn_act_dependencies.click()
            mock_ask.assert_called()

        with patch.object(self.widget, "ask_question") as mock_ask:
            self.widget.btn_act_knowledge.click()
            mock_ask.assert_called()

        with patch.object(self.widget, "ask_question") as mock_ask:
            self.widget.btn_act_lab.click()
            mock_ask.assert_called()

    # -------------------------------------------------------------------------
    # 8. Resizable Output Area Presets
    # -------------------------------------------------------------------------

    def test_08_resize_height_presets(self):
        """Test cycling resize button changes conversation area minimum height."""
        initial_h = self.widget.scroll_area.minimumHeight()
        self.assertEqual(initial_h, 320)

        self.widget.resize_btn.click()
        self.assertEqual(self.widget.scroll_area.minimumHeight(), 480)
        self.assertIn("Expanded", self.widget.resize_btn.text())

        self.widget.resize_btn.click()
        self.assertEqual(self.widget.scroll_area.minimumHeight(), 680)
        self.assertIn("Tall", self.widget.resize_btn.text())

        self.widget.resize_btn.click()
        self.assertEqual(self.widget.scroll_area.minimumHeight(), 320)

    # -------------------------------------------------------------------------
    # 9. Context Transparency Viewer
    # -------------------------------------------------------------------------

    def test_09_context_viewer_dialog(self):
        """Test context viewer dialog formats structured facts."""
        facts = self.assistant_service.format_project_context_prompt(self.sample_context)
        self.assertIn("CyberRacer", facts)
        self.assertIn("Hero_Car", facts)
        self.assertIn("City_Signs.fbx", facts)
        self.assertIn("Level Design", facts)

    # -------------------------------------------------------------------------
    # 10. Copy and Disabled AI State
    # -------------------------------------------------------------------------

    def test_10_copy_and_disabled_state(self):
        """Test copy action and disabled state UI updates."""
        self.widget._last_assistant_answer = "Sample response text"
        self.widget._copy_latest_response()

        self.ai_service.set_enabled(False)
        self.widget._update_ai_status()
        self.assertFalse(self.widget.ask_btn.isEnabled())
        self.assertFalse(self.widget.btn_act_summary.isEnabled())
        self.assertIn("Disabled", self.widget.status_badge.text())


if __name__ == "__main__":
    unittest.main()
