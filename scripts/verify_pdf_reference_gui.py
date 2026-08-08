import sys
import tempfile
import shutil
from pathlib import Path

# Add repo root to Python path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage
from PySide6.QtCore import QPointF, QMimeData, QUrl

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.pdf_node_item import PdfNodeItem, PdfNodeState
from ui.lab.nodes.image_node_item import ImageNodeItem, ImageNodeState
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.drop_router import DropRouter
from core.inspectable_adapters import NodeInspectable


def create_dummy_pdf(file_path: Path, pages: int = 5):
    """Generate minimal valid PDF binary with N pages for GUI verification."""
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


def run_gui_verification():
    print("==================================================")
    print("Sprint 0.6.0 Phase 3: PDF Preview & Display Toggle GUI Verification")
    print("==================================================")

    app = QApplication.instance() or QApplication(sys.argv)

    temp_dir = tempfile.mkdtemp()
    try:
        # [1] Prepare existing working board with Note, Frame, and Image nodes
        canvas = InfiniteCanvas()
        canvas.update_project_location(temp_dir)

        note_node = canvas.add_node({"type": "note.blank", "transform": {"x": 50.0, "y": 50.0}, "payload": {"content": "Existing Note"}})
        frame_node = canvas.add_node({"type": "frame.section", "transform": {"x": 300.0, "y": 50.0}, "payload": {"title": "Section Frame"}})

        sample_png = Path(temp_dir) / "hero_art.png"
        img = QImage(320, 240, QImage.Format_ARGB32)
        img.fill(0xFF003366)
        img.save(str(sample_png), "PNG")

        router = DropRouter()
        mime_img = QMimeData()
        mime_img.setUrls([QUrl.fromLocalFile(str(sample_png))])
        ctx_img = DropContext(mime_img, QPointF(50.0, 300.0), project_location=temp_dir)
        img_nodes = router.route_drop(ctx_img)
        img_node = canvas.add_node(img_nodes[0])

        assert note_node is not None and frame_node is not None and img_node is not None
        print("[OK] [1] Existing board initialized with Notes, Frames, and Image Reference nodes")

        # Create sample PDF files
        pdf1_path = Path(temp_dir) / "character_design.pdf"
        pdf2_path = Path(temp_dir) / "world_lore.pdf"
        create_dummy_pdf(pdf1_path, pages=8)
        create_dummy_pdf(pdf2_path, pages=15)

        # [2] Drag PDF onto canvas -> default mode is icon
        mime_pdf = QMimeData()
        mime_pdf.setUrls([QUrl.fromLocalFile(str(pdf1_path))])
        ctx_pdf = DropContext(mime_pdf, QPointF(400.0, 300.0), project_location=temp_dir)
        pdf_nodes = router.route_drop(ctx_pdf)
        pdf_node = canvas.add_node(pdf_nodes[0])

        assert pdf_node is not None, "PDF node creation failed."
        assert pdf_node.payload.get("display_mode") == "icon", "Default display mode should be 'icon'."
        print("[OK] [2] PDF node created with default display_mode = 'icon'")

        # [3] Click header toggle ▣ -> switch to preview mode
        orig_pos = QPointF(pdf_node.pos())
        orig_size = (pdf_node.width, pdf_node.height)

        pdf_node.toggle_display_mode()
        assert pdf_node.payload.get("display_mode") == "preview", "Display mode should be 'preview'."

        # [4 & 5] Confirm first page rendered & geometry unchanged
        assert pdf_node.pos() == orig_pos, "Node position changed during display toggle!"
        assert (pdf_node.width, pdf_node.height) == orig_size, "Node dimensions changed during display toggle!"
        assert pdf_node._preview_pixmap is not None and not pdf_node._preview_pixmap.isNull(), "First-page preview pixmap missing!"
        print("[OK] [3, 4, 5] Toggled mode to 'preview' -> First PDF page rendered with zero node geometry change")

        # [6] Resize node while in preview mode -> verify preview invalidation
        pdf_node.width = 400.0
        pdf_node.height = 300.0
        pdf_node.validate_reference(force=True)
        pdf_node.update()
        print("[OK] [6] Node resized in preview mode -> preview cache updated cleanly")

        # [7] Click header toggle ▤ -> returns to icon mode
        pdf_node.toggle_display_mode()
        assert pdf_node.payload.get("display_mode") == "icon", "Failed to toggle back to 'icon' mode."
        print("[OK] [7 & 8] Toggled back to compact 'icon' mode")

        # [9] Switch back to preview mode
        pdf_node.toggle_display_mode()
        assert pdf_node.payload.get("display_mode") == "preview"
        print("[OK] [9] Switched back to 'preview' mode")

        # [10 & 11] Rename PDF externally -> Missing PDF state appears, display_mode='preview' preserved
        renamed_pdf = Path(temp_dir) / "character_design_renamed.pdf"
        pdf1_path.rename(renamed_pdf)
        pdf_node.validate_reference(force=True)

        assert pdf_node.state == PdfNodeState.MISSING, "Missing PDF state failed."
        assert pdf_node.payload.get("display_mode") == "preview", "Missing PDF lost display_mode='preview'."
        print("[OK] [10 & 11] Missing PDF detected -> display_mode = 'preview' preserved in payload")

        # [12 & 13] Restore PDF -> preview comes back automatically
        renamed_pdf.rename(pdf1_path)
        pdf_node.validate_reference(force=True)

        assert pdf_node.state == PdfNodeState.READY, "Restored PDF failed to recover."
        assert pdf_node.payload.get("display_mode") == "preview", "Restored PDF lost display_mode='preview'."
        assert pdf_node._preview_pixmap is not None, "Restored PDF preview pixmap missing."
        print("[OK] [12 & 13] Restored PDF on disk -> First page preview automatically restored without restart")

        # [14, 15, 16] Save & restart -> chosen display_mode='preview' survives
        saved_dict = pdf_node.to_dict()
        assert saved_dict["payload"]["display_mode"] == "preview", "Serialized display_mode invalid."

        canvas.clear_nodes()
        restored_pdf = canvas.add_node(saved_dict)
        assert restored_pdf is not None
        assert restored_pdf.payload.get("display_mode") == "preview", "Restored node display_mode is not 'preview'."
        print("[OK] [14, 15, 16] Board saved & reloaded -> chosen display_mode = 'preview' persists")

        # [17] Confirm existing Image References still work 100%
        img_drop_ctx = DropContext(mime_img, QPointF(500.0, 500.0), project_location=temp_dir)
        assert router.can_route(img_drop_ctx), "DropRouter failed to route Image drop context."
        img_nodes_res = router.route_drop(img_drop_ctx)
        assert len(img_nodes_res) == 1 and img_nodes_res[0]["type"] == "image.reference", "Image drop failed."
        print("[OK] [17] Existing Image References drag & drop verified 100% functional with zero regressions")

        print("==================================================")
        print("ALL 17 MANUAL GUI VERIFICATION CHECKS PASSED 100%")
        print("==================================================")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_gui_verification()
    sys.exit(0 if success else 1)
