"""Safe, non-destructive migration utility for Client data in CreativeWorkspace.

Provides dry-run analysis, conflict detection, timestamped backups, and safe migration
from legacy directories (.creativeworkspace/clients/) to the portable shared directory (data/clients/).
"""

import argparse
import json
import shutil
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.paths import get_app_root, get_shared_clients_dir
from core.storage import atomic_write_json, safe_read_json


@dataclass
class ClientConflictDetail:
    client_id: str
    client_name: str
    differing_fields: List[str]
    source_values: Dict[str, Any]
    target_values: Dict[str, Any]
    contacts_differ: bool
    differing_extra_files: List[str] = field(default_factory=list)


@dataclass
class ClientMigrationReport:
    source_dir: str
    target_dir: str
    backup_dir: Optional[str] = None
    dry_run: bool = True

    # Detailed folder and file counts
    source_subfolders: int = 0
    source_client_files: int = 0
    source_contacts_files: int = 0

    target_subfolders: int = 0
    target_client_files: int = 0
    target_contacts_files: int = 0

    new_records: List[Dict[str, Any]] = field(default_factory=list)
    identical_records: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_records: List[ClientConflictDetail] = field(default_factory=list)
    malformed_records: List[Dict[str, Any]] = field(default_factory=list)
    missing_fields_warnings: Dict[str, List[str]] = field(default_factory=dict)
    executed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        lines = [
            f"# Client Migration Report ({'DRY-RUN - NO CHANGES MADE' if self.dry_run else 'EXECUTED'})",
            f"- **Source Directory:** `{self.source_dir}`",
            f"- **Target Directory:** `{self.target_dir}`",
            f"- **Backup Location:** `{self.backup_dir or 'N/A (Dry Run)'}`",
            "",
            "## Inventory Breakdown",
            f"- **Source Client Subfolders:** {self.source_subfolders}",
            f"  - Valid `client.json` files: {self.source_client_files}",
            f"  - Valid `contacts.json` files: {self.source_contacts_files}",
            f"- **Target Existing Client Subfolders:** {self.target_subfolders}",
            f"  - Existing `client.json` files: {self.target_client_files}",
            f"  - Existing `contacts.json` files: {self.target_contacts_files}",
            "",
            "## Actions Summary",
            f"- **New Records to Migrate:** {len(self.new_records)}",
            f"- **Identical Records (Skipped cleanly):** {len(self.identical_records)}",
            f"- **Conflicting Records (Preserved in target & saved to isolated conflict bundle):** {len(self.conflicting_records)}",
            f"- **Malformed / Corrupt Records:** {len(self.malformed_records)}",
        ]

        if self.new_records:
            lines.append("\n### New Records to Migrate")
            for r in self.new_records:
                lines.append(f"- `[{r.get('id')}]` **{r.get('name', 'Unnamed')}** | Status: `{r.get('status', 'Unknown')}` | Company: `{r.get('company', 'None')}` | Contacts: {len(r.get('contacts', []))}")

        if self.conflicting_records:
            lines.append("\n### Conflicting Records (Manual Review)")
            for c in self.conflicting_records:
                lines.append(f"- **Client ID:** `{c.client_id}` ({c.client_name})")
                if c.differing_fields:
                    lines.append(f"  - Differing Metadata Fields: {', '.join(c.differing_fields)}")
                if c.contacts_differ:
                    lines.append("  - Contacts Differ: True")
                if c.differing_extra_files:
                    lines.append(f"  - Differing Extra Files: {', '.join(c.differing_extra_files)}")

        if self.malformed_records:
            lines.append("\n### Malformed / Corrupted Records")
            for m in self.malformed_records:
                lines.append(f"- `{m.get('folder')}`: {m.get('error')}")

        if self.missing_fields_warnings:
            lines.append("\n### Missing Fields Warnings")
            for cid, fields in self.missing_fields_warnings.items():
                lines.append(f"- `{cid}`: Missing fields: {', '.join(fields)}")

        return "\n".join(lines)


EXPECTED_CLIENT_FIELDS = ["id", "name", "status", "client_type", "created", "modified"]


def _load_client_bundle(client_folder: Path) -> Tuple[Optional[dict], Optional[list], Optional[str]]:
    """Load client.json and contacts.json from a client folder.

    Returns: (client_dict, contacts_list, error_msg)
    """
    client_json = client_folder / "client.json"
    if not client_json.exists():
        return None, None, "Missing client.json"

    data, err = safe_read_json(client_json)
    if err or not isinstance(data, dict):
        return None, None, f"Invalid client.json: {err or 'not an object'}"

    contacts = []
    contacts_json = client_folder / "contacts.json"
    if contacts_json.exists():
        c_data, c_err = safe_read_json(contacts_json)
        if c_err or not isinstance(c_data, list):
            return data, None, f"Invalid contacts.json: {c_err or 'not a list'}"
        contacts = c_data

    return data, contacts, None


