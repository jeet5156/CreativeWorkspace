from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Union
import json
from datetime import datetime
import os

from PySide6.QtCore import QObject, Signal


class AssetService(QObject):
    """Manages asset index and filesystem operations. Emits assets_changed(project, category)
    so UI panels can refresh themselves. Keeps business logic out of UI.
    """

    assets_changed = Signal(object, str)

    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp", ".exr", ".hdr", ".tga"}
    MODEL_3D_EXTS = {".fbx", ".obj", ".blend", ".gltf", ".glb", ".usd", ".usda", ".usdc", ".usdz", ".abc", ".stl", ".dae"}
    AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
    VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    DOC_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xlsx", ".pptx"}

    INDEX_FILENAME = ".asset_index.json"

    def __init__(self, project_service=None):
        super().__init__()
        self.project_service = project_service
        # cache of loaded indices: project_location -> list of asset dicts
        self._indices = {}

    # -----------------
    # Index helpers
    # -----------------
    def _index_path(self, project):
        return Path(project.location) / self.INDEX_FILENAME

    def _load_index(self, project):
        idx_path = self._index_path(project)
        if idx_path.exists():
            try:
                with open(idx_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._indices[project.location] = data
                    return data
            except Exception:
                # corrupted index -> reset
                self._indices[project.location] = []
                return self._indices[project.location]
        else:
            self._indices[project.location] = []
            return self._indices[project.location]

    def _save_index(self, project):
        idx_path = self._index_path(project)
        data = self._indices.get(project.location, [])
        try:
            with open(idx_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass

    def _ensure_index_loaded(self, project):
        if project.location not in self._indices:
            idx_path = self._index_path(project)
            if not idx_path.exists():
                self.rebuild_index(project)
            else:
                self._load_index(project)
        return self._indices.get(project.location, [])

    def _friendly_type_for(self, path: Path) -> str:
        ext = path.suffix.lower()
        if ext in self.MODEL_3D_EXTS:
            return f"{ext[1:].upper()} 3D Model"
        if ext in self.IMAGE_EXTS:
            return f"{ext[1:].upper()} Image"
        if ext in self.AUDIO_EXTS:
            return f"{ext[1:].upper()} Audio"
        if ext in self.VIDEO_EXTS:
            return f"{ext[1:].upper()} Video"
        if ext in self.DOC_EXTS:
            return f"{ext[1:].upper()} Document"
        return f"{ext[1:].upper()} File" if ext else "File"

    def _make_asset_entry(self, project, file_abs: str, category: str, date_added: str | None = None):
        project_root = Path(project.location)
        try:
            rel = str(Path(file_abs).relative_to(project_root)).replace("\\", "/")
        except Exception:
            rel = str(Path(file_abs))
        now = datetime.now().isoformat()
        date_added_val = date_added or now
        # determine size if possible (business logic in service)
        size = None
        try:
            size = int(Path(file_abs).stat().st_size)
        except Exception:
            size = 0
        entry = {
            "id": f"{hash((str(project_root), rel, date_added_val))}",
            "filename": Path(rel).name,
            "relative_path": rel,
            "absolute_path": str(Path(file_abs)),
            "category": category,
            "friendly_type": self._friendly_type_for(Path(file_abs)),
            "date_added": date_added_val,
            "created_at": date_added_val,
            "updated_at": date_added_val,
            "size": size,
            "favorite": False,
            "tags": [],
            "notes": "",
        }
        return entry

    # -----------------
    # Public API
    # -----------------
    def get_assets(self, project, category: str | None = None, relative_path: str | None = None):
        """Return list of asset metadata dicts for a project. 
        If category is set, filter by category.
        If relative_path is set, filter by assets residing directly inside that directory.
        """
        assets = self._ensure_index_loaded(project)
        result = list(assets)
        if category:
            cat_lower = category.lower()
            if cat_lower in ("library_references", "library references", "library_reference"):
                result = [a for a in result if bool(a.get("is_library_reference")) or (a.get("category") or "").lower() in ("library_references", "library references", "library_reference")]
            else:
                result = [a for a in result if (a.get("category") or "").lower() == cat_lower]
        if relative_path:
            target_dir = relative_path.replace("\\", "/").strip("/")
            filtered = []
            for a in result:
                rp = a.get("relative_path", "")
                parent_dir = rp.rsplit("/", 1)[0] if "/" in rp else ""
                if parent_dir == target_dir:
                    filtered.append(a)
            result = filtered
        return result

    def has_index(self, project) -> bool:
        """Return True if the asset index file exists for the given project."""
        return self._index_path(project).exists()

    def rebuild_index(self, project, force: bool = False):
        """Scan project folders (Assets, References, Renders, Exports) and build the index.
        If force is False and an index already exists, this is a no-op.
        After rebuilding, the index is saved and assets_changed is emitted.
        """
        idx_path = self._index_path(project)
        if idx_path.exists() and not force:
            # Nothing to do
            return True

        # Preserve existing library references
        existing_refs = [a for a in self._indices.get(project.location, []) if a.get("is_library_reference")]

        project_root = Path(project.location)
        folders = ["Assets", "References", "Renders", "Exports"]
        entries = []
        seen = set()

        for folder in folders:
            folder_path = project_root / folder
            if not folder_path.exists():
                continue
            for file in folder_path.rglob("*"):
                if not file.is_file():
                    continue
                try:
                    rel = str(file.relative_to(project_root)).replace("\\", "/")
                except Exception:
                    rel = str(file)
                if rel in seen:
                    continue
                seen.add(rel)
                # determine category by top-level folder
                top = Path(rel).parts[0] if len(Path(rel).parts) > 0 else folder
                category = top.capitalize() if top else "Assets"
                mtime_iso = datetime.fromtimestamp(file.stat().st_mtime).isoformat()
                entry = self._make_asset_entry(project, str(file.resolve()), category, date_added=mtime_iso)
                entries.append(entry)

        # Merge preserved library references
        entries.extend(existing_refs)

        # overwrite index
        self._indices[project.location] = entries
        self._save_index(project)
        try:
            self.assets_changed.emit(project, None)
        except Exception:
            pass
        return True

    def import_paths(self, project, section: str, paths: List[str], target_rel_path: str | None = None, preserve_hierarchy: bool = True):
        """
        Import files/folders and update the index. Returns report dict.
        If target_rel_path is provided (e.g. "Assets/Hero"), imports files directly into that directory.
        If preserve_hierarchy is True (default), maintains subfolder directory structures for directory imports.
        Emits assets_changed(project, section) when done.
        """
        imported = []
        skipped = []
        errors = []

        # Ensure index loaded
        self._ensure_index_loaded(project)
        assets = self._indices[project.location]

        norm_target_rel = str(target_rel_path).replace("\\", "/").strip("/") if target_rel_path else None

        for p in paths:
            src = Path(p)

            if not src.exists():
                errors.append(f"Source does not exist: {p}")
                continue

            # Prevent importing project folder into itself
            try:
                project_root = Path(project.location).resolve()
                if project_root in src.resolve().parents or project_root == src.resolve():
                    errors.append(f"Skipped project folder itself: {p}")
                    continue
            except Exception:
                pass

            if src.is_dir():
                if norm_target_rel:
                    base_dest = Path(project.location) / norm_target_rel
                else:
                    base_dest = self._determine_dest_dir(project, section, src)

                # Ensure imported directory itself is created
                dest_root_folder = base_dest / src.name
                dest_root_folder.mkdir(parents=True, exist_ok=True)

                for item in src.rglob("*"):
                    rel_sub = item.relative_to(src.parent)
                    dest = base_dest / rel_sub

                    if item.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                        continue

                    if item.is_file():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        res = self._copy_with_duplicate_handling(item, dest, imported, skipped)
                        if isinstance(res, str):
                            errors.append(f"Error copying {item}: {res}")
                        else:
                            if res:
                                rel = str(dest.relative_to(Path(project.location))).replace('\\', '/')
                                top = rel.split('/')[0] if '/' in rel else None
                                cat = top.capitalize() if top else ("Assets" if section == "assets" else section.capitalize())
                                entry = self._make_asset_entry(project, str(dest.resolve()), cat)
                                assets.append(entry)

            else:
                if norm_target_rel:
                    dest_dir = Path(project.location) / norm_target_rel
                else:
                    dest_dir = self._determine_dest_dir(project, section, src)
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                res = self._copy_with_duplicate_handling(src, dest, imported, skipped)
                if isinstance(res, str):
                    errors.append(f"Error copying {src}: {res}")
                else:
                    if res:
                        rel = str(dest.relative_to(Path(project.location))).replace('\\', '/')
                        top = rel.split('/')[0] if '/' in rel else None
                        cat = top.capitalize() if top else ("Assets" if section == "assets" else section.capitalize())
                        entry = self._make_asset_entry(project, str(dest.resolve()), cat)
                        assets.append(entry)

        # save index
        self._save_index(project)

        # emit change
        try:
            self.assets_changed.emit(project, section)
        except Exception:
            pass

        return {"imported": imported, "skipped": skipped, "errors": errors}

    def _determine_dest_dir(self, project, section: str, src_path: Path) -> Path:
        base = Path(project.location)

        if section == "references":
            return base / "References"

        if section == "assets":
            ext = src_path.suffix.lower()

            if ext in self.IMAGE_EXTS:
                return base / "Assets" / "Images"

            if ext in self.AUDIO_EXTS:
                return base / "Assets" / "Audio"

            if ext in self.VIDEO_EXTS:
                return base / "Assets" / "Video"

            if ext in self.DOC_EXTS:
                return base / "Assets" / "Documents"

            return base / "Assets"

        return base / section.capitalize()

    def _copy_with_duplicate_handling(self, src: Path, dest: Path, imported: List[str], skipped: List[str]):
        try:
            if dest.exists():
                if dest.stat().st_size == src.stat().st_size:
                    skipped.append(str(dest))
                    return False

                stem = dest.stem
                suffix = dest.suffix
                parent = dest.parent
                i = 1
                while True:
                    candidate = parent / f"{stem}_{i}{suffix}"
                    if not candidate.exists():
                        dest = candidate
                        break
                    i += 1

            shutil.copy2(src, dest)
            imported.append(str(dest))
            return True

        except Exception as e:
            return str(e)

    # -----------------
    # Asset operations
    # -----------------
    def open_asset(self, project, asset_id):
        assets = self._ensure_index_loaded(project)
        entry = next((a for a in assets if a.get("id") == asset_id), None)
        if not entry:
            return False
        abs_path = Path(entry.get("absolute_path")) if entry.get("absolute_path") else Path(project.location) / entry["relative_path"]
        try:
            if os.name == 'nt':
                os.startfile(str(abs_path))
            else:
                import subprocess
                subprocess.Popen(['xdg-open' if os.name == 'posix' else 'open', str(abs_path)])
            return True
        except Exception:
            return False

    def open_containing_folder(self, project, asset_id):
        assets = self._ensure_index_loaded(project)
        entry = next((a for a in assets if a.get("id") == asset_id), None)
        if not entry and str(asset_id).startswith("seq_"):
            real_id = str(asset_id)[4:]
            entry = next((a for a in assets if a.get("id") == real_id), None)
        if not entry:
            return False
        abs_path = Path(entry.get("absolute_path")) if entry.get("absolute_path") else Path(project.location) / entry["relative_path"]
        folder = abs_path.parent
        try:
            if os.name == 'nt':
                os.startfile(str(folder))
            else:
                import subprocess
                subprocess.Popen(['xdg-open' if os.name == 'posix' else 'open', str(folder)])
            return True
        except Exception:
            return False

    def delete_asset(self, project, asset_id):
        assets = self._ensure_index_loaded(project)
        idx = next((i for i, a in enumerate(assets) if a.get("id") == asset_id), None)
        if idx is None:
            return False
        entry = assets.pop(idx)
        abs_path = Path(entry.get("absolute_path")) if entry.get("absolute_path") else Path(project.location) / entry["relative_path"]
        try:
            if abs_path.exists():
                abs_path.unlink()
        except Exception:
            pass
        self._save_index(project)
        try:
            self.assets_changed.emit(project, entry.get("category"))
        except Exception:
            pass
        return True

    def delete_assets(self, project, asset_ids: list):
        """Delete multiple assets in a single batch, removing files and updating index once."""
        if not asset_ids:
            return True
        assets = self._ensure_index_loaded(project)
        id_set = set(asset_ids)
        remaining = []
        deleted_entries = []
        for a in assets:
            if a.get("id") in id_set:
                deleted_entries.append(a)
                abs_path = Path(a.get("absolute_path")) if a.get("absolute_path") else Path(project.location) / a.get("relative_path", "")
                try:
                    if abs_path.exists():
                        abs_path.unlink()
                except Exception:
                    pass
            else:
                remaining.append(a)

        self._indices[project.location] = remaining
        self._save_index(project)
        try:
            cat = deleted_entries[0].get("category") if deleted_entries else None
            self.assets_changed.emit(project, cat)
        except Exception:
            pass
        return len(deleted_entries) == len(id_set)

    # -----------------
    # Favorites & Tags
    # -----------------
    def toggle_favorite(self, project, asset_id):
        assets = self._ensure_index_loaded(project)
        entry = next((a for a in assets if a.get("id") == asset_id), None)
        if not entry:
            return False
        entry["favorite"] = not bool(entry.get("favorite"))
        self._save_index(project)
        try:
            self.assets_changed.emit(project, entry.get("category"))
        except Exception:
            pass
        return entry["favorite"]

    def add_tag(self, project, asset_id, tag: str):
        assets = self._ensure_index_loaded(project)
        entry = next((a for a in assets if a.get("id") == asset_id), None)
        if not entry:
            return False
        tags = entry.get("tags") or []
        if tag not in tags:
            tags.append(tag)
            entry["tags"] = tags
            self._save_index(project)
            try:
                self.assets_changed.emit(project, entry.get("category"))
            except Exception:
                pass
        return True

    def remove_tag(self, project, asset_id, tag: str):
        assets = self._ensure_index_loaded(project)
        entry = next((a for a in assets if a.get("id") == asset_id), None)
        if not entry:
            return False
        tags = entry.get("tags") or []
        if tag in tags:
            tags.remove(tag)
            entry["tags"] = tags
            self._save_index(project)
            try:
                self.assets_changed.emit(project, entry.get("category"))
            except Exception:
                pass
        return True
    def rename_asset(self, project, asset_id, new_name):
        assets = self._ensure_index_loaded(project)
        entry = next((a for a in assets if a.get("id") == asset_id), None)
        if not entry:
            return False
        abs_path = Path(project.location) / entry["relative_path"]
        new_path = abs_path.parent / new_name
        try:
            abs_path.rename(new_path)
            # update entry
            entry["filename"] = new_name
            entry["relative_path"] = str(Path(entry["relative_path"]).parent.joinpath(new_name)).replace("\\", "/")
            # update absolute path and timestamps
            entry["absolute_path"] = str(new_path)
            entry["updated_at"] = datetime.now().isoformat()
            self._save_index(project)
            try:
                self.assets_changed.emit(project, entry.get("category"))
            except Exception:
                pass
            return True
        except Exception:
            return False

    def refresh_index(self, project):
        """Reload index from disk and emit assets_changed."""
        self._load_index(project)
        try:
            self.assets_changed.emit(project, None)
        except Exception:
            pass

    def update_asset(self, project, asset_id, updates: dict):
        """Update fields (e.g. tags, notes) on an asset entry and persist index to disk."""
        assets = self._ensure_index_loaded(project)
        entry = next((a for a in assets if a.get("id") == asset_id), None)
        if not entry:
            return False
        for k, v in updates.items():
            entry[k] = v
        entry["updated_at"] = datetime.now().isoformat()
        self._save_index(project)
        return True

    def _is_entry_physically_live(self, project, entry: dict) -> bool:
        """Return True if entry is physically present on disk or is an external Library reference."""
        if not entry:
            return False
        if entry.get("is_library_reference"):
            return True
        p_root = Path(project.location)
        abs_p = entry.get("absolute_path")
        if abs_p and Path(abs_p).exists() and Path(abs_p).is_file():
            return True
        rel_p = entry.get("relative_path")
        if rel_p and (p_root / rel_p).exists() and (p_root / rel_p).is_file():
            return True
        return False

    def get_asset(self, project, asset_id_or_path: str):
        """Return a single asset metadata dict by id, relative_path, or filename, preferring live physical files over stale index entries."""
        if not project or not asset_id_or_path:
            return None
        assets = self._ensure_index_loaded(project)
        target_str = str(asset_id_or_path).strip()
        stale_candidate = None

        # 1. Exact ID match
        for a in assets:
            if str(a.get("id")) == target_str:
                if self._is_entry_physically_live(project, a):
                    return a
                elif stale_candidate is None:
                    stale_candidate = a

        # 2. Normalized relative path match
        norm_target = target_str.replace("\\", "/").strip("/")
        for a in assets:
            rp = (a.get("relative_path") or "").replace("\\", "/").strip("/")
            if rp.lower() == norm_target.lower():
                if self._is_entry_physically_live(project, a):
                    return a
                elif stale_candidate is None:
                    stale_candidate = a

        # 3. Filename match across indexed assets (preferring physically live files)
        candidate_names = set()
        if "." in Path(norm_target).name:
            candidate_names.add(Path(norm_target).name.lower())
        if stale_candidate:
            stale_fn = stale_candidate.get("filename") or Path(stale_candidate.get("relative_path", "")).name
            if stale_fn:
                candidate_names.add(stale_fn.lower())

        if candidate_names:
            for a in assets:
                fn = (a.get("filename") or Path(a.get("relative_path", "")).name).lower()
                if fn in candidate_names:
                    if self._is_entry_physically_live(project, a):
                        return a
                    elif stale_candidate is None:
                        stale_candidate = a

        # 4. Fallback check for file on disk inside project root or standard subfolders
        try:
            p_root = Path(project.location)
            candidate_p = p_root / norm_target
            if candidate_p.exists() and candidate_p.is_file():
                rel = str(candidate_p.relative_to(p_root)).replace("\\", "/")
                # Check if existing index entry matches this relative path
                existing_match = next((a for a in assets if (a.get("relative_path") or "").replace("\\", "/").lower() == rel.lower()), None)
                if existing_match:
                    return existing_match
                top = rel.split("/")[0] if "/" in rel else "Assets"
                cat = top.capitalize()
                return self._make_asset_entry(project, str(candidate_p.resolve()), cat)

            # Search in standard category folders if not directly found
            folders = ["References", "Assets", "Renders", "Exports"]
            search_filenames = [norm_target]
            search_filenames.extend(list(candidate_names))

            for folder in folders:
                for fn_query in search_filenames:
                    f_candidate = p_root / folder / fn_query
                    if f_candidate.exists() and f_candidate.is_file():
                        rel = str(f_candidate.relative_to(p_root)).replace("\\", "/")
                        existing_match = next((a for a in assets if (a.get("relative_path") or "").replace("\\", "/").lower() == rel.lower()), None)
                        if existing_match:
                            return existing_match
                        return self._make_asset_entry(project, str(f_candidate.resolve()), folder)
        except Exception:
            pass

        return stale_candidate

    def get_asset_by_path(self, project, rel_path: str):
        """Lookup asset metadata by relative path."""
        return self.get_asset(project, rel_path)

    def add_library_reference(
        self,
        project,
        library_asset,
        target_category: str = "Library References",
        library_service=None,
    ) -> dict:
        """Reference an existing global Library asset in the current project.

        CRITICAL: Never copies or moves the physical file. The reference
        points directly to the library asset identity (library_asset_id, drive_id, drive_relative_path).
        """
        assets = self._ensure_index_loaded(project)

        # Extract attributes from LibraryAsset model or dict
        if isinstance(library_asset, dict):
            lib_id = library_asset.get("id") or library_asset.get("library_asset_id")
            filename = library_asset.get("filename")
            drive_id = library_asset.get("drive_id")
            drive_rel = library_asset.get("drive_relative_path")
            friendly_type = library_asset.get("friendly_type")
            size = library_asset.get("file_size") or library_asset.get("size", 0)
            tags = library_asset.get("tags", [])
            notes = library_asset.get("notes", "")
        else:
            lib_id = getattr(library_asset, "id", None) or getattr(library_asset, "library_asset_id", None)
            filename = getattr(library_asset, "filename", None)
            drive_id = getattr(library_asset, "drive_id", None)
            drive_rel = getattr(library_asset, "drive_relative_path", None)
            friendly_type = getattr(library_asset, "friendly_type", None)
            size = getattr(library_asset, "file_size", 0)
            tags = getattr(library_asset, "tags", [])
            notes = getattr(library_asset, "notes", "")

        ref_id = f"lib_ref_{lib_id}"
        target_category_norm = target_category.capitalize() if target_category else "References"
        now_iso = datetime.now().isoformat()

        # Check if already referenced in project
        existing = next((a for a in assets if a.get("id") == ref_id or a.get("library_asset_id") == lib_id), None)
        if existing:
            existing["updated_at"] = now_iso
            existing["category"] = target_category_norm
            existing["filename"] = filename
            existing["drive_id"] = drive_id
            existing["drive_relative_path"] = drive_rel
            entry = existing
        else:
            entry = {
                "id": ref_id,
                "filename": filename,
                "relative_path": f"{target_category_norm}/{filename}",
                "category": target_category_norm,
                "is_library_reference": True,
                "library_asset_id": lib_id,
                "drive_id": drive_id,
                "drive_relative_path": drive_rel,
                "friendly_type": friendly_type or self._friendly_type_for(Path(filename)),
                "date_added": now_iso,
                "created_at": now_iso,
                "updated_at": now_iso,
                "size": size,
                "favorite": False,
                "tags": list(tags) if tags else [],
                "notes": notes or "",
            }
            assets.append(entry)

        self._save_index(project)

        if library_service and lib_id and hasattr(library_service, "log_project_reference"):
            try:
                library_service.log_project_reference(lib_id, project.location, project.name, mode="reference")
            except Exception:
                pass

        try:
            self.assets_changed.emit(project, target_category_norm.lower())
        except Exception:
            pass
        return entry

    def copy_library_asset(
        self,
        project,
        library_asset,
        library_service,
        target_section: str = "References",
    ) -> Optional[dict]:
        """Explicitly copy a global Library asset into project-local storage.

        Creates a genuine independent copy on disk and indexes it as a project-local asset.
        """
        src_path = library_service.resolve_asset_path(library_asset)
        if not src_path or not Path(src_path).exists():
            raise FileNotFoundError(f"Source library asset is offline or missing: {src_path}")

        res = self.import_paths(project, target_section.lower(), [str(src_path)])
        if res.get("imported"):
            lib_id = library_asset.get("id") if isinstance(library_asset, dict) else getattr(library_asset, "id", None)
            if lib_id and hasattr(library_service, "log_project_reference"):
                library_service.log_project_reference(lib_id, project.location, project.name, mode="copy")
            return res["imported"][0]
        return None

    def remove_library_reference(
        self,
        project,
        asset_id_or_lib_id: str,
        library_service=None,
    ) -> bool:
        """Remove a Library reference from the project index only.

        CRITICAL: Never deletes or touches the physical file or the global Library catalog.
        """
        assets = self._ensure_index_loaded(project)
        target = None
        for a in assets:
            if a.get("is_library_reference"):
                if a.get("id") == asset_id_or_lib_id or a.get("library_asset_id") == asset_id_or_lib_id:
                    target = a
                    break

        if not target:
            return False

        lib_id = target.get("library_asset_id")
        assets.remove(target)
        self._save_index(project)

        # Notify LibraryService to clean up project reference record
        if library_service and lib_id:
            try:
                library_service.remove_project_reference(lib_id, project.location)
            except Exception:
                pass

        try:
            self.assets_changed.emit(project, "library_references")
        except Exception:
            pass
        return True

