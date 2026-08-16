"""Anthropic Claude REST API Provider implementation."""

import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from models.ai import AIRequest, AIResponse, AIUsage, AIConfig
from services.ai.providers.base_provider import BaseAIProvider


class ClaudeProvider(BaseAIProvider):
    """Provider for Anthropic Claude API."""

    def __init__(self):
        super().__init__(
            provider_id="claude",
            display_name="Anthropic Claude",
            default_model="claude-3-5-sonnet-20241022",
        )

    def get_env_var_names(self) -> list[str]:
        return ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"]

    def generate(self, request: AIRequest, config: AIConfig) -> AIResponse:
        api_key = self.get_api_key(config)
        if not api_key:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=self.get_model(request, config),
                error_message="Claude API key is missing. Please set ANTHROPIC_API_KEY or configure local AI settings.",
            )

        model = self.get_model(request, config)
        endpoint = (self.get_endpoint(config) or "https://api.anthropic.com/v1").rstrip("/")
        url = f"{endpoint}/messages"

        # Anthropic requires user/assistant roles alternating and system instruction top-level
        messages = []
        for msg in request.get_effective_messages():
            role = "user" if msg.role != "assistant" else "assistant"
            messages.append({"role": role, "content": msg.content})

        if not messages:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=model,
                error_message="Cannot generate response with empty prompt/messages.",
            )

        max_toks = request.max_tokens or config.max_tokens or 2048

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_toks,
            "temperature": request.temperature if request.temperature is not None else config.temperature,
        }

        if request.system_instruction:
            payload["system"] = request.system_instruction

        if request.stop_sequences:
            payload["stop_sequences"] = request.stop_sequences

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "User-Agent": "CreativeWorkspace-AI/1.0",
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            content_blocks = resp_data.get("content", [])
            text_blocks = [c.get("text", "") for c in content_blocks if c.get("type") == "text"]
            text_content = "".join(text_blocks)

            usage_data = resp_data.get("usage", {})
            usage = AIUsage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            )

            return AIResponse(
                text=text_content,
                provider=self.provider_id,
                model=resp_data.get("model", model),
                usage=usage,
                success=True,
                raw_response=resp_data,
            )

        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                msg = f"HTTP Error {e.code}: {e.reason}"
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=model,
                error_message=f"Claude API Error: {msg}",
            )
        except urllib.error.URLError as e:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=model,
                error_message=f"Network connection failed: {e.reason}",
            )
        except Exception as e:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=model,
                error_message=f"Unexpected error communicating with Claude: {str(e)}",
            )
