import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize

from models.project import Project
from services.project_service import ProjectService
from services.asset_service import AssetService
from services.thumbnail_service import ThumbnailService
from services.folder_service import FolderService
from ui.widgets.asset_card import AssetCard
from ui.widgets.folder_card import FolderCard
from ui.panels.asset_workspace_panel import AssetWorkspacePanel

app = QApplication.instance() or QApplication([])


class TestAssetWorkspaceGrid(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_service = ProjectService()
        self.asset_service = AssetService(self.project_service)
        self.thumbnail_service = ThumbnailService()
        self.folder_service = FolderService(self.project_service, self.asset_service)

        self.project = self.project_service.create_project(
            "Test Grid Project", "game", self.temp_dir + "/proj", "T"
        )

        self.context = type('Context', (), {
            'project_service': self.project_service,
            'asset_service': self.asset_service,
            'thumbnail_service': self.thumbnail_service,
            'folder_service': self.folder_service,
            'asset_operations': None,
            'activity_service': type('ActSvc', (), {'record': lambda *args, **kwargs: None})(),
        })()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_asset_card_truncates_long_filenames_and_preserves_card_geometry(self):
        """Verify long filenames are elided with ellipsis without expanding fixed card geometry."""
        long_filename = "unbroken_extremely_long_asset_diffuse_roughness_specular_sequence_0001_final_master_v99.png"
        asset = {
            "id": "ast-001",
            "filename": long_filename,
            "friendly_type": "PNG Image",
            "category": "Assets",
            "relative_path": f"Assets/{long_filename}",
            "date_added": "2026-08-14T10:00:00",
        }

        card = AssetCard(asset, size=QSize(150, 185))
        self.assertEqual(card.width(), 150)
        self.assertEqual(card.height(), 185)

        # Name text must be elided (shorter than raw string) and contain ellipsis
        self.assertIn("…", card.name.text())
        self.assertLess(len(card.name.text()), len(long_filename))

        # Full tooltip and internal filename preserved
        self.assertIn(long_filename, card.name.toolTip())
        self.assertEqual(card._full_filename, long_filename)

    def test_folder_card_truncates_long_names_and_distinct_visual_styles(self):
        """Verify folder cards truncate long names and are visually distinguishable from asset cards."""
        long_foldername = "textures_and_materials_high_resolution_environment_assets_collection"
        fcard = FolderCard(
            folder_name=long_foldername,
            rel_path=f"Assets/{long_foldername}",
            size=QSize(150, 185),
            is_parent_nav=False,
            item_count=12,
        )

        self.assertEqual(fcard.width(), 150)
        self.assertEqual(fcard.height(), 185)
        self.assertIn("…", fcard.name.text())
        self.assertIn("📁", fcard.thumb.text())
        self.assertIn("12 items", fcard.meta.text())

        # Parent navigation card distinction
        parent_card = FolderCard(
            folder_name="..",
            rel_path="Assets",
            size=QSize(150, 185),
            is_parent_nav=True,
        )
        self.assertEqual(parent_card.thumb.text(), "⬆️")
        self.assertIn("Parent Folder", parent_card.meta.text())

    def test_asset_workspace_panel_grid_reflow(self):
        """Verify AssetWorkspacePanel sets top-left alignment and reflows cards into columns."""
        panel = AssetWorkspacePanel()
        panel.resize(800, 600)

        # Create assets in project
        assets_dir = Path(self.project.location) / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        for i in range(6):
            fpath = assets_dir / f"model_{i:02d}.fbx"
            fpath.write_text("fbx data")

        # Create a subfolder
        sub = assets_dir / "Subfolder"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "subfile.txt").write_text("text")

        self.asset_service.rebuild_index(self.project, force=True)

        panel.show_project_section(self.project, "assets", context=self.context)

        # Check alignment
        self.assertTrue(bool(panel.grid.alignment() & Qt.AlignTop))
        self.assertTrue(bool(panel.grid.alignment() & Qt.AlignLeft))

        # Check total widgets in panel (1 subfolder + 6 assets = 7 widgets)
        self.assertEqual(len(panel._ordered_widgets), 7)
        self.assertEqual(len(panel._cards), 6)

        # Test relayout with different widths
        panel.scroll.resize(400, 600)
        panel._relayout_grid()
        # With 400px width and 150px cards + spacing, should have ~2 columns
        self.assertGreaterEqual(panel.grid.columnCount(), 1)

        panel.scroll.resize(900, 600)
        panel._relayout_grid()
        # With 900px width, should have more columns
        self.assertGreater(panel.grid.columnCount(), 2)

    def test_references_view_empty_and_populated(self):
        """Verify References section displays distinct icon prefix, empty state, and populated items."""
        panel = AssetWorkspacePanel()
        panel.show_project_section(self.project, "references", context=self.context)

        self.assertIn("🖼️", panel.title.text())
        self.assertIn("References", panel.title.text())

        # Add a reference image
        ref_dir = Path(self.project.location) / "References"
        ref_dir.mkdir(parents=True, exist_ok=True)
        ref_file = ref_dir / "moodboard.png"
        # Valid 1x1 transparent PNG
        ref_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82")

        self.asset_service.rebuild_index(self.project, force=True)
        panel.show_project_section(self.project, "references", context=self.context)

        self.assertEqual(len(panel._cards), 1)
        self.assertIn("1", panel.title.text())

    def test_selection_handling_and_emission(self):
        """Verify selection updates card visuals and emits asset_selected."""
        panel = AssetWorkspacePanel()
        assets_dir = Path(self.project.location) / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        (assets_dir / "a.png").write_text("a")
        (assets_dir / "b.png").write_text("b")

        self.asset_service.rebuild_index(self.project, force=True)
        panel.show_project_section(self.project, "assets", context=self.context)

        aids = list(panel._cards.keys())
        self.assertEqual(len(aids), 2)

        emitted = []
        panel.asset_selected.connect(lambda aid: emitted.append(aid))

        # Select first asset
        panel._on_card_clicked(aids[0])
        self.assertEqual(panel.get_selected_ids(), [aids[0]])
        self.assertTrue(panel._cards[aids[0]]._selected)
        self.assertFalse(panel._cards[aids[1]]._selected)

    def test_card_selection_visual_highlighting(self):
        """Verify AssetCard and FolderCard use WA_StyledBackground and distinct selection styling."""
        card = AssetCard({"filename": "test.png", "category": "Assets"}, size=QSize(150, 185))
        self.assertTrue(card.testAttribute(Qt.WA_StyledBackground))
        self.assertFalse(card._selected)

        card.set_selected(True)
        self.assertTrue(card._selected)
        self.assertIn("#6366F1", card.styleSheet())
        self.assertIn("#1A1E36", card.thumb.styleSheet())

        card.set_selected(False)
        self.assertFalse(card._selected)
        self.assertIn("#1E2130", card.styleSheet())

        fcard = FolderCard("Subfolder", "Assets/Subfolder", size=QSize(150, 185))
        self.assertTrue(fcard.testAttribute(Qt.WA_StyledBackground))
        self.assertFalse(fcard._selected)

        fcard.set_selected(True)
        self.assertTrue(fcard._selected)
        self.assertIn("#F59E0B", fcard.styleSheet())
        self.assertIn("#382C18", fcard.thumb.styleSheet())

        fcard.set_selected(False)
        self.assertFalse(fcard._selected)
        self.assertIn("#1F2232", fcard.styleSheet())

    def test_inspector_width_stability_with_long_filenames(self):
        """Verify Inspector panel width remains stable when inspecting assets with very long filenames."""
        from ui.panels.inspector_panel import InspectorPanel
        from core.inspectable_adapters import AssetInspectable

        inspector = InspectorPanel()
        inspector.resize(280, 600)

        # Baseline width metrics
        baseline_hint_w = inspector.sizeHint().width()

        long_name = "unbroken_extremely_long_filename_" * 10 + ".png"
        long_path = "Assets/" + "nested_deeply_directory_" * 5 + "/" + long_name
        asset_dict = {
            "id": "long-01",
            "filename": long_name,
            "friendly_type": "PNG Image",
            "category": "Assets",
            "relative_path": long_path,
            "tags": ["tag1", "tag2", "tag3_extremely_long_unbroken_tag_name"],
            "notes": "Some notes for the asset",
        }

        inspectable = AssetInspectable(asset_dict)
        inspector.inspect(inspectable)

        # Full text must be in tooltip
        self.assertIn(long_name, inspector.header_title.toolTip())

        # Size hint width must not blow up to extreme widths (e.g. >1000px)
        self.assertLess(inspector.sizeHint().width(), 500)

    def test_asset_tags_and_notes_persistence_via_inspector(self):
        """Verify modifying tags and notes in AssetInspectable persists changes through AssetService to disk."""
        from core.inspectable_adapters import AssetInspectable

        # Create an asset in the project
        assets_dir = Path(self.project.location) / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        sample_file = assets_dir / "character.png"
        sample_file.write_text("dummy")

        self.asset_service.rebuild_index(self.project, force=True)
        assets = self.asset_service.get_assets(self.project)
        self.assertGreater(len(assets), 0)
        target_asset = assets[0]
        asset_id = target_asset["id"]

        inspectable = AssetInspectable(target_asset, asset_service=self.asset_service, project=self.project)

        # Update tags and notes
        inspectable.set_inspectable_property("tags", "concept, hero, 3d")
        inspectable.set_inspectable_property("notes", "Main character model for hero sequence")

        # Verify in-memory inspection state
        self.assertEqual(target_asset["tags"], ["concept", "hero", "3d"])
        self.assertEqual(target_asset["notes"], "Main character model for hero sequence")

        # Verify through asset service
        updated_from_svc = self.asset_service.get_asset(self.project, asset_id)
        self.assertEqual(updated_from_svc["tags"], ["concept", "hero", "3d"])
        self.assertEqual(updated_from_svc["notes"], "Main character model for hero sequence")

        # Verify on-disk persistence by fresh index load
        new_svc = AssetService(self.project_service)
        fresh_assets = new_svc.get_assets(self.project)
        fresh_entry = next((a for a in fresh_assets if a["id"] == asset_id), None)
        self.assertIsNotNone(fresh_entry)
        self.assertEqual(fresh_entry["tags"], ["concept", "hero", "3d"])
        self.assertEqual(fresh_entry["notes"], "Main character model for hero sequence")

    def test_tooltip_styling_and_readability(self):
        """Verify tooltips have readable styles matching the dark theme."""
        from ui.theme import DARK_THEME

        # Verify DARK_THEME contains QToolTip rule
        self.assertIn("QToolTip", DARK_THEME)

        card = AssetCard({"filename": "a_very_long_file_name_for_tooltip_testing.png", "category": "Assets"}, size=QSize(150, 185))
        self.assertIn("QToolTip", card.styleSheet())
        self.assertIn("#F1F5F9", card.styleSheet())

    def test_inspector_tags_and_notes_interactive_editing_and_reselection(self):
        """Verify Tags is single-line editable QLineEdit and Notes is multi-line editable QTextEdit, persisting across re-selection."""
        from ui.panels.inspector_panel import InspectorPanel
        from PySide6.QtWidgets import QLineEdit, QTextEdit

        # Create an asset in the project
        assets_dir = Path(self.project.location) / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        test_file = assets_dir / "prop_sword.fbx"
        test_file.write_text("model data")

        self.asset_service.rebuild_index(self.project, force=True)
        assets = self.asset_service.get_assets(self.project)
        target = assets[0]
        aid = target["id"]

        inspector = InspectorPanel()
        inspector.set_context(self.context)
        inspector.show_asset(self.project, aid)

        # Locate Tags QLineEdit and Notes QTextEdit
        line_edits = inspector.findChildren(QLineEdit)
        text_edits = inspector.findChildren(QTextEdit)

        self.assertGreater(len(line_edits), 0, "Tags should be rendered as a QLineEdit")
        self.assertGreater(len(text_edits), 0, "Notes should be rendered as a QTextEdit")

        tags_edit = line_edits[0]
        notes_edit = text_edits[0]

        # Verify not read-only
        self.assertFalse(tags_edit.isReadOnly())
        self.assertFalse(notes_edit.isReadOnly())

        # Simulate user typing into Tags and Notes
        tags_edit.setText("concept, weapon, legendary")
        notes_edit.setPlainText("Hero legendary sword model.\nPoly count: 12k tris.\nReady for texturing.")

        # Trigger pending save (as timer does)
        inspector._execute_pending_save()

        # Reselect asset in Inspector to verify persistence and reload
        inspector.show_asset(self.project, aid)

        new_line_edits = inspector.findChildren(QLineEdit)
        new_text_edits = inspector.findChildren(QTextEdit)
        self.assertEqual(new_line_edits[0].text(), "concept, weapon, legendary")
        self.assertEqual(new_text_edits[0].toPlainText(), "Hero legendary sword model.\nPoly count: 12k tris.\nReady for texturing.")

        # Verify on-disk persistence
        fresh_svc = AssetService(self.project_service)
        fresh_asset = fresh_svc.get_asset(self.project, aid)
        self.assertEqual(fresh_asset["tags"], ["concept", "weapon", "legendary"])
        self.assertEqual(fresh_asset["notes"], "Hero legendary sword model.\nPoly count: 12k tris.\nReady for texturing.")

    def test_inspector_lifecycle_selection_transitions(self):
        """Verify lifecycle cleanup across transitions: project -> asset A -> asset B -> project, with single sections and editable fields."""
        from ui.panels.inspector_panel import InspectorPanel
        from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QTextEdit

        # Create two distinct assets in the project
        assets_dir = Path(self.project.location) / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        file_a = assets_dir / "ranjit-rana-render2.png"
        file_a.write_text("render 2 content")
        file_b = assets_dir / "steam03.jpg"
        file_b.write_text("steam 03 content")

        self.asset_service.rebuild_index(self.project, force=True)
        assets = self.asset_service.get_assets(self.project)
        asset_a = next(a for a in assets if a["filename"] == "ranjit-rana-render2.png")
        asset_b = next(a for a in assets if a["filename"] == "steam03.jpg")

        inspector = InspectorPanel()
        inspector.set_context(self.context)

        # 1. Inspect Project
        inspector.show_project(self.project)
        project_boxes = inspector.findChildren(QFrame, "section_box")
        section_titles = [b.findChild(QLabel, "section_title").text() for b in project_boxes if b.findChild(QLabel, "section_title")]
        self.assertIn("General", section_titles)
        self.assertIn("Organization", section_titles)
        self.assertNotIn("Asset Properties", section_titles)
        # Check exactly one "General" section
        self.assertEqual(section_titles.count("General"), 1)

        # 2. Transition Project -> Asset A
        inspector.show_asset(self.project, asset_a["id"])
        asset_boxes_a = inspector.findChildren(QFrame, "section_box")
        titles_a = [b.findChild(QLabel, "section_title").text() for b in asset_boxes_a if b.findChild(QLabel, "section_title")]
        self.assertEqual(len(titles_a), 1)
        self.assertEqual(titles_a[0], "Asset Properties")
        self.assertIn("ranjit-rana-render2.png", inspector.header_title.text())

        # Verify Tags and Notes are editable
        tags_le_a = inspector.findChildren(QLineEdit)[0]
        notes_te_a = inspector.findChildren(QTextEdit)[0]
        self.assertFalse(tags_le_a.isReadOnly())
        self.assertFalse(notes_te_a.isReadOnly())

        # 3. Transition Asset A -> Asset B (leaves exactly ONE Asset Properties section, old filename gone)
        inspector.show_asset(self.project, asset_b["id"])
        asset_boxes_b = inspector.findChildren(QFrame, "section_box")
        titles_b = [b.findChild(QLabel, "section_title").text() for b in asset_boxes_b if b.findChild(QLabel, "section_title")]
        self.assertEqual(len(titles_b), 1, "Switching assets must leave exactly ONE Asset Properties section")
        self.assertEqual(titles_b[0], "Asset Properties")
        self.assertIn("steam03.jpg", inspector.header_title.text())
        self.assertNotIn("ranjit-rana-render2.png", inspector.header_title.text())

        # Verify Tags and Notes are still editable on Asset B
        tags_le_b = inspector.findChildren(QLineEdit)[0]
        notes_te_b = inspector.findChildren(QTextEdit)[0]
        self.assertFalse(tags_le_b.isReadOnly())
        self.assertFalse(notes_te_b.isReadOnly())

        # 4. Transition Asset B -> Project
        inspector.show_project(self.project)
        project_boxes_2 = inspector.findChildren(QFrame, "section_box")
        titles_proj_2 = [b.findChild(QLabel, "section_title").text() for b in project_boxes_2 if b.findChild(QLabel, "section_title")]
        self.assertEqual(titles_proj_2.count("General"), 1)
        self.assertNotIn("Asset Properties", titles_proj_2)

        # 5. Stale / deleted asset selection is safely ignored
        inspector.show_asset(self.project, "non-existent-stale-id")
        # Current inspectable should remain project without breaking
        self.assertEqual(type(inspector._current_inspectable).__name__, "ProjectInspectable")


if __name__ == "__main__":
    unittest.main()
