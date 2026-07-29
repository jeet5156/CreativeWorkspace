from pathlib import Path
import shutil
from typing import List
import json
from datetime import datetime
import os

from PySide6.QtCore import QObject, Signal


class AssetService(QObject):
    """Manages asset index and filesystem operations. Emits assets_changed(project, category)
    so UI panels can refresh themselves. Keeps business logic out of UI.
    """

    assets_changed = Signal(object, str)

    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
    AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a"}
    VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    DOC_EXTS = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xlsx", ".pptx"}

    INDEX_FILENAME = ".asset_index.json"

    def __init__(self, project_service):
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
                return []
        else:
            self._indices[project.location] = []
            return []

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
            return self._load_index(project)
        return self._indices[project.location]

    def _friendly_type_for(self, path: Path) -> str:
        ext = path.suffix.lower()
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
    def get_assets(self, project, category: str | None = None):
        """Return list of asset metadata dicts for a project. If category is set, filter by it."""
        assets = self._ensure_index_loaded(project)
        if category:
            return [a for a in assets if a.get("category") == category]
        return list(assets)

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

        # overwrite index
        self._indices[project.location] = entries
        self._save_index(project)
        try:
            self.assets_changed.emit(project, None)
        except Exception:
            pass
        return True

    def import_paths(self, project, section: str, paths: List[str]):
        """
        Import files/folders and update the index. Returns report dict same as before.
        Emits assets_changed(project, section) when done.
        """
        imported = []
        skipped = []
        errors = []

        # Ensure index loaded
        self._ensure_index_loaded(project)
        assets = self._indices[project.location]

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
                for file in src.rglob("*"):
                    if not file.is_file():
                        continue
                    dest_dir = self._determine_dest_dir(project, section, file)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest = dest_dir / file.name
                    res = self._copy_with_duplicate_handling(file, dest, imported, skipped)
                    if isinstance(res, str):
                        errors.append(f"Error copying {file}: {res}")
                    else:
                        if res:
                            # add metadata entry
                            entry = self._make_asset_entry(project, str(dest.resolve()), "Assets" if section == "assets" else section.capitalize())
                            assets.append(entry)

            else:
                dest_dir = self._determine_dest_dir(project, section, src)
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / src.name
                res = self._copy_with_duplicate_handling(src, dest, imported, skipped)
                if isinstance(res, str):
                    errors.append(f"Error copying {src}: {res}")
                else:
                    if res:
                        entry = self._make_asset_entry(project, str(dest.resolve()), "Assets" if section == "assets" else section.capitalize())
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

    def get_asset(self, project, asset_id):
        """Return a single asset metadata dict by id or None."""
        assets = self._ensure_index_loaded(project)
        return next((a for a in assets if a.get("id") == asset_id), None)

