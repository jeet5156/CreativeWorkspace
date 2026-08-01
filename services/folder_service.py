from pathlib import Path
import shutil
import os
from PySide6.QtCore import QObject


class FolderService(QObject):
    """Manage folders inside a project.

    Responsibilities:
    - create, rename, delete, move folders
    - update AssetService index to reflect moves/renames/deletes
    - invalidate thumbnails via ThumbnailService
    - record activities via ActivityService
    - emit AssetService.assets_changed indirectly by calling asset_service._save_index and asset_service.assets_changed

    The implementation updates asset entries in-place to preserve asset ids where possible so selections don't break.
    """

    def __init__(self, project_service, asset_service, activity_service=None, thumbnail_service=None):
        super().__init__()
        self.project_service = project_service
        self.asset_service = asset_service
        self.activity_service = activity_service
        self.thumbnail_service = thumbnail_service
        self.IGNORE_FOLDERS = {".git", "__pycache__", ".creativeworkspace", ".DS_Store", "node_modules", ".venv", "venv", ".idea", ".vscode"}

    def _abs_from_rel(self, project, rel: str) -> Path:
        try:
            return Path(project.location) / rel
        except Exception:
            return Path(project.location)

    def create_folder(self, project, parent_rel: str, name: str) -> bool:
        """Create a folder under parent_rel (relative to project). parent_rel may be a top-level section like 'Assets' or a subfolder path (e.g. 'Assets/Images').
        Returns True on success.
        """
        try:
            parent = str(parent_rel or "")
            rel = (Path(parent) / name).as_posix()
            abs_path = self._abs_from_rel(project, rel)
            abs_path.mkdir(parents=True, exist_ok=True)
            try:
                if self.activity_service:
                    self.activity_service.record('create_folder', {'project': project.location, 'folder': rel})
            except Exception:
                pass
            # no index changes required for empty folder, but emit assets_changed so UI refreshes
            try:
                self.asset_service.assets_changed.emit(project, None)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def list_subfolders(self, project, relative_path: str) -> list:
        """Return a list of folder names found inside the given relative path.
        Filters out system/ignored folders.
        """
        try:
            abs_dir = self._abs_from_rel(project, relative_path)
            if not abs_dir.exists() or not abs_dir.is_dir():
                return []
            
            subfolders = []
            for item in abs_dir.iterdir():
                if item.is_dir() and item.name not in self.IGNORE_FOLDERS:
                    subfolders.append(item.name)
            
            return sorted(subfolders, key=str.lower)
        except Exception:
            return []

    def delete_folder(self, project, rel_path: str) -> bool:
        """Delete a folder and all contained assets. Updates index and invalidates thumbnails."""
        try:
            # compute abs
            abs_folder = self._abs_from_rel(project, rel_path)
            if not abs_folder.exists():
                return False
            # remove files/directories
            shutil.rmtree(abs_folder)
            # update index: remove any entries whose relative_path startswith rel_path
            self.asset_service._ensure_index_loaded(project)
            assets = self.asset_service._indices.get(project.location, [])
            removed_categories = set()
            remaining = []
            for e in assets:
                rp = e.get('relative_path') or ''
                if rp.startswith(str(Path(rel_path).as_posix())):
                    removed_categories.add(e.get('category'))
                    # invalidate thumbnail for this asset
                    try:
                        if self.thumbnail_service:
                            self.thumbnail_service.invalidate(project.location, rel_path=rp)
                    except Exception:
                        pass
                    continue
                remaining.append(e)
            self.asset_service._indices[project.location] = remaining
            self.asset_service._save_index(project)
            try:
                if self.activity_service:
                    self.activity_service.record('delete_folder', {'project': project.location, 'folder': rel_path})
            except Exception:
                pass
            # emit change for affected categories (or None)
            try:
                # if multiple categories removed, emit general refresh
                if removed_categories:
                    self.asset_service.assets_changed.emit(project, None)
                else:
                    self.asset_service.assets_changed.emit(project, None)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def rename_folder(self, project, old_rel: str, new_name: str) -> bool:
        """Rename a folder (single-level name change). old_rel is the folder relative path to rename; new_name is the new final segment name.
        Updates index entries for assets inside, preserves ids, updates absolute paths, invalidates thumbnails for old entries and queues generation for new ones.
        """
        try:
            old_path = Path(old_rel)
            parent = old_path.parent
            new_rel = str((parent / new_name).as_posix())
            abs_old = self._abs_from_rel(project, old_rel)
            abs_new = self._abs_from_rel(project, new_rel)
            if not abs_old.exists():
                return False
            # perform filesystem rename
            abs_new_parent = abs_new.parent
            abs_new_parent.mkdir(parents=True, exist_ok=True)
            abs_old.rename(abs_new)
            # update index entries: for entries under old_rel, update relative_path and absolute_path
            self.asset_service._ensure_index_loaded(project)
            assets = self.asset_service._indices.get(project.location, [])
            updated_cats = set()
            for e in assets:
                rp = e.get('relative_path') or ''
                if rp.startswith(str(old_rel).rstrip('/') + '/') or rp == str(old_rel):
                    # compute new relative path
                    try:
                        suffix = Path(rp).relative_to(old_rel).as_posix()
                    except Exception:
                        # fallback
                        suffix = Path(rp).name
                    new_rp = str(Path(new_rel) / suffix).replace('\\', '/')
                    e['relative_path'] = new_rp
                    e['absolute_path'] = str(Path(project.location) / new_rp)
                    e['updated_at'] = __import__('datetime').datetime.now().isoformat()
                    updated_cats.add(e.get('category'))
                    # invalidate old thumbnail and queue new generation
                    try:
                        if self.thumbnail_service:
                            self.thumbnail_service.invalidate(project.location, rel_path=rp)
                            # queue generation for new
                            try:
                                self.thumbnail_service.generate_async(project.location, new_rp, e.get('absolute_path'), None, e.get('id'))
                            except Exception:
                                pass
                    except Exception:
                        pass
            self.asset_service._save_index(project)
            try:
                if self.activity_service:
                    self.activity_service.record('rename_folder', {'project': project.location, 'old': old_rel, 'new': new_rel})
            except Exception:
                pass
            try:
                self.asset_service.assets_changed.emit(project, None)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def move_folder(self, project, src_rel: str, dest_parent_rel: str) -> bool:
        """Move a folder under a new parent inside the project. dest_parent_rel is the target folder under which src folder will be placed.
        Example: move_folder(project, 'Assets/Images/old', 'Assets/Images2') -> resulting folder 'Assets/Images2/old'
        """
        try:
            src = Path(src_rel)
            dest_parent = Path(dest_parent_rel) if dest_parent_rel else Path('')
            new_rel = str((dest_parent / src.name).as_posix())
            abs_src = self._abs_from_rel(project, src_rel)
            abs_dest = self._abs_from_rel(project, new_rel)
            if not abs_src.exists():
                return False
            abs_dest_parent = abs_dest.parent
            abs_dest_parent.mkdir(parents=True, exist_ok=True)
            abs_src.rename(abs_dest)
            # update index entries like rename
            self.asset_service._ensure_index_loaded(project)
            assets = self.asset_service._indices.get(project.location, [])
            for e in assets:
                rp = e.get('relative_path') or ''
                if rp.startswith(str(src_rel).rstrip('/') + '/') or rp == str(src_rel):
                    try:
                        suffix = Path(rp).relative_to(src_rel).as_posix()
                    except Exception:
                        suffix = Path(rp).name
                    new_rp = str(Path(new_rel) / suffix).replace('\\', '/')
                    e['relative_path'] = new_rp
                    e['absolute_path'] = str(Path(project.location) / new_rp)
                    e['updated_at'] = __import__('datetime').datetime.now().isoformat()
                    try:
                        if self.thumbnail_service:
                            self.thumbnail_service.invalidate(project.location, rel_path=rp)
                            try:
                                self.thumbnail_service.generate_async(project.location, new_rp, e.get('absolute_path'), None, e.get('id'))
                            except Exception:
                                pass
                    except Exception:
                        pass
            self.asset_service._save_index(project)
            try:
                if self.activity_service:
                    self.activity_service.record('move_folder', {'project': project.location, 'src': src_rel, 'dest': new_rel})
            except Exception:
                pass
            try:
                self.asset_service.assets_changed.emit(project, None)
            except Exception:
                pass
            return True
        except Exception:
            return False
