"""Focused unit tests for Global Asset Library Service and Drive Detection."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.library_models import AssetAvailability, LibraryAsset, LibraryDrive, LibraryLocation
from services.drive_detection_service import DriveDetectionService, MARKER_FILENAME
from services.library_service import LibraryService


class TestLibraryService(unittest.TestCase):
    """Test suite covering headless Asset Library catalog, drive detection, and delta scanning."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir)

        # Storage directory for global catalog (~/.creativeworkspace/library/)
        self.storage_dir = self.test_root / "library_storage"
        self.storage_dir.mkdir(parents=True)

        # Mock External Drive 1 (Simulating e.g. "E:\\")
        self.mock_drive_1 = self.test_root / "Drive_E"
        self.mock_drive_1.mkdir(parents=True)

        # Mock External Drive 2 (Simulating e.g. "F:\\")
        self.mock_drive_2 = self.test_root / "Drive_F"
        self.mock_drive_2.mkdir(parents=True)

        self.drive_detector = DriveDetectionService()
        self.library_service = LibraryService(
            storage_dir=self.storage_dir,
            drive_detector=self.drive_detector,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_drive_marker_creation_and_persistent_identity(self):
        """Verify adding a location creates .creativeworkspace/library_drive.json marker."""
        loc_dir = self.mock_drive_1 / "3D_Assets" / "Megascans"
        loc_dir.mkdir(parents=True)
        (loc_dir / "Rock_01.fbx").write_bytes(b"dummy_fbx_data")

        # Mock get_drive_root to return mock_drive_1
        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            self.drive_detector.set_test_mount_override("temp_id", str(self.mock_drive_1))
            loc, drive = self.library_service.add_library_location(
                loc_dir,
                display_name="Megascans Collection",
                drive_name="Samsung T7 Portable",
            )

            # Check marker file on drive root
            marker_path = self.mock_drive_1 / MARKER_FILENAME
            self.assertTrue(marker_path.exists())

            marker_data = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertEqual(marker_data["drive_id"], drive.drive_id)
            self.assertEqual(marker_data["name"], "Samsung T7 Portable")

    def test_nested_folder_scanning_and_asset_registration(self):
        """Verify recursive nested folder scanning registers assets with metadata in-place."""
        loc_dir = self.mock_drive_1 / "Textures"
        sub_dir_1 = loc_dir / "PBR" / "Wood"
        sub_dir_2 = loc_dir / "HDRIs" / "Outdoor"
        sub_dir_1.mkdir(parents=True)
        sub_dir_2.mkdir(parents=True)

        (sub_dir_1 / "Oak_Albedo_v02.png").write_bytes(b"png_data")
        (sub_dir_1 / "Oak_Normal.tga").write_bytes(b"tga_data")
        (sub_dir_2 / "sunset_field_4k.exr").write_bytes(b"exr_data")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            self.drive_detector.set_test_mount_override("temp", str(self.mock_drive_1))
            loc, drive = self.library_service.add_library_location(
                loc_dir,
                display_name="Textures & HDRIs",
                drive_name="WorkDrive_01",
            )

            # Verify 3 assets registered
            assets = self.library_service.query_assets(location_id=loc.location_id)
            self.assertEqual(len(assets), 3)

            filenames = {a.filename for a in assets}
            self.assertIn("Oak_Albedo_v02.png", filenames)
            self.assertIn("Oak_Normal.tga", filenames)
            self.assertIn("sunset_field_4k.exr", filenames)

            # Check intelligence parsing (version / category)
            oak_asset = next(a for a in assets if a.filename == "Oak_Albedo_v02.png")
            self.assertEqual(oak_asset.version, "v02")
            self.assertEqual(oak_asset.category, "Textures & Images")

            hdri_asset = next(a for a in assets if a.filename == "sunset_field_4k.exr")
            self.assertEqual(hdri_asset.category, "HDRIs & Passes")

    def test_delta_scan_avoids_reindexing_unchanged_files(self):
        """Verify delta scan identifies unchanged files without redundant re-indexing."""
        loc_dir = self.mock_drive_1 / "Models"
        loc_dir.mkdir(parents=True)
        (loc_dir / "robot_lod0.glb").write_bytes(b"glb_data_initial")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            self.drive_detector.set_test_mount_override("temp", str(self.mock_drive_1))
            loc, drive = self.library_service.add_library_location(loc_dir, display_name="Models")

            # First scan happened during add_library_location -> 1 added
            # Second scan without changes
            stats_2 = self.library_service.scan_location(loc.location_id)
            self.assertEqual(stats_2["unchanged"], 1)
            self.assertEqual(stats_2["added"], 0)
            self.assertEqual(stats_2["updated"], 0)

            # Add a new file
            (loc_dir / "robot_lod1.glb").write_bytes(b"glb_data_lod1")
            stats_3 = self.library_service.scan_location(loc.location_id)
            self.assertEqual(stats_3["unchanged"], 1)
            self.assertEqual(stats_3["added"], 1)
            self.assertEqual(stats_3["updated"], 0)

    def test_drive_letter_change_immunity(self):
        """Verify assets resolve cleanly when Windows changes drive letter (e.g. E: -> F:)."""
        loc_dir = self.mock_drive_1 / "Kitbash"
        loc_dir.mkdir(parents=True)
        model_file = loc_dir / "sci_fi_door.fbx"
        model_file.write_bytes(b"fbx_door_data")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(
                loc_dir,
                display_name="Kitbash",
                drive_name="Samsung T7",
            )

        asset = self.library_service.query_assets(location_id=loc.location_id)[0]

        # Simulate Drive currently mounted on mock_drive_1 (e.g. "E:\")
        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.AVAILABLE)
        resolved_p1 = self.library_service.resolve_asset_path(asset)
        self.assertEqual(resolved_p1.resolve(), model_file.resolve())

        # Simulate Drive unmounted and remounted at a NEW drive path (e.g. "F:\" -> mock_drive_2)
        # Move files to mock_drive_2 to simulate same physical volume mounted under a different drive letter
        shutil.copytree(self.mock_drive_1, self.mock_drive_2, dirs_exist_ok=True)
        remounted_model_file = self.mock_drive_2 / "Kitbash" / "sci_fi_door.fbx"

        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_2))

        # Asset should IMMEDIATELY resolve to mock_drive_2 with ZERO catalog modification
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.AVAILABLE)
        resolved_p2 = self.library_service.resolve_asset_path(asset)
        self.assertEqual(resolved_p2.resolve(), remounted_model_file.resolve())

    def test_drive_offline_and_reconnection_state_transitions(self):
        """Verify availability transitions: Available -> Offline -> Available when drive unplugs."""
        loc_dir = self.mock_drive_1 / "Audio"
        loc_dir.mkdir(parents=True)
        (loc_dir / "laser_blast.wav").write_bytes(b"wav_data")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(loc_dir, display_name="Audio")

        asset = self.library_service.query_assets(location_id=loc.location_id)[0]

        # 1. Drive is connected
        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.AVAILABLE)
        self.assertIsNotNone(self.library_service.resolve_asset_path(asset))

        # 2. Drive is unplugged / disconnected
        self.drive_detector.set_test_mount_override(drive.drive_id, None)
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.OFFLINE)
        # Path resolution returns None when offline
        self.assertIsNone(self.library_service.resolve_asset_path(asset))
        # But metadata is STILL fully accessible in catalog
        cached_asset = self.library_service.get_asset(asset.id)
        self.assertEqual(cached_asset.filename, "laser_blast.wav")
        self.assertEqual(cached_asset.category, "Audio")

        # 3. Drive is reconnected
        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.AVAILABLE)
        self.assertIsNotNone(self.library_service.resolve_asset_path(asset))

    def test_missing_and_possibly_changed_states(self):
        """Verify Missing and Possibly Changed availability states when files are deleted or modified on disk."""
        loc_dir = self.mock_drive_1 / "Shaders"
        loc_dir.mkdir(parents=True)
        shader_file = loc_dir / "glass_shader.blend"
        shader_file.write_bytes(b"initial_blend_content")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(loc_dir, display_name="Shaders")

        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
        asset = self.library_service.query_assets(location_id=loc.location_id)[0]

        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.AVAILABLE)

        # 1. Modify file on disk -> Possibly Changed
        shader_file.write_bytes(b"modified_longer_blend_content_updated")
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.POSSIBLY_CHANGED)

        # Rescan updates catalog back to Available
        self.library_service.scan_location(loc.location_id)
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.AVAILABLE)

        # 2. Delete file on disk -> Missing (since drive is mounted)
        shader_file.unlink()
        self.assertEqual(self.library_service.get_asset_availability(asset), AssetAvailability.MISSING)

    def test_metadata_editing_and_project_referencing(self):
        """Verify tags, notes, favorites, and project reference logging persist across service reloads."""
        loc_dir = self.mock_drive_1 / "Props"
        loc_dir.mkdir(parents=True)
        (loc_dir / "wooden_chair.glb").write_bytes(b"chair_glb")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            self.drive_detector.set_test_mount_override("temp", str(self.mock_drive_1))
            loc, drive = self.library_service.add_library_location(loc_dir, display_name="Props")

        asset = self.library_service.query_assets(location_id=loc.location_id)[0]

        # Update metadata
        self.library_service.update_asset(
            asset.id,
            tags=["furniture", "props", "interior"],
            notes="Low-poly medieval tavern prop.",
            favorite=True,
        )

        # Record project reference
        self.library_service.record_project_reference(
            asset.id,
            project_location="C:/Projects/MedievalTavern",
            project_name="MedievalTavern",
            mode="reference",
        )

        # Create a new LibraryService pointing to the same storage_dir to test persistence reload
        reloaded_service = LibraryService(
            storage_dir=self.storage_dir,
            drive_detector=self.drive_detector,
        )
        reloaded_asset = reloaded_service.get_asset(asset.id)

        self.assertIsNotNone(reloaded_asset)
        self.assertEqual(reloaded_asset.tags, ["furniture", "props", "interior"])
        self.assertEqual(reloaded_asset.notes, "Low-poly medieval tavern prop.")
        self.assertTrue(reloaded_asset.favorite)
        self.assertEqual(len(reloaded_asset.project_references), 1)
        self.assertEqual(reloaded_asset.project_references[0]["project_name"], "MedievalTavern")

    def test_query_filter_capabilities(self):
        """Verify search and multi-facet filtering across catalog assets."""
        loc_dir = self.mock_drive_1 / "Variety"
        loc_dir.mkdir(parents=True)
        (loc_dir / "hero_armor.fbx").write_bytes(b"data1")
        (loc_dir / "environment_rock.fbx").write_bytes(b"data2")
        (loc_dir / "ambient_wind.wav").write_bytes(b"data3")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            self.drive_detector.set_test_mount_override("temp", str(self.mock_drive_1))
            loc, drive = self.library_service.add_library_location(loc_dir, display_name="Variety")

        assets = self.library_service.query_assets(location_id=loc.location_id)
        hero = next(a for a in assets if "hero" in a.filename)
        self.library_service.update_asset(hero.id, tags=["character", "armor"], favorite=True)

        # Text query
        q_results = self.library_service.query_assets(query="armor")
        self.assertEqual(len(q_results), 1)
        self.assertEqual(q_results[0].filename, "hero_armor.fbx")

        # Category filter
        model_results = self.library_service.query_assets(category="3D Models")
        self.assertEqual(len(model_results), 2)

        audio_results = self.library_service.query_assets(category="Audio")
        self.assertEqual(len(audio_results), 1)

        # Favorites filter
        fav_results = self.library_service.query_assets(favorite=True)
        self.assertEqual(len(fav_results), 1)
        self.assertEqual(fav_results[0].filename, "hero_armor.fbx")


if __name__ == "__main__":
    unittest.main()
