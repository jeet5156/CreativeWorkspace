"""Project Context Service for CreativeWorkspace.

Aggregates structured, provider-independent project context from:
- ProjectService
- AssetService
- LibraryService
- KnowledgeService
- LabService

CRITICAL INVARIANTS:
1. Read-only metadata & index queries only.
2. ZERO physical drive crawling or os.walk scanning during context aggregation.
3. ZERO AI provider calls or embeddings generation.
4. Non-destructive version analysis using AssetIntelligence.
"""

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Signal

from models.project import Project
from models.project_context import (
    ProjectContext,
    ProjectKnowledgeSummary,
    ProjectAssetSummary,
    ProjectLibrarySummary,
    ProjectLabSummary,
    ProjectAvailabilitySummary,
    ProjectVersionSummary,
)
from models.library_models import AssetAvailability
from core.asset_intelligence import detect_version, detect_lod, VERSION_PATTERN


class ProjectContextService(QObject):
    """Single source of truth for aggregating structured Project Context and summary metrics."""

    context_updated = Signal(object)

    def __init__(
        self,
        context: Optional[Any] = None,
        project_service: Optional[Any] = None,
        asset_service: Optional[Any] = None,
        library_service: Optional[Any] = None,
        knowledge_service: Optional[Any] = None,
        lab_service: Optional[Any] = None,
    ):
        super().__init__()
        self._context = context
        self._project_service = project_service
        self._asset_service = asset_service
        self._library_service = library_service
        self._knowledge_service = knowledge_service
        self._lab_service = lab_service

        self._cached_contexts: Dict[str, ProjectContext] = {}

        self._connect_signals()

    # -------------------------------------------------------------------------
    # Service Accessors
    # -------------------------------------------------------------------------

    @property
    def project_service(self):
        if self._project_service is not None:
            return self._project_service
        if self._context and hasattr(self._context, "project_service"):
            return self._context.project_service
        return None

    @property
    def asset_service(self):
        if self._asset_service is not None:
            return self._asset_service
        if self._context and hasattr(self._context, "asset_service"):
            return self._context.asset_service
        return None

    @property
    def library_service(self):
        if self._library_service is not None:
            return self._library_service
        if self._context and hasattr(self._context, "library_service"):
            return self._context.library_service
        return None

    @property
    def knowledge_service(self):
        if self._knowledge_service is not None:
            return self._knowledge_service
        if self._context and hasattr(self._context, "knowledge_service"):
            return self._context.knowledge_service
        return None

    @property
    def lab_service(self):
        if self._lab_service is not None:
            return self._lab_service
        if self._context and hasattr(self._context, "lab_service"):
            return self._context.lab_service
        return None

    # -------------------------------------------------------------------------
    # Signal Wiring
    # -------------------------------------------------------------------------

    def _connect_signals(self):
        """Listen to underlying services for state changes."""
        if self.project_service and hasattr(self.project_service, "project_updated"):
            try:
                self.project_service.project_updated.connect(self._on_project_updated)
            except Exception:
                pass

        if self.asset_service and hasattr(self.asset_service, "assets_changed"):
            try:
                self.asset_service.assets_changed.connect(self._on_assets_changed)
            except Exception:
                pass

        if self.knowledge_service:
            if hasattr(self.knowledge_service, "relationship_added"):
                try:
                    self.knowledge_service.relationship_added.connect(self._on_knowledge_changed)
                except Exception:
                    pass
            if hasattr(self.knowledge_service, "relationship_removed"):
                try:
                    self.knowledge_service.relationship_removed.connect(self._on_knowledge_changed)
                except Exception:
                    pass
            if hasattr(self.knowledge_service, "knowledge_reloaded"):
                try:
                    self.knowledge_service.knowledge_reloaded.connect(self._on_knowledge_changed)
                except Exception:
                    pass

        if self.lab_service:
            if hasattr(self.lab_service, "board_updated"):
                try:
                    self.lab_service.board_updated.connect(self._on_lab_changed)
                except Exception:
                    pass
            if hasattr(self.lab_service, "manifest_updated"):
                try:
                    self.lab_service.manifest_updated.connect(self._on_lab_changed)
                except Exception:
                    pass

        if self.library_service and hasattr(self.library_service, "drive_mounts_changed"):
            try:
                self.library_service.drive_mounts_changed.connect(self._on_library_changed)
            except Exception:
                pass

    def _on_project_updated(self, project):
        if project:
            self.refresh_project_context(project)

    def _on_assets_changed(self, project, category=None):
        if project:
            self.refresh_project_context(project)

    def _on_knowledge_changed(self, *args, **kwargs):
        # Refresh current project context if active
        curr = getattr(self._context, "current_project", None) if self._context else None
        if curr:
            self.refresh_project_context(curr)

    def _on_lab_changed(self, project, *args, **kwargs):
        if project:
            self.refresh_project_context(project)

    def _on_library_changed(self, *args, **kwargs):
        curr = getattr(self._context, "current_project", None) if self._context else None
        if curr:
            self.refresh_project_context(curr)

    # -------------------------------------------------------------------------
    # Project Resolution Helper
    # -------------------------------------------------------------------------

    def _resolve_project(self, project_or_id: Union[str, Project, None]) -> Optional[Project]:
        """Resolve a Project object from an instance or string ID/name/path."""
        if project_or_id is None:
            return None
        if isinstance(project_or_id, Project):
            return project_or_id

        if not self.project_service:
            return None

        clean_id = str(project_or_id).strip()
        for p in self.project_service.all_projects():
            if (
                p.name == clean_id
                or getattr(p, "location", "") == clean_id
                or getattr(p, "id", None) == clean_id
                or str(Path(p.location).resolve()) == str(Path(clean_id).resolve())
            ):
                return p

        # Check if project folder directly loadable
        try:
            p_path = Path(clean_id)
            if p_path.exists() and (p_path / "project.json").exists():
                return self.project_service.load_project(p_path)
        except Exception:
            pass

        return None

    # -------------------------------------------------------------------------
    # Core Aggregation Engine
    # -------------------------------------------------------------------------

    def get_project_context(self, project_or_id: Union[str, Project, None]) -> ProjectContext:
        """Aggregate and return a complete ProjectContext model for the given project.
        
        Guaranteed to be fast, read-only, non-destructive, and free of drive-wide crawling.
        """
        project = self._resolve_project(project_or_id)
        if not project:
            return ProjectContext(
                project_id=str(project_or_id or ""),
                project_name="Unknown Project" if project_or_id else "No Project Selected",
                project_path="",
            )

        proj_loc = getattr(project, "location", "")

        # 1. Project Metadata
        created_str = (
            project.created.isoformat()
            if isinstance(project.created, datetime)
            else str(project.created or "")
        )
        modified_str = (
            project.modified.isoformat()
            if isinstance(project.modified, datetime)
            else str(project.modified or "")
        )
        last_opened_str = (
            project.last_opened.isoformat()
            if isinstance(getattr(project, "last_opened", None), datetime)
            else str(getattr(project, "last_opened", "") or "")
        )

        metadata = {
            "priority": getattr(project, "priority", "medium"),
            "status": getattr(project, "status", "active"),
            "tags": list(getattr(project, "tags", [])),
            "client": getattr(project, "client", ""),
            "client_id": getattr(project, "client_id", ""),
            "repository": getattr(project, "repository", ""),
            "deadline": getattr(project, "deadline", ""),
            "is_pinned": bool(getattr(project, "is_pinned", False)),
            "description": getattr(project, "description", ""),
        }

        # 2. Knowledge Aggregation
        knowledge_summary = self._gather_knowledge_summary(project)

        # 3. Asset & Version Aggregation
        asset_summary, version_summary = self._gather_asset_and_version_summary(project)

        # 4. Library & Availability Aggregation
        library_summary, availability_summary = self._gather_library_and_availability_summary(project)

        # 5. Lab Aggregation
        lab_summary = self._gather_lab_summary(project)

        # 6. Entity Counts
        related_entity_counts = {
            "knowledge": knowledge_summary.total_notes,
            "assets": asset_summary.total_assets,
            "library": library_summary.total_linked_assets,
            "lab": lab_summary.total_boards,
            "available_library": availability_summary.online_library_assets,
            "offline_library": availability_summary.offline_library_assets,
            "missing_library": availability_summary.missing_library_assets,
            "changed_library": availability_summary.possibly_changed_assets,
            "tasks_total": lab_summary.task_status.get("total", 0),
            "tasks_completed": lab_summary.task_status.get("completed", 0),
        }

        ctx = ProjectContext(
            project_id=project.name,
            project_name=project.name,
            project_path=proj_loc,
            project_type=getattr(project, "project_type", "general"),
            created=created_str,
            modified=modified_str,
            last_opened=last_opened_str,
            metadata=metadata,
            knowledge_summary=knowledge_summary,
            asset_summary=asset_summary,
            library_summary=library_summary,
            lab_summary=lab_summary,
            availability_summary=availability_summary,
            version_summary=version_summary,
            related_entity_counts=related_entity_counts,
        )

        self._cached_contexts[proj_loc] = ctx
        return ctx

    def get_project_summary(self, project_or_id: Union[str, Project, None]) -> Dict[str, Any]:
        """Return a lightweight dictionary summary for fast UI / Inspector rendering."""
        ctx = self.get_project_context(project_or_id)
        return {
            "name": ctx.project_name,
            "path": ctx.project_path,
            "type": ctx.project_type,
            "counts": ctx.related_entity_counts,
            "availability": ctx.availability_summary.to_dict(),
            "tasks": ctx.lab_summary.task_status,
            "modified": ctx.modified,
        }

    def refresh_project_context(self, project_or_id: Union[str, Project, None]) -> ProjectContext:
        """Re-aggregate context and emit context_updated signal."""
        ctx = self.get_project_context(project_or_id)
        try:
            self.context_updated.emit(ctx)
        except Exception:
            pass
        return ctx

    # -------------------------------------------------------------------------
    # Knowledge Aggregator
    # -------------------------------------------------------------------------

    def _gather_knowledge_summary(self, project: Project) -> ProjectKnowledgeSummary:
        ks = self.knowledge_service
        if not ks:
            return ProjectKnowledgeSummary()

        proj_name = project.name
        proj_loc = getattr(project, "location", "")

        # Find explicitly associated documents
        # Match by project name or project location in project_ids
        seen_ids = set()
        related_docs = []

        try:
            docs_by_name = ks.find_documents_for_project(proj_name)
            for d in docs_by_name:
                if d.id not in seen_ids:
                    seen_ids.add(d.id)
                    related_docs.append(d)
        except Exception:
            pass

        if proj_loc and proj_loc != proj_name:
            try:
                docs_by_loc = ks.find_documents_for_project(proj_loc)
                for d in docs_by_loc:
                    if d.id not in seen_ids:
                        seen_ids.add(d.id)
                        related_docs.append(d)
            except Exception:
                pass

        total_notes = len(related_docs)
        fav_notes = sum(1 for d in related_docs if bool(getattr(d, "favorite", False) or getattr(d, "is_favorite", False)))

        # Sort recent notes by modified timestamp descending
        sorted_recent = sorted(
            related_docs,
            key=lambda d: getattr(d, "modified", "") or getattr(d, "created", ""),
            reverse=True,
        )

        recent_items = [
            {
                "id": d.id,
                "title": d.title,
                "created": getattr(d, "created", ""),
                "modified": getattr(d, "modified", ""),
                "is_favorite": bool(getattr(d, "favorite", False) or getattr(d, "is_favorite", False)),
                "tags": list(getattr(d, "tags", [])),
                "folder_id": getattr(d, "folder_id", None),
            }
            for d in sorted_recent[:10]
        ]

        related_items = [
            {
                "id": d.id,
                "title": d.title,
                "is_favorite": bool(getattr(d, "favorite", False) or getattr(d, "is_favorite", False)),
                "tags": list(getattr(d, "tags", [])),
            }
            for d in related_docs
        ]

        # Gather folders and category tags for related documents
        category_counts: Dict[str, int] = {}
        folders_list = []
        fld_ids = {d.folder_id for d in related_docs if getattr(d, "folder_id", None)}
        for fid in fld_ids:
            fld = getattr(ks, "_folders", {}).get(fid)
            if fld:
                folders_list.append({"id": fld.id, "name": fld.name})

        for d in related_docs:
            for t in getattr(d, "tags", []):
                category_counts[t] = category_counts.get(t, 0) + 1

        return ProjectKnowledgeSummary(
            total_notes=total_notes,
            favorite_notes=fav_notes,
            recent_notes=recent_items,
            related_notes=related_items,
            folders=folders_list,
            categories=category_counts,
        )

    # -------------------------------------------------------------------------
    # Asset & Version Aggregator
    # -------------------------------------------------------------------------

    def _gather_asset_and_version_summary(self, project: Project) -> tuple[ProjectAssetSummary, ProjectVersionSummary]:
        ast_svc = self.asset_service
        if not ast_svc:
            return ProjectAssetSummary(), ProjectVersionSummary()

        try:
            all_entries = ast_svc.get_assets(project)
            raw_assets = [a for a in all_entries if not bool(a.get("is_library_reference"))]
        except Exception:
            raw_assets = []

        total_assets = len(raw_assets)
        by_category: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        lod_counts: Dict[str, int] = {}
        total_size = 0

        # Sort recent assets by date_added / updated_at
        sorted_assets = sorted(
            raw_assets,
            key=lambda a: a.get("date_added") or a.get("updated_at") or a.get("created_at") or "",
            reverse=True,
        )

        recent_assets = [
            {
                "id": a.get("id"),
                "filename": a.get("filename"),
                "category": a.get("category"),
                "friendly_type": a.get("friendly_type"),
                "date_added": a.get("date_added") or a.get("updated_at"),
                "size": a.get("size", 0),
                "is_library_reference": bool(a.get("is_library_reference")),
            }
            for a in sorted_assets[:15]
        ]

        # Version grouping logic
        # Group assets by logical base stem stripped of version tokens
        version_candidates: Dict[str, List[Dict[str, Any]]] = {}

        for a in raw_assets:
            cat = a.get("category") or "Assets"
            by_category[cat] = by_category.get(cat, 0) + 1

            ftype = a.get("friendly_type") or "File"
            by_type[ftype] = by_type.get(ftype, 0) + 1

            sz = a.get("size") or 0
            if isinstance(sz, (int, float)):
                total_size += int(sz)

            fn = a.get("filename", "")

            # LOD detection
            lod = a.get("lod") or detect_lod(fn)
            if lod:
                lod_counts[lod] = lod_counts.get(lod, 0) + 1

            # Version detection
            ver = a.get("version") or detect_version(fn)
            if ver:
                # Determine logical stem by removing version pattern
                stem = Path(fn).stem
                logical_base = VERSION_PATTERN.sub("", stem).strip("._- ") or stem
                if logical_base not in version_candidates:
                    version_candidates[logical_base] = []
                version_candidates[logical_base].append({
                    "id": a.get("id"),
                    "filename": fn,
                    "version": ver,
                    "category": cat,
                    "date_added": a.get("date_added") or a.get("updated_at", ""),
                })

        version_groups = []
        total_versioned_assets = 0

        for base_name, items in version_candidates.items():
            # Sort versions naturally (e.g. v001, v002, v003)
            def version_sort_key(it):
                v_str = it.get("version", "")
                m = re.search(r'\d+', v_str)
                return int(m.group(0)) if m else 0

            items.sort(key=version_sort_key)
            versions_list = [it["version"] for it in items]
            latest_version = items[-1]["version"] if items else None
            total_versioned_assets += len(items)

            version_groups.append({
                "logical_name": base_name,
                "versions": versions_list,
                "latest": latest_version,
                "count": len(items),
                "items": items,
            })

        asset_summary = ProjectAssetSummary(
            total_assets=total_assets,
            by_category=by_category,
            by_type=by_type,
            recent_assets=recent_assets,
            version_groups=version_groups,
            lod_counts=lod_counts,
            total_size=total_size,
        )

        version_summary = ProjectVersionSummary(
            total_versioned_assets=total_versioned_assets,
            groups=version_groups,
        )

        return asset_summary, version_summary

    # -------------------------------------------------------------------------
    # Library & Availability Aggregator (ZERO External Drive Scans)
    # -------------------------------------------------------------------------

    def _gather_library_and_availability_summary(self, project: Project) -> tuple[ProjectLibrarySummary, ProjectAvailabilitySummary]:
        ast_svc = self.asset_service
        lib_svc = self.library_service

        if not ast_svc:
            return ProjectLibrarySummary(), ProjectAvailabilitySummary()

        try:
            all_assets = ast_svc.get_assets(project)
        except Exception:
            all_assets = []

        # Find all library reference assets in this project
        ref_assets = [a for a in all_assets if bool(a.get("is_library_reference"))]

        total_linked = len(ref_assets)
        available_cnt = 0
        offline_cnt = 0
        missing_cnt = 0
        changed_cnt = 0

        linked_details = []

        for ref in ref_assets:
            lib_id = ref.get("library_asset_id")
            drive_id = ref.get("drive_id")
            drive_rel = ref.get("drive_relative_path")
            fn = ref.get("filename", "")

            status_str = "available"
            if lib_svc:
                try:
                    # Query existing library asset model without disk scans
                    lib_asset = lib_svc.get_asset(lib_id) if lib_id else None
                    if not lib_asset and drive_id and drive_rel:
                        lib_asset = lib_svc.get_asset_by_drive_path(drive_id, drive_rel)

                    if lib_asset:
                        avail = lib_svc.get_asset_availability(lib_asset)
                    else:
                        # Drive mounted check
                        if drive_id and hasattr(lib_svc, "drive_detector") and not lib_svc.drive_detector.is_drive_mounted(drive_id):
                            avail = AssetAvailability.OFFLINE
                        else:
                            avail = AssetAvailability.MISSING

                    if avail == AssetAvailability.AVAILABLE:
                        status_str = "available"
                        available_cnt += 1
                    elif avail == AssetAvailability.OFFLINE:
                        status_str = "offline"
                        offline_cnt += 1
                    elif avail == AssetAvailability.MISSING:
                        status_str = "missing"
                        missing_cnt += 1
                    elif avail == AssetAvailability.POSSIBLY_CHANGED:
                        status_str = "possibly_changed"
                        changed_cnt += 1
                    else:
                        status_str = "available"
                        available_cnt += 1
                except Exception:
                    status_str = "available"
                    available_cnt += 1
            else:
                available_cnt += 1

            linked_details.append({
                "id": ref.get("id"),
                "library_asset_id": lib_id,
                "filename": fn,
                "category": ref.get("category", "References"),
                "status": status_str,
                "drive_id": drive_id,
                "drive_relative_path": drive_rel,
            })

        lib_summary = ProjectLibrarySummary(
            total_linked_assets=total_linked,
            available_assets=available_cnt,
            offline_assets=offline_cnt,
            missing_assets=missing_cnt,
            possibly_changed_assets=changed_cnt,
            linked_assets=linked_details,
        )

        avail_summary = ProjectAvailabilitySummary(
            online_library_assets=available_cnt,
            offline_library_assets=offline_cnt,
            missing_library_assets=missing_cnt,
            possibly_changed_assets=changed_cnt,
        )

        return lib_summary, avail_summary

    # -------------------------------------------------------------------------
    # Lab Aggregator
    # -------------------------------------------------------------------------

    def _gather_lab_summary(self, project: Project) -> ProjectLabSummary:
        lab_svc = self.lab_service
        if not lab_svc:
            return ProjectLabSummary()

        try:
            summary = lab_svc.get_project_summary_metadata(project)
        except Exception:
            summary = {}

        boards_data = summary.get("boards", []) if isinstance(summary, dict) else []
        total_boards = len(boards_data)
        total_nodes = summary.get("total_nodes", 0)
        task_stats = summary.get("task_stats", {})

        # Node types breakdown across loaded boards
        node_types: Dict[str, int] = {}
        recent_boards = []

        for b in boards_data:
            b_id = b.get("id")
            b_name = b.get("name", "Untitled")
            modified_ts = b.get("modified", "")
            item_count = b.get("item_count", 0)

            recent_boards.append({
                "id": b_id,
                "name": b_name,
                "node_count": item_count,
                "modified": modified_ts,
                "favorite": b.get("favorite", False),
                "icon": b.get("icon"),
            })

            # Inspect items in board if loaded
            try:
                b_data = lab_svc.load_board(project, b_id)
                items = b_data.get("items", []) if isinstance(b_data, dict) else []
                for item in items:
                    t = item.get("type", "note.blank")
                    node_types[t] = node_types.get(t, 0) + 1
            except Exception:
                pass

        # Sort recent boards by modified descending
        recent_boards.sort(key=lambda b: b.get("modified", ""), reverse=True)

        task_status_clean = {
            "total": task_stats.get("total", 0),
            "completed": task_stats.get("completed", 0),
            "pending": task_stats.get("pending", 0),
        }

        return ProjectLabSummary(
            total_boards=total_boards,
            total_nodes=total_nodes,
            node_types=node_types,
            task_status=task_status_clean,
            recent_boards=recent_boards[:10],
        )
