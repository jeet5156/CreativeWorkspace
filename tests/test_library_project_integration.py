"""Focused tests for Library Asset -> Project integration (Reference and Copy workflows)."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

from models.project import Project
from models.library_models import AssetAvailability, LibraryAsset, LibraryDrive, LibraryLocation
from services.drive_detection_service import DriveDetectionService
from services.library_service import LibraryService
from services.asset_service import AssetService
from services.thumbnail_service import ThumbnailService
from core.inspectable_adapters import AssetInspectable, LibraryAssetInspectable
from ui.panels.library_workspace_panel import LibraryWorkspacePanel
from ui.panels.inspector_panel import InspectorPanel


# Ensure single QApplication instance
app = QApplication.instance()
if not app:
    app = QApplication([])


class TestLibraryProjectIntegration(unittest.TestCase):
    """Test suite verifying Library asset Reference and Copy integration into projects."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # External drives
        self.mock_drive_1 = self.temp_path / "Drive_E"
        self.mock_drive_1.mkdir(parents=True)
        self.mock_drive_2 = self.temp_path / "Drive_F"
        self.mock_drive_2.mkdir(parents=True)

        # Global library catalog
        self.library_dir = self.temp_path / "global_library"
        self.library_dir.mkdir(parents=True)

        # Project folder
        self.project_dir = self.temp_path / "Project_SciFi"
        self.project_dir.mkdir(parents=True)
        for folder in ("Assets", "References", "Renders", "Exports"):
            (self.project_dir / folder).mkdir(parents=True)

        self.project = Project(
            name="Sci-Fi Weapon",
            project_type="game_asset",
            location=str(self.project_dir),
        )

        # Services
        self.drive_detector = DriveDetectionService()
        self.drive_detector.set_test_mount_override("drv_1", str(self.mock_drive_1))
        self.drive_detector.set_test_mount_override("drv_2", str(self.mock_drive_2))

        self.library_service = LibraryService(storage_dir=self.library_dir, drive_detector=self.drive_detector)
        self.asset_service = AssetService()
        self.thumbnail_service = ThumbnailService(asset_service=self.asset_service)

        # Mock context
        self.context = MagicMock()
        self.context.current_project = self.project
        self.context.library_service = self.library_service
        self.context.asset_service = self.asset_service
        self.context.thumbnail_service = self.thumbnail_service

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 1. Reference in Project Tests
    # -------------------------------------------------------------------------

    def test_reference_asset_without_copying_source_file(self):
        """Verify adding a reference creates a catalog reference without copying source file."""
        models_dir = self.mock_drive_1 / "3DModels"
        models_dir.mkdir(parents=True)
        src_file = models_dir / "plasma_rifle.fbx"
        src_file.write_bytes(b"PLASMA_RIFLE_RAW_BINARY_DATA")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(models_dir, display_name="3DModels")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
            self.library_service._last_checked_mounts[drive.drive_id] = str(self.mock_drive_1)

        lib_assets = self.library_service.query_assets()
        self.assertEqual(len(lib_assets), 1)
        lib_asset = lib_assets[0]

        # Add library reference to active project
        ref_entry = self.asset_service.add_library_reference(self.project, lib_asset, target_category="References")

        # 1. Verify NO file was copied to project References folder
        project_ref_file = self.project_dir / "References" / "plasma_rifle.fbx"
        self.assertFalse(project_ref_file.exists())

        # 2. Verify reference properties stored
        self.assertTrue(ref_entry.get("is_library_reference"))
        self.assertEqual(ref_entry.get("library_asset_id"), lib_asset.id)
        self.assertEqual(ref_entry.get("drive_id"), drive.drive_id)
        self.assertEqual(ref_entry.get("drive_relative_path"), "3DModels/plasma_rifle.fbx")
        self.assertNotIn(str(self.mock_drive_1), str(ref_entry.get("drive_relative_path")))

    def test_reference_persists_in_project_data_across_reloads(self):
        """Verify project library references persist on disk across service reloads and index rebuilds."""
        fol = self.mock_drive_1 / "Textures"
        fol.mkdir(parents=True)
        (fol / "metal_diffuse.png").write_bytes(b"PNG_DATA")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Textures")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        self.asset_service.add_library_reference(self.project, lib_asset, target_category="References")

        # Reload fresh AssetService
        fresh_asset_service = AssetService()
        project_refs = fresh_asset_service.get_assets(self.project, category="library_references")
        self.assertEqual(len(project_refs), 1)
        self.assertEqual(project_refs[0]["filename"], "metal_diffuse.png")
        self.assertTrue(project_refs[0]["is_library_reference"])

        # Run rebuild_index and ensure reference is preserved
        fresh_asset_service.rebuild_index(self.project, force=True)
        rebuilt_refs = fresh_asset_service.get_assets(self.project, category="library_references")
        self.assertEqual(len(rebuilt_refs), 1)
        self.assertTrue(rebuilt_refs[0]["is_library_reference"])

    def test_reference_resolves_after_simulated_drive_letter_change(self):
        """Verify reference resolves dynamically when drive letter / mount point changes from E: to F:."""
        fol = self.mock_drive_1 / "Props"
        fol.mkdir(parents=True)
        (fol / "turret.glb").write_bytes(b"TURRET_GLB")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Props")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        ref_entry = self.asset_service.add_library_reference(self.project, lib_asset)

        # Initial path resolution
        resolved_1 = self.drive_detector.resolve_drive_path(ref_entry["drive_id"], ref_entry["drive_relative_path"])
        self.assertEqual(resolved_1, self.mock_drive_1 / "Props" / "turret.glb")

        # Simulate drive letter change to Drive_F (e.g. E: -> F:)
        new_mount = self.mock_drive_2
        (new_mount / "Props").mkdir(parents=True, exist_ok=True)
        (new_mount / "Props" / "turret.glb").write_bytes(b"TURRET_GLB")

        self.drive_detector.set_test_mount_override(drive.drive_id, str(new_mount))
        self.library_service.check_drive_mounts()

        # Dynamic resolution to new mount point
        resolved_2 = self.drive_detector.resolve_drive_path(ref_entry["drive_id"], ref_entry["drive_relative_path"])
        self.assertEqual(resolved_2, new_mount / "Props" / "turret.glb")

    def test_offline_referenced_asset_remains_in_project(self):
        """Verify when external drive is disconnected, the reference stays in the project as Offline."""
        fol = self.mock_drive_1 / "Audio"
        fol.mkdir(parents=True)
        (fol / "laser_blast.wav").write_bytes(b"WAV_DATA")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Audio")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        self.asset_service.add_library_reference(self.project, lib_asset)

        # Simulate Drive Disconnected
        self.drive_detector.set_test_mount_override(drive.drive_id, None)
        self.library_service.check_drive_mounts()

        # Reference must still be in project
        proj_assets = self.asset_service.get_assets(self.project, category="Library References")
        self.assertEqual(len(proj_assets), 1)
        ref_asset = proj_assets[0]
        self.assertEqual(ref_asset["filename"], "laser_blast.wav")

        # Drive is offline so resolved path is None
        resolved_path = self.drive_detector.resolve_drive_path(ref_asset["drive_id"], ref_asset["drive_relative_path"])
        self.assertIsNone(resolved_path)

    # -------------------------------------------------------------------------
    # 2. Copy to Project Tests
    # -------------------------------------------------------------------------

    def test_copy_creates_independent_project_local_file(self):
        """Verify copying a library asset creates a genuine local file in project storage."""
        fol = self.mock_drive_1 / "Concept"
        fol.mkdir(parents=True)
        (fol / "concept_art.psd").write_bytes(b"PSD_DATA")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Art")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        self.asset_service.copy_library_asset(self.project, lib_asset, self.library_service, target_section="References")

        # Verify physical file exists in project storage
        local_path = self.project_dir / "References" / "concept_art.psd"
        self.assertTrue(local_path.exists())
        self.assertEqual(local_path.read_bytes(), b"PSD_DATA")

        # Verify indexed in project metadata as a native project asset (not a library reference)
        proj_assets = self.asset_service.get_assets(self.project, category="References")
        self.assertEqual(len(proj_assets), 1)
        self.assertFalse(proj_assets[0].get("is_library_reference", False))
        self.assertEqual(proj_assets[0]["category"], "References")

    def test_reference_and_copy_are_distinct_operations(self):
        """Verify Reference creates index pointer without file, while Copy creates independent file."""
        fol = self.mock_drive_1 / "Meshes"
        fol.mkdir(parents=True)
        (fol / "helmet.obj").write_bytes(b"HELMET")
        (fol / "shield.obj").write_bytes(b"SHIELD")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Meshes")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        assets = self.library_service.query_assets()
        helmet = next(a for a in assets if a.filename == "helmet.obj")
        shield = next(a for a in assets if a.filename == "shield.obj")

        # 1. Reference helmet
        self.asset_service.add_library_reference(self.project, helmet)
        # 2. Copy shield
        self.asset_service.copy_library_asset(self.project, shield, self.library_service)

        # Helmet has no local file; Shield has a local file
        self.assertFalse((self.project_dir / "References" / "helmet.obj").exists())
        self.assertTrue((self.project_dir / "References" / "shield.obj").exists())

        # Both are visible in project index (1 in Library References, 1 in References)
        all_assets = self.asset_service.get_assets(self.project)
        self.assertEqual(len(all_assets), 2)
        ref_names = {r["filename"] for r in all_assets}
        self.assertEqual(ref_names, {"helmet.obj", "shield.obj"})
        self.assertEqual(len(self.asset_service.get_assets(self.project, category="References")), 1)
        self.assertEqual(len(self.asset_service.get_assets(self.project, category="Library References")), 1)

    # -------------------------------------------------------------------------
    # 3. UI Context Menu & Inspector Integration
    # -------------------------------------------------------------------------

    def test_inspector_exposes_library_source_and_project_reference_status(self):
        """Verify Inspector displays catalog source and current project reference status."""
        fol = self.mock_drive_1 / "VFX"
        fol.mkdir(parents=True)
        (fol / "spark.png").write_bytes(b"SPARK")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="VFX")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]

        # Inspect before referencing
        inspectable_1 = LibraryAssetInspectable(lib_asset, library_service=self.library_service, context=self.context)
        sections_1 = inspectable_1.get_inspection_sections()
        field_map_1 = {f.key: f.value for f in sections_1[0].fields}
        self.assertEqual(field_map_1["source"], "📚 Global Asset Library")
        self.assertEqual(field_map_1["project_reference"], f"Not Referenced in '{self.project.name}'")

        # Add project reference and log in library
        self.asset_service.add_library_reference(self.project, lib_asset)
        self.library_service.log_project_reference(lib_asset.id, self.project.location, self.project.name, mode="reference")

        # Inspect after referencing
        inspectable_2 = LibraryAssetInspectable(lib_asset, library_service=self.library_service, context=self.context)
        sections_2 = inspectable_2.get_inspection_sections()
        field_map_2 = {f.key: f.value for f in sections_2[0].fields}
        self.assertEqual(field_map_2["project_reference"], f"Referenced in '{self.project.name}'")

    def test_library_workspace_panel_toolbar_buttons_and_actions(self):
        """Verify LibraryWorkspacePanel toolbar buttons enable on selection and execute reference/copy."""
        fol = self.mock_drive_1 / "Vehicles"
        fol.mkdir(parents=True)
        (fol / "speeder.fbx").write_bytes(b"SPEEDER_FBX")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Vehicles")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        panel = LibraryWorkspacePanel(self.context)
        panel.show()
        panel.refresh_library()

        # Initially no selection -> buttons disabled
        self.assertFalse(panel.btn_ref_project.isEnabled())
        self.assertFalse(panel.btn_copy_project.isEnabled())

        # Select location folder -> still no asset selected
        lib_asset = self.library_service.query_assets()[0]
        panel._current_location_id = loc.location_id
        panel.refresh_library()

        # Select the asset card
        panel._on_card_clicked(lib_asset.id)
        self.assertTrue(panel.btn_ref_project.isEnabled())
        self.assertTrue(panel.btn_copy_project.isEnabled())

        # Trigger reference action from panel (with mocked QMessageBox)
        with patch.object(QMessageBox, "information") as mock_info:
            panel._on_toolbar_reference_clicked()
            mock_info.assert_called_once()

        # Verify reference created in project
        proj_refs = self.asset_service.get_assets(self.project, category="library_references")
        self.assertEqual(len(proj_refs), 1)
        self.assertEqual(proj_refs[0]["filename"], "speeder.fbx")
        self.assertTrue(proj_refs[0]["is_library_reference"])

        # Trigger copy action from panel (with mocked QMessageBox)
        with patch.object(QMessageBox, "information") as mock_info_copy:
            panel._on_toolbar_copy_clicked()
            mock_info_copy.assert_called_once()

        # Verify copy created in local project filesystem
        self.assertTrue((self.project_dir / "References" / "speeder.fbx").exists())

    def test_asset_inspectable_shows_library_reference_properties(self):
        """Verify project AssetInspectable formats library-referenced assets correctly."""
        fol = self.mock_drive_1 / "GUI"
        fol.mkdir(parents=True)
        (fol / "crosshair.png").write_bytes(b"CROSSHAIR")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="GUI")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        ref_entry = self.asset_service.add_library_reference(self.project, lib_asset)

        inspectable = AssetInspectable(ref_entry, asset_service=self.asset_service, project=self.project)
        sections = inspectable.get_inspection_sections()
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, "Library Reference Properties")

        field_map = {f.key: f.value for f in sections[0].fields}
        self.assertEqual(field_map["source"], "📚 Global Asset Library Reference")
        self.assertEqual(field_map["filename"], "crosshair.png")
        self.assertEqual(field_map["drive_relative_path"], "GUI/crosshair.png")

    def test_referenced_asset_appears_in_project_library_references_section(self):
        """Verify referenced assets are returned by category='library_references' and populate UI."""
        from ui.panels.asset_workspace_panel import AssetWorkspacePanel

        fol = self.mock_drive_1 / "Textures"
        fol.mkdir(parents=True)
        (fol / "brick_diffuse.png").write_bytes(b"BRICK")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Textures")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        ref = self.asset_service.add_library_reference(self.project, lib_asset)

        # AssetService query
        lib_refs = self.asset_service.get_assets(self.project, category="library_references")
        self.assertEqual(len(lib_refs), 1)
        self.assertEqual(lib_refs[0]["filename"], "brick_diffuse.png")
        self.assertTrue(lib_refs[0]["is_library_reference"])

        # AssetWorkspacePanel display
        panel = AssetWorkspacePanel()
        panel.show_project_section(self.project, "library_references", self.context)
        self.assertEqual(len(panel._cards), 1)
        self.assertIn(ref["id"], panel._cards)
        card = panel._cards[ref["id"]]
        self.assertIn("🔗 Library", card.meta.text())

    def test_offline_reference_remains_visible_with_offline_state(self):
        """Verify referenced asset remains visible in project workspace with Offline status when drive detached."""
        from ui.panels.asset_workspace_panel import AssetWorkspacePanel

        fol = self.mock_drive_1 / "Audio"
        fol.mkdir(parents=True)
        (fol / "theme.wav").write_bytes(b"WAV")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Audio")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        ref = self.asset_service.add_library_reference(self.project, lib_asset)

        # Simulate drive detachment
        self.drive_detector.set_test_mount_override(drive.drive_id, None)
        self.library_service.check_drive_mounts()

        # Reload workspace section
        panel = AssetWorkspacePanel()
        panel.show_project_section(self.project, "library_references", self.context)

        # Still visible
        self.assertEqual(len(panel._cards), 1)
        card = panel._cards[ref["id"]]
        self.assertEqual(card.asset.get("availability"), "Offline")
        self.assertIn("⚠️ Offline", card.meta.text())

    def test_remove_reference_does_not_delete_library_asset_or_file(self):
        """Verify removing a reference from project removes only project entry, leaving source file & library intact."""
        fol = self.mock_drive_1 / "Props"
        fol.mkdir(parents=True)
        source_file = fol / "chair.fbx"
        source_file.write_bytes(b"CHAIR_FBX")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Props")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        ref = self.asset_service.add_library_reference(self.project, lib_asset, library_service=self.library_service)

        self.assertEqual(len(self.asset_service.get_assets(self.project, category="library_references")), 1)
        self.assertEqual(len(lib_asset.project_references), 1)

        # Remove reference from project
        res = self.asset_service.remove_library_reference(self.project, ref["id"], library_service=self.library_service)
        self.assertTrue(res)

        # Verify project no longer has reference
        self.assertEqual(len(self.asset_service.get_assets(self.project, category="library_references")), 0)

        # CRITICAL: Physical file on drive MUST still exist
        self.assertTrue(source_file.exists())

        # CRITICAL: LibraryAsset in global catalog MUST still exist
        catalog_assets = self.library_service.query_assets()
        self.assertEqual(len(catalog_assets), 1)
        self.assertEqual(catalog_assets[0].filename, "chair.fbx")
        self.assertEqual(len(catalog_assets[0].project_references), 0)

    def test_open_in_asset_library_navigation_and_selection(self):
        """Verify 'Reveal in Asset Library' navigates directly to containing folder and selects the asset."""
        from ui.panels.asset_workspace_panel import AssetWorkspacePanel

        # 1. Setup nested library folder hierarchy
        root_fol = self.mock_drive_1 / "3D_Assets"
        nested_fol = root_fol / "Characters" / "Hero"
        nested_fol.mkdir(parents=True)
        (nested_fol / "warrior.fbx").write_bytes(b"WARRIOR_FBX")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(root_fol, display_name="3D Assets")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        lib_asset = self.library_service.query_assets()[0]
        ref = self.asset_service.add_library_reference(self.project, lib_asset, library_service=self.library_service)

        # 2. Setup LibraryWorkspacePanel and WorkspaceManager
        library_panel = LibraryWorkspacePanel(self.context)
        library_panel.show()

        mock_wm = MagicMock()
        mock_wm.library_panel = library_panel
        self.context.workspace_manager = mock_wm

        project_panel = AssetWorkspacePanel()
        project_panel.show_project_section(self.project, "library_references", self.context)

        # 3. Trigger Reveal in Asset Library from project reference
        project_panel._open_in_asset_library(ref["id"])

        mock_wm.show_module.assert_called_once_with("assets_lib")
        self.assertEqual(library_panel._current_location_id, loc.location_id)
        self.assertEqual(library_panel._current_subpath, "Characters/Hero")
        self.assertEqual(library_panel.get_selected_ids(), [lib_asset.id])

        # 4. Verify Reveal in Asset Library works even when drive is Offline
        self.drive_detector.set_test_mount_override(drive.drive_id, None)
        self.library_service.check_drive_mounts()

        # Reset panel to root
        library_panel._current_location_id = None
        library_panel._current_subpath = ""
        library_panel.refresh_library()

        # Trigger navigation while offline
        res = library_panel.navigate_to_asset(ref)
        self.assertTrue(res)
        self.assertEqual(library_panel._current_location_id, loc.location_id)
        self.assertEqual(library_panel._current_subpath, "Characters/Hero")
        self.assertEqual(library_panel.get_selected_ids(), [lib_asset.id])
        self.assertIn(lib_asset.id, library_panel._cards)
        self.assertEqual(library_panel._cards[lib_asset.id].asset.get("availability"), "Offline")

    def test_project_references_vs_library_references_segregation_and_legacy_records(self):
        """Regression test for Issue 3B:
        - 1 normal local project reference in References/
        - 1 global library reference with legacy category 'References'
        Verify:
        - References returns only local file
        - Library References returns only library asset
        - Zero duplication across sections
        """
        # 1. Create a physical project reference in References/
        ref_dir = Path(self.project.location) / "References"
        ref_dir.mkdir(parents=True, exist_ok=True)
        local_file = ref_dir / "local_concept.png"
        local_file.write_bytes(b"LOCAL_CONCEPT_PNG")

        self.asset_service.rebuild_index(self.project, force=True)

        # 2. Inject a global library reference that has legacy category 'References'
        legacy_lib_ref = {
            "id": "lib_ref_legacy_001",
            "filename": "legacy_texture.png",
            "relative_path": "References/legacy_texture.png",
            "category": "References",  # Old legacy record
            "is_library_reference": True,
            "library_asset_id": "lib_asset_legacy_001",
            "drive_id": "drv_001",
            "drive_relative_path": "textures/legacy_texture.png",
            "friendly_type": "Texture",
            "date_added": "2026-08-16T12:00:00",
            "size": 1024,
            "favorite": False,
            "tags": [],
            "notes": "",
        }
        assets = self.asset_service._ensure_index_loaded(self.project)
        assets.append(legacy_lib_ref)
        self.asset_service._save_index(self.project)

        # 3. Query References
        local_refs = self.asset_service.get_assets(self.project, category="References")
        local_filenames = [a.get("filename") for a in local_refs]
        self.assertIn("local_concept.png", local_filenames)
        self.assertNotIn("legacy_texture.png", local_filenames)
        self.assertFalse(any(a.get("is_library_reference") for a in local_refs))

        # 4. Query Library References
        lib_refs = self.asset_service.get_assets(self.project, category="Library References")
        lib_filenames = [a.get("filename") for a in lib_refs]
        self.assertIn("legacy_texture.png", lib_filenames)
        self.assertNotIn("local_concept.png", lib_filenames)
        self.assertTrue(all(a.get("is_library_reference") for a in lib_refs))

        # 5. Query other local categories (e.g. Assets, Renders)
        other_assets = self.asset_service.get_assets(self.project, category="Assets")
        self.assertNotIn("legacy_texture.png", [a.get("filename") for a in other_assets])


if __name__ == "__main__":
    unittest.main()
