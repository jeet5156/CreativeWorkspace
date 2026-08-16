from pathlib import Path
import shutil
import os
import json
from PySide6.QtCore import QObject, QSize, QMimeData, QByteArray

MIME_ASSETS = "application/x-creativeworkspace-assets"


class AssetOperationsService(QObject):
    """Centralizes filesystem operations on assets and keeps services in sync.

    Responsibilities:
    - rename, delete, duplicate, move, reveal_in_explorer, copy_path
    - update AssetService index and emit assets_changed via AssetService
    - record actions with ActivityService
    - update AppState.current_asset when relevant
    - do NOT manipulate UI directly; emit/update via existing services
    """

    MIME_ASSETS = MIME_ASSETS

    @staticmethod
    def create_asset_mime_data(project_location: str, asset_ids: list, source_rel_path: str, operation: str = "move", **extra) -> QMimeData:
        payload = {
            "source_project_location": project_location,
            "source_rel_path": source_rel_path,
            "asset_ids": asset_ids,
            "operation": operation,
        }
        payload.update(extra)
        data_bytes = json.dumps(payload).encode("utf-8")
        mime_data = QMimeData()
        mime_data.setData(MIME_ASSETS, QByteArray(data_bytes))
        return mime_data

    @staticmethod
    def decode_asset_mime_data(mime_data: QMimeData) -> dict:
        if not mime_data or not mime_data.hasFormat(MIME_ASSETS):
            return {}
        try:
            raw_bytes = mime_data.data(MIME_ASSETS).data()
            return json.loads(raw_bytes.decode("utf-8"))
        except Exception:
            return {}

    def __init__(self, asset_service, activity_service, project_service, app_state=None, thumbnail_service=None):
        super().__init__()
        self.asset_service = asset_service
        self.activity_service = activity_service
        self.project_service = project_service
        self.app_state = app_state
        self.thumbnail_service = thumbnail_service

    def _get_entry(self, project, asset_id):
        entry = self.asset_service.get_asset(project, asset_id)
        if not entry and str(asset_id).startswith("seq_"):
            real_id = str(asset_id)[4:]
            entry = self.asset_service.get_asset(project, real_id)
        return entry

    def rename_asset(self, project, asset_id, new_name):
        entry = self._get_entry(project, asset_id)
        if not entry:
            return False
        # store old relative path to invalidate thumbnail cache for it
        old_rel = entry.get('relative_path')
        try:
            res = self.asset_service.rename_asset(project, asset_id, new_name)
            if res:
                try:
                    self.activity_service.record('rename_asset', {'project': project.location, 'asset_id': asset_id, 'new_name': new_name})
                except Exception:
                    pass
                # invalidate thumbnail for the previous path
                try:
                    if getattr(self, 'thumbnail_service', None) and old_rel:
                        self.thumbnail_service.invalidate(project.location, rel_path=old_rel)
                except Exception:
                    pass
            return res
        except Exception:
            return False

    def delete_asset(self, project, asset_id):
        entry = self._get_entry(project, asset_id)
        if not entry:
            return False
        # record relative path to invalidate
        rel = entry.get('relative_path')
        try:
            res = self.asset_service.delete_asset(project, asset_id)
            if res:
                try:
                    self.activity_service.record('delete_asset', {'project': project.location, 'asset_id': asset_id, 'filename': entry.get('filename')})
                except Exception:
                    pass
                # invalidate thumbnail cache for deleted asset
                try:
                    if getattr(self, 'thumbnail_service', None) and rel:
                        self.thumbnail_service.invalidate(project.location, rel_path=rel)
                except Exception:
                    pass
                # If the deleted asset was the current asset in app state, clear it so Inspector updates
                try:
                    if self.app_state and self.app_state.get_current_asset() == asset_id:
                        self.app_state.set_current_asset(None)
                except Exception:
                    pass
            return res
        except Exception:
            return False

    def delete_assets(self, project, asset_ids: list):
        if not asset_ids:
            return True
        try:
            if hasattr(self.asset_service, "delete_assets"):
                res = self.asset_service.delete_assets(project, asset_ids)
            else:
                res = all(self.delete_asset(project, aid) for aid in asset_ids)
            return res
        except Exception:
            return False

    def duplicate_asset(self, project, asset_id):
        entry = self._get_entry(project, asset_id)
        if not entry:
            return False
        src = Path(entry.get('absolute_path') or (Path(project.location) / entry.get('relative_path')))
        if not src.exists():
            return False
        try:
            parent = src.parent
            stem = src.stem
            suffix = src.suffix
            i = 1
            while True:
                candidate = parent / f"{stem}_copy{i}{suffix}"
                if not candidate.exists():
                    break
                i += 1
            shutil.copy2(src, candidate)
            # add to index using asset_service helpers
            self.asset_service._ensure_index_loaded(project)
            new_entry = self.asset_service._make_asset_entry(project, str(candidate.resolve()), entry.get('category'))
            self.asset_service._indices[project.location].append(new_entry)
            self.asset_service._save_index(project)
            try:
                self.activity_service.record('duplicate_asset', {'project': project.location, 'asset_id': asset_id, 'new_asset_id': new_entry.get('id')})
            except Exception:
                pass
            try:
                self.asset_service.assets_changed.emit(project, entry.get('category'))
            except Exception:
                pass
            # queue thumbnail generation for the new asset
            try:
                if getattr(self, 'thumbnail_service', None):
                    rel_new = new_entry.get('relative_path')
                    abs_new = new_entry.get('absolute_path') or str(Path(project.location) / rel_new)
                    self.thumbnail_service.generate_async(project.location, rel_new, abs_new, QSize(140,160), new_entry.get('id'))
            except Exception:
                pass
            return True
        except Exception:
            return False

    def move_asset(self, project, asset_id, target_section):
        """Move asset to a different project section (assets/references/renders/exports).
        target_section is a section key like 'assets' or 'references'."""
        entry = self._get_entry(project, asset_id)
        if not entry:
            return False
        src = Path(entry.get('absolute_path') or (Path(project.location) / entry.get('relative_path')))
        if not src.exists():
            return False
        try:
            # remember old relative path for invalidation
            old_rel = entry.get('relative_path')
            dest_dir = self.asset_service._determine_dest_dir(project, target_section, src)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            # handle duplicate names
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                j = 1
                while True:
                    cand = dest_dir / f"{stem}_{j}{suffix}"
                    if not cand.exists():
                        dest = cand
                        break
                    j += 1
            shutil.move(str(src), str(dest))
            # update index entry
            assets = self.asset_service._ensure_index_loaded(project)
            e = next((a for a in assets if a.get('id') == asset_id), None)
            if e:
                e['filename'] = dest.name
                try:
                    rel = str(dest.relative_to(Path(project.location))).replace('\\', '/')
                except Exception:
                    rel = str(dest)
                e['relative_path'] = rel
                e['absolute_path'] = str(dest)
                e['category'] = target_section.capitalize() if target_section != 'assets' else 'Assets'
                e['updated_at'] = __import__('datetime').datetime.now().isoformat()
                self.asset_service._save_index(project)
            try:
                self.activity_service.record('move_asset', {'project': project.location, 'asset_id': asset_id, 'to': target_section})
            except Exception:
                pass
            # invalidate old thumbnail and queue generation for new location
            try:
                if getattr(self, 'thumbnail_service', None) and old_rel:
                    try:
                        self.thumbnail_service.invalidate(project.location, rel_path=old_rel)
                    except Exception:
                        pass
                if getattr(self, 'thumbnail_service', None) and e:
                    try:
                        rel_new = e.get('relative_path')
                        abs_new = e.get('absolute_path')
                        self.thumbnail_service.generate_async(project.location, rel_new, abs_new, QSize(140,160), asset_id)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                self.asset_service.assets_changed.emit(project, e.get('category') if e else None)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def move_assets_to_folder(self, project, mime_or_ids, target_rel_path: str) -> bool:
        """Move one or more assets to a target subfolder relative path inside the project.
        Accepts either a list of asset IDs or a QMimeData payload.
        """
        if isinstance(mime_or_ids, (list, tuple, set)):
            asset_ids = list(mime_or_ids)
            source_rel_path = None
        elif hasattr(mime_or_ids, 'hasFormat'):
            payload = self.decode_asset_mime_data(mime_or_ids)
            if not payload:
                return False
            asset_ids = payload.get("asset_ids", [])
            source_rel_path = payload.get("source_rel_path")
        else:
            return False

        if not asset_ids or not target_rel_path:
            return False

        # No-op check: target folder is identical to source folder
        norm_target = target_rel_path.replace('\\', '/').strip('/')
        if source_rel_path and source_rel_path.replace('\\', '/').strip('/') == norm_target:
            return True

        target_dir = Path(project.location) / norm_target
        target_dir.mkdir(parents=True, exist_ok=True)

        moved_count = 0
        for asset_id in asset_ids:
            entry = self._get_entry(project, asset_id)
            if not entry:
                continue

            old_rel = entry.get('relative_path') or ''
            old_parent = str(Path(old_rel).parent).replace('\\', '/').strip('.')
            if old_parent.lower() == norm_target.lower():
                # Already in target folder -> no-op for this item
                continue

            src = Path(entry.get('absolute_path') or (Path(project.location) / old_rel))
            if not src.exists():
                continue

            dest = target_dir / src.name
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                j = 1
                while True:
                    cand = target_dir / f"{stem}_{j}{suffix}"
                    if not cand.exists():
                        dest = cand
                        break
                    j += 1

            shutil.move(str(src), str(dest))

            # update index entry
            assets = self.asset_service._ensure_index_loaded(project)
            e = next((a for a in assets if a.get('id') == asset_id), None)
            if e:
                e['filename'] = dest.name
                try:
                    rel = str(dest.relative_to(Path(project.location))).replace('\\', '/')
                except Exception:
                    rel = str(dest)
                e['relative_path'] = rel
                e['absolute_path'] = str(dest)
                # Derive category from top-level directory segment of destination relative path
                top_folder = rel.split('/')[0] if '/' in rel else norm_target.split('/')[0]
                e['category'] = top_folder
                e['updated_at'] = __import__('datetime').datetime.now().isoformat()

            # thumbnail invalidation & regeneration
            try:
                if getattr(self, 'thumbnail_service', None) and old_rel:
                    try:
                        self.thumbnail_service.invalidate(project.location, rel_path=old_rel)
                    except Exception:
                        pass
                    if e:
                        try:
                            self.thumbnail_service.generate_async(project.location, e.get('relative_path'), e.get('absolute_path'), QSize(140, 160), asset_id)
                        except Exception:
                            pass
            except Exception:
                pass

            moved_count += 1

        if moved_count > 0:
            self.asset_service._save_index(project)
            try:
                self.activity_service.record('move_assets_to_folder', {'project': project.location, 'count': moved_count, 'target': norm_target})
            except Exception:
                pass
            try:
                self.asset_service.assets_changed.emit(project, None)
            except Exception:
                pass
            return True

        return False

    def reveal_in_explorer(self, project, asset_id):
        try:
            res = self.asset_service.open_containing_folder(project, asset_id)
            try:
                self.activity_service.record('reveal_in_explorer', {'project': project.location, 'asset_id': asset_id})
            except Exception:
                pass
            return res
        except Exception:
            return False

    # -----------------
    # Folder operations (delegates to FolderService if available)
    # -----------------
    def create_folder(self, project, parent_rel: str, name: str):
        fs = getattr(self, 'folder_service', None)
        if not fs:
            return False
        return fs.create_folder(project, parent_rel, name)

    def delete_folder(self, project, rel_path: str):
        fs = getattr(self, 'folder_service', None)
        if not fs:
            return False
        return fs.delete_folder(project, rel_path)

    def rename_folder(self, project, old_rel: str, new_name: str):
        fs = getattr(self, 'folder_service', None)
        if not fs:
            return False
        return fs.rename_folder(project, old_rel, new_name)

    def move_folder(self, project, src_rel: str, dest_parent_rel: str):
        fs = getattr(self, 'folder_service', None)
        if not fs:
            return False
        return fs.move_folder(project, src_rel, dest_parent_rel)

    def copy_path(self, project, asset_id):
        entry = self._get_entry(project, asset_id)
        if not entry:
            return False
        try:
            path = entry.get('absolute_path') or str(Path(project.location) / entry.get('relative_path'))
            try:
                from PySide6.QtGui import QGuiApplication
                QGuiApplication.clipboard().setText(path)
            except Exception:
                # fallback: attempt to write to clipboard via os if available
                pass
            try:
                self.activity_service.record('copy_path', {'project': project.location, 'asset_id': asset_id, 'path': path})
            except Exception:
                pass
            return True
        except Exception:
            return False
