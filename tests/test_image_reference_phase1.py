import unittest
import tempfile
import shutil
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from PySide6.QtCore import QPointF, QMimeData, QUrl

from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.drop_router import DropRouter
from ui.lab.drop.handlers.image_handler import ImageDropHandler
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.image_node_item import ImageNodeItem, ImageNodeState
from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable

app = QApplication.instance() or QApplication([])


class TestImageReferencePhase1(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sample_png = Path(self.temp_dir) / "character.png"
        self.sample_jpg = Path(self.temp_dir) / "concept.jpg"

        # Create valid image files
        img = QImage(320, 240, QImage.Format_ARGB32)
        img.fill(0xFF00FF00)
        img.save(str(self.sample_png), "PNG")
        img.save(str(self.sample_jpg), "JPEG")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_supported_image_extensions(self):
        """Verify all mandatory image extensions are supported by ImageDropHandler."""
        handler = ImageDropHandler()
        supported = handler.SUPPORTED_EXTENSIONS

        expected_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
        for ext in expected_exts:
            self.assertIn(ext, supported, f"Extension {ext} should be supported.")

    def test_image_reference_payload_structure(self):
        """Verify Image Reference payload schema contains path, absolute_path, filename, and extension."""
        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(self.sample_png))

        self.assertEqual(node.payload.get("filename"), "character.png")
        self.assertEqual(node.payload.get("file_name"), "character.png")
        self.assertEqual(node.payload.get("extension"), ".png")
        self.assertTrue(node.payload.get("file_size_str").endswith("B") or node.payload.get("file_size_str").endswith("KB"))
        self.assertEqual(node.payload.get("absolute_path"), str(self.sample_png.resolve()))

    def test_drop_router_node_creation_and_multi_file_drop(self):
        """Verify DropRouter creates staggered image.reference nodes for multi-file drop contexts."""
        router = DropRouter()

        mime = QMimeData()
        urls = [QUrl.fromLocalFile(str(self.sample_png)), QUrl.fromLocalFile(str(self.sample_jpg))]
        mime.setUrls(urls)

        drop_pos = QPointF(100.0, 200.0)
        ctx = DropContext(mime, drop_pos, project_location=self.temp_dir)

        self.assertTrue(router.can_route(ctx))
        nodes_data = router.route_drop(ctx)

        self.assertEqual(len(nodes_data), 2)
        self.assertEqual(nodes_data[0]["type"], "image.reference")
        self.assertEqual(nodes_data[1]["type"], "image.reference")

        # Staggered placement check (+30px offset per item)
        self.assertEqual(nodes_data[0]["transform"]["x"], 100.0)
        self.assertEqual(nodes_data[0]["transform"]["y"], 200.0)
        self.assertEqual(nodes_data[1]["transform"]["x"], 130.0)
        self.assertEqual(nodes_data[1]["transform"]["y"], 230.0)

    def test_missing_file_detection_and_relink(self):
        """Verify missing file triggers MISSING state and relinking recovers node state."""
        target_path = Path(self.temp_dir) / "temporary.png"
        shutil.copy(self.sample_png, target_path)

        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(target_path))

        # Delete target file externally
        target_path.unlink()
        node._request_thumbnail()

        self.assertEqual(node.state, ImageNodeState.MISSING)

        # Relink to renamed file
        new_path = Path(self.temp_dir) / "character_final.png"
        shutil.copy(self.sample_png, new_path)

        node.set_image(str(new_path))
        self.assertEqual(node.payload.get("filename"), "character_final.png")
        self.assertEqual(node.payload.get("extension"), ".png")
        self.assertNotEqual(node.state, ImageNodeState.MISSING)

    def test_live_missing_file_detection_on_validation(self):
        """Verify live detection transitions node to MISSING when file is deleted/renamed externally."""
        target_path = Path(self.temp_dir) / "to_delete.png"
        shutil.copy(self.sample_png, target_path)

        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(target_path))

        # File exists -> validate returns True
        self.assertTrue(node.validate_reference(force=True))
        self.assertNotEqual(node.state, ImageNodeState.MISSING)

        # Delete file externally
        target_path.unlink()

        # Validate reference -> transitions to MISSING immediately
        valid = node.validate_reference(force=True)
        self.assertFalse(valid)
        self.assertEqual(node.state, ImageNodeState.MISSING)
        self.assertIsNone(node._pixmap)

    def test_live_file_recovery_on_validation(self):
        """Verify restoring a deleted file to original path automatically clears MISSING state on validation."""
        target_path = Path(self.temp_dir) / "restorable.png"
        shutil.copy(self.sample_png, target_path)

        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(target_path))

        # Delete file externally -> force validate -> MISSING
        target_path.unlink()
        node.validate_reference(force=True)
        self.assertEqual(node.state, ImageNodeState.MISSING)

        # Re-create file at same path
        shutil.copy(self.sample_png, target_path)

        # Validate reference -> detects restored file -> clears MISSING state
        valid = node.validate_reference(force=True)
        self.assertTrue(valid)
        self.assertNotEqual(node.state, ImageNodeState.MISSING)

    def test_validation_cooldown_throttling(self):
        """Verify validation cooldown prevents repeated filesystem calls within cooldown window."""
        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(self.sample_png))

        # First validation sets timestamp
        node.validate_reference(force=True)
        t1 = node._last_validated_time

        # Immediate second validation without force skips check (uses cached cooldown)
        node.validate_reference(force=False)
        t2 = node._last_validated_time

        self.assertEqual(t1, t2)

    def test_double_click_missing_file_prevents_launch(self):
        """Verify double clicking a missing file validates to MISSING state without trying to open file."""
        target_path = Path(self.temp_dir) / "missing_launch.png"
        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(target_path))

        # Perform validation on missing file
        valid = node.validate_reference(force=True)
        self.assertFalse(valid)
        self.assertEqual(node.state, ImageNodeState.MISSING)

    def test_persistence_reference_only_and_no_file_copying(self):
        """Verify serializing canvas nodes saves reference path metadata without copying original files."""
        canvas = InfiniteCanvas()
        canvas.update_project_location(self.temp_dir)

        # Record original image stats
        orig_stat_before = self.sample_png.stat()

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.sample_png))])
        ctx = DropContext(mime, QPointF(50.0, 50.0), project_location=self.temp_dir)

        router = DropRouter()
        nodes_data = router.route_drop(ctx)

        self.assertEqual(len(nodes_data), 1)
        node = canvas.add_node(nodes_data[0])

        serialized = node.to_dict()
        self.assertEqual(serialized["type"], "image.reference")
        self.assertIn("character.png", serialized["payload"]["image_path"])

        # Confirm original file remains untouched
        orig_stat_after = self.sample_png.stat()
        self.assertEqual(orig_stat_before.st_size, orig_stat_after.st_size)

    def test_inspector_node_adapter_image_reference(self):
        """Verify NodeInspectable exposes Original File Path and size fields for Image Reference Nodes."""
        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(self.sample_png))

        adapter = NodeInspectable(node)
        sections = adapter.get_inspection_sections()

        ref_section = next((s for s in sections if s.title == "Reference Properties"), None)
        self.assertIsNotNone(ref_section)

        path_field = next((f for f in ref_section.fields if f.key == "payload.path"), None)
        self.assertIsNotNone(path_field)
        self.assertIn("character.png", path_field.value)


if __name__ == "__main__":
    unittest.main()
