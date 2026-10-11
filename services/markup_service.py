"""Service for managing visual markups and annotations.

Provides local-first, atomic JSON persistence for Markup documents,
safe missing/corrupt file handling, source-image lookup, and annotation CRUD.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from PySide6.QtCore import QObject, Signal

from core.paths import get_shared_markups_dir
from core.storage import atomic_write_json, safe_read_json
from models.markup import MarkupDocument, VALID_ANNOTATION_TYPES


class MarkupService(QObject):
    """Core service for managing Visual Markup documents and image annotations."""

    markup_created = Signal(object)
    markup_updated = Signal(object)
    markup_deleted = Signal(str)
    markups_reloaded = Signal()

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        super().__init__()
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = get_shared_markups_dir()

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir = self.storage_dir / "documents"
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        # In-memory storage: markup_id -> MarkupDocument
        self._markups: Dict[str, MarkupDocument] = {}

        self.reload()

    # -------------------------------------------------------------------------
    # Persistence & Atomic Storage
    # -------------------------------------------------------------------------

    def reload(self):
        """Reload all markup documents from storage."""
        self._markups.clear()

        if self.docs_dir.exists():
            for doc_path in self.docs_dir.glob("*.json"):
                data, err = safe_read_json(doc_path)
                if not err and isinstance(data, dict):
                    try:
                        doc = MarkupDocument.from_dict(data)
                        self._markups[doc.id] = doc
                    except Exception:
                        pass

        try:
            self.markups_reloaded.emit()
        except Exception:
            pass

    def _atomic_write_json(self, target_path: Path, data: Any):
        """Atomically write JSON data to avoid corruption."""
        atomic_write_json(target_path, data)

    def _persist_markup(self, markup: MarkupDocument):
        """Save a single markup document atomically."""
        doc_path = self.docs_dir / f"{markup.id}.json"
        self._atomic_write_json(doc_path, markup.to_dict())


    def _remove_markup_file(self, markup_id: str):
        """Remove a markup document file from storage."""
        doc_path = self.docs_dir / f"{markup_id}.json"
        if doc_path.exists():
            try:
                doc_path.unlink()
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Document CRUD API
    # -------------------------------------------------------------------------

    def create_markup(self, source_reference: Dict[str, Any], name: str = "Untitled Markup") -> MarkupDocument:
        """Create and persist a new MarkupDocument linked to a source asset."""
        now = datetime.now().isoformat()
        doc = MarkupDocument(
            name=name,
            source_reference=dict(source_reference or {}),
            annotations=[],
            created_at=now,
            updated_at=now,
        )
        self._markups[doc.id] = doc
        self._persist_markup(doc)

        try:
            self.markup_created.emit(doc)
        except Exception:
            pass

        return doc

    def get_markup(self, markup_id: str) -> Optional[MarkupDocument]:
        """Retrieve a MarkupDocument by its ID."""
        if not markup_id:
            return None

        if markup_id in self._markups:
            return self._markups[markup_id]

        # Fallback disk check
        doc_path = self.docs_dir / f"{markup_id}.json"
        if doc_path.exists():
            try:
                data = json.loads(doc_path.read_text(encoding="utf-8"))
                doc = MarkupDocument.from_dict(data)
                self._markups[doc.id] = doc
                return doc
            except Exception:
                return None

        return None

    def update_markup(self, markup: MarkupDocument) -> bool:
        """Update and persist an existing MarkupDocument."""
        if not markup or not markup.id:
            return False

        markup.updated_at = datetime.now().isoformat()
        self._markups[markup.id] = markup
        try:
            self._persist_markup(markup)
            self.markup_updated.emit(markup)
            return True
        except Exception:
            return False

    def delete_markup(self, markup_id: str) -> bool:
        """Delete a MarkupDocument by ID."""
        if not markup_id:
            return False

        existed = markup_id in self._markups
        self._markups.pop(markup_id, None)
        self._remove_markup_file(markup_id)

        if existed:
            try:
                self.markup_deleted.emit(markup_id)
            except Exception:
                pass
            return True

        return False

    def list_markups_for_source(self, source_reference: Dict[str, Any]) -> List[MarkupDocument]:
        """Find all markup documents referencing a given source asset."""
        if not source_reference or not isinstance(source_reference, dict):
            return []

        src_type = source_reference.get("source_type")
        results = []

        for doc in self._markups.values():
            doc_src = doc.source_reference
            if not doc_src or not isinstance(doc_src, dict):
                continue

            if src_type and doc_src.get("source_type") != src_type:
                continue

            if src_type == "project_asset":
                # Match project asset: project_id and asset_id or relative_path
                p_match = (
                    doc_src.get("project_id") == source_reference.get("project_id")
                    if "project_id" in source_reference
                    else True
                )
                a_match = False
                if "asset_id" in source_reference and "asset_id" in doc_src:
                    if doc_src.get("asset_id") == source_reference.get("asset_id"):
                        a_match = True
                if not a_match and "relative_path" in source_reference and "relative_path" in doc_src:
                    norm_a = str(doc_src.get("relative_path", "")).replace("\\", "/").strip("/")
                    norm_b = str(source_reference.get("relative_path", "")).replace("\\", "/").strip("/")
                    if norm_a and norm_a == norm_b:
                        a_match = True

                if p_match and a_match:
                    results.append(doc)

            elif src_type == "library_asset":
                # Match library asset: library_asset_id
                lib_id = source_reference.get("library_asset_id")
                if lib_id and doc_src.get("library_asset_id") == lib_id:
                    results.append(doc)

            else:
                # Generic fallback match for arbitrary source references
                is_match = True
                for k, v in source_reference.items():
                    if doc_src.get(k) != v:
                        is_match = False
                        break
                if is_match:
                    results.append(doc)

        return sorted(results, key=lambda d: d.created_at)

    # -------------------------------------------------------------------------
    # Annotation CRUD API
    # -------------------------------------------------------------------------

    def add_annotation(self, markup_id: str, annotation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a new annotation to a markup document and persist."""
        doc = self.get_markup(markup_id)
        if not doc or not isinstance(annotation, dict):
            return None

        ann = dict(annotation)
        if "id" not in ann or not ann["id"]:
            ann["id"] = f"ann_{uuid.uuid4().hex[:8]}"

        doc.annotations.append(ann)
        doc.updated_at = datetime.now().isoformat()

        self._persist_markup(doc)
        try:
            self.markup_updated.emit(doc)
        except Exception:
            pass

        return ann

    def update_annotation(self, markup_id: str, annotation_id: str, changes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update properties of an existing annotation inside a markup document."""
        doc = self.get_markup(markup_id)
        if not doc or not annotation_id or not isinstance(changes, dict):
            return None

        target_ann = None
        for i, ann in enumerate(doc.annotations):
            if ann.get("id") == annotation_id:
                # Merge changes preserving id
                updated = dict(ann)
                updated.update(changes)
                updated["id"] = annotation_id
                doc.annotations[i] = updated
                target_ann = updated
                break

        if target_ann is not None:
            doc.updated_at = datetime.now().isoformat()
            self._persist_markup(doc)
            try:
                self.markup_updated.emit(doc)
            except Exception:
                pass
            return target_ann

        return None

    def remove_annotation(self, markup_id: str, annotation_id: str) -> bool:
        """Remove an annotation from a markup document."""
        doc = self.get_markup(markup_id)
        if not doc or not annotation_id:
            return False

        original_len = len(doc.annotations)
        doc.annotations = [a for a in doc.annotations if a.get("id") != annotation_id]

        if len(doc.annotations) < original_len:
            doc.updated_at = datetime.now().isoformat()
            self._persist_markup(doc)
            try:
                self.markup_updated.emit(doc)
            except Exception:
                pass
            return True

        return False
