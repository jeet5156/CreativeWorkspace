"""OpenAI REST API Provider implementation."""

import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from models.ai import AIRequest, AIResponse, AIUsage, AIConfig
from services.ai.providers.base_provider import BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    """Provider for OpenAI and OpenAI-compatible endpoints."""

    def __init__(self):
        super().__init__(
            provider_id="openai",
            display_name="OpenAI",
            default_model="gpt-4o",
        )

    def get_env_var_names(self) -> list[str]:
        return ["OPENAI_API_KEY", "OPENAI_KEY"]

    def generate(self, request: AIRequest, config: AIConfig) -> AIResponse:
        api_key = self.get_api_key(config)
        if not api_key:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=self.get_model(request, config),
                error_message="OpenAI API key is missing. Please set OPENAI_API_KEY or configure local AI settings.",
            )

        model = self.get_model(request, config)
        endpoint = (self.get_endpoint(config) or "https://api.openai.com/v1").rstrip("/")
        url = f"{endpoint}/chat/completions"

        # Build messages payload
        messages = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})

        for msg in request.get_effective_messages():
            messages.append({"role": msg.role, "content": msg.content})

        if not messages:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=model,
                error_message="Cannot generate response with empty prompt/messages.",
            )

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature if request.temperature is not None else config.temperature,
        }

        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        elif config.max_tokens:
            payload["max_tokens"] = config.max_tokens

        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "CreativeWorkspace-AI/1.0",
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            choices = resp_data.get("choices", [])
            if not choices:
                return AIResponse(
                    success=False,
                    provider=self.provider_id,
                    model=model,
                    error_message="OpenAI returned an empty response with no choices.",
                    raw_response=resp_data,
                )

            first_choice = choices[0]
            msg_obj = first_choice.get("message", {})
            text_content = msg_obj.get("content", "")

            # Usage info
            usage_data = resp_data.get("usage", {})
            usage = AIUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
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
                error_message=f"OpenAI API Error: {msg}",
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
                error_message=f"Unexpected error communicating with OpenAI: {str(e)}",
            )
