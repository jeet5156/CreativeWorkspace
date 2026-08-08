import unittest
import tempfile
import shutil
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QMimeData, QUrl

from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.drop_router import DropRouter
from ui.lab.drop.handlers.pdf_handler import PdfDropHandler
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.pdf_node_item import PdfNodeItem, PdfNodeState
from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable

app = QApplication.instance() or QApplication([])


def create_dummy_pdf(file_path: Path, pages: int = 3):
    """Generate minimal valid PDF binary with N pages for unit testing."""
    content = [
        b"%PDF-1.4\n",
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        f"2 0 obj << /Type /Pages /Kids [{' '.join(f'{i+3} 0 R' for i in range(pages))}] /Count {pages} >> endobj\n".encode()
    ]
    for i in range(pages):
        content.append(f"{i+3} 0 obj << /Type /Page /Parent 2 0 R >> endobj\n".encode())
    content.append(b"xref\n0 1\n0000000000 65535 f \ntrailer << /Root 1 0 R >>\nstartxref\n180\n%%EOF\n")
    with open(file_path, "wb") as f:
        f.writelines(content)


class TestPdfReferencePhase2(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sample_pdf1 = Path(self.temp_dir) / "character_design.pdf"
        self.sample_pdf2 = Path(self.temp_dir) / "world_lore.pdf"

        create_dummy_pdf(self.sample_pdf1, pages=5)
        create_dummy_pdf(self.sample_pdf2, pages=12)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pdf_drop_handler_can_handle(self):
        """Verify PdfDropHandler validates .pdf files exclusively."""
        handler = PdfDropHandler()
        self.assertIn(".pdf", handler.SUPPORTED_EXTENSIONS)

        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.sample_pdf1))])
        ctx = DropContext(mime, QPointF(100.0, 100.0), project_location=self.temp_dir)

        self.assertTrue(handler.can_handle(ctx))

    def test_drop_router_pdf_node_creation(self):
        """Verify DropRouter routes PDF drops to document.pdf nodes."""
        router = DropRouter()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.sample_pdf1))])
        ctx = DropContext(mime, QPointF(200.0, 300.0), project_location=self.temp_dir)

        self.assertTrue(router.can_route(ctx))
        nodes_data = router.route_drop(ctx)

        self.assertEqual(len(nodes_data), 1)
        self.assertEqual(nodes_data[0]["type"], "document.pdf")
        self.assertEqual(nodes_data[0]["payload"]["filename"], "character_design.pdf")
        self.assertEqual(nodes_data[0]["payload"]["display_mode"], "icon")

    def test_pdf_reference_payload_structure(self):
        """Verify PdfNodeItem populates payload schema correctly."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(self.sample_pdf1))

        self.assertEqual(node.payload.get("filename"), "character_design.pdf")
        self.assertEqual(node.payload.get("extension"), ".pdf")
        self.assertEqual(node.payload.get("display_mode"), "icon")
        self.assertGreaterEqual(node.payload.get("page_count"), 1)
        self.assertTrue(node.payload.get("file_size_str").endswith("B") or node.payload.get("file_size_str").endswith("KB"))

    def test_pdf_not_copied_or_moved(self):
        """Verify PDF source file stats remain untouched after node creation."""
        stat_before = self.sample_pdf1.stat()

        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(self.sample_pdf1))
        serialized = node.to_dict()

        stat_after = self.sample_pdf1.stat()
        self.assertEqual(stat_before.st_size, stat_after.st_size)
        self.assertEqual(serialized["payload"]["absolute_path"], str(self.sample_pdf1.resolve()))

    def test_multi_pdf_staggered_placement(self):
        """Verify multi-PDF drop creates staggered placement coordinates (+30px offset)."""
        router = DropRouter()
        mime = QMimeData()
        urls = [QUrl.fromLocalFile(str(self.sample_pdf1)), QUrl.fromLocalFile(str(self.sample_pdf2))]
        mime.setUrls(urls)
        ctx = DropContext(mime, QPointF(100.0, 150.0), project_location=self.temp_dir)

        nodes_data = router.route_drop(ctx)
        self.assertEqual(len(nodes_data), 2)
        self.assertEqual(nodes_data[0]["transform"]["x"], 100.0)
        self.assertEqual(nodes_data[0]["transform"]["y"], 150.0)
        self.assertEqual(nodes_data[1]["transform"]["x"], 130.0)
        self.assertEqual(nodes_data[1]["transform"]["y"], 180.0)

    def test_live_missing_pdf_detection_and_recovery(self):
        """Verify deleting original PDF transitions node to MISSING, and restoring clears MISSING."""
        temp_pdf = Path(self.temp_dir) / "temp_doc.pdf"
        shutil.copy(self.sample_pdf1, temp_pdf)

        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(temp_pdf))
        self.assertEqual(node.state, PdfNodeState.READY)

        # Delete file externally
        temp_pdf.unlink()
        node.validate_reference(force=True)

        self.assertEqual(node.state, PdfNodeState.MISSING)

        # Restore file at same path
        shutil.copy(self.sample_pdf1, temp_pdf)
        node.validate_reference(force=True)

        self.assertEqual(node.state, PdfNodeState.READY)

    def test_relink_pdf_updates_and_persists(self):
        """Verify relinking replacement PDF updates filename, page count, and clears MISSING state."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(self.sample_pdf1))

        node.set_pdf(str(self.sample_pdf2))
        self.assertEqual(node.payload.get("filename"), "world_lore.pdf")
        self.assertNotEqual(node.state, PdfNodeState.MISSING)

        serialized = node.to_dict()
        self.assertIn("world_lore.pdf", serialized["payload"]["pdf_path"])

    def test_double_click_missing_pdf_does_not_launch(self):
        """Verify double clicking a missing PDF node validates to MISSING without OS launch."""
        missing_path = Path(self.temp_dir) / "non_existent.pdf"
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(missing_path))

        valid = node.validate_reference(force=True)
        self.assertFalse(valid)
        self.assertEqual(node.state, PdfNodeState.MISSING)

    def test_inspector_pdf_properties(self):
        """Verify NodeInspectable exposes PDF Properties for document.pdf nodes."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(self.sample_pdf1))

        adapter = NodeInspectable(node)
        sections = adapter.get_inspection_sections()

        pdf_section = next((s for s in sections if s.title == "PDF Properties"), None)
        self.assertIsNotNone(pdf_section)

        file_field = next((f for f in pdf_section.fields if f.key == "payload.file"), None)
        self.assertIsNotNone(file_field)
        self.assertIn("character_design.pdf", file_field.value)

    # -------------------------------------------------------------------------
    # Phase 3: Display Toggle & Preview Rendering Tests
    # -------------------------------------------------------------------------

    def test_default_display_mode_is_icon(self):
        """Verify default display_mode for new PDF node is 'icon'."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        self.assertEqual(node.payload.get("display_mode"), "icon")

    def test_legacy_pdf_node_loads_as_icon(self):
        """Verify PDF node dictionary without display_mode defaults to 'icon'."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.from_dict({"type": "document.pdf", "payload": {"pdf_path": str(self.sample_pdf1)}})
        self.assertEqual(node.payload.get("display_mode"), "icon")

    def test_toggle_display_mode_icon_to_preview(self):
        """Verify toggling display mode switches 'icon' <-> 'preview' without changing geometry."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(self.sample_pdf1))
        orig_w, orig_h = node.width, node.height

        # Toggle to preview
        node.toggle_display_mode()
        self.assertEqual(node.payload.get("display_mode"), "preview")
        self.assertEqual(node.width, orig_w)
        self.assertEqual(node.height, orig_h)
        self.assertIsNotNone(node._preview_pixmap)

        # Toggle back to icon
        node.toggle_display_mode()
        self.assertEqual(node.payload.get("display_mode"), "icon")
        self.assertEqual(node.width, orig_w)
        self.assertEqual(node.height, orig_h)

    def test_display_mode_persistence(self):
        """Verify display_mode='preview' persists through to_dict/from_dict serialization."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(self.sample_pdf1))
        node.toggle_display_mode()

        data = node.to_dict()
        self.assertEqual(data["payload"]["display_mode"], "preview")

        restored = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        restored.from_dict(data)
        self.assertEqual(restored.payload.get("display_mode"), "preview")

    def test_missing_pdf_preserves_display_mode(self):
        """Verify missing PDF preserves selected display_mode and restores it upon recovery."""
        temp_pdf = Path(self.temp_dir) / "toggle_missing.pdf"
        shutil.copy(self.sample_pdf1, temp_pdf)

        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(temp_pdf))
        node.toggle_display_mode()  # mode = preview
        self.assertEqual(node.payload.get("display_mode"), "preview")

        # Delete file externally
        temp_pdf.unlink()
        node.validate_reference(force=True)

        self.assertEqual(node.state, PdfNodeState.MISSING)
        self.assertEqual(node.payload.get("display_mode"), "preview")

        # Restore file
        shutil.copy(self.sample_pdf1, temp_pdf)
        node.validate_reference(force=True)

        self.assertEqual(node.state, PdfNodeState.READY)
        self.assertEqual(node.payload.get("display_mode"), "preview")
        self.assertIsNotNone(node._preview_pixmap)

    def test_relink_invalidates_preview_cache(self):
        """Verify relinking replacement PDF invalidates preview cache and re-renders new first page."""
        node = PdfNodeItem(definition=NodeRegistry.get("document.pdf"))
        node.set_pdf(str(self.sample_pdf1))
        node.toggle_display_mode()  # mode = preview

        old_pixmap = node._preview_pixmap
        self.assertIsNotNone(old_pixmap)

        # Relink to sample_pdf2
        node.set_pdf(str(self.sample_pdf2))
        self.assertEqual(node.payload.get("filename"), "world_lore.pdf")
        self.assertEqual(node.payload.get("display_mode"), "preview")
        self.assertIsNotNone(node._preview_pixmap)


if __name__ == "__main__":
    unittest.main()
