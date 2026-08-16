"""Core AI Service for CreativeWorkspace.

Provides a unified, provider-agnostic interface for AI generation, provider management,
and secure local configuration persistence.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Callable

from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

from models.ai import AIRequest, AIResponse, AIConfig, AIProviderType
from services.ai.providers.base_provider import BaseAIProvider
from services.ai.providers.openai_provider import OpenAIProvider
from services.ai.providers.gemini_provider import GeminiProvider
from services.ai.providers.claude_provider import ClaudeProvider
from services.ai.providers.local_provider import LocalProvider
from services.ai.providers.mock_provider import MockProvider


class AIWorkerSignals(QObject):
    """Signals for background AI worker tasks."""
    started = Signal(object)              # (AIRequest)
    finished = Signal(object, object)    # (AIRequest, AIResponse)
    error = Signal(str)                  # (error_message)


class ModelDiscoverySignals(QObject):
    """Signals for background model discovery tasks."""
    started = Signal(str)                # (provider_id)
    finished = Signal(str, list, str)    # (provider_id, models_list, error_message)
    error = Signal(str)                  # (error_message)


class AIWorker(QRunnable):
    """Asynchronous worker executing AI requests in a background thread pool."""

    def __init__(self, ai_service: "AIService", request: AIRequest, provider_id: Optional[str] = None):
        super().__init__()
        self.ai_service = ai_service
        self.request = request
        self.provider_id = provider_id
        self.signals = AIWorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        """Mark worker as cancelled."""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        """Check if worker was cancelled."""
        return self._is_cancelled

    def run(self):
        """Execute request on background thread and dispatch results via signals."""
        if self._is_cancelled:
            return
        try:
            self.signals.started.emit(self.request)
        except Exception:
            pass

        try:
            response = self.ai_service.generate(self.request, provider_id=self.provider_id)
        except Exception as e:
            response = AIResponse(
                success=False,
                provider=self.provider_id or self.ai_service.get_active_provider_id(),
                error_message=f"Async AI execution error: {e}",
            )

        if not self._is_cancelled:
            try:
                self.signals.finished.emit(self.request, response)
                if not response.success and response.error_message:
                    self.signals.error.emit(response.error_message)
            except Exception:
                pass


class ModelDiscoveryWorker(QRunnable):
    """Asynchronous worker querying dynamic models from a provider API."""

    def __init__(self, ai_service: "AIService", provider_id: str):
        super().__init__()
        self.ai_service = ai_service
        self.provider_id = provider_id
        self.signals = ModelDiscoverySignals()
        self._is_cancelled = False

    def cancel(self):
        """Mark worker as cancelled."""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        """Query models on background thread and emit signals."""
        if self._is_cancelled:
            return
        try:
            self.signals.started.emit(self.provider_id)
        except Exception:
            pass

        try:
            success, models, err = self.ai_service.discover_models(self.provider_id)
        except Exception as e:
            success, models, err = False, [], str(e)

        if not self._is_cancelled:
            try:
                self.signals.finished.emit(self.provider_id, models, err)
                if not success and err:
                    self.signals.error.emit(err)
            except Exception:
                pass


class AIService(QObject):
    """Central manager coordinating AI providers, secure settings, and generation requests."""

    ai_status_changed = Signal(bool, str)  # (enabled, active_provider)
    ai_request_started = Signal(object)    # (AIRequest)
    ai_request_finished = Signal(object, object)  # (AIRequest, AIResponse)
    ai_error = Signal(str)                 # (error_message)

    def __init__(self, config_dir: Optional[Union[str, Path]] = None):
        super().__init__()
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".creativeworkspace"

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "ai_config.json"

        # Provider Registry
        self._providers: Dict[str, BaseAIProvider] = {}
        self._register_default_providers()

        # Load persisted config
        self._config: AIConfig = self._load_config()

    def _register_default_providers(self):
        """Register out-of-the-box provider adapters."""
        self.register_provider(OpenAIProvider())
        self.register_provider(GeminiProvider())
        self.register_provider(ClaudeProvider())
        self.register_provider(LocalProvider())
        self.register_provider(MockProvider())

    def register_provider(self, provider: BaseAIProvider):
        """Register or override an AI provider adapter."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> Optional[BaseAIProvider]:
        """Get registered provider instance by ID."""
        return self._providers.get(provider_id)

    # -------------------------------------------------------------------------
    # Configuration Management & Persistence
    # -------------------------------------------------------------------------

    def _load_config(self) -> AIConfig:
        """Load configuration from local storage file or create default."""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return AIConfig.from_dict(data)
            except Exception:
                pass
        return AIConfig()

    def _save_config(self) -> bool:
        """Atomically persist configuration to local user directory."""
        try:
            data = self._config.to_dict()
            tmp_fd, tmp_path = tempfile.mkstemp(dir=str(self.config_dir), prefix="ai_cfg_", suffix=".tmp")
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Atomic replace
            os.replace(tmp_path, str(self.config_file))
            return True
        except Exception:
            return False

    def get_config(self) -> AIConfig:
        """Return current AIConfig copy."""
        return self._config

    def is_enabled(self) -> bool:
        """Check if AI capabilities are globally enabled."""
        return bool(self._config.enabled)

    def set_enabled(self, enabled: bool) -> bool:
        """Enable or disable global AI capabilities."""
        self._config.enabled = bool(enabled)
        saved = self._save_config()
        try:
            self.ai_status_changed.emit(self._config.enabled, self._config.active_provider)
        except Exception:
            pass
        return saved

    def get_active_provider_id(self) -> str:
        """Get ID of active provider."""
        return self._config.active_provider

    def set_active_provider(self, provider_id: str) -> bool:
        """Set active provider."""
        if provider_id not in self._providers:
            return False
        self._config.active_provider = provider_id
        saved = self._save_config()
        try:
            self.ai_status_changed.emit(self._config.enabled, self._config.active_provider)
        except Exception:
            pass
        return saved

    def get_active_provider(self) -> Optional[BaseAIProvider]:
        """Get currently active provider instance."""
        return self._providers.get(self._config.active_provider)

    def set_api_key(self, provider_id: str, api_key: str) -> bool:
        """Set and persist API key securely in user config."""
        cleaned_key = api_key.strip()
        if cleaned_key:
            self._config.api_keys[provider_id] = cleaned_key
        else:
            self._config.api_keys.pop(provider_id, None)
        return self._save_config()

    def set_model_override(self, provider_id: str, model: str) -> bool:
        """Set model override for a specific provider."""
        cleaned = model.strip()
        if cleaned:
            self._config.model_overrides[provider_id] = cleaned
        else:
            self._config.model_overrides.pop(provider_id, None)
        return self._save_config()

    def set_endpoint(self, provider_id: str, endpoint: str) -> bool:
        """Set custom endpoint for a provider (e.g. local Ollama or private proxy)."""
        cleaned = endpoint.strip()
        if cleaned:
            self._config.endpoints[provider_id] = cleaned
        else:
            self._config.endpoints.pop(provider_id, None)
        return self._save_config()

    def get_api_key(self, provider_id: str) -> str:
        """Get stored API key for a provider from user config."""
        return self._config.api_keys.get(provider_id, "")

    def get_model(self, provider_id: str) -> str:
        """Get effective model for a provider."""
        provider = self.get_provider(provider_id)
        if provider:
            return provider.get_model(None, self._config)
        return self._config.model_overrides.get(provider_id, "")

    def get_endpoint(self, provider_id: str) -> str:
        """Get configured endpoint for a provider."""
        provider = self.get_provider(provider_id)
        if provider:
            return provider.get_endpoint(self._config)
        return self._config.endpoints.get(provider_id, "")

    def is_provider_configured(self, provider_id: str) -> bool:
        """Check if a specific provider is configured with credentials/endpoint."""
        provider = self.get_provider(provider_id)
        if provider:
            return provider.is_configured(self._config)
        return False

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Return list of all registered providers with their configuration and readiness state."""
        results = []
        for pid, provider in self._providers.items():
            is_cfg = provider.is_configured(self._config)
            model = provider.get_model(None, self._config)
            results.append({
                "id": pid,
                "name": provider.display_name,
                "configured": is_cfg,
                "active": (pid == self._config.active_provider),
                "model": model,
                "endpoint": provider.get_endpoint(self._config),
            })
        return results

    def validate_active_provider(self) -> Tuple[bool, str]:
        """Validate connection readiness of the currently active provider."""
        provider = self.get_active_provider()
        if not provider:
            return False, f"Active provider '{self._config.active_provider}' is not registered."
        return provider.validate_connection(self._config)

    # -------------------------------------------------------------------------
    # Execution & Generation Routing
    # -------------------------------------------------------------------------

    def generate(self, request: AIRequest, provider_id: Optional[str] = None) -> AIResponse:
        """Route an AI generation request to the active or specified provider safely."""
        if not self.is_enabled():
            return AIResponse(
                success=False,
                provider=provider_id or self._config.active_provider,
                error_message="AI features are currently disabled in settings. Enable AI to generate responses.",
            )

        target_id = provider_id or self._config.active_provider
        provider = self._providers.get(target_id)
        if not provider:
            err = f"AI Provider '{target_id}' is not registered."
            try:
                self.ai_error.emit(err)
            except Exception:
                pass
            return AIResponse(
                success=False,
                provider=target_id,
                error_message=err,
            )

        try:
            self.ai_request_started.emit(request)
        except Exception:
            pass

        try:
            response = provider.generate(request, self._config)
        except Exception as e:
            # Mask any potential API key substrings
            err_msg = str(e)
            for k in self._config.api_keys.values():
                if k and k in err_msg:
                    err_msg = err_msg.replace(k, "***")

            response = AIResponse(
                success=False,
                provider=target_id,
                error_message=f"Provider '{target_id}' execution failed: {err_msg}",
            )

        try:
            self.ai_request_finished.emit(request, response)
            if not response.success and response.error_message:
                self.ai_error.emit(response.error_message)
        except Exception:
            pass

        return response

    def generate_async(
        self,
        request: AIRequest,
        on_finished: Optional[Callable[[AIRequest, AIResponse], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        provider_id: Optional[str] = None,
    ) -> AIWorker:
        """Execute an AI generation request asynchronously on the global thread pool."""
        worker = AIWorker(self, request, provider_id=provider_id)
        if on_finished:
            worker.signals.finished.connect(on_finished)
        if on_error:
            worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)
        return worker

    def get_cached_models(self, provider_id: str) -> List[str]:
        """Get cached discovered model list for a provider."""
        return list(self._config.cached_models.get(provider_id, []))

    def set_cached_models(self, provider_id: str, models: List[str]) -> bool:
        """Persist discovered model list for a provider in user config."""
        self._config.cached_models[provider_id] = list(models)
        return self._save_config()

    def discover_models(self, provider_id: Optional[str] = None) -> Tuple[bool, List[str], str]:
        """Query models from provider API synchronously."""
        target_id = provider_id or self.get_active_provider_id()
        provider = self.get_provider(target_id)
        if not provider:
            return False, [], f"Provider '{target_id}' is not registered."

        if not hasattr(provider, "discover_models"):
            return True, [], ""

        success, models, err = provider.discover_models(self._config)
        if success and models:
            self.set_cached_models(target_id, models)
        return success, models, err

    def discover_models_async(
        self,
        provider_id: Optional[str] = None,
        on_finished: Optional[Callable[[str, List[str], str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> ModelDiscoveryWorker:
        """Query models from provider API asynchronously on QThreadPool."""
        target_id = provider_id or self.get_active_provider_id()
        worker = ModelDiscoveryWorker(self, target_id)
        if on_finished:
            worker.signals.finished.connect(on_finished)
        if on_error:
            worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)
        return worker

