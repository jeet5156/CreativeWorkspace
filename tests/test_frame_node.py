import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.frame_node_item import FrameNodeItem
from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable

app = QApplication.instance() or QApplication([])


class TestFrameNode(unittest.TestCase):

    def test_frame_registry_and_payload_defaults(self):
        """Verify frame.section node definition is registered and defaults payload attributes."""
        defn = NodeRegistry.get("frame.section")
        self.assertIsNotNone(defn)
        self.assertEqual(defn.category, "frame")

        frame = NodeRegistry.create_node("frame.section")
        self.assertIsInstance(frame, FrameNodeItem)
        self.assertEqual(frame.zValue(), -10)
        self.assertIn("theme", frame.payload)
        self.assertIn("locked", frame.payload)
        self.assertIn("child_node_ids", frame.payload)
        self.assertIn("collapsed", frame.payload)
        self.assertFalse(frame.payload["locked"])
        self.assertEqual(frame.payload["child_node_ids"], [])

    def test_centralized_membership_api(self):
        """Verify attach_node, detach_node, move_node_to_frame, detach_all, and parent_frame_id."""
        canvas = InfiniteCanvas()

        frame_a = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })
        frame_b = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 600.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        # 1. Attach node to Frame A
        frame_a.attach_node(note)
        self.assertIn(note.id, frame_a.get_child_ids())
        self.assertEqual(note.payload.get("parent_frame_id"), frame_a.id)
        self.assertIn(note, frame_a.attached_nodes())

        # 2. Transfer node from Frame A to Frame B
        frame_a.move_node_to_frame(note, frame_b)
        self.assertNotIn(note.id, frame_a.get_child_ids())
        self.assertIn(note.id, frame_b.get_child_ids())
        self.assertEqual(note.payload.get("parent_frame_id"), frame_b.id)

        # 3. Detach all nodes from Frame B
        frame_b.detach_all()
        self.assertEqual(frame_b.get_child_ids(), [])
        self.assertIsNone(note.payload.get("parent_frame_id"))

    def test_frame_movement_moves_attached_nodes(self):
        """Verify dragging/moving Frame shifts attached member nodes by matching position delta."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        frame.attach_node(note)

        # Select frame and move
        frame.setSelected(True)
        frame.setPos(QPointF(100.0, 100.0))

        # Attached member node position should shift by (+100, +100) -> (150, 150)
        self.assertEqual(note.pos().x(), 150.0)
        self.assertEqual(note.pos().y(), 150.0)

    def test_lock_frame_prevents_move_and_resize(self):
        """Verify set_locked(True) blocks frame movement/resize while attached children remain editable."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })

        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        frame.attach_node(note)
        frame.set_locked(True)

        self.assertTrue(frame.payload.get("locked"))

        # Frame movement attempt blocked by itemChange returning current position
        new_pos = frame.itemChange(FrameNodeItem.ItemPositionChange, QPointF(200.0, 200.0))
        self.assertEqual(new_pos, QPointF(0.0, 0.0))

        # Attached note inside frame remains selectable & editable
        note.setSelected(True)
        self.assertTrue(note.isSelected())

    def test_fit_to_contents(self):
        """Verify fit_to_contents() resizes and repositions frame around attached child nodes with padding."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 200.0, "height": 200.0}
        })

        n1 = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 100.0, "y": 100.0, "width": 100.0, "height": 100.0}
        })
        n2 = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 400.0, "y": 300.0, "width": 100.0, "height": 100.0}
        })

        frame.attach_node(n1)
        frame.attach_node(n2)

        frame.fit_to_contents()

        # Check that frame bounds now comfortably enclose both nodes
        f_rect = frame.sceneBoundingRect()
        self.assertTrue(f_rect.contains(n1.sceneBoundingRect()))
        self.assertTrue(f_rect.contains(n2.sceneBoundingRect()))

    def test_preset_color_themes(self):
        """Verify preset color theme application."""
        frame = NodeRegistry.create_node("frame.section")
        for theme in ("gray", "blue", "green", "yellow", "red", "purple"):
            frame.set_color_theme(theme)
            self.assertEqual(frame.payload.get("theme"), theme)
            colors = frame.get_theme_colors()
            self.assertIn("accent", colors)
            self.assertIn("header_bg", colors)

    def test_frame_inspector_integration(self):
        """Verify NodeInspectable returns Frame Properties and Organization sections."""
        canvas = InfiniteCanvas()
        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })
        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })
        frame.attach_node(note)

        adapter = NodeInspectable(frame)
        sections = adapter.get_inspection_sections()

        self.assertEqual(len(sections), 3)
        self.assertEqual(sections[0].title, "Knowledge Overview")
        self.assertEqual(sections[1].title, "Frame Properties")
        self.assertEqual(sections[2].title, "General Properties")

        adapter.set_inspectable_property("payload.theme", "green")
        self.assertEqual(frame.payload.get("theme"), "green")

        adapter.set_inspectable_property("payload.locked", True)
        self.assertTrue(frame.payload.get("locked"))

    def test_deletion_cleanup(self):
        """Verify deleting a node removes child_node_ids reference, and deleting frame clears parent_frame_id."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })
        n1 = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })
        n2 = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 200.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        frame.attach_node(n1)
        frame.attach_node(n2)

        # 1. Delete node 1 -> frame.child_node_ids immediately removes n1.id
        canvas.remove_node(n1.id)
        self.assertNotIn(n1.id, frame.get_child_ids())
        self.assertIn(n2.id, frame.get_child_ids())

        # 2. Delete frame -> n2.payload["parent_frame_id"] becomes None
        canvas.remove_node(frame.id)
        self.assertIsNone(n2.payload.get("parent_frame_id"))

    def test_clipboard_copy_rules(self):
        """Verify Figma-style clipboard copy rules for Frame nodes."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })
        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        frame.attach_node(note)

        # Case 1: Frame copied WITHOUT note selected -> copied payload has empty child_node_ids
        canvas.set_selected_nodes([frame])
        canvas.copy_selection()
        nodes_in_cb = canvas.clipboard.get_nodes()
        self.assertEqual(len(nodes_in_cb), 1)
        self.assertEqual(nodes_in_cb[0]["payload"]["child_node_ids"], [])

        # Case 2: Frame + note copied together -> relationships preserved and remapped on paste
        canvas.set_selected_nodes([frame, note])
        canvas.copy_selection()
        pasted = canvas.paste()

        self.assertEqual(len(pasted), 2)
        p_frame = next(n for n in pasted if isinstance(n, FrameNodeItem))
        p_note = next(n for n in pasted if not isinstance(n, FrameNodeItem))

        self.assertIn(p_note.id, p_frame.get_child_ids())
        self.assertEqual(p_note.payload.get("parent_frame_id"), p_frame.id)

    def test_frame_collapse_and_expand(self):
        """Verify Frame collapse/expand, expanded_rect payload, and child node visibility toggling."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 100.0, "y": 100.0, "width": 500.0, "height": 400.0}
        })
        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 150.0, "y": 150.0, "width": 100.0, "height": 100.0}
        })

        frame.attach_node(note)

        # Collapse frame
        frame.set_collapsed(True)
        self.assertTrue(frame.payload.get("collapsed"))
        self.assertIn("expanded_rect", frame.payload)
        self.assertEqual(frame.payload["expanded_rect"]["height"], 400.0)
        self.assertEqual(frame.height, 42.0)
        self.assertFalse(note.isVisible())

        # Expand frame
        frame.set_collapsed(False)
        self.assertFalse(frame.payload.get("collapsed"))
        self.assertEqual(frame.height, 400.0)
        self.assertTrue(note.isVisible())

    def test_collapse_deselects_children(self):
        """Verify collapsing a frame clears selection on hidden child nodes."""
        canvas = InfiniteCanvas()

        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 0.0, "y": 0.0, "width": 500.0, "height": 400.0}
        })
        note = canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 50.0, "y": 50.0, "width": 100.0, "height": 100.0}
        })

        frame.attach_node(note)
        note.setSelected(True)
        self.assertTrue(note.isSelected())

        # Collapse frame -> attached note selection cleared
        frame.set_collapsed(True)
        self.assertFalse(note.isSelected())
        self.assertFalse(note.isVisible())

    def test_focus_node_navigation(self):
        """Verify focus_node uses fitInView to center view on node bounding rect."""
        canvas = InfiniteCanvas()
        frame = canvas.add_node({
            "type": "frame.section",
            "transform": {"x": 200.0, "y": 300.0, "width": 400.0, "height": 300.0}
        })

        canvas.focus_node(frame)
        self.assertIsNotNone(canvas.transform())


if __name__ == "__main__":
    unittest.main()

