"""Structured Knowledge Service for CreativeWorkspace.

Local-first, atomic JSON persistence for Knowledge documents and folders,
with nesting, tagging, favorites, basic search, and future relationship hooks.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from PySide6.QtCore import QObject, Signal

from models.knowledge import KnowledgeDocument, KnowledgeFolder

_UNSET = object()


class KnowledgeService(QObject):
    """Core service for managing the local knowledge catalog, folders, and documents."""

    document_created = Signal(object)
    document_updated = Signal(object)
    document_deleted = Signal(str)
    folder_created = Signal(object)
    folder_updated = Signal(object)
    folder_deleted = Signal(str)
    relationship_added = Signal(str, str, object)
    relationship_removed = Signal(str, str, object)
    knowledge_reloaded = Signal()

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        super().__init__()
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / ".creativeworkspace" / "knowledge"

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir = self.storage_dir / "documents"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.folders_file = self.storage_dir / "folders.json"
        self.manifest_file = self.storage_dir / "knowledge_catalog.json"

        # In-memory storage
        self._folders: Dict[str, KnowledgeFolder] = {}
        self._documents: Dict[str, KnowledgeDocument] = {}

        self.reload()

    # -------------------------------------------------------------------------
    # Persistence & Atomic Storage
    # -------------------------------------------------------------------------

    def reload(self):
        """Reload all folders and documents from storage."""
        self._folders.clear()
        self._documents.clear()

        # 1. Load folders
        if self.folders_file.exists():
            try:
                folders_data = json.loads(self.folders_file.read_text(encoding="utf-8"))
                for item in folders_data:
                    fld = KnowledgeFolder.from_dict(item)
                    self._folders[fld.id] = fld
            except Exception:
                pass

        # 2. Load individual document files from docs_dir
        if self.docs_dir.exists():
            for doc_path in self.docs_dir.glob("*.json"):
                try:
                    doc_data = json.loads(doc_path.read_text(encoding="utf-8"))
                    doc = KnowledgeDocument.from_dict(doc_data)
                    self._documents[doc.id] = doc
                except Exception:
                    pass

        try:
            self.knowledge_reloaded.emit()
        except Exception:
            pass

    def _atomic_write_json(self, target_path: Path, data: Any):
        """Atomically write JSON data to avoid corruption during unexpected interrupts."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_file = tempfile.mkstemp(dir=str(target_path.parent), prefix="tmp_k_", suffix=".json")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, str(target_path))
        except Exception:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
            raise

    def _persist_folders(self):
        """Save folder hierarchy atomically."""
        data = [fld.to_dict() for fld in self._folders.values()]
        self._atomic_write_json(self.folders_file, data)

    def _persist_document(self, doc: KnowledgeDocument):
        """Save a single document atomically."""
        doc_path = self.docs_dir / f"{doc.id}.json"
        self._atomic_write_json(doc_path, doc.to_dict())

    def _remove_document_file(self, doc_id: str):
        """Remove a document file from storage."""
        doc_path = self.docs_dir / f"{doc_id}.json"
        if doc_path.exists():
            try:
                doc_path.unlink()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Folder Management
    # -------------------------------------------------------------------------

    def create_folder(self, name: str = "New Folder", parent_id: Optional[str] = None, folder_id: Optional[str] = None) -> KnowledgeFolder:
        """Create and persist a new knowledge folder."""
        if parent_id and parent_id not in self._folders:
            raise ValueError(f"Parent folder '{parent_id}' does not exist.")

        now = datetime.now().isoformat()
        folder = KnowledgeFolder(
            id=folder_id or f"fld_{os.urandom(6).hex()}",
            name=name.strip() or "Untitled Folder",
            parent_id=parent_id,
            created=now,
            modified=now,
        )
        self._folders[folder.id] = folder
        self._persist_folders()

        try:
            self.folder_created.emit(folder)
        except Exception:
            pass

        return folder

    def get_folder(self, folder_id: str) -> Optional[KnowledgeFolder]:
        """Retrieve folder by its ID."""
        return self._folders.get(folder_id)

    def rename_folder(self, folder_id: str, new_name: str) -> Optional[KnowledgeFolder]:
        """Rename an existing folder."""
        folder = self._folders.get(folder_id)
        if not folder:
            return None

        folder.name = new_name.strip() or folder.name
        folder.modified = datetime.now().isoformat()
        self._persist_folders()

        try:
            self.folder_updated.emit(folder)
        except Exception:
            pass

        return folder

    def move_folder(self, folder_id: str, target_parent_id: Optional[str]) -> Optional[KnowledgeFolder]:
        """Move a folder to a new parent folder, with cycle prevention."""
        folder = self._folders.get(folder_id)
        if not folder:
            return None

        if target_parent_id:
            if target_parent_id not in self._folders:
                raise ValueError(f"Target parent folder '{target_parent_id}' does not exist.")
            if target_parent_id == folder_id:
                raise ValueError("Cannot move a folder inside itself.")
            # Check for cycle: target_parent_id must not be a descendant of folder_id
            descendants = set(self.get_descendant_folder_ids(folder_id))
            if target_parent_id in descendants:
                raise ValueError(f"Cannot move folder into its own descendant '{target_parent_id}'.")

        folder.parent_id = target_parent_id
        folder.modified = datetime.now().isoformat()
        self._persist_folders()

        try:
            self.folder_updated.emit(folder)
        except Exception:
            pass

        return folder

    def get_descendant_folder_ids(self, folder_id: str) -> List[str]:
        """Return all direct and indirect descendant folder IDs."""
        descendants = []
        queue = [folder_id]
        while queue:
            curr = queue.pop(0)
            for f in self._folders.values():
                if f.parent_id == curr:
                    descendants.append(f.id)
                    queue.append(f.id)
        return descendants

    def get_folder_path(self, folder_id: str) -> List[KnowledgeFolder]:
        """Get the breadcrumb path of folders from root down to this folder."""
        path = []
        curr_id = folder_id
        visited = set()
        while curr_id and curr_id in self._folders and curr_id not in visited:
            visited.add(curr_id)
            folder = self._folders[curr_id]
            path.append(folder)
            curr_id = folder.parent_id
        path.reverse()
        return path

    def list_folders(self, parent_id: Optional[str] = _UNSET) -> List[KnowledgeFolder]:
        """List folders. If parent_id is specified (including None for root), filters by parent."""
        if parent_id is _UNSET:
            return list(self._folders.values())
        return [f for f in self._folders.values() if f.parent_id == parent_id]

    def delete_folder(self, folder_id: str, safe_mode: bool = True, reparent_children: bool = False) -> bool:
        """Delete a folder safely without deleting external project or library assets.
        
        Args:
            folder_id: ID of the folder to delete.
            safe_mode: If True and reparent_children is False, refuses to delete if folder contains children.
            reparent_children: If True, reparents subfolders and documents to this folder's parent.
        """
        folder = self._folders.get(folder_id)
        if not folder:
            return False

        child_folders = [f for f in self._folders.values() if f.parent_id == folder_id]
        child_docs = [d for d in self._documents.values() if d.folder_id == folder_id]

        if (child_folders or child_docs) and safe_mode and not reparent_children:
            raise ValueError(
                f"Folder '{folder.name}' is not empty ({len(child_folders)} subfolders, {len(child_docs)} documents). "
                "Specify reparent_children=True or delete contents first."
            )

        if reparent_children:
            parent_id = folder.parent_id
            for cf in child_folders:
                cf.parent_id = parent_id
                cf.modified = datetime.now().isoformat()
            for cd in child_docs:
                cd.folder_id = parent_id
                cd.modified = datetime.now().isoformat()
                self._persist_document(cd)
        elif not safe_mode:
            # Cascade delete knowledge children (strictly within knowledge catalog)
            for cd in child_docs:
                self.delete_document(cd.id)
            for cf in child_folders:
                self.delete_folder(cf.id, safe_mode=False, reparent_children=False)

        del self._folders[folder_id]
        self._persist_folders()

        try:
            self.folder_deleted.emit(folder_id)
        except Exception:
            pass

        return True

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    def create_document(
        self,
        title: str = "Untitled Document",
        content: str = "",
        folder_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        favorite: bool = False,
        project_ids: Optional[List[str]] = None,
        library_asset_ids: Optional[List[str]] = None,
        project_asset_refs: Optional[List[Dict[str, Any]]] = None,
        lab_node_ids: Optional[List[str]] = None,
        attachment_ids: Optional[List[str]] = None,
        doc_id: Optional[str] = None,
    ) -> KnowledgeDocument:
        """Create and persist a new knowledge document."""
        if folder_id and folder_id not in self._folders:
            raise ValueError(f"Folder '{folder_id}' does not exist.")

        now = datetime.now().isoformat()
        # Clean and deduplicate tags
        cleaned_tags = list(dict.fromkeys(t.strip() for t in (tags or []) if t.strip()))

        doc = KnowledgeDocument(
            id=doc_id or f"doc_{os.urandom(6).hex()}",
            title=title.strip() or "Untitled Document",
            content=content,
            folder_id=folder_id,
            tags=cleaned_tags,
            favorite=favorite,
            created=now,
            modified=now,
            project_ids=list(project_ids or []),
            library_asset_ids=list(library_asset_ids or []),
            project_asset_refs=list(project_asset_refs or []),
            lab_node_ids=list(lab_node_ids or []),
            attachment_ids=list(attachment_ids or []),
        )

        self._documents[doc.id] = doc
        self._persist_document(doc)

        try:
            self.document_created.emit(doc)
        except Exception:
            pass

        return doc

    def get_document(self, doc_id: str) -> Optional[KnowledgeDocument]:
        """Get document by ID."""
        return self._documents.get(doc_id)

    def update_document(
        self,
        doc_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        folder_id: Any = _UNSET,
        tags: Optional[List[str]] = None,
        favorite: Optional[bool] = None,
        project_ids: Optional[List[str]] = None,
        library_asset_ids: Optional[List[str]] = None,
        project_asset_refs: Optional[List[Dict[str, Any]]] = None,
        lab_node_ids: Optional[List[str]] = None,
        attachment_ids: Optional[List[str]] = None,
    ) -> Optional[KnowledgeDocument]:
        """Update an existing knowledge document and persist atomically."""
        doc = self._documents.get(doc_id)
        if not doc:
            return None

        if title is not None:
            doc.title = title.strip() or "Untitled Document"
        if content is not None:
            doc.content = content
        if folder_id is not _UNSET:
            if folder_id is not None and folder_id not in self._folders:
                raise ValueError(f"Target folder '{folder_id}' does not exist.")
            doc.folder_id = folder_id
        if tags is not None:
            doc.tags = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
        if favorite is not None:
            doc.favorite = bool(favorite)
        if project_ids is not None:
            doc.project_ids = list(project_ids)
        if library_asset_ids is not None:
            doc.library_asset_ids = list(library_asset_ids)
        if project_asset_refs is not None:
            doc.project_asset_refs = list(project_asset_refs)
        if lab_node_ids is not None:
            doc.lab_node_ids = list(lab_node_ids)
        if attachment_ids is not None:
            doc.attachment_ids = list(attachment_ids)

        doc.modified = datetime.now().isoformat()
        self._persist_document(doc)

        try:
            self.document_updated.emit(doc)
        except Exception:
            pass

        return doc

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the knowledge catalog without affecting external assets."""
        if doc_id not in self._documents:
            return False

        del self._documents[doc_id]
        self._remove_document_file(doc_id)

        try:
            self.document_deleted.emit(doc_id)
        except Exception:
            pass

        return True

    def move_document(self, doc_id: str, target_folder_id: Optional[str]) -> Optional[KnowledgeDocument]:
        """Move a document to another folder or root."""
        return self.update_document(doc_id, folder_id=target_folder_id)

    def list_documents(
        self,
        folder_id: Any = _UNSET,
        recursive: bool = False,
        tag: Optional[str] = None,
        favorite_only: bool = False,
    ) -> List[KnowledgeDocument]:
        """List documents matching folder, tag, or favorite filters."""
        docs = list(self._documents.values())

        if folder_id is not _UNSET:
            if folder_id is None:
                # Root documents
                docs = [d for d in docs if d.folder_id is None]
            elif recursive:
                valid_folder_ids = {folder_id} | set(self.get_descendant_folder_ids(folder_id))
                docs = [d for d in docs if d.folder_id in valid_folder_ids]
            else:
                docs = [d for d in docs if d.folder_id == folder_id]

        if tag:
            tag_lower = tag.strip().lower()
            docs = [d for d in docs if any(t.lower() == tag_lower for t in d.tags)]

        if favorite_only:
            docs = [d for d in docs if d.favorite]

        return docs

    # -------------------------------------------------------------------------
    # Favorites & Tags
    # -------------------------------------------------------------------------

    def set_favorite(self, doc_id: str, favorite: bool = True) -> Optional[KnowledgeDocument]:
        """Set favorite status of a document."""
        return self.update_document(doc_id, favorite=favorite)

    def toggle_favorite(self, doc_id: str) -> Optional[KnowledgeDocument]:
        """Toggle favorite status of a document."""
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        return self.update_document(doc_id, favorite=not doc.favorite)

    def favorite(self, doc_id: str) -> Optional[KnowledgeDocument]:
        """Mark document as favorite."""
        return self.set_favorite(doc_id, True)

    def unfavorite(self, doc_id: str) -> Optional[KnowledgeDocument]:
        """Unmark document as favorite."""
        return self.set_favorite(doc_id, False)

    def add_tag(self, doc_id: str, tag: str) -> Optional[KnowledgeDocument]:
        """Add a tag to a document if not already present."""
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        tag_clean = tag.strip()
        if not tag_clean:
            return doc
        if any(t.lower() == tag_clean.lower() for t in doc.tags):
            return doc
        new_tags = list(doc.tags) + [tag_clean]
        return self.update_document(doc_id, tags=new_tags)

    def remove_tag(self, doc_id: str, tag: str) -> Optional[KnowledgeDocument]:
        """Remove a tag from a document."""
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        tag_clean = tag.strip().lower()
        new_tags = [t for t in doc.tags if t.lower() != tag_clean]
        return self.update_document(doc_id, tags=new_tags)

    def get_all_tags(self) -> List[str]:
        """Get sorted list of all unique tags used across all knowledge documents."""
        unique_tags: Set[str] = set()
        for doc in self._documents.values():
            unique_tags.update(doc.tags)
        return sorted(unique_tags, key=str.lower)

    # -------------------------------------------------------------------------
    # Basic Search
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        tag: Optional[str] = None,
        favorite_only: bool = False,
        folder_id: Any = _UNSET,
        recursive: bool = True,
    ) -> List[KnowledgeDocument]:
        """Search documents across title, content, and tags.
        
        Simple keyword filtering with optional tag, favorite, and folder constraints.
        """
        # Treat None or _UNSET as global search across all folders
        effective_folder_id = _UNSET if (folder_id is None or folder_id is _UNSET) else folder_id

        # Base candidate documents matching folder & favorite filters
        candidates = self.list_documents(
            folder_id=effective_folder_id,
            recursive=recursive,
            tag=tag,
            favorite_only=favorite_only,
        )

        query_clean = query.strip().lower()
        if not query_clean:
            return candidates

        results = []
        for doc in candidates:
            title_str = (getattr(doc, "title", None) or "").lower()
            content_str = (getattr(doc, "content", None) or "").lower()
            tags_list = getattr(doc, "tags", []) or []

            title_match = query_clean in title_str
            content_match = query_clean in content_str
            tag_match = any(query_clean in str(t).lower() for t in tags_list)

            if title_match or content_match or tag_match:
                results.append(doc)

        return results

    # -------------------------------------------------------------------------
    # Relationship Management
    # -------------------------------------------------------------------------

    # 1. Project Relationships
    def add_project_relationship(self, document_id: str, project_id: str) -> Optional[KnowledgeDocument]:
        """Associate a Knowledge document with a Project (idempotent)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        project_id_clean = project_id.strip()
        if not project_id_clean:
            return doc

        if project_id_clean not in doc.project_ids:
            doc.project_ids.append(project_id_clean)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                self.relationship_added.emit(document_id, "project", project_id_clean)
                self.document_updated.emit(doc)
            except Exception:
                pass

        return doc

    def remove_project_relationship(self, document_id: str, project_id: str) -> Optional[KnowledgeDocument]:
        """Remove association between a Knowledge document and a Project (safe no-op)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        project_id_clean = project_id.strip()
        if project_id_clean in doc.project_ids:
            doc.project_ids.remove(project_id_clean)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                self.relationship_removed.emit(document_id, "project", project_id_clean)
                self.document_updated.emit(doc)
            except Exception:
                pass

        return doc

    def get_related_projects(self, document_id: str) -> List[str]:
        """Get all Project IDs associated with a Knowledge document."""
        doc = self._documents.get(document_id)
        if not doc:
            return []
        return list(doc.project_ids)

    def find_documents_for_project(self, project_id: str) -> List[KnowledgeDocument]:
        """Reverse lookup: find all Knowledge documents referencing a Project."""
        project_id_clean = project_id.strip()
        if not project_id_clean:
            return []
        return [d for d in self._documents.values() if project_id_clean in d.project_ids]

    # 2. Global Library Asset Relationships
    def add_library_asset_relationship(self, document_id: str, asset_id: str) -> Optional[KnowledgeDocument]:
        """Associate a Knowledge document with a Global Library Asset ID (idempotent)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        asset_id_clean = asset_id.strip()
        if not asset_id_clean:
            return doc

        if asset_id_clean not in doc.library_asset_ids:
            doc.library_asset_ids.append(asset_id_clean)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                self.relationship_added.emit(document_id, "library_asset", asset_id_clean)
                self.document_updated.emit(doc)
            except Exception:
                pass

        return doc

    def remove_library_asset_relationship(self, document_id: str, asset_id: str) -> Optional[KnowledgeDocument]:
        """Remove association between a Knowledge document and a Library Asset ID (safe no-op)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        asset_id_clean = asset_id.strip()
        if asset_id_clean in doc.library_asset_ids:
            doc.library_asset_ids.remove(asset_id_clean)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                self.relationship_removed.emit(document_id, "library_asset", asset_id_clean)
                self.document_updated.emit(doc)
            except Exception:
                pass

        return doc

    def get_related_library_assets(self, document_id: str) -> List[str]:
        """Get all Library Asset IDs associated with a Knowledge document."""
        doc = self._documents.get(document_id)
        if not doc:
            return []
        return list(doc.library_asset_ids)

    def find_documents_for_library_asset(self, asset_id: str) -> List[KnowledgeDocument]:
        """Reverse lookup: find all Knowledge documents referencing a Library Asset ID."""
        asset_id_clean = asset_id.strip()
        if not asset_id_clean:
            return []
        return [d for d in self._documents.values() if asset_id_clean in d.library_asset_ids]

    # 3. Project-Local Asset Relationships
    def add_project_asset_relationship(
        self,
        document_id: str,
        project_id: str,
        asset_id: str,
        relative_path: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Optional[KnowledgeDocument]:
        """Associate a Knowledge document with a project-local asset (idempotent)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        proj_clean = project_id.strip()
        asset_clean = asset_id.strip()
        if not proj_clean or not asset_clean:
            return doc

        rel_path_clean = relative_path.strip().replace("\\", "/") if relative_path else ""

        # Derive category
        category_clean = (category or "").strip()
        if not category_clean and rel_path_clean:
            top_part = rel_path_clean.split("/")[0] if "/" in rel_path_clean else rel_path_clean
            category_clean = top_part.capitalize()
        if not category_clean:
            category_clean = "Assets"

        # Check if already referenced (match by project_id and asset_id OR matching relative_path OR matching filename in same project)
        def _matches(ref: Dict[str, Any]) -> bool:
            if ref.get("project_id", "").lower() != proj_clean.lower():
                return False
            ref_aid = str(ref.get("asset_id", "")).strip()
            ref_rp = str(ref.get("relative_path", "")).strip().replace("\\", "/")
            if ref_aid and ref_aid == asset_clean:
                return True
            if rel_path_clean and ref_rp and ref_rp.lower() == rel_path_clean.lower():
                return True
            if rel_path_clean and ref_aid and (ref_aid.lower() == rel_path_clean.lower() or ref_rp.lower() == asset_clean.lower()):
                return True
            if rel_path_clean and ref_rp and Path(ref_rp).name.lower() == Path(rel_path_clean).name.lower():
                ref_cat = (ref.get("category") or ref_rp.split("/")[0]).lower()
                new_cat = category_clean.lower()
                if ref_cat == new_cat:
                    return True
            return False

        existing = next((ref for ref in doc.project_asset_refs if _matches(ref)), None)

        if not existing:
            new_ref = {
                "project_id": proj_clean,
                "asset_id": asset_clean,
                "relative_path": rel_path_clean,
                "category": category_clean,
            }
            doc.project_asset_refs.append(new_ref)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                self.relationship_added.emit(document_id, "project_asset", new_ref)
                self.document_updated.emit(doc)
            except Exception:
                pass
        else:
            changed = False
            if rel_path_clean and existing.get("relative_path") != rel_path_clean:
                existing["relative_path"] = rel_path_clean
                changed = True
            if category_clean and existing.get("category") != category_clean:
                existing["category"] = category_clean
                changed = True
            if asset_clean and existing.get("asset_id") != asset_clean:
                existing["asset_id"] = asset_clean
                changed = True

            if changed:
                doc.modified = datetime.now().isoformat()
                self._persist_document(doc)
                try:
                    self.document_updated.emit(doc)
                except Exception:
                    pass

        return doc

    def remove_project_asset_relationship(
        self,
        document_id: str,
        project_id: str,
        asset_id: str,
    ) -> Optional[KnowledgeDocument]:
        """Remove association between a Knowledge document and a project-local asset (safe no-op)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        proj_clean = project_id.strip()
        asset_clean = asset_id.strip().replace("\\", "/")

        def _matches(ref: Dict[str, Any]) -> bool:
            if ref.get("project_id", "").lower() != proj_clean.lower():
                return False
            ref_aid = str(ref.get("asset_id", "")).strip()
            ref_rp = str(ref.get("relative_path", "")).strip().replace("\\", "/")
            if ref_aid and ref_aid == asset_clean:
                return True
            if ref_rp and ref_rp.lower() == asset_clean.lower():
                return True
            if ref_rp and Path(ref_rp).name.lower() == Path(asset_clean).name.lower():
                return True
            return False

        matching = [ref for ref in doc.project_asset_refs if _matches(ref)]

        if matching:
            for m in matching:
                doc.project_asset_refs.remove(m)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                self.relationship_removed.emit(document_id, "project_asset", {"project_id": proj_clean, "asset_id": asset_clean})
                self.document_updated.emit(doc)
            except Exception:
                pass

        return doc

    def reconcile_project_asset_relationship(
        self,
        document_id: Optional[str],
        project_id: str,
        stale_asset_id_or_path: str,
        live_entry: Dict[str, Any],
    ) -> List[KnowledgeDocument]:
        """Reconcile and migrate stale project asset relationships across Knowledge documents to live asset metadata."""
        if not project_id or not live_entry:
            return []

        proj_clean = project_id.strip()
        stale_clean = str(stale_asset_id_or_path or "").strip().replace("\\", "/")
        live_id = str(live_entry.get("id", "")).strip()
        live_rp = str(live_entry.get("relative_path", "")).strip().replace("\\", "/")
        live_cat = live_entry.get("category") or (live_rp.split("/")[0] if "/" in live_rp else "Assets")

        target_docs = [self._documents[document_id]] if (document_id and document_id in self._documents) else list(self._documents.values())
        updated_docs = []

        def _matches(ref: Dict[str, Any]) -> bool:
            if ref.get("project_id", "").lower() != proj_clean.lower():
                return False
            ref_aid = str(ref.get("asset_id", "")).strip()
            ref_rp = str(ref.get("relative_path", "")).strip().replace("\\", "/")
            if stale_clean and (ref_aid == stale_clean or ref_rp.lower() == stale_clean.lower() or Path(ref_rp).name.lower() == Path(stale_clean).name.lower()):
                return True
            if live_id and ref_aid == live_id:
                return True
            if live_rp and (ref_rp.lower() == live_rp.lower() or Path(ref_rp).name.lower() == Path(live_rp).name.lower()):
                return True
            return False

        for doc in target_docs:
            matching = [ref for ref in doc.project_asset_refs if _matches(ref)]
            if not matching:
                continue

            changed = False
            # Deduplicate if multiple matches exist
            primary_ref = matching[0]
            for extra in matching[1:]:
                doc.project_asset_refs.remove(extra)
                changed = True

            if live_id and primary_ref.get("asset_id") != live_id:
                primary_ref["asset_id"] = live_id
                changed = True
            if live_rp and primary_ref.get("relative_path") != live_rp:
                primary_ref["relative_path"] = live_rp
                changed = True
            if live_cat and primary_ref.get("category") != live_cat:
                primary_ref["category"] = live_cat
                changed = True

            if changed:
                doc.modified = datetime.now().isoformat()
                self._persist_document(doc)
                try:
                    self.document_updated.emit(doc)
                except Exception:
                    pass
                updated_docs.append(doc)

        return updated_docs

    def get_related_project_assets(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all Project Asset references associated with a Knowledge document."""
        doc = self._documents.get(document_id)
        if not doc:
            return []
        return [dict(ref) for ref in doc.project_asset_refs]

    def find_documents_for_project_asset(self, project_id: str, asset_id: str) -> List[KnowledgeDocument]:
        """Reverse lookup: find all Knowledge documents referencing a specific project asset."""
        proj_clean = project_id.strip()
        asset_clean = asset_id.strip().replace("\\", "/")
        if not proj_clean or not asset_clean:
            return []

        def _matches(ref: Dict[str, Any]) -> bool:
            if ref.get("project_id", "").lower() != proj_clean.lower():
                return False
            ref_aid = str(ref.get("asset_id", "")).strip()
            ref_rp = str(ref.get("relative_path", "")).strip().replace("\\", "/")
            if ref_aid and ref_aid == asset_clean:
                return True
            if ref_rp and ref_rp.lower() == asset_clean.lower():
                return True
            if ref_rp and Path(ref_rp).name.lower() == Path(asset_clean).name.lower():
                return True
            return False

        results = []
        for d in self._documents.values():
            for ref in d.project_asset_refs:
                if _matches(ref):
                    results.append(d)
                    break
        return results

    # 4. Creative Lab Node Relationships
    def add_lab_node_relationship(
        self,
        document_id: str,
        node_id: str,
        board_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Optional[KnowledgeDocument]:
        """Associate a Knowledge document with a Lab Node ID (idempotent)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        node_id_clean = node_id.strip()
        if not node_id_clean:
            return doc

        if node_id_clean not in doc.lab_node_ids:
            doc.lab_node_ids.append(node_id_clean)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                payload = {"node_id": node_id_clean, "board_id": board_id, "project_id": project_id}
                self.relationship_added.emit(document_id, "lab_node", payload)
                self.document_updated.emit(doc)
            except Exception:
                pass

        return doc

    def remove_lab_node_relationship(self, document_id: str, node_id: str) -> Optional[KnowledgeDocument]:
        """Remove association between a Knowledge document and a Lab Node ID (safe no-op)."""
        doc = self._documents.get(document_id)
        if not doc:
            return None

        node_id_clean = node_id.strip()
        if node_id_clean in doc.lab_node_ids:
            doc.lab_node_ids.remove(node_id_clean)
            doc.modified = datetime.now().isoformat()
            self._persist_document(doc)

            try:
                self.relationship_removed.emit(document_id, "lab_node", node_id_clean)
                self.document_updated.emit(doc)
            except Exception:
                pass

        return doc

    def get_related_lab_nodes(self, document_id: str) -> List[str]:
        """Get all Lab Node IDs associated with a Knowledge document."""
        doc = self._documents.get(document_id)
        if not doc:
            return []
        return list(doc.lab_node_ids)

    def find_documents_for_lab_node(self, node_id: str) -> List[KnowledgeDocument]:
        """Reverse lookup: find all Knowledge documents referencing a Lab Node ID."""
        node_id_clean = node_id.strip()
        if not node_id_clean:
            return []
        return [d for d in self._documents.values() if node_id_clean in d.lab_node_ids]
