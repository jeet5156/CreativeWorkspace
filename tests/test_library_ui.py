"""Focused unit tests for Global Asset Library UI Panel, Hierarchy, Safe Removal, Thumbnails, and Folder Selection."""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt, QUrl, QMimeData, QSize
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QApplication

from models.library_models import AssetAvailability, LibraryAsset, LibraryDrive, LibraryLocation
from models.project import Project
from services.drive_detection_service import DriveDetectionService
from services.library_service import LibraryService
from services.project_service import ProjectService
from services.asset_service import AssetService
from services.thumbnail_service import ThumbnailService
from core.inspectable_adapters import LibraryAssetInspectable, LibraryFolderInspectable
from ui.panels.library_workspace_panel import LibraryWorkspacePanel
from ui.panels.inspector_panel import InspectorPanel
from ui.widgets.asset_card import AssetCard
from ui.widgets.folder_card import FolderCard

app = QApplication.instance() or QApplication([])


class MockDropEvent:
    """Synthetic drop event helper for Qt widget testing."""
    def __init__(self, urls):
        self._urls = [QUrl.fromLocalFile(str(u)) for u in urls]
        self._mime = QMimeData()
        self._mime.setUrls(self._urls)
        self.accepted = False

    def mimeData(self):
        return self._mime

    def acceptProposedAction(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False


class MockAppContext:
    def __init__(self, library_service=None, asset_service=None, project_service=None, thumbnail_service=None):
        self.library_service = library_service
        self.asset_service = asset_service
        self.project_service = project_service
        self.thumbnail_service = thumbnail_service
        self.current_project = None


class TestLibraryUI(unittest.TestCase):
    """Test suite for Asset Library UI, Safe Removal, Folder Hierarchy, Selection, and Thumbnails."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_root = Path(self.test_dir)

        # Global catalog storage
        self.storage_dir = self.test_root / "global_storage"
        self.storage_dir.mkdir(parents=True)

        # Mock external source drives (e.g. "E:\\" and "F:\\")
        self.mock_drive_1 = self.test_root / "Drive_Samsung"
        self.mock_drive_1.mkdir(parents=True)

        self.mock_drive_2 = self.test_root / "Drive_SanDisk"
        self.mock_drive_2.mkdir(parents=True)

        # Project folder
        self.project_dir = self.test_root / "ProjectAlpha"
        self.project_dir.mkdir(parents=True)
        (self.project_dir / "Assets").mkdir()
        (self.project_dir / "References").mkdir()

        self.drive_detector = DriveDetectionService()
        self.drive_detector.set_test_mount_override("drv_1", str(self.mock_drive_1))
        self.drive_detector.set_test_mount_override("drv_2", str(self.mock_drive_2))

        self.library_service = LibraryService(
            storage_dir=self.storage_dir,
            drive_detector=self.drive_detector,
        )

        self.project_service = ProjectService()
        self.asset_service = AssetService(self.project_service)
        self.project = Project("ProjectAlpha", "game", str(self.project_dir))
        self.project_service.projects.append(self.project)

        self.thumbnail_service = ThumbnailService(self.asset_service)

        self.context = MockAppContext(
            library_service=self.library_service,
            asset_service=self.asset_service,
            project_service=self.project_service,
            thumbnail_service=self.thumbnail_service,
        )

        self.panel = LibraryWorkspacePanel(self.context)
        self.inspector = InspectorPanel()
        self.inspector.set_context(self.context)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Folder Selection & Inspector Tests
    # -------------------------------------------------------------------------

    def test_folder_click_selection_highlights_and_reaches_inspector(self):
        """Verify single click on FolderCard highlights it, emits folder_selected, and shows in Inspector."""
        fol = self.mock_drive_1 / "Environment"
        fol.mkdir(parents=True)
        (fol / "cliff_rock.fbx").write_bytes(b"data1")
        (fol / "tree_bark.png").write_bytes(b"data2")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Environment")

        self.panel.refresh_library()
        self.assertEqual(len(self.panel._folder_cards), 1)
        f_card = self.panel._folder_cards[0]

        selected_folders = []
        self.panel.folder_selected.connect(lambda fd: selected_folders.append(fd))

        # Simulate single-click on folder card
        f_card.mousePressEvent(type("MockMouseEvent", (), {"button": lambda self=None: Qt.LeftButton})())

        # Folder card is selected
        self.assertTrue(f_card._selected)
        self.assertEqual(len(selected_folders), 1)
        fdata = selected_folders[0]
        self.assertEqual(fdata["name"], "Environment")
        self.assertEqual(fdata["asset_count"], 2)

        # Inspector receives folder inspectable
        self.inspector.show_library_folder(fdata)
        self.assertIn("Environment", self.inspector.header_title.text())
        self.assertIn("Folder Properties", self.inspector.header_subtitle.text())

    def test_folder_favorite_persistence_and_independence(self):
        """Verify favoriting a folder persists in catalog without modifying child asset favorites."""
        props_dir = self.mock_drive_1 / "Props"
        props_dir.mkdir(parents=True)
        (props_dir / "chair.glb").write_bytes(b"chair")
        (props_dir / "table.glb").write_bytes(b"table")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(props_dir, display_name="Props")

        # Initial state: folder and children are not favorites
        self.assertFalse(loc.favorite)
        assets = self.library_service.query_assets(location_id=loc.location_id)
        for a in assets:
            self.assertFalse(a.favorite)

        # Favorite the folder via LibraryService / FolderInspectable
        folder_data = {
            "type": "location",
            "location_id": loc.location_id,
            "name": "Props",
            "favorite": False,
        }
        inspectable = LibraryFolderInspectable(folder_data, library_service=self.library_service)
        res = inspectable.set_inspectable_property("favorite", True)
        self.assertTrue(res)

        # Folder is favorited in catalog
        refreshed_loc = self.library_service.get_location(loc.location_id)
        self.assertTrue(refreshed_loc.favorite)

        # Children remain unaffected (NOT favorited)
        assets_after = self.library_service.query_assets(location_id=loc.location_id)
        for a in assets_after:
            self.assertFalse(a.favorite)

        # Unfavoriting folder also does not alter children
        inspectable.set_inspectable_property("favorite", False)
        self.assertFalse(self.library_service.get_location(loc.location_id).favorite)

    # -------------------------------------------------------------------------
    # 2. Folder Availability Tests
    # -------------------------------------------------------------------------

    def test_folder_availability_offline_and_reconnection(self):
        """Verify folder cards display Available vs Offline state when drive status changes."""
        tex_dir = self.mock_drive_1 / "Textures"
        tex_dir.mkdir(parents=True)
        (tex_dir / "metal.png").write_bytes(b"metal")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(tex_dir, display_name="Textures")

        # 1. Drive is online -> Available
        self.panel.refresh_library()
        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertNotIn("Offline", self.panel._folder_cards[0].meta.text())

        # 2. Drive unplugs -> Offline
        self.drive_detector.set_test_mount_override(drive.drive_id, None)
        self.panel.refresh_library()
        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertIn("Offline", self.panel._folder_cards[0].meta.text())

        # 3. Drive reconnects -> Available
        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
        self.panel.refresh_library()
        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertNotIn("Offline", self.panel._folder_cards[0].meta.text())

    # -------------------------------------------------------------------------
    # 3. Safe Remove Semantics Tests
    # -------------------------------------------------------------------------

    def test_remove_from_library_does_not_delete_source_file(self):
        """Verify 'Remove from Library' purges the catalog entry while leaving source file 100% intact."""
        ext_folder = self.mock_drive_1 / "Textures"
        ext_folder.mkdir(parents=True)
        source_tex = ext_folder / "cobblestone_albedo.png"
        source_tex.write_bytes(b"png_bytes_original")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(ext_folder, display_name="Textures")

        assets = self.library_service.query_assets()
        self.assertEqual(len(assets), 1)
        asset_id = assets[0].id

        # Safe removal from catalog
        res = self.library_service.remove_asset(asset_id, delete_file=False)
        self.assertTrue(res)

        # Asset is removed from catalog
        self.assertEqual(len(self.library_service.query_assets()), 0)
        self.assertIsNone(self.library_service.get_asset(asset_id))

        # Source file STILL EXISTS on disk!
        self.assertTrue(source_tex.exists())
        self.assertEqual(source_tex.read_bytes(), b"png_bytes_original")

    def test_delete_original_file_destructively_removes_from_disk_and_library(self):
        """Verify explicit destructive action deletes file from disk and purges library catalog."""
        ext_folder = self.mock_drive_1 / "TempModels"
        ext_folder.mkdir(parents=True)
        source_file = ext_folder / "trash_barrel.fbx"
        source_file.write_bytes(b"barrel_bytes")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(ext_folder, display_name="TempModels")

        assets = self.library_service.query_assets()
        asset_id = assets[0].id

        # Destructive deletion
        res = self.library_service.remove_asset(asset_id, delete_file=True)
        self.assertTrue(res)

        # Asset is removed from catalog AND deleted from disk
        self.assertEqual(len(self.library_service.query_assets()), 0)
        self.assertFalse(source_file.exists())

    def test_remove_location_does_not_delete_source_folder(self):
        """Verify removing a library location removes catalog index without touching source directory."""
        fol = self.mock_drive_1 / "Characters"
        fol.mkdir(parents=True)
        (fol / "hero.fbx").write_bytes(b"hero_data")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Characters")

        # Safe location removal
        res = self.library_service.remove_library_location(loc.location_id, delete_folder=False)
        self.assertTrue(res)

        # Location and assets removed from catalog
        self.assertEqual(len(self.library_service.get_locations()), 0)
        self.assertEqual(len(self.library_service.query_assets()), 0)

        # Directory and files on disk are intact!
        self.assertTrue(fol.exists())
        self.assertTrue((fol / "hero.fbx").exists())

    # -------------------------------------------------------------------------
    # 4. Folder Hierarchy & Navigation Tests
    # -------------------------------------------------------------------------

    def test_folder_registration_preserves_root_folder_and_no_loose_assets_at_root(self):
        """Verify dropping a folder renders ONLY a FolderCard in the root view, not dumped loose assets."""
        new_images = self.mock_drive_1 / "New Images"
        new_images.mkdir(parents=True)
        (new_images / "image01.png").write_bytes(b"img1")
        (new_images / "image02.png").write_bytes(b"img2")
        (new_images / "image03.png").write_bytes(b"img3")

        drop_ev = MockDropEvent([new_images])
        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            self.panel.dropEvent(drop_ev)

        # Root view should display ONLY the FolderCard for "New Images", 0 loose AssetCards
        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertEqual(len(self.panel._cards), 0)
        self.assertIn("New Images", self.panel._folder_cards[0].folder_name)

    def test_folder_navigation_filters_assets_correctly(self):
        """Verify double clicking a folder enters it and displays only assets directly in that folder."""
        gallery = self.mock_drive_1 / "Gallery"
        gallery.mkdir(parents=True)
        (gallery / "photo_a.jpg").write_bytes(b"a")
        (gallery / "photo_b.jpg").write_bytes(b"b")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(gallery, display_name="Gallery")

        self.panel.refresh_library()
        # At root: 1 folder card, 0 asset cards
        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertEqual(len(self.panel._cards), 0)

        # Enter location
        self.panel._navigate_into_location(loc.location_id)
        # Inside location: 1 Parent Directory folder card, 2 asset cards
        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertTrue(self.panel._folder_cards[0].is_parent_nav)
        self.assertEqual(len(self.panel._cards), 2)
        card_names = [c._full_filename for c in self.panel._cards.values()]
        self.assertIn("photo_a.jpg", card_names)
        self.assertIn("photo_b.jpg", card_names)

        # Navigate up returns to root view
        self.panel._navigate_up()
        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertEqual(len(self.panel._cards), 0)

    def test_nested_folder_hierarchy_is_preserved(self):
        """Verify deep nested folder structures (e.g. Kitbash/Doors/metal.glb) remain structured."""
        kitbash = self.mock_drive_1 / "Kitbash"
        doors = kitbash / "Doors"
        pipes = kitbash / "Pipes"
        doors.mkdir(parents=True)
        pipes.mkdir(parents=True)

        (doors / "blast_door.glb").write_bytes(b"door")
        (pipes / "exhaust_pipe.fbx").write_bytes(b"pipe")
        (kitbash / "readme.txt").write_bytes(b"txt")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(kitbash, display_name="Kitbash")

        # Enter Kitbash location root
        self.panel._navigate_into_location(loc.location_id)
        folder_names = [fc.folder_name for fc in self.panel._folder_cards]
        self.assertIn("Doors", folder_names)
        self.assertIn("Pipes", folder_names)
        self.assertEqual(len(self.panel._cards), 1)
        self.assertEqual(list(self.panel._cards.values())[0]._full_filename, "readme.txt")

        # Enter Doors subfolder
        self.panel._navigate_into_subpath("Doors")
        self.assertEqual(len(self.panel._cards), 1)
        self.assertEqual(list(self.panel._cards.values())[0]._full_filename, "blast_door.glb")

    def test_two_registered_folders_with_same_name_remain_distinct(self):
        """Verify two folders named 'Assets' on different drives/locations remain distinct."""
        fol1 = self.mock_drive_1 / "Assets"
        fol2 = self.mock_drive_2 / "Assets"
        fol1.mkdir(parents=True)
        fol2.mkdir(parents=True)

        (fol1 / "samsung_prop.glb").write_bytes(b"d1")
        (fol2 / "sandisk_prop.glb").write_bytes(b"d2")

        def mock_identify(root):
            if "Samsung" in str(root):
                return "drv_1", "SN_SAMSUNG", "Samsung T7"
            return "drv_2", "SN_SANDISK", "SanDisk Extreme"

        with patch.object(self.drive_detector, "get_drive_root", side_effect=lambda p: self.mock_drive_1 if "Samsung" in str(p) else self.mock_drive_2), \
             patch.object(self.drive_detector, "identify_drive", side_effect=mock_identify):
            loc1, drv1 = self.library_service.add_library_location(fol1, display_name="Assets", drive_name="Samsung T7")
            loc2, drv2 = self.library_service.add_library_location(fol2, display_name="Assets", drive_name="SanDisk Extreme")

        self.panel.refresh_library()
        self.assertEqual(len(self.panel._folder_cards), 2)
        f_titles = [fc.folder_name for fc in self.panel._folder_cards]
        self.assertTrue(any("Samsung T7" in t for t in f_titles))
        self.assertTrue(any("SanDisk Extreme" in t for t in f_titles))

    # -------------------------------------------------------------------------
    # 5. Image Thumbnails & ThumbnailService Integration Tests
    # -------------------------------------------------------------------------

    def test_image_assets_generate_and_cache_thumbnails(self):
        """Verify image assets generate and cache thumbnails via ThumbnailService."""
        img_dir = self.mock_drive_1 / "ConceptArt"
        img_dir.mkdir(parents=True)
        img_file = img_dir / "landscape.png"

        # Create a valid test PNG image
        img = QImage(120, 80, QImage.Format_RGB32)
        img.fill(Qt.blue)
        img.save(str(img_file), "PNG")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(img_dir, display_name="ConceptArt")

        asset = self.library_service.query_assets()[0]
        # Request async thumbnail generation
        res = self.thumbnail_service.generate_async(
            "__global_library__",
            asset.drive_relative_path,
            str(img_file),
            QSize(140, 160),
            asset.id,
        )
        self.assertTrue(res)

        # Wait for worker thread to complete
        self.thumbnail_service.pool.waitForDone(2000)

        # Thumbnail should now be in cache
        cached_path = self.thumbnail_service.get_cached("__global_library__", asset.drive_relative_path, str(img_file))
        self.assertIsNotNone(cached_path)
        self.assertTrue(Path(cached_path).exists())

    def test_offline_assets_remain_visible_and_retain_cached_thumbnail(self):
        """Verify offline assets on disconnected drives remain visible with Offline badge and cached thumb."""
        tex_dir = self.mock_drive_1 / "Materials"
        tex_dir.mkdir(parents=True)
        tex_file = tex_dir / "brick_diffuse.png"

        img = QImage(64, 64, QImage.Format_RGB32)
        img.fill(Qt.red)
        img.save(str(tex_file), "PNG")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(tex_dir, display_name="Materials")

        # Pre-cache thumbnail
        thumb_folder = self.thumbnail_service._thumb_folder("__global_library__")
        cached_thumb_file = thumb_folder / "test_thumb.jpg"
        img.save(str(cached_thumb_file), "JPEG")
        self.thumbnail_service._update_index("__global_library__", "Materials/brick_diffuse.png", str(cached_thumb_file), os.path.getmtime(tex_file))

        # Unplug drive (simulate offline)
        self.drive_detector.set_test_mount_override(drive.drive_id, None)

        # ThumbnailService should still return cached thumbnail even when file is offline
        cached_res = self.thumbnail_service.get_cached("__global_library__", "Materials/brick_diffuse.png", str(tex_file))
        self.assertEqual(cached_res, str(cached_thumb_file))

        # Refresh panel view
        self.panel._navigate_into_location(loc.location_id)
        self.assertEqual(len(self.panel._cards), 1)
        card = list(self.panel._cards.values())[0]
        self.assertIn("Offline", card.meta.text())

    # -------------------------------------------------------------------------
    # 6. Live Drive Availability & Lifecycle Tests
    # -------------------------------------------------------------------------

    def test_live_drive_disconnect_and_reconnect_refreshes_ui_and_inspector(self):
        """Verify check_drive_mounts automatically refreshes panel & inspector without leaving page."""
        fol = self.mock_drive_1 / "Props"
        fol.mkdir(parents=True)
        (fol / "crate.fbx").write_bytes(b"crate")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Props")

        # Set up panel & inspector wiring
        self.panel.set_context(self.context)
        self.panel.folder_selected.connect(self.inspector.show_library_folder)

        # Select folder card
        f_card = self.panel._folder_cards[0]
        f_card.mousePressEvent(type("MockMouseEvent", (), {"button": lambda self=None: Qt.LeftButton})())
        self.assertTrue(f_card._selected)
        self.assertNotIn("Offline", f_card.meta.text())

        # 1. Simulate Drive Unplugged while app running
        self.drive_detector.set_test_mount_override(drive.drive_id, None)

        # Trigger live check
        changed = self.library_service.check_drive_mounts()
        self.assertTrue(changed)

        # Verify folder card is now visibly Offline
        updated_card = self.panel._folder_cards[0]
        self.assertIn("Offline", updated_card.meta.text())
        self.assertTrue(updated_card._selected)  # Selection preserved!

        # 2. Simulate Drive Reconnected while app running
        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))

        # Trigger live check
        changed2 = self.library_service.check_drive_mounts()
        self.assertTrue(changed2)

        # Verify folder card returns to Available
        restored_card = self.panel._folder_cards[0]
        self.assertNotIn("Offline", restored_card.meta.text())
        self.assertTrue(restored_card._selected)  # Selection preserved!

    def test_drive_letter_change_resolves_and_updates_live(self):
        """Verify drive reconnecting with a new mount path resolves dynamically."""
        fol = self.mock_drive_1 / "Vehicles"
        fol.mkdir(parents=True)
        (fol / "rover.glb").write_bytes(b"rover")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Vehicles")

        asset = self.library_service.query_assets()[0]
        # Initial path
        path1 = self.library_service.resolve_asset_path(asset)
        self.assertEqual(path1, self.mock_drive_1 / "Vehicles" / "rover.glb")

        # Simulate drive re-mounting to drive 2 (simulating drive letter change e.g. E: -> F:)
        new_mount = self.mock_drive_2
        (new_mount / "Vehicles").mkdir(parents=True, exist_ok=True)
        (new_mount / "Vehicles" / "rover.glb").write_bytes(b"rover")

        self.drive_detector.set_test_mount_override(drive.drive_id, str(new_mount))
        changed = self.library_service.check_drive_mounts()
        self.assertTrue(changed)

        # Resolves cleanly to new mount path
        path2 = self.library_service.resolve_asset_path(asset)
        self.assertEqual(path2, new_mount / "Vehicles" / "rover.glb")

    def test_unchanged_drive_state_does_not_cause_unnecessary_reload(self):
        """Verify checking mounts when nothing has changed returns False and emits no signals."""
        fol = self.mock_drive_1 / "Audio"
        fol.mkdir(parents=True)
        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(fol, display_name="Audio")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
            self.library_service._last_checked_mounts[drive.drive_id] = str(self.mock_drive_1)

        emitted = []
        self.library_service.drive_mounts_changed.connect(lambda: emitted.append(True))

        # Check with no changes
        changed = self.library_service.check_drive_mounts()
        self.assertFalse(changed)
        self.assertEqual(len(emitted), 0)

    def test_inside_folder_live_availability_updates_without_navigating_away(self):
        """Verify that when inside an open Library folder, unplug/reconnect updates visible cards in-place."""
        foo_dir = self.mock_drive_1 / "Foo"
        foo_dir.mkdir(parents=True)
        sub_dir = foo_dir / "SubProps"
        sub_dir.mkdir(parents=True)
        (foo_dir / "asset_root.fbx").write_bytes(b"root_asset")
        (sub_dir / "asset_sub.fbx").write_bytes(b"sub_asset")

        with patch.object(self.drive_detector, "get_drive_root", return_value=self.mock_drive_1):
            loc, drive = self.library_service.add_library_location(foo_dir, display_name="Foo")
            self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
            self.library_service._last_checked_mounts[drive.drive_id] = str(self.mock_drive_1)

        self.panel.set_context(self.context)

        # 1. Open / Enter Library/Foo
        self.panel._navigate_into_location(loc.location_id)
        self.assertEqual(self.panel._current_location_id, loc.location_id)

        # Confirm 1 SubProps FolderCard (+ 1 Parent Directory card) and 1 AssetCard
        asset_cards_initial = list(self.panel._cards.values())
        self.assertEqual(len(asset_cards_initial), 1)
        self.assertNotIn("Offline", asset_cards_initial[0].meta.text())

        # 2. Unplug drive while inside Foo
        self.drive_detector.set_test_mount_override(drive.drive_id, None)
        changed = self.library_service.check_drive_mounts()
        self.assertTrue(changed)

        # Verify state inside Foo updated WITHOUT navigating away
        self.assertEqual(self.panel._current_location_id, loc.location_id)
        asset_cards_offline = list(self.panel._cards.values())
        self.assertEqual(len(asset_cards_offline), 1)
        self.assertIn("Offline", asset_cards_offline[0].meta.text())

        # 3. Plug drive back in while inside Foo
        self.drive_detector.set_test_mount_override(drive.drive_id, str(self.mock_drive_1))
        changed2 = self.library_service.check_drive_mounts()
        self.assertTrue(changed2)

        # Verify state inside Foo returned to Available WITHOUT navigating away
        self.assertEqual(self.panel._current_location_id, loc.location_id)
        asset_cards_reconnected = list(self.panel._cards.values())
        self.assertEqual(len(asset_cards_reconnected), 1)
        self.assertNotIn("Offline", asset_cards_reconnected[0].meta.text())


if __name__ == "__main__":
    unittest.main()
