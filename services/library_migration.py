"""Safe, non-destructive migration utility for Global Asset Library in CreativeWorkspace.

Provides dry-run analysis, drive/location/asset merging, conflict detection,
timestamped backups, and safe migration from legacy home directories (~/.creativeworkspace/library/)
to the portable shared directory (<APP_ROOT>/data/library/).
"""

import argparse
import copy
import json
import shutil
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.paths import get_app_root, get_shared_library_dir, get_local_config_dir
from core.storage import atomic_write_json, safe_read_json


@dataclass
class LibraryConflictDetail:
    item_type: str  # "drive", "location", or "asset"
    item_id: str
    item_name: str
    differing_keys: List[str]
    source_summary: Dict[str, Any]
    target_summary: Dict[str, Any]


@dataclass
class LibraryMigrationReport:
    source_dir: str
    target_dir: str
    backup_dir: Optional[str] = None
    dry_run: bool = True

    # Inventory counts
    source_drives_count: int = 0
    source_locations_count: int = 0
    source_assets_count: int = 0
    source_total_asset_bytes: int = 0
    source_has_config: bool = False
    source_has_index: bool = False

    target_drives_count: int = 0
    target_locations_count: int = 0
    target_assets_count: int = 0
    target_total_asset_bytes: int = 0
    target_has_config: bool = False
    target_has_index: bool = False

    new_drives: List[Dict[str, Any]] = field(default_factory=list)
    identical_drives: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_drives: List[LibraryConflictDetail] = field(default_factory=list)

    new_locations: List[Dict[str, Any]] = field(default_factory=list)
    identical_locations: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_locations: List[LibraryConflictDetail] = field(default_factory=list)

    new_assets: List[Dict[str, Any]] = field(default_factory=list)
    identical_assets: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_assets: List[LibraryConflictDetail] = field(default_factory=list)

    malformed_files: List[Dict[str, Any]] = field(default_factory=list)
    executed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        lines = [
            f"# Asset Library Migration Report ({'DRY-RUN - NO CHANGES MADE' if self.dry_run else 'EXECUTED'})",
            f"- **Source Directory:** `{self.source_dir}`",
            f"- **Target Directory:** `{self.target_dir}`",
            f"- **Backup Location:** `{self.backup_dir or 'N/A (Dry Run)'}`",
            "",
            "## Inventory Breakdown",
            f"- **Source Config (global_library.json):** {self.source_has_config} (Drives: {self.source_drives_count}, Locations: {self.source_locations_count})",
            f"- **Source Index (library_index.json):** {self.source_has_index} (Assets: {self.source_assets_count}, Total Indexed Size: {self.source_total_asset_bytes / (1024*1024):.2f} MB)",
            f"- **Target Config (global_library.json):** {self.target_has_config} (Drives: {self.target_drives_count}, Locations: {self.target_locations_count})",
            f"- **Target Index (library_index.json):** {self.target_has_index} (Assets: {self.target_assets_count}, Total Indexed Size: {self.target_total_asset_bytes / (1024*1024):.2f} MB)",
            "",
            "## Actions Summary",
            f"- **New Drives to Merge:** {len(self.new_drives)}",
            f"- **Identical Drives (Skipped cleanly):** {len(self.identical_drives)}",
            f"- **Conflicting Drives:** {len(self.conflicting_drives)}",
            f"- **New Locations to Merge:** {len(self.new_locations)}",
            f"- **Identical Locations (Skipped cleanly):** {len(self.identical_locations)}",
            f"- **Conflicting Locations:** {len(self.conflicting_locations)}",
            f"- **New Assets to Index:** {len(self.new_assets)}",
            f"- **Identical Assets (Skipped cleanly):** {len(self.identical_assets)}",
            f"- **Conflicting Assets (Preserved in target & isolated to conflict bundle):** {len(self.conflicting_assets)}",
            f"- **Malformed / Corrupt Files:** {len(self.malformed_files)}",
        ]

        if self.new_drives:
            lines.append("\n### New Drives to Merge")
            for d in self.new_drives:
                lines.append(f"- `[{d.get('drive_id')}]` **{d.get('name', 'Untitled Drive')}** (Serial: {d.get('volume_serial')})")

        if self.new_locations:
            lines.append("\n### New Locations to Merge")
            for loc in self.new_locations:
                lines.append(f"- `[{loc.get('location_id')}]` **{loc.get('display_name', 'Untitled Location')}** (Path: {loc.get('drive_relative_path')})")

        if self.new_assets:
            lines.append(f"\n### New Assets to Migrate ({len(self.new_assets)} total)")
            for a in self.new_assets[:10]:
                lines.append(f"- `[{a.get('id')}]` **{a.get('filename')}** ({a.get('friendly_type', 'Asset')}, Category: {a.get('category')})")
            if len(self.new_assets) > 10:
                lines.append(f"- *... and {len(self.new_assets) - 10} more assets*")

        if self.conflicting_drives or self.conflicting_locations or self.conflicting_assets:
            lines.append("\n### Conflicts (Manual Review)")
            for c in self.conflicting_drives + self.conflicting_locations + self.conflicting_assets:
                lines.append(f"- **{c.item_type.capitalize()} ID:** `{c.item_id}` ({c.item_name})")
                lines.append(f"  - Differing Keys: {', '.join(c.differing_keys)}")

        if self.malformed_files:
            lines.append("\n### Malformed / Corrupt Files")
            for m in self.malformed_files:
                lines.append(f"- `{m.get('filename')}`: {m.get('error')}")

        return "\n".join(lines)


