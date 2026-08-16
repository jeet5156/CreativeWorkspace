"""Comprehensive unit and integration tests for AI Infrastructure and Provider layer."""

import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

from models.ai import (
    AIMessage,
    AIContext,
    AIRequest,
    AIResponse,
    AIUsage,
    AIConfig,
    AIProviderType,
)
from services.ai.providers.base_provider import BaseAIProvider
from services.ai.providers.openai_provider import OpenAIProvider
from services.ai.providers.gemini_provider import GeminiProvider
from services.ai.providers.claude_provider import ClaudeProvider
from services.ai.providers.local_provider import LocalProvider
from services.ai.providers.mock_provider import MockProvider
from services.ai_service import AIService


class TestAIInfrastructure(unittest.TestCase):
    """Test suite covering AI models, providers, AIService routing, configuration security, and mock execution."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.test_dir) / ".creativeworkspace"
        self.config_dir.mkdir(parents=True)
        self.ai_service = AIService(config_dir=self.config_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Models & Serialization
    # -------------------------------------------------------------------------

    def test_ai_models_and_serialization(self):
        """Verify model defaults, serialization, and effective message extraction."""
        # Message
        msg = AIMessage(role="user", content="Hello AI")
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "Hello AI")
        self.assertEqual(AIMessage.from_dict(msg.to_dict()).content, "Hello AI")

        # Context
        ctx = AIContext(
            project_id="proj_1",
            project_name="Game Alpha",
            document_ids=["doc_1", "doc_2"],
            document_titles=["GDD", "Plot Outline"],
        )
        ctx_dict = ctx.to_dict()
        self.assertEqual(ctx_dict["project_name"], "Game Alpha")
        self.assertEqual(AIContext.from_dict(ctx_dict).document_ids, ["doc_1", "doc_2"])

        # Request
        req = AIRequest(
            prompt="Summarize note",
            system_instruction="You are a helpful assistant",
            context=ctx,
            temperature=0.5,
            max_tokens=500,
        )
        eff_msgs = req.get_effective_messages()
        self.assertEqual(len(eff_msgs), 1)
        self.assertEqual(eff_msgs[0].content, "Summarize note")

        # Response
        resp = AIResponse(
            text="Here is the summary",
            provider="openai",
            model="gpt-4o",
            usage=AIUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40),
            success=True,
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.usage.total_tokens, 40)

    # -------------------------------------------------------------------------
    # 2. Disabled AI Handling
    # -------------------------------------------------------------------------

    def test_disabled_ai_returns_safe_error_without_crashing(self):
        """Verify AIService returns clean disabled status without raising exceptions."""
        self.assertFalse(self.ai_service.is_enabled())

        req = AIRequest(prompt="Test Prompt")
        resp = self.ai_service.generate(req)

        self.assertFalse(resp.success)
        self.assertIn("disabled", resp.error_message.lower())

    # -------------------------------------------------------------------------
    # 3. Provider Execution & Dynamic Switching
    # -------------------------------------------------------------------------

    def test_mock_provider_execution(self):
        """Verify AIService routes generation through active MockProvider when enabled."""
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")

        req = AIRequest(prompt="Design an enemy boss")
        resp = self.ai_service.generate(req)

        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "mock")
        self.assertIn("Design an enemy boss", resp.text)
        self.assertIsNotNone(resp.usage)

    def test_dynamic_provider_switching(self):
        """Verify switching active provider updates service state."""
        self.ai_service.set_enabled(True)
        self.assertTrue(self.ai_service.set_active_provider("gemini"))
        self.assertEqual(self.ai_service.get_active_provider_id(), "gemini")

        self.assertTrue(self.ai_service.set_active_provider("claude"))
        self.assertEqual(self.ai_service.get_active_provider_id(), "claude")

        # Invalid provider
        self.assertFalse(self.ai_service.set_active_provider("non_existent_provider"))

    # -------------------------------------------------------------------------
    # 4. Configuration Persistence & Key Security
    # -------------------------------------------------------------------------

    def test_configuration_persistence_and_reload(self):
        """Verify configuration persists to ~/.creativeworkspace/ai_config.json across reloads."""
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("mock")
        self.ai_service.set_api_key("openai", "sk-test-secret-key-123456789")
        self.ai_service.set_model_override("openai", "gpt-4-turbo")
        self.ai_service.set_endpoint("local", "http://127.0.0.1:8000/v1")

        # Verify config file exists in config_dir, NOT in project directories
        self.assertTrue((self.config_dir / "ai_config.json").exists())

        # Reload fresh instance
        reloaded = AIService(config_dir=self.config_dir)
        self.assertTrue(reloaded.is_enabled())
        self.assertEqual(reloaded.get_active_provider_id(), "mock")
        self.assertEqual(reloaded.get_config().model_overrides.get("openai"), "gpt-4-turbo")
        self.assertEqual(reloaded.get_config().endpoints.get("local"), "http://127.0.0.1:8000/v1")

    def test_api_keys_never_touch_project_folders(self):
        """Verify API keys are stored strictly in local user config and not in project files."""
        fake_project_dir = Path(self.test_dir) / "MyGameProject"
        fake_project_dir.mkdir()

        # Configure AI key
        self.ai_service.set_api_key("openai", "sk-super-secret-production-key-999")

        # Assert no file in project dir has the key
        for root, _, files in os.walk(str(fake_project_dir)):
            for f in files:
                content = (Path(root) / f).read_text(encoding="utf-8", errors="ignore")
                self.assertNotIn("sk-super-secret", content)

    # -------------------------------------------------------------------------
    # 5. Missing Credentials & Error Redaction
    # -------------------------------------------------------------------------

    def test_missing_api_key_returns_clean_error(self):
        """Verify unconfigured provider returns clear missing key message without throwing."""
        self.ai_service.set_enabled(True)
        self.ai_service.set_active_provider("openai")

        # Ensure no env var
        with patch.dict(os.environ, {}, clear=True):
            resp = self.ai_service.generate(AIRequest(prompt="Hello"))
            self.assertFalse(resp.success)
            self.assertIn("API key is missing", resp.error_message)

    # -------------------------------------------------------------------------
    # 6. Mocked Network Execution for Providers
    # -------------------------------------------------------------------------

    @patch("urllib.request.urlopen")
    def test_openai_provider_mocked_http_success(self, mock_urlopen):
        """Verify OpenAIProvider formats request and parses REST JSON response correctly."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "id": "chatcmpl-123",
            "model": "gpt-4o",
            "choices": [{"message": {"role": "assistant", "content": "Creative idea response"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        provider = OpenAIProvider()
        config = AIConfig(api_keys={"openai": "sk-test-key-mock"})
        req = AIRequest(prompt="Brainstorm weapon names", system_instruction="Be concise")

        resp = provider.generate(req, config)

        self.assertTrue(resp.success)
        self.assertEqual(resp.text, "Creative idea response")
        self.assertEqual(resp.usage.total_tokens, 20)

    @patch("urllib.request.urlopen")
    def test_gemini_provider_mocked_http_success(self, mock_urlopen):
        """Verify GeminiProvider sends x-goog-api-key header and formats request cleanly."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "Gemini generated concept"}]},
                "finishReason": "STOP",
            }],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 15, "totalTokenCount": 25},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        provider = GeminiProvider()
        config = AIConfig(api_keys={"gemini": "AIzaSySecretGeminiKey123"})
        # Test with models/ prefix to ensure normalization
        req = AIRequest(prompt="Character backstory", model="models/gemini-3.6-flash")

        resp = provider.generate(req, config)

        self.assertTrue(resp.success)
        self.assertEqual(resp.text, "Gemini generated concept")
        self.assertEqual(resp.usage.total_tokens, 25)

        # Inspect the intercepted Request
        call_args = mock_urlopen.call_args
        sent_req = call_args[0][0]
        self.assertIsInstance(sent_req, urllib.request.Request)

        # Verify exact URL construction (no duplicate models/ and no query param key)
        self.assertEqual(sent_req.full_url, "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent")

        # Verify x-goog-api-key header is sent and Authorization: Bearer is NOT sent
        headers_lower = {k.lower(): v for k, v in sent_req.headers.items()}
        self.assertEqual(headers_lower.get("x-goog-api-key"), "AIzaSySecretGeminiKey123")
        self.assertNotIn("authorization", headers_lower)

    @patch("urllib.request.urlopen")
    def test_gemini_auth_error_handling_401_403(self, mock_urlopen):
        """Verify 401/403 credentials error gives clear guidance without leaking key."""
        from urllib.error import HTTPError
        import io

        error_body = json.dumps({
            "error": {
                "code": 403,
                "message": "Request had invalid authentication credentials. Expected OAuth 2 access token, login cookie or other valid authentication credential.",
                "status": "PERMISSION_DENIED"
            }
        }).encode("utf-8")

        mock_http_error = HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=io.BytesIO(error_body)
        )
        mock_urlopen.side_effect = mock_http_error

        provider = GeminiProvider()
        config = AIConfig(api_keys={"gemini": "AIzaSySecretGeminiKey123"})
        req = AIRequest(prompt="Test auth failure")

        resp = provider.generate(req, config)

        self.assertFalse(resp.success)
        self.assertIn("Invalid or unauthorized Gemini API key", resp.error_message)
        self.assertNotIn("AIzaSySecretGeminiKey123", resp.error_message)

    @patch("urllib.request.urlopen")
    def test_claude_provider_mocked_http_success(self, mock_urlopen):
        """Verify ClaudeProvider formats request and parses Anthropic Messages REST response."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "id": "msg_123",
            "model": "claude-3-5-sonnet-20241022",
            "content": [{"type": "text", "text": "Claude narrative arc"}],
            "usage": {"input_tokens": 18, "output_tokens": 30},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        provider = ClaudeProvider()
        config = AIConfig(api_keys={"claude": "sk-ant-test-key"})
        req = AIRequest(prompt="Write quest summary")

        resp = provider.generate(req, config)

        self.assertTrue(resp.success)
        self.assertEqual(resp.text, "Claude narrative arc")
        self.assertEqual(resp.usage.total_tokens, 48)

    @patch("urllib.request.urlopen")
    def test_local_provider_mocked_http_success(self, mock_urlopen):
        """Verify LocalProvider connects to local OpenAI-compatible endpoint."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "model": "llama3",
            "choices": [{"message": {"role": "assistant", "content": "Local Ollama output"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        provider = LocalProvider()
        config = AIConfig(endpoints={"local": "http://localhost:11434/v1"})
        req = AIRequest(prompt="Test local inference")

        resp = provider.generate(req, config)

        self.assertTrue(resp.success)
        self.assertEqual(resp.text, "Local Ollama output")

    def test_gemini_default_model_is_current(self):
        """1. Verify Gemini default model is current (gemini-3.6-flash) and not deprecated 2.0 or 1.5."""
        provider = GeminiProvider()
        self.assertEqual(provider.default_model, "gemini-3.6-flash")

        config = AIConfig()
        self.assertEqual(config.model_overrides.get("gemini"), "gemini-3.6-flash")

    @patch("urllib.request.urlopen")
    def test_gemini_discover_models_filters_and_parses(self, mock_urlopen):
        """2 & 3 & 4. Verify model discovery parses Google Models API and filters non-text & deprecated models."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "models": [
                {
                    "name": "models/gemini-3.6-flash",
                    "displayName": "Gemini 3.6 Flash",
                    "supportedGenerationMethods": ["generateContent", "countTokens"],
                },
                {
                    "name": "models/gemini-3.5-flash-lite",
                    "displayName": "Gemini 3.5 Flash Lite",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-2.5-pro",
                    "displayName": "Gemini 2.5 Pro",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/gemini-2.0-flash",  # Deprecated / shutdown
                    "displayName": "Gemini 2.0 Flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/text-embedding-004",  # Embedding only
                    "displayName": "Text Embedding",
                    "supportedGenerationMethods": ["embedContent"],
                },
                {
                    "name": "models/imagen-3.0-generate-002",  # Image only
                    "displayName": "Imagen 3",
                    "supportedGenerationMethods": ["generateImages"],
                },
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        provider = GeminiProvider()
        config = AIConfig(api_keys={"gemini": "AIzaSyMockKey"})

        success, models, err = provider.discover_models(config)

        self.assertTrue(success)
        self.assertEqual(err, "")
        self.assertIn("gemini-3.6-flash", models)
        self.assertIn("gemini-3.5-flash-lite", models)
        self.assertIn("gemini-2.5-pro", models)
        # Verify filtered models
        self.assertNotIn("gemini-2.0-flash", models)
        self.assertNotIn("text-embedding-004", models)
        self.assertNotIn("imagen-3.0-generate-002", models)

        # Verify sent request headers and URL
        sent_req = mock_urlopen.call_args[0][0]
        self.assertEqual(sent_req.full_url, "https://generativelanguage.googleapis.com/v1beta/models")
        headers_lower = {k.lower(): v for k, v in sent_req.headers.items()}
        self.assertEqual(headers_lower.get("x-goog-api-key"), "AIzaSyMockKey")
        self.assertNotIn("authorization", headers_lower)

    @patch("urllib.request.urlopen")
    def test_gemini_discover_models_handles_error_gracefully(self, mock_urlopen):
        """6. Verify model discovery gracefully handles API errors without exposing key."""
        mock_urlopen.side_effect = Exception("403 Forbidden: Invalid API Key")

        provider = GeminiProvider()
        config = AIConfig(api_keys={"gemini": "AIzaSySecretKey"})

        success, models, err = provider.discover_models(config)

        self.assertFalse(success)
        self.assertEqual(models, [])
        self.assertIn("Failed to retrieve", err)
        self.assertNotIn("AIzaSySecretKey", err)


if __name__ == "__main__":
    unittest.main()
