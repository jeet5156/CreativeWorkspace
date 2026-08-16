"""Global Asset Library Service for CreativeWorkspace."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from PySide6.QtCore import QObject, Signal
from models.library_models import AssetAvailability, LibraryAsset, LibraryDrive, LibraryLocation
from services.drive_detection_service import DriveDetectionService
from core.asset_intelligence import detect_version, detect_lod


DEFAULT_IGNORED_DIRS = {
    ".git", "__pycache__", ".creativeworkspace", ".DS_Store",
    "node_modules", ".venv", "venv", ".idea", ".vscode", "$RECYCLE.BIN", "System Volume Information"
}

TYPE_MAP = {
    # 3D Formats
    ".fbx": "FBX 3D Model",
    ".glb": "GLB 3D Model",
    ".gltf": "GLTF 3D Model",
    ".obj": "OBJ 3D Model",
    ".usd": "USD Scene",
    ".usda": "USDA Scene",
    ".usdc": "USDC Scene",
    ".usdz": "USDZ Package",
    ".blend": "Blender Scene",
    ".abc": "Alembic Cache",
    ".stl": "STL Geometry",
    # Images / Textures / Renders
    ".png": "PNG Image",
    ".jpg": "JPEG Image",
    ".jpeg": "JPEG Image",
    ".exr": "OpenEXR Image",
    ".hdr": "HDRI Environment",
    ".tga": "Targa Image",
    ".tif": "TIFF Image",
    ".tiff": "TIFF Image",
    ".dpx": "DPX Image",
    ".webp": "WebP Image",
    ".bmp": "Bitmap Image",
    ".psd": "Photoshop Document",
    # Audio / Media
    ".wav": "WAV Audio",
    ".mp3": "MP3 Audio",
    ".mp4": "MP4 Video",
    ".mov": "QuickTime Video",
}


def _friendly_type_for_ext(ext: str) -> str:
    return TYPE_MAP.get(ext.lower(), f"{ext.upper().lstrip('.')} File" if ext else "File")


def _determine_category_for_ext(ext: str) -> str:
    ext = ext.lower()
    if ext in {".fbx", ".glb", ".gltf", ".obj", ".usd", ".usda", ".usdc", ".usdz", ".blend", ".abc", ".stl"}:
        return "3D Models"
    if ext in {".exr", ".hdr"}:
        return "HDRIs & Passes"
    if ext in {".png", ".jpg", ".jpeg", ".tga", ".tif", ".tiff", ".webp", ".bmp", ".psd"}:
        return "Textures & Images"
    if ext in {".wav", ".mp3", ".ogg", ".flac"}:
        return "Audio"
    if ext in {".mp4", ".mov", ".mkv", ".avi"}:
        return "Video"
    return "Assets"


class LibraryService(QObject):
    """Core service managing the global asset catalog, portable drives, and in-place delta indexing."""

    drive_mounts_changed = Signal()
    assets_changed = Signal()

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None, drive_detector: Optional[DriveDetectionService] = None):
        super().__init__()
        self.storage_dir = Path(storage_dir) if storage_dir else Path.home() / ".creativeworkspace" / "library"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.drive_detector = drive_detector or DriveDetectionService()

        self.config_path = self.storage_dir / "global_library.json"
        self.index_path = self.storage_dir / "library_index.json"

        # In-memory indices
        self._drives: Dict[str, LibraryDrive] = {}
        # location_id -> LibraryLocation
        self._locations: Dict[str, LibraryLocation] = {}
        # asset_id -> LibraryAsset
        self._assets: Dict[str, LibraryAsset] = {}
        # (drive_id, drive_relative_path) -> asset_id
        self._path_to_asset_id: Dict[Tuple[str, str], str] = {}
        # drive_id -> last verified mount point
        self._last_checked_mounts: Dict[str, Optional[str]] = {}

        self._load_storage()
        for did in self._drives.keys():
            self._last_checked_mounts[did] = self.drive_detector.get_mount_point(did)

    def check_drive_mounts(self) -> bool:
        """Lightweight check of drive mount states across known registered drives.
        
        Returns True if any drive's mount status or mount point changed since the last check.
        """
        current_mounts = self.drive_detector.refresh_mounts(self._drives)

        # Compare mount state for all registered drives against last verified state
        changed = False
        for did in self._drives.keys():
            old_m = self._last_checked_mounts.get(did)
            new_m = current_mounts.get(did)
            if old_m != new_m:
                changed = True
                self._last_checked_mounts[did] = new_m

        if changed:
            self._save_storage()
            try:
                self.drive_mounts_changed.emit()
            except Exception:
                pass
        return changed

    # -------------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------------

    def _load_storage(self):
        """Load global library config and asset catalog from disk."""
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                for d_data in data.get("drives", []):
                    d = LibraryDrive.from_dict(d_data)
                    self._drives[d.drive_id] = d

                for l_data in data.get("locations", []):
                    loc = LibraryLocation.from_dict(l_data)
                    self._locations[loc.location_id] = loc
            except Exception:
                pass

        if self.index_path.exists():
            try:
                assets_data = json.loads(self.index_path.read_text(encoding="utf-8"))
                for a_data in assets_data:
                    a = LibraryAsset.from_dict(a_data)
                    self._assets[a.id] = a
                    self._path_to_asset_id[(a.drive_id, a.drive_relative_path)] = a.id
            except Exception:
                pass

        # Refresh drive mount states with known drives
        self.drive_detector.refresh_mounts(self._drives)

    def _save_storage(self):
        """Persist library config and asset index using atomic file replacement."""
        # 1. Save global_library.json
        config_payload = {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "drives": [d.to_dict() for d in self._drives.values()],
            "locations": [loc.to_dict() for loc in self._locations.values()],
        }
        self._atomic_write_json(self.config_path, config_payload)

        # 2. Save library_index.json
        assets_payload = [a.to_dict() for a in self._assets.values()]
        self._atomic_write_json(self.index_path, assets_payload)

    def _atomic_write_json(self, target_path: Path, data: Any):
        """Atomically write JSON data to avoid corruption during unexpected shutdowns."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_fd, temp_file = tempfile.mkstemp(dir=str(target_path.parent), prefix="tmp_lib_", suffix=".json")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_file, str(target_path))
        except Exception:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
            raise

    # -------------------------------------------------------------------------
    # Drive and Location Management
    # -------------------------------------------------------------------------

    def get_drives(self) -> List[LibraryDrive]:
        """Get all registered LibraryDrives."""
        return list(self._drives.values())

    def get_drive(self, drive_id: str) -> Optional[LibraryDrive]:
        """Get a specific LibraryDrive by ID."""
        return self._drives.get(drive_id)

    def get_locations(self, drive_id: Optional[str] = None) -> List[LibraryLocation]:
        """Get all LibraryLocations, optionally filtered by drive_id."""
        if drive_id:
            return [loc for loc in self._locations.values() if loc.drive_id == drive_id]
        return list(self._locations.values())

    def get_location(self, location_id: str) -> Optional[LibraryLocation]:
        """Get a LibraryLocation by ID."""
        return self._locations.get(location_id)

    def add_library_location(
        self,
        folder_path: Union[str, Path],
        display_name: Optional[str] = None,
        drive_name: Optional[str] = None,
        default_category: str = "Assets",
        scan_immediately: bool = True,
    ) -> Tuple[LibraryLocation, LibraryDrive]:
        """Register a folder as a LibraryLocation, auto-registering its drive."""
        path = Path(folder_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Location path does not exist: {path}")

        drive = self.drive_detector.register_drive(path, name=drive_name)
        self._drives[drive.drive_id] = drive

        drive_root = self.drive_detector.get_drive_root(path)
        try:
            drive_rel = str(path.relative_to(drive_root)).replace("\\", "/").strip("/")
        except Exception:
            drive_rel = str(path).replace("\\", "/").strip("/")

        loc_name = display_name or path.name or f"Library ({path})"
        location = LibraryLocation(
            drive_id=drive.drive_id,
            display_name=loc_name,
            drive_relative_path=drive_rel,
            default_category=default_category,
        )
        self._locations[location.location_id] = location
        self._last_checked_mounts[drive.drive_id] = self.drive_detector.get_mount_point(drive.drive_id)
        self._save_storage()

        if scan_immediately:
            self.scan_location(location.location_id)

        return location, drive

    def remove_library_location(self, location_id: str, remove_assets: bool = True, delete_folder: bool = False) -> bool:
        """Remove a LibraryLocation from catalog.
        
        If delete_folder is False (default): Only removes the catalog/index entry. Source files remain untouched.
        If delete_folder is True: Deletes the physical directory from the source drive as well.
        """
        loc = self._locations.get(location_id)
        if not loc:
            return False

        if delete_folder:
            resolved_root = self.drive_detector.resolve_drive_path(loc.drive_id, loc.drive_relative_path)
            if resolved_root and resolved_root.exists() and resolved_root.is_dir():
                try:
                    shutil.rmtree(resolved_root)
                except Exception:
                    pass

        self._locations.pop(location_id, None)

        if remove_assets:
            ids_to_remove = [aid for aid, a in self._assets.items() if a.location_id == location_id]
            for aid in ids_to_remove:
                asset = self._assets.pop(aid, None)
                if asset:
                    self._path_to_asset_id.pop((asset.drive_id, asset.drive_relative_path), None)

        self._save_storage()
        return True

    def remove_asset(self, asset_id: str, delete_file: bool = False) -> bool:
        """Remove an asset from the Library catalog.
        
        If delete_file is False (default): Only removes the catalog/index entry. Source file is NEVER touched.
        If delete_file is True: Deletes the physical file from the external drive as well.
        """
        asset = self._assets.get(asset_id)
        if not asset:
            return False

        if delete_file:
            phys_path = self.resolve_asset_path(asset)
            if phys_path and phys_path.exists() and phys_path.is_file():
                try:
                    os.remove(str(phys_path))
                except Exception:
                    pass

        self._assets.pop(asset_id, None)
        self._path_to_asset_id.pop((asset.drive_id, asset.drive_relative_path), None)
        self._save_storage()
        return True

    # -------------------------------------------------------------------------
    # In-Place Delta Indexing & Scanning
    # -------------------------------------------------------------------------

    def scan_location(self, location_id: str, force_full: bool = False) -> Dict[str, int]:
        """Scan a library location in-place on external drive without moving or copying files.
        
        Returns summary stats: {"added": int, "updated": int, "unchanged": int, "missing": int}
        """
        loc = self._locations.get(location_id)
        if not loc:
            return {"added": 0, "updated": 0, "unchanged": 0, "missing": 0}

        resolved_root = self.drive_detector.resolve_drive_path(loc.drive_id, loc.drive_relative_path)
        if not resolved_root or not resolved_root.exists():
            return {"added": 0, "updated": 0, "unchanged": 0, "missing": 0}

        drive_root = self.drive_detector.get_drive_root(resolved_root)
        stats = {"added": 0, "updated": 0, "unchanged": 0, "missing": 0}

        found_drive_rel_paths: Set[str] = set()

        for root, dirs, files in os.walk(str(resolved_root)):
            # Filter ignored directories
            dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]

            root_path = Path(root)

            for filename in files:
                if filename.startswith(".") or filename.endswith(".tmp"):
                    continue

                file_path = root_path / filename
                try:
                    rel_to_loc = str(file_path.relative_to(resolved_root)).replace("\\", "/").strip("/")
                except Exception:
                    rel_to_loc = filename

                if loc.drive_relative_path:
                    drive_rel = f"{loc.drive_relative_path}/{rel_to_loc}" if rel_to_loc and rel_to_loc != "." else loc.drive_relative_path
                else:
                    drive_rel = rel_to_loc

                drive_rel = drive_rel.replace("\\", "/").strip("/")
                found_drive_rel_paths.add(drive_rel)

                try:
                    stat = file_path.stat()
                    f_size = stat.st_size
                    f_mtime = stat.st_mtime
                except Exception:
                    continue

                existing_id = self._path_to_asset_id.get((loc.drive_id, drive_rel))

                if existing_id and existing_id in self._assets:
                    asset = self._assets[existing_id]
                    # Check if unchanged
                    if not force_full and asset.file_size == f_size and abs(asset.file_mtime - f_mtime) < 0.001:
                        stats["unchanged"] += 1
                        continue

                    # Update changed asset
                    asset.file_size = f_size
                    asset.file_mtime = f_mtime
                    asset.updated_at = datetime.now().isoformat()
                    stats["updated"] += 1
                else:
                    # New asset discovered
                    ext = file_path.suffix.lower()
                    friendly_type = _friendly_type_for_ext(ext)
                    category = _determine_category_for_ext(ext)
                    version = detect_version(filename)
                    lod = detect_lod(filename)

                    new_asset = LibraryAsset(
                        filename=filename,
                        drive_id=loc.drive_id,
                        location_id=loc.location_id,
                        drive_relative_path=drive_rel,
                        file_size=f_size,
                        file_mtime=f_mtime,
                        friendly_type=friendly_type,
                        category=category,
                        version=version,
                        lod=lod,
                    )
                    self._assets[new_asset.id] = new_asset
                    self._path_to_asset_id[(loc.drive_id, drive_rel)] = new_asset.id
                    stats["added"] += 1

        loc.last_scanned_at = datetime.now().isoformat()
        self._save_storage()
        return stats

    def scan_all_locations(self) -> Dict[str, Dict[str, int]]:
        """Scan all currently available library locations."""
        self.drive_detector.refresh_mounts(self._drives)
        results = {}
        for loc_id in list(self._locations.keys()):
            results[loc_id] = self.scan_location(loc_id)
        return results

    # -------------------------------------------------------------------------
    # Availability & Path Resolution
    # -------------------------------------------------------------------------

    def get_asset_availability(self, asset_or_id: Union[str, LibraryAsset]) -> AssetAvailability:
        """Evaluate the live availability state of a library asset."""
        asset = self._get_asset_obj(asset_or_id)
        if not asset:
            return AssetAvailability.MISSING

        # Check if drive is mounted
        if not self.drive_detector.is_drive_mounted(asset.drive_id):
            return AssetAvailability.OFFLINE

        physical_path = self.drive_detector.resolve_drive_path(asset.drive_id, asset.drive_relative_path)
        if not physical_path or not physical_path.exists():
            return AssetAvailability.MISSING

        try:
            stat = physical_path.stat()
            if stat.st_size != asset.file_size or abs(stat.st_mtime - asset.file_mtime) > 1.0:
                return AssetAvailability.POSSIBLY_CHANGED
        except Exception:
            return AssetAvailability.MISSING

        return AssetAvailability.AVAILABLE

    def get_location_availability(self, location_or_id: Union[str, LibraryLocation]) -> AssetAvailability:
        """Evaluate the live availability of a LibraryLocation."""
        loc = self._locations.get(str(location_or_id)) if isinstance(location_or_id, str) else location_or_id
        if not loc:
            return AssetAvailability.MISSING

        if not self.drive_detector.is_drive_mounted(loc.drive_id):
            return AssetAvailability.OFFLINE

        physical_path = self.drive_detector.resolve_drive_path(loc.drive_id, loc.drive_relative_path)
        if not physical_path or not physical_path.exists():
            return AssetAvailability.MISSING

        return AssetAvailability.AVAILABLE

    def update_location(
        self,
        location_id: str,
        display_name: Optional[str] = None,
        favorite: Optional[bool] = None,
    ) -> bool:
        """Update metadata on a registered LibraryLocation."""
        loc = self._locations.get(location_id)
        if not loc:
            return False

        if display_name is not None:
            loc.display_name = str(display_name).strip()
        if favorite is not None:
            loc.favorite = bool(favorite)

        self._save_storage()
        return True

    def resolve_asset_path(self, asset_or_id: Union[str, LibraryAsset]) -> Optional[Path]:
        """Resolve a library asset to its current real filesystem Path, or None if offline."""
        asset = self._get_asset_obj(asset_or_id)
        if not asset:
            return None
        return self.drive_detector.resolve_drive_path(asset.drive_id, asset.drive_relative_path)

    def _get_asset_obj(self, asset_or_id: Union[str, LibraryAsset]) -> Optional[LibraryAsset]:
        if isinstance(asset_or_id, LibraryAsset):
            return asset_or_id
        return self._assets.get(str(asset_or_id))

    # -------------------------------------------------------------------------
    # Metadata & Query Operations
    # -------------------------------------------------------------------------

    def get_asset(self, asset_id: str) -> Optional[LibraryAsset]:
        """Get a LibraryAsset by ID."""
        return self._assets.get(asset_id)

    def get_all_assets(self) -> List[LibraryAsset]:
        """Return a list of all indexed LibraryAssets."""
        return list(self._assets.values())

    def get_favorite_assets(self) -> List[LibraryAsset]:
        """Return a list of all favorite LibraryAssets."""
        return [a for a in self._assets.values() if getattr(a, "favorite", False)]

    def get_asset_by_drive_path(self, drive_id: str, drive_relative_path: str) -> Optional[LibraryAsset]:
        """Find a cataloged LibraryAsset by its drive ID and drive-relative path."""
        norm_path = drive_relative_path.replace("\\", "/").strip("/")
        # Check fast lookup map
        aid = self._path_to_asset_id.get((drive_id, norm_path))
        if aid and aid in self._assets:
            return self._assets[aid]
        for asset in self._assets.values():
            if asset.drive_id == drive_id and asset.drive_relative_path.replace("\\", "/").strip("/") == norm_path:
                return asset
        return None

    def update_asset(
        self,
        asset_id: str,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
        favorite: Optional[bool] = None,
        category: Optional[str] = None,
    ) -> bool:
        """Update user metadata (tags, notes, favorite, category) for a library asset."""
        asset = self._assets.get(asset_id)
        if not asset:
            return False

        if tags is not None:
            asset.tags = list(tags)
        if notes is not None:
            asset.notes = str(notes)
        if favorite is not None:
            asset.favorite = bool(favorite)
        if category is not None:
            asset.category = str(category)

        asset.updated_at = datetime.now().isoformat()
        self._save_storage()
        return True

    def record_project_reference(
        self,
        asset_id: str,
        project_location: str,
        project_name: str,
        mode: str = "reference",
    ) -> bool:
        """Record that a project references this global library asset."""
        asset = self._assets.get(asset_id)
        if not asset:
            return False

        # Avoid duplicate records for same project
        asset.project_references = [
            ref for ref in asset.project_references
            if ref.get("project_location") != project_location
        ]
        asset.project_references.append({
            "project_location": project_location,
            "project_name": project_name,
            "referenced_at": datetime.now().isoformat(),
            "mode": mode,
        })
        asset.updated_at = datetime.now().isoformat()
        self._save_storage()
        return True

    def remove_project_reference(self, asset_id: str, project_location: str) -> bool:
        """Remove a project reference from the global catalog asset record."""
        asset = self._assets.get(asset_id)
        if not asset:
            return False

        orig_len = len(asset.project_references)
        asset.project_references = [
            ref for ref in asset.project_references
            if ref.get("project_location") != project_location
        ]
        if len(asset.project_references) != orig_len:
            asset.updated_at = datetime.now().isoformat()
            self._save_storage()
            return True
        return False

    log_project_reference = record_project_reference

    def query_assets(
        self,
        query: Optional[str] = None,
        drive_id: Optional[str] = None,
        location_id: Optional[str] = None,
        availability: Optional[AssetAvailability] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        favorite: Optional[bool] = None,
    ) -> List[LibraryAsset]:
        """Fast in-memory filter and search across the global asset catalog."""
        results = list(self._assets.values())

        if drive_id:
            results = [a for a in results if a.drive_id == drive_id]

        if location_id:
            results = [a for a in results if a.location_id == location_id]

        if category:
            results = [a for a in results if a.category.lower() == category.lower()]

        if favorite is not None:
            results = [a for a in results if a.favorite == favorite]

        if tags:
            tag_set = {t.lower() for t in tags}
            results = [a for a in results if tag_set.issubset({t.lower() for t in a.tags})]

        if query:
            q = query.lower().strip()
            results = [
                a for a in results
                if q in a.filename.lower()
                or q in a.notes.lower()
                or any(q in t.lower() for t in a.tags)
                or q in a.friendly_type.lower()
                or q in a.drive_relative_path.lower()
            ]

        if availability:
            results = [a for a in results if self.get_asset_availability(a) == availability]

        return results
