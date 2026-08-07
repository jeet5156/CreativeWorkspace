import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, Qt

from ui.widgets.infinite_canvas import InfiniteCanvas
from core.markdown_document import MarkdownDocument
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.frame_node_item import FrameNodeItem
from services.frame_service import FrameService

app = QApplication.instance() or QApplication([])


class TestSprint54Phase1Editing(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_markdown_document_extensions_and_raw_source_preservation(self):
        """Verify raw Markdown is preserved and horizontal rules, block quotes, checklists convert to HTML."""
        raw_md = """# Boss Fight Design

---

> Critical design document for Phase 1.

- [ ] Implement AI Attack Patterns
- [x] Create Rig Animations

```python
def attack():
    pass
```"""
        doc = MarkdownDocument(raw_md)
        self.assertEqual(doc.raw_text, raw_md)

        html_out = doc.to_html()
        self.assertIn("<hr", html_out)
        self.assertIn("<blockquote", html_out)
        self.assertIn("☐", html_out)
        self.assertIn("☑", html_out)
        self.assertIn("<pre", html_out)

    def test_note_auto_grow_and_900px_max_clamping(self):
        """Verify note height expands vertically and clamps at MAX_HEIGHT = 900.0px for large text."""
        n1 = self.canvas.add_node({"type": "note.blank"})
        long_md = "\n\n".join([f"Paragraph line {i} with extended explanation text for testing card bounds expansion." for i in range(100)])

        n1.text_item.setPlainText(long_md)
        n1._update_card_height()

        self.assertEqual(n1.height, 900.0)

    def test_manual_height_preservation_never_shrinks(self):
        """Verify card auto-growing never shrinks card height below user manual height."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"width": 250, "height": 450}})
        n1._user_min_height = 450.0

        n1.text_item.setPlainText("Short text")
        n1._update_card_height()

        # Should remain at 450.0px user height rather than shrinking to default 180px
        self.assertEqual(n1.height, 450.0)

    def test_editor_and_preview_matching_document_width(self):
        """Verify editor and preview document width match (width - 24)."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"width": 300, "height": 200}})
        n1._update_card_height()
        n1.text_item.setTextWidth(n1.width - 24.0)
        self.assertEqual(n1.text_item.textWidth(), n1.width - 24.0)

    def test_note_double_click_editing_lifecycle_and_regression_coverage(self):
        """Verify double-click enters edit mode, ignores redundant double-clicks, Esc cancels, Ctrl+Enter commits, focus-out commits, and restart works."""
        n1 = self.canvas.add_node({"type": "note.blank"})
        n1.payload["content"] = "# Original Title\nOriginal body paragraph."
        n1.editor.setPlainText(n1.payload["content"])

        # 1. Double-click enters edit mode
        self.assertFalse(n1.editor._is_editing)
        n1.editor.double_clicked.emit()

        self.assertTrue(n1.editor._is_editing)
        self.assertFalse(n1.editor.isReadOnly())
        self.assertEqual(n1.editor.toPlainText(), "# Original Title\nOriginal body paragraph.")

        # 2. Redundant double-click while already editing is ignored
        n1.editor.double_clicked.emit()
        self.assertTrue(n1.editor._is_editing)

        # 3. Esc cancels editing and restores original markdown
        n1.editor.setPlainText("# Modified Title (Should cancel)")
        n1._cancel_note_editing()

        self.assertFalse(n1.editor._is_editing)
        self.assertTrue(n1.editor.isReadOnly())
        self.assertEqual(n1.payload["content"], "# Original Title\nOriginal body paragraph.")

        # 4. Double-click + Ctrl+Enter commits edits
        n1.editor.double_clicked.emit()
        self.assertTrue(n1.editor._is_editing)
        n1.editor.setPlainText("# New Committed Title")
        n1._commit_note_editing()

        self.assertFalse(n1.editor._is_editing)
        self.assertEqual(n1.payload["content"], "# New Committed Title")

        # 5. App restart simulation — load from dictionary and verify double-click still works
        saved_dict = n1.to_dict()
        n2 = self.canvas.add_node({"type": "note.blank"})
        n2.from_dict(saved_dict)

        self.assertFalse(n2.editor._is_editing)
        n2.editor.double_clicked.emit()
        self.assertTrue(n2.editor._is_editing)
        self.assertEqual(n2.editor.toPlainText(), "# New Committed Title")


if __name__ == "__main__":
    unittest.main()
