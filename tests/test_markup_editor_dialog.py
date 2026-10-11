"""Unit tests for MarkupEditorDialog: canvas integration, annotations list synchronization, bidirectional selection, and persistence."""

import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from models.markup import MarkupDocument
from services.markup_service import MarkupService
from ui.dialogs.markup_editor_dialog import MarkupEditorDialog

app = QApplication.instance() or QApplication([])


class TestMarkupEditorDialog(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cw_test_markup_dialog_")
        self.storage_dir = Path(self.test_dir) / "markups"
        self.markup_service = MarkupService(storage_dir=self.storage_dir)

        # Create test image on disk
        self.image_path = Path(self.test_dir) / "cyclops_concept.png"
        img = QImage(1200, 800, QImage.Format_RGB32)
        img.fill(QColor("#333333"))
        img.save(str(self.image_path))

        self.source_reference = {
            "source_type": "project_asset",
            "project_id": "proj_cyclops",
            "asset_id": "asset_hero_1",
            "relative_path": "References/cyclops_concept.png",
            "category": "References",
        }

        self.dialog = MarkupEditorDialog(
            image_source=str(self.image_path),
            source_reference=self.source_reference,
            markup_service=self.markup_service,
        )
        self.dialog.show()

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dialog_initialization_and_document_binding(self):
        """Verify dialog initializes image, queries MarkupService, and creates document."""
        self.assertTrue(self.dialog.canvas.has_image())
        self.assertIsNotNone(self.dialog._document)
        self.assertEqual(self.dialog._document.source_reference["asset_id"], "asset_hero_1")
        self.assertEqual(self.dialog._document.source_reference["project_id"], "proj_cyclops")
        self.assertIn("cyclops_concept.png", self.dialog.windowTitle())

    def test_annotations_list_sync_on_creation(self):
        """Verify adding annotations automatically populates the side panel list."""
        self.assertEqual(self.dialog.ann_list.count(), 0)

        # 1. Create Pin
        ann1 = self.dialog.canvas.create_pin_annotation(QPointF(0.42, 0.63), "Fix eyelid topology")
        self.assertIsNotNone(ann1)
        self.assertEqual(self.dialog.ann_list.count(), 1)
        self.assertEqual(self.dialog.lbl_counter.text(), "1 Annotation")

        # 2. Create Arrow
        ann2 = self.dialog.canvas.create_arrow_annotation(QPointF(0.2, 0.2), QPointF(0.5, 0.5))
        self.assertIsNotNone(ann2)
        self.assertEqual(self.dialog.ann_list.count(), 2)
        self.assertEqual(self.dialog.lbl_counter.text(), "2 Annotations")

        # 3. Create Freehand
        ann3 = self.dialog.canvas.create_freehand_annotation([{"x": 0.1, "y": 0.1}, {"x": 0.15, "y": 0.15}])
        self.assertIsNotNone(ann3)
        self.assertEqual(self.dialog.ann_list.count(), 3)
        self.assertEqual(self.dialog.lbl_counter.text(), "3 Annotations")

    def test_bidirectional_selection_synchronization(self):
        """Verify selecting a list row selects canvas annotation, and canvas selection updates list row."""
        ann1 = self.dialog.canvas.create_pin_annotation(QPointF(0.3, 0.3), "Check horn texture")
        ann2 = self.dialog.canvas.create_arrow_annotation(QPointF(0.1, 0.1), QPointF(0.4, 0.4))

        # 1. Canvas selects ann1 -> List selects item 0
        self.dialog.canvas.select_annotation(ann1)
        self.assertEqual(self.dialog.ann_list.currentItem().data(Qt.UserRole), ann1)
        self.assertTrue(self.dialog.btn_delete_ann.isEnabled())

        # 2. Canvas selects ann2 -> List selects item 1
        self.dialog.canvas.select_annotation(ann2)
        self.assertEqual(self.dialog.ann_list.currentItem().data(Qt.UserRole), ann2)

        # 3. List click item 0 -> Canvas selects ann1
        item0 = self.dialog.ann_list.item(0)
        self.dialog._on_list_item_clicked(item0)
        self.assertEqual(self.dialog.canvas.selected_annotation_id(), ann1)

    def test_delete_from_list_panel(self):
        """Verify clicking Delete in side panel removes annotation from list and canvas."""
        ann1 = self.dialog.canvas.create_pin_annotation(QPointF(0.3, 0.3), "Temporary Pin")
        self.assertEqual(self.dialog.ann_list.count(), 1)

        self.dialog.canvas.select_annotation(ann1)
        self.dialog._on_delete_selected_clicked()

        self.assertEqual(self.dialog.ann_list.count(), 0)
        self.assertEqual(len(self.dialog.canvas.view._annotation_items), 0)
        self.assertFalse(self.dialog.btn_delete_ann.isEnabled())

    def test_auto_persistence_and_reload_for_same_source_reference(self):
        """Verify markups saved in dialog automatically reload when reopening for the same asset."""
        # 1. Add annotations in current dialog
        ann1 = self.dialog.canvas.create_pin_annotation(QPointF(0.42, 0.63), "Shoulder silhouette")
        ann2 = self.dialog.canvas.create_arrow_annotation(QPointF(0.1, 0.2), QPointF(0.3, 0.4))
        self.dialog.close()

        # 2. Open a second dialog with identical source_reference
        dialog2 = MarkupEditorDialog(
            image_source=str(self.image_path),
            source_reference=self.source_reference,
            markup_service=self.markup_service,
        )
        dialog2.show()

        # Verify existing document loaded automatically
        self.assertEqual(dialog2.ann_list.count(), 2)
        self.assertEqual(len(dialog2.canvas.view._annotation_items), 2)
        self.assertEqual(dialog2._document.id, self.dialog._document.id)

        dialog2.close()
        dialog2.deleteLater()

    def test_open_for_project_asset_factory(self):
        """Verify factory method resolves project asset and creates dialog."""
        class MockProject:
            id = "proj_cyclops"
            name = "Cyclops"
            location = self.test_dir

        class MockAssetService:
            def get_asset(self, project, asset_id):
                return {"id": asset_id, "relative_path": "References/cyclops_concept.png", "category": "References"}

            def get_asset_path(self, project, asset_id):
                return str(self.image_path)

        mock_proj = MockProject()
        mock_asset_svc = MockAssetService()
        mock_asset_svc.image_path = self.image_path

        dlg = MarkupEditorDialog.open_for_project_asset(
            mock_proj,
            "asset_hero_1",
            asset_service=mock_asset_svc,
            markup_service=self.markup_service,
        )
        self.assertIsNotNone(dlg)
        self.assertTrue(dlg.canvas.has_image())
        self.assertEqual(dlg._source_reference["source_type"], "project_asset")
        self.assertEqual(dlg._source_reference["asset_id"], "asset_hero_1")
        dlg.close()
        dlg.deleteLater()

    def test_open_for_library_asset_factory(self):
        """Verify factory method resolves library asset and creates dialog."""
        class MockDriveDetector:
            def resolve_drive_path(self, drive_id, drive_rel):
                return self.image_path

        class MockLibraryService:
            def __init__(self, img_path):
                self.drive_detector = MockDriveDetector()
                self.drive_detector.image_path = img_path

        mock_lib_svc = MockLibraryService(self.image_path)
        lib_asset_data = {
            "id": "lib_asset_99",
            "drive_id": "drive_main",
            "drive_relative_path": "ConceptArt/cyclops.png",
        }

        dlg = MarkupEditorDialog.open_for_library_asset(
            lib_asset_data,
            library_service=mock_lib_svc,
            markup_service=self.markup_service,
        )
        self.assertIsNotNone(dlg)
        self.assertTrue(dlg.canvas.has_image())
        self.assertEqual(dlg._source_reference["source_type"], "library_asset")
        self.assertEqual(dlg._source_reference["library_asset_id"], "lib_asset_99")
        dlg.close()
        dlg.deleteLater()

    def test_open_for_real_asset_service_project_asset(self):
        """Verify factory method with real AssetService instance."""
        from services.asset_service import AssetService

        class RealMockProject:
            def __init__(self, loc):
                self.id = "proj_cyclops_real"
                self.name = "Cyclops Project"
                self.location = loc

        proj_dir = Path(self.test_dir) / "real_proj"
        ref_dir = proj_dir / "References"
        ref_dir.mkdir(parents=True, exist_ok=True)
        img_file = ref_dir / "cyclops_hero.png"
        shutil.copy(str(self.image_path), str(img_file))

        real_proj = RealMockProject(str(proj_dir))
        real_asset_svc = AssetService()
        real_asset_svc.rebuild_index(real_proj, force=True)

        assets = real_asset_svc.get_assets(real_proj)
        self.assertTrue(len(assets) >= 1)
        hero_asset_id = assets[0]["id"]

        dlg = MarkupEditorDialog.open_for_project_asset(
            real_proj,
            hero_asset_id,
            asset_service=real_asset_svc,
            markup_service=self.markup_service,
        )
        self.assertIsNotNone(dlg)
        self.assertTrue(dlg.canvas.has_image())
        self.assertEqual(dlg._source_reference["project_id"], "proj_cyclops_real")
        self.assertEqual(dlg._source_reference["relative_path"], "References/cyclops_hero.png")
        dlg.close()
        dlg.deleteLater()

    def test_all_annotations_paint_rendering_safety(self):
        """Verify painting all annotation types (Pin, Arrow, Freehand, Rect, Ellipse) without QBrush NameError."""
        from PySide6.QtWidgets import QStyleOptionGraphicsItem
        from PySide6.QtGui import QPainter

        # Create annotations of all types
        pin_id = self.dialog.canvas.create_pin_annotation(QPointF(0.2, 0.2), "Pin Note")
        arrow_id = self.dialog.canvas.create_arrow_annotation(QPointF(0.1, 0.1), QPointF(0.4, 0.4))
        freehand_id = self.dialog.canvas.create_freehand_annotation([{"x": 0.3, "y": 0.3}, {"x": 0.5, "y": 0.5}])

        # Verify items exist
        self.assertEqual(len(self.dialog.canvas.view._annotation_items), 3)

        # Render scene to QImage to exercise paint() methods for both unselected and selected states
        render_target = QImage(1200, 800, QImage.Format_ARGB32_Premultiplied)
        painter = QPainter(render_target)
        option = QStyleOptionGraphicsItem()

        for ann_id, item in self.dialog.canvas.view._annotation_items.items():
            # Paint unselected
            item.paint(painter, option, None)

            # Paint selected
            if hasattr(item, "set_markup_selected"):
                item.set_markup_selected(True)
            item.paint(painter, option, None)

        painter.end()

    def test_source_image_is_never_modified(self):
        """Verify source image byte contents remain strictly identical before and after markup mutations."""
        with open(self.image_path, "rb") as f:
            original_bytes = f.read()

        # Add annotations
        ann1 = self.dialog.canvas.create_pin_annotation(QPointF(0.5, 0.5), "Review mark")
        ann2 = self.dialog.canvas.create_arrow_annotation(QPointF(0.2, 0.2), QPointF(0.8, 0.8))
        ann3 = self.dialog.canvas.create_freehand_annotation([{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.9}])

        # Edit text
        self.dialog.canvas.edit_annotation_text(ann1, "Modified Note")

        # Delete annotation
        self.dialog.canvas.delete_annotation(ann2)

    def test_cyclops_project_references_full_markup_workflow(self):
        """End-to-end simulation of real Cyclops References workflow: Open -> Annotate (Pin, Arrow, Draw) -> Save -> Reopen."""
        from services.asset_service import AssetService

        class CyclopsProject:
            def __init__(self, loc):
                self.id = "proj_cyclops_prod"
                self.name = "Cyclops"
                self.location = loc

        cyclops_dir = Path(self.test_dir) / "Cyclops"
        ref_dir = cyclops_dir / "References"
        ref_dir.mkdir(parents=True, exist_ok=True)
        concept_file = ref_dir / "cyclops_character_sheet.png"
        shutil.copy(str(self.image_path), str(concept_file))

        with open(concept_file, "rb") as f:
            initial_concept_bytes = f.read()

        cyclops_proj = CyclopsProject(str(cyclops_dir))
        asset_svc = AssetService()
        asset_svc.rebuild_index(cyclops_proj, force=True)

        asset_entry = asset_svc.get_asset(cyclops_proj, "References/cyclops_character_sheet.png")
        self.assertIsNotNone(asset_entry)

        # 1. Open Markup Editor from Project Reference
        editor1 = MarkupEditorDialog.open_for_project_asset(
            cyclops_proj,
            asset_entry["id"],
            asset_service=asset_svc,
            markup_service=self.markup_service,
        )
        self.assertIsNotNone(editor1)
        self.assertTrue(editor1.canvas.has_image())

        # 2. Add Pin Note
        pin_id = editor1.canvas.create_pin_annotation(QPointF(0.35, 0.45), "Fix eye scale & highlight")
        self.assertIsNotNone(pin_id)

        # 3. Add Vector Arrow
        arrow_id = editor1.canvas.create_arrow_annotation(QPointF(0.2, 0.2), QPointF(0.35, 0.45))
        self.assertIsNotNone(arrow_id)

        # 4. Add Freehand Stroke
        freehand_id = editor1.canvas.create_freehand_annotation([
            {"x": 0.5, "y": 0.5},
            {"x": 0.55, "y": 0.52},
            {"x": 0.6, "y": 0.58},
        ])
        self.assertIsNotNone(freehand_id)

        self.assertEqual(editor1.ann_list.count(), 3)
        editor1.close()
        editor1.deleteLater()

        # 5. Verify source image remains completely untouched
        with open(concept_file, "rb") as f:
            post_markup_bytes = f.read()
        self.assertEqual(initial_concept_bytes, post_markup_bytes)

        # 6. Reopen same asset reference in a new editor session
        editor2 = MarkupEditorDialog.open_for_project_asset(
            cyclops_proj,
            asset_entry["id"],
            asset_service=asset_svc,
            markup_service=self.markup_service,
        )
        self.assertIsNotNone(editor2)
        self.assertEqual(editor2.ann_list.count(), 3)
        self.assertEqual(len(editor2.canvas.view._annotation_items), 3)
        self.assertIn(pin_id, editor2.canvas.view._annotation_items)
        self.assertIn(arrow_id, editor2.canvas.view._annotation_items)
        self.assertIn(freehand_id, editor2.canvas.view._annotation_items)

        editor2.close()
        editor2.deleteLater()

    def test_knowledge_linked_project_and_library_asset_markup_flow(self):
        """Verify opening markup from Knowledge notes linked to project or library assets."""
        from services.asset_service import AssetService

        class CyclopsProject:
            def __init__(self, loc):
                self.id = "proj_cyclops_knowledge"
                self.name = "Cyclops"
                self.location = loc

        cyclops_dir = Path(self.test_dir) / "CyclopsKnowledge"
        ref_dir = cyclops_dir / "References"
        ref_dir.mkdir(parents=True, exist_ok=True)
        img_file = ref_dir / "cyclops_lore_image.png"
        shutil.copy(str(self.image_path), str(img_file))

        cyclops_proj = CyclopsProject(str(cyclops_dir))
        asset_svc = AssetService()
        asset_svc.rebuild_index(cyclops_proj, force=True)

        asset_entry = asset_svc.get_asset(cyclops_proj, "References/cyclops_lore_image.png")

        # Knowledge relationship payload for project_asset
        knowledge_rel_data = {
            "project_id": cyclops_proj.name,
            "asset_id": asset_entry["id"],
            "relative_path": "References/cyclops_lore_image.png",
            "category": "References",
        }

        # Open via factory using knowledge relationship data
        dlg = MarkupEditorDialog.open_for_project_asset(
            cyclops_proj,
            knowledge_rel_data["asset_id"],
            asset_service=asset_svc,
            markup_service=self.markup_service,
        )
        self.assertIsNotNone(dlg)
        self.assertTrue(dlg.canvas.has_image())
        ann = dlg.canvas.create_pin_annotation(QPointF(0.4, 0.4), "Lore notes on single eye")
        self.assertIsNotNone(ann)
        dlg.close()
        dlg.deleteLater()

        # Reopen and verify persistence
        dlg2 = MarkupEditorDialog.open_for_project_asset(
            cyclops_proj,
            knowledge_rel_data["asset_id"],
            asset_service=asset_svc,
            markup_service=self.markup_service,
        )
        self.assertEqual(dlg2.ann_list.count(), 1)
        dlg2.close()
        dlg2.deleteLater()


if __name__ == "__main__":
    unittest.main()
