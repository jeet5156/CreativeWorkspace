import sys
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF

from ui.widgets.infinite_canvas import InfiniteCanvas
from core.canvas_clipboard import CanvasClipboard, CLIPBOARD_TYPE_HEADER, CLIPBOARD_VERSION
from core.canvas_command import CanvasCommand
from ui.lab.nodes.frame_node_item import FrameNodeItem
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.image_node_item import ImageNodeItem

app = QApplication.instance() or QApplication(sys.argv)


class TestCanvasClipboard(unittest.TestCase):
    """Comprehensive regression test suite for Creative Lab Canvas Clipboard and Commands."""

    def setUp(self):
        self.canvas = InfiniteCanvas()

    def test_clipboard_payload_structure_and_versioning(self):
        """Verify CanvasClipboard manages versioned JSON payload with creativeworkspace.clipboard header."""
        clipboard = CanvasClipboard()
        self.assertFalse(clipboard.has_content())
        self.assertEqual(clipboard.get_nodes(), [])

        # Create dummy node and copy
        n = self.canvas.add_node({"id": "n1", "type": "note.blank", "transform": {"x": 10, "y": 20, "width": 100, "height": 80}})
        clipboard.copy([n])

        self.assertTrue(clipboard.has_content())
        nodes = clipboard.get_nodes()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["id"], "n1")
        self.assertEqual(clipboard._data.get("type"), CLIPBOARD_TYPE_HEADER)
        self.assertEqual(clipboard._data.get("version"), CLIPBOARD_VERSION)

    def test_copy_single_and_multiple_nodes(self):
        """Verify copy_selection() serializes single and multiple selected nodes into canvas.clipboard."""
        n1 = self.canvas.add_node({"id": "node_a", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        n2 = self.canvas.add_node({"id": "node_b", "type": "note.blank", "transform": {"x": 300, "y": 0, "width": 200, "height": 150}})

        n1.setSelected(True)
        self.canvas.execute_command(CanvasCommand.COPY)
        self.assertEqual(len(self.canvas.clipboard.get_nodes()), 1)

        n2.setSelected(True)
        self.canvas.execute_command(CanvasCommand.COPY)
        self.assertEqual(len(self.canvas.clipboard.get_nodes()), 2)

    def test_fresh_uuid_generation_and_selection_transfer(self):
        """Verify paste generates brand-new UUIDs and transfers selection exclusively to pasted nodes."""
        n1 = self.canvas.add_node({"id": "orig_uuid_123", "type": "note.blank", "transform": {"x": 50, "y": 50, "width": 200, "height": 150}})
        n1.setSelected(True)

        self.canvas.execute_command(CanvasCommand.COPY)
        pasted = self.canvas.execute_command(CanvasCommand.PASTE)

        self.assertEqual(len(pasted), 1)
        pasted_node = pasted[0]
        self.assertNotEqual(pasted_node.id, "orig_uuid_123")

        # Selection transfers to newly pasted node
        selected = self.canvas.selected_nodes()
        self.assertEqual(selected, [pasted_node])
        self.assertFalse(n1.isSelected())

    def test_offset_paste_progression_and_reset_on_copy(self):
        """Verify paste applies (+20, +20) cumulative offsets and resets offset when a new copy occurs."""
        n1 = self.canvas.add_node({"id": "offset_n", "type": "note.blank", "transform": {"x": 100, "y": 100, "width": 200, "height": 150}})
        n1.setSelected(True)

        self.canvas.execute_command(CanvasCommand.COPY)

        p1 = self.canvas.execute_command(CanvasCommand.PASTE)[0]
        self.assertEqual(p1.pos().x(), 120.0)
        self.assertEqual(p1.pos().y(), 120.0)

        p2 = self.canvas.execute_command(CanvasCommand.PASTE)[0]
        self.assertEqual(p2.pos().x(), 140.0)
        self.assertEqual(p2.pos().y(), 140.0)

        # Re-copy resets cumulative paste offset back to +20 for first paste
        p2.setSelected(True)
        self.canvas.execute_command(CanvasCommand.COPY)

        p3 = self.canvas.execute_command(CanvasCommand.PASTE)[0]
        self.assertEqual(p3.pos().x(), 160.0)
        self.assertEqual(p3.pos().y(), 160.0)

    def test_duplicate_command_code_path(self):
        """Verify Duplicate executes Copy -> Paste as a single unified code path."""
        n1 = self.canvas.add_node({"id": "dup_node", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        n1.setSelected(True)

        duplicated = self.canvas.execute_command(CanvasCommand.DUPLICATE)
        self.assertEqual(len(duplicated), 1)

        dup_node = duplicated[0]
        self.assertNotEqual(dup_node.id, "dup_node")
        self.assertEqual(dup_node.pos().x(), 20.0)
        self.assertEqual(dup_node.pos().y(), 20.0)
        self.assertEqual(self.canvas.selected_nodes(), [dup_node])

    def test_image_node_preservation_and_delete_original(self):
        """Verify copying an Image node, deleting original, and pasting preserves relative image_path and metadata."""
        img_data = {
            "id": "img_orig",
            "type": "image",
            "transform": {"x": 100, "y": 100, "width": 300, "height": 200},
            "payload": {
                "image_path": "References/concept_art.png",
                "filename": "concept_art.png",
                "caption": "Hero Concept",
            }
        }
        orig_img = self.canvas.add_node(img_data)
        orig_img.setSelected(True)

        self.canvas.execute_command(CanvasCommand.COPY)

        # Delete original image node
        self.canvas.execute_command(CanvasCommand.DELETE)
        self.assertIsNone(self.canvas.find_node("img_orig"))

        # Paste image node
        pasted_list = self.canvas.execute_command(CanvasCommand.PASTE)
        self.assertEqual(len(pasted_list), 1)

        pasted_img = pasted_list[0]
        self.assertEqual(pasted_img.payload.get("image_path"), "References/concept_art.png")
        self.assertEqual(pasted_img.payload.get("filename"), "concept_art.png")
        self.assertEqual(pasted_img.payload.get("caption"), "Hero Concept")

    def test_note_text_content_preservation(self):
        """Verify Note text content and payload are fully preserved on paste."""
        note_data = {
            "id": "note_orig",
            "type": "note.goal",
            "transform": {"x": 0, "y": 0, "width": 200, "height": 150},
            "payload": {
                "content": "Sprint 5.1 Goal: Production Selection & Clipboard System",
                "target_date": "2026-08-15"
            }
        }
        note = self.canvas.add_node(note_data)
        note.setSelected(True)

        self.canvas.execute_command(CanvasCommand.COPY)
        pasted_note = self.canvas.execute_command(CanvasCommand.PASTE)[0]

        self.assertEqual(pasted_note.payload.get("content"), "Sprint 5.1 Goal: Production Selection & Clipboard System")
        self.assertEqual(pasted_note.payload.get("target_date"), "2026-08-15")

    def test_frame_copy_does_not_copy_unselected_contained_nodes(self):
        """Verify copying a Frame node alone copies only the Frame node, without contained nodes."""
        frame_data = {"id": "frame_only", "type": "frame.section", "transform": {"x": 0, "y": 0, "width": 500, "height": 400}, "payload": {"title": "Design Systems", "color_theme": "amber"}}
        note_data = {"id": "inner_note", "type": "note.blank", "transform": {"x": 50, "y": 50, "width": 200, "height": 150}}

        frame = self.canvas.add_node(frame_data)
        note = self.canvas.add_node(note_data)

        # Select ONLY the Frame
        frame.setSelected(True)
        note.setSelected(False)

        self.canvas.execute_command(CanvasCommand.COPY)
        pasted_nodes = self.canvas.execute_command(CanvasCommand.PASTE)

        self.assertEqual(len(pasted_nodes), 1)
        pasted_frame = pasted_nodes[0]
        self.assertIsInstance(pasted_frame, FrameNodeItem)
        self.assertEqual(pasted_frame.payload.get("title"), "Design Systems")
        self.assertEqual(pasted_frame.payload.get("color_theme"), "amber")

    def test_empty_clipboard_paste(self):
        """Verify pasting when clipboard has no content returns empty list cleanly."""
        self.canvas.clipboard.clear()
        result = self.canvas.execute_command(CanvasCommand.PASTE)
        self.assertEqual(result, [])

    def test_paste_at_mouse_cursor_position(self):
        """Verify paste near mouse cursor position when mouse_pos coordinate is supplied."""
        n1 = self.canvas.add_node({"id": "mouse_n", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        n1.setSelected(True)

        self.canvas.execute_command(CanvasCommand.COPY)
        cursor_pos = QPointF(500.0, 500.0)
        pasted = self.canvas.execute_command(CanvasCommand.PASTE, mouse_pos=cursor_pos)[0]

        # Centroid of 200x150 note at (0,0) is (100,75). Aligning centroid at (500,500) places top-left at (400, 425)
        self.assertEqual(pasted.pos().x(), 400.0)
        self.assertEqual(pasted.pos().y(), 410.0)


if __name__ == "__main__":
    unittest.main()
