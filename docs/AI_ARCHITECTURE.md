# CreativeWorkspace AI Architecture & Provider Layer

## 1. Overview

The CreativeWorkspace AI layer is designed around a **provider-agnostic, decentralized architecture**. UI components and feature subsystems (such as Knowledge, Asset Library, Project Intelligence, and Lab) never communicate directly with vendor SDKs (OpenAI, Gemini, Anthropic, etc.). Instead, all interactions flow through the centralized `AIService`.

```
┌────────────────────────────────────────────────────────────┐
│      CreativeWorkspace Features & UI Components            │
│   (Knowledge Notes, Asset Library, Lab Canvas, Projects)   │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼ AIRequest
┌────────────────────────────────────────────────────────────┐
│                        AIService                           │
│  - Active Provider Routing       - Status & Signals        │
│  - Key Redaction & Validation    - Error Recovery          │
└─────────────────────────────┬──────────────────────────────┘
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
       ┌──────────────┐┌──────────────┐┌──────────────┐
       │OpenAIProvider││GeminiProvider││ClaudeProvider│  ...
       └───────┬──────┘└──────┬───────┘└──────┬───────┘
               ▼              ▼              ▼
       ┌──────────────┐┌──────────────┐┌──────────────┐
       │ OpenAI REST  ││ Gemini REST  ││ Claude REST  │
       │     API      ││     API      ││     API      │
       └──────────────┘└──────────────┘└──────────────┘
```

---

## 2. Core Principles

1. **Decoupled & Provider-Agnostic**: Feature code construct standard `AIRequest` objects and receive standard `AIResponse` objects.
2. **Zero Hard Dependencies**: REST HTTP adapters use Python's built-in networking (`urllib.request` / `requests`). External SDKs are not required for core application startup.
3. **Fail-Safe & Non-Blocking**: If AI is disabled, unconfigured, or offline, `AIService` returns structured errors (`AIResponse(success=False, error_message=...)`) and never crashes the application.
4. **Strict Security & Key Hygiene**:
   - API keys are **NEVER** stored inside project files (`project.json`, `.asset_index.json`, `.lab.json`, or Knowledge documents).
   - API keys are **NEVER** committed to git-tracked files.
   - API keys are resolved first from standard environment variables (`OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`), and second from local user config (`~/.creativeworkspace/ai_config.json`).
   - Logging, exceptions, and signals automatically redact sensitive tokens (`sk-...` -> `sk-***`).

---

## 3. Data Models (`models/ai.py`)

### `AIRequest`
| Field | Type | Description |
| :--- | :--- | :--- |
| `prompt` | `str` | Main text prompt (convenience for single-turn requests). |
| `messages` | `List[AIMessage]` | Multi-turn chat messages (`role="user"\|"assistant"\|"system"`). |
| `system_instruction`| `Optional[str]` | High-level system prompt controlling AI behavior. |
| `context` | `Optional[AIContext]` | Structured CreativeWorkspace context (project, docs, assets, nodes). |
| `model` | `Optional[str]` | Optional request-level model override. |
| `temperature` | `float` | Sampling temperature (default: `0.7`). |
| `max_tokens` | `Optional[int]` | Maximum response token limit. |
| `stop_sequences` | `List[str]` | Custom generation stop words/sequences. |

### `AIResponse`
| Field | Type | Description |
| :--- | :--- | :--- |
| `text` | `str` | Generated output text from the AI. |
| `provider` | `str` | Provider ID that handled the request (e.g. `"openai"`, `"gemini"`). |
| `model` | `str` | Specific model used for the generation. |
| `usage` | `Optional[AIUsage]` | Token counts (`prompt_tokens`, `completion_tokens`, `total_tokens`). |
| `success` | `bool` | `True` if successful, `False` on error. |
| `error_message` | `Optional[str]` | User-friendly explanation if `success` is `False`. |

---

## 4. How Features Should Call `AIService`

When adding future AI features (e.g., Knowledge Document Summarization, Auto-Tagging, or Asset Description):

```python
from models.ai import AIRequest, AIContext

# 1. Retrieve AIService from AppContext
ai_service = context.ai_service

# 2. Check readiness if desired (optional, generate() handles disabled state gracefully)
if not ai_service.is_enabled():
    print("AI features are currently disabled.")

# 3. Construct the request
request = AIRequest(
    system_instruction="You are a creative game design assistant.",
    prompt=f"Summarize the key plot points in the following note:\n\n{doc.content}",
    context=AIContext(
        project_name="Project Alpha",
        document_ids=[doc.id],
        document_titles=[doc.title],
    ),
    temperature=0.5,
)

# 4. Generate response
response = ai_service.generate(request)

# 5. Handle output safely
if response.success:
    print("Summary:", response.text)
else:
    print("AI Generation failed:", response.error_message)
```

---

## 5. Adding a New Provider

To integrate a new provider:

1. Create a new subclass of `BaseAIProvider` in `services/ai/providers/`:
   ```python
   from services.ai.providers.base_provider import BaseAIProvider
   from models.ai import AIRequest, AIResponse, AIConfig

   class CustomProvider(BaseAIProvider):
       def __init__(self):
           super().__init__(
               provider_id="my_custom",
               display_name="My Custom AI",
               default_model="custom-v1",
           )

       def generate(self, request: AIRequest, config: AIConfig) -> AIResponse:
           # Format payload and execute HTTP request
           ...
   ```
2. Register the provider in `AIService._register_default_providers()` or dynamically via `ai_service.register_provider(CustomProvider())`.
