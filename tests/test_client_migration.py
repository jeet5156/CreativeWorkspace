"""Tests for safe client migration, dry-run reporting, backups, collision-proof conflicts, and extra files."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.storage import atomic_write_json, safe_read_json
from services.client_migration import (
    inspect_client_migration,
    execute_client_migration,
    ClientMigrationReport,
)
from services.client_service import ClientService
from models.client import Client, ClientContact


class TestClientMigration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_synthetic_client(
        self,
        folder: Path,
        client_id: str,
        name: str = "Test Client",
        company: str = "Studio A",
        status: str = "Active",
        contacts: list = None,
        client_json_raw: str = None,
    ):
        c_folder = folder / client_id
        c_folder.mkdir(parents=True, exist_ok=True)

        if client_json_raw is not None:
            (c_folder / "client.json").write_text(client_json_raw, encoding="utf-8")
        else:
            data = {
                "id": client_id,
                "name": name,
                "company": company,
                "status": status,
                "client_type": "Game Studio",
                "created": "2026-01-01T10:00:00",
                "modified": "2026-01-01T10:00:00",
                "tags": ["VFX"],
                "notes": "Sample notes",
                "project_ids": ["proj-1"],
            }
            atomic_write_json(c_folder / "client.json", data)

        if contacts is not None:
            atomic_write_json(c_folder / "contacts.json", contacts)

    def test_dry_run_is_strictly_read_only(self):
        """Verify dry-run does NOT create target directory or modify any files."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "non_existent_target"

        self._create_synthetic_client(source_dir, "client-1", name="Alpha Studio", contacts=[{"name": "Alice"}])
        self._create_synthetic_client(source_dir, "client-2", name="Beta Games", contacts=[{"name": "Bob"}])

        report = inspect_client_migration(source_dir, target_dir)

        self.assertTrue(report.dry_run)
        self.assertEqual(report.source_subfolders, 2)
        self.assertEqual(report.source_client_files, 2)
        self.assertEqual(report.source_contacts_files, 2)
        self.assertEqual(report.target_subfolders, 0)
        self.assertEqual(len(report.new_records), 2)
        self.assertEqual(len(report.conflicting_records), 0)
        # Strictly verify target directory was NOT created
        self.assertFalse(target_dir.exists())

    def test_migration_execution_copies_nested_structure_and_creates_backup(self):
        """Verify migration safely copies full nested structure including subdirectories and writes backups."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"
        backup_base = self.tmp_path / "backups"

        contacts = [{"name": "Jane Lead", "role": "Director", "email": "jane@alpha.com", "notes": ""}]
        self._create_synthetic_client(source_dir, "client-1", name="Alpha Studio", contacts=contacts)

        # Add extra attachment file and nested subfolder
        (source_dir / "client-1" / "avatar.png").write_bytes(b"PNGDATA")
        nested_docs = source_dir / "client-1" / "documents"
        nested_docs.mkdir(parents=True)
        (nested_docs / "contract.txt").write_text("Terms", encoding="utf-8")

        report = execute_client_migration(source_dir, target_dir, backup_parent_dir=backup_base, dry_run=False)

        self.assertFalse(report.dry_run)
        self.assertEqual(len(report.new_records), 1)
        self.assertTrue(target_dir.exists())
        self.assertTrue((target_dir / "client-1" / "client.json").exists())
        self.assertTrue((target_dir / "client-1" / "contacts.json").exists())
        self.assertTrue((target_dir / "client-1" / "avatar.png").exists())
        self.assertTrue((target_dir / "client-1" / "documents" / "contract.txt").exists())
        self.assertTrue((target_dir / "migration_report.json").exists())

        # Verify backup exists
        self.assertTrue(backup_base.exists())
        backups = list(backup_base.glob("clients_migration_backup_*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "source_snapshot" / "client-1" / "client.json").exists())

        # Verify source was NOT deleted or altered
        self.assertTrue((source_dir / "client-1" / "client.json").exists())

    def test_migration_aborts_safely_if_backup_fails(self):
        """Verify migration aborts before modifying target if pre-migration backup fails."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"
        invalid_backup_path = self.tmp_path / "non_writable_file"
        invalid_backup_path.write_text("blocker", encoding="utf-8")  # File instead of dir causes mkdir failure

        self._create_synthetic_client(source_dir, "client-1", name="Alpha Studio")

        with self.assertRaises(RuntimeError):
            execute_client_migration(
                source_dir,
                target_dir,
                backup_parent_dir=invalid_backup_path / "sub",
                dry_run=False,
            )

        # Target directory should not have been populated
        self.assertFalse((target_dir / "client-1").exists())

    def test_two_conflict_bundles_within_same_second_are_collision_proof(self):
        """Requirement 1: Verify two conflict bundle creations in immediate succession create distinct bundles without overwriting."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"

        # Target has version A
        self._create_synthetic_client(target_dir, "client-1", name="Alpha Target Version")
        # Source has version B
        self._create_synthetic_client(source_dir, "client-1", name="Alpha Source Version 1")

        # First run creating conflict bundle 1
        execute_client_migration(source_dir, target_dir, dry_run=False)

        # Source updated to version C
        self._create_synthetic_client(source_dir, "client-1", name="Alpha Source Version 2")

        # Second run immediately following (within subsecond / same second)
        execute_client_migration(source_dir, target_dir, dry_run=False)

        conflicts_dir = target_dir / "client-1" / "conflicts"
        bundles = sorted(list(conflicts_dir.glob("conflict_*")))
        self.assertEqual(len(bundles), 2, "Must create 2 distinct collision-proof bundles")

        # Verify both distinct conflict payloads exist and neither was overwritten
        data1, _ = safe_read_json(bundles[0] / "client.json")
        data2, _ = safe_read_json(bundles[1] / "client.json")
        names = {data1["name"], data2["name"]}
        self.assertIn("Alpha Source Version 1", names)
        self.assertIn("Alpha Source Version 2", names)

    def test_existing_target_subfolders_with_matching_and_differing_files(self):
        """Requirement 2 & 3: Verify target content is preserved, missing source content is copied, and differing files are flagged as conflict."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"

        # Both have identical client.json & contacts.json
        self._create_synthetic_client(source_dir, "client-1", name="Shared Studio", contacts=[{"name": "Alice"}])
        self._create_synthetic_client(target_dir, "client-1", name="Shared Studio", contacts=[{"name": "Alice"}])

        # Source has: logo.png (matching), doc.txt (missing in target), extra.bin (differing in target)
        (source_dir / "client-1" / "logo.png").write_bytes(b"SHARED_LOGO")
        (source_dir / "client-1" / "doc.txt").write_bytes(b"SOURCE_DOC")
        (source_dir / "client-1" / "extra.bin").write_bytes(b"SOURCE_BYTES_A")

        # Target has: logo.png (matching), target_only.txt (preserved), extra.bin (differing!)
        (target_dir / "client-1" / "logo.png").write_bytes(b"SHARED_LOGO")
        (target_dir / "client-1" / "target_only.txt").write_bytes(b"KEEP_ME")
        (target_dir / "client-1" / "extra.bin").write_bytes(b"TARGET_BYTES_B")

        report = inspect_client_migration(source_dir, target_dir)
        # extra.bin differences MUST be flagged as conflict
        self.assertEqual(len(report.conflicting_records), 1)
        conflict = report.conflicting_records[0]
        self.assertIn("extra.bin", conflict.differing_extra_files)

        # Execute migration
        execute_client_migration(source_dir, target_dir, dry_run=False)

        # Target content MUST be preserved
        self.assertEqual((target_dir / "client-1" / "target_only.txt").read_bytes(), b"KEEP_ME")
        self.assertEqual((target_dir / "client-1" / "extra.bin").read_bytes(), b"TARGET_BYTES_B")

        # Conflict bundle must contain the source version of extra.bin
        conflicts = list((target_dir / "client-1" / "conflicts").glob("conflict_*"))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual((conflicts[0] / "extra.bin").read_bytes(), b"SOURCE_BYTES_A")

    def test_second_migration_run_preserves_all_target_content(self):
        """Requirement 3: Verify running migration a second time is completely idempotent and preserves all target content."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"

        self._create_synthetic_client(source_dir, "client-1", name="Alpha Studio", contacts=[{"name": "Alice"}])
        (source_dir / "client-1" / "logo.png").write_bytes(b"LOGO_BYTES")

        # 1. First migration
        execute_client_migration(source_dir, target_dir, dry_run=False)

        # Add a new target-side file (e.g. created after migration on target)
        (target_dir / "client-1" / "notes_target.txt").write_text("New Note on Target", encoding="utf-8")

        # 2. Second migration run
        repeat_report = execute_client_migration(source_dir, target_dir, dry_run=False)

        self.assertEqual(len(repeat_report.new_records), 0)
        self.assertEqual(len(repeat_report.identical_records), 1)
        self.assertEqual(len(repeat_report.conflicting_records), 0)

        # Target side note MUST be preserved
        self.assertTrue((target_dir / "client-1" / "notes_target.txt").exists())
        self.assertEqual((target_dir / "client-1" / "notes_target.txt").read_text(encoding="utf-8"), "New Note on Target")
        self.assertTrue((target_dir / "client-1" / "logo.png").exists())


if __name__ == "__main__":
    unittest.main()
