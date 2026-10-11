"""Tests for Global Workbench Boards portability, project/global separation, and safe migration."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.paths import (
    get_app_root,
    get_shared_workbench_boards_dir,
    get_local_config_dir,
)
from core.storage import atomic_write_json, safe_read_json
from services.lab_service import LabService
from services.workbench_migration import (
    inspect_workbench_migration,
    execute_workbench_migration,
    WorkbenchMigrationReport,
)
from models.project import Project


class TestWorkbenchMigration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_synthetic_board(
        self,
        folder: Path,
        board_id: str,
        name: str = "Test Board",
        items: list = None,
    ):
        folder.mkdir(parents=True, exist_ok=True)
        board_data = {
            "version": "1.0",
            "board_id": board_id,
            "name": name,
            "created": "2026-01-01T10:00:00",
            "modified": "2026-01-01T10:00:00",
            "viewport": {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0},
            "items": items or [],
            "connectors": [],
            "groups": [],
        }
        atomic_write_json(folder / f"{board_id}.lab.json", board_data)

    def _create_synthetic_manifest(
        self,
        folder: Path,
        boards: list = None,
        active_board_id: str = None,
    ):
        folder.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": "1.0",
            "active_board_id": active_board_id,
            "last_view": {"zoom": 1.0, "pan_x": 0.0, "pan_y": 0.0},
            "boards": boards or [],
        }
        atomic_write_json(folder / "board_manifest.json", manifest)

    def test_global_and_project_path_separation(self):
        """Requirement 1 & 3: Global boards resolve to shared data; project boards resolve to project location."""
        global_custom = self.tmp_path / "shared" / "workbench" / "boards"
        service = LabService(global_storage_dir=global_custom)

        # 1. Global (no project)
        global_path = service.get_boards_dir(None)
        self.assertEqual(global_path, global_custom)
        self.assertTrue(global_path.exists())

        # 2. Project-bound (has project location)
        project_folder = self.tmp_path / "projects" / "ProjectAlpha"
        proj = Project(name="ProjectAlpha", location=str(project_folder), project_type="general")
        project_boards_dir = service.get_boards_dir(proj)

        self.assertEqual(project_boards_dir, project_folder / "Lab" / "boards")
        self.assertTrue(project_boards_dir.exists())

        # Verify operations in project do not affect global directory
        entry = service.create_board(proj, name="Project Specific Board")
        self.assertTrue((project_boards_dir / f"{entry['id']}.lab.json").exists())
        self.assertFalse((global_path / f"{entry['id']}.lab.json").exists())

    def test_dry_run_is_strictly_read_only(self):
        """Requirement 4: Dry-run does not create target directory or modify any files."""
        source_dir = self.tmp_path / "source_legacy_boards"
        target_dir = self.tmp_path / "non_existent_target"

        self._create_synthetic_board(source_dir, "board-1", name="Main Board")
        self._create_synthetic_manifest(source_dir, boards=[{"id": "board-1", "name": "Main Board"}], active_board_id="board-1")

        report = inspect_workbench_migration(source_dir, target_dir)

        self.assertTrue(report.dry_run)
        self.assertEqual(report.source_board_files, 1)
        self.assertTrue(report.source_has_manifest)
        self.assertEqual(report.target_board_files, 0)
        self.assertFalse(report.target_has_manifest)
        self.assertEqual(len(report.new_boards), 1)
        # Target directory MUST NOT be created
        self.assertFalse(target_dir.exists())

    def test_migration_execution_merges_manifest_and_creates_backup(self):
        """Requirement 4: Execution merges manifest, copies board files, and creates backups."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"
        backup_base = self.tmp_path / "backups"

        self._create_synthetic_board(source_dir, "board-1", name="Workbench A", items=[{"id": "item-1"}])
        self._create_synthetic_manifest(source_dir, boards=[{"id": "board-1", "name": "Workbench A"}], active_board_id="board-1")

        report = execute_workbench_migration(source_dir, target_dir, backup_parent_dir=backup_base, dry_run=False)

        self.assertFalse(report.dry_run)
        self.assertEqual(len(report.new_boards), 1)
        self.assertTrue(target_dir.exists())
        self.assertTrue((target_dir / "board-1.lab.json").exists())
        self.assertTrue((target_dir / "board_manifest.json").exists())

        # Verify manifest content
        manifest, _ = safe_read_json(target_dir / "board_manifest.json")
        self.assertEqual(len(manifest["boards"]), 1)
        self.assertEqual(manifest["boards"][0]["id"], "board-1")
        self.assertEqual(manifest["active_board_id"], "board-1")

        # Verify backup exists
        backups = list(backup_base.glob("workbench_migration_backup_*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "source_snapshot" / "board-1.lab.json").exists())

        # Verify source was NOT deleted or altered
        self.assertTrue((source_dir / "board-1.lab.json").exists())

    def test_migration_aborts_safely_if_backup_fails(self):
        """Requirement 4: Migration aborts before writing target if backup fails."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"
        invalid_backup_path = self.tmp_path / "blocked_file"
        invalid_backup_path.write_text("blocker", encoding="utf-8")

        self._create_synthetic_board(source_dir, "board-1", name="Workbench Board")

        with self.assertRaises(RuntimeError):
            execute_workbench_migration(
                source_dir,
                target_dir,
                backup_parent_dir=invalid_backup_path / "nested",
                dry_run=False,
            )

        # Target should not have been created or modified
        self.assertFalse((target_dir / "board-1.lab.json").exists())

    def test_two_conflict_bundles_within_same_second_are_collision_proof(self):
        """Requirement 4 & 6: Rapid conflict creation generates distinct collision-proof bundles without overwriting."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"

        # Target has version A
        self._create_synthetic_board(target_dir, "board-1", name="Target Board Version")
        self._create_synthetic_manifest(target_dir, boards=[{"id": "board-1", "name": "Target Board Version"}])

        # Source has version B
        self._create_synthetic_board(source_dir, "board-1", name="Source Board Version 1", items=[{"id": "s1"}])

        # First run creating conflict bundle 1
        execute_workbench_migration(source_dir, target_dir, dry_run=False)

        # Source updated to version C
        self._create_synthetic_board(source_dir, "board-1", name="Source Board Version 2", items=[{"id": "s2"}])

        # Second run immediately following (within same subsecond)
        execute_workbench_migration(source_dir, target_dir, dry_run=False)

        conflicts_dir = target_dir / "conflicts" / "board-1"
        bundles = sorted(list(conflicts_dir.glob("conflict_*")))
        self.assertEqual(len(bundles), 2, "Must create 2 distinct collision-proof bundles")

        # Verify target was NOT overwritten
        target_data, _ = safe_read_json(target_dir / "board-1.lab.json")
        self.assertEqual(target_data["name"], "Target Board Version")

    def test_repeated_migration_is_idempotent(self):
        """Requirement 6: Running migration twice cleanly skips identical boards and preserves existing target content."""
        source_dir = self.tmp_path / "source_legacy"
        target_dir = self.tmp_path / "target_shared"

        self._create_synthetic_board(source_dir, "board-1", name="Workbench A")
        self._create_synthetic_manifest(source_dir, boards=[{"id": "board-1", "name": "Workbench A"}])

        # 1. First run
        execute_workbench_migration(source_dir, target_dir, dry_run=False)

        # Add a new board on target side (created after migration)
        self._create_synthetic_board(target_dir, "board-target-only", name="Created on Target")
        target_manifest, _ = safe_read_json(target_dir / "board_manifest.json")
        target_manifest["boards"].append({"id": "board-target-only", "name": "Created on Target"})
        atomic_write_json(target_dir / "board_manifest.json", target_manifest)

        # 2. Second migration run
        repeat_report = execute_workbench_migration(source_dir, target_dir, dry_run=False)

        self.assertEqual(len(repeat_report.new_boards), 0)
        self.assertEqual(len(repeat_report.identical_boards), 1)
        self.assertEqual(len(repeat_report.conflicting_boards), 0)

        # Target-only board MUST be preserved in manifest and files
        self.assertTrue((target_dir / "board-target-only.lab.json").exists())
        final_manifest, _ = safe_read_json(target_dir / "board_manifest.json")
        board_ids = [b["id"] for b in final_manifest["boards"]]
        self.assertIn("board-1", board_ids)
        self.assertIn("board-target-only", board_ids)


if __name__ == "__main__":
    unittest.main()
