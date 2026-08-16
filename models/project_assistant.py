"""Data models for Project AI Assistant and Traceable Sources (Phase 5B)."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class ProjectSourceType(str, Enum):
    """Types of workspace entities attributable as traceable sources in Project AI answers."""
    PROJECT = "project"
    ASSET = "asset"
    LIBRARY_ASSET = "library_asset"
    KNOWLEDGE = "knowledge"
    LAB_BOARD = "lab_board"
    LAB_TASK = "lab_task"


@dataclass
class TraceableSourceItem:
    """Represents a single traceable, clickable entity used to ground an AI response."""
    source_type: str                  # "project", "asset", "library_asset", "knowledge", "lab_board", "lab_task"
    title: str                        # Display title (e.g. "HeroCharacter_v004.blend", "Lore Bible")
    target_id: Optional[str] = None   # Unique identifier (doc_id, board_id, asset_id, etc.)
    target_path: Optional[str] = None # File path or project relative location
    status: Optional[str] = None      # "online", "offline", "missing", "changed", "available"
    badge: Optional[str] = None       # e.g. "v004", "Offline", "⭐ Favorite", "5 nodes"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceableSourceItem":
        return cls(
            source_type=data.get("source_type", "project"),
            title=data.get("title", ""),
            target_id=data.get("target_id"),
            target_path=data.get("target_path"),
            status=data.get("status"),
            badge=data.get("badge"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ProjectAssistantResponse:
    """Structured response returned by ProjectAssistantService."""
    answer: str
    sources: List[TraceableSourceItem] = field(default_factory=list)
    project_name: str = ""
    project_path: str = ""
    success: bool = True
    error_message: str = ""
    raw_response: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": [s.to_dict() for s in self.sources],
            "project_name": self.project_name,
            "project_path": self.project_path,
            "success": self.success,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectAssistantResponse":
        sources_raw = data.get("sources", [])
        return cls(
            answer=data.get("answer", ""),
            sources=[TraceableSourceItem.from_dict(s) for s in sources_raw],
            project_name=data.get("project_name", ""),
            project_path=data.get("project_path", ""),
            success=data.get("success", True),
            error_message=data.get("error_message", ""),
        )
