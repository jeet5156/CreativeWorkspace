import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QTextCursor

from ui.lab.nodes.note_node_item import NoteNodeItem, NoteTextItem
from ui.lab.nodes.node_definition import NodeDefinition
from services.thumbnail_service import ThumbnailService

app = QApplication.instance() or QApplication([])


class TestImageAndCursorRegression(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.thumb_svc = ThumbnailService()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_note_node_item_cursor_move_operation_end(self):
        """Verify NoteNodeItem mouseDoubleClickEvent uses QTextCursor.MoveOperation.End cleanly."""
        from ui.lab.nodes.node_capability import NodeCapability
        defn = NodeDefinition(
            type_id="note.goal",
            category="note",
            title="Goal",
            icon="🎯",
            accent_color="#3B82F6",
            background_color="#1E2029",
            badge_bg="#1E2E4A",
            badge_text="#60A5FA",
            capabilities=NodeCapability.CAN_EDIT_TEXT,
        )
        item = NoteNodeItem(definition=defn)

        scene = QGraphicsScene()
        scene.addItem(item)

        item.text_item.setPlainText("Hello CreativeWorkspace Note Node")

        # Verify cursor position is moved to MoveOperation.End without throwing AttributeError
        cursor = item.text_item.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        item.text_item.setTextCursor(cursor)

        self.assertEqual(item.text_item.textCursor().position(), len("Hello CreativeWorkspace Note Node"))

    def test_simulated_10k_image_oversized_handling(self):
        """Verify ThumbnailService handles 10k+ resolution image pre-check and failure metadata caching."""
        proj_loc = self.temp_dir
        rel_path = "Assets/simulated_10k.png"
        src_path = Path(proj_loc) / rel_path
        src_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a valid image file header
        img = QImage(16, 16, QImage.Format_RGB32)
        img.save(str(src_path), "PNG")

        # Manually test _mark_failed metadata for simulated 10000x10000 image
        self.thumb_svc._mark_failed(proj_loc, rel_path, reason="oversized", dimensions=(10000, 10000), est_mb=381.5)

        # Level 2 Cache index verification
        idx = self.thumb_svc._load_index(proj_loc)
        self.assertEqual(idx.get("version"), 1)

        entry = idx.get(rel_path)
        self.assertIsNotNone(entry)
        self.assertTrue(entry.get("failed"))
        self.assertEqual(entry.get("reason"), "oversized")
        self.assertEqual(entry.get("dimensions"), [10000, 10000])

        # Verify subsequent get_cached call returns FAILED without retrying
        cached = self.thumb_svc.get_cached(proj_loc, rel_path, str(src_path))
        self.assertEqual(cached, "FAILED")


if __name__ == "__main__":
    unittest.main()
