"""AI Context Retrieval models for CreativeWorkspace.

Provider-agnostic domain models representing context queries, sources, items,
scopes, and compact serialization packages for AI operations.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Set, Union


class ContextSource(str, Enum):
    """Supported metadata sources for context retrieval."""
    KNOWLEDGE = "knowledge"
    LIBRARY_ASSET = "library_asset"
    PROJECT_ASSET = "project_asset"
    PROJECT = "project"
    LAB_NODE = "lab_node"
    LAB_BOARD = "lab_board"


class ContextScope(str, Enum):
    """Boundary scopes controlling retrieval range."""
    CURRENT_DOCUMENT = "current_document"
    CURRENT_PROJECT = "current_project"
    PROJECT_AND_ASSETS = "project_and_assets"
    LIBRARY = "library"
    LAB = "lab"
    WORKSPACE = "workspace"
    RELATED_ONLY = "related_only"


@dataclass
class ContextItem:
    """Individual retrieved metadata entity with scoring and provenance."""
    id: str
    source_type: Union[ContextSource, str]
    title: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    project_id: Optional[str] = None
    availability: Optional[str] = None
    path_hint: Optional[str] = None
    matched_terms: List[str] = field(default_factory=list)
    is_explicit_relationship: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if isinstance(self.source_type, ContextSource):
            data["source_type"] = self.source_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextItem":
        src = data.get("source_type", ContextSource.KNOWLEDGE)
        if isinstance(src, str):
            try:
                src = ContextSource(src)
            except ValueError:
                pass
        return cls(
            id=data.get("id", ""),
            source_type=src,
            title=data.get("title", ""),
            description=data.get("description", ""),
            metadata=dict(data.get("metadata", {})),
            relevance_score=float(data.get("relevance_score", 0.0)),
            project_id=data.get("project_id"),
            availability=data.get("availability"),
            path_hint=data.get("path_hint"),
            matched_terms=list(data.get("matched_terms", [])),
            is_explicit_relationship=bool(data.get("is_explicit_relationship", False)),
        )


@dataclass
class ContextQuery:
    """Configurable query parameterizing context search and ranking."""
    text: str = ""
    scope: Union[ContextScope, str] = ContextScope.WORKSPACE
    project_id: Optional[str] = None
    document_id: Optional[str] = None
    explicit_relationships: Optional[Dict[str, List[Any]]] = None
    filter_tags: List[str] = field(default_factory=list)
    filter_categories: List[str] = field(default_factory=list)
    sources: Optional[List[Union[ContextSource, str]]] = None

    # Hard limits
    max_items: int = 20
    max_knowledge_items: int = 5
    max_library_assets: int = 10
    max_project_assets: int = 10
    max_lab_nodes: int = 10
    max_projects: int = 5
    min_score: float = 0.0
    include_offline_assets: bool = True

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if isinstance(self.scope, ContextScope):
            data["scope"] = self.scope.value
        if self.sources:
            data["sources"] = [s.value if isinstance(s, ContextSource) else str(s) for s in self.sources]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextQuery":
        scope = data.get("scope", ContextScope.WORKSPACE)
        if isinstance(scope, str):
            try:
                scope = ContextScope(scope)
            except ValueError:
                pass

        sources = None
        if data.get("sources") is not None:
            sources = []
            for s in data["sources"]:
                if isinstance(s, str):
                    try:
                        sources.append(ContextSource(s))
                    except ValueError:
                        sources.append(s)
                else:
                    sources.append(s)

        return cls(
            text=data.get("text", ""),
            scope=scope,
            project_id=data.get("project_id"),
            document_id=data.get("document_id"),
            explicit_relationships=data.get("explicit_relationships"),
            filter_tags=list(data.get("filter_tags", [])),
            filter_categories=list(data.get("filter_categories", [])),
            sources=sources,
            max_items=int(data.get("max_items", 20)),
            max_knowledge_items=int(data.get("max_knowledge_items", 5)),
            max_library_assets=int(data.get("max_library_assets", 10)),
            max_project_assets=int(data.get("max_project_assets", 10)),
            max_lab_nodes=int(data.get("max_lab_nodes", 10)),
            max_projects=int(data.get("max_projects", 5)),
            min_score=float(data.get("min_score", 0.0)),
            include_offline_assets=bool(data.get("include_offline_assets", True)),
        )


@dataclass
class ContextResult:
    """Aggregated, ranked retrieval results with high-signal AI serialization."""
    items: List[ContextItem] = field(default_factory=list)
    total_candidates: int = 0
    query: ContextQuery = field(default_factory=ContextQuery)
    scope: Union[ContextScope, str] = ContextScope.WORKSPACE
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [it.to_dict() for it in self.items],
            "total_candidates": self.total_candidates,
            "query": self.query.to_dict() if hasattr(self.query, "to_dict") else self.query,
            "scope": self.scope.value if isinstance(self.scope, ContextScope) else str(self.scope),
            "execution_time_ms": self.execution_time_ms,
        }

    def to_ai_context(self) -> str:
        """Produce a compact, high-signal formatted text structure suitable for AI consumption."""
        if not self.items:
            return ""

        sections: List[str] = []

        # 1. Projects
        project_items = [it for it in self.items if it.source_type in (ContextSource.PROJECT, "project")]
        if project_items:
            lines = ["PROJECT:"]
            for p in project_items:
                lines.append(p.title)
                if p.description:
                    lines.append(f"  Description: {p.description}")
            sections.append("\n".join(lines))

        # 2. Knowledge
        knowledge_items = [it for it in self.items if it.source_type in (ContextSource.KNOWLEDGE, "knowledge")]
        if knowledge_items:
            lines = ["RELATED KNOWLEDGE:"]
            for k in knowledge_items:
                lines.append(f"- {k.title}")
                tags = k.metadata.get("tags")
                if tags:
                    lines.append(f"  Tags: {', '.join(tags)}")
                if k.description and k.description != k.title:
                    lines.append(f"  Summary: {k.description}")
            sections.append("\n".join(lines))

        # 3. Library Assets
        library_items = [it for it in self.items if it.source_type in (ContextSource.LIBRARY_ASSET, "library_asset")]
        if library_items:
            lines = ["LIBRARY ASSETS:"]
            for l in library_items:
                lines.append(f"- {l.title}")
                loc = l.path_hint or l.metadata.get("drive_relative_path")
                if loc:
                    lines.append(f"  Location: {loc}")
                status = l.availability or ("Online" if l.metadata.get("is_online", True) else "Offline")
                lines.append(f"  Status: {status.capitalize()}")
                tags = l.metadata.get("tags")
                if tags:
                    lines.append(f"  Tags: {', '.join(tags)}")
            sections.append("\n".join(lines))

        # 4. Project Assets
        proj_asset_items = [it for it in self.items if it.source_type in (ContextSource.PROJECT_ASSET, "project_asset")]
        if proj_asset_items:
            lines = ["PROJECT ASSETS:"]
            for pa in proj_asset_items:
                lines.append(f"- {pa.title}")
                cat = pa.metadata.get("category")
                if cat:
                    lines.append(f"  Category: {cat}")
                tags = pa.metadata.get("tags")
                if tags:
                    lines.append(f"  Tags: {', '.join(tags)}")
            sections.append("\n".join(lines))

        # 5. Lab
        lab_items = [it for it in self.items if it.source_type in (ContextSource.LAB_NODE, ContextSource.LAB_BOARD, "lab_node", "lab_board")]
        if lab_items:
            lines = ["LAB:"]
            for lb in lab_items:
                board_name = lb.metadata.get("board_name") or "Lab Board"
                lines.append(f"- {board_name}")
                node_type = lb.metadata.get("node_type")
                if node_type:
                    lines.append(f"  Node: {lb.title} ({node_type})")
                else:
                    lines.append(f"  Node: {lb.title}")
                if lb.description and lb.description != lb.title:
                    lines.append(f"  Details: {lb.description}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections).strip()
