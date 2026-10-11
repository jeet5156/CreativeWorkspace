"""Safe, non-destructive migration utility for Knowledge Base in CreativeWorkspace.

Provides dry-run analysis, folder hierarchy merging, document conflict detection,
timestamped backups, and safe migration from legacy home directories (~/.creativeworkspace/knowledge/)
to the portable shared directory (<APP_ROOT>/data/knowledge/).
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

from core.paths import get_app_root, get_shared_knowledge_dir, get_local_config_dir
from core.storage import atomic_write_json, safe_read_json


@dataclass
class KnowledgeConflictDetail:
    item_type: str  # "document" or "folder"
    item_id: str
    item_title: str
    differing_keys: List[str]
    source_summary: Dict[str, Any]
    target_summary: Dict[str, Any]


@dataclass
class KnowledgeMigrationReport:
    source_dir: str
    target_dir: str
    backup_dir: Optional[str] = None
    dry_run: bool = True

    # Inventory counts
    source_documents_count: int = 0
    source_folders_count: int = 0
    source_has_folders_file: bool = False
    target_documents_count: int = 0
    target_folders_count: int = 0
    target_has_folders_file: bool = False

    new_documents: List[Dict[str, Any]] = field(default_factory=list)
    identical_documents: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_documents: List[KnowledgeConflictDetail] = field(default_factory=list)

    new_folders: List[Dict[str, Any]] = field(default_factory=list)
    identical_folders: List[Dict[str, Any]] = field(default_factory=list)
    conflicting_folders: List[KnowledgeConflictDetail] = field(default_factory=list)

    malformed_files: List[Dict[str, Any]] = field(default_factory=list)
    executed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        lines = [
            f"# Knowledge Migration Report ({'DRY-RUN - NO CHANGES MADE' if self.dry_run else 'EXECUTED'})",
            f"- **Source Directory:** `{self.source_dir}`",
            f"- **Target Directory:** `{self.target_dir}`",
            f"- **Backup Location:** `{self.backup_dir or 'N/A (Dry Run)'}`",
            "",
            "## Inventory Breakdown",
            f"- **Source Documents:** {self.source_documents_count}",
            f"- **Source Folders:** {self.source_folders_count} (folders.json: {self.source_has_folders_file})",
            f"- **Target Documents:** {self.target_documents_count}",
            f"- **Target Folders:** {self.target_folders_count} (folders.json: {self.target_has_folders_file})",
            "",
            "## Actions Summary",
            f"- **New Documents to Migrate:** {len(self.new_documents)}",
            f"- **Identical Documents (Skipped cleanly):** {len(self.identical_documents)}",
            f"- **Conflicting Documents (Preserved in target & isolated to conflict bundle):** {len(self.conflicting_documents)}",
            f"- **New Folders to Merge:** {len(self.new_folders)}",
            f"- **Identical Folders (Skipped cleanly):** {len(self.identical_folders)}",
            f"- **Conflicting Folders:** {len(self.conflicting_folders)}",
            f"- **Malformed / Corrupt Files:** {len(self.malformed_files)}",
        ]

        if self.new_documents:
            lines.append("\n### New Documents to Migrate")
            for d in self.new_documents:
                lines.append(f"- `[{d.get('id')}]` **{d.get('title', 'Untitled')}** (Tags: {d.get('tags_count', 0)}, Project Refs: {d.get('project_refs_count', 0)})")

        if self.new_folders:
            lines.append("\n### New Folders to Merge")
            for fld in self.new_folders:
                lines.append(f"- `[{fld.get('id')}]` **{fld.get('name', 'Untitled')}** (Parent: {fld.get('parent_id')})")

        if self.conflicting_documents:
            lines.append("\n### Conflicting Documents (Manual Review)")
            for c in self.conflicting_documents:
                lines.append(f"- **Doc ID:** `{c.item_id}` ({c.item_title})")
                lines.append(f"  - Differing Keys: {', '.join(c.differing_keys)}")

        if self.conflicting_folders:
            lines.append("\n### Conflicting Folders (Manual Review)")
            for c in self.conflicting_folders:
                lines.append(f"- **Folder ID:** `{c.item_id}` ({c.item_title})")
                lines.append(f"  - Differing Keys: {', '.join(c.differing_keys)}")

        if self.malformed_files:
            lines.append("\n### Malformed / Corrupt Files")
            for m in self.malformed_files:
                lines.append(f"- `{m.get('filename')}`: {m.get('error')}")

        return "\n".join(lines)


def _load_doc_file(path: Path) -> Tuple[Optional[dict], Optional[str]]:
    """Safely load a document JSON file."""
    if not path.exists():
        return None, "File not found"
    data, err = safe_read_json(path)
    if err or not isinstance(data, dict):
        return None, err or "Not a JSON object"
    return data, None


def _load_folders_file(path: Path) -> Tuple[Optional[List[dict]], Optional[str]]:
    """Safely load folders.json."""
    if not path.exists():
        return None, "File not found"
    data, err = safe_read_json(path)
    if err or not isinstance(data, list):
        return None, err or "Not a JSON list"
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


class KnowledgeMigrationService:
    """Orchestrates safe dry-run analysis and non-destructive execution of Knowledge data."""

    def __init__(self, source_dir: Union[str, Path], target_dir: Union[str, Path]):
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve()
        self.source_docs_dir = self.source_dir / "documents"
        self.target_docs_dir = self.target_dir / "documents"
        self.source_folders_file = self.source_dir / "folders.json"
        self.target_folders_file = self.target_dir / "folders.json"

    def analyze(self) -> KnowledgeMigrationReport:
        """Perform a strictly read-only inspection and return a detailed report."""
        report = KnowledgeMigrationReport(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
            dry_run=True,
        )

        if not self.source_dir.exists():
            return report

        # 1. Inspect Source Folders
        source_folders_map: Dict[str, dict] = {}
        if self.source_folders_file.exists():
            report.source_has_folders_file = True
            folders_list, err = _load_folders_file(self.source_folders_file)
            if err:
                report.malformed_files.append({"filename": "folders.json (source)", "error": err})
            elif folders_list is not None:
                report.source_folders_count = len(folders_list)
                for fld in folders_list:
                    if isinstance(fld, dict) and "id" in fld:
                        source_folders_map[fld["id"]] = fld

        # 2. Inspect Target Folders
        target_folders_map: Dict[str, dict] = {}
        if self.target_folders_file.exists():
            report.target_has_folders_file = True
            folders_list, err = _load_folders_file(self.target_folders_file)
            if err:
                report.malformed_files.append({"filename": "folders.json (target)", "error": err})
            elif folders_list is not None:
                report.target_folders_count = len(folders_list)
                for fld in folders_list:
                    if isinstance(fld, dict) and "id" in fld:
                        target_folders_map[fld["id"]] = fld

        # Compare Folders
        for fld_id, src_fld in source_folders_map.items():
            if fld_id not in target_folders_map:
                report.new_folders.append({
                    "id": fld_id,
                    "name": src_fld.get("name", "Untitled Folder"),
                    "parent_id": src_fld.get("parent_id"),
                })
            else:
                tgt_fld = target_folders_map[fld_id]
                diff = _compare_dict_records(src_fld, tgt_fld)
                if not diff:
                    report.identical_folders.append({"id": fld_id, "name": src_fld.get("name", "")})
                else:
                    report.conflicting_folders.append(KnowledgeConflictDetail(
                        item_type="folder",
                        item_id=fld_id,
                        item_title=src_fld.get("name", "Untitled"),
                        differing_keys=diff,
                        source_summary={"name": src_fld.get("name"), "parent_id": src_fld.get("parent_id")},
                        target_summary={"name": tgt_fld.get("name"), "parent_id": tgt_fld.get("parent_id")},
                    ))

        # 3. Inspect Source Documents
        source_doc_files = sorted(self.source_docs_dir.glob("*.json")) if self.source_docs_dir.exists() else []
        report.source_documents_count = len(source_doc_files)

        # 4. Inspect Target Documents
        target_doc_files = sorted(self.target_docs_dir.glob("*.json")) if self.target_docs_dir.exists() else []
        report.target_documents_count = len(target_doc_files)
        target_doc_map = {f.stem: f for f in target_doc_files}

        for src_file in source_doc_files:
            doc_id = src_file.stem
            src_data, src_err = _load_doc_file(src_file)
            if src_err:
                report.malformed_files.append({"filename": src_file.name, "error": src_err})
                continue

            doc_title = src_data.get("title", src_data.get("name", "Untitled"))
            tags = src_data.get("tags", [])
            proj_refs = src_data.get("project_asset_refs", [])

            if doc_id not in target_doc_map:
                report.new_documents.append({
                    "id": doc_id,
                    "title": doc_title,
                    "tags_count": len(tags) if isinstance(tags, list) else 0,
                    "project_refs_count": len(proj_refs) if isinstance(proj_refs, list) else 0,
                    "file_name": src_file.name,
                })
            else:
                tgt_file = target_doc_map[doc_id]
                tgt_data, tgt_err = _load_doc_file(tgt_file)
                if tgt_err:
                    report.malformed_files.append({"filename": tgt_file.name, "error": tgt_err})
                    continue

                diff = _compare_dict_records(src_data, tgt_data, ignore_keys={"modified"})
                if not diff:
                    report.identical_documents.append({
                        "id": doc_id,
                        "title": doc_title,
                        "file_name": src_file.name,
                    })
                else:
                    report.conflicting_documents.append(KnowledgeConflictDetail(
                        item_type="document",
                        item_id=doc_id,
                        item_title=doc_title,
                        differing_keys=diff,
                        source_summary={
                            "title": doc_title,
                            "content_len": len(src_data.get("content", "")),
                            "tags": tags,
                        },
                        target_summary={
                            "title": tgt_data.get("title", tgt_data.get("name", "Untitled")),
                            "content_len": len(tgt_data.get("content", "")),
                            "tags": tgt_data.get("tags", []),
                        },
                    ))

        return report

    def _create_backup(self) -> Path:
        """Create a timestamped backup of the existing target knowledge directory."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_token = uuid.uuid4().hex[:8]
        backup_parent = self.target_dir.parent / "backups"
        backup_parent.mkdir(parents=True, exist_ok=True)
        backup_dir = backup_parent / f"knowledge_migration_backup_{ts}_{unique_token}"
        backup_dir.mkdir(parents=True, exist_ok=False)

        if self.target_dir.exists():
            if self.target_folders_file.exists():
                shutil.copy2(self.target_folders_file, backup_dir / "folders.json")
            if self.target_docs_dir.exists():
                backup_docs = backup_dir / "documents"
                backup_docs.mkdir(parents=True, exist_ok=True)
                for f in self.target_docs_dir.glob("*.json"):
                    shutil.copy2(f, backup_docs / f.name)

        return backup_dir

    def _create_conflict_bundle(self, report: KnowledgeMigrationReport) -> Optional[Path]:
        """Save isolated conflict information if conflicts exist."""
        if not report.conflicting_documents and not report.conflicting_folders:
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
            "conflicting_folders": [asdict(c) for c in report.conflicting_folders],
        }
        atomic_write_json(conflict_dir / "conflict_manifest.json", meta)

        # Copy conflicting documents
        if report.conflicting_documents:
            conflict_docs_src = conflict_dir / "source_documents"
            conflict_docs_tgt = conflict_dir / "target_documents"
            conflict_docs_src.mkdir(parents=True, exist_ok=True)
            conflict_docs_tgt.mkdir(parents=True, exist_ok=True)

            for c in report.conflicting_documents:
                s_file = self.source_docs_dir / f"{c.item_id}.json"
                t_file = self.target_docs_dir / f"{c.item_id}.json"
                if s_file.exists():
                    shutil.copy2(s_file, conflict_docs_src / s_file.name)
                if t_file.exists():
                    shutil.copy2(t_file, conflict_docs_tgt / t_file.name)

        return conflict_dir

    def execute(self) -> KnowledgeMigrationReport:
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
        if report.conflicting_documents or report.conflicting_folders:
            self._create_conflict_bundle(report)

        # Step 3: Ensure target directories exist
        self.target_dir.mkdir(parents=True, exist_ok=True)
        self.target_docs_dir.mkdir(parents=True, exist_ok=True)

        # Step 4: Merge Folders safely
        target_folders_list: List[dict] = []
        if self.target_folders_file.exists():
            loaded, err = _load_folders_file(self.target_folders_file)
            if not err and isinstance(loaded, list):
                target_folders_list = loaded

        target_folder_ids = {fld.get("id") for fld in target_folders_list if isinstance(fld, dict)}

        if self.source_folders_file.exists():
            source_folders_list, err = _load_folders_file(self.source_folders_file)
            if not err and isinstance(source_folders_list, list):
                for s_fld in source_folders_list:
                    if isinstance(s_fld, dict) and s_fld.get("id") and s_fld["id"] not in target_folder_ids:
                        target_folders_list.append(s_fld)
                        target_folder_ids.add(s_fld["id"])

        if target_folders_list:
            atomic_write_json(self.target_folders_file, target_folders_list)

        # Step 5: Copy new non-conflicting documents atomically
        new_doc_ids = {d["id"] for d in report.new_documents}
        for doc_id in new_doc_ids:
            src_file = self.source_docs_dir / f"{doc_id}.json"
            tgt_file = self.target_docs_dir / f"{doc_id}.json"
            if src_file.exists():
                data, err = _load_doc_file(src_file)
                if not err and data is not None:
                    atomic_write_json(tgt_file, data)

        report.executed_at = datetime.now().isoformat()
        return report


def main():
    parser = argparse.ArgumentParser(description="CreativeWorkspace Knowledge Migration Utility")
    parser.add_argument("--source", type=str, default=str(get_local_config_dir() / "knowledge"), help="Source knowledge directory")
    parser.add_argument("--target", type=str, default=str(get_shared_knowledge_dir()), help="Target shared knowledge directory")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Perform read-only inspection (default)")
    parser.add_argument("--execute", action="store_true", default=False, help="Execute actual migration with backup")

    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)
    is_execute = args.execute and not args.dry_run

    print("=" * 70)
    print("CreativeWorkspace Knowledge Migration")
    print(f"Mode: {'EXECUTE' if is_execute else 'DRY-RUN (Inspection Only)'}")
    print(f"Source: {source}")
    print(f"Target: {target}")
    print("=" * 70)

    service = KnowledgeMigrationService(source_dir=source, target_dir=target)

    if is_execute:
        report = service.execute()
    else:
        report = service.analyze()

    print(report.summary_markdown())
    print("=" * 70)


if __name__ == "__main__":
    main()
