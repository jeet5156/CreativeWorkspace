"""Base interface for all AI Providers in CreativeWorkspace."""

import os
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any

from models.ai import AIRequest, AIResponse, AIConfig


class BaseAIProvider(ABC):
    """Abstract base provider defining standardized generation and configuration interface."""

    def __init__(self, provider_id: str, display_name: str, default_model: str):
        self.provider_id = provider_id
        self.display_name = display_name
        self.default_model = default_model

    @abstractmethod
    def generate(self, request: AIRequest, config: AIConfig) -> AIResponse:
        """Execute text/message generation and return structured AIResponse."""
        pass

    def is_configured(self, config: AIConfig) -> bool:
        """Check if provider has required authentication credentials (env or config)."""
        key = self.get_api_key(config)
        return bool(key and key.strip())

    def get_api_key(self, config: AIConfig) -> Optional[str]:
        """Resolve API key checking provider-specific environment variables first, then local config."""
        # Check standard environment variables
        env_vars = self.get_env_var_names()
        for var in env_vars:
            val = os.environ.get(var)
            if val and val.strip():
                return val.strip()

        # Fallback to local secure config
        if config and config.api_keys:
            key = config.api_keys.get(self.provider_id)
            if key and key.strip():
                return key.strip()

        return None

    def get_env_var_names(self) -> list[str]:
        """Return list of environment variable names checked for this provider."""
        return [f"{self.provider_id.upper()}_API_KEY"]

    def get_endpoint(self, config: AIConfig) -> str:
        """Resolve base API endpoint from config or default."""
        if config and config.endpoints and self.provider_id in config.endpoints:
            return config.endpoints[self.provider_id]
        return ""

    def get_model(self, request: AIRequest, config: AIConfig) -> str:
        """Resolve effective model: request-level override -> config-level override -> provider default."""
        if request and request.model:
            return request.model
        if config and config.model_overrides and self.provider_id in config.model_overrides:
            return config.model_overrides[self.provider_id]
        return self.default_model

    def validate_connection(self, config: AIConfig) -> Tuple[bool, str]:
        """Validate whether provider is ready to process requests."""
        if not self.is_configured(config):
            return False, f"{self.display_name} API key is not configured. Set environment variable {self.get_env_var_names()[0]} or configure local settings."
        return True, f"{self.display_name} is configured."

    def _redact_key(self, key: Optional[str]) -> str:
        """Utility to safely mask API keys for debug/display."""
        if not key or len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"
