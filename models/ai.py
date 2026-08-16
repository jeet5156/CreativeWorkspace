"""Data models for CreativeWorkspace AI Infrastructure & Provider Layer."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class AIProviderType(str, Enum):
    """Supported AI provider identifiers."""
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    LOCAL = "local"
    MOCK = "mock"


@dataclass
class AIMessage:
    """Individual chat/conversation message."""
    role: str = "user"  # "user", "assistant", "system"
    content: str = ""
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIMessage":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            name=data.get("name"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class AIContext:
    """Structured CreativeWorkspace domain context attached to an AI request."""
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    document_id: Optional[str] = None
    document_ids: List[str] = field(default_factory=list)
    document_titles: List[str] = field(default_factory=list)
    asset_ids: List[str] = field(default_factory=list)
    lab_node_ids: List[str] = field(default_factory=list)
    workspace_context: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIContext":
        return cls(
            project_id=data.get("project_id"),
            project_name=data.get("project_name"),
            document_id=data.get("document_id"),
            document_ids=list(data.get("document_ids", [])),
            document_titles=list(data.get("document_titles", [])),
            asset_ids=list(data.get("asset_ids", [])),
            lab_node_ids=list(data.get("lab_node_ids", [])),
            workspace_context=data.get("workspace_context"),
            extra=dict(data.get("extra", {})),
        )


@dataclass
class AIRequest:
    """Provider-agnostic request model sent to AIService."""
    prompt: str = ""
    messages: List[AIMessage] = field(default_factory=list)
    system_instruction: Optional[str] = None
    context: Optional[AIContext] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stop_sequences: List[str] = field(default_factory=list)
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def get_effective_messages(self) -> List[AIMessage]:
        """Return full list of messages, inserting prompt as user message if messages list is empty."""
        if self.messages:
            return list(self.messages)
        if self.prompt:
            return [AIMessage(role="user", content=self.prompt)]
        return []

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.messages:
            d["messages"] = [m.to_dict() if isinstance(m, AIMessage) else m for m in self.messages]
        if self.context and isinstance(self.context, AIContext):
            d["context"] = self.context.to_dict()
        return d


@dataclass
class AIUsage:
    """Token / resource usage stats."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIResponse:
    """Provider-agnostic response returned from AIService."""
    text: str = ""
    provider: str = ""
    model: str = ""
    usage: Optional[AIUsage] = None
    success: bool = True
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.usage and isinstance(self.usage, AIUsage):
            d["usage"] = self.usage.to_dict()
        return d


@dataclass
class AIConfig:
    """Persistent local AI configuration."""
    enabled: bool = False
    active_provider: str = "openai"
    model_overrides: Dict[str, str] = field(default_factory=lambda: {
        "openai": "gpt-4o",
        "gemini": "gemini-3.6-flash",
        "claude": "claude-3-5-sonnet-20241022",
        "local": "llama3",
        "mock": "mock-model-v1",
    })
    endpoints: Dict[str, str] = field(default_factory=lambda: {
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "claude": "https://api.anthropic.com/v1",
        "local": "http://localhost:11434/v1",
    })
    api_keys: Dict[str, str] = field(default_factory=dict)  # provider_id -> key
    cached_models: Dict[str, List[str]] = field(default_factory=dict)  # provider_id -> list of discovered models
    temperature: float = 0.7
    max_tokens: int = 2048

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIConfig":
        default_models = {
            "openai": "gpt-4o",
            "gemini": "gemini-3.6-flash",
            "claude": "claude-3-5-sonnet-20241022",
            "local": "llama3",
            "mock": "mock-model-v1",
        }
        default_endpoints = {
            "openai": "https://api.openai.com/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta",
            "claude": "https://api.anthropic.com/v1",
            "local": "http://localhost:11434/v1",
        }

        models = dict(default_models)
        models.update(data.get("model_overrides", {}))

        endpoints = dict(default_endpoints)
        endpoints.update(data.get("endpoints", {}))

        return cls(
            enabled=bool(data.get("enabled", False)),
            active_provider=data.get("active_provider", "openai"),
            model_overrides=models,
            endpoints=endpoints,
            api_keys=dict(data.get("api_keys", {})),
            cached_models=dict(data.get("cached_models", {})),
            temperature=float(data.get("temperature", 0.7)),
            max_tokens=int(data.get("max_tokens", 2048)),
        )