def _scan_extra_files(client_folder: Path) -> Dict[str, bytes]:
    """Scan all additional files in client_folder (excluding client.json, contacts.json, and conflicts dir).

    Returns: map of relative_posix_path -> file_bytes
    """
    extras: Dict[str, bytes] = {}
    if not client_folder.exists():
        return extras

    for item in client_folder.rglob("*"):
        if item.is_file():
            rel = item.relative_to(client_folder)
            if rel.parts[0] in ("conflicts", ".creativeworkspace") or rel.as_posix() in ("client.json", "contacts.json"):
                continue
            try:
                extras[rel.as_posix()] = item.read_bytes()
            except Exception:
                pass
    return extras


def inspect_client_migration(source_dir: Union[str, Path], target_dir: Union[str, Path]) -> ClientMigrationReport:
    """Analyze source and target directories and generate a dry-run migration report without writing anything."""
    source_p = Path(source_dir).resolve()
    target_p = Path(target_dir).resolve()

    report = ClientMigrationReport(
        source_dir=str(source_p),
        target_dir=str(target_p),
        dry_run=True,
    )

    # 1. Scan target directory existing records (READ-ONLY: do not create target_p)
    target_clients: Dict[str, Tuple[dict, list, Path]] = {}
    if target_p.exists():
        for tfolder in target_p.iterdir():
            if tfolder.is_dir() and tfolder.name != "conflicts" and not tfolder.name.startswith("."):
                report.target_subfolders += 1
                if (tfolder / "client.json").exists():
                    report.target_client_files += 1
                if (tfolder / "contacts.json").exists():
                    report.target_contacts_files += 1

                c_data, contacts, _ = _load_client_bundle(tfolder)
                if c_data and "id" in c_data:
                    target_clients[c_data["id"]] = (c_data, contacts or [], tfolder)

    if not source_p.exists():
        return report

    # 2. Scan source directory records (READ-ONLY)
    source_folders = [f for f in source_p.iterdir() if f.is_dir() and not f.name.startswith(".")]
    report.source_subfolders = len(source_folders)

    for sfolder in source_folders:
        if (sfolder / "client.json").exists():
            report.source_client_files += 1
        if (sfolder / "contacts.json").exists():
            report.source_contacts_files += 1

        c_data, contacts, err = _load_client_bundle(sfolder)
        if err or not c_data or "id" not in c_data:
            report.malformed_records.append({
                "folder": sfolder.name,
                "error": err or "Missing ID in client data",
            })
            continue

        cid = c_data["id"]

        # Check missing standard fields
        missing = [f for f in EXPECTED_CLIENT_FIELDS if f not in c_data or c_data[f] is None]
        if missing:
            report.missing_fields_warnings[cid] = missing

        if cid not in target_clients:
            # New record to migrate
            report.new_records.append({
                "id": cid,
                "name": c_data.get("name", "Unnamed"),
                "status": c_data.get("status", "Active"),
                "company": c_data.get("company", ""),
                "folder": sfolder.name,
                "data": c_data,
                "contacts": contacts or [],
                "source_folder_path": str(sfolder),
            })
        else:
            # ID collision -> compare metadata content, contacts, and extra files
            target_c_data, target_contacts, target_folder = target_clients[cid]

            diff_fields = []
            all_keys = set(c_data.keys()).union(set(target_c_data.keys()))
            for k in sorted(all_keys):
                if k in ("modified", "last_opened"):
                    continue  # Ignore transient timestamps if contents match
                if c_data.get(k) != target_c_data.get(k):
                    diff_fields.append(k)

            contacts_differ = (contacts != target_contacts)

            # Compare extra files (e.g. avatars, documents)
            source_extras = _scan_extra_files(sfolder)
            target_extras = _scan_extra_files(target_folder)
            differing_extra_files = []
            for rel_name, s_bytes in source_extras.items():
                if rel_name in target_extras and target_extras[rel_name] != s_bytes:
                    differing_extra_files.append(rel_name)

            if not diff_fields and not contacts_differ and not differing_extra_files:
                report.identical_records.append({
                    "id": cid,
                    "name": c_data.get("name", ""),
                    "source_folder_path": str(sfolder),
                    "target_folder_path": str(target_folder),
                })
            else:
                report.conflicting_records.append(ClientConflictDetail(
                    client_id=cid,
                    client_name=c_data.get("name") or target_c_data.get("name", "Unnamed"),
                    differing_fields=diff_fields,
                    source_values={k: c_data.get(k) for k in diff_fields},
                    target_values={k: target_c_data.get(k) for k in diff_fields},
                    contacts_differ=contacts_differ,
                    differing_extra_files=differing_extra_files,
                ))

    return report


