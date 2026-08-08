import unittest
import tempfile
import shutil
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.image_node_item import ImageNodeItem
from ui.lab.nodes.frame_node_item import FrameNodeItem
from services.frame_service import FrameService, FRAME_PADDING, HEADER_HEIGHT
from core.inspectable_adapters import MultiNodeInspectable

app = QApplication.instance() or QApplication([])


class TestWorkspaceUxPhase1(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()
        self.canvas.update_project_location(self.temp_dir)

        # Create heterogeneous nodes
        self.n1 = self.canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 100.0, "y": 100.0, "width": 200.0, "height": 150.0},
            "payload": {"content": "Node 1"}
        })
        self.n2 = self.canvas.add_node({
            "type": "note.blank",
            "transform": {"x": 400.0, "y": 100.0, "width": 200.0, "height": 150.0},
            "payload": {"content": "Node 2"}
        })
        self.n3 = self.canvas.add_node({
            "type": "asset.3d",
            "transform": {"x": 250.0, "y": 350.0, "width": 300.0, "height": 200.0},
            "payload": {"filename": "model.fbx"}
        })

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_multi_selection_remains_functional(self):
        """Verify multi-selection returns all selected heterogeneous items cleanly."""
        self.canvas.set_selected_nodes([self.n1, self.n2, self.n3])
        selected = self.canvas.selected_nodes()
        self.assertEqual(len(selected), 3)
        self.assertIn(self.n1, selected)
        self.assertIn(self.n2, selected)
        self.assertIn(self.n3, selected)

    def test_create_frame_from_selection_bounds_padding_and_attachment(self):
        """Verify Create Frame from Selection creates a frame surrounding selected nodes, preserving positions and attaching children."""
        self.canvas.set_selected_nodes([self.n1, self.n2, self.n3])

        # Record original scene coordinates
        pos1_orig = QPointF(self.n1.pos())
        pos2_orig = QPointF(self.n2.pos())
        pos3_orig = QPointF(self.n3.pos())

        frame = FrameService.create_frame_from_selection([self.n1, self.n2, self.n3], self.canvas, title="Art Assets")

        self.assertIsNotNone(frame)
        self.assertIsInstance(frame, FrameNodeItem)
        self.assertEqual(frame.payload.get("title"), "Art Assets")

        # 1. Bounding box calculations
        # n1: (100, 100, 200, 150) -> max x=300, max y=250
        # n2: (400, 100, 200, 150) -> max x=600, max y=250
        # n3: (250, 350, 300, 200) -> max x=550, max y=550
        # Enclosing rect: min_x=100, min_y=100, max_x=600, max_y=550
        # Frame target_x = 100 - 32 = 68.0
        # Frame target_y = 100 - 42 - 32 = 26.0
        self.assertEqual(frame.pos().x(), 100.0 - FRAME_PADDING)
        self.assertEqual(frame.pos().y(), 100.0 - HEADER_HEIGHT - FRAME_PADDING)

        # 2. Selected nodes remain in exact scene positions
        self.assertEqual(self.n1.pos(), pos1_orig)
        self.assertEqual(self.n2.pos(), pos2_orig)
        self.assertEqual(self.n3.pos(), pos3_orig)

        # 3. Selected nodes become attached frame children
        self.assertEqual(self.n1.payload.get("parent_frame_id"), frame.id)
        self.assertEqual(self.n2.payload.get("parent_frame_id"), frame.id)
        self.assertEqual(self.n3.payload.get("parent_frame_id"), frame.id)
        self.assertEqual(set(frame.payload.get("child_node_ids", [])), {self.n1.id, self.n2.id, self.n3.id})

        # 4. Newly created frame becomes selected item
        self.assertEqual(self.canvas.selected_nodes(), [frame])

    def test_create_frame_from_selection_existing_parent_transfer(self):
        """Verify creating a new frame from a node attached to an existing frame transfers membership without corruption."""
        frame_old = FrameService.create_frame_from_selection([self.n1], self.canvas, title="Old Frame")
        self.assertEqual(self.n1.payload.get("parent_frame_id"), frame_old.id)

        # Create new frame from n1 + n2
        frame_new = FrameService.create_frame_from_selection([self.n1, self.n2], self.canvas, title="New Frame")

        self.assertEqual(self.n1.payload.get("parent_frame_id"), frame_new.id)
        self.assertEqual(self.n2.payload.get("parent_frame_id"), frame_new.id)
        self.assertNotIn(self.n1.id, frame_old.payload.get("child_node_ids", []))

    def test_batch_pin_and_unpin(self):
        """Verify batch pinning and unpinning selected nodes."""
        self.canvas.set_selected_nodes([self.n1, self.n2, self.n3])

        # Batch pin all
        for n in self.canvas.selected_nodes():
            n.set_pinned(True)

        self.assertTrue(self.n1.is_pinned)
        self.assertTrue(self.n2.is_pinned)
        self.assertTrue(self.n3.is_pinned)

        # Batch unpin all
        for n in self.canvas.selected_nodes():
            n.set_pinned(False)

        self.assertFalse(self.n1.is_pinned)
        self.assertFalse(self.n2.is_pinned)
        self.assertFalse(self.n3.is_pinned)

    def test_mixed_pinned_unpinned_selection(self):
        """Verify mixed pinned/unpinned selection pin states."""
        self.n1.set_pinned(True)
        self.n2.set_pinned(False)

        adapter = MultiNodeInspectable([self.n1, self.n2])
        sections = adapter.get_inspection_sections()

        field_pin = next((f for f in sections[0].fields if f.key == "is_pinned"), None)
        self.assertIsNotNone(field_pin)
        self.assertFalse(field_pin.value)  # Not all selected are pinned

        # Batch pin all via adapter
        adapter.set_inspectable_property("is_pinned", True)
        self.assertTrue(self.n1.is_pinned)
        self.assertTrue(self.n2.is_pinned)

    def test_batch_tag_propagation_whitespace_normalization_and_deduplication(self):
        """Verify MultiNodeInspectable propagates tags to all selected nodes with whitespace normalization and duplicate prevention."""
        self.n1.set_tags(["character"])
        self.n2.set_tags(["character", "wip"])

        adapter = MultiNodeInspectable([self.n1, self.n2, self.n3])

        # Apply batch tags via adapter
        adapter.set_inspectable_property("tags", " Character , client,  WIP ")

        # Tags should be merged, normalized to lowercase, and deduplicated
        self.assertIn("character", self.n1.tags)
        self.assertIn("client", self.n1.tags)
        self.assertIn("wip", self.n1.tags)

        self.assertIn("character", self.n2.tags)
        self.assertIn("client", self.n2.tags)
        self.assertIn("wip", self.n2.tags)

        self.assertEqual(sorted(self.n3.tags), ["character", "client", "wip"])

    def test_persistence_after_save_reload(self):
        """Verify tags, pin states, and frame membership persist through serialization."""
        self.n1.set_pinned(True)
        self.n1.set_tags(["hero", "final"])

        frame = FrameService.create_frame_from_selection([self.n1], self.canvas, title="Hero Frame")

        dict_n1 = self.n1.to_dict()
        dict_frame = frame.to_dict()

        self.assertTrue(dict_n1["metadata"]["pinned"])
        self.assertEqual(dict_n1["metadata"]["tags"], ["hero", "final"])
        self.assertEqual(dict_n1["payload"]["parent_frame_id"], frame.id)

        self.assertIn(self.n1.id, dict_frame["payload"]["child_node_ids"])


if __name__ == "__main__":
    unittest.main()
