import json
import tempfile
import unittest
from pathlib import Path
from services.settings_service import SettingsService


class TestSettingsService(unittest.TestCase):
    """Focused unit tests for SettingsService machine-local persistence and resilience."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_location_is_machine_local(self):
        """1. Verify default config directory points to ~/.creativeworkspace."""
        service = SettingsService()
        expected_folder = Path.home() / ".creativeworkspace"
        expected_file = expected_folder / "settings.json"
        self.assertEqual(service.config_folder, expected_folder)
        self.assertEqual(service.settings_file, expected_file)
        self.assertTrue(service.settings_file.exists())

    def test_missing_settings_file(self):
        """2. Verify missing settings file is created with clean defaults upon initialization."""
        settings_file = self.config_dir / "settings.json"
        self.assertFalse(settings_file.exists())

        service = SettingsService(config_dir=self.config_dir)
        self.assertTrue(settings_file.exists())

        data = service.load()
        self.assertEqual(data.get("recent_projects"), [])
        self.assertEqual(data.get("last_session"), {})
        self.assertEqual(service.recent_projects(), [])
        self.assertEqual(service.load_last_session(), {})

    def test_empty_zero_byte_settings_file(self):
        """3. Verify zero-byte/empty settings file recovers gracefully without throwing JSONDecodeError."""
        settings_file = self.config_dir / "settings.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("", encoding="utf-8")
        self.assertEqual(settings_file.stat().st_size, 0)

        service = SettingsService(config_dir=self.config_dir)
        data = service.load()
        self.assertEqual(data.get("recent_projects"), [])
        self.assertEqual(data.get("last_session"), {})
        self.assertGreater(settings_file.stat().st_size, 0)

    def test_malformed_json_settings_file(self):
        """4. Verify invalid/malformed JSON recovers cleanly with default structure written back."""
        settings_file = self.config_dir / "settings.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("{corrupt json ...", encoding="utf-8")

        service = SettingsService(config_dir=self.config_dir)
        data = service.load()
        self.assertEqual(data.get("recent_projects"), [])
        self.assertEqual(data.get("last_session"), {})

        # Verify disk file is now valid JSON
        with open(settings_file, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        self.assertIn("recent_projects", persisted)
        self.assertIn("last_session", persisted)

    def test_malformed_non_dict_json(self):
        """5. Verify JSON containing non-dict root (e.g. array or primitive) recovers to default dict."""
        settings_file = self.config_dir / "settings.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text("[\"item1\", \"item2\"]", encoding="utf-8")

        service = SettingsService(config_dir=self.config_dir)
        data = service.load()
        self.assertEqual(data.get("recent_projects"), [])
        self.assertEqual(data.get("last_session"), {})

    def test_missing_expected_keys(self):
        """6. Verify settings file with missing expected keys is repaired and preserved."""
        settings_file = self.config_dir / "settings.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        # File has custom key but missing recent_projects and last_session
        partial_data = {"custom_field": 123}
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(partial_data, f)

        service = SettingsService(config_dir=self.config_dir)
        data = service.load()
        self.assertEqual(data.get("recent_projects"), [])
        self.assertEqual(data.get("last_session"), {})
        self.assertEqual(data.get("custom_field"), 123)

        # Verify repaired file was saved to disk
        with open(settings_file, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        self.assertIn("recent_projects", persisted)
        self.assertIn("last_session", persisted)
        self.assertEqual(persisted.get("custom_field"), 123)

    def test_valid_settings_loading_and_persistence(self):
        """7. Verify valid settings load accurately and changes persist to the local file."""
        service = SettingsService(config_dir=self.config_dir)

        # Add recent projects
        proj1 = r"G:\My Drive\CreativeWorkspace\workspace\proj1"
        proj2 = r"G:\My Drive\CreativeWorkspace\workspace\proj2"
        service.add_recent_project(proj1)
        service.add_recent_project(proj2)

        # Verify ordering (most recent first)
        recent = service.recent_projects()
        self.assertEqual(recent[0], str(Path(proj2)))
        self.assertEqual(recent[1], str(Path(proj1)))

        # Save and load session
        session_data = {
            "project": proj2,
            "workspace": "references",
            "explorer": {"projects_expanded": True},
        }
        service.save_last_session(session_data)
        self.assertEqual(service.load_last_session(), session_data)

        # Splitter state
        service.set_splitter_state("000000ff")
        self.assertEqual(service.get_splitter_state(), "000000ff")

        # Reload new instance from same directory
        service2 = SettingsService(config_dir=self.config_dir)
        self.assertEqual(service2.recent_projects(), [str(Path(proj2)), str(Path(proj1))])
        self.assertEqual(service2.load_last_session(), session_data)
        self.assertEqual(service2.get_splitter_state(), "000000ff")

    def test_remove_recent_project(self):
        """8. Verify removing a recent project updates settings."""
        service = SettingsService(config_dir=self.config_dir)
        proj1 = r"G:\My Drive\CreativeWorkspace\workspace\proj1"
        proj2 = r"G:\My Drive\CreativeWorkspace\workspace\proj2"
        service.add_recent_project(proj1)
        service.add_recent_project(proj2)

        service.remove_recent_project(proj1)
        self.assertEqual(service.recent_projects(), [str(Path(proj2))])


if __name__ == "__main__":
    unittest.main()
