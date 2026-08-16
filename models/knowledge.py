"""Data models for CreativeWorkspace Knowledge subsystem."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
import uuid


@dataclass
class KnowledgeFolder:
    """Represents a hierarchical folder organizing Knowledge documents."""
    id: str = field(default_factory=lambda: f"fld_{uuid.uuid4().hex[:12]}")
    name: str = "New Folder"
    parent_id: Optional[str] = None
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    modified: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeFolder":
        return cls(
            id=data.get("id", f"fld_{uuid.uuid4().hex[:12]}"),
            name=data.get("name", "New Folder"),
            parent_id=data.get("parent_id"),
            created=data.get("created", datetime.now().isoformat()),
            modified=data.get("modified", datetime.now().isoformat()),
        )


@dataclass
class KnowledgeDocument:
    """Represents a structured knowledge document or note with tagging, hierarchy, and future relation anchors."""
    id: str = field(default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}")
    title: str = "Untitled Document"
    content: str = ""
    folder_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    favorite: bool = False
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    modified: str = field(default_factory=lambda: datetime.now().isoformat())

    # Relationship anchors (stable IDs / structured refs)
    project_ids: List[str] = field(default_factory=list)
    library_asset_ids: List[str] = field(default_factory=list)
    project_asset_refs: List[Dict[str, Any]] = field(default_factory=list)
    lab_node_ids: List[str] = field(default_factory=list)
    attachment_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeDocument":
        return cls(
            id=data.get("id", f"doc_{uuid.uuid4().hex[:12]}"),
            title=data.get("title", "Untitled Document"),
            content=data.get("content", ""),
            folder_id=data.get("folder_id"),
            tags=list(data.get("tags", [])),
            favorite=bool(data.get("favorite", False)),
            created=data.get("created", datetime.now().isoformat()),
            modified=data.get("modified", datetime.now().isoformat()),
            project_ids=list(data.get("project_ids", [])),
            library_asset_ids=list(data.get("library_asset_ids", [])),
            project_asset_refs=list(data.get("project_asset_refs", [])),
            lab_node_ids=list(data.get("lab_node_ids", [])),
            attachment_ids=list(data.get("attachment_ids", [])),
        )
