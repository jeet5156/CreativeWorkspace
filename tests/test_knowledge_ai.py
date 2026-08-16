"""Unit and UI Integration tests for Knowledge AI Actions (Phase 3).

Verifies:
1. Summarize -> preview -> explicit Insert (top/bottom)
2. Generate Tags -> selectable suggestion chips -> explicit Apply
3. Key Takeaways -> preview -> explicit Insert (top/bottom)
4. AI disabled/error -> graceful UI state
5. Existing note/tags/relationships remain untouched unless explicitly applied
6. Async / non-blocking background request execution via Qt facilities
7. Mock provider in tests with zero real network calls or extra SDK dependencies
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, QCoreApplication, QEventLoop
from PySide6.QtWidgets import QApplication, QPushButton

from core.app_context import AppContext
from models.ai import AIConfig, AIRequest, AIResponse, AIUsage
from models.knowledge import KnowledgeDocument
from services.ai.providers.mock_provider import MockProvider
from services.ai_service import AIService
from services.knowledge_ai_service import KnowledgeAIService
from services.knowledge_service import KnowledgeService
from ui.panels.inspector_panel import InspectorPanel
from ui.panels.knowledge_workspace_panel import KnowledgeWorkspacePanel
from ui.widgets.knowledge_ai_assist_widget import KnowledgeAIAssistWidget

app = QApplication.instance() or QApplication([])


class TestKnowledgeAIService(unittest.TestCase):
    """Test suite covering KnowledgeAIService prompt construction, parsing, and execution."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.test_dir) / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)

        self.ai_service = AIService(config_dir=self.config_dir)
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")

        self.mock_provider = MockProvider(echo_prompt=False)
        self.ai_service.register_provider(self.mock_provider)

        self.knowledge_dir = Path(self.test_dir) / "knowledge"
        self.knowledge_service = KnowledgeService(storage_dir=self.knowledge_dir)

        self.knowledge_ai = KnowledgeAIService(self.ai_service, self.knowledge_service)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_build_requests_include_document_context(self):
        """1. Verify request builders construct structured prompts and context without modifying doc."""
        doc = KnowledgeDocument(
            id="doc_test_123",
            title="Boss Fight Design",
            content="Phase 1: Melee combat with dodge rolls.\nPhase 2: Ranged laser attacks.",
            tags=["combat", "boss"],
        )

        sum_req = self.knowledge_ai.build_summary_request(doc)
        self.assertIn("Boss Fight Design", sum_req.prompt)
        self.assertIn("Melee combat", sum_req.prompt)
        self.assertEqual(sum_req.context.document_ids, ["doc_test_123"])

        tag_req = self.knowledge_ai.build_tags_request(doc)
        self.assertIn("combat, boss", tag_req.prompt)

        takeaway_req = self.knowledge_ai.build_takeaways_request(doc)
        self.assertIn("Boss Fight Design", takeaway_req.prompt)

    def test_parse_tags_from_text(self):
        """2. Verify robust tag parsing from comma-separated, JSON, and bullet formats."""
        # Comma-separated with hashtags and mixed case
        raw_1 = "#gameplay, COMBAT, mechanics, #lore"
        tags_1 = KnowledgeAIService.parse_tags_from_text(raw_1, existing_tags=["combat"])
        self.assertEqual(tags_1, ["gameplay", "mechanics", "lore"])

        # Bullet points with markdown bold
        raw_2 = "• **multiplayer**\n• *networking*\n• server-side\n• gameplay"
        tags_2 = KnowledgeAIService.parse_tags_from_text(raw_2, existing_tags=["gameplay"])
        self.assertEqual(tags_2, ["multiplayer", "networking", "server-side"])

        # JSON array string
        raw_3 = '["vfx", "shaders", "lighting"]'
        tags_3 = KnowledgeAIService.parse_tags_from_text(raw_3, existing_tags=[])
        self.assertEqual(tags_3, ["vfx", "shaders", "lighting"])

        # Empty / whitespace
        self.assertEqual(KnowledgeAIService.parse_tags_from_text("", existing_tags=[]), [])

    def test_summarize_document_sync_and_async(self):
        """3. Verify document summarization synchronously and asynchronously via MockProvider."""
        self.mock_provider.canned_response = "A comprehensive guide to boss mechanics across multiple phases."

        doc = KnowledgeDocument(
            title="Boss Mechanics",
            content="Detailed mechanics outline.",
            tags=["boss"],
        )

        # Sync
        resp = self.knowledge_ai.summarize_document(doc)
        self.assertTrue(resp.success)
        self.assertIn("boss mechanics", resp.text)

        # Async
        async_result = {}
        loop = QEventLoop()

        def _on_finished(d, r):
            async_result["doc"] = d
            async_result["resp"] = r
            loop.quit()

        worker = self.knowledge_ai.summarize_document_async(doc, on_finished=_on_finished)
        self.assertIsNotNone(worker)
        loop.exec()

        self.assertEqual(async_result["doc"].id, doc.id)
        self.assertTrue(async_result["resp"].success)
        self.assertIn("boss mechanics", async_result["resp"].text)

    def test_generate_tags_and_filter_existing(self):
        """4. Verify tag generation returns clean suggestions excluding existing tags."""
        self.mock_provider.canned_response = "gameplay, combat, lore, mechanics, boss"

        doc = KnowledgeDocument(
            title="Boss Mechanics",
            content="Detailed mechanics outline.",
            tags=["combat", "boss"],
        )

        resp, suggested = self.knowledge_ai.generate_tags(doc)
        self.assertTrue(resp.success)
        self.assertEqual(suggested, ["gameplay", "lore", "mechanics"])
        self.assertNotIn("combat", suggested)
        self.assertNotIn("boss", suggested)

    def test_extract_key_takeaways(self):
        """5. Verify key takeaways extraction."""
        self.mock_provider.canned_response = "• Phase 1 focuses on physical tells\n• Phase 2 introduces telegraph lasers"

        doc = KnowledgeDocument(
            title="Boss Mechanics",
            content="Detailed mechanics outline.",
        )

        resp = self.knowledge_ai.extract_key_takeaways(doc)
        self.assertTrue(resp.success)
        self.assertIn("Phase 1 focuses", resp.text)

    def test_disabled_ai_graceful_handling(self):
        """6. Verify disabled AI returns non-crashing safe error."""
        self.ai_service.set_enabled(False)

        doc = KnowledgeDocument(title="Disabled AI Test", content="Content")

        resp = self.knowledge_ai.summarize_document(doc)
        self.assertFalse(resp.success)
        self.assertIn("disabled", resp.error_message.lower())


