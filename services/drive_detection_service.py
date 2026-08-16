"""Drive Detection and Persistent Volume Identity Service for CreativeWorkspace."""

import ctypes
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from models.library_models import LibraryDrive


MARKER_FILENAME = ".creativeworkspace/library_drive.json"


def get_volume_info_windows(root_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Retrieve Windows volume serial number and volume name using Win32 API.
    
    Returns: (volume_serial_hex, volume_label)
    """
    if os.name != "nt":
        return None, None

    try:
        # Normalize root to e.g. "D:\\"
        root = str(Path(root_path).anchor)
        if not root.endswith("\\"):
            root += "\\"

        vol_name_buf = ctypes.create_unicode_buffer(261)
        fs_name_buf = ctypes.create_unicode_buffer(261)
        serial_number = ctypes.c_ulong()
        max_component_len = ctypes.c_ulong()
        fs_flags = ctypes.c_ulong()

        kernel32 = ctypes.windll.kernel32
        success = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            vol_name_buf,
            ctypes.sizeof(vol_name_buf) // 2,
            ctypes.byref(serial_number),
            ctypes.byref(max_component_len),
            ctypes.byref(fs_flags),
            fs_name_buf,
            ctypes.sizeof(fs_name_buf) // 2,
        )

        if success:
            sn_val = serial_number.value
            # Format as standard Windows 8-digit hex e.g. "A1B2-C3D4"
            sn_hex = f"{(sn_val >> 16) & 0xFFFF:04X}-{(sn_val & 0xFFFF):04X}"
            vol_label = vol_name_buf.value or None
            return sn_hex, vol_label
    except Exception:
        pass

    return None, None


class DriveDetectionService:
    """Manages persistent drive identity and dynamic mount point resolution."""

    def __init__(self):
        # drive_id -> active mount root path string (e.g. "E:\" or "/Volumes/SSD")
        self._active_mounts: Dict[str, str] = {}
        # drive_id -> LibraryDrive
        self._registered_drives: Dict[str, LibraryDrive] = {}
        # Manual/test mount overrides
        self._test_mount_overrides: Dict[str, str] = {}

    def get_drive_root(self, path: Path) -> Path:
        """Find the root mount directory of any given file/folder path."""
        p = Path(path).resolve()
        return Path(p.anchor) if p.anchor else Path(p.parts[0])

    def read_drive_marker(self, root_dir: Path) -> Optional[dict]:
        """Read the in-band .creativeworkspace/library_drive.json marker if it exists."""
        marker_path = root_dir / MARKER_FILENAME
        if marker_path.is_file():
            try:
                data = json.loads(marker_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("drive_id"):
                    return data
            except Exception:
                pass
        return None

    def write_drive_marker(self, root_dir: Path, drive: LibraryDrive) -> bool:
        """Write the in-band .creativeworkspace/library_drive.json marker to the drive root."""
        marker_path = root_dir / MARKER_FILENAME
        try:
            marker_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "drive_id": drive.drive_id,
                "name": drive.name,
                "volume_serial": drive.volume_serial,
                "volume_label": drive.volume_label,
                "created_at": drive.created_at,
                "format_version": 1,
            }
            marker_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def identify_drive(self, folder_or_root: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Identify a drive by marker or OS volume serial.
        
        Returns: (drive_id, volume_serial, volume_label)
        """
        root = self.get_drive_root(folder_or_root)
        marker = self.read_drive_marker(root)
        if marker and marker.get("drive_id"):
            return marker.get("drive_id"), marker.get("volume_serial"), marker.get("name") or marker.get("volume_label")

        # Fallback to OS volume serial
        vol_serial, vol_label = get_volume_info_windows(str(root))
        return None, vol_serial, vol_label

    def register_drive(self, folder_or_root: Path, name: Optional[str] = None) -> LibraryDrive:
        """Register a new or existing LibraryDrive for a given folder path."""
        root = self.get_drive_root(folder_or_root)
        drive_id, vol_serial, vol_label = self.identify_drive(root)

        if drive_id and drive_id in self._registered_drives:
            drive = self._registered_drives[drive_id]
            drive.last_known_mount = str(root)
            if name:
                drive.name = name
            self._active_mounts[drive.drive_id] = str(root)
            return drive

        # Check if known by volume_serial
        if vol_serial:
            for d in self._registered_drives.values():
                if d.volume_serial == vol_serial:
                    d.last_known_mount = str(root)
                    if name:
                        d.name = name
                    self.write_drive_marker(root, d)
                    self._active_mounts[d.drive_id] = str(root)
                    return d

        # Create brand new LibraryDrive
        drive_name = name or vol_label or f"Drive ({root})"
        new_drive = LibraryDrive(
            name=drive_name,
            volume_serial=vol_serial,
            volume_label=vol_label,
            last_known_mount=str(root),
        )
        if drive_id:
            new_drive.drive_id = drive_id

        self.write_drive_marker(root, new_drive)
        self._registered_drives[new_drive.drive_id] = new_drive
        self._active_mounts[new_drive.drive_id] = str(root)
        return new_drive

    def list_system_drives(self) -> List[Path]:
        """Discover all currently mounted logical root drives on the operating system."""
        roots = []
        if os.name == "nt":
            import string
            for letter in string.ascii_uppercase:
                drive_str = f"{letter}:\\"
                if os.path.exists(drive_str):
                    roots.append(Path(drive_str))
        else:
            # POSIX / macOS
            roots.append(Path("/"))
            vols = Path("/Volumes")
            if vols.is_dir():
                for v in vols.iterdir():
                    if v.is_dir():
                        roots.append(v)
            media = Path("/media")
            if media.is_dir():
                for u in media.iterdir():
                    if u.is_dir():
                        for m in u.iterdir():
                            if m.is_dir():
                                roots.append(m)
        return roots

    def refresh_mounts(self, known_drives: Optional[Dict[str, LibraryDrive]] = None) -> Dict[str, str]:
        """Scan all mounted system drives and match them to known LibraryDrives.
        
        Returns: active_mounts map (drive_id -> current root path)
        """
        if known_drives is not None:
            self._registered_drives = dict(known_drives)

        new_active: Dict[str, str] = {}

        # 1. Apply test overrides first
        for did, path in self._test_mount_overrides.items():
            if path and Path(path).exists():
                new_active[did] = str(Path(path).resolve())

        # 2. Scan physical mounts
        mounted_roots = self.list_system_drives()
        for root in mounted_roots:
            try:
                marker = self.read_drive_marker(root)
                if marker and marker.get("drive_id"):
                    did = marker["drive_id"]
                    if did not in self._test_mount_overrides:
                        new_active[did] = str(root)
                        if did in self._registered_drives:
                            self._registered_drives[did].last_known_mount = str(root)
                    continue

                # Try volume serial matching
                vol_serial, _ = get_volume_info_windows(str(root))
                if vol_serial:
                    for d in self._registered_drives.values():
                        if d.volume_serial == vol_serial and d.drive_id not in self._test_mount_overrides:
                            new_active[d.drive_id] = str(root)
                            d.last_known_mount = str(root)
                            # Best-effort attempt to write marker if missing
                            self.write_drive_marker(root, d)
                            break
            except Exception:
                continue

        self._active_mounts = new_active
        return self._active_mounts

    def is_drive_mounted(self, drive_id: str) -> bool:
        """Check if a drive is currently connected and mounted."""
        return drive_id in self._active_mounts

    def get_mount_point(self, drive_id: str) -> Optional[str]:
        """Get the current mount root path of a drive, or None if offline."""
        return self._active_mounts.get(drive_id)

    def resolve_drive_path(self, drive_id: str, drive_relative_path: str) -> Optional[Path]:
        """Resolve a drive-relative path to the current physical filesystem path.
        
        Returns Path if drive is mounted, or None if offline.
        """
        mount = self.get_mount_point(drive_id)
        if not mount:
            return None

        clean_rel = drive_relative_path.replace("\\", "/").strip("/")
        return Path(mount) / clean_rel

    def set_test_mount_override(self, drive_id: str, path: Optional[str]):
        """Helper for unit tests to simulate drive mounting, letter changes, and disconnects."""
        if path is None:
            self._test_mount_overrides[drive_id] = None
            self._active_mounts.pop(drive_id, None)
        else:
            self._test_mount_overrides[drive_id] = str(Path(path).resolve())
            self._active_mounts[drive_id] = str(Path(path).resolve())
