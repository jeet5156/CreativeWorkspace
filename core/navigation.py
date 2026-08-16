"""Unified Navigation Target Model and Payload for CreativeWorkspace.

Provides a single, standardized navigation contract across Relationship Chips,
Project Dashboard, Inspector, Home Workspace, and AI Assistants to navigate to
and select exact entities across all workspaces.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Union


class NavigationTargetType(str, Enum):
    """Enumeration of all navigable entity types in CreativeWorkspace."""
    PROJECT = "project"
    PROJECT_ASSET = "project_asset"
    LIBRARY_ASSET = "library_asset"
    KNOWLEDGE_DOC = "knowledge_doc"
    LAB_NODE = "lab_node"
    LAB_BOARD = "lab_board"


@dataclass
class NavigationPayload:
    """Unified payload describing the target entity, location, and selection state."""
    target_type: str
    project_id: Optional[str] = None
    project: Optional[Any] = None
    section: Optional[str] = None  # e.g. "assets", "references", "library_references", "renders", "exports", "lab", "knowledge", "dashboard"
    rel_path: Optional[str] = None  # Folder relative path to navigate into
    target_id: Optional[str] = None  # Exact asset ID, doc ID, board ID, node ID
    sub_target_id: Optional[str] = None  # e.g. node ID inside a board
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_project(cls, project_or_name: Any, section: str = "dashboard") -> "NavigationPayload":
        """Construct payload targeting a project overview or workspace section."""
        p_name = project_or_name.name if hasattr(project_or_name, "name") else str(project_or_name)
        p_obj = project_or_name if hasattr(project_or_name, "name") else None
        return cls(
            target_type=NavigationTargetType.PROJECT.value,
            project_id=p_name,
            project=p_obj,
            section=section,
            target_id=p_name,
        )

    @classmethod
    def for_project_asset(
        cls,
        project_or_name: Any,
        asset_id_or_path: str,
        rel_path: Optional[str] = None,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "NavigationPayload":
        """Construct payload targeting an exact project asset and its containing folder."""
        p_name = project_or_name.name if hasattr(project_or_name, "name") else str(project_or_name)
        p_obj = project_or_name if hasattr(project_or_name, "name") else None

        meta = dict(metadata or {})
        effective_rel_path = rel_path or meta.get("relative_path") or (asset_id_or_path if "/" in str(asset_id_or_path) or "\\" in str(asset_id_or_path) else None)
        normalized_rel = str(effective_rel_path).replace("\\", "/").strip("/") if effective_rel_path else ""

        effective_category = category or meta.get("category")

        # Determine workspace section from relative path or category
        section = "assets"
        folder_subpath = None

        if normalized_rel:
            parts = normalized_rel.split("/")
            top_part = parts[0].lower()
            if top_part in ("references", "renders", "exports", "notes"):
                section = top_part
            elif top_part == "library references" or top_part == "library_references":
                section = "library_references"
            else:
                section = "assets"

            # Compute folder subpath (parent directory of the file)
            if len(parts) > 1:
                folder_subpath = "/".join(parts[:-1])
            else:
                folder_subpath = parts[0]
        elif effective_category:
            cat_l = str(effective_category).lower()
            if cat_l in ("references", "renders", "exports", "notes", "library_references"):
                section = cat_l
                folder_subpath = effective_category.capitalize()
            else:
                section = "assets"
                folder_subpath = "Assets"

        return cls(
            target_type=NavigationTargetType.PROJECT_ASSET.value,
            project_id=p_name,
            project=p_obj,
            section=section,
            rel_path=folder_subpath,
            target_id=str(asset_id_or_path),
            metadata=meta,
        )

    @classmethod
    def for_library_asset(cls, asset_id_or_data: Any, metadata: Optional[Dict[str, Any]] = None) -> "NavigationPayload":
        """Construct payload targeting an exact global Library Asset."""
        target_id = ""
        meta = dict(metadata or {})
        if isinstance(asset_id_or_data, str):
            target_id = asset_id_or_data
        elif isinstance(asset_id_or_data, dict):
            target_id = asset_id_or_data.get("library_asset_id") or asset_id_or_data.get("asset_id") or asset_id_or_data.get("id") or ""
            meta.update(asset_id_or_data)
        elif hasattr(asset_id_or_data, "id"):
            target_id = asset_id_or_data.id

        return cls(
            target_type=NavigationTargetType.LIBRARY_ASSET.value,
            section="assets_lib",
            target_id=str(target_id),
            metadata=meta,
        )

    @classmethod
    def for_knowledge_doc(cls, doc_id_or_data: Any, metadata: Optional[Dict[str, Any]] = None) -> "NavigationPayload":
        """Construct payload targeting an exact Knowledge document."""
        doc_id = ""
        meta = dict(metadata or {})
        if isinstance(doc_id_or_data, str):
            doc_id = doc_id_or_data
        elif isinstance(doc_id_or_data, dict):
            doc_id = doc_id_or_data.get("id") or doc_id_or_data.get("doc_id") or ""
            meta.update(doc_id_or_data)
        elif hasattr(doc_id_or_data, "id"):
            doc_id = doc_id_or_data.id

        return cls(
            target_type=NavigationTargetType.KNOWLEDGE_DOC.value,
            section="knowledge",
            target_id=str(doc_id),
            metadata=meta,
        )

    @classmethod
    def for_lab_node(
        cls,
        node_id: str,
        board_id: Optional[str] = None,
        project_or_name: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "NavigationPayload":
        """Construct payload targeting an exact Lab node on a specific board."""
        p_name = None
        p_obj = None
        if project_or_name:
            p_name = project_or_name.name if hasattr(project_or_name, "name") else str(project_or_name)
            p_obj = project_or_name if hasattr(project_or_name, "name") else None

        return cls(
            target_type=NavigationTargetType.LAB_NODE.value,
            project_id=p_name,
            project=p_obj,
            section="lab",
            target_id=board_id,
            sub_target_id=node_id,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def for_lab_board(
        cls,
        board_id: str,
        project_or_name: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "NavigationPayload":
        """Construct payload targeting an entire Lab board."""
        p_name = None
        p_obj = None
        if project_or_name:
            p_name = project_or_name.name if hasattr(project_or_name, "name") else str(project_or_name)
            p_obj = project_or_name if hasattr(project_or_name, "name") else None

        return cls(
            target_type=NavigationTargetType.LAB_BOARD.value,
            project_id=p_name,
            project=p_obj,
            section="lab",
            target_id=board_id,
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_type": self.target_type,
            "project_id": self.project_id,
            "section": self.section,
            "rel_path": self.rel_path,
            "target_id": self.target_id,
            "sub_target_id": self.sub_target_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NavigationPayload":
        if not data:
            return cls(target_type=NavigationTargetType.PROJECT.value)
        return cls(
            target_type=data.get("target_type", NavigationTargetType.PROJECT.value),
            project_id=data.get("project_id"),
            section=data.get("section"),
            rel_path=data.get("rel_path"),
            target_id=data.get("target_id"),
            sub_target_id=data.get("sub_target_id"),
            metadata=dict(data.get("metadata", {})),
        )
