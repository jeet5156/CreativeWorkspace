import sys
import unittest
from PySide6.QtWidgets import QApplication, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QKeyEvent

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.panels.lab_panel import LabPanel
from ui.panels.inspector_panel import InspectorPanel
from core.app_context import AppContext
from ui.lab.nodes.node_item import NodeItem
from ui.lab.nodes.frame_node_item import FrameNodeItem
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.image_node_item import ImageNodeItem

app = QApplication.instance() or QApplication(sys.argv)


class TestCanvasSelection(unittest.TestCase):
    """Comprehensive regression test suite for Creative Lab Canvas Selection System."""

    def setUp(self):
        self.canvas = InfiniteCanvas()

    def test_qt_single_source_of_truth_selection(self):
        """Verify canvas derives selection dynamically from QGraphicsScene.selectedItems()."""
        node1_data = {"id": "node1", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}}
        node2_data = {"id": "node2", "type": "note.blank", "transform": {"x": 300, "y": 0, "width": 200, "height": 150}}
        
        n1 = self.canvas.add_node(node1_data)
        n2 = self.canvas.add_node(node2_data)

        self.assertEqual(len(self.canvas.selected_nodes()), 0)

        n1.setSelected(True)
        self.assertEqual(len(self.canvas.selected_nodes()), 1)
        self.assertIn(n1, self.canvas.selected_nodes())

        n2.setSelected(True)
        self.assertEqual(len(self.canvas.selected_nodes()), 2)
        self.assertIn(n1, self.canvas.selected_nodes())
        self.assertIn(n2, self.canvas.selected_nodes())

        n1.setSelected(False)
        self.assertEqual(len(self.canvas.selected_nodes()), 1)
        self.assertIn(n2, self.canvas.selected_nodes())

    def test_node_flags_selectable_and_movable(self):
        """Verify all created spatial node items possess ItemIsSelectable and ItemIsMovable flags."""
        node_data = {"id": "flag_node", "type": "note.blank", "transform": {"x": 50, "y": 50, "width": 200, "height": 150}}
        n = self.canvas.add_node(node_data)

        self.assertTrue(n.flags() & QGraphicsItem.ItemIsSelectable)
        self.assertTrue(n.flags() & QGraphicsItem.ItemIsMovable)

    def test_rubberband_drag_mode(self):
        """Verify InfiniteCanvas uses RubberBandDrag mode for marquee selection."""
        from PySide6.QtWidgets import QGraphicsView
        self.assertEqual(self.canvas.dragMode(), QGraphicsView.RubberBandDrag)

    def test_selection_changed_signal_emission(self):
        """Verify InfiniteCanvas emits selection_changed list whenever scene selection changes."""
        received_selections = []

        def on_selection(nodes):
            received_selections.append(list(nodes))

        self.canvas.selection_changed.connect(on_selection)

        node_data = {"id": "sig_node", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}}
        n = self.canvas.add_node(node_data)

        n.setSelected(True)
        self.assertEqual(len(received_selections), 1)
        self.assertEqual(received_selections[-1], [n])

        n.setSelected(False)
        self.assertEqual(len(received_selections), 2)
        self.assertEqual(received_selections[-1], [])

    def test_escape_key_clears_selection(self):
        """Verify pressing Escape key deselects all nodes and emits empty selection."""
        n1 = self.canvas.add_node({"id": "n1", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        n2 = self.canvas.add_node({"id": "n2", "type": "note.blank", "transform": {"x": 300, "y": 0, "width": 200, "height": 150}})

        n1.setSelected(True)
        n2.setSelected(True)
        self.assertEqual(len(self.canvas.selected_nodes()), 2)

        # Simulate Escape key press
        esc_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
        self.canvas.keyPressEvent(esc_event)

        self.assertEqual(len(self.canvas.selected_nodes()), 0)

    def test_empty_canvas_clears_selection(self):
        """Verify clear_selection() deselects all nodes."""
        n1 = self.canvas.add_node({"id": "n1", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        n1.setSelected(True)
        self.assertEqual(len(self.canvas.selected_nodes()), 1)

        self.canvas.clear_selection()
        self.assertEqual(len(self.canvas.selected_nodes()), 0)

    def test_frame_node_hit_testing(self):
        """Verify clicking a contained node inside a frame selects the contained node due to zValue hierarchy."""
        frame_data = {"id": "frame1", "type": "frame.section", "transform": {"x": 0, "y": 0, "width": 600, "height": 400}}
        note_data = {"id": "contained_note", "type": "note.blank", "transform": {"x": 100, "y": 100, "width": 200, "height": 150}}

        frame = self.canvas.add_node(frame_data)
        note = self.canvas.add_node(note_data)

        # Confirm Frame has lower zValue than Note
        self.assertLess(frame.zValue(), note.zValue())

        # Scene item lookup at Note position must evaluate Note hierarchy before Frame
        items_at_note = self.canvas._scene.items(QPointF(150, 150))
        self.assertTrue(len(items_at_note) >= 2)
        top_node = items_at_note[0].parentItem() if items_at_note[0].parentItem() else items_at_note[0]
        self.assertEqual(top_node, note)

    def test_mixed_node_selection(self):
        """Verify selecting Frame, Note, and Image items simultaneously."""
        frame_data = {"id": "f1", "type": "frame.section", "transform": {"x": 0, "y": 0, "width": 400, "height": 300}}
        note_data = {"id": "n1", "type": "note.blank", "transform": {"x": 50, "y": 50, "width": 200, "height": 150}}
        image_data = {"id": "i1", "type": "image", "transform": {"x": 500, "y": 50, "width": 200, "height": 150}}

        frame = self.canvas.add_node(frame_data)
        note = self.canvas.add_node(note_data)
        image = self.canvas.add_node(image_data)

        frame.setSelected(True)
        note.setSelected(True)
        image.setSelected(True)

        selected = self.canvas.selected_nodes()
        self.assertEqual(len(selected), 3)
        self.assertIn(frame, selected)
        self.assertIn(note, selected)
        self.assertIn(image, selected)

    def test_delete_mixed_selection(self):
        """Verify deleting mixed selection (Image, Note, Frame) removes all three and clears selection without crash."""
        frame_data = {"id": "f_del", "type": "frame.section", "transform": {"x": 0, "y": 0, "width": 400, "height": 300}}
        note_data = {"id": "n_del", "type": "note.blank", "transform": {"x": 50, "y": 50, "width": 200, "height": 150}}
        image_data = {"id": "i_del", "type": "image", "transform": {"x": 500, "y": 50, "width": 200, "height": 150}}

        frame = self.canvas.add_node(frame_data)
        note = self.canvas.add_node(note_data)
        image = self.canvas.add_node(image_data)

        frame.setSelected(True)
        note.setSelected(True)
        image.setSelected(True)

        self.canvas.delete_selected_nodes()

        self.assertEqual(len(self.canvas.selected_nodes()), 0)
        self.assertIsNone(self.canvas.find_node("f_del"))
        self.assertIsNone(self.canvas.find_node("n_del"))
        self.assertIsNone(self.canvas.find_node("i_del"))

    def test_inspector_notification_on_selection_changed(self):
        """Verify LabPanel receives selection_changed signal and updates InspectorPanel."""
        context = AppContext()
        inspector = InspectorPanel()
        inspector.set_context(context)
        context.inspector_panel = inspector
        lab_panel = LabPanel(context)

        n1 = lab_panel.canvas.add_node({"id": "insp_node1", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        n2 = lab_panel.canvas.add_node({"id": "insp_node2", "type": "note.blank", "transform": {"x": 300, "y": 0, "width": 200, "height": 150}})

        # Single selection -> shows single node inspectable
        n1.setSelected(True)
        self.assertIsNotNone(inspector._current_inspectable)
        self.assertTrue("Sticky Note" in inspector.header_title.text() or "Blank Note" in inspector.header_title.text())

        # Multi-selection -> shows MultiNodeInspectable
        n2.setSelected(True)
        self.assertIsNotNone(inspector._current_inspectable)
        self.assertEqual(inspector._current_inspectable.get_display_name(), "2 Items Selected")

        # Deselect all -> clears inspector
        lab_panel.canvas.clear_selection()
        self.assertIsNone(inspector._current_inspectable)


if __name__ == "__main__":
    unittest.main()