def _compare_dict_records(src: dict, tgt: dict, ignore_keys: Optional[set] = None) -> List[str]:
    """Compare two dictionaries and return list of differing keys."""
    ignore = ignore_keys or set()
    differing = []
    all_keys = set(src.keys()).union(set(tgt.keys())) - ignore

    for k in all_keys:
        v_src = src.get(k)
        v_tgt = tgt.get(k)
        if json.dumps(v_src, sort_keys=True, default=str) != json.dumps(v_tgt, sort_keys=True, default=str):
            differing.append(k)
    return sorted(differing)


class LibraryMigrationService:
    """Orchestrates safe dry-run analysis and non-destructive execution of Global Asset Library data."""

    def __init__(self, source_dir: Union[str, Path], target_dir: Union[str, Path]):
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve()
        self.source_config_file = self.source_dir / "global_library.json"
        self.source_index_file = self.source_dir / "library_index.json"
        self.target_config_file = self.target_dir / "global_library.json"
        self.target_index_file = self.target_dir / "library_index.json"

    def analyze(self) -> LibraryMigrationReport:
        """Perform a strictly read-only inspection and return a detailed report."""
        report = LibraryMigrationReport(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
            dry_run=True,
        )

        if not self.source_dir.exists():
            return report

        # 1. Load Source Config (Drives & Locations)
        source_drives_map: Dict[str, dict] = {}
        source_locations_map: Dict[str, dict] = {}
        if self.source_config_file.exists():
            report.source_has_config = True
            cfg, err = safe_read_json(self.source_config_file)
            if err or not isinstance(cfg, dict):
                report.malformed_files.append({"filename": "global_library.json (source)", "error": err or "Not a JSON object"})
            else:
                for d in cfg.get("drives", []):
                    if isinstance(d, dict) and "drive_id" in d:
                        source_drives_map[d["drive_id"]] = d
                for loc in cfg.get("locations", []):
                    if isinstance(loc, dict) and "location_id" in loc:
                        source_locations_map[loc["location_id"]] = loc

        report.source_drives_count = len(source_drives_map)
        report.source_locations_count = len(source_locations_map)

        # 2. Load Target Config (Drives & Locations)
        target_drives_map: Dict[str, dict] = {}
        target_locations_map: Dict[str, dict] = {}
        if self.target_config_file.exists():
            report.target_has_config = True
            cfg, err = safe_read_json(self.target_config_file)
            if err or not isinstance(cfg, dict):
                report.malformed_files.append({"filename": "global_library.json (target)", "error": err or "Not a JSON object"})
            else:
                for d in cfg.get("drives", []):
                    if isinstance(d, dict) and "drive_id" in d:
                        target_drives_map[d["drive_id"]] = d
                for loc in cfg.get("locations", []):
                    if isinstance(loc, dict) and "location_id" in loc:
                        target_locations_map[loc["location_id"]] = loc

        report.target_drives_count = len(target_drives_map)
        report.target_locations_count = len(target_locations_map)

        # Compare Drives
        for d_id, s_drive in source_drives_map.items():
            if d_id not in target_drives_map:
                report.new_drives.append({
                    "drive_id": d_id,
                    "name": s_drive.get("name", "Untitled Drive"),
                    "volume_serial": s_drive.get("volume_serial"),
                })
            else:
                t_drive = target_drives_map[d_id]
                diff = _compare_dict_records(s_drive, t_drive, ignore_keys={"last_known_mount", "updated_at"})
                if not diff:
                    report.identical_drives.append({"drive_id": d_id, "name": s_drive.get("name", "")})
                else:
                    report.conflicting_drives.append(LibraryConflictDetail(
                        item_type="drive",
                        item_id=d_id,
                        item_name=s_drive.get("name", "Untitled Drive"),
                        differing_keys=diff,
                        source_summary={"name": s_drive.get("name"), "volume_serial": s_drive.get("volume_serial")},
                        target_summary={"name": t_drive.get("name"), "volume_serial": t_drive.get("volume_serial")},
                    ))

        # Compare Locations
        for loc_id, s_loc in source_locations_map.items():
            if loc_id not in target_locations_map:
                report.new_locations.append({
                    "location_id": loc_id,
                    "display_name": s_loc.get("display_name", "Untitled Location"),
                    "drive_relative_path": s_loc.get("drive_relative_path"),
                })
            else:
                t_loc = target_locations_map[loc_id]
                diff = _compare_dict_records(s_loc, t_loc, ignore_keys={"last_scanned_at"})
                if not diff:
                    report.identical_locations.append({"location_id": loc_id, "display_name": s_loc.get("display_name", "")})
                else:
                    report.conflicting_locations.append(LibraryConflictDetail(
                        item_type="location",
                        item_id=loc_id,
                        item_name=s_loc.get("display_name", "Untitled Location"),
                        differing_keys=diff,
                        source_summary={"display_name": s_loc.get("display_name"), "drive_relative_path": s_loc.get("drive_relative_path")},
                        target_summary={"display_name": t_loc.get("display_name"), "drive_relative_path": t_loc.get("drive_relative_path")},
                    ))

        # 3. Load Source Index (Assets)
        source_assets_map: Dict[str, dict] = {}
        if self.source_index_file.exists():
            report.source_has_index = True
            assets_list, err = safe_read_json(self.source_index_file)
            if err or not isinstance(assets_list, list):
                report.malformed_files.append({"filename": "library_index.json (source)", "error": err or "Not a JSON list"})
            else:
                report.source_assets_count = len(assets_list)
                for a in assets_list:
                    if isinstance(a, dict) and "id" in a:
                        source_assets_map[a["id"]] = a
                        report.source_total_asset_bytes += a.get("file_size", 0)

        # 4. Load Target Index (Assets)
        target_assets_map: Dict[str, dict] = {}
        if self.target_index_file.exists():
            report.target_has_index = True
            assets_list, err = safe_read_json(self.target_index_file)
            if err or not isinstance(assets_list, list):
                report.malformed_files.append({"filename": "library_index.json (target)", "error": err or "Not a JSON list"})
            else:
                report.target_assets_count = len(assets_list)
                for a in assets_list:
                    if isinstance(a, dict) and "id" in a:
                        target_assets_map[a["id"]] = a
                        report.target_total_asset_bytes += a.get("file_size", 0)

        # Compare Assets
        for a_id, s_asset in source_assets_map.items():
            if a_id not in target_assets_map:
                report.new_assets.append({
                    "id": a_id,
                    "filename": s_asset.get("filename", ""),
                    "friendly_type": s_asset.get("friendly_type", ""),
                    "category": s_asset.get("category", ""),
                    "file_size": s_asset.get("file_size", 0),
                })
            else:
                t_asset = target_assets_map[a_id]
                diff = _compare_dict_records(s_asset, t_asset, ignore_keys={"updated_at"})
                if not diff:
                    report.identical_assets.append({"id": a_id, "filename": s_asset.get("filename", "")})
                else:
                    report.conflicting_assets.append(LibraryConflictDetail(
                        item_type="asset",
                        item_id=a_id,
                        item_name=s_asset.get("filename", "Untitled Asset"),
                        differing_keys=diff,
                        source_summary={"filename": s_asset.get("filename"), "file_size": s_asset.get("file_size")},
                        target_summary={"filename": t_asset.get("filename"), "file_size": t_asset.get("file_size")},
                    ))

        return report

    def _create_backup(self) -> Path:
        """Create a timestamped backup of existing target library files and verify contents."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_token = uuid.uuid4().hex[:8]
        backup_parent = self.target_dir.parent / "backups"
        backup_parent.mkdir(parents=True, exist_ok=True)
        backup_dir = backup_parent / f"library_migration_backup_{ts}_{unique_token}"
        backup_dir.mkdir(parents=True, exist_ok=False)

        manifest = {
            "created_at": datetime.now().isoformat(),
            "target_dir": str(self.target_dir),
            "backed_up_files": [],
        }

        if self.target_dir.exists():
            if self.target_config_file.exists():
                dest_cfg = backup_dir / "global_library.json"
                shutil.copy2(self.target_config_file, dest_cfg)
                if not dest_cfg.exists() or dest_cfg.stat().st_size != self.target_config_file.stat().st_size:
                    raise RuntimeError("Backup verification failed: global_library.json mismatch in backup")
                manifest["backed_up_files"].append({
                    "filename": "global_library.json",
                    "bytes": dest_cfg.stat().st_size,
                    "verified": True,
                })
            if self.target_index_file.exists():
                dest_idx = backup_dir / "library_index.json"
                shutil.copy2(self.target_index_file, dest_idx)
                if not dest_idx.exists() or dest_idx.stat().st_size != self.target_index_file.stat().st_size:
                    raise RuntimeError("Backup verification failed: library_index.json mismatch in backup")
                manifest["backed_up_files"].append({
                    "filename": "library_index.json",
                    "bytes": dest_idx.stat().st_size,
                    "verified": True,
                })

        atomic_write_json(backup_dir / "backup_manifest.json", manifest)
        return backup_dir

    def _create_conflict_bundle(self, report: LibraryMigrationReport) -> Optional[Path]:
        """Save isolated conflict information if conflicts exist."""
        if not report.conflicting_drives and not report.conflicting_locations and not report.conflicting_assets:
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_id = uuid.uuid4().hex[:8]
        conflict_dir = self.target_dir / "conflicts" / f"conflict_{ts}_{unique_id}"
        conflict_dir.mkdir(parents=True, exist_ok=False)

        meta = {
            "timestamp": datetime.now().isoformat(),
            "source_dir": str(self.source_dir),
            "target_dir": str(self.target_dir),
            "conflicting_drives": [asdict(c) for c in report.conflicting_drives],
            "conflicting_locations": [asdict(c) for c in report.conflicting_locations],
            "conflicting_assets": [asdict(c) for c in report.conflicting_assets],
        }
        atomic_write_json(conflict_dir / "conflict_manifest.json", meta)
        return conflict_dir

    def execute(self) -> LibraryMigrationReport:
        """Execute the migration safely with backups, conflict protection, and atomic writes."""
        report = self.analyze()
        report.dry_run = False

        if not self.source_dir.exists():
            return report

        # Step 1: Create atomic timestamped backup
        try:
            backup_dir = self._create_backup()
            report.backup_dir = str(backup_dir)
        except Exception as e:
            raise RuntimeError(f"Migration aborted: Failed to create target backup: {e}") from e

        # Step 2: Handle conflicts
        if report.conflicting_drives or report.conflicting_locations or report.conflicting_assets:
            self._create_conflict_bundle(report)

        # Step 3: Ensure target directory exists
        self.target_dir.mkdir(parents=True, exist_ok=True)

        # Step 4: Merge Config (Drives & Locations)
        target_drives_list: List[dict] = []
        target_locations_list: List[dict] = []

        if self.target_config_file.exists():
            t_cfg, _ = safe_read_json(self.target_config_file)
            if isinstance(t_cfg, dict):
                target_drives_list = t_cfg.get("drives", [])
                target_locations_list = t_cfg.get("locations", [])

        target_drive_ids = {d.get("drive_id") for d in target_drives_list if isinstance(d, dict)}
        target_location_ids = {loc.get("location_id") for loc in target_locations_list if isinstance(loc, dict)}

        if self.source_config_file.exists():
            s_cfg, _ = safe_read_json(self.source_config_file)
            if isinstance(s_cfg, dict):
                for s_d in s_cfg.get("drives", []):
                    if isinstance(s_d, dict) and s_d.get("drive_id") and s_d["drive_id"] not in target_drive_ids:
                        target_drives_list.append(s_d)
                        target_drive_ids.add(s_d["drive_id"])

                for s_loc in s_cfg.get("locations", []):
                    if isinstance(s_loc, dict) and s_loc.get("location_id") and s_loc["location_id"] not in target_location_ids:
                        target_locations_list.append(s_loc)
                        target_location_ids.add(s_loc["location_id"])

        merged_config = {
            "version": 1,
            "updated_at": datetime.now().isoformat(),
            "drives": target_drives_list,
            "locations": target_locations_list,
        }
        atomic_write_json(self.target_config_file, merged_config)

        # Step 5: Merge Index (Assets)
        target_assets_list: List[dict] = []
        if self.target_index_file.exists():
            t_idx, _ = safe_read_json(self.target_index_file)
            if isinstance(t_idx, list):
                target_assets_list = t_idx

        target_asset_ids = {a.get("id") for a in target_assets_list if isinstance(a, dict)}

        if self.source_index_file.exists():
            s_idx, _ = safe_read_json(self.source_index_file)
            if isinstance(s_idx, list):
                for s_a in s_idx:
                    if isinstance(s_a, dict) and s_a.get("id") and s_a["id"] not in target_asset_ids:
                        target_assets_list.append(s_a)
                        target_asset_ids.add(s_a["id"])

        atomic_write_json(self.target_index_file, target_assets_list)

        report.executed_at = datetime.now().isoformat()
        return report


def main():
    parser = argparse.ArgumentParser(description="CreativeWorkspace Global Asset Library Migration Utility")
    parser.add_argument("--source", type=str, default=str(get_local_config_dir() / "library"), help="Source library directory")
    parser.add_argument("--target", type=str, default=str(get_shared_library_dir()), help="Target shared library directory")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Perform read-only inspection (default)")
    parser.add_argument("--execute", action="store_true", default=False, help="Execute actual migration with backup")

    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    is_execute = args.execute and not args.dry_run

    print("=" * 70)
    print("CreativeWorkspace Global Asset Library Migration")
    print(f"Mode: {'EXECUTE' if is_execute else 'DRY-RUN (Inspection Only)'}")
    print(f"Source: {source}")
    print(f"Target: {target}")
    print("=" * 70)

    service = LibraryMigrationService(source_dir=source, target_dir=target)

    if is_execute:
        report = service.execute()
    else:
        report = service.analyze()

    print(report.summary_markdown())
    print("=" * 70)


if __name__ == "__main__":
    main()
