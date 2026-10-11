"""Tests for dynamic portable path resolution and atomic file persistence."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.paths import (
    get_app_root,
    get_shared_data_dir,
    get_shared_clients_dir,
    get_local_config_dir,
    get_local_cache_dir,
)
from core.storage import atomic_write_json, safe_read_json


class TestPortablePathsAndStorage(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tmp_path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_app_root_resolution(self):
        """Verify application root resolves to repository root regardless of current working directory."""
        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            root = get_app_root()
            self.assertTrue(root.is_dir())
            self.assertTrue((root / "core" / "paths.py").exists())
            self.assertEqual(get_shared_data_dir(), root / "data")
            self.assertEqual(get_shared_clients_dir(), root / "data" / "clients")
        finally:
            os.chdir(original_cwd)

    def test_env_override_paths(self):
        """Verify paths respect environment variable overrides."""
        fake_root = self.tmp_path / "fake_app"
        fake_root.mkdir()
        fake_data = self.tmp_path / "custom_data"
        fake_data.mkdir()

        os.environ["CREATIVE_WORKSPACE_APP_ROOT"] = str(fake_root)
        os.environ["CREATIVE_WORKSPACE_SHARED_DATA_DIR"] = str(fake_data)
        try:
            self.assertEqual(get_app_root(), fake_root)
            self.assertEqual(get_shared_data_dir(), fake_data)
            self.assertEqual(get_shared_clients_dir(), fake_data / "clients")
        finally:
            os.environ.pop("CREATIVE_WORKSPACE_APP_ROOT", None)
            os.environ.pop("CREATIVE_WORKSPACE_SHARED_DATA_DIR", None)

    def test_atomic_write_json_basic(self):
        """Verify atomic write creates valid JSON file and cleans up temp files."""
        target_file = self.tmp_path / "test_folder" / "sample.json"
        data = {"key": "value", "numbers": [1, 2, 3], "nested": {"a": True}}

        result_path = atomic_write_json(target_file, data)
        self.assertEqual(result_path, target_file)
        self.assertTrue(target_file.exists())

        # Verify no temp files remain in directory
        temp_files = list(target_file.parent.glob("*.tmp"))
        self.assertEqual(len(temp_files), 0)

        read_data, err = safe_read_json(target_file)
        self.assertIsNone(err)
        self.assertEqual(read_data, data)

    def test_atomic_write_overwrites_existing(self):
        """Verify atomic write cleanly updates existing file."""
        target_file = self.tmp_path / "update.json"
        atomic_write_json(target_file, {"version": 1})
        atomic_write_json(target_file, {"version": 2, "updated": True})

        read_data, err = safe_read_json(target_file)
        self.assertIsNone(err)
        self.assertEqual(read_data["version"], 2)
        self.assertTrue(read_data["updated"])

    def test_safe_read_json_errors(self):
        """Verify safe read gracefully handles missing, empty, and corrupted JSON files."""
        # 1. Non-existent file
        missing = self.tmp_path / "non_existent.json"
        data, err = safe_read_json(missing, default={"fallback": True})
        self.assertEqual(data, {"fallback": True})
        self.assertIn("not found", err.lower())

        # 2. Empty file
        empty = self.tmp_path / "empty.json"
        empty.write_text("", encoding="utf-8")
        data, err = safe_read_json(empty, default=[])
        self.assertEqual(data, [])
        self.assertIn("empty", err.lower())

        # 3. Corrupt file
        corrupt = self.tmp_path / "corrupt.json"
        corrupt.write_text("{invalid json: broken", encoding="utf-8")
        data, err = safe_read_json(corrupt, default=None)
        self.assertIsNone(data)
        self.assertIn("decode error", err.lower())


if __name__ == "__main__":
    unittest.main()
