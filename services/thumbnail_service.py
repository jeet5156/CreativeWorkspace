from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Qt, QSize
from PySide6.QtGui import QImage
from pathlib import Path
import json
import hashlib
import os


class _ThumbWorker(QRunnable):
    def __init__(self, service, project_location, rel_path, src_path, thumb_path, size, asset_id):
        super().__init__()
        self.service = service
        self.project_location = project_location
        self.rel_path = rel_path
        self.src_path = src_path
        self.thumb_path = thumb_path
        self.size = size
        self.asset_id = asset_id

    def run(self):
        try:
            # Load using Qt QImage (thread-safe for non-GUI threads)
            img = QImage()
            loaded = img.load(str(self.src_path))
            if not loaded or img.isNull():
                # nothing to do
                return
            # scale while keeping aspect
            w = self.size.width()
            h = self.size.height()
            scaled = img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            # ensure parent exists
            self.thumb_path.parent.mkdir(parents=True, exist_ok=True)
            # save as jpg for broad support
            scaled.save(str(self.thumb_path), "JPEG", quality=85)
            # update index
            try:
                self.service._update_index(self.project_location, self.rel_path, str(self.thumb_path), os.path.getmtime(self.src_path))
            except Exception:
                pass
            # emit ready
            try:
                self.service.thumbnail_ready.emit(self.asset_id, str(self.thumb_path))
            except Exception:
                pass
            # remove queued marker
            try:
                key = (str(self.project_location), str(self.rel_path))
                if key in self.service._queued:
                    try:
                        self.service._queued.remove(key)
                    except Exception:
                        try:
                            self.service._queued.discard(key)
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            # ensure queued cleared on unexpected failure
            try:
                key = (str(self.project_location), str(self.rel_path))
                if key in self.service._queued:
                    try:
                        self.service._queued.remove(key)
                    except Exception:
                        try:
                            self.service._queued.discard(key)
                        except Exception:
                            pass
            except Exception:
                pass


class ThumbnailService(QObject):
    """ThumbnailService

    Responsibilities:
    - generate thumbnails in background threads
    - cache thumbnails under <project>/.creativeworkspace/thumbnails
    - emit thumbnail_ready(asset_id, thumb_path) when ready
    - provide get_cached(project, asset) and generate_async methods
    - invalidate thumbnails when assets change
    """

    thumbnail_ready = Signal(str, str)  # asset_id, thumb_path

    def __init__(self, asset_service=None):
        super().__init__()
        self.asset_service = asset_service
        self.pool = QThreadPool.globalInstance()
        # track queued tasks to avoid duplicates: keys are (project_location, rel_path)
        self._queued = set()

    def _thumb_folder(self, project_location: str) -> Path:
        p = Path(project_location) / ".creativeworkspace" / "thumbnails"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _index_file(self, project_location: str) -> Path:
        return Path(project_location) / ".creativeworkspace" / "thumbnails" / "index.json"

    def _load_index(self, project_location: str) -> dict:
        idx_path = self._index_file(project_location)
        if not idx_path.exists():
            return {}
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_index(self, project_location: str, data: dict):
        idx_path = self._index_file(project_location)
        try:
            idx_path.parent.mkdir(parents=True, exist_ok=True)
            with open(idx_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _update_index(self, project_location: str, rel_path: str, thumb_path: str, mtime: float):
        data = self._load_index(project_location)
        data[str(rel_path)] = {"thumb": str(thumb_path), "mtime": mtime}
        self._save_index(project_location, data)

    def get_cached(self, project_location: str, rel_path: str, src_path: str):
        """Return cached thumbnail path if still valid, otherwise None."""
        try:
            idx = self._load_index(project_location)
            entry = idx.get(str(rel_path))
            if not entry:
                return None
            thumb = Path(entry.get("thumb"))
            if not thumb.exists():
                return None
            # validate mtime
            try:
                src_mtime = os.path.getmtime(src_path)
                if float(entry.get("mtime", 0)) != float(src_mtime):
                    return None
            except Exception:
                return None
            return str(thumb)
        except Exception:
            return None

    def _thumb_name_for(self, rel_path: str, mtime: float) -> str:
        key = f"{rel_path}|{int(mtime)}"
        h = hashlib.sha1(key.encode('utf-8')).hexdigest()
        return f"{h}.jpg"

    def generate_async(self, project_location: str, rel_path: str, src_path: str, size, asset_id: str):
        """Start background generation if not queued or cached. Returns True if generation queued or already exists."""
        try:
            # ensure size default
            if not size:
                size = QSize(140, 160)
            # if cached and valid, emit ready synchronously
            cached = self.get_cached(project_location, rel_path, src_path)
            if cached:
                try:
                    self.thumbnail_ready.emit(asset_id, cached)
                except Exception:
                    pass
                return True
            key = (str(project_location), str(rel_path))
            if key in self._queued:
                return True
            # prepare target filename based on mtime to handle invalidation
            try:
                mtime = os.path.getmtime(src_path)
            except Exception:
                mtime = 0
            name = self._thumb_name_for(rel_path, mtime)
            thumb_dir = self._thumb_folder(project_location)
            thumb_path = thumb_dir / name
            # queue worker
            worker = _ThumbWorker(self, project_location, rel_path, src_path, thumb_path, size, asset_id)
            self._queued.add(key)

            # Submit to pool
            self.pool.start(worker)
            return True
        except Exception:
            return False

    def invalidate(self, project_location: str, rel_path: str = None, src_path: str = None):
        """Invalidate cached thumbnails for a given relative path or source path.
        If rel_path provided, remove mapping entry and file. If src_path provided, remove any index entries referencing that absolute path.
        """
        try:
            idx = self._load_index(project_location)
            modified = False
            keys = list(idx.keys())
            for k in keys:
                if rel_path and k == str(rel_path):
                    # remove file
                    try:
                        p = Path(idx[k].get('thumb'))
                        if p.exists():
                            p.unlink()
                    except Exception:
                        pass
                    try:
                        del idx[k]
                        modified = True
                    except Exception:
                        pass
                elif src_path:
                    # if src_path matches the current src (best-effort) compare mtimes? skip for now
                    pass
            if modified:
                self._save_index(project_location, idx)
        except Exception:
            pass

    def clear_project_cache(self, project_location: str):
        try:
            thumb_dir = self._thumb_folder(project_location)
            # remove thumbnails folder entirely
            for p in thumb_dir.iterdir():
                try:
                    if p.is_file():
                        p.unlink()
                except Exception:
                    pass
        except Exception:
            pass
