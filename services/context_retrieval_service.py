"""AI Context Retrieval Engine for CreativeWorkspace.

Provides fast, provider-independent, metadata/index-based context retrieval
across Knowledge documents, Library asset catalogs, Project-local assets,
Projects, and Lab boards/nodes.

Zero Drive-Wide Scanning Invariant:
Queries inspect only in-memory service models and local JSON index catalogs.
No physical drive scanning, binary file opening, hashing, or network calls occur.
"""

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from PySide6.QtCore import QObject

from models.ai_context import (
    ContextItem,
    ContextQuery,
    ContextResult,
    ContextScope,
    ContextSource,
)


class ContextRetrievalService(QObject):
    """Central engine for gathering, scoring, and formatting workspace context for AI."""

    def __init__(
        self,
        context: Optional[Any] = None,
        knowledge_service: Optional[Any] = None,
        library_service: Optional[Any] = None,
        asset_service: Optional[Any] = None,
        project_service: Optional[Any] = None,
        lab_service: Optional[Any] = None,
    ):
        super().__init__()
        self._context = context
        self._knowledge_service = knowledge_service
        self._library_service = library_service
        self._asset_service = asset_service
        self._project_service = project_service
        self._lab_service = lab_service

    # -------------------------------------------------------------------------
    # Service Accessors
    # -------------------------------------------------------------------------

    @property
    def knowledge_service(self):
        if self._knowledge_service is not None:
            return self._knowledge_service
        if self._context and hasattr(self._context, "knowledge_service"):
            return self._context.knowledge_service
        return None

    @property
    def library_service(self):
        if self._library_service is not None:
            return self._library_service
        if self._context and hasattr(self._context, "library_service"):
            return self._context.library_service
        return None

    @property
    def asset_service(self):
        if self._asset_service is not None:
            return self._asset_service
        if self._context and hasattr(self._context, "asset_service"):
            return self._context.asset_service
        return None

    @property
    def project_service(self):
        if self._project_service is not None:
            return self._project_service
        if self._context and hasattr(self._context, "project_service"):
            return self._context.project_service
        return None

    @property
    def lab_service(self):
        if self._lab_service is not None:
            return self._lab_service
        if self._context and hasattr(self._context, "lab_service"):
            return self._context.lab_service
        return None

    def _get_current_project(self, query: ContextQuery) -> Optional[Any]:
        """Resolve current project from query, project service, or app context."""
        if query.project_id and self.project_service:
            for p in getattr(self.project_service, "projects", []):
                if p.name == query.project_id or getattr(p, "id", None) == query.project_id or p.location == query.project_id:
                    return p
        if self._context and hasattr(self._context, "current_project") and self._context.current_project:
            return self._context.current_project
        if self.project_service and getattr(self.project_service, "projects", None):
            return self.project_service.projects[0]
        return None

    # -------------------------------------------------------------------------
    # Core Retrieval Entrypoint
    # -------------------------------------------------------------------------

    def retrieve(self, query: Optional[ContextQuery] = None) -> ContextResult:
        """Execute non-blocking indexed context retrieval matching query parameters."""
        start_time = time.time()
        if query is None:
            query = ContextQuery()

        scope = query.scope if isinstance(query.scope, ContextScope) else ContextScope(str(query.scope))
        candidates: List[ContextItem] = []

        # 1. Resolve active document relationships if document_id is provided
        active_doc_relations = self._resolve_document_relations(query)

        # 2. Gather candidates per source based on scope and source filters
        sources_to_search = self._determine_sources_for_scope(scope, query.sources)

        if ContextSource.KNOWLEDGE in sources_to_search and self.knowledge_service:
            candidates.extend(self._gather_knowledge_candidates(query, active_doc_relations))

        if ContextSource.LIBRARY_ASSET in sources_to_search and self.library_service:
            candidates.extend(self._gather_library_candidates(query, active_doc_relations))

        if ContextSource.PROJECT_ASSET in sources_to_search and self.asset_service:
            candidates.extend(self._gather_project_asset_candidates(query, active_doc_relations))

        if ContextSource.PROJECT in sources_to_search and self.project_service:
            candidates.extend(self._gather_project_candidates(query, active_doc_relations))

        if ContextSource.LAB_NODE in sources_to_search and self.lab_service:
            candidates.extend(self._gather_lab_candidates(query, active_doc_relations))

        # 3. Filter candidates by min_score and scope constraints
        filtered = [c for c in candidates if c.relevance_score >= query.min_score]

        if scope == ContextScope.RELATED_ONLY:
            filtered = [c for c in filtered if c.is_explicit_relationship]

        # 4. Sort deterministically by relevance score descending
        filtered.sort(key=lambda item: (-item.relevance_score, str(item.source_type), item.title, item.id))

        total_candidates = len(filtered)

        # 5. Apply per-source and total hard limits
        final_items = self._apply_limits(filtered, query)

        elapsed_ms = (time.time() - start_time) * 1000.0

        return ContextResult(
            items=final_items,
            total_candidates=total_candidates,
            query=query,
            scope=scope,
            execution_time_ms=elapsed_ms,
        )

    # -------------------------------------------------------------------------
    # Relationship & Scope Utilities
    # -------------------------------------------------------------------------

    def _resolve_document_relations(self, query: ContextQuery) -> Dict[str, Set[str]]:
        """Extract explicit relationship IDs from the current document or query."""
        relations: Dict[str, Set[str]] = {
            "project_ids": set(),
            "library_asset_ids": set(),
            "project_asset_refs": set(),
            "lab_node_ids": set(),
            "document_ids": set(),
        }

        # Seed from query.explicit_relationships if passed
        if query.explicit_relationships:
            for k, ids in query.explicit_relationships.items():
                if k in relations and isinstance(ids, (list, set, tuple)):
                    relations[k].update(str(x) for x in ids)

        # Seed from active document
        if query.document_id and self.knowledge_service:
            doc = self.knowledge_service.get_document(query.document_id)
            if doc:
                relations["document_ids"].add(doc.id)
                relations["project_ids"].update(str(x) for x in getattr(doc, "project_ids", []))
                relations["library_asset_ids"].update(str(x) for x in getattr(doc, "library_asset_ids", []))
                relations["lab_node_ids"].update(str(x) for x in getattr(doc, "lab_node_ids", []))
                for ref in getattr(doc, "project_asset_refs", []):
                    if isinstance(ref, dict):
                        aid = ref.get("asset_id") or ref.get("relative_path")
                        if aid:
                            relations["project_asset_refs"].add(str(aid))
                    elif isinstance(ref, str):
                        relations["project_asset_refs"].add(ref)

        return relations

    def _determine_sources_for_scope(
        self,
        scope: ContextScope,
        requested_sources: Optional[List[Union[ContextSource, str]]],
    ) -> Set[ContextSource]:
        """Determine allowed sources based on scope and explicit request."""
        if requested_sources:
            parsed = set()
            for s in requested_sources:
                if isinstance(s, ContextSource):
                    parsed.add(s)
                elif isinstance(s, str):
                    try:
                        parsed.add(ContextSource(s))
                    except ValueError:
                        pass
            return parsed

        if scope == ContextScope.LIBRARY:
            return {ContextSource.LIBRARY_ASSET}
        if scope == ContextScope.LAB:
            return {ContextSource.LAB_NODE, ContextSource.LAB_BOARD}
        if scope == ContextScope.PROJECT_AND_ASSETS:
            return {ContextSource.PROJECT, ContextSource.PROJECT_ASSET, ContextSource.LIBRARY_ASSET}
        if scope == ContextScope.CURRENT_DOCUMENT:
            return {
                ContextSource.KNOWLEDGE,
                ContextSource.LIBRARY_ASSET,
                ContextSource.PROJECT_ASSET,
                ContextSource.PROJECT,
                ContextSource.LAB_NODE,
            }

        # WORKSPACE, CURRENT_PROJECT, RELATED_ONLY
        return {
            ContextSource.KNOWLEDGE,
            ContextSource.LIBRARY_ASSET,
            ContextSource.PROJECT_ASSET,
            ContextSource.PROJECT,
            ContextSource.LAB_NODE,
        }

    # -------------------------------------------------------------------------
    # Scoring Algorithm
    # -------------------------------------------------------------------------

    def _score_candidate(
        self,
        title: str,
        description: str,
        tags: List[str],
        path_or_category: str,
        query: ContextQuery,
        is_explicit_rel: bool,
        is_current_proj: bool,
    ) -> Tuple[float, List[str]]:
        """Calculate weighted relevance score and match provenance."""
        score = 0.0
        matched_terms: List[str] = []

        # 1. Explicit Relationship Weight (+100)
        if is_explicit_rel:
            score += 100.0
            matched_terms.append("explicit_relationship")

        # 2. Current Project Weight (+50)
        if is_current_proj:
            score += 50.0
            matched_terms.append("current_project")

        q_str = (query.text or "").strip().lower()
        if not q_str:
            # When no text query is supplied, return base score
            if score == 0.0:
                score = 1.0
            return score, matched_terms

        # Tokenize query
        tokens = [t for t in re.split(r"[\s,._\-]+", q_str) if len(t) >= 2]
        title_lower = (title or "").lower()
        desc_lower = (description or "").lower()
        tags_lower = [t.lower() for t in (tags or [])]
        path_lower = (path_or_category or "").lower()

        # 3. Exact Title / Filename Match (+40)
        if q_str == title_lower or Path(title_lower).stem == q_str:
            score += 40.0
            matched_terms.append(f"exact_title:{q_str}")
        elif q_str in title_lower:
            score += 30.0
            matched_terms.append(f"title_substr:{q_str}")
        elif tokens and all(t in title_lower for t in tokens):
            score += 25.0
            matched_terms.append("title_all_tokens")
        elif any(t in title_lower for t in tokens):
            score += 15.0
            matched_terms.append("title_any_tokens")

        # 4. Tag Match (+30)
        if any(q_str == t for t in tags_lower):
            score += 30.0
            matched_terms.append(f"exact_tag:{q_str}")
        elif any(q_str in t for t in tags_lower):
            score += 25.0
            matched_terms.append(f"tag_substr:{q_str}")
        elif any(any(tok in t for tok in tokens) for t in tags_lower):
            score += 20.0
            matched_terms.append("tag_token_match")

        # 5. Content / Snippet Match (+20)
        if q_str in desc_lower:
            score += 20.0
            matched_terms.append(f"content_substr:{q_str}")
        elif tokens and all(t in desc_lower for t in tokens):
            score += 15.0
            matched_terms.append("content_all_tokens")
        elif any(t in desc_lower for t in tokens):
            score += 10.0
            matched_terms.append("content_any_tokens")

        # 6. Path / Category / Folder Match (+10)
        if q_str in path_lower:
            score += 10.0
            matched_terms.append(f"path_substr:{q_str}")
        elif any(t in path_lower for t in tokens):
            score += 5.0
            matched_terms.append("path_token_match")

        return score, matched_terms

    # -------------------------------------------------------------------------
    # Candidate Gatherers (Indexed / In-Memory only)
    # -------------------------------------------------------------------------

    def _gather_knowledge_candidates(
        self,
        query: ContextQuery,
        relations: Dict[str, Set[str]],
    ) -> List[ContextItem]:
        """Gather and score Knowledge documents without reading arbitrary external files."""
        candidates: List[ContextItem] = []
        if not self.knowledge_service:
            return candidates

        if hasattr(self.knowledge_service, "list_documents"):
            docs = self.knowledge_service.list_documents()
        elif hasattr(self.knowledge_service, "_documents"):
            docs = list(self.knowledge_service._documents.values())
        else:
            docs = []

        curr_proj = self._get_current_project(query)
        curr_proj_id = str(getattr(curr_proj, "id", getattr(curr_proj, "name", ""))) if curr_proj else None

        for doc in docs:
            is_active_doc = (query.document_id and doc.id == query.document_id)
            is_explicit_rel = (
                is_active_doc
                or doc.id in relations["document_ids"]
                or any(pid in relations["project_ids"] for pid in getattr(doc, "project_ids", []))
            )

            if query.scope == ContextScope.CURRENT_DOCUMENT and not is_active_doc and not is_explicit_rel:
                continue

            doc_proj_ids = [str(x) for x in getattr(doc, "project_ids", [])]
            is_curr_proj = bool(curr_proj_id and curr_proj_id in doc_proj_ids)

            if query.scope == ContextScope.CURRENT_PROJECT and curr_proj_id and not is_curr_proj and not is_explicit_rel:
                continue

            if query.filter_tags:
                doc_tags_lower = {t.lower() for t in doc.tags}
                if not any(ft.lower() in doc_tags_lower for ft in query.filter_tags):
                    continue

            score, matched_terms = self._score_candidate(
                title=doc.title,
                description=doc.content[:300] if doc.content else "",
                tags=doc.tags,
                path_or_category=doc.folder_id or "",
                query=query,
                is_explicit_rel=is_explicit_rel,
                is_current_proj=is_curr_proj,
            )

            if score <= 0.0 and query.text:
                continue

            item = ContextItem(
                id=doc.id,
                source_type=ContextSource.KNOWLEDGE,
                title=doc.title,
                description=doc.content[:200] if doc.content else "",
                metadata={
                    "tags": list(doc.tags),
                    "favorite": doc.favorite,
                    "folder_id": doc.folder_id,
                    "project_ids": doc_proj_ids,
                    "library_asset_ids": list(getattr(doc, "library_asset_ids", [])),
                    "lab_node_ids": list(getattr(doc, "lab_node_ids", [])),
                },
                relevance_score=score,
                project_id=doc_proj_ids[0] if doc_proj_ids else None,
                availability="online",
                matched_terms=matched_terms,
                is_explicit_relationship=is_explicit_rel,
            )
            candidates.append(item)

        return candidates

    def _gather_library_candidates(
        self,
        query: ContextQuery,
        relations: Dict[str, Set[str]],
    ) -> List[ContextItem]:
        """Gather and score Library assets from the global catalog without scanning drives."""
        candidates: List[ContextItem] = []
        if not self.library_service:
            return candidates

        assets = self.library_service.query_assets()

        curr_proj = self._get_current_project(query)
        curr_proj_loc = getattr(curr_proj, "location", None)
        curr_proj_id = str(getattr(curr_proj, "id", getattr(curr_proj, "name", ""))) if curr_proj else None

        for asset in assets:
            is_explicit_rel = (
                asset.id in relations["library_asset_ids"]
                or str(asset.id) in relations["library_asset_ids"]
            )

            if query.scope == ContextScope.CURRENT_DOCUMENT and not is_explicit_rel:
                continue

            is_curr_proj = False
            if curr_proj_loc:
                is_curr_proj = any(
                    ref.get("project_location") == curr_proj_loc
                    for ref in getattr(asset, "project_references", [])
                )

            if query.scope == ContextScope.CURRENT_PROJECT and not is_curr_proj and not is_explicit_rel:
                continue

            if query.filter_categories and asset.category:
                if not any(fc.lower() == asset.category.lower() for fc in query.filter_categories):
                    continue

            if query.filter_tags and asset.tags:
                asset_tags_lower = {t.lower() for t in asset.tags}
                if not any(ft.lower() in asset_tags_lower for ft in query.filter_tags):
                    continue

            avail_enum = self.library_service.get_asset_availability(asset)
            avail_raw = avail_enum.value if hasattr(avail_enum, "value") else str(avail_enum)
            avail_str = "offline" if avail_raw.lower() == "offline" else "online"
            if not query.include_offline_assets and avail_str == "offline":
                continue

            score, matched_terms = self._score_candidate(
                title=asset.filename,
                description=asset.notes or asset.friendly_type,
                tags=asset.tags,
                path_or_category=f"{asset.category}/{asset.drive_relative_path}",
                query=query,
                is_explicit_rel=is_explicit_rel,
                is_current_proj=is_curr_proj,
            )

            if score <= 0.0 and query.text:
                continue

            item = ContextItem(
                id=asset.id,
                source_type=ContextSource.LIBRARY_ASSET,
                title=asset.filename,
                description=asset.notes or asset.friendly_type,
                metadata={
                    "category": asset.category,
                    "tags": list(asset.tags),
                    "drive_id": asset.drive_id,
                    "drive_relative_path": asset.drive_relative_path,
                    "version": asset.version,
                    "lod": asset.lod,
                    "is_online": (avail_str == "online"),
                },
                relevance_score=score,
                project_id=curr_proj_id if is_curr_proj else None,
                availability=avail_str,
                path_hint=asset.drive_relative_path,
                matched_terms=matched_terms,
                is_explicit_relationship=is_explicit_rel,
            )
            candidates.append(item)

        return candidates

    def _gather_project_asset_candidates(
        self,
        query: ContextQuery,
        relations: Dict[str, Set[str]],
    ) -> List[ContextItem]:
        """Gather and score Project-local assets from the project asset index."""
        candidates: List[ContextItem] = []
        if not self.asset_service:
            return candidates

        projects = []
        curr_proj = self._get_current_project(query)
        if query.scope in (ContextScope.CURRENT_PROJECT, ContextScope.CURRENT_DOCUMENT) or query.project_id:
            if curr_proj:
                projects = [curr_proj]
        elif self.project_service and getattr(self.project_service, "projects", None):
            projects = list(self.project_service.projects)
        elif curr_proj:
            projects = [curr_proj]

        for proj in projects:
            proj_id = str(getattr(proj, "id", proj.name))
            is_curr_proj = (curr_proj and getattr(curr_proj, "location", None) == getattr(proj, "location", None))

            try:
                assets = self.asset_service.get_assets(proj)
            except Exception:
                assets = []

            for asset in assets:
                aid = str(asset.get("id", ""))
                rel_path = str(asset.get("relative_path", ""))
                filename = str(asset.get("filename", Path(rel_path).name if rel_path else "Asset"))
                category = str(asset.get("category", "Assets"))
                tags = list(asset.get("tags", []))
                notes = str(asset.get("notes", ""))

                is_explicit_rel = (
                    aid in relations["project_asset_refs"]
                    or rel_path in relations["project_asset_refs"]
                    or filename in relations["project_asset_refs"]
                )

                if query.scope == ContextScope.CURRENT_DOCUMENT and not is_explicit_rel:
                    continue

                if query.filter_categories and category:
                    if not any(fc.lower() == category.lower() for fc in query.filter_categories):
                        continue

                if query.filter_tags and tags:
                    tags_lower = {t.lower() for t in tags}
                    if not any(ft.lower() in tags_lower for ft in query.filter_tags):
                        continue

                score, matched_terms = self._score_candidate(
                    title=filename,
                    description=notes or asset.get("friendly_type", ""),
                    tags=tags,
                    path_or_category=f"{category}/{rel_path}",
                    query=query,
                    is_explicit_rel=is_explicit_rel,
                    is_current_proj=is_curr_proj,
                )

                if score <= 0.0 and query.text:
                    continue

                item = ContextItem(
                    id=aid or f"pa_{rel_path}",
                    source_type=ContextSource.PROJECT_ASSET,
                    title=filename,
                    description=notes or asset.get("friendly_type", ""),
                    metadata={
                        "category": category,
                        "tags": tags,
                        "relative_path": rel_path,
                        "project_name": proj.name,
                    },
                    relevance_score=score,
                    project_id=proj_id,
                    availability="online",
                    path_hint=rel_path,
                    matched_terms=matched_terms,
                    is_explicit_relationship=is_explicit_rel,
                )
                candidates.append(item)

        return candidates

    def _gather_project_candidates(
        self,
        query: ContextQuery,
        relations: Dict[str, Set[str]],
    ) -> List[ContextItem]:
        """Gather and score Projects from ProjectService metadata."""
        candidates: List[ContextItem] = []
        if not self.project_service:
            return candidates

        projects = list(getattr(self.project_service, "projects", []))
        curr_proj = self._get_current_project(query)
        curr_proj_id = str(getattr(curr_proj, "id", getattr(curr_proj, "name", ""))) if curr_proj else None

        for proj in projects:
            proj_id = str(getattr(proj, "id", proj.name))
            is_curr_proj = (curr_proj_id and proj_id == curr_proj_id)
            is_explicit_rel = (
                proj_id in relations["project_ids"]
                or proj.name in relations["project_ids"]
            )

            if query.scope == ContextScope.CURRENT_DOCUMENT and not is_explicit_rel:
                continue

            if query.scope == ContextScope.CURRENT_PROJECT and not is_curr_proj and not is_explicit_rel:
                continue

            score, matched_terms = self._score_candidate(
                title=proj.name,
                description=proj.description or proj.project_type,
                tags=[proj.project_type],
                path_or_category=proj.location,
                query=query,
                is_explicit_rel=is_explicit_rel,
                is_current_proj=is_curr_proj,
            )

            if score <= 0.0 and query.text:
                continue

            item = ContextItem(
                id=proj_id,
                source_type=ContextSource.PROJECT,
                title=proj.name,
                description=proj.description or f"{proj.project_type} project",
                metadata={
                    "project_type": proj.project_type,
                    "location": proj.location,
                    "is_pinned": getattr(proj, "is_pinned", False),
                },
                relevance_score=score,
                project_id=proj_id,
                availability="online",
                path_hint=proj.location,
                matched_terms=matched_terms,
                is_explicit_relationship=is_explicit_rel,
            )
            candidates.append(item)

        return candidates

    def _gather_lab_candidates(
        self,
        query: ContextQuery,
        relations: Dict[str, Set[str]],
    ) -> List[ContextItem]:
        """Gather and score Lab nodes and boards from LabService indexes."""
        candidates: List[ContextItem] = []
        if not self.lab_service:
            return candidates

        projects = []
        curr_proj = self._get_current_project(query)
        if query.scope in (ContextScope.CURRENT_PROJECT, ContextScope.CURRENT_DOCUMENT) or query.project_id:
            if curr_proj:
                projects = [curr_proj]
        elif self.project_service and getattr(self.project_service, "projects", None):
            projects = list(self.project_service.projects)
        elif curr_proj:
            projects = [curr_proj]
        else:
            projects = [None]

        for proj in projects:
            proj_id = str(getattr(proj, "id", getattr(proj, "name", "workbench"))) if proj else "workbench"
            is_curr_proj = (curr_proj and proj and getattr(curr_proj, "location", None) == getattr(proj, "location", None))

            try:
                manifest = self.lab_service.get_manifest(proj)
                boards = manifest.get("boards", [])
            except Exception:
                boards = []

            for b in boards:
                bid = b.get("id")
                bname = b.get("name", "Board")
                bdata = {}
                try:
                    boards_dir = self.lab_service.get_boards_dir(proj)
                    board_file = boards_dir / f"{bid}.lab.json"
                    if board_file.exists():
                        import json
                        with open(board_file, "r", encoding="utf-8") as f:
                            bdata = json.load(f)
                except Exception:
                    bdata = {}

                items = bdata.get("items", []) if isinstance(bdata, dict) else []

                for node in items:
                    nid = str(node.get("id", ""))
                    ntitle = str(node.get("name") or node.get("title") or node.get("text") or node.get("type", "Node"))
                    ndesc = str(node.get("text") or node.get("content") or node.get("description") or "")
                    ntype = str(node.get("type", "card"))
                    ntags = list(node.get("tags", []))

                    is_explicit_rel = (
                        nid in relations["lab_node_ids"]
                        or str(node.get("id")) in relations["lab_node_ids"]
                    )

                    if query.scope == ContextScope.CURRENT_DOCUMENT and not is_explicit_rel:
                        continue

                    score, matched_terms = self._score_candidate(
                        title=ntitle,
                        description=ndesc,
                        tags=ntags,
                        path_or_category=f"{bname}/{ntype}",
                        query=query,
                        is_explicit_rel=is_explicit_rel,
                        is_current_proj=is_curr_proj,
                    )

                    if score <= 0.0 and query.text:
                        continue

                    item = ContextItem(
                        id=nid or f"lab_{bid}_{ntitle}",
                        source_type=ContextSource.LAB_NODE,
                        title=ntitle,
                        description=ndesc or f"Lab node in {bname}",
                        metadata={
                            "board_id": bid,
                            "board_name": bname,
                            "node_type": ntype,
                            "tags": ntags,
                            "project_name": getattr(proj, "name", "Workbench") if proj else "Workbench",
                        },
                        relevance_score=score,
                        project_id=proj_id,
                        availability="online",
                        path_hint=f"Lab/{bname}/{ntitle}",
                        matched_terms=matched_terms,
                        is_explicit_relationship=is_explicit_rel,
                    )
                    candidates.append(item)

        return candidates

    # -------------------------------------------------------------------------
    # Hard Limit Enforcement
    # -------------------------------------------------------------------------

    def _apply_limits(self, candidates: List[ContextItem], query: ContextQuery) -> List[ContextItem]:
        """Enforce strict per-source and total item constraints."""
        counts: Dict[Union[ContextSource, str], int] = {
            ContextSource.KNOWLEDGE: 0,
            ContextSource.LIBRARY_ASSET: 0,
            ContextSource.PROJECT_ASSET: 0,
            ContextSource.PROJECT: 0,
            ContextSource.LAB_NODE: 0,
            ContextSource.LAB_BOARD: 0,
        }

        per_source_max: Dict[Union[ContextSource, str], int] = {
            ContextSource.KNOWLEDGE: query.max_knowledge_items,
            ContextSource.LIBRARY_ASSET: query.max_library_assets,
            ContextSource.PROJECT_ASSET: query.max_project_assets,
            ContextSource.PROJECT: query.max_projects,
            ContextSource.LAB_NODE: query.max_lab_nodes,
            ContextSource.LAB_BOARD: query.max_lab_nodes,
        }

        result: List[ContextItem] = []
        for item in candidates:
            if len(result) >= query.max_items:
                break

            stype = item.source_type
            max_for_source = per_source_max.get(stype, 10)
            curr_count = counts.get(stype, 0)

            if curr_count < max_for_source:
                result.append(item)
                counts[stype] = curr_count + 1

        return result
