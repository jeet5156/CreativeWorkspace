"""Structured, provider-independent Project Context models for CreativeWorkspace.

These models aggregate read-only, indexed metadata from ProjectService,
AssetService, LibraryService, KnowledgeService, and LabService.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class ProjectKnowledgeSummary:
    """Summary of Knowledge base documents associated with a project."""
    total_notes: int = 0
    favorite_notes: int = 0
    recent_notes: List[Dict[str, Any]] = field(default_factory=list)
    related_notes: List[Dict[str, Any]] = field(default_factory=list)
    folders: List[Dict[str, Any]] = field(default_factory=list)
    categories: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectKnowledgeSummary":
        if not data:
            return cls()
        return cls(
            total_notes=data.get("total_notes", 0),
            favorite_notes=data.get("favorite_notes", 0),
            recent_notes=list(data.get("recent_notes", [])),
            related_notes=list(data.get("related_notes", [])),
            folders=list(data.get("folders", [])),
            categories=dict(data.get("categories", {})),
        )


@dataclass
class ProjectAssetSummary:
    """Summary of project-local assets and their organization."""
    total_assets: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    recent_assets: List[Dict[str, Any]] = field(default_factory=list)
    version_groups: List[Dict[str, Any]] = field(default_factory=list)
    lod_counts: Dict[str, int] = field(default_factory=dict)
    total_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectAssetSummary":
        if not data:
            return cls()
        return cls(
            total_assets=data.get("total_assets", 0),
            by_category=dict(data.get("by_category", {})),
            by_type=dict(data.get("by_type", {})),
            recent_assets=list(data.get("recent_assets", [])),
            version_groups=list(data.get("version_groups", [])),
            lod_counts=dict(data.get("lod_counts", {})),
            total_size=data.get("total_size", 0),
        )


@dataclass
class ProjectLibrarySummary:
    """Summary of Global Asset Library references linked to the project."""
    total_linked_assets: int = 0
    available_assets: int = 0
    offline_assets: int = 0
    missing_assets: int = 0
    possibly_changed_assets: int = 0
    linked_assets: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectLibrarySummary":
        if not data:
            return cls()
        return cls(
            total_linked_assets=data.get("total_linked_assets", 0),
            available_assets=data.get("available_assets", 0),
            offline_assets=data.get("offline_assets", 0),
            missing_assets=data.get("missing_assets", 0),
            possibly_changed_assets=data.get("possibly_changed_assets", 0),
            linked_assets=list(data.get("linked_assets", [])),
        )


@dataclass
class ProjectLabSummary:
    """Summary of spatial Lab boards, nodes, and task items for the project."""
    total_boards: int = 0
    total_nodes: int = 0
    node_types: Dict[str, int] = field(default_factory=dict)
    task_status: Dict[str, int] = field(default_factory=dict)
    recent_boards: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectLabSummary":
        if not data:
            return cls()
        return cls(
            total_boards=data.get("total_boards", 0),
            total_nodes=data.get("total_nodes", 0),
            node_types=dict(data.get("node_types", {})),
            task_status=dict(data.get("task_status", {})),
            recent_boards=list(data.get("recent_boards", [])),
        )


@dataclass
class ProjectAvailabilitySummary:
    """Fast summary of library reference availability for portable drive workflows."""
    online_library_assets: int = 0
    offline_library_assets: int = 0
    missing_library_assets: int = 0
    possibly_changed_assets: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectAvailabilitySummary":
        if not data:
            return cls()
        return cls(
            online_library_assets=data.get("online_library_assets", 0),
            offline_library_assets=data.get("offline_library_assets", 0),
            missing_library_assets=data.get("missing_library_assets", 0),
            possibly_changed_assets=data.get("possibly_changed_assets", 0),
        )


@dataclass
class ProjectVersionSummary:
    """Logical version groupings for project and linked assets."""
    total_versioned_assets: int = 0
    groups: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectVersionSummary":
        if not data:
            return cls()
        return cls(
            total_versioned_assets=data.get("total_versioned_assets", 0),
            groups=list(data.get("groups", [])),
        )


@dataclass
class ProjectContext:
    """Structured, provider-independent model representing aggregated project context."""
    project_id: str = ""
    project_name: str = ""
    project_path: str = ""
    project_type: str = "general"
    created: Optional[str] = None
    modified: Optional[str] = None
    last_opened: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    knowledge_summary: ProjectKnowledgeSummary = field(default_factory=ProjectKnowledgeSummary)
    asset_summary: ProjectAssetSummary = field(default_factory=ProjectAssetSummary)
    library_summary: ProjectLibrarySummary = field(default_factory=ProjectLibrarySummary)
    lab_summary: ProjectLabSummary = field(default_factory=ProjectLabSummary)
    availability_summary: ProjectAvailabilitySummary = field(default_factory=ProjectAvailabilitySummary)
    version_summary: ProjectVersionSummary = field(default_factory=ProjectVersionSummary)
    related_entity_counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_path": self.project_path,
            "project_type": self.project_type,
            "created": self.created,
            "modified": self.modified,
            "last_opened": self.last_opened,
            "metadata": self.metadata,
            "knowledge_summary": self.knowledge_summary.to_dict(),
            "asset_summary": self.asset_summary.to_dict(),
            "library_summary": self.library_summary.to_dict(),
            "lab_summary": self.lab_summary.to_dict(),
            "availability_summary": self.availability_summary.to_dict(),
            "version_summary": self.version_summary.to_dict(),
            "related_entity_counts": self.related_entity_counts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectContext":
        if not data:
            return cls()
        return cls(
            project_id=data.get("project_id", ""),
            project_name=data.get("project_name", ""),
            project_path=data.get("project_path", ""),
            project_type=data.get("project_type", "general"),
            created=data.get("created"),
            modified=data.get("modified"),
            last_opened=data.get("last_opened"),
            metadata=dict(data.get("metadata", {})),
            knowledge_summary=ProjectKnowledgeSummary.from_dict(data.get("knowledge_summary", {})),
            asset_summary=ProjectAssetSummary.from_dict(data.get("asset_summary", {})),
            library_summary=ProjectLibrarySummary.from_dict(data.get("library_summary", {})),
            lab_summary=ProjectLabSummary.from_dict(data.get("lab_summary", {})),
            availability_summary=ProjectAvailabilitySummary.from_dict(data.get("availability_summary", {})),
            version_summary=ProjectVersionSummary.from_dict(data.get("version_summary", {})),
            related_entity_counts=dict(data.get("related_entity_counts", {})),
        )
