"""Unit tests for Global Asset Library path portability and migration safeguards."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.paths import (
    get_app_root,
    get_shared_data_dir,
    get_shared_library_dir,
    get_local_config_dir,
)
from services.library_service import LibraryService
from services.library_migration import LibraryMigrationService


class TestLibraryMigration(unittest.TestCase):
    """Test suite for Milestone 4: Global Asset Library portability and migration safeguards."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="cw_test_m4_"))
        self.source_dir = self.test_dir / "source"
        self.target_dir = self.test_dir / "target"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Path Resolution Tests
    # -------------------------------------------------------------------------

    def test_path_resolution_library(self):
        """Verify dynamic resolution of shared library directory."""
        shared_data = get_shared_data_dir()
        self.assertEqual(get_shared_library_dir(), shared_data / "library")

    # -------------------------------------------------------------------------
    # 2. Dry-Run Non-Mutation Tests
    # -------------------------------------------------------------------------

    def test_library_dry_run_is_strictly_read_only(self):
        """Verify dry-run does not create target directories, files, or backups."""
        src_lib = self.source_dir / "library"
        src_lib.mkdir(parents=True, exist_ok=True)

        config_data = {
            "version": 1,
            "drives": [{"drive_id": "drv_1", "name": "Drive 1", "volume_serial": "1111"}],
            "locations": [{"location_id": "loc_1", "drive_id": "drv_1", "display_name": "Assets", "drive_relative_path": "Assets"}],
        }
        (src_lib / "global_library.json").write_text(json.dumps(config_data), encoding="utf-8")

        index_data = [
            {
                "id": "lib_1",
                "filename": "model.obj",
                "drive_id": "drv_1",
                "location_id": "loc_1",
                "file_size": 1024,
                "project_references": [{"project_name": "Cyclops", "mode": "copy"}],
            }
        ]
        (src_lib / "library_index.json").write_text(json.dumps(index_data), encoding="utf-8")

        tgt_lib = self.target_dir / "library"  # Does not exist yet

        migrator = LibraryMigrationService(source_dir=src_lib, target_dir=tgt_lib)
        report = migrator.analyze()

        self.assertEqual(report.source_drives_count, 1)
        self.assertEqual(report.source_locations_count, 1)
        self.assertEqual(report.source_assets_count, 1)
        self.assertEqual(len(report.new_drives), 1)
        self.assertEqual(len(report.new_locations), 1)
        self.assertEqual(len(report.new_assets), 1)
        self.assertFalse(tgt_lib.exists())
        self.assertIsNone(report.backup_dir)

    # -------------------------------------------------------------------------
    # 3. Migration Execution & Idempotency Tests
    # -------------------------------------------------------------------------

    def test_library_migration_execution_and_idempotency(self):
        """Verify execution copies config and index, preserving project asset references, and repeated migration is idempotent."""
        src_lib = self.source_dir / "library"
        src_lib.mkdir(parents=True, exist_ok=True)

        config_data = {
            "version": 1,
            "drives": [{"drive_id": "drv_1", "name": "Drive 1", "volume_serial": "1111"}],
            "locations": [{"location_id": "loc_1", "drive_id": "drv_1", "display_name": "Assets", "drive_relative_path": "Assets"}],
        }
        (src_lib / "global_library.json").write_text(json.dumps(config_data), encoding="utf-8")

        index_data = [
            {
                "id": "lib_1",
                "filename": "model.obj",
                "drive_id": "drv_1",
                "location_id": "loc_1",
                "file_size": 1024,
                "project_references": [{"project_name": "Cyclops", "mode": "copy"}],
            }
        ]
        (src_lib / "library_index.json").write_text(json.dumps(index_data), encoding="utf-8")

        tgt_lib = self.target_dir / "library"

        migrator = LibraryMigrationService(source_dir=src_lib, target_dir=tgt_lib)
        report1 = migrator.execute()

        self.assertEqual(len(report1.new_drives), 1)
        self.assertEqual(len(report1.new_locations), 1)
        self.assertEqual(len(report1.new_assets), 1)
        self.assertTrue((tgt_lib / "global_library.json").exists())
        self.assertTrue((tgt_lib / "library_index.json").exists())

        # Verify project reference preserved in target index
        tgt_index = json.loads((tgt_lib / "library_index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tgt_index), 1)
        self.assertEqual(tgt_index[0]["project_references"][0]["project_name"], "Cyclops")

        # Repeated migration (idempotent)
        migrator2 = LibraryMigrationService(source_dir=src_lib, target_dir=tgt_lib)
        report2 = migrator2.analyze()
        self.assertEqual(len(report2.new_drives), 0)
        self.assertEqual(len(report2.identical_drives), 1)
        self.assertEqual(len(report2.new_locations), 0)
        self.assertEqual(len(report2.identical_locations), 1)
        self.assertEqual(len(report2.new_assets), 0)
        self.assertEqual(len(report2.identical_assets), 1)
        self.assertEqual(len(report2.conflicting_assets), 0)

    # -------------------------------------------------------------------------
    # 4. Conflict Detection and Bundle Isolation Tests
    # -------------------------------------------------------------------------

    def test_library_conflict_detection_and_bundle_isolation(self):
        """Verify differing asset/drive records trigger conflict bundles without overwriting target."""
        src_lib = self.source_dir / "library"
        src_lib.mkdir(parents=True, exist_ok=True)
        (src_lib / "global_library.json").write_text(json.dumps({
            "drives": [{"drive_id": "drv_1", "name": "Source Drive Name", "volume_serial": "SRC_SER"}],
            "locations": [],
        }), encoding="utf-8")
        (src_lib / "library_index.json").write_text(json.dumps([
            {"id": "lib_1", "filename": "source_asset.png", "file_size": 100}
        ]), encoding="utf-8")

        tgt_lib = self.target_dir / "library"
        tgt_lib.mkdir(parents=True, exist_ok=True)
        (tgt_lib / "global_library.json").write_text(json.dumps({
            "drives": [{"drive_id": "drv_1", "name": "Target Drive Name", "volume_serial": "TGT_SER"}],
            "locations": [],
        }), encoding="utf-8")
        (tgt_lib / "library_index.json").write_text(json.dumps([
            {"id": "lib_1", "filename": "target_asset.png", "file_size": 200}
        ]), encoding="utf-8")

        migrator = LibraryMigrationService(source_dir=src_lib, target_dir=tgt_lib)
        report = migrator.execute()

        self.assertEqual(len(report.conflicting_drives), 1)
        self.assertEqual(len(report.conflicting_assets), 1)

        # Target records must NOT be overwritten
        tgt_cfg = json.loads((tgt_lib / "global_library.json").read_text(encoding="utf-8"))
        self.assertEqual(tgt_cfg["drives"][0]["name"], "Target Drive Name")
        tgt_idx = json.loads((tgt_lib / "library_index.json").read_text(encoding="utf-8"))
        self.assertEqual(tgt_idx[0]["filename"], "target_asset.png")

        # Conflict bundle exists
        conflicts = list((tgt_lib / "conflicts").glob("conflict_*"))
        self.assertEqual(len(conflicts), 1)
        self.assertTrue((conflicts[0] / "conflict_manifest.json").exists())

    # -------------------------------------------------------------------------
    # 5. Service Live Initialization Tests
    # -------------------------------------------------------------------------

    def test_library_service_custom_storage(self):
        """Verify LibraryService reads and writes to assigned directory."""
        lib_dir = self.test_dir / "lib_live"
        svc = LibraryService(storage_dir=lib_dir)

        self.assertTrue(lib_dir.exists())
        self.assertEqual(len(svc.get_drives()), 0)


if __name__ == "__main__":
    unittest.main()
