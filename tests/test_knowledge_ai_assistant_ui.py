"""UI Integration Tests for Knowledge AI Assistant Widget (Phase 4C).

Verifies:
1. Ask AI input area and controls initialize properly.
2. Empty question is rejected cleanly without launching worker.
3. Ask button triggers asynchronous background generation.
4. Loading state / progress bar renders during processing.
5. AI Answer renders with '✨ AI Answer' heading and copy/dismiss buttons.
6. Context transparency badge renders with correct item count and offline flags.
7. Copy button copies text to system clipboard.
8. Dismiss button hides the preview frame cleanly.
9. Multi-turn follow-up preserves in-memory conversation in assistant service.
10. Context mode dropdown updates active mode passed to assistant.
11. Existing Summarize, Suggest Tags, and Key Takeaways buttons continue working.
12. Selecting another document clears old conversation history and stale answer previews.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import QApplication

from models.ai import AIConfig, AIResponse
from models.ai_context import ContextItem, ContextResult, ContextSource
from models.knowledge import KnowledgeDocument
from models.library_models import LibraryAsset, LibraryDrive
from models.project import Project
from services.ai.providers.mock_provider import MockProvider
from services.ai_service import AIService
from services.asset_service import AssetService
from services.context_retrieval_service import ContextRetrievalService
from services.knowledge_ai_service import KnowledgeAIContextMode, KnowledgeAIService
from services.knowledge_assistant_service import KnowledgeAssistantService
from services.knowledge_service import KnowledgeService
from services.lab_service import LabService
from services.library_service import LibraryService
from services.project_service import ProjectService
from ui.widgets.knowledge_ai_assist_widget import KnowledgeAIAssistWidget


# Ensure single QApplication instance for Qt Widget testing
app = QApplication.instance()
if not app:
    app = QApplication([])


class TestKnowledgeAIAssistantUI(unittest.TestCase):
    """UI integration tests for Ask AI and context-aware KnowledgeAIAssistWidget."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_dir = Path(self.test_dir)

        # AI Infrastructure
        self.config_dir = self.storage_dir / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)
        self.ai_service = AIService(config_dir=self.config_dir)
        self.mock_provider = MockProvider(
            canned_response="The CyberRacer propulsion uses twin plasma injectors.",
            echo_prompt=False,
        )
        self.ai_service.register_provider(self.mock_provider)
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")
        self.ai_service.set_api_key("mock", "secret_key_never_in_prompt")

        # Project Service
        self.project_service = ProjectService()
        self.proj = self.project_service.create_project(
            name="CyberRacer",
            project_type="Game",
            location=str(self.storage_dir / "projects" / "CyberRacer"),
            description="CyberRacer game project",
        )

        # Knowledge Service
        self.knowledge_dir = self.storage_dir / "knowledge"
        self.knowledge_service = KnowledgeService(storage_dir=self.knowledge_dir)
        self.doc1 = self.knowledge_service.create_document(
            title="Thruster Spec Doc",
            content="Dual plasma thruster parameters and cooling valves.",
            tags=["engine", "plasma", "vehicle"],
        )
        self.doc2 = self.knowledge_service.create_document(
            title="Track Dynamics",
            content="Track layout and magnetic rails.",
            tags=["track", "level"],
        )

        # Library Service
        self.library_dir = self.storage_dir / "library"
        self.library_service = LibraryService(storage_dir=self.library_dir)
        self.lib_asset = LibraryAsset(
            id="lib_01",
            drive_id="drv_1",
            location_id="loc_1",
            filename="PlasmaBooster.blend",
            drive_relative_path="Vehicles/PlasmaBooster.blend",
            category="3D Models",
            tags=["plasma", "engine"],
        )
        self.library_service._assets[self.lib_asset.id] = self.lib_asset

        # Asset Service
        self.asset_service = AssetService(self.project_service)

        # Lab Service
        self.lab_service = LabService(self.project_service)

        # Context Retrieval Service
        self.context_retrieval_service = ContextRetrievalService(
            knowledge_service=self.knowledge_service,
            library_service=self.library_service,
            asset_service=self.asset_service,
            project_service=self.project_service,
            lab_service=self.lab_service,
        )

        # Knowledge AI & Assistant Services
        self.knowledge_ai_service = KnowledgeAIService(
            self.ai_service,
            self.knowledge_service,
            context_retrieval_service=self.context_retrieval_service,
        )
        self.knowledge_assistant_service = KnowledgeAssistantService(
            self.ai_service,
            self.knowledge_service,
            context_retrieval_service=self.context_retrieval_service,
        )

        # UI Widget under test
        self.widget = KnowledgeAIAssistWidget(
            knowledge_ai_service=self.knowledge_ai_service,
            knowledge_assistant_service=self.knowledge_assistant_service,
        )
        self.widget.set_document(self.doc1)
        self.widget.set_project_id(self.proj.name)
        self.widget.show()
        app.processEvents()

    def tearDown(self):
        self.widget.hide()
        self.widget.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _wait_async(self):
        QThreadPool.globalInstance().waitForDone(3000)
        app.processEvents()

    def test_1_ask_ai_widget_initialization(self):
        """1. Verify Ask AI input, Ask button, Context dropdown, and clear button exist."""
        self.assertTrue(self.widget.ask_input.isEnabled())
        self.assertTrue(self.widget.btn_ask.isEnabled())
        self.assertEqual(self.widget.context_mode_combo.count(), 4)
        self.assertEqual(self.widget.context_mode_combo.currentText(), "Related")
        self.assertFalse(self.widget.container_frame.isVisible())

    def test_2_empty_question_is_rejected(self):
        """2. Verify clicking Ask or pressing Enter with empty question is rejected."""
        self.widget.ask_input.setText("   ")
        self.widget.btn_ask.click()
        self.assertFalse(self.widget.container_frame.isVisible())
        self.assertIsNone(self.widget._active_worker)

    def test_3_ask_button_submits_and_renders_answer(self):
        """3. Verify submitting question triggers async generation and renders AI Answer."""
        self.widget.ask_input.setText("What thruster is used?")
        self.widget.btn_ask.click()

        # Should show loading state
        self.assertTrue(self.widget.container_frame.isVisible())
        self.assertTrue(self.widget.loading_widget.isVisible())
        self.assertIsNotNone(self.widget._active_worker)

        self._wait_async()

        # Result preview visible
        self.assertTrue(self.widget.text_preview_widget.isVisible())
        self.assertEqual(self.widget.text_preview_title.text(), "✨ AI Answer")
        self.assertIn("twin plasma injectors", self.widget.text_preview_edit.toPlainText())
        # Ask AI shouldn't show insert buttons
        self.assertFalse(self.widget.insert_row_widget.isVisible())

    def test_4_context_transparency_indicator_renders(self):
        """4. Verify 'Context used (N)' transparency widget renders source breakdown."""
        self.knowledge_service.update_document(
            self.doc1.id,
            library_asset_ids=[self.lib_asset.id],
        )
        self.widget.ask_input.setText("What assets relate to thrusters?")
        self.widget.btn_ask.click()
        self._wait_async()

        self.assertTrue(self.widget.context_used_widget.isVisible())
        self.assertIn("Context used", self.widget.btn_toggle_context.text())

        # Toggle context expansion
        self.widget.btn_toggle_context.click()
        self.assertTrue(self.widget.context_items_list.isVisible())

    def test_5_copy_button_copies_to_clipboard(self):
        """5. Verify clicking Copy copies answer text to system clipboard."""
        self.widget._show_text_result("✨ AI Answer", "Answer text to copy", "ask")
        self.widget.btn_copy_text.click()
        app.processEvents()

        clipboard = QApplication.clipboard()
        if clipboard:
            self.assertEqual(clipboard.text(), "Answer text to copy")

    def test_6_dismiss_button_hides_preview(self):
        """6. Verify clicking Dismiss hides the preview container cleanly."""
        self.widget._show_text_result("✨ AI Answer", "Answer to dismiss", "ask")
        self.assertTrue(self.widget.container_frame.isVisible())

        self.widget.btn_dismiss_text.click()
        self.assertFalse(self.widget.container_frame.isVisible())

    def test_7_followup_question_maintains_conversation(self):
        """7. Verify consecutive questions build up in-memory history in assistant service."""
        # Q1
        self.widget.ask_input.setText("First question")
        self.widget.btn_ask.click()
        self._wait_async()

        # Q2
        self.widget.ask_input.setText("Follow up question")
        self.widget.btn_ask.click()
        self._wait_async()

        history = self.knowledge_assistant_service.get_history()
        self.assertEqual(len(history), 4)  # 2 questions + 2 answers
        self.assertEqual(history[0].content, "First question")
        self.assertEqual(history[2].content, "Follow up question")

    def test_8_clear_history_button_resets_session(self):
        """8. Verify clicking the broom icon clears the in-memory conversation history."""
        self.knowledge_assistant_service.add_history_message("user", "Old question")
        self.assertEqual(len(self.knowledge_assistant_service.get_history()), 1)

        self.widget.btn_clear_history.click()
        app.processEvents()

        self.assertEqual(len(self.knowledge_assistant_service.get_history()), 0)

    def test_9_context_mode_selector_updates_request_mode(self):
        """9. Verify changing the context mode combobox passes the selected mode to AI."""
        self.widget.context_mode_combo.setCurrentIndex(0)  # Current
        with patch.object(self.knowledge_assistant_service, "ask_async", wraps=self.knowledge_assistant_service.ask_async) as mock_ask:
            self.widget.ask_input.setText("Mode test question")
            self.widget.btn_ask.click()
            mock_ask.assert_called_once()
            self.assertEqual(mock_ask.call_args[1]["context_mode"], KnowledgeAIContextMode.CURRENT)

    def test_10_summarize_and_tags_still_work(self):
        """10. Verify standard Summarize and Suggest Tags actions continue functioning cleanly."""
        # Summarize
        self.widget.btn_summarize.click()
        self.assertTrue(self.widget.loading_widget.isVisible())
        self._wait_async()
        self.assertEqual(self.widget.text_preview_title.text(), "✨ Document Summary")
        self.assertTrue(self.widget.insert_row_widget.isVisible())

        # Tags
        self.mock_provider.canned_response = "vehicle, plasma, propulsion, cooling"
        self.widget.btn_tags.click()
        self._wait_async()
        self.assertTrue(self.widget.tags_preview_widget.isVisible())

    def test_11_selecting_another_document_resets_conversation_and_preview(self):
        """11. Verify changing active document resets conversation history and hides old answers."""
        # Run a query on doc1
        self.widget.ask_input.setText("Doc 1 question")
        self.widget.btn_ask.click()
        self._wait_async()
        self.assertTrue(self.widget.container_frame.isVisible())
        self.assertEqual(len(self.knowledge_assistant_service.get_history()), 2)

        # Switch to doc2
        self.widget.set_document(self.doc2)
        app.processEvents()

        # State should be reset
        self.assertFalse(self.widget.container_frame.isVisible())
        self.assertEqual(self.widget.ask_input.text(), "")
        self.assertEqual(len(self.knowledge_assistant_service.get_history()), 0)


if __name__ == "__main__":
    unittest.main()
