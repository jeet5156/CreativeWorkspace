"""Unit tests for Visual Markup data model and MarkupService persistence."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from models.markup import (
    MarkupDocument,
    is_valid_normalized_coord,
    is_valid_normalized_point,
    VALID_ANNOTATION_TYPES,
)
from services.markup_service import MarkupService

app = QApplication.instance() or QApplication([])


class TestMarkupService(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="cw_test_markup_")
        self.storage_dir = Path(self.test_dir) / "markups"
        self.service = MarkupService(storage_dir=self.storage_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_markup_model_serialization(self):
        """Test MarkupDocument to_dict and from_dict roundtrip."""
        source_ref = {
            "source_type": "project_asset",
            "project_id": "proj_123",
            "asset_id": "asset_456",
            "relative_path": "References/moodboard.png",
            "category": "References",
        }
        doc = MarkupDocument(
            name="Review 1",
            source_reference=source_ref,
            annotations=[
                {
                    "id": "ann_1",
                    "type": "arrow",
                    "start": {"x": 0.1, "y": 0.2},
                    "end": {"x": 0.5, "y": 0.6},
                    "style": {"color": "#FF0000", "width": 3},
                }
            ],
        )

        data = doc.to_dict()
        self.assertTrue(data["id"].startswith("mkp_"))
        self.assertEqual(data["name"], "Review 1")
        self.assertEqual(data["source_reference"]["project_id"], "proj_123")
        self.assertEqual(len(data["annotations"]), 1)

        loaded = MarkupDocument.from_dict(data)
        self.assertEqual(loaded.id, doc.id)
        self.assertEqual(loaded.name, doc.name)
        self.assertEqual(loaded.source_reference, doc.source_reference)
        self.assertEqual(len(loaded.annotations), 1)
        self.assertEqual(loaded.annotations[0]["type"], "arrow")

    def test_create_load_persist_markup(self):
        """Test creating a markup document, writing atomically to disk, and loading back."""
        source_ref = {
            "source_type": "project_asset",
            "project_id": "proj_abc",
            "asset_id": "asset_001",
            "relative_path": "Assets/hero_prop.png",
        }

        created = self.service.create_markup(source_ref, name="Lighting Notes")
        self.assertTrue(created.id.startswith("mkp_"))
        self.assertEqual(created.name, "Lighting Notes")

        # Verify file exists on disk
        doc_path = self.service.docs_dir / f"{created.id}.json"
        self.assertTrue(doc_path.exists())

        # Retrieve from service
        retrieved = self.service.get_markup(created.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, created.id)
        self.assertEqual(retrieved.name, "Lighting Notes")

        # Reload service to simulate fresh session
        self.service.reload()
        reloaded = self.service.get_markup(created.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.id, created.id)

    def test_project_asset_source(self):
        """Test creating and finding markups for a project asset."""
        source_ref = {
            "source_type": "project_asset",
            "project_id": "project_alpha",
            "asset_id": "asset_999",
            "relative_path": "Renders/shot_001.png",
            "category": "Renders",
        }

        doc = self.service.create_markup(source_ref, name="VFX Notes")
        markups = self.service.list_markups_for_source(source_ref)
        self.assertEqual(len(markups), 1)
        self.assertEqual(markups[0].id, doc.id)

    def test_library_asset_source(self):
        """Test creating and finding markups for a global library asset."""
        source_ref = {
            "source_type": "library_asset",
            "library_asset_id": "lib_asset_xyz_789",
        }

        doc = self.service.create_markup(source_ref, name="Global Texture Feedback")
        markups = self.service.list_markups_for_source(source_ref)
        self.assertEqual(len(markups), 1)
        self.assertEqual(markups[0].id, doc.id)
        self.assertEqual(markups[0].source_reference["library_asset_id"], "lib_asset_xyz_789")

    def test_multiple_markups_for_same_source(self):
        """Test that a single source image can have multiple independent markups."""
        source_ref = {
            "source_type": "project_asset",
            "project_id": "proj_1",
            "asset_id": "asset_hero",
            "relative_path": "Renders/hero.png",
        }

        mkp1 = self.service.create_markup(source_ref, name="Art Director Notes")
        mkp2 = self.service.create_markup(source_ref, name="Compositing Callouts")
        mkp3 = self.service.create_markup(source_ref, name="Client Review")

        markups = self.service.list_markups_for_source(source_ref)
        self.assertEqual(len(markups), 3)
        markup_ids = {m.id for m in markups}
        self.assertEqual(markup_ids, {mkp1.id, mkp2.id, mkp3.id})

    def test_annotation_crud(self):
        """Test adding, updating, and removing visual annotations."""
        source_ref = {"source_type": "library_asset", "library_asset_id": "lib_001"}
        doc = self.service.create_markup(source_ref)

        # 1. Add freehand annotation
        freehand_ann = {
            "type": "freehand",
            "points": [{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.2}, {"x": 0.3, "y": 0.25}],
            "style": {"color": "#00FF00", "width": 2},
        }
        added_fh = self.service.add_annotation(doc.id, freehand_ann)
        self.assertIsNotNone(added_fh)
        self.assertIn("id", added_fh)
        ann_id = added_fh["id"]

        # 2. Add text annotation
        text_ann = {
            "type": "text",
            "position": {"x": 0.5, "y": 0.5},
            "text": "Increase specular highlight",
            "style": {"color": "#FFFFFF", "font_size": 14},
        }
        added_txt = self.service.add_annotation(doc.id, text_ann)
        self.assertIsNotNone(added_txt)

        # Verify both exist
        loaded = self.service.get_markup(doc.id)
        self.assertEqual(len(loaded.annotations), 2)

        # 3. Update annotation
        updated = self.service.update_annotation(
            doc.id, ann_id, {"style": {"color": "#0000FF", "width": 4}}
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["style"]["color"], "#0000FF")
        self.assertEqual(updated["style"]["width"], 4)

        # 4. Remove annotation
        removed = self.service.remove_annotation(doc.id, ann_id)
        self.assertTrue(removed)

        loaded_after = self.service.get_markup(doc.id)
        self.assertEqual(len(loaded_after.annotations), 1)
        self.assertEqual(loaded_after.annotations[0]["type"], "text")

    def test_normalized_coordinates_helpers(self):
        """Test normalized coordinate validation utilities."""
        self.assertTrue(is_valid_normalized_coord(0.0))
        self.assertTrue(is_valid_normalized_coord(0.5))
        self.assertTrue(is_valid_normalized_coord(1.0))
        self.assertFalse(is_valid_normalized_coord(-0.01))
        self.assertFalse(is_valid_normalized_coord(1.01))
        self.assertFalse(is_valid_normalized_coord("not_a_num"))

        self.assertTrue(is_valid_normalized_point({"x": 0.2, "y": 0.8}))
        self.assertFalse(is_valid_normalized_point({"x": 1.2, "y": 0.8}))
        self.assertTrue(is_valid_normalized_point([0.3, 0.4]))
        self.assertFalse(is_valid_normalized_point([0.3, -0.1]))

    def test_delete_markup(self):
        """Test deleting a markup document removes it from memory and disk."""
        source_ref = {"source_type": "project_asset", "project_id": "p1", "asset_id": "a1"}
        doc = self.service.create_markup(source_ref, name="Temporary Markup")
        doc_file = self.service.docs_dir / f"{doc.id}.json"
        self.assertTrue(doc_file.exists())

        # Delete
        deleted = self.service.delete_markup(doc.id)
        self.assertTrue(deleted)
        self.assertFalse(doc_file.exists())
        self.assertIsNone(self.service.get_markup(doc.id))

        # Deleting non-existent markup returns False
        self.assertFalse(self.service.delete_markup("non_existent_id"))

    def test_missing_and_corrupt_markup_handling(self):
        """Test graceful handling of missing or corrupt markup files."""
        self.assertIsNone(self.service.get_markup("non_existent"))

        # Write corrupt JSON file into docs_dir
        corrupt_file = self.service.docs_dir / "corrupt.json"
        corrupt_file.write_text("{invalid_json: 123", encoding="utf-8")

        # Reload should not crash and skips corrupt file
        self.service.reload()
        self.assertNotIn("corrupt", self.service._markups)

    def test_original_image_untouched(self):
        """Verify that creating, modifying, and deleting markups NEVER alters the original source image file."""
        fake_img = Path(self.test_dir) / "original_image.png"
        fake_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest")
        initial_stat = fake_img.stat()
        initial_bytes = fake_img.read_bytes()

        source_ref = {
            "source_type": "project_asset",
            "project_id": "proj_test",
            "asset_id": "img_001",
            "relative_path": str(fake_img),
        }

        # Perform markup operations
        doc = self.service.create_markup(source_ref, name="Test Notes")
        self.service.add_annotation(
            doc.id,
            {
                "type": "rectangle",
                "rect": [0.1, 0.1, 0.4, 0.4],
                "style": {"color": "#FFFF00", "width": 2},
            },
        )
        self.service.update_markup(doc)
        self.service.delete_markup(doc.id)

        # Verify original image was completely untouched
        current_bytes = fake_img.read_bytes()
        current_stat = fake_img.stat()

        self.assertEqual(current_bytes, initial_bytes)
        self.assertEqual(current_stat.st_mtime, initial_stat.st_mtime)
        self.assertEqual(current_stat.st_size, initial_stat.st_size)


if __name__ == "__main__":
    unittest.main()
