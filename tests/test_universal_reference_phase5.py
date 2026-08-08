import unittest
import tempfile
import shutil
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QMimeData, QUrl

from ui.lab.drop.drop_context import DropContext
from ui.lab.drop.drop_router import DropRouter
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.generic_file_node_item import GenericFileNodeItem, GenericFileNodeState
from ui.lab.nodes.folder_node_item import FolderNodeItem, FolderNodeState
from ui.lab.nodes.archive_node_item import ArchiveNodeItem, ArchiveNodeState
from core.inspectable_adapters import NodeInspectable

app = QApplication.instance() or QApplication([])


def create_dummy_file(file_path: Path, content: bytes = b"DUMMY_DATA"):
    with open(file_path, "wb") as f:
        f.write(content)


class TestUniversalReferencePhase5(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sample_png = Path(self.temp_dir) / "art.png"
        self.sample_pdf = Path(self.temp_dir) / "doc.pdf"
        self.sample_fbx = Path(self.temp_dir) / "model.fbx"
        self.sample_zip = Path(self.temp_dir) / "assets.zip"
        self.sample_psd = Path(self.temp_dir) / "ui_design.psd"
        self.sample_dir = Path(self.temp_dir) / "Character_Assets"
        self.sample_dir.mkdir(parents=True, exist_ok=True)

        create_dummy_file(self.sample_png)
        create_dummy_file(self.sample_pdf)
        create_dummy_file(self.sample_fbx)
        create_dummy_file(self.sample_zip)
        create_dummy_file(self.sample_psd)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_routing_priority_sequence(self):
        """Verify DropRouter routes file formats according to priority sequence:
        PNG -> image.reference
        PDF -> document.pdf
        FBX -> asset.3d
        ZIP -> archive.reference
        Folder -> folder.reference
        PSD -> file.reference
        """
        router = DropRouter()

        # 1. PNG -> image.reference
        mime_png = QMimeData()
        mime_png.setUrls([QUrl.fromLocalFile(str(self.sample_png))])
        res_png = router.route_drop(DropContext(mime_png, QPointF(0, 0), project_location=self.temp_dir))
        self.assertEqual(res_png[0]["type"], "image.reference")

        # 2. PDF -> document.pdf
        mime_pdf = QMimeData()
        mime_pdf.setUrls([QUrl.fromLocalFile(str(self.sample_pdf))])
        res_pdf = router.route_drop(DropContext(mime_pdf, QPointF(0, 0), project_location=self.temp_dir))
        self.assertEqual(res_pdf[0]["type"], "document.pdf")

        # 3. FBX -> asset.3d
        mime_fbx = QMimeData()
        mime_fbx.setUrls([QUrl.fromLocalFile(str(self.sample_fbx))])
        res_fbx = router.route_drop(DropContext(mime_fbx, QPointF(0, 0), project_location=self.temp_dir))
        self.assertEqual(res_fbx[0]["type"], "asset.3d")

        # 4. ZIP -> archive.reference
        mime_zip = QMimeData()
        mime_zip.setUrls([QUrl.fromLocalFile(str(self.sample_zip))])
        res_zip = router.route_drop(DropContext(mime_zip, QPointF(0, 0), project_location=self.temp_dir))
        self.assertEqual(res_zip[0]["type"], "archive.reference")

        # 5. Folder -> folder.reference
        mime_dir = QMimeData()
        mime_dir.setUrls([QUrl.fromLocalFile(str(self.sample_dir))])
        res_dir = router.route_drop(DropContext(mime_dir, QPointF(0, 0), project_location=self.temp_dir))
        self.assertEqual(res_dir[0]["type"], "folder.reference")

        # 6. PSD -> file.reference
        mime_psd = QMimeData()
        mime_psd.setUrls([QUrl.fromLocalFile(str(self.sample_psd))])
        res_psd = router.route_drop(DropContext(mime_psd, QPointF(0, 0), project_location=self.temp_dir))
        self.assertEqual(res_psd[0]["type"], "file.reference")

    def test_generic_file_node_lifecycle(self):
        """Verify GenericFileNodeItem creation, missing detection, recovery, and relinking."""
        node = GenericFileNodeItem(definition=NodeRegistry.get("file.reference"))
        node.set_file(str(self.sample_psd))

        self.assertEqual(node.payload.get("filename"), "ui_design.psd")
        self.assertEqual(node.payload.get("extension"), ".psd")
        self.assertEqual(node.state, GenericFileNodeState.READY)

        # Missing state
        temp_psd = Path(self.temp_dir) / "temp_design.psd"
        shutil.copy(self.sample_psd, temp_psd)
        node.set_file(str(temp_psd))
        temp_psd.unlink()
        node.validate_reference(force=True)
        self.assertEqual(node.state, GenericFileNodeState.MISSING)

        # Recovery
        shutil.copy(self.sample_psd, temp_psd)
        node.validate_reference(force=True)
        self.assertEqual(node.state, GenericFileNodeState.READY)

    def test_folder_node_lifecycle(self):
        """Verify FolderNodeItem creation, missing detection, recovery, and relinking without folder enumeration."""
        node = FolderNodeItem(definition=NodeRegistry.get("folder.reference"))
        node.set_folder(str(self.sample_dir))

        self.assertEqual(node.payload.get("foldername"), "Character_Assets")
        self.assertEqual(node.state, FolderNodeState.READY)

        # Missing state
        temp_dir = Path(self.temp_dir) / "Temp_Folder"
        temp_dir.mkdir(parents=True, exist_ok=True)
        node.set_folder(str(temp_dir))
        temp_dir.rmdir()
        node.validate_reference(force=True)
        self.assertEqual(node.state, FolderNodeState.MISSING)

        # Recovery
        temp_dir.mkdir(parents=True, exist_ok=True)
        node.validate_reference(force=True)
        self.assertEqual(node.state, FolderNodeState.READY)

    def test_archive_node_lifecycle(self):
        """Verify ArchiveNodeItem creation, missing detection, recovery, and relinking without extraction."""
        node = ArchiveNodeItem(definition=NodeRegistry.get("archive.reference"))
        node.set_archive(str(self.sample_zip))

        self.assertEqual(node.payload.get("filename"), "assets.zip")
        self.assertEqual(node.payload.get("extension"), ".zip")
        self.assertEqual(node.state, ArchiveNodeState.READY)

        # Missing state
        temp_zip = Path(self.temp_dir) / "temp_pack.zip"
        shutil.copy(self.sample_zip, temp_zip)
        node.set_archive(str(temp_zip))
        temp_zip.unlink()
        node.validate_reference(force=True)
        self.assertEqual(node.state, ArchiveNodeState.MISSING)

        # Recovery
        shutil.copy(self.sample_zip, temp_zip)
        node.validate_reference(force=True)
        self.assertEqual(node.state, ArchiveNodeState.READY)

    def test_inspector_universal_sections(self):
        """Verify NodeInspectable exposes appropriate section properties for generic files, folders, and archives."""
        node_file = GenericFileNodeItem(definition=NodeRegistry.get("file.reference"))
        node_file.set_file(str(self.sample_psd))
        sec_file = NodeInspectable(node_file).get_inspection_sections()
        self.assertTrue(any(s.title == "File Reference Properties" for s in sec_file))

        node_folder = FolderNodeItem(definition=NodeRegistry.get("folder.reference"))
        node_folder.set_folder(str(self.sample_dir))
        sec_folder = NodeInspectable(node_folder).get_inspection_sections()
        self.assertTrue(any(s.title == "Folder Reference Properties" for s in sec_folder))

        node_archive = ArchiveNodeItem(definition=NodeRegistry.get("archive.reference"))
        node_archive.set_archive(str(self.sample_zip))
        sec_archive = NodeInspectable(node_archive).get_inspection_sections()
        self.assertTrue(any(s.title == "Archive Reference Properties" for s in sec_archive))


if __name__ == "__main__":
    unittest.main()
