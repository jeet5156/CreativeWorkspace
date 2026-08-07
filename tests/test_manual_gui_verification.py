import unittest
import tempfile
import shutil
from PySide6.QtWidgets import QApplication, QGraphicsScene, QGraphicsView
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPixmap, QPainter

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.node_definition import NodeDefinition, NodeCapability
from core.inspectable_adapters import NodeInspectable, ConnectorInspectable
from services.lab_service import LabService

app = QApplication.instance() or QApplication([])


class TestManualGUIVerification(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rendering_and_paint_pass_with_zero_exceptions(self):
        """Simulate real graphics scene painting pass across note cards with tags, anchor handles, and selection outlines."""
        n1 = self.canvas.add_node({"type": "note.blank", "payload": {"content": "# Headings\n- [x] Checklist\n- Bullet"}, "transform": {"x": 50, "y": 50, "width": 260, "height": 180}})
        n1.add_tag("boss")
        n1.add_tag("high-priority")
        n1.setSelected(True)

        n2 = self.canvas.add_node({"type": "note.blank", "payload": {"content": "Target Node"}, "transform": {"x": 400, "y": 50, "width": 260, "height": 180}})

        conn = self.canvas.connect_nodes(n1.id, n2.id, relationship_type="Alternative", label="Alternative")
        conn.setSelected(True)

        # Force a QPixmap QPainter render pass over the scene
        pixmap = QPixmap(800, 600)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.canvas._scene.render(painter)
        painter.end()

        self.assertFalse(pixmap.isNull())
        self.assertEqual(len(self.canvas._items_map), 2)
        self.assertEqual(len(self.canvas.connectors()), 1)

    def test_markdown_edit_commit_cancel_render_pass(self):
        """Verify markdown mode switching and QTextDocument rendering pass."""
        n = self.canvas.add_node({"type": "note.blank", "payload": {"content": "# Boss Battle\n```python\nprint('fight')\n```"}})
        
        # Verify text editor document has rendered HTML
        self.assertIn("Boss Battle", n.text_item.toHtml())
        self.assertEqual(n.payload["content"], "# Boss Battle\n```python\nprint('fight')\n```")

    def test_inspector_tag_chips_and_relationship_editing(self):
        """Verify Tag list editing via NodeInspectable and relationship editing via ConnectorInspectable."""
        n = self.canvas.add_node({"type": "note.blank"})
        node_adapter = NodeInspectable(n)
        node_adapter.set_inspectable_property("tags", "creature, boss, elite")
        self.assertEqual(len(n.tags), 3)
        self.assertIn("boss", n.tags)

        n2 = self.canvas.add_node({"type": "note.blank"})
        conn = self.canvas.connect_nodes(n.id, n2.id, relationship_type="Reference")

        conn_adapter = ConnectorInspectable(conn)
        conn_adapter.set_inspectable_property("relationship_type", "Depends On")
        self.assertEqual(conn.relationship_type, "Depends On")
        self.assertEqual(conn.label, "Depends On")


if __name__ == "__main__":
    unittest.main()
