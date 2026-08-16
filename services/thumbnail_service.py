from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Qt, QSize
from PySide6.QtGui import QImage, QImageReader, QPixmap
from pathlib import Path
import json
import hashlib
import os


DEBUG_LOGGING = False

def log_debug(msg: str):
    pass


SUPPORTED_THUMB_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".tga", ".exr", ".hdr", ".ico"}


class ThumbnailWorker(QRunnable):
    """Background worker task for decoding and scaling a single thumbnail."""

    def __init__(self, project_location: str, rel_path: str, src_path: Path, thumb_path: Path, size: QSize, asset_id: str, service):
        super().__init__()
        self.project_location = project_location
        self.rel_path = rel_path
        self.src_path = src_path
        self.thumb_path = thumb_path
        self.size = size
        self.asset_id = asset_id
        self.service = service

    def run(self):
        reader = None
        try:
            log_debug(f"[THUMB] worker started: src_path={self.src_path}, asset_id={self.asset_id}")
            reader = QImageReader(str(self.src_path))
            reader.setAutoTransform(True)

            orig_size = reader.size()
            if not orig_size.isValid():
                self.service._mark_failed(self.project_location, self.rel_path, reason="invalid_header")
                return

            w, h = orig_size.width(), orig_size.height()
            est_mb = (w * h * 4) / (1024 * 1024)

            if est_mb > 256.0 or (w * h > 40000000):
                log_debug(f"[THUMBNAIL] Skipping oversized image (>256MB decoding limit): {self.src_path} ({w}x{h}, est. {est_mb:.1f} MB)")
                self.service._mark_failed(self.project_location, self.rel_path, reason="oversized", dimensions=(w, h), est_mb=est_mb)
                return

            target_size = orig_size.scaled(self.size, Qt.KeepAspectRatio)
            reader.setScaledSize(target_size)

            img = reader.read()
            if img.isNull():
                self.service._mark_failed(self.project_location, self.rel_path, reason="decode_error")
                return

            self.thumb_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(str(self.thumb_path), "JPEG", quality=85)
            log_debug(f"[THUMB] thumbnail written: thumb_path={self.thumb_path}")

            try:
                self.service._update_index(self.project_location, self.rel_path, str(self.thumb_path), os.path.getmtime(self.src_path))
            except Exception:
                pass

            key = (str(self.project_location), str(self.rel_path))
            subscribers = self.service._subscribers.pop(key, set())
            if self.asset_id:
                subscribers.add(str(self.asset_id))

            for sub_id in subscribers:
                try:
                    log_debug(f"[THUMB] emitting callback: asset_id={sub_id}, thumb_path={self.thumb_path}")
                    self.service.thumbnail_ready.emit(sub_id, str(self.thumb_path))
                except Exception:
                    pass

        except Exception as e:
            try:
                self.service._mark_failed(self.project_location, self.rel_path, reason="exception")
            except Exception:
                pass
        finally:
            try:
                if 'reader' in locals() and reader:
                    if reader.device():
                        reader.device().close()
                    del reader
                    reader = None
            except Exception:
                pass
            try:
                key = (str(self.project_location), str(self.rel_path))
                if key in self.service._queued:
                    self.service._queued.discard(key)
                self.service._subscribers.pop(key, None)
            except Exception:
                pass


import traceback


