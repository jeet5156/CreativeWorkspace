"""Safe, non-destructive migration utility for Visual Markups in CreativeWorkspace.

Provides dry-run analysis, annotation conflict detection, timestamped backups,
and safe migration from legacy home directories (~/.creativeworkspace/markups/)
to the portable shared directory (<APP_ROOT>/data/markups/).
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

from core.paths import get_app_root, get_shared_markups_dir, get_local_config_dir
from core.storage import atomic_write_json, safe_read_json


@dataclass
class MarkupConflictDetail:
    markup_id: str
    markup_name: str
    differing_keys: List[str]
    source_summary: Dict[str, Any]
    target_summary: Dict[str, Any]


@dataclass
class MarkupMigrationReport:
    source_dir: str
    target_dir: str
    backup_dir: Optional[str] = None
    dry_run: bool = True

    # Inventory counts
    source_documents_count: int = 0
    target_documents_count: int = 0

    new_documents: List[Dict[str, Any]] = field(default_factory=list)
    identical_documents: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_documents: List[MarkupConflictDetail] = field(default_factory=list)
    malformed_files: List[Dict[str, Any]] = field(default_factory=list)
    executed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        lines = [
            f"# Markups Migration Report ({'DRY-RUN - NO CHANGES MADE' if self.dry_run else 'EXECUTED'})",
            f"- **Source Directory:** `{self.source_dir}`",
            f"- **Target Directory:** `{self.target_dir}`",
            f"- **Backup Location:** `{self.backup_dir or 'N/A (Dry Run)'}`",
            "",
            "## Inventory Breakdown",
            f"- **Source Markup Documents:** {self.source_documents_count}",
            f"- **Target Markup Documents:** {self.target_documents_count}",
            "",
            "## Actions Summary",
            f"- **New Markups to Migrate:** {len(self.new_documents)}",
            f"- **Identical Markups (Skipped cleanly):** {len(self.identical_documents)}",
            f"- **Conflicting Markups (Preserved in target & isolated to conflict bundle):** {len(self.conflicting_documents)}",
            f"- **Malformed / Corrupt Files:** {len(self.malformed_files)}",
        ]

        if self.new_documents:
            lines.append("\n### New Markups to Migrate")
            for m in self.new_documents:
                lines.append(f"- `[{m.get('id')}]` **{m.get('name', 'Untitled')}** (Annotations: {m.get('annotations_count', 0)}, Source Asset: {m.get('source_asset_path', 'None')})")

        if self.conflicting_documents:
            lines.append("\n### Conflicting Markups (Manual Review)")
            for c in self.conflicting_documents:
                lines.append(f"- **Markup ID:** `{c.markup_id}` ({c.markup_name})")
                lines.append(f"  - Differing Keys: {', '.join(c.differing_keys)}")

        if self.malformed_files:
            lines.append("\n### Malformed / Corrupt Files")
            for m in self.malformed_files:
                lines.append(f"- `{m.get('filename')}`: {m.get('error')}")

        return "\n".join(lines)


def _load_markup_file(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    """Safely load a markup document JSON file."""
    if not path.exists():
        return None, "File not found"
    data, err = safe_read_json(path)
    if err or not isinstance(data, dict):
        return None, err or "Not a JSON object"
    return data, None


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


class MarkupMigrationService:
    """Orchestrates safe dry-run analysis and non-destructive execution of Visual Markups data."""

    def __init__(self, source_dir: Union[str, Path], target_dir: Union[str, Path]):
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve()
        self.source_docs_dir = self.source_dir / "documents"
        self.target_docs_dir = self.target_dir / "documents"

    def analyze(self) -> MarkupMigrationReport:
        """Perform a strictly read-only inspection and return a detailed report."""
        report = MarkupMigrationReport(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
            dry_run=True,
        )

        if not self.source_dir.exists():
            return report

        # 1. Inspect Source Documents
        source_doc_files = sorted(self.source_docs_dir.glob("*.json")) if self.source_docs_dir.exists() else []
        report.source_documents_count = len(source_doc_files)

        # 2. Inspect Target Documents
        target_doc_files = sorted(self.target_docs_dir.glob("*.json")) if self.target_docs_dir.exists() else []
        report.target_documents_count = len(target_doc_files)
        target_doc_map = {f.stem: f for f in target_doc_files}

        for src_file in source_doc_files:
            markup_id = src_file.stem
            src_data, src_err = _load_markup_file(src_file)
            if src_err:
                report.malformed_files.append({"filename": src_file.name, "error": src_err})
                continue

            markup_name = src_data.get("name", "Untitled Markup")
            annotations = src_data.get("annotations", [])
            source_ref = src_data.get("source_reference", {})
            source_asset_path = source_ref.get("relative_path", "")

            if markup_id not in target_doc_map:
                report.new_documents.append({
                    "id": markup_id,
                    "name": markup_name,
                    "annotations_count": len(annotations) if isinstance(annotations, list) else 0,
                    "source_asset_path": source_asset_path,
                    "file_name": src_file.name,
                })
            else:
                tgt_file = target_doc_map[markup_id]
                tgt_data, tgt_err = _load_markup_file(tgt_file)
                if tgt_err:
                    report.malformed_files.append({"filename": tgt_file.name, "error": tgt_err})
                    continue

                diff = _compare_dict_records(src_data, tgt_data, ignore_keys={"updated_at"})
                if not diff:
                    report.identical_documents.append({
                        "id": markup_id,
                        "name": markup_name,
                        "file_name": src_file.name,
                    })
                else:
                    report.conflicting_documents.append(MarkupConflictDetail(
                        markup_id=markup_id,
                        markup_name=markup_name,
                        differing_keys=diff,
                        source_summary={
                            "name": markup_name,
                            "annotations_count": len(annotations) if isinstance(annotations, list) else 0,
                            "source_reference": source_ref,
                        },
                        target_summary={
                            "name": tgt_data.get("name", "Untitled Markup"),
                            "annotations_count": len(tgt_data.get("annotations", [])) if isinstance(tgt_data.get("annotations"), list) else 0,
                            "source_reference": tgt_data.get("source_reference", {}),
                        },
                    ))

        return report

    def _create_backup(self) -> Path:
        """Create a timestamped backup of the existing target markups directory."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_token = uuid.uuid4().hex[:8]
        backup_parent = self.target_dir.parent / "backups"
        backup_parent.mkdir(parents=True, exist_ok=True)
        backup_dir = backup_parent / f"markups_migration_backup_{ts}_{unique_token}"
        backup_dir.mkdir(parents=True, exist_ok=False)

        if self.target_dir.exists() and self.target_docs_dir.exists():
            backup_docs = backup_dir / "documents"
            backup_docs.mkdir(parents=True, exist_ok=True)
            for f in self.target_docs_dir.glob("*.json"):
                shutil.copy2(f, backup_docs / f.name)

        return backup_dir

    def _create_conflict_bundle(self, report: MarkupMigrationReport) -> Optional[Path]:
        """Save isolated conflict information if conflicts exist."""
        if not report.conflicting_documents:
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_id = uuid.uuid4().hex[:8]
        conflict_dir = self.target_dir / "conflicts" / f"conflict_{ts}_{unique_id}"
        conflict_dir.mkdir(parents=True, exist_ok=False)

        meta = {
            "timestamp": datetime.now().isoformat(),
            "source_dir": str(self.source_dir),
            "target_dir": str(self.target_dir),
            "conflicting_documents": [asdict(c) for c in report.conflicting_documents],
        }
        atomic_write_json(conflict_dir / "conflict_manifest.json", meta)

        conflict_docs_src = conflict_dir / "source_documents"
        conflict_docs_tgt = conflict_dir / "target_documents"
        conflict_docs_src.mkdir(parents=True, exist_ok=True)
        conflict_docs_tgt.mkdir(parents=True, exist_ok=True)

        for c in report.conflicting_documents:
            s_file = self.source_docs_dir / f"{c.markup_id}.json"
            t_file = self.target_docs_dir / f"{c.markup_id}.json"
            if s_file.exists():
                shutil.copy2(s_file, conflict_docs_src / s_file.name)
            if t_file.exists():
                shutil.copy2(t_file, conflict_docs_tgt / t_file.name)

        return conflict_dir

    def execute(self) -> MarkupMigrationReport:
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
        if report.conflicting_documents:
            self._create_conflict_bundle(report)

        # Step 3: Ensure target directory exists
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self.target_docs_dir.mkdir(parents=True, exist_ok=True)

        # Step 4: Copy new non-conflicting markup documents atomically
        new_markup_ids = {m["id"] for m in report.new_documents}
        for markup_id in new_markup_ids:
            src_file = self.source_docs_dir / f"{markup_id}.json"
            tgt_file = self.target_docs_dir / f"{markup_id}.json"
            if src_file.exists():
                data, err = _load_markup_file(src_file)
                if not err and data is not None:
                    atomic_write_json(tgt_file, data)

        report.executed_at = datetime.now().isoformat()
        return report


def main():
    parser = argparse.ArgumentParser(description="CreativeWorkspace Markups Migration Utility")
    parser.add_argument("--source", type=str, default=str(get_local_config_dir() / "markups"), help="Source markups directory")
    parser.add_argument("--target", type=str, default=str(get_shared_markups_dir()), help="Target shared markups directory")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Perform read-only inspection (default)")
    parser.add_argument("--execute", action="store_true", default=False, help="Execute actual migration with backup")

    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    is_execute = args.execute and not args.dry_run

    print("=" * 70)
    print("CreativeWorkspace Visual Markups Migration")
    print(f"Mode: {'EXECUTE' if is_execute else 'DRY-RUN (Inspection Only)'}")
    print(f"Source: {source}")
    print(f"Target: {target}")
    print("=" * 70)

    service = MarkupMigrationService(source_dir=source, target_dir=target)

    if is_execute:
        report = service.execute()
    else:
        report = service.analyze()

    print(report.summary_markdown())
    print("=" * 70)


if __name__ == "__main__":
    main()
