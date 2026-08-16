"""Google Gemini REST API Provider implementation with dynamic model discovery and modern header authentication."""

import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List, Tuple

from models.ai import AIRequest, AIResponse, AIUsage, AIConfig
from services.ai.providers.base_provider import BaseAIProvider


class GeminiProvider(BaseAIProvider):
    """Provider for Google Gemini API using official header-based authentication."""

    def __init__(self):
        super().__init__(
            provider_id="gemini",
            display_name="Google Gemini",
            default_model="gemini-3.6-flash",
        )

    def get_env_var_names(self) -> list[str]:
        return ["GEMINI_API_KEY", "GOOGLE_API_KEY"]

    def _normalize_model_name(self, model: Optional[str]) -> str:
        """Strip 'models/' prefix and ensure clean model identifier."""
        if not model or not model.strip():
            return self.default_model
        cleaned = model.strip()
        while cleaned.startswith("models/"):
            cleaned = cleaned[len("models/"):]
        return cleaned or self.default_model

    def _mask_key(self, text: str, api_key: Optional[str]) -> str:
        """Sanitize error messages to ensure API keys are never leaked."""
        if not text:
            return ""
        if api_key and api_key in text:
            return text.replace(api_key, "***")
        return text

    def discover_models(self, config: AIConfig) -> Tuple[bool, List[str], str]:
        """Fetch available models from Google Models API using x-goog-api-key authentication."""
        api_key = self.get_api_key(config)
        if not api_key:
            return False, [], "Gemini API key is not configured. Enter an API key first in Settings → AI."

        endpoint = (self.get_endpoint(config) or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{endpoint}/models"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CreativeWorkspace-AI/1.0",
            "x-goog-api-key": api_key,
        }

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            models_raw = resp_data.get("models", [])
            if not models_raw:
                return False, [], "No models returned by Google Models API."

            deprecated_ids = {
                "gemini-2.0-flash",
                "gemini-2.0-flash-exp",
                "gemini-1.0-pro",
                "gemini-1.0-pro-vision",
                "gemini-pro",
                "gemini-pro-vision",
                "gemini-1.5-flash-8b-deprecated",
            }

            discovered = []
            for item in models_raw:
                raw_name = item.get("name", "")
                model_id = self._normalize_model_name(raw_name)
                methods = item.get("supportedGenerationMethods", [])

                # Must support generateContent
                if "generateContent" not in methods:
                    continue

                # Filter out embedding, image, audio, or specialized models
                low = model_id.lower()
                if any(k in low for k in ["embedding", "imagen", "tts", "whisper", "aqa", "medlm", "bison", "gecko"]):
                    continue

                # Filter out explicitly deprecated / shutdown models
                if model_id in deprecated_ids or "deprecated" in low:
                    continue

                discovered.append(model_id)

            if not discovered:
                return False, [], "No suitable text-generation models found from Google Models API."

            return True, discovered, ""

        except urllib.error.HTTPError as e:
            err_body = {}
            try:
                err_body = json.loads(e.read().decode("utf-8"))
            except Exception:
                pass
            msg = err_body.get("error", {}).get("message", "")
            status = getattr(e, "code", 0)

            if status in (401, 403) or "API_KEY_INVALID" in msg or "invalid authentication" in msg.lower():
                err_text = "Invalid or unauthorized Gemini API key. Please check your API key in Settings → AI."
            elif status == 429 or "RESOURCE_EXHAUSTED" in msg:
                err_text = "Gemini API rate limit or quota exceeded. Please try again later."
            else:
                err_text = f"Gemini Models API Error (HTTP {status}): {msg or e.reason}"

            return False, [], self._mask_key(err_text, api_key)

        except urllib.error.URLError as e:
            return False, [], f"Network connection error contacting Gemini Models API: {e.reason}"
        except Exception as e:
            return False, [], self._mask_key(f"Failed to retrieve Gemini models: {str(e)}", api_key)

    def generate(self, request: AIRequest, config: AIConfig) -> AIResponse:
        api_key = self.get_api_key(config)
        raw_model = self.get_model(request, config)
        clean_model = self._normalize_model_name(raw_model)

        if not api_key:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=clean_model,
                error_message="Gemini API key is missing. Please set GEMINI_API_KEY or configure local AI settings in Settings → AI.",
            )

        endpoint = (self.get_endpoint(config) or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{endpoint}/models/{clean_model}:generateContent"

        contents = []
        for msg in request.get_effective_messages():
            role = "user" if msg.role in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        if not contents:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=clean_model,
                error_message="Cannot generate response with empty prompt/messages.",
            )

        payload: Dict[str, Any] = {
            "contents": contents,
        }

        # System instruction support
        if request.system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_instruction}]
            }

        # Generation config
        gen_config: Dict[str, Any] = {}
        if request.temperature is not None:
            gen_config["temperature"] = request.temperature
        elif config.temperature is not None:
            gen_config["temperature"] = config.temperature

        if request.max_tokens:
            gen_config["maxOutputTokens"] = request.max_tokens
        elif config.max_tokens:
            gen_config["maxOutputTokens"] = config.max_tokens

        if request.stop_sequences:
            gen_config["stopSequences"] = request.stop_sequences

        if gen_config:
            payload["generationConfig"] = gen_config

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CreativeWorkspace-AI/1.0",
            "x-goog-api-key": api_key,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))

            candidates = resp_data.get("candidates", [])
            if not candidates:
                feedback = resp_data.get("promptFeedback", {})
                block_reason = feedback.get("blockReason")
                err_msg = f"Gemini blocked content: {block_reason}" if block_reason else "Gemini returned no response candidates."
                return AIResponse(
                    success=False,
                    provider=self.provider_id,
                    model=clean_model,
                    error_message=err_msg,
                    raw_response=resp_data,
                )

            first_cand = candidates[0]
            parts = first_cand.get("content", {}).get("parts", [])
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            text_content = "".join(text_parts)

            # Usage metadata
            usage_meta = resp_data.get("usageMetadata", {})
            usage = AIUsage(
                prompt_tokens=usage_meta.get("promptTokenCount", 0),
                completion_tokens=usage_meta.get("candidatesTokenCount", 0),
                total_tokens=usage_meta.get("totalTokenCount", 0),
            )

            return AIResponse(
                text=text_content,
                provider=self.provider_id,
                model=clean_model,
                usage=usage,
                success=True,
                raw_response=resp_data,
            )

        except urllib.error.HTTPError as e:
            err_body = {}
            try:
                err_body = json.loads(e.read().decode("utf-8"))
            except Exception:
                pass
            msg = err_body.get("error", {}).get("message", "")
            status = getattr(e, "code", 0)

            if status in (401, 403) or "API_KEY_INVALID" in msg or "invalid authentication" in msg.lower() or "permission" in msg.lower():
                err_text = "Invalid or unauthorized Gemini API key. Please check your API key in Settings → AI."
            elif status == 404 or "not found" in msg.lower():
                err_text = f"Model '{clean_model}' was not found or is unavailable. Click 'Refresh Models' in Settings → AI to update available models."
            elif status == 429 or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                err_text = "Gemini quota exceeded or rate limited. Please try again in a few moments."
            elif status == 400 or "INVALID_ARGUMENT" in msg:
                err_text = f"Invalid Gemini request parameters: {msg or e.reason}"
            else:
                err_text = f"Gemini API Error (HTTP {status}): {msg or e.reason}"

            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=clean_model,
                error_message=self._mask_key(err_text, api_key),
            )

        except urllib.error.URLError as e:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=clean_model,
                error_message=f"Network error connecting to Gemini: {e.reason}",
            )
        except Exception as e:
            return AIResponse(
                success=False,
                provider=self.provider_id,
                model=clean_model,
                error_message=self._mask_key(f"Unexpected error communicating with Gemini: {str(e)}", api_key),
            )