class TestKnowledgeAIUIIntegration(unittest.TestCase):
    """UI integration tests for KnowledgeAIAssistWidget within KnowledgeWorkspacePanel."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.test_dir) / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)

        self.ai_service = AIService(config_dir=self.config_dir)
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")

        self.mock_provider = MockProvider(echo_prompt=False)
        self.ai_service.register_provider(self.mock_provider)

        self.storage_dir = Path(self.test_dir) / "knowledge"
        self.knowledge_service = KnowledgeService(storage_dir=self.storage_dir)

        self.knowledge_ai = KnowledgeAIService(self.ai_service, self.knowledge_service)

        self.context = AppContext()
        self.context.ai_service = self.ai_service
        self.context.knowledge_service = self.knowledge_service
        self.context.knowledge_ai_service = self.knowledge_ai

        self.inspector = InspectorPanel()
        self.inspector.set_context(self.context)
        self.context.inspector_panel = self.inspector

        self.panel = KnowledgeWorkspacePanel(self.context)
        self.panel.document_selected.connect(self.inspector.show_knowledge_document)

        self.panel.show()
        self.inspector.show()

    def tearDown(self):
        self.panel.deleteLater()
        self.inspector.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_ai_assist_widget_initial_state(self):
        """1. Verify AI assist widget initializes cleanly and enables only when doc is active."""
        widget = self.panel.ai_assist_widget
        self.assertIsNotNone(widget)
        self.assertFalse(widget.container_frame.isVisible())

        # When no document selected, buttons are disabled
        self.panel._load_document_into_editor(None)
        self.assertFalse(widget.btn_summarize.isEnabled())

        # When note created, buttons are enabled
        self.panel.create_new_note()
        self.assertTrue(widget.btn_summarize.isEnabled())
        self.assertTrue(widget.btn_tags.isEnabled())
        self.assertTrue(widget.btn_takeaways.isEnabled())

    def test_summarize_preview_and_explicit_insert_top_bottom(self):
        """2. Verify Summarize generates preview and inserts at top/bottom only upon explicit user action."""
        self.mock_provider.canned_response = "Quick summary of level design guidelines."

        self.panel.create_new_note()
        doc_id = self.panel._current_doc_id
        self.panel.editor_content.setPlainText("Original body text.")
        self.panel._save_active_document()

        widget = self.panel.ai_assist_widget

        # Click Summarize (Async)
        widget.btn_summarize.click()

        # Let background worker run and signal delivery complete
        loop = QEventLoop()
        widget.insert_content_requested.connect(lambda *args: loop.quit())
        
        # Poll briefly for UI preview to become visible
        for _ in range(50):
            QCoreApplication.processEvents()
            if widget.text_preview_widget.isVisible():
                break

        self.assertTrue(widget.text_preview_widget.isVisible())
        self.assertIn("Quick summary", widget.text_preview_edit.toPlainText())

        # Verify note content is NOT touched before explicit insertion
        saved_doc = self.knowledge_service.get_document(doc_id)
        self.assertEqual(saved_doc.content, "Original body text.")

        # Explicitly click "Insert at Top"
        widget.btn_insert_top.click()
        QCoreApplication.processEvents()

        # Verify preview is closed and document is updated
        self.assertFalse(widget.container_frame.isVisible())
        updated_doc = self.knowledge_service.get_document(doc_id)
        self.assertTrue(updated_doc.content.startswith("## Summary\n\nQuick summary"))
        self.assertTrue(updated_doc.content.endswith("Original body text."))

    def test_key_takeaways_preview_and_explicit_insert_bottom(self):
        """3. Verify Key Takeaways generates preview and inserts at bottom upon explicit click."""
        self.mock_provider.canned_response = "• Optimize lighting passes\n• Validate shader memory"

        self.panel.create_new_note()
        doc_id = self.panel._current_doc_id
        self.panel.editor_content.setPlainText("Level 01 Render Notes.")
        self.panel._save_active_document()

        widget = self.panel.ai_assist_widget

        # Click Key Takeaways
        widget.btn_takeaways.click()

        for _ in range(50):
            QCoreApplication.processEvents()
            if widget.text_preview_widget.isVisible():
                break

        self.assertTrue(widget.text_preview_widget.isVisible())
        self.assertIn("Optimize lighting", widget.text_preview_edit.toPlainText())

        # Explicitly click "Insert at Bottom"
        widget.btn_insert_bottom.click()
        QCoreApplication.processEvents()

        updated_doc = self.knowledge_service.get_document(doc_id)
        self.assertTrue(updated_doc.content.startswith("Level 01 Render Notes."))
        self.assertIn("## Key Takeaways\n\n• Optimize lighting passes", updated_doc.content)

    def test_tag_suggestions_selection_and_explicit_apply(self):
        """4. Verify Tag suggestions are selectable and only applied when user clicks Apply."""
        self.mock_provider.canned_response = "gameplay, audio, quest, lighting"

        self.panel.create_new_note()
        doc_id = self.panel._current_doc_id
        self.panel.editor_tags.setText("initial, core")
        self.panel._save_active_document()

        widget = self.panel.ai_assist_widget

        # Click Suggest Tags
        widget.btn_tags.click()

        for _ in range(50):
            QCoreApplication.processEvents()
            if widget.tags_preview_widget.isVisible():
                break

        self.assertTrue(widget.tags_preview_widget.isVisible())
        self.assertIn("gameplay", widget._selected_suggested_tags)
        self.assertIn("audio", widget._selected_suggested_tags)

        # Verify tags NOT changed in document yet
        saved_doc = self.knowledge_service.get_document(doc_id)
        self.assertEqual(saved_doc.tags, ["initial", "core"])

        # Uncheck "audio" chip
        for i in range(widget.tags_chips_layout.count()):
            w = widget.tags_chips_layout.itemAt(i).widget()
            if isinstance(w, QPushButton) and getattr(w, "property", None) and w.property("tag_val") == "audio":
                w.click()
                break

        self.assertNotIn("audio", widget._selected_suggested_tags)
        self.assertIn("gameplay", widget._selected_suggested_tags)

        # Explicitly Apply
        widget.btn_apply_tags.click()
        QCoreApplication.processEvents()

        # Verify merged tags in service and UI
        updated_doc = self.knowledge_service.get_document(doc_id)
        self.assertIn("initial", updated_doc.tags)
        self.assertIn("core", updated_doc.tags)
        self.assertIn("gameplay", updated_doc.tags)
        self.assertIn("quest", updated_doc.tags)
        self.assertNotIn("audio", updated_doc.tags)

    def test_dismiss_leaves_document_untouched(self):
        """5. Verify Dismiss button discards AI result leaving document completely unmodified."""
        self.mock_provider.canned_response = "Temporary summary that should be dismissed."

        self.panel.create_new_note()
        doc_id = self.panel._current_doc_id
        self.panel.editor_content.setPlainText("Untouched content.")
        self.panel._save_active_document()

        widget = self.panel.ai_assist_widget
        widget.btn_summarize.click()

        for _ in range(50):
            QCoreApplication.processEvents()
            if widget.text_preview_widget.isVisible():
                break

        self.assertTrue(widget.text_preview_widget.isVisible())

        # Click Dismiss
        widget.btn_dismiss_text.click()
        QCoreApplication.processEvents()

        self.assertFalse(widget.container_frame.isVisible())
        saved_doc = self.knowledge_service.get_document(doc_id)
        self.assertEqual(saved_doc.content, "Untouched content.")

    def test_ai_disabled_shows_graceful_error_state(self):
        """6. Verify disabled AI state renders friendly alert without exceptions."""
        self.ai_service.set_enabled(False)

        self.panel.create_new_note()
        widget = self.panel.ai_assist_widget

        widget.btn_summarize.click()
        QCoreApplication.processEvents()

        self.assertTrue(widget.error_widget.isVisible())
        self.assertIn("not configured", widget.error_label.text().lower())
        self.assertTrue(widget.btn_open_settings.isVisible())

        # Dismiss error
        widget.btn_dismiss_error.click()
        self.assertFalse(widget.container_frame.isVisible())
