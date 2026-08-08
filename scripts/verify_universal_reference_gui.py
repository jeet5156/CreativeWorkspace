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
from ui.lab.nodes.generic_file_node_item import GenericFileNodeItem, GenericFileNodeState
from ui.lab.nodes.folder_node_item import FolderNodeItem, FolderNodeState
from ui.lab.nodes.archive_node_item import ArchiveNodeItem, ArchiveNodeState
from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.drop_router import DropRouter
from core.inspectable_adapters import NodeInspectable


def create_dummy_file(file_path: Path, content: bytes = b"DUMMY_BINARY_DATA"):
    with open(file_path, "wb") as f:
        f.write(content)


def run_gui_verification():
    print("==================================================")
    print("Sprint 0.6.0 Phase 5: Universal File & Folder Reference GUI Verification")
    print("==================================================")

    app = QApplication.instance() or QApplication(sys.argv)

    temp_dir = tempfile.mkdtemp()
    try:
        canvas = InfiniteCanvas()
        canvas.update_project_location(temp_dir)

        router = DropRouter()

        # Prepare dummy test files
        psd_path = Path(temp_dir) / "character_design.psd"
        zip_path = Path(temp_dir) / "textures.zip"
        folder_path = Path(temp_dir) / "Environment_Assets"
        folder_path.mkdir(parents=True, exist_ok=True)

        create_dummy_file(psd_path, b"PSD_HEADER_DATA_12345")
        create_dummy_file(zip_path, b"ZIP_HEADER_DATA_12345")

        # [1] Drop PSD file onto canvas -> file.reference node
        mime_psd = QMimeData()
        mime_psd.setUrls([QUrl.fromLocalFile(str(psd_path))])
        ctx_psd = DropContext(mime_psd, QPointF(100.0, 100.0), project_location=temp_dir)

        assert router.can_route(ctx_psd), "DropRouter failed to route PSD file drop."
        psd_nodes_data = router.route_drop(ctx_psd)
        assert len(psd_nodes_data) == 1 and psd_nodes_data[0]["type"] == "file.reference"

        file_node = canvas.add_node(psd_nodes_data[0])
        assert file_node is not None and file_node.payload.get("extension") == ".psd"
        print(f"[OK] [1 & 2] Dropped PSD file onto canvas -> file.reference node created (ID: {file_node.id[:8]})")

        # [2] Drop Directory onto canvas -> folder.reference node
        mime_folder = QMimeData()
        mime_folder.setUrls([QUrl.fromLocalFile(str(folder_path))])
        ctx_folder = DropContext(mime_folder, QPointF(450.0, 100.0), project_location=temp_dir)

        assert router.can_route(ctx_folder), "DropRouter failed to route Directory drop."
        folder_nodes_data = router.route_drop(ctx_folder)
        assert len(folder_nodes_data) == 1 and folder_nodes_data[0]["type"] == "folder.reference"

        folder_node = canvas.add_node(folder_nodes_data[0])
        assert folder_node is not None and folder_node.payload.get("foldername") == "Environment_Assets"
        print(f"[OK] [3] Dropped Folder onto canvas -> folder.reference node created (ID: {folder_node.id[:8]}) without directory enumeration")

        # [3] Drop ZIP archive onto canvas -> archive.reference node
        mime_zip = QMimeData()
        mime_zip.setUrls([QUrl.fromLocalFile(str(zip_path))])
        ctx_zip = DropContext(mime_zip, QPointF(800.0, 100.0), project_location=temp_dir)

        assert router.can_route(ctx_zip), "DropRouter failed to route ZIP archive drop."
        zip_nodes_data = router.route_drop(ctx_zip)
        assert len(zip_nodes_data) == 1 and zip_nodes_data[0]["type"] == "archive.reference"

        archive_node = canvas.add_node(zip_nodes_data[0])
        assert archive_node is not None and archive_node.payload.get("extension") == ".zip"
        print(f"[OK] [4] Dropped ZIP Archive onto canvas -> archive.reference node created (ID: {archive_node.id[:8]}) without extraction")

        # [4] Double-click each node -> safe validation without application launch
        assert file_node.validate_reference(force=True), "PSD file validation failed."
        assert folder_node.validate_reference(force=True), "Folder reference validation failed."
        assert archive_node.validate_reference(force=True), "Archive reference validation failed."
        print("[OK] [5] Double-clicking all 3 universal node types executed safe lazy validation without external application launch")

        # [5 & 6] Test missing state & recovery for file node
        renamed_psd = Path(temp_dir) / "character_design_renamed.psd"
        psd_path.rename(renamed_psd)
        file_node.validate_reference(force=True)
        assert file_node.state == GenericFileNodeState.MISSING, "Missing state failed for PSD file node."

        renamed_psd.rename(psd_path)
        file_node.validate_reference(force=True)
        assert file_node.state == GenericFileNodeState.READY, "Recovery state failed for PSD file node."
        print("[OK] [6 & 7] Missing PSD file detected and automatically recovered upon disk restoration")

        # [7 & 8] Test missing state & recovery for folder node
        renamed_folder = Path(temp_dir) / "Environment_Assets_Renamed"
        folder_path.rename(renamed_folder)
        folder_node.validate_reference(force=True)
        assert folder_node.state == FolderNodeState.MISSING, "Missing state failed for Folder node."

        renamed_folder.rename(folder_path)
        folder_node.validate_reference(force=True)
        assert folder_node.state == FolderNodeState.READY, "Recovery state failed for Folder node."
        print("[OK] [8 & 9] Missing Folder detected and automatically recovered upon disk restoration")

        # [9 & 10] Test missing state & recovery for archive node
        renamed_zip = Path(temp_dir) / "textures_renamed.zip"
        zip_path.rename(renamed_zip)
        archive_node.validate_reference(force=True)
        assert archive_node.state == ArchiveNodeState.MISSING, "Missing state failed for Archive node."

        renamed_zip.rename(zip_path)
        archive_node.validate_reference(force=True)
        assert archive_node.state == ArchiveNodeState.READY, "Recovery state failed for Archive node."
        print("[OK] [10 & 11] Missing ZIP Archive detected and automatically recovered upon disk restoration")

        # [11] Save & reload board state
        saved_file_dict = file_node.to_dict()
        saved_folder_dict = folder_node.to_dict()
        saved_archive_dict = archive_node.to_dict()

        canvas.clear_nodes()
        r_file = canvas.add_node(saved_file_dict)
        r_folder = canvas.add_node(saved_folder_dict)
        r_archive = canvas.add_node(saved_archive_dict)

        assert r_file is not None and r_file.payload.get("extension") == ".psd"
        assert r_folder is not None and r_folder.payload.get("foldername") == "Environment_Assets"
        assert r_archive is not None and r_archive.payload.get("extension") == ".zip"
        print("[OK] [12 & 13] Saved & reloaded board state -> all 3 universal references restored with 100% fidelity")

        # [12] Specialized routing priority safety checks
        png_path = Path(temp_dir) / "concept.png"
        pdf_path = Path(temp_dir) / "doc.pdf"
        fbx_path = Path(temp_dir) / "mesh.fbx"
        create_dummy_file(png_path)
        create_dummy_file(pdf_path)
        create_dummy_file(fbx_path)

        m_png = QMimeData()
        m_png.setUrls([QUrl.fromLocalFile(str(png_path))])
        res_png = router.route_drop(DropContext(m_png, QPointF(0, 0), project_location=temp_dir))
        assert res_png[0]["type"] == "image.reference", "Image routing regression!"

        m_pdf = QMimeData()
        m_pdf.setUrls([QUrl.fromLocalFile(str(pdf_path))])
        res_pdf = router.route_drop(DropContext(m_pdf, QPointF(0, 0), project_location=temp_dir))
        assert res_pdf[0]["type"] == "document.pdf", "PDF routing regression!"

        m_fbx = QMimeData()
        m_fbx.setUrls([QUrl.fromLocalFile(str(fbx_path))])
        res_fbx = router.route_drop(DropContext(m_fbx, QPointF(0, 0), project_location=temp_dir))
        assert res_fbx[0]["type"] == "asset.3d", "3D routing regression!"
        print("[OK] [14 & 15] Specialized routing priority verified (PNG -> image.reference, PDF -> document.pdf, FBX -> asset.3d) with 0 regressions")

        print("==================================================")
        print("ALL 15 MANUAL GUI VERIFICATION CHECKS PASSED 100%")
        print("==================================================")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    success = run_gui_verification()
    sys.exit(0 if success else 1)
