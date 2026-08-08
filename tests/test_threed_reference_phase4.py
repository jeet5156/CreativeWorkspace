import unittest
import tempfile
import shutil
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QMimeData, QUrl

from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.drop_router import DropRouter
from ui.lab.drop.handlers.threed_handler import ThreeDDropHandler
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.threed_node_item import ThreeDNodeItem, ThreeDNodeState
from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable

app = QApplication.instance() or QApplication([])


def create_dummy_3d_file(file_path: Path):
    """Generate dummy 3D file binary for unit testing."""
    with open(file_path, "wb") as f:
        f.write(b"HEADER_DUMMY_3D_ASSET_DATA_1234567890")


class TestThreeDReferencePhase4(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sample_fbx = Path(self.temp_dir) / "character_rig.fbx"
        self.sample_obj = Path(self.temp_dir) / "prop_chair.obj"
        self.sample_blend = Path(self.temp_dir) / "environment.blend"

        create_dummy_3d_file(self.sample_fbx)
        create_dummy_3d_file(self.sample_obj)
        create_dummy_3d_file(self.sample_blend)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_all_14_supported_extensions(self):
        """Verify all mandatory 14 3D extensions are supported by ThreeDDropHandler."""
        handler = ThreeDDropHandler()
        supported = handler.SUPPORTED_EXTENSIONS

        expected_exts = {
            ".fbx", ".obj", ".glb", ".gltf", ".blend", ".abc",
            ".usd", ".usda", ".usdc", ".usdz", ".ztl", ".ma", ".mb", ".max"
        }
        self.assertEqual(expected_exts, supported)

    def test_unsupported_extensions_rejected(self):
        """Verify unsupported extensions (.exe, .py, .txt) are rejected by ThreeDDropHandler."""
        handler = ThreeDDropHandler()
        dummy_txt = Path(self.temp_dir) / "notes.txt"
        with open(dummy_txt, "w") as f:
            f.write("text content")

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(dummy_txt))])
        ctx = DropContext(mime, QPointF(50.0, 50.0), project_location=self.temp_dir)

        self.assertFalse(handler.can_handle(ctx))

    def test_drop_router_creates_threed_asset_node(self):
        """Verify DropRouter routes .fbx drop to asset.3d node with correct payload."""
        router = DropRouter()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.sample_fbx))])
        ctx = DropContext(mime, QPointF(100.0, 200.0), project_location=self.temp_dir)

        self.assertTrue(router.can_route(ctx))
        nodes_data = router.route_drop(ctx)

        self.assertEqual(len(nodes_data), 1)
        self.assertEqual(nodes_data[0]["type"], "asset.3d")
        self.assertEqual(nodes_data[0]["payload"]["filename"], "character_rig.fbx")
        self.assertEqual(nodes_data[0]["payload"]["format_label"], "FBX 3D Model")

    def test_threed_payload_structure(self):
        """Verify ThreeDNodeItem populates payload schema correctly."""
        node = ThreeDNodeItem(definition=NodeRegistry.get("asset.3d"))
        node.set_asset(str(self.sample_fbx))

        self.assertEqual(node.payload.get("filename"), "character_rig.fbx")
        self.assertEqual(node.payload.get("extension"), ".fbx")
        self.assertEqual(node.payload.get("format_label"), "FBX 3D Model")
        self.assertEqual(node.payload.get("display_mode"), "icon")
        self.assertTrue(node.payload.get("file_size_str").endswith("B"))

    def test_source_file_not_copied_or_moved(self):
        """Verify 3D source file stats remain untouched after node creation."""
        stat_before = self.sample_fbx.stat()

        node = ThreeDNodeItem(definition=NodeRegistry.get("asset.3d"))
        node.set_asset(str(self.sample_fbx))
        serialized = node.to_dict()

        stat_after = self.sample_fbx.stat()
        self.assertEqual(stat_before.st_size, stat_after.st_size)
        self.assertEqual(serialized["payload"]["absolute_path"], str(self.sample_fbx.resolve()))

    def test_multi_file_staggered_placement(self):
        """Verify multi 3D file drop creates staggered placement coordinates (+30px offset)."""
        router = DropRouter()
        mime = QMimeData()
        urls = [QUrl.fromLocalFile(str(self.sample_fbx)), QUrl.fromLocalFile(str(self.sample_obj))]
        mime.setUrls(urls)
        ctx = DropContext(mime, QPointF(50.0, 50.0), project_location=self.temp_dir)

        nodes_data = router.route_drop(ctx)
        self.assertEqual(len(nodes_data), 2)
        self.assertEqual(nodes_data[0]["transform"]["x"], 50.0)
        self.assertEqual(nodes_data[0]["transform"]["y"], 50.0)
        self.assertEqual(nodes_data[1]["transform"]["x"], 80.0)
        self.assertEqual(nodes_data[1]["transform"]["y"], 80.0)

    def test_zero_process_double_click(self):
        """Verify double clicking a 3D asset node validates reference without external application launch."""
        node = ThreeDNodeItem(definition=NodeRegistry.get("asset.3d"))
        node.set_asset(str(self.sample_fbx))

        # Double click should execute cleanly without throwing or launching external process
        self.assertTrue(node.validate_reference(force=True))
        self.assertEqual(node.state, ThreeDNodeState.READY)

    def test_live_missing_detection_and_recovery(self):
        """Verify deleting original 3D asset transitions node to MISSING, and restoring clears MISSING."""
        temp_3d = Path(self.temp_dir) / "temp_mesh.obj"
        shutil.copy(self.sample_obj, temp_3d)

        node = ThreeDNodeItem(definition=NodeRegistry.get("asset.3d"))
        node.set_asset(str(temp_3d))
        self.assertEqual(node.state, ThreeDNodeState.READY)

        # Delete file externally
        temp_3d.unlink()
        node.validate_reference(force=True)

        self.assertEqual(node.state, ThreeDNodeState.MISSING)

        # Restore file at same path
        shutil.copy(self.sample_obj, temp_3d)
        node.validate_reference(force=True)

        self.assertEqual(node.state, ThreeDNodeState.READY)

    def test_relink_threed_asset(self):
        """Verify relinking replacement 3D asset updates filename, extension, format_label, and clears MISSING state."""
        node = ThreeDNodeItem(definition=NodeRegistry.get("asset.3d"))
        node.set_asset(str(self.sample_fbx))

        node.set_asset(str(self.sample_blend))
        self.assertEqual(node.payload.get("filename"), "environment.blend")
        self.assertEqual(node.payload.get("extension"), ".blend")
        self.assertEqual(node.payload.get("format_label"), "Blender Project File")
        self.assertNotEqual(node.state, ThreeDNodeState.MISSING)

        serialized = node.to_dict()
        self.assertIn("environment.blend", serialized["payload"]["asset_path"])

    def test_inspector_threed_properties(self):
        """Verify NodeInspectable exposes 3D Asset Properties for asset.3d nodes."""
        node = ThreeDNodeItem(definition=NodeRegistry.get("asset.3d"))
        node.set_asset(str(self.sample_fbx))

        adapter = NodeInspectable(node)
        sections = adapter.get_inspection_sections()

        threed_section = next((s for s in sections if s.title == "3D Asset Properties"), None)
        self.assertIsNotNone(threed_section)

        file_field = next((f for f in threed_section.fields if f.key == "payload.file"), None)
        self.assertIsNotNone(file_field)
        self.assertIn("character_rig.fbx", file_field.value)

        format_field = next((f for f in threed_section.fields if f.key == "payload.format"), None)
        self.assertIsNotNone(format_field)
        self.assertEqual("FBX 3D Model", format_field.value)


if __name__ == "__main__":
    unittest.main()
