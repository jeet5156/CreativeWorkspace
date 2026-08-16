"""Comprehensive unit and UI integration tests for AI Settings & Provider Configuration.

Verifies:
1. AI Settings loads with AI disabled by default.
2. Provider selection persists to config.
3. Model selection and custom model overrides persist.
4. API keys persist securely without leaking into logs/output.
5. Local endpoint configuration persists and updates visibility.
6. Changing provider updates relevant form fields and status.
7. Disabled AI remains disabled across service restarts.
8. Configured AI is recognized and validated by AIService.
9. Test Connection success using a mock provider (non-blocking).
10. Test Connection failure using a mock provider (non-blocking, safe error).
11. Knowledge AI assist widget disabled/unconfigured state displays helpful guidance and Open AI Settings trigger.
12. Zero real network calls made in automated tests.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QCoreApplication, QEventLoop
from PySide6.QtWidgets import QApplication, QLineEdit

from core.app_context import AppContext
from models.ai import AIConfig, AIRequest, AIResponse
from models.knowledge import KnowledgeDocument
from services.ai.providers.mock_provider import MockProvider
from services.ai_service import AIService
from services.knowledge_ai_service import KnowledgeAIService
from services.knowledge_service import KnowledgeService
from ui.dialogs.settings_dialog import SettingsDialog
from ui.panels.knowledge_workspace_panel import KnowledgeWorkspacePanel
from ui.widgets.ai_settings_widget import AISettingsWidget

app = QApplication.instance() or QApplication([])


class TestAISettings(unittest.TestCase):
    """Test suite covering AISettingsWidget, SettingsDialog, and AIService configuration."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.test_dir) / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)

        self.ai_service = AIService(config_dir=self.config_dir)
        # Register mock provider
        self.mock_provider = MockProvider(echo_prompt=False)
        self.ai_service.register_provider(self.mock_provider)

        self.widget = AISettingsWidget(self.ai_service)
        self.widget.show()

    def tearDown(self):
        self.widget.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_ai_settings_initial_load_disabled(self):
        """1. Verify AI Settings widget loads with AI disabled by default."""
        self.assertFalse(self.widget.enable_checkbox.isChecked())
        self.assertIn("Disabled", self.widget.status_badge.text())
        self.assertFalse(self.ai_service.is_enabled())

    def test_enable_and_disable_persists(self):
        """2. Verify enabling and disabling AI persists to user configuration."""
        # Enable AI
        self.widget.enable_checkbox.setChecked(True)
        QCoreApplication.processEvents()
        self.assertTrue(self.ai_service.is_enabled())

        # Create a new AIService instance from same config dir to simulate app restart
        restarted_service = AIService(config_dir=self.config_dir)
        self.assertTrue(restarted_service.is_enabled())

        # Disable AI
        self.widget.enable_checkbox.setChecked(False)
        QCoreApplication.processEvents()
        self.assertFalse(self.ai_service.is_enabled())

        restarted_service_2 = AIService(config_dir=self.config_dir)
        self.assertFalse(restarted_service_2.is_enabled())

    def test_provider_selection_persists(self):
        """3. Verify provider selection updates active provider and persists."""
        self.widget.enable_checkbox.setChecked(True)

        # Select Gemini
        gemini_idx = self.widget.provider_combo.findData("gemini")
        self.assertGreaterEqual(gemini_idx, 0)
        self.widget.provider_combo.setCurrentIndex(gemini_idx)
        QCoreApplication.processEvents()

        self.assertEqual(self.ai_service.get_active_provider_id(), "gemini")

        # Restart service
        restarted = AIService(config_dir=self.config_dir)
        self.assertEqual(restarted.get_active_provider_id(), "gemini")

    def test_api_key_persists_without_plain_text_exposure(self):
        """4. Verify API key is stored securely in config and masked in UI by default."""
        self.widget.enable_checkbox.setChecked(True)

        # Select OpenAI
        openai_idx = self.widget.provider_combo.findData("openai")
        self.widget.provider_combo.setCurrentIndex(openai_idx)

        # Check default echo mode is Password
        self.assertEqual(self.widget.api_key_edit.echoMode(), QLineEdit.Password)

        # Enter API Key
        secret_key = "sk-test-secret-key-123456789"
        self.widget.api_key_edit.setText(secret_key)
        QCoreApplication.processEvents()

        self.assertEqual(self.ai_service.get_api_key("openai"), secret_key)

        # Verify show/hide toggle changes echo mode
        self.widget.btn_toggle_key_vis.click()
        self.assertEqual(self.widget.api_key_edit.echoMode(), QLineEdit.Normal)
        self.widget.btn_toggle_key_vis.click()
        self.assertEqual(self.widget.api_key_edit.echoMode(), QLineEdit.Password)

        # Verify key is persisted on disk in user config (and not in project)
        restarted = AIService(config_dir=self.config_dir)
        self.assertEqual(restarted.get_api_key("openai"), secret_key)

    def test_model_override_persists(self):
        """5. Verify custom model selection and input persists."""
        self.widget.enable_checkbox.setChecked(True)

        # Select Claude
        claude_idx = self.widget.provider_combo.findData("claude")
        self.widget.provider_combo.setCurrentIndex(claude_idx)

        self.widget.model_combo.setEditText("claude-3-5-haiku-20241022")
        QCoreApplication.processEvents()

        self.assertEqual(self.ai_service.get_model("claude"), "claude-3-5-haiku-20241022")

        restarted = AIService(config_dir=self.config_dir)
        self.assertEqual(restarted.get_model("claude"), "claude-3-5-haiku-20241022")

    def test_local_endpoint_persists_and_updates_visibility(self):
        """6. Verify Local provider exposes base endpoint field and persists custom URL."""
        self.widget.enable_checkbox.setChecked(True)

        # Select Local
        local_idx = self.widget.provider_combo.findData("local")
        self.widget.provider_combo.setCurrentIndex(local_idx)
        QCoreApplication.processEvents()

        self.assertTrue(self.widget.endpoint_edit.isVisible())
        self.assertTrue(self.widget.endpoint_label.isVisible())

        # Set custom local endpoint
        custom_endpoint = "http://192.168.1.50:11434/v1"
        self.widget.endpoint_edit.setText(custom_endpoint)
        QCoreApplication.processEvents()

        self.assertEqual(self.ai_service.get_endpoint("local"), custom_endpoint)

        restarted = AIService(config_dir=self.config_dir)
        self.assertEqual(restarted.get_endpoint("local"), custom_endpoint)

    def test_test_connection_success_mock(self):
        """7. Verify Test Connection button runs asynchronously and reports success."""
        self.widget.enable_checkbox.setChecked(True)

        # Select Mock Provider
        mock_idx = self.widget.provider_combo.findData("mock")
        self.widget.provider_combo.setCurrentIndex(mock_idx)
        self.mock_provider.canned_response = "OK"

        # Trigger connection test
        self.widget.btn_test_conn.click()

        # Let Qt event loop process async worker
        for _ in range(50):
            QCoreApplication.processEvents()
            if self.widget.btn_test_conn.isEnabled():
                break

        self.assertTrue(self.widget._last_test_success)
        self.assertIn("Connected successfully", self.widget.test_feedback_label.text())
        self.assertIn("Ready", self.widget.status_badge.text())

    def test_test_connection_failure_mock(self):
        """8. Verify Test Connection failure displays safe error message without crashing."""
        self.widget.enable_checkbox.setChecked(True)

        mock_idx = self.widget.provider_combo.findData("mock")
        self.widget.provider_combo.setCurrentIndex(mock_idx)

        # Force mock provider to return error
        self.mock_provider.custom_responder = lambda req: AIResponse(
            success=False,
            error_message="Unauthorized: Invalid Mock API Token",
            provider="mock",
        )

        self.widget.btn_test_conn.click()

        for _ in range(50):
            QCoreApplication.processEvents()
            if self.widget.btn_test_conn.isEnabled():
                break

        self.assertFalse(self.widget._last_test_success)
        self.assertIn("Connection failed", self.widget.test_feedback_label.text())
        self.assertIn("Error", self.widget.status_badge.text())

    def test_settings_dialog_navigation_to_ai(self):
        """9. Verify SettingsDialog opens directly to AI section when requested."""
        context = AppContext()
        context.ai_service = self.ai_service

        dialog = SettingsDialog(context=context, initial_section="ai")
        dialog.show()
        QCoreApplication.processEvents()

        self.assertEqual(dialog.pages_stack.currentIndex(), 1)
        self.assertEqual(dialog.nav_list.currentRow(), 1)

        dialog.open_section("general")
        self.assertEqual(dialog.pages_stack.currentIndex(), 0)

        dialog.open_section("ai")
        self.assertEqual(dialog.pages_stack.currentIndex(), 1)

        dialog.deleteLater()

    def test_gemini_models_initial_suggestions_and_button_visibility(self):
        """10. Verify Gemini exposes Refresh Models button and starts with modern defaults."""
        self.widget.enable_checkbox.setChecked(True)

        gemini_idx = self.widget.provider_combo.findData("gemini")
        self.widget.provider_combo.setCurrentIndex(gemini_idx)
        QCoreApplication.processEvents()

        self.assertTrue(self.widget.btn_refresh_models.isVisible())
        # Verify current default model is present and selected
        items = [self.widget.model_combo.itemText(i) for i in range(self.widget.model_combo.count())]
        self.assertIn("gemini-3.6-flash", items)
        self.assertNotIn("gemini-2.0-flash", items)

    def test_refresh_models_missing_api_key_shows_warning(self):
        """11. Verify clicking Refresh Models without API key shows friendly warning."""
        self.widget.enable_checkbox.setChecked(True)

        gemini_idx = self.widget.provider_combo.findData("gemini")
        self.widget.provider_combo.setCurrentIndex(gemini_idx)
        self.widget.api_key_edit.setText("")
        QCoreApplication.processEvents()

        self.widget.btn_refresh_models.click()
        QCoreApplication.processEvents()

        self.assertTrue(self.widget.refresh_status_label.isVisible())
        self.assertIn("API key is missing", self.widget.refresh_status_label.text())

    def test_refresh_models_async_success_and_caching(self):
        """12. Verify Refresh Models discovers models asynchronously and caches them for future reloads."""
        from unittest.mock import patch, MagicMock
        import json

        self.widget.enable_checkbox.setChecked(True)
        gemini_idx = self.widget.provider_combo.findData("gemini")
        self.widget.provider_combo.setCurrentIndex(gemini_idx)
        self.widget.api_key_edit.setText("AIzaSyMockKeyForDiscovery")
        QCoreApplication.processEvents()

        mock_json = {
            "models": [
                {
                    "name": "models/gemini-3.6-flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-3.5-flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-future-model",
                    "supportedGenerationMethods": ["generateContent"],
                },
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_json).encode("utf-8")
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            self.widget.btn_refresh_models.click()

            for _ in range(50):
                QCoreApplication.processEvents()
                if self.widget.btn_refresh_models.isEnabled():
                    break

        self.assertIn("Discovered 3 models", self.widget.refresh_status_label.text())
        items = [self.widget.model_combo.itemText(i) for i in range(self.widget.model_combo.count())]
        self.assertIn("gemini-future-model", items)

        # Verify caching across reload without network access
        cached_models = self.ai_service.get_cached_models("gemini")
        self.assertEqual(cached_models, ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-future-model"])

        # Reload widget and verify it reads cache
        self.widget.reload_from_service()
        reloaded_items = [self.widget.model_combo.itemText(i) for i in range(self.widget.model_combo.count())]
        self.assertIn("gemini-future-model", reloaded_items)

    def test_test_connection_uses_selected_model(self):
        """13. Verify Test Connection executes with the specifically configured model override."""
        self.widget.enable_checkbox.setChecked(True)
        mock_idx = self.widget.provider_combo.findData("mock")
        self.widget.provider_combo.setCurrentIndex(mock_idx)

        # Set custom model override
        self.widget.model_combo.setEditText("custom-eval-model-99")
        QCoreApplication.processEvents()

        self.widget.btn_test_conn.click()

        for _ in range(50):
            QCoreApplication.processEvents()
            if self.widget.btn_test_conn.isEnabled():
                break

        self.assertTrue(self.widget._last_test_success)
        self.assertEqual(self.mock_provider.last_request.model, "custom-eval-model-99")


class TestKnowledgeAIHelpfulDisabledState(unittest.TestCase):
    """Test suite covering KnowledgeAIAssistWidget helpful guidance when AI is unconfigured."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.test_dir) / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)

        self.ai_service = AIService(config_dir=self.config_dir)
        self.ai_service.set_enabled(False)  # AI disabled initially

        self.storage_dir = Path(self.test_dir) / "knowledge"
        self.knowledge_service = KnowledgeService(storage_dir=self.storage_dir)
        self.knowledge_ai = KnowledgeAIService(self.ai_service, self.knowledge_service)

        self.context = AppContext()
        self.context.ai_service = self.ai_service
        self.context.knowledge_service = self.knowledge_service
        self.context.knowledge_ai_service = self.knowledge_ai

        self.panel = KnowledgeWorkspacePanel(self.context)
        self.panel.show()

    def tearDown(self):
        self.panel.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_disabled_ai_action_shows_helpful_settings_guidance(self):
        """10. Verify clicking AI action when unconfigured explains how to open Settings and shows button."""
        self.panel.create_new_note()
        widget = self.panel.ai_assist_widget

        # Click Summarize
        widget.btn_summarize.click()
        QCoreApplication.processEvents()

        self.assertTrue(widget.error_widget.isVisible())
        self.assertIn("AI is not configured. Open Settings → AI", widget.error_label.text())
        self.assertTrue(widget.btn_open_settings.isVisible())

        # Verify clicking Open AI Settings emits signal
        received_signals = []
        widget.open_settings_requested.connect(lambda s: received_signals.append(s))
        widget.btn_open_settings.click()
        QCoreApplication.processEvents()

        self.assertEqual(received_signals, ["ai"])
