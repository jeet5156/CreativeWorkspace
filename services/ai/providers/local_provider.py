"""Local / Custom OpenAI-compatible Server Provider (Ollama, LM Studio, LocalAI, etc.)."""

import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from models.ai import AIRequest, AIResponse, AIUsage, AIConfig
from services.ai.providers.base_provider import BaseAIProvider


class LocalProvider(BaseAIProvider):
    """Provider for local and custom self-hosted endpoints (e.g. Ollama, LM Studio)."""

    def __init__(self):
        super().__init__(
            provider_id="local",
            display_name="Local / Custom Server",
            default_model="llama3",
        )

    def is_configured(self, config: AIConfig) -> bool:
        # Local endpoints typically do not require an API key; presence of an endpoint is sufficient
        endpoint = self.get_endpoint(config)
        return bool(endpoint and endpoint.strip())

    def get_env_var_names(self) -> list[str]:
        return ["LOCAL_AI_API_KEY", "OLLAMA_API_KEY"]

    def generate(self, request: AIRequest, config: AIConfig) -> AIResponse:
        endpoint = (self.get_endpoint(config) or "http://localhost:11434/v1").rstrip("/")
        model = self.get_model(request, config)
        api_key = self.get_api_key(config) or "local-key"

        url = f"{endpoint}/chat/completions"

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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "CreativeWorkspace-AI/1.0",
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=45) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            choices = resp_data.get("choices", [])
            if not choices:
                return AIResponse(
                    success=False,
                    provider=self.provider_id,
                    model=model,
                    error_message=f"Local server at {endpoint} returned no completion choices.",
                    raw_response=resp_data,
                )

            msg_obj = choices[0].get("message", {})
            text_content = msg_obj.get("content", "")

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

        except urllib.error.URLError as e:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=model,
                error_message=f"Local server unavailable at {endpoint}: {e.reason}",
            )
        except Exception as e:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=model,
                error_message=f"Error connecting to local server: {str(e)}",
            )
