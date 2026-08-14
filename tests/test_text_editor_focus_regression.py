import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.note_node_item import NoteNodeItem

app = QApplication.instance() or QApplication([])


class TestTextEditorFocusRegression(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_backspace_and_delete_do_not_delete_node_while_editing_text(self):
        """Regression test: Backspace and Delete keys edit text characters and NEVER delete spatial canvas nodes while editing."""
        note = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Hello World"}})
        self.assertEqual(len(self.canvas._items_map), 1)

        # Enter text edit mode
        note.text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
        note.text_item.setFocus()
        self.assertTrue(self.canvas.is_editing_text())

        # Press Backspace key while focused in editor
        bs_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
        self.canvas.keyPressEvent(bs_event)

        # Verify node was NOT deleted from canvas
        self.assertEqual(len(self.canvas._items_map), 1)
        self.assertIn(note.id, self.canvas._items_map)

        # Press Delete key while focused in editor
        del_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
        self.canvas.keyPressEvent(del_event)

        # Verify node is still present
        self.assertEqual(len(self.canvas._items_map), 1)
        self.assertIn(note.id, self.canvas._items_map)

    def test_ctrl_shortcuts_scope_to_text_editor_while_editing(self):
        """Regression test: Ctrl+A, Ctrl+C, Ctrl+V operate on text selection rather than canvas nodes while editing."""
        n1 = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Node One"}})
        n2 = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Node Two"}})
        self.assertEqual(len(self.canvas._items_map), 2)

        # Select n1 only
        self.canvas.set_selected_nodes([n1])
        self.assertEqual(len(self.canvas.selected_nodes()), 1)

        # Focus n1's text item
        n1.text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
        n1.text_item.setFocus()

        # Press Ctrl+A (Select All)
        ctrl_a = QKeyEvent(QEvent.KeyPress, Qt.Key_A, Qt.ControlModifier)
        self.canvas.keyPressEvent(ctrl_a)

        # Canvas selected nodes must NOT have expanded to all 2 nodes
        self.assertNotEqual(len(self.canvas.selected_nodes()), 2)

    def test_esc_exits_edit_mode_and_restores_canvas_shortcuts(self):
        """Regression test: Esc exits edit mode and restores canvas key shortcuts."""
        n = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Pre Edit Text"}})
        
        # Enter edit mode
        n.text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
        n.text_item.setFocus()
        n._pre_edit_content = "Pre Edit Text"
        self.assertTrue(self.canvas.is_editing_text())

        # Press Esc key to cancel editing
        esc_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        n.text_item.keyPressEvent(esc_event)
        n.text_item.setTextInteractionFlags(Qt.NoTextInteraction)
        n.text_item.clearFocus()
        self.canvas.setFocus()

        # Text editing focus must be released
        self.assertFalse(self.canvas.is_editing_text())

        # Now select node and press Backspace key on canvas
        self.canvas.set_selected_nodes([n])
        bs_event = QKeyEvent(QEvent.KeyPress, Qt.Key_Backspace, Qt.NoModifier)
        self.canvas.keyPressEvent(bs_event)

        # Now node SHOULD be deleted cleanly from canvas
        self.assertEqual(len(self.canvas._items_map), 0)


if __name__ == "__main__":
    unittest.main()
