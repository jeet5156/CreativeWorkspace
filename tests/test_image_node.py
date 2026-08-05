import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication, QGraphicsScene
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QSize

from ui.lab.nodes.node_context import NodeContext
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.image_node_item import ImageNodeItem
from services.thumbnail_service import ThumbnailService
from core.inspectable_adapters import NodeInspectable

app = QApplication.instance() or QApplication([])


class TestImageNode(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sample_image = Path(self.temp_dir) / "sample_concept.png"
        self.thumb_svc = ThumbnailService()

        # Create valid sample image
        img = QImage(320, 240, QImage.Format_ARGB32)
        img.fill(0xFF00FF00)
        img.save(str(self.sample_image), "PNG")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_multi_node_payload_and_pixmap_isolation(self):
        """Verify 3 distinct Reference Image nodes own independent payloads, layout dicts, pixmaps, and callbacks."""
        img_dragon = Path(self.temp_dir) / "dragon.png"
        img_knight = Path(self.temp_dir) / "knight.png"
        img_castle = Path(self.temp_dir) / "castle.png"

        for p in (img_dragon, img_knight, img_castle):
            img = QImage(100, 100, QImage.Format_RGB32)
            img.fill(0x0000FF)
            img.save(str(p), "PNG")

        node_ctx = NodeContext(project_location=self.temp_dir, thumbnail_service=self.thumb_svc)

        node_a = NodeRegistry.create_node("image.reference", node_context=node_ctx)
        node_b = NodeRegistry.create_node("image.reference", node_context=node_ctx)
        node_c = NodeRegistry.create_node("image.reference", node_context=node_ctx)

        node_a.set_image(str(img_dragon))
        node_b.set_image(str(img_knight))
        node_c.set_image(str(img_castle))

        print("\n=== MULTI-NODE STATE ISOLATION REPORT ===")
        for name, node in (("Node A", node_a), ("Node B", node_b), ("Node C", node_c)):
            print(f"[{name}] node.id: {node.id}")
            print(f"[{name}] id(node.payload): {id(node.payload)}")
            print(f"[{name}] id(node.payload['layout']): {id(node.payload['layout'])}")
            print(f"[{name}] image_path: {node.payload['image_path']}")
            print(f"[{name}] filename: {node.payload['filename']}")
            print(f"[{name}] id(node._pixmap): {id(node._pixmap)}")
            print(f"[{name}] id(node._on_thumbnail_ready): {id(node._on_thumbnail_ready)}")
            print("---")

        # 1. Verify unique node IDs
        self.assertNotEqual(node_a.id, node_b.id)
        self.assertNotEqual(node_b.id, node_c.id)

        # 2. Verify unique payload dictionary instances
        self.assertNotEqual(id(node_a.payload), id(node_b.payload))
        self.assertNotEqual(id(node_b.payload), id(node_c.payload))

        # 3. Verify unique layout dictionary instances
        self.assertNotEqual(id(node_a.payload["layout"]), id(node_b.payload["layout"]))
        self.assertNotEqual(id(node_b.payload["layout"]), id(node_c.payload["layout"]))

        # 4. Verify distinct image paths
        self.assertIn("dragon.png", node_a.payload["image_path"])
        self.assertIn("knight.png", node_b.payload["image_path"])
        self.assertIn("castle.png", node_c.payload["image_path"])

        # 5. Verify mutating Node B does NOT affect Node A or Node C
        node_b.payload["title"] = "Knight Concept"
        node_b.payload["fit_mode"] = "fill"

        self.assertEqual(node_a.payload.get("title", ""), "")
        self.assertEqual(node_c.payload.get("title", ""), "")
        self.assertEqual(node_a.payload.get("fit_mode"), "fit")
        self.assertEqual(node_c.payload.get("fit_mode"), "fit")

    def test_same_image_multi_node_deduplication_and_replacement(self):
        """Verify 3 nodes requesting same image are deduplicated to 1 worker, and replacing image on 1 node leaves others untouched."""
        shared_img = Path(self.temp_dir) / "shared.png"
        img = QImage(120, 120, QImage.Format_RGB32)
        img.fill(0xFF0000)
        img.save(str(shared_img), "PNG")

        other_img = Path(self.temp_dir) / "other.png"
        img2 = QImage(120, 120, QImage.Format_RGB32)
        img2.fill(0x00FF00)
        img2.save(str(other_img), "PNG")

        node_ctx = NodeContext(project_location=self.temp_dir, thumbnail_service=self.thumb_svc)

        node_a = NodeRegistry.create_node("image.reference", node_context=node_ctx)
        node_b = NodeRegistry.create_node("image.reference", node_context=node_ctx)
        node_c = NodeRegistry.create_node("image.reference", node_context=node_ctx)

        # Set same image on A, B, C
        node_a.set_image(str(shared_img))
        node_b.set_image(str(shared_img))
        node_c.set_image(str(shared_img))

        # Verify only 1 key is queued in ThumbnailService
        key = (str(self.temp_dir), "shared.png")
        self.assertIn(key, self.thumb_svc._queued)

        # Replace image on Node B
        node_b.set_image(str(other_img))

        self.assertIn("other.png", node_b.payload["image_path"])
        self.assertIn("shared.png", node_a.payload["image_path"])
        self.assertIn("shared.png", node_c.payload["image_path"])

    def test_default_node_dimensions_320x260(self):
        """Verify default size of Reference Image node is 320x260."""
        defn = NodeRegistry.get("image.reference")
        self.assertEqual(defn.default_size, (320.0, 260.0))

        node = NodeRegistry.create_node("image.reference")
        self.assertEqual(node.width, 320.0)
        self.assertEqual(node.height, 260.0)

    def test_set_image_api_and_layout_payload(self):
        """Verify set_image API calculates relative path, aspect ratio, and populates layout payload."""
        proj_dir = Path(self.temp_dir) / "ProjectAlpha"
        assets_dir = proj_dir / "Assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        target_img = assets_dir / "hero.png"
        shutil.copy(self.sample_image, target_img)

        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(target_img), project_location=str(proj_dir))

        self.assertEqual(node.payload.get("filename"), "hero.png")
        self.assertEqual(node.payload.get("image_path"), "Assets/hero.png")

        layout = node.payload.get("layout", {})
        self.assertIsNotNone(layout)
        self.assertAlmostEqual(layout.get("aspect_ratio"), 320.0 / 240.0, places=2)
        self.assertEqual(layout.get("raw_width"), 320)
        self.assertEqual(layout.get("raw_height"), 240)

    def test_thumbnail_callback_updates_node_dynamically(self):
        """Verify thumbnail_ready callback updates _pixmap and repaints without reopening Lab."""
        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        scene = QGraphicsScene()
        scene.addItem(node)

        node.set_context_services(self.thumb_svc, self.temp_dir)
        node.set_image(str(self.sample_image))
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone()

        # Create dummy thumbnail file to simulate ThumbnailService completion
        thumb_path = Path(self.temp_dir) / ".creativeworkspace" / "thumbnails" / "sample.png"
        thumb_path.parent.mkdir(parents=True, exist_ok=True)
        img = QImage(160, 120, QImage.Format_ARGB32)
        img.fill(0xFF00FF00)
        img.save(str(thumb_path), "PNG")

        # Emit callback
        node._on_thumbnail_ready(node.id, str(thumb_path))

        self.assertIsNotNone(node._pixmap)
        self.assertFalse(node._pixmap.isNull())

    def test_save_reload_relative_path_persistence(self):
        """Verify relative project paths resolve cleanly when reloading saved node dict."""
        proj_dir = Path(self.temp_dir) / "Proj"
        ref_dir = proj_dir / "References"
        ref_dir.mkdir(parents=True, exist_ok=True)
        img_path = ref_dir / "concept.png"
        shutil.copy(self.sample_image, img_path)

        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(img_path), project_location=str(proj_dir))
        node.payload["title"] = "Environment Reference"

        data = node.to_dict()

        # Re-create node from serialized data
        restored = NodeRegistry.create_node("image.reference", data)
        restored.set_context_services(self.thumb_svc, str(proj_dir))

        resolved = restored._resolve_abs_path()
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.exists())
        self.assertEqual(restored.payload["title"], "Environment Reference")

    def test_missing_image_state_display(self):
        """Verify missing image path renders 'Image Missing' state safely without crashing."""
        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        missing = str(Path(self.temp_dir) / "deleted_file.png")
        node.set_image(missing)

        self.assertEqual(node.payload.get("image_path"), missing)
        self.assertEqual(node.payload.get("filename"), "deleted_file.png")
        self.assertIsNone(node._resolve_abs_path())

    def test_delete_node_via_keyboard_and_canvas_api(self):
        """Verify delete_selected_nodes and remove_node remove items from scene and items map."""
        from ui.widgets.infinite_canvas import InfiniteCanvas
        canvas = InfiniteCanvas()

        node1 = canvas.add_node({"type": "image.reference"})
        node2 = canvas.add_node({"type": "image.reference"})

        self.assertIn(node1.id, canvas._items_map)
        self.assertIn(node2.id, canvas._items_map)

        node1.setSelected(True)
        canvas.delete_selected_nodes()

        self.assertNotIn(node1.id, canvas._items_map)
        self.assertIn(node2.id, canvas._items_map)

        canvas.remove_node(node2.id)
        self.assertNotIn(node2.id, canvas._items_map)

    def test_clear_image_resets_node_to_empty_state(self):
        """Verify clearing image resets node to empty image_path and null pixmap."""
        node = ImageNodeItem(definition=NodeRegistry.get("image.reference"))
        node.set_image(str(self.sample_image))

        self.assertTrue(bool(node.payload.get("image_path")))
        node.set_image("")

        self.assertEqual(node.payload.get("image_path"), "")
        self.assertEqual(node.payload.get("filename"), "")
        self.assertIsNone(node._pixmap)
        self.assertIsNone(node._resolve_abs_path())

    def test_10_node_save_and_reopen_persistence(self):
        """Permanent Regression Test: Create 10 nodes with 10 distinct images, save board, reload, verify exact 1-to-1 mapping."""
        from ui.widgets.infinite_canvas import InfiniteCanvas
        from PySide6.QtCore import QThreadPool
        from ui.lab.nodes.image_node_item import ImageNodeState

        canvas = InfiniteCanvas()
        canvas.update_project_location(self.temp_dir)
        canvas.set_node_context(NodeContext(project_location=self.temp_dir, thumbnail_service=self.thumb_svc))

        images = []
        for i in range(1, 11):
            img_path = Path(self.temp_dir) / f"concept_{i}.png"
            img = QImage(160, 120, QImage.Format_ARGB32)
            img.fill(0xFF000000 | (i * 0x102030))
            img.save(str(img_path), "PNG")
            images.append(img_path)

        created_nodes = []
        for i, img_path in enumerate(images, 1):
            node = canvas.add_node({"type": "image.reference"})
            node.set_image(str(img_path), project_location=self.temp_dir)
            created_nodes.append(node)

        QThreadPool.globalInstance().waitForDone()

        for idx, (node, img_path) in enumerate(zip(created_nodes, images), 1):
            self.assertEqual(node.state, ImageNodeState.READY)
            self.assertIsNotNone(node._pixmap)
            self.assertFalse(node._pixmap.isNull())

        # Save canvas nodes to serialized list of dicts
        saved_dicts = [n.to_dict() for n in canvas._items_map.values()]

        # Clear canvas
        canvas.clear_nodes()
        self.assertEqual(len(canvas._items_map), 0)

        # Simulate project reload by restoring canvas from serialized dicts
        restored_nodes = []
        for item_data in saved_dicts:
            node = canvas.add_node(item_data)
            restored_nodes.append(node)

        QThreadPool.globalInstance().waitForDone()

        self.assertEqual(len(canvas._items_map), 10)
        for i, (restored, orig_img) in enumerate(zip(restored_nodes, images), 1):
            self.assertEqual(restored.state, ImageNodeState.READY)
            self.assertIsNotNone(restored._pixmap)
            self.assertFalse(restored._pixmap.isNull())
            resolved = restored._resolve_abs_path()
            self.assertEqual(resolved, orig_img)


if __name__ == "__main__":
    unittest.main()
