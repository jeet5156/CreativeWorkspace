"""Safe, non-destructive migration utility for Global Workbench Boards in CreativeWorkspace.

Provides dry-run analysis, manifest merging, conflict detection, timestamped backups,
and safe migration from legacy home directories (~/.creativeworkspace/workbench/boards/)
to the portable shared directory (<APP_ROOT>/data/workbench/boards/).
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

from core.paths import get_app_root, get_shared_workbench_boards_dir, get_local_config_dir
from core.storage import atomic_write_json, safe_read_json


@dataclass
class BoardConflictDetail:
    board_id: str
    board_name: str
    differing_keys: List[str]
    source_summary: Dict[str, Any]
    target_summary: Dict[str, Any]


@dataclass
class WorkbenchMigrationReport:
    source_dir: str
    target_dir: str
    backup_dir: Optional[str] = None
    dry_run: bool = True

    # Inventory counts
    source_board_files: int = 0
    source_has_manifest: bool = False
    target_board_files: int = 0
    target_has_manifest: bool = False

    new_boards: List[Dict[str, Any]] = field(default_factory=list)
    identical_boards: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_boards: List[BoardConflictDetail] = field(default_factory=list)
    orphaned_boards: List[Dict[str, Any]] = field(default_factory=list)
    malformed_files: List[Dict[str, Any]] = field(default_factory=list)
    executed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        lines = [
            f"# Workbench Boards Migration Report ({'DRY-RUN - NO CHANGES MADE' if self.dry_run else 'EXECUTED'})",
            f"- **Source Directory:** `{self.source_dir}`",
            f"- **Target Directory:** `{self.target_dir}`",
            f"- **Backup Location:** `{self.backup_dir or 'N/A (Dry Run)'}`",
            "",
            "## Inventory Breakdown",
            f"- **Source `*.lab.json` Board Files:** {self.source_board_files}",
            f"- **Source Manifest Exists:** {self.source_has_manifest}",
            f"- **Target `*.lab.json` Board Files:** {self.target_board_files}",
            f"- **Target Manifest Exists:** {self.target_has_manifest}",
            "",
            "## Actions Summary",
            f"- **New Boards to Migrate:** {len(self.new_boards)}",
            f"- **Identical Boards (Skipped cleanly):** {len(self.identical_boards)}",
            f"- **Conflicting Boards (Preserved in target & saved to isolated conflict bundle):** {len(self.conflicting_boards)}",
            f"- **Orphaned Empty Legacy Files (Skipped from Workbench):** {len(self.orphaned_boards)}",
            f"- **Malformed / Corrupt Board Files:** {len(self.malformed_files)}",
        ]

        if self.orphaned_boards:
            lines.append("\n### Orphaned Empty Legacy Files (Skipped from Workbench)")
            for o in self.orphaned_boards:
                lines.append(f"- `[{o.get('id')}]` **{o.get('name', 'Untitled')}** (`{o.get('filename')}`) | Items: 0 | Connectors: 0")

        if self.new_boards:
            lines.append("\n### New Boards to Migrate")
            for b in self.new_boards:
                recovered_tag = " (Recovered Unmanifested)" if b.get("manifest_entry", {}).get("unmanifested_recovered") else ""
                lines.append(f"- `[{b.get('id')}]` **{b.get('name', 'Untitled')}**{recovered_tag} | Items: {b.get('item_count', 0)} | Connectors: {b.get('connector_count', 0)}")

        if self.conflicting_boards:
            lines.append("\n### Conflicting Boards (Manual Review)")
            for c in self.conflicting_boards:
                lines.append(f"- **Board ID:** `{c.board_id}` ({c.board_name})")
                lines.append(f"  - Differing Keys: {', '.join(c.differing_keys)}")

        if self.malformed_files:
            lines.append("\n### Malformed / Corrupt Files")
            for m in self.malformed_files:
                lines.append(f"- `{m.get('filename')}`: {m.get('error')}")

        return "\n".join(lines)


def _load_board_file(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    """Safely load a .lab.json board file."""
    if not path.exists():
        return None, "File not found"
    data, err = safe_read_json(path)
    if err or not isinstance(data, dict):
        return None, err or "Not a JSON object"
    return data, None


def inspect_workbench_migration(
    source_dir: Union[str, Path],
    target_dir: Union[str, Path],
) -> WorkbenchMigrationReport:
    """Analyze source and target directories and return a strictly read-only dry-run migration report."""
    source_p = Path(source_dir).resolve()
    target_p = Path(target_dir).resolve()

    report = WorkbenchMigrationReport(
        source_dir=str(source_p),
        target_dir=str(target_p),
        dry_run=True,
    )

    # 1. Scan target directory (READ-ONLY: do not create target_p)
    target_boards: Dict[str, dict] = {}
    if target_p.exists() and target_p.is_dir():
        target_manifest_path = target_p / "board_manifest.json"
        report.target_has_manifest = target_manifest_path.exists()

        for tfile in target_p.glob("*.lab.json"):
            report.target_board_files += 1
            bdata, _ = _load_board_file(tfile)
            if bdata:
                bid = bdata.get("board_id", tfile.stem)
                target_boards[bid] = bdata

    if not source_p.exists() or not source_p.is_dir():
        return report

    # 2. Scan source directory (READ-ONLY)
    source_manifest_path = source_p / "board_manifest.json"
    report.source_has_manifest = source_manifest_path.exists()
    source_manifest_data, _ = safe_read_json(source_manifest_path) if report.source_has_manifest else ({}, None)
    source_manifest_entries = {
        b.get("id"): b for b in source_manifest_data.get("boards", []) if isinstance(b, dict) and b.get("id")
    } if isinstance(source_manifest_data, dict) else {}

    for sfile in source_p.glob("*.lab.json"):
        report.source_board_files += 1
        bdata, err = _load_board_file(sfile)
        if err or not bdata:
            report.malformed_files.append({
                "filename": sfile.name,
                "error": err or "Invalid board data",
            })
            continue

        bid = bdata.get("board_id", sfile.stem)
        manifest_entry = source_manifest_entries.get(bid, {})
        board_name = bdata.get("name") or manifest_entry.get("name", sfile.stem)
        item_count = len(bdata.get("items", []))
        connector_count = len(bdata.get("connectors", []))

        # If the source directory has a manifest, files not registered in the manifest
        # are checked for user data.
        # 1. Empty stubs (0 items, 0 connectors) are orphaned legacy files (e.g. from prior
        #    project isolation leaks) and must NOT be imported as new Workbench boards.
        # 2. Files with valid user content (items > 0 or connectors > 0) must NOT be silently
        #    excluded; they are preserved and migrated with recovered metadata.
        if report.source_has_manifest and bid not in source_manifest_entries:
            if item_count == 0 and connector_count == 0:
                report.orphaned_boards.append({
                    "id": bid,
                    "name": board_name,
                    "filename": sfile.name,
                    "item_count": item_count,
                    "connector_count": connector_count,
                    "data": bdata,
                    "manifest_entry": manifest_entry,
                    "source_file_path": str(sfile),
                    "is_empty": True,
                })
                continue
            else:
                manifest_entry = {
                    "id": bid,
                    "name": board_name,
                    "filename": sfile.name,
                    "unmanifested_recovered": True,
                }

        if bid not in target_boards:
            # New board to migrate
            report.new_boards.append({
                "id": bid,
                "name": board_name,
                "filename": sfile.name,
                "item_count": len(bdata.get("items", [])),
                "connector_count": len(bdata.get("connectors", [])),
                "data": bdata,
                "manifest_entry": manifest_entry,
                "source_file_path": str(sfile),
            })
        else:
            # Board ID collision -> compare content
            target_bdata = target_boards[bid]

            diff_keys = []
            for k in ("name", "items", "connectors", "groups", "viewport"):
                if bdata.get(k) != target_bdata.get(k):
                    diff_keys.append(k)

            if not diff_keys:
                report.identical_boards.append({
                    "id": bid,
                    "name": board_name,
                    "filename": sfile.name,
                })
            else:
                report.conflicting_boards.append(BoardConflictDetail(
                    board_id=bid,
                    board_name=board_name,
                    differing_keys=diff_keys,
                    source_summary={
                        "name": bdata.get("name"),
                        "item_count": len(bdata.get("items", [])),
                        "connector_count": len(bdata.get("connectors", [])),
                    },
                    target_summary={
                        "name": target_bdata.get("name"),
                        "item_count": len(target_bdata.get("items", [])),
                        "connector_count": len(target_bdata.get("connectors", [])),
                    },
                ))

    return report


def execute_workbench_migration(
    source_dir: Union[str, Path],
    target_dir: Union[str, Path],
    backup_parent_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = True,
) -> WorkbenchMigrationReport:
    """Execute migration with dry-run support, manifest merging, collision-proof backups, and conflict bundles."""
    report = inspect_workbench_migration(source_dir, target_dir)
    report.dry_run = dry_run

    if dry_run:
        return report

    source_p = Path(source_dir).resolve()
    target_p = Path(target_dir).resolve()

    # 1. Create timestamped backup before modifying target
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_base = Path(backup_parent_dir).resolve() if backup_parent_dir else target_p.parent / "backups"
    backup_dir = backup_base / f"workbench_migration_backup_{timestamp_str}_{uuid.uuid4().hex[:8]}"

    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        report.backup_dir = str(backup_dir)

        # Backup existing target if any
        if target_p.exists() and any(target_p.iterdir()):
            shutil.copytree(target_p, backup_dir / "target_before_migration", dirs_exist_ok=True)

        # Snapshot source into backup
        if source_p.exists() and any(source_p.iterdir()):
            shutil.copytree(source_p, backup_dir / "source_snapshot", dirs_exist_ok=True)
    except Exception as backup_err:
        raise RuntimeError(f"Workbench migration aborted: Pre-migration backup failed: {backup_err}") from backup_err

    # 2. Ensure target directory exists
    target_p.mkdir(parents=True, exist_ok=True)

    # 3. Load or initialize target manifest
    target_manifest_path = target_p / "board_manifest.json"
    target_manifest = {}
    if target_manifest_path.exists():
        t_data, _ = safe_read_json(target_manifest_path)
        if isinstance(t_data, dict):
            target_manifest = t_data

    if "version" not in target_manifest:
        target_manifest["version"] = "1.0"
    if "boards" not in target_manifest or not isinstance(target_manifest["boards"], list):
        target_manifest["boards"] = []
    if "last_view" not in target_manifest or not isinstance(target_manifest["last_view"], dict):
        target_manifest["last_view"] = {
            "zoom": 1.0,
            "pan_x": 0.0,
            "pan_y": 0.0,
            "grid_visible": True,
            "snap_to_grid": False,
        }

    # 4. Copy new board files atomically and add manifest entries
    existing_target_board_ids = {b.get("id") for b in target_manifest["boards"] if isinstance(b, dict)}

    for rec in report.new_boards:
        bid = rec["id"]
        filename = rec.get("filename", f"{bid}.lab.json")
        dest_board_file = target_p / filename

        atomic_write_json(dest_board_file, rec["data"])

        # Add manifest entry if not already present
        if bid not in existing_target_board_ids:
            entry = rec.get("manifest_entry") or {
                "id": bid,
                "name": rec.get("name", "Untitled Board"),
                "filename": filename,
                "created": datetime.now().isoformat(),
                "modified": datetime.now().isoformat(),
                "color": None,
                "icon": None,
                "thumbnail": None,
                "favorite": False,
                "locked": False,
                "order": len(target_manifest["boards"]),
            }
            target_manifest["boards"].append(entry)
            existing_target_board_ids.add(bid)

    if not target_manifest.get("active_board_id") and target_manifest["boards"]:
        target_manifest["active_board_id"] = target_manifest["boards"][0].get("id")

    # Save merged target manifest
    atomic_write_json(target_manifest_path, target_manifest)

    # 5. For conflicting boards: preserve target AND save unique collision-proof conflict bundle
    for conflict in report.conflicting_boards:
        bid = conflict.board_id
        conflicts_base = target_p / "conflicts" / bid
        conflicts_base.mkdir(parents=True, exist_ok=True)

        while True:
            unique_tag = f"conflict_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:8]}"
            conflict_bundle_dir = conflicts_base / unique_tag
            try:
                conflict_bundle_dir.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                continue

        source_board_file = source_p / f"{bid}.lab.json"
        if source_board_file.exists():
            shutil.copy2(source_board_file, conflict_bundle_dir / source_board_file.name)

        conflict_meta = {
            "board_id": conflict.board_id,
            "board_name": conflict.board_name,
            "differing_keys": conflict.differing_keys,
            "source_summary": conflict.source_summary,
            "target_summary": conflict.target_summary,
            "recorded_at": datetime.now().isoformat(),
        }
        atomic_write_json(conflict_bundle_dir / "conflict_info.json", conflict_meta)

    report.executed_at = datetime.now().isoformat()

    # 6. Save migration report in target directory
    atomic_write_json(target_p / "migration_report.json", report.to_dict())

    return report


def main():
    parser = argparse.ArgumentParser(description="CreativeWorkspace Global Workbench Boards Migration Tool")
    parser.add_argument(
        "--source",
        type=str,
        default=str(get_local_config_dir() / "workbench" / "boards"),
        help="Source legacy workbench boards directory (default: ~/.creativeworkspace/workbench/boards)",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=str(get_shared_workbench_boards_dir()),
        help="Target shared workbench boards directory (default: <APP_ROOT>/data/workbench/boards)",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=None,
        help="Custom backup directory location (default: <target_parent>/backups)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run inspection mode (default: True, writes no data)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration (overrides --dry-run)",
    )

    args = parser.parse_args()
    is_dry_run = not args.execute

    print("=" * 70)
    print("CreativeWorkspace Global Workbench Boards Migration")
    print(f"Mode: {'DRY-RUN (Inspection Only)' if is_dry_run else 'EXECUTE'}")
    print(f"Source: {args.source}")
    print(f"Target: {args.target}")
    print("=" * 70)

    if is_dry_run:
        report = inspect_workbench_migration(args.source, args.target)
    else:
        report = execute_workbench_migration(
            args.source,
            args.target,
            backup_parent_dir=args.backup_dir,
            dry_run=False,
        )

    print(report.summary_markdown())
    print("=" * 70)


if __name__ == "__main__":
    main()
