import os
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox
from PySide6.QtCore import Qt, QSize

from models.project import Project
from services.project_service import ProjectService
from services.asset_service import AssetService
from services.folder_service import FolderService
from services.thumbnail_service import ThumbnailService
from ui.panels.asset_workspace_panel import AssetWorkspacePanel
from ui.widgets.asset_card import AssetCard

app = QApplication.instance() or QApplication([])


class MockAppContext:
    def __init__(self, project_service, asset_service, folder_service, thumbnail_service):
        self.project_service = project_service
        self.asset_service = asset_service
        self.folder_service = folder_service
        self.thumbnail_service = thumbnail_service


class TestRendersExportsGrid(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.test_dir) / "SciFiWeapon"
        self.project_dir.mkdir(parents=True, exist_ok=True)

        for sub in ["Assets", "References", "Renders", "Exports", "Notes", "Lab"]:
            (self.project_dir / sub).mkdir(parents=True, exist_ok=True)

        self.project = Project(
            name="SciFiWeapon",
            project_type="game",
            location=str(self.project_dir),
            description="Sci-Fi Weapon Model and Renders",
        )

        self.project_service = ProjectService()
        self.asset_service = AssetService(self.project_service)
        self.folder_service = FolderService(self.project_service, self.asset_service)
        self.thumbnail_service = ThumbnailService(self.asset_service)
        self.context = MockAppContext(
            self.project_service,
            self.asset_service,
            self.folder_service,
            self.thumbnail_service,
        )

        self.panel = AssetWorkspacePanel()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_friendly_type_and_icon_map_for_renders_and_exports(self):
        """Verify DCC 3D and render formats produce friendly types and icons."""
        # 3D models
        self.assertEqual(self.asset_service._friendly_type_for(Path("rifle.fbx")), "FBX 3D Model")
        self.assertEqual(self.asset_service._friendly_type_for(Path("rifle.glb")), "GLB 3D Model")
        self.assertEqual(self.asset_service._friendly_type_for(Path("scene.usd")), "USD 3D Model")
        self.assertEqual(self.asset_service._friendly_type_for(Path("mesh.blend")), "BLEND 3D Model")

        # Renders / Images
        self.assertEqual(self.asset_service._friendly_type_for(Path("shot_01.exr")), "EXR Image")
        self.assertEqual(self.asset_service._friendly_type_for(Path("env.hdr")), "HDR Image")
        self.assertEqual(self.asset_service._friendly_type_for(Path("preview.png")), "PNG Image")

        # Icon map
        self.assertEqual(AssetCard.ICON_MAP.get('.fbx'), '🧩')
        self.assertEqual(AssetCard.ICON_MAP.get('.glb'), '🧩')
        self.assertEqual(AssetCard.ICON_MAP.get('.usd'), '🧩')
        self.assertEqual(AssetCard.ICON_MAP.get('.exr'), '🎬')
        self.assertEqual(AssetCard.ICON_MAP.get('.hdr'), '🎬')

    def test_renders_empty_state_and_title_icon(self):
        """Verify Renders section shows 🎬 icon and custom empty state."""
        self.panel.show_project_section(self.project, "renders", context=self.context)

        # Title bar check
        self.assertIn("🎬", self.panel.title.text())
        self.assertIn("Renders", self.panel.title.text())

        # Empty state label check
        lbl = self.panel.grid.itemAt(0).widget()
        self.assertIsInstance(lbl, QLabel)
        self.assertIn("No renders yet", lbl.text())
        self.assertIn("viewport snapshots", lbl.text())

    def test_exports_empty_state_and_title_icon(self):
        """Verify Exports section shows 📤 icon and custom empty state."""
        self.panel.show_project_section(self.project, "exports", context=self.context)

        # Title bar check
        self.assertIn("📤", self.panel.title.text())
        self.assertIn("Exports", self.panel.title.text())

        # Empty state label check
        lbl = self.panel.grid.itemAt(0).widget()
        self.assertIsInstance(lbl, QLabel)
        self.assertIn("No exports yet", lbl.text())
        self.assertIn("Export game-ready 3D models", lbl.text())

    def test_renders_card_grid_and_selection(self):
        """Verify populated Renders section builds AssetCards and handles selection."""
        # Create render files
        (self.project_dir / "Renders" / "turntable_v01.png").write_bytes(b"dummy")
        (self.project_dir / "Renders" / "beauty_pass_final.exr").write_bytes(b"dummy")

        self.asset_service.rebuild_index(self.project, force=True)
        self.panel.show_project_section(self.project, "renders", context=self.context)

        self.assertEqual(len(self.panel._cards), 2)
        self.assertIn("🎬", self.panel.title.text())
        self.assertIn("(2)", self.panel.title.text())

        # Selection test
        selected_emits = []
        self.panel.asset_selected.connect(lambda aid: selected_emits.append(aid))

        first_aid = self.panel._card_order[0]
        self.panel.request_select_asset(first_aid)

        card = self.panel._cards[first_aid]
        self.assertTrue(card._selected)
        self.assertEqual(len(selected_emits), 1)
        self.assertEqual(selected_emits[0], first_aid)

    def test_exports_card_grid_with_subfolders(self):
        """Verify Exports section displays FolderCards and 3D AssetCards."""
        # Create export subfolder and files
        (self.project_dir / "Exports" / "UnrealEngine").mkdir(parents=True, exist_ok=True)
        (self.project_dir / "Exports" / "weapon_lod0.glb").write_bytes(b"dummy")
        (self.project_dir / "Exports" / "weapon_lod1.fbx").write_bytes(b"dummy")

        self.asset_service.rebuild_index(self.project, force=True)
        self.panel.show_project_section(self.project, "exports", context=self.context)

        self.assertEqual(len(self.panel._folder_cards), 1)
        self.assertEqual(len(self.panel._cards), 2)
        self.assertIn("📤", self.panel.title.text())
        self.assertIn("(3)", self.panel.title.text())

    def test_live_import_into_renders_refreshes_grid_immediately(self):
        """Verify importing into visible Renders section refreshes grid immediately without navigating away."""
        from ui.panels.workspace_panel import WorkspacePanel

        ws = WorkspacePanel()
        ws.set_context(self.context)
        self.asset_service.assets_changed.connect(ws._on_assets_changed)

        # Initial render file
        (self.project_dir / "Renders" / "initial_render.png").write_bytes(b"dummy")
        self.asset_service.rebuild_index(self.project, force=True)

        ws.show_section(self.project, "renders")
        self.assertEqual(len(ws.asset_workspace._cards), 1)

        # Create external file to import
        src_file = Path(self.test_dir) / "new_render_pass.png"
        src_file.write_bytes(b"dummy_pass")

        # Import into visible renders section
        self.asset_service.import_paths(self.project, "renders", [str(src_file)])

        # Verify grid immediately has 2 cards
        self.assertEqual(len(ws.asset_workspace._cards), 2)
        self.assertIn("(2)", ws.asset_workspace.title.text())

    def test_live_import_into_exports_preserves_selection(self):
        """Verify live import refreshes Exports grid while smoothly preserving active card selection."""
        from ui.panels.workspace_panel import WorkspacePanel

        ws = WorkspacePanel()
        ws.set_context(self.context)
        self.asset_service.assets_changed.connect(ws._on_assets_changed)

        (self.project_dir / "Exports" / "model_a.glb").write_bytes(b"dummy")
        (self.project_dir / "Exports" / "model_b.glb").write_bytes(b"dummy")
        self.asset_service.rebuild_index(self.project, force=True)

        ws.show_section(self.project, "exports")
        self.assertEqual(len(ws.asset_workspace._cards), 2)

        # Select first model
        first_aid = ws.asset_workspace._card_order[0]
        ws.asset_workspace.request_select_asset(first_aid)
        self.assertTrue(ws.asset_workspace._cards[first_aid]._selected)

        # Import 3rd export model
        src_file = Path(self.test_dir) / "model_c.fbx"
        src_file.write_bytes(b"dummy")
        self.asset_service.import_paths(self.project, "exports", [str(src_file)])

        # Verify grid updated to 3 cards and first_aid remains selected
        self.assertEqual(len(ws.asset_workspace._cards), 3)
        self.assertIn(first_aid, ws.asset_workspace._cards)
        self.assertTrue(ws.asset_workspace._cards[first_aid]._selected)

    def test_renders_and_exports_inspector_fields_and_persistence(self):
        """Verify AssetInspectable displays dedicated Render/Export sections and persists edits."""
        from core.inspectable_adapters import AssetInspectable

        # 1. Render Inspectable
        render_dict = {
            "id": "rend_01",
            "filename": "turntable.png",
            "friendly_type": "PNG Image",
            "category": "Renders",
            "relative_path": "Renders/turntable.png",
            "tags": ["turntable", "wip"],
            "notes": "Draft render",
        }
        r_inspectable = AssetInspectable(render_dict, asset_service=self.asset_service, project=self.project)
        self.assertEqual(r_inspectable.get_display_icon(), "🎬")
        sections = r_inspectable.get_inspection_sections()
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].title, "Render Properties")

        # 2. Export Inspectable
        export_dict = {
            "id": "exp_01",
            "filename": "character_lod0.glb",
            "friendly_type": "GLB 3D Model",
            "category": "Exports",
            "relative_path": "Exports/character_lod0.glb",
            "tags": ["game-ready"],
            "notes": "Optimized GLTF mesh",
        }
        e_inspectable = AssetInspectable(export_dict, asset_service=self.asset_service, project=self.project)
        self.assertEqual(e_inspectable.get_display_icon(), "📤")
        e_sections = e_inspectable.get_inspection_sections()
        self.assertEqual(len(e_sections), 1)
        self.assertEqual(e_sections[0].title, "Export Properties")

        # 3. Test persistence via set_inspectable_property
        self.asset_service._indices[self.project.location] = [export_dict]
        self.asset_service._save_index(self.project)

        e_inspectable.set_inspectable_property("tags", "unreal5, lod0, final")
        e_inspectable.set_inspectable_property("notes", "Approved for release")

        loaded = self.asset_service.get_asset(self.project, "exp_01")
        self.assertEqual(loaded["tags"], ["unreal5", "lod0", "final"])
        self.assertEqual(loaded["notes"], "Approved for release")

    def test_single_file_import_preserves_single_file(self):
        """Verify importing a single file places it directly into the target section root."""
        src_file = Path(self.test_dir) / "hero_render.png"
        src_file.write_bytes(b"image_content")

        res = self.asset_service.import_paths(self.project, "renders", [str(src_file)], target_rel_path="Renders")
        self.assertEqual(len(res["imported"]), 1)
        self.assertTrue((self.project_dir / "Renders" / "hero_render.png").exists())

    def test_folder_import_preserves_folder_and_nested_files(self):
        """Verify importing a folder into Renders preserves the imported folder and its files."""
        # Create external folder with files
        src_folder = Path(self.test_dir) / "RenderPasses"
        src_folder.mkdir(parents=True, exist_ok=True)
        (src_folder / "diffuse.exr").write_bytes(b"diffuse_bytes")
        (src_folder / "specular.exr").write_bytes(b"specular_bytes")

        res = self.asset_service.import_paths(self.project, "renders", [str(src_folder)], target_rel_path="Renders")
        self.assertEqual(len(res["imported"]), 2)

        # Verify folder structure on disk
        self.assertTrue((self.project_dir / "Renders" / "RenderPasses").is_dir())
        self.assertTrue((self.project_dir / "Renders" / "RenderPasses" / "diffuse.exr").exists())
        self.assertTrue((self.project_dir / "Renders" / "RenderPasses" / "specular.exr").exists())

        # Verify folder service discovers it as a subfolder
        subfolders = self.folder_service.list_subfolders(self.project, "Renders")
        self.assertIn("RenderPasses", subfolders)

    def test_nested_folder_import_preserves_hierarchy(self):
        """Verify nested subfolders within an imported folder remain structured."""
        src_folder = Path(self.test_dir) / "ExportBundle"
        (src_folder / "Meshes" / "LODs").mkdir(parents=True, exist_ok=True)
        (src_folder / "Textures").mkdir(parents=True, exist_ok=True)
        (src_folder / "Meshes" / "LODs" / "hero_lod0.glb").write_bytes(b"glb_data")
        (src_folder / "Textures" / "hero_albedo.png").write_bytes(b"albedo_data")

        res = self.asset_service.import_paths(self.project, "exports", [str(src_folder)], target_rel_path="Exports")
        self.assertEqual(len(res["imported"]), 2)

        # Verify full hierarchy
        self.assertTrue((self.project_dir / "Exports" / "ExportBundle" / "Meshes" / "LODs" / "hero_lod0.glb").exists())
        self.assertTrue((self.project_dir / "Exports" / "ExportBundle" / "Textures" / "hero_albedo.png").exists())

        subfolders = self.folder_service.list_subfolders(self.project, "Exports")
        self.assertIn("ExportBundle", subfolders)

    def test_live_refresh_after_folder_import(self):
        """Verify importing a folder immediately refreshes the grid to display a FolderCard."""
        from ui.panels.workspace_panel import WorkspacePanel

        ws = WorkspacePanel()
        ws.set_context(self.context)
        self.asset_service.assets_changed.connect(ws._on_assets_changed)

        ws.show_section(self.project, "renders")
        self.assertEqual(len(ws.asset_workspace._folder_cards), 0)

        # Import a folder
        src_folder = Path(self.test_dir) / "TurntableFrames"
        src_folder.mkdir(parents=True, exist_ok=True)
        (src_folder / "frame_01.png").write_bytes(b"dummy")

        self.asset_service.import_paths(self.project, "renders", [str(src_folder)], target_rel_path="Renders")

        # Grid should immediately contain the FolderCard
        self.assertEqual(len(ws.asset_workspace._folder_cards), 1)
        self.assertEqual(ws.asset_workspace._folder_cards[0].folder_name, "TurntableFrames")

    def test_sequence_detection_and_grouping(self):
        """Verify sequential frames (e.g. shot_01.0001.exr ... shot_01.0010.exr) are grouped into 1 sequence card."""
        from core.asset_intelligence import detect_version, detect_lod, parse_sequence_component, group_assets_and_sequences

        # Test sequence component parser
        parsed = parse_sequence_component("shot_01.0042.exr")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["prefix"], "shot_01")
        self.assertEqual(parsed["sep"], ".")
        self.assertEqual(parsed["frame_str"], "0042")
        self.assertEqual(parsed["frame_num"], 42)
        self.assertEqual(parsed["padding"], 4)
        self.assertEqual(parsed["ext"], "exr")

        # Test grouping multiple frames
        assets = [
            {"id": f"f_{i}", "filename": f"shot_01.{i:04d}.exr", "relative_path": f"Renders/shot_01.{i:04d}.exr", "category": "Renders"}
            for i in range(1, 11)
        ]
        # Add a standalone non-sequence asset
        assets.append({"id": "standalone", "filename": "preview.jpg", "relative_path": "Renders/preview.jpg", "category": "Renders"})

        grouped = group_assets_and_sequences(assets)
        self.assertEqual(len(grouped), 2)  # 1 sequence + 1 standalone

        seq = next(a for a in grouped if a.get("is_sequence"))
        self.assertEqual(seq["filename"], "shot_01.####.exr")
        self.assertEqual(seq["frame_count"], 10)
        self.assertEqual(seq["frame_range"], "0001 – 0010 (10 frames)")
        self.assertEqual(seq["friendly_type"], "EXR Sequence")

    def test_version_and_lod_detection(self):
        """Verify version and LOD tokens are accurately parsed without altering filenames."""
        from core.asset_intelligence import detect_version, detect_lod

        # Version detection
        self.assertEqual(detect_version("turntable_v002.png"), "v002")
        self.assertEqual(detect_version("character.v01.glb"), "v01")
        self.assertEqual(detect_version("shot_01_v3.exr"), "v3")
        self.assertIsNone(detect_version("generic_mesh.fbx"))

        # LOD detection
        self.assertEqual(detect_lod("weapon_lod0.glb"), "LOD0")
        self.assertEqual(detect_lod("hero_character_LOD2.fbx"), "LOD2")
        self.assertEqual(detect_lod("tree.lod1.obj"), "LOD1")
        self.assertIsNone(detect_lod("sword_final.glb"))

    def test_sequence_inspector_and_editing_persistence(self):
        """Verify Sequence AssetInspectable presents sequence fields and syncs tags/notes to member frames."""
        from core.inspectable_adapters import AssetInspectable

        frame_assets = [
            {"id": "frame_1", "filename": "shot_01.0001.exr", "tags": [], "notes": ""},
            {"id": "frame_2", "filename": "shot_01.0002.exr", "tags": [], "notes": ""},
        ]
        self.asset_service._indices[self.project.location] = list(frame_assets)
        self.asset_service._save_index(self.project)

        seq_dict = {
            "id": "seq_frame_1",
            "filename": "shot_01.####.exr",
            "friendly_type": "EXR Sequence",
            "category": "Renders",
            "relative_path": "Renders/shot_01.####.exr",
            "frame_range": "0001 – 0002 (2 frames)",
            "frame_assets": frame_assets,
            "tags": [],
            "notes": "",
        }

        seq_inspectable = AssetInspectable(seq_dict, asset_service=self.asset_service, project=self.project)
        sections = seq_inspectable.get_inspection_sections()
        field_keys = [f.key for f in sections[0].fields]
        self.assertIn("frame_range", field_keys)

        # Mutate tags & notes
        seq_inspectable.set_inspectable_property("tags", "final_render, 4k")
        seq_inspectable.set_inspectable_property("notes", "Clean pass approved")

        # Verify persisted into both frame assets in index
        for fid in ["frame_1", "frame_2"]:
            a = self.asset_service.get_asset(self.project, fid)
            self.assertEqual(a["tags"], ["final_render", "4k"])
            self.assertEqual(a["notes"], "Clean pass approved")

    def test_sequence_card_delete_removes_all_constituent_frames(self):
        """Verify deleting a sequence card removes all underlying frame files and index entries."""
        from PySide6.QtWidgets import QMessageBox
        from unittest.mock import patch

        # Create 5 sequence frames
        renders_dir = self.project_dir / "Renders"
        for i in range(1, 6):
            (renders_dir / f"shot_02.{i:04d}.exr").write_bytes(b"dummy")

        self.asset_service.rebuild_index(self.project, force=True)
        self.panel.show_project_section(self.project, "renders", context=self.context)

        # Confirm sequence is displayed as 1 card
        self.assertEqual(len(self.panel._cards), 1)
        seq_aid = self.panel._card_order[0]
        self.assertTrue(self.panel._cards[seq_aid].asset.get("is_sequence"))
        self.thumbnail_service.pool.waitForDone(1000)

        # Trigger delete with confirmation mocked to Yes
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
             patch.object(QMessageBox, "warning"):
            self.panel._delete_asset(seq_aid)

        # Verify all 5 frame files are deleted from disk
        for i in range(1, 6):
            self.assertFalse((renders_dir / f"shot_02.{i:04d}.exr").exists())

        # Verify index has 0 assets left
        remaining = self.asset_service.get_assets(self.project, "Renders")
        self.assertEqual(len(remaining), 0)

    def test_sequence_card_reveal_resolves_to_real_filesystem_folder(self):
        """Verify Reveal in Explorer on a sequence card targets the real folder containing the frames."""
        from unittest.mock import patch

        renders_dir = self.project_dir / "Renders"
        for i in range(1, 4):
            (renders_dir / f"shot_03.{i:04d}.png").write_bytes(b"dummy")

        self.asset_service.rebuild_index(self.project, force=True)
        self.panel.show_project_section(self.project, "renders", context=self.context)

        seq_aid = self.panel._card_order[0]

        opened_paths = []
        with patch("os.startfile", side_effect=lambda p: opened_paths.append(str(p))):
            res = self.panel._reveal_asset(seq_aid)
            self.assertTrue(res)

        self.assertEqual(len(opened_paths), 1)
        self.assertEqual(Path(opened_paths[0]).resolve(), renders_dir.resolve())

    def test_normal_asset_delete_and_reveal_still_works(self):
        """Verify normal single file delete and reveal operations continue working as expected."""
        from PySide6.QtWidgets import QMessageBox
        from unittest.mock import patch

        exports_dir = self.project_dir / "Exports"
        single_model = exports_dir / "hero_mesh.glb"
        single_model.write_bytes(b"glb_data")

        self.asset_service.rebuild_index(self.project, force=True)
        self.panel.show_project_section(self.project, "exports", context=self.context)

        aid = self.panel._card_order[0]

        # Test reveal
        opened_paths = []
        with patch("os.startfile", side_effect=lambda p: opened_paths.append(str(p))):
            res = self.panel._reveal_asset(aid)
            self.assertTrue(res)
        self.assertEqual(Path(opened_paths[0]).resolve(), exports_dir.resolve())

        # Test delete
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.panel._delete_asset(aid)

        self.assertFalse(single_model.exists())
        self.assertEqual(len(self.asset_service.get_assets(self.project, "Exports")), 0)


if __name__ == "__main__":
    unittest.main()