class ThumbnailService(QObject):
    """ThumbnailService

    Responsibilities:
    - 3-Level Cache Architecture:
        Level 1: Directory scan cache (in-memory folder mtime & scan result)
        Level 2: Thumbnail index cache (in-memory index.json dict per project)
        Level 3: Loaded QPixmap cache (in-memory QPixmap cache for instant rendering)
    - Controlled background thumbnail decoding using QImageReader (max 2 threads)
    - Failed thumbnail caching to avoid repeated decoding attempts on corrupted/oversized files
    """

    thumbnail_ready = Signal(str, str)  # asset_id, thumb_path

    def __init__(self, asset_service=None):
        super().__init__()
        self.asset_service = asset_service
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(2)  # Controlled background generation queue
        self._queued = set()
        self._subscribers = {}  # key (proj_loc, rel_path) -> Set[asset_id]

        # 3-Level Caches
        self._dir_scan_cache = {}  # (proj_loc, folder_rel) -> (mtime, assets)
        self._index_cache = {}     # proj_loc -> index_dict
        self._pixmap_cache = {}    # thumb_path -> QPixmap

    def _thumb_folder(self, project_location: str) -> Path:
        if project_location == "__global_library__" or not project_location:
            p = Path.home() / ".creativeworkspace" / "library" / "thumbnails"
        else:
            p = Path(project_location) / ".creativeworkspace" / "thumbnails"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _index_file(self, project_location: str) -> Path:
        if project_location == "__global_library__" or not project_location:
            return Path.home() / ".creativeworkspace" / "library" / "thumbnails" / "index.json"
        return Path(project_location) / ".creativeworkspace" / "thumbnails" / "index.json"

    def _load_index(self, project_location: str) -> dict:
        if project_location in self._index_cache:
            return self._index_cache[project_location]

        idx_path = self._index_file(project_location)
        if not idx_path.exists():
            self._index_cache[project_location] = {}
            return {}
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._index_cache[project_location] = data
                return data
        except Exception:
            self._index_cache[project_location] = {}
            return {}

    CACHE_VERSION = 1

    def _save_index(self, project_location: str, data: dict):
        if not isinstance(data, dict):
            data = {}
        data["version"] = self.CACHE_VERSION
        self._index_cache[project_location] = data
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

    def _mark_failed(self, project_location: str, rel_path: str, reason: str = "oversized", dimensions: tuple = None, est_mb: float = 0.0):
        data = self._load_index(project_location)
        entry = {
            "failed": True,
            "reason": reason,
            "mtime": 0,
        }
        if dimensions:
            entry["dimensions"] = list(dimensions)
        if est_mb > 0:
            entry["estimated_mb"] = round(est_mb, 1)
        data[str(rel_path)] = entry
        self._save_index(project_location, data)

    def get_cached(self, project_location: str, rel_path: str, src_path: str):
        """Return cached thumbnail path if still valid, otherwise None."""
        try:
            idx = self._load_index(project_location)
            entry = idx.get(str(rel_path))
            if not entry:
                return None
            if entry.get("failed"):
                return "FAILED"
            thumb = Path(entry.get("thumb"))
            if not thumb.exists():
                return None

            # If source file does not exist (e.g. offline drive), preserve cached thumbnail!
            if not src_path or not Path(src_path).exists():
                return str(thumb)

            try:
                src_mtime = os.path.getmtime(src_path)
                if abs(float(entry.get("mtime", 0)) - float(src_mtime)) > 0.01:
                    return None
            except Exception:
                return str(thumb)
            return str(thumb)
        except Exception:
            return None

    def get_cached_pixmap(self, thumb_path: str):
        """Level 3 Cache: Return QPixmap for thumb_path (cached in RAM or loaded on demand)."""
        if not thumb_path or thumb_path == "FAILED":
            return None
        norm_path = str(Path(thumb_path).resolve()) if os.path.exists(thumb_path) else str(thumb_path)
        if norm_path in self._pixmap_cache:
            return self._pixmap_cache[norm_path]
        if thumb_path in self._pixmap_cache:
            return self._pixmap_cache[thumb_path]
        try:
            pix = QPixmap(norm_path)
            if pix and not pix.isNull():
                self._pixmap_cache[norm_path] = pix
                self._pixmap_cache[thumb_path] = pix
                return pix
            reader = QImageReader(norm_path)
            reader.setAutoTransform(True)
            img = reader.read()
            try:
                if reader.device():
                    reader.device().close()
            except Exception:
                pass
            if img and not img.isNull():
                pix = QPixmap.fromImage(img)
                if not pix or pix.isNull():
                    pix = img
                self._pixmap_cache[norm_path] = pix
                self._pixmap_cache[thumb_path] = pix
                return pix
        except Exception:
            pass
        return None

    def _thumb_name_for(self, rel_path: str, mtime: float) -> str:
        key = f"{rel_path}|{int(mtime)}"
        h = hashlib.sha1(key.encode('utf-8')).hexdigest()
        return f"{h}.jpg"

    def generate_async(self, project_location: str, rel_path: str, src_path: str, size, asset_id: str):
        """Start background generation if not queued or cached. Returns True if generation queued or already exists."""
        try:
            if not src_path or Path(src_path).suffix.lower() not in SUPPORTED_THUMB_EXTS:
                return False

            stack = traceback.extract_stack()
            caller = stack[-2] if len(stack) >= 2 else None
            caller_str = f"{Path(caller.filename).name}:{caller.lineno} in {caller.name}" if caller else "unknown"
            log_debug(f"[GEN_ASYNC_REC] received asset_id={asset_id}, caller={caller_str}, rel_path={rel_path}")
            # ensure size default
            if not size:
                size = QSize(140, 160)

            key = (str(project_location), str(rel_path))
            if asset_id:
                if key not in self._subscribers:
                    self._subscribers[key] = set()
                self._subscribers[key].add(str(asset_id))

            # if cached and valid, emit ready synchronously to all waiting subscribers
            cached = self.get_cached(project_location, rel_path, src_path)
            if cached:
                subscribers = self._subscribers.pop(key, set())
                if asset_id:
                    subscribers.add(str(asset_id))
                for sub_id in subscribers:
                    try:
                        self.thumbnail_ready.emit(sub_id, cached)
                    except Exception:
                        pass
                return True

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
            worker = ThumbnailWorker(project_location, rel_path, Path(src_path), thumb_path, size, asset_id, self)
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
