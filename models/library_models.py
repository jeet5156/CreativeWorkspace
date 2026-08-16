"""Data models for CreativeWorkspace Global Asset Library."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid


class AssetAvailability(str, Enum):
    """Availability state of a cataloged library asset."""
    AVAILABLE = "Available"
    OFFLINE = "Offline"
    MISSING = "Missing"
    POSSIBLY_CHANGED = "Possibly Changed"


@dataclass
class LibraryDrive:
    """Represents a physical storage volume (portable SSD, external HDD, or internal volume)."""
    drive_id: str = field(default_factory=lambda: f"drv_{uuid.uuid4()}")
    name: str = "External Drive"
    volume_serial: Optional[str] = None
    volume_label: Optional[str] = None
    last_known_mount: Optional[str] = None  # e.g., "E:\\" or "/Volumes/MyDrive"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LibraryDrive":
        return cls(
            drive_id=data.get("drive_id", f"drv_{uuid.uuid4()}"),
            name=data.get("name", "External Drive"),
            volume_serial=data.get("volume_serial"),
            volume_label=data.get("volume_label"),
            last_known_mount=data.get("last_known_mount"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


@dataclass
class LibraryLocation:
    """Represents an indexed root folder on a designated LibraryDrive."""
    location_id: str = field(default_factory=lambda: f"loc_{uuid.uuid4()}")
    drive_id: str = ""
    display_name: str = ""
    drive_relative_path: str = ""  # Path relative to the drive root, e.g. "3D_Assets/Megascans"
    default_category: str = "Assets"
    watch_for_changes: bool = True
    scan_depth_limit: int = 15
    favorite: bool = False
    last_scanned_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LibraryLocation":
        return cls(
            location_id=data.get("location_id", f"loc_{uuid.uuid4()}"),
            drive_id=data.get("drive_id", ""),
            display_name=data.get("display_name", ""),
            drive_relative_path=data.get("drive_relative_path", "").replace("\\", "/").strip("/"),
            default_category=data.get("default_category", "Assets"),
            watch_for_changes=data.get("watch_for_changes", True),
            scan_depth_limit=data.get("scan_depth_limit", 15),
            favorite=bool(data.get("favorite", False)),
            last_scanned_at=data.get("last_scanned_at"),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class LibraryAsset:
    """Represents an indexed asset in the global catalog."""
    id: str = field(default_factory=lambda: f"lib_{uuid.uuid4()}")
    filename: str = ""
    drive_id: str = ""
    location_id: str = ""
    drive_relative_path: str = ""  # Path from drive root, e.g. "3D_Assets/Megascans/Rock_01.fbx"
    file_size: int = 0
    file_mtime: float = 0.0
    friendly_type: str = "Unknown"
    category: str = "Assets"
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    version: Optional[str] = None
    lod: Optional[str] = None
    resolution: Optional[str] = None
    thumbnail_rel: Optional[str] = None
    favorite: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    project_references: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LibraryAsset":
        return cls(
            id=data.get("id", f"lib_{uuid.uuid4()}"),
            filename=data.get("filename", ""),
            drive_id=data.get("drive_id", ""),
            location_id=data.get("location_id", ""),
            drive_relative_path=data.get("drive_relative_path", "").replace("\\", "/").strip("/"),
            file_size=data.get("file_size", 0),
            file_mtime=data.get("file_mtime", 0.0),
            friendly_type=data.get("friendly_type", "Unknown"),
            category=data.get("category", "Assets"),
            tags=list(data.get("tags", [])),
            notes=data.get("notes", ""),
            version=data.get("version"),
            lod=data.get("lod"),
            resolution=data.get("resolution"),
            thumbnail_rel=data.get("thumbnail_rel"),
            favorite=data.get("favorite", False),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            project_references=list(data.get("project_references", [])),
        )
