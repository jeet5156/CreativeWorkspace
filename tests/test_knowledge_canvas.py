import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF

from ui.widgets.infinite_canvas import InfiniteCanvas
from core.markdown_document import MarkdownDocument
from ui.widgets.markdown_renderer import MarkdownRenderer
from ui.dialogs.node_search_dialog import NodeSearchDialog

app = QApplication.instance() or QApplication([])


class TestKnowledgeCanvasFoundation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_markdown_document_parsing_and_html_generation(self):
        """Verify MarkdownDocument parses headings, checklists, code blocks, and lists."""
        doc = MarkdownDocument(
            "# Heading 1\n"
            "## Heading 2\n"
            "- [ ] Unfinished Task\n"
            "- [x] Completed Task\n"
            "- Bullet Point\n"
            "```python\n"
            "print('hello')\n"
            "```\n"
            "Inline `code` and **bold** text."
        )

        html_out = doc.to_html()
        self.assertIn("Heading 1", html_out)
        self.assertIn("Heading 2", html_out)
        self.assertTrue("[ ]" in html_out or "[ &nbsp; ]" in html_out)
        self.assertIn("[✓]", html_out)
        self.assertIn("print('hello')", html_out)
        self.assertIn("<b>bold</b>", html_out)

    def test_decoupled_markdown_renderer(self):
        """Verify MarkdownRenderer applies HTML styling to Qt QTextDocument."""
        from PySide6.QtGui import QTextDocument
        doc = QTextDocument()
        MarkdownRenderer.render_to_document("**Bold Text** and *Italic*", doc)
        self.assertIn("Bold Text", doc.toHtml())

    def test_tag_management_and_searchable_text(self):
        """Verify NodeItem tag management API, deduplication, and searchable text formatting."""
        n = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Defeat the dragon"}})
        self.assertEqual(len(n.tags), 0)

        # Add tags
        n.add_tag("Boss")
        n.add_tag("Enemy")
        n.add_tag("boss")  # Duplicate check
        self.assertEqual(len(n.tags), 2)
        self.assertIn("boss", n.tags)
        self.assertIn("enemy", n.tags)

        # Searchable text check
        st = n.get_searchable_text()
        self.assertIn("dragon", st)
        self.assertIn("boss", st)
        self.assertIn("enemy", st)

        # Remove tag
        n.remove_tag("boss")
        self.assertNotIn("boss", n.tags)

    def test_rich_knowledge_metadata_schema(self):
        """Verify NodeItem get_knowledge_metadata exposes rich AI-ready schema."""
        n = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Game Design Notes"}})
        n.add_tag("High Priority")
        n.setPos(150.0, 300.0)

        meta = n.get_knowledge_metadata()
        self.assertIn("id", meta)
        self.assertIn("type", meta)
        self.assertIn("title", meta)
        self.assertIn("content", meta)
        self.assertIn("tags", meta)
        self.assertIn("relationships", meta)
        self.assertIn("created", meta)
        self.assertIn("modified", meta)
        self.assertIn("board", meta)
        self.assertIn("frame", meta)
        self.assertIn("position", meta)

        self.assertEqual(meta["position"], [150.0, 300.0])
        self.assertIn("high priority", meta["tags"])

    def test_node_search_dialog_filtering_and_tag_query(self):
        """Verify NodeSearchDialog filters by title, content snippet, and tag:xxx syntax."""
        n1 = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Find the secret key"}})
        n1.add_tag("quest")

        n2 = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Defeat the final boss"}})
        n2.add_tag("boss")

        dlg = NodeSearchDialog([n1, n2])

        # Test general query
        dlg._filter_nodes("secret")
        self.assertEqual(len(dlg._filtered_nodes), 1)
        self.assertEqual(dlg._filtered_nodes[0].id, n1.id)

        # Test tag query syntax
        dlg._filter_nodes("tag:boss")
        self.assertEqual(len(dlg._filtered_nodes), 1)
        self.assertEqual(dlg._filtered_nodes[0].id, n2.id)


    def test_note_markdown_editing_commit_and_cancel_lifecycle(self):
        """Verify note double-click edit, Ctrl+Enter / focus-out commit, Esc cancelation, and raw source preservation."""
        n = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Initial Markdown"}})
        self.assertEqual(n.payload["content"], "Initial Markdown")

        # Double click to enter edit mode
        n.mouseDoubleClickEvent(type('DummyEvent', (), {'button': lambda *args: Qt.LeftButton, 'accept': lambda *args: None})())
        self.assertEqual(n._pre_edit_content, "Initial Markdown")

        # Edit text in item
        n.text_item.setPlainText("# Modified Heading")

        # Trigger commit
        n._on_editing_finished()
        self.assertEqual(n.payload["content"], "# Modified Heading")
        self.assertIn("Modified Heading", n.text_item.toHtml())

        # Test Esc Cancellation
        n.mouseDoubleClickEvent(type('DummyEvent', (), {'button': lambda *args: Qt.LeftButton, 'accept': lambda *args: None})())
        n.text_item.setPlainText("Cancelled Text")
        n._on_editing_canceled()
        self.assertEqual(n.payload["content"], "# Modified Heading")

    def test_semantic_relationships_and_inspector_integration(self):
        """Verify 6 core semantic relationships (Reference, Alternative, Depends On, Uses, Inspires, Decision) and ConnectorInspectable."""
        from core.inspectable_adapters import ConnectorInspectable
        from services.lab_service import LabService

        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 300, "y": 0, "width": 200, "height": 150}})

        # Create Alternative Relationship
        conn = self.canvas.connect_nodes(n1.id, n2.id, relationship_type="Alternative", label="Alternative")
        self.assertIsNotNone(conn)
        self.assertEqual(conn.relationship_type.lower(), "alternative")
        self.assertEqual(conn.label, "Alternative")

        # Modify via ConnectorInspectable
        adapter = ConnectorInspectable(conn)
        self.assertEqual(adapter.get_display_name(), "Relationship: Alternative")

        adapter.set_inspectable_property("relationship_type", "Depends On")
        self.assertEqual(conn.relationship_type.lower(), "depends_on")
        self.assertEqual(conn.label, "Depends On")
        self.assertEqual(conn.label, "Depends On")

        adapter.set_inspectable_property("notes", "Critical balance dependency")
        self.assertEqual(conn.notes, "Critical balance dependency")

        # Board Persistence Verification
        svc = LabService()
        class DummyProj:
            location = self.temp_dir

        proj = DummyProj()
        items_data = [item.to_dict() for item in self.canvas._items_map.values()]
        connectors_data = [c.to_dict() for c in self.canvas.connectors()]
        svc.save_items(proj, items_data, connectors_list=connectors_data, board_id_or_name="Main")

        loaded_board = svc.load_board(proj, "Main")
        self.assertEqual(len(loaded_board["connectors"]), 1)
        self.assertEqual(loaded_board["connectors"][0]["relationship_type"].lower(), "depends_on")
        self.assertEqual(loaded_board["connectors"][0]["notes"], "Critical balance dependency")


if __name__ == "__main__":
    unittest.main()