def execute_client_migration(
    source_dir: Union[str, Path],
    target_dir: Union[str, Path],
    backup_parent_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = True,
) -> ClientMigrationReport:
    """Execute migration with dry-run support, timestamped backup, and safe conflict preservation.

    Source records are NEVER deleted or altered.
    """
    report = inspect_client_migration(source_dir, target_dir)
    report.dry_run = dry_run

    if dry_run:
        return report

    source_p = Path(source_dir).resolve()
    target_p = Path(target_dir).resolve()

    # 1. Create timestamped backup of existing target records prior to creating/modifying target
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_base = Path(backup_parent_dir).resolve() if backup_parent_dir else target_p.parent / "backups"
    backup_dir = backup_base / f"clients_migration_backup_{timestamp_str}"

    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        report.backup_dir = str(backup_dir)

        # Backup existing target if any
        if target_p.exists() and any(target_p.iterdir()):
            shutil.copytree(target_p, backup_dir / "target_before_migration", dirs_exist_ok=True)

        # Also snapshot source into backup dir for complete provenance
        if source_p.exists():
            shutil.copytree(source_p, backup_dir / "source_snapshot", dirs_exist_ok=True)
    except Exception as backup_err:
        raise RuntimeError(f"Migration aborted: Pre-migration backup failed: {backup_err}") from backup_err

    # 2. Now ensure target directory exists
    target_p.mkdir(parents=True, exist_ok=True)

    # 3. Write new records atomically and recursively copy any nested assets/files
    for rec in report.new_records:
        cid = rec["id"]
        client_target_folder = target_p / cid
        client_target_folder.mkdir(parents=True, exist_ok=True)

        atomic_write_json(client_target_folder / "client.json", rec["data"])
        if rec.get("contacts") is not None:
            atomic_write_json(client_target_folder / "contacts.json", rec["contacts"])

        # Recursively copy any additional files or subfolders in source client folder
        sfolder_path = Path(rec.get("source_folder_path", ""))
        if sfolder_path.exists():
            s_extras = _scan_extra_files(sfolder_path)
            for rel_posix in s_extras.keys():
                dest_file = client_target_folder / Path(rel_posix)
                if not dest_file.exists():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sfolder_path / Path(rel_posix), dest_file)

    # 4. Copy missing extra files for identical records (preserving existing target content)
    for rec in report.identical_records:
        cid = rec["id"]
        client_target_folder = target_p / cid
        sfolder_path = Path(rec.get("source_folder_path", ""))
        if sfolder_path.exists() and client_target_folder.exists():
            s_extras = _scan_extra_files(sfolder_path)
            for rel_posix in s_extras.keys():
                dest_file = client_target_folder / Path(rel_posix)
                if not dest_file.exists():
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sfolder_path / Path(rel_posix), dest_file)

    # 5. For conflicting records: preserve target AND save collision-proof unique conflict bundle
    for conflict in report.conflicting_records:
        cid = conflict.client_id
        conflicts_base = target_p / cid / "conflicts"
        conflicts_base.mkdir(parents=True, exist_ok=True)

        # Create collision-proof unique directory using microseconds and UUID
        while True:
            unique_tag = f"conflict_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:8]}"
            conflict_bundle_dir = conflicts_base / unique_tag
            try:
                conflict_bundle_dir.mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                continue

        source_client_folder = source_p / cid
        if source_client_folder.exists():
            for s_item in source_client_folder.iterdir():
                if s_item.name == "conflicts":
                    continue
                if s_item.is_file():
                    shutil.copy2(s_item, conflict_bundle_dir / s_item.name)
                elif s_item.is_dir():
                    shutil.copytree(s_item, conflict_bundle_dir / s_item.name)

        # Write conflict details metadata into the bundle
        conflict_meta = {
            "client_id": conflict.client_id,
            "differing_fields": conflict.differing_fields,
            "source_values": conflict.source_values,
            "target_values": conflict.target_values,
            "contacts_differ": conflict.contacts_differ,
            "differing_extra_files": conflict.differing_extra_files,
            "recorded_at": datetime.now().isoformat(),
        }
        atomic_write_json(conflict_bundle_dir / "conflict_info.json", conflict_meta)

    report.executed_at = datetime.now().isoformat()

    # 6. Save migration report in target directory
    atomic_write_json(target_p / "migration_report.json", report.to_dict())

    return report


def main():
    parser = argparse.ArgumentParser(description="CreativeWorkspace Client Migration Tool")
    parser.add_argument(
        "--source",
        type=str,
        default=str(get_app_root() / ".creativeworkspace" / "clients"),
        help="Source legacy clients directory (default: <APP_ROOT>/.creativeworkspace/clients)",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=str(get_shared_clients_dir()),
        help="Target shared clients directory (default: <APP_ROOT>/data/clients)",
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
    print("CreativeWorkspace Client Data Migration")
    print(f"Mode: {'DRY-RUN (Inspection Only)' if is_dry_run else 'EXECUTE'}")
    print(f"Source: {args.source}")
    print(f"Target: {args.target}")
    print("=" * 70)

    if is_dry_run:
        report = inspect_client_migration(args.source, args.target)
    else:
        report = execute_client_migration(
            args.source,
            args.target,
            backup_parent_dir=args.backup_dir,
            dry_run=False,
        )

    print(report.summary_markdown())
    print("=" * 70)


if __name__ == "__main__":
    main()
