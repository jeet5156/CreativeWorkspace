"""Deterministic Mock Provider for unit testing."""

from typing import Optional, Dict, Any, Callable
from models.ai import AIRequest, AIResponse, AIUsage, AIConfig
from services.ai.providers.base_provider import BaseAIProvider


class MockProvider(BaseAIProvider):
    """Deterministic in-memory mock provider for testing without real network or API keys."""

    def __init__(self, canned_response: str = "Mocked AI Response", echo_prompt: bool = True):
        super().__init__(
            provider_id="mock",
            display_name="Mock Provider",
            default_model="mock-model-v1",
        )
        self.canned_response = canned_response
        self.echo_prompt = echo_prompt
        self.custom_responder: Optional[Callable[[AIRequest], AIResponse]] = None
        self.call_count = 0
        self.last_request: Optional[AIRequest] = None

    def is_configured(self, config: AIConfig) -> bool:
        return True

    def generate(self, request: AIRequest, config: AIConfig) -> AIResponse:
        self.call_count += 1
        self.last_request = request

        if self.custom_responder:
            return self.custom_responder(request)

        if self.echo_prompt:
            prompt_str = request.prompt or (request.messages[-1].content if request.messages else "")
            text = f"{self.canned_response} for prompt: '{prompt_str}'"
        else:
            text = self.canned_response

        return AIResponse(
            text=text,
            provider=self.provider_id,
            model=self.get_model(request, config),
            usage=AIUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            success=True,
            metadata={"mock_call_count": self.call_count},
        )
