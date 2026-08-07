import unittest
import tempfile
import shutil
import time
from PySide6.QtWidgets import QApplication

from ui.widgets.infinite_canvas import InfiniteCanvas
from ui.lab.models.relationship import Relationship
from ui.lab.models.relationship_registry import RelationshipRegistry, RelationshipDefinition
from ui.lab.services.connection_manager import ConnectionManager
from core.inspectable_adapters import ConnectorInspectable
from services.lab_service import LabService

app = QApplication.instance() or QApplication([])


class TestKnowledgeRelationshipsPhase1(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.canvas = InfiniteCanvas()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_relationship_registry(self):
        """Verify RelationshipRegistry provides single source of truth for definitions, colors, and directionality."""
        defs = RelationshipRegistry.all_definitions()
        self.assertGreaterEqual(len(defs), 11)

        # Check directional vs non-directional
        self.assertFalse(RelationshipRegistry.is_directional("related_to"))
        self.assertTrue(RelationshipRegistry.is_directional("depends_on"))

        # Check color mapping
        self.assertEqual(RelationshipRegistry.get_color("depends_on"), "#EF4444")
        self.assertEqual(RelationshipRegistry.get_color("references"), "#3B82F6")

    def test_relationship_domain_model_and_serialization(self):
        """Verify pure domain Relationship data model serialization and defaults."""
        rel = Relationship(
            source_node_id="n1",
            target_node_id="n2",
            relationship_type="decision",
            title="Chosen for Production",
            notes="Using Behavior Trees because easier to debug.",
            weight=2.5,
            created_by="manual"
        )

        d = rel.to_dict()
        self.assertEqual(d["relationship_type"], "decision")
        self.assertEqual(d["title"], "Chosen for Production")
        self.assertEqual(d["weight"], 2.5)

        restored = Relationship.from_dict(d)
        self.assertEqual(restored.relationship_type, "decision")
        self.assertEqual(restored.title, "Chosen for Production")
        self.assertEqual(restored.notes, "Using Behavior Trees because easier to debug.")
        self.assertEqual(restored.weight, 2.5)

    def test_connection_manager_exclusive_crud_api(self):
        """Verify ConnectionManager owns domain state and emits explicit manager signals."""
        mgr = ConnectionManager(canvas=self.canvas)
        created_signals = []
        reversed_signals = []
        deleted_signals = []

        mgr.relationship_created.connect(lambda r: created_signals.append(r))
        mgr.relationship_reversed.connect(lambda r: reversed_signals.append(r))
        mgr.relationship_deleted.connect(lambda rid: deleted_signals.append(rid))

        rel = mgr.create_relationship(
            source_node_id="node_a",
            target_node_id="node_b",
            relationship_type="depends_on",
            notes="Test dependency rationale"
        )
        self.assertIsNotNone(rel)
        self.assertEqual(len(created_signals), 1)

        # Reverse Relationship
        mgr.reverse_relationship(rel.id)
        self.assertEqual(rel.source_node_id, "node_b")
        self.assertEqual(rel.target_node_id, "node_a")
        self.assertEqual(len(reversed_signals), 1)

        # Duplicate Relationship
        dup = mgr.duplicate_relationship(rel.id)
        self.assertIsNotNone(dup)
        self.assertNotEqual(dup.id, rel.id)

        # Delete Relationship
        rel_id = rel.id
        res = mgr.delete_relationship(rel_id)
        self.assertTrue(res)
        self.assertEqual(len(deleted_signals), 1)

    def test_node_deletion_cleanup_prevents_orphans(self):
        """Verify node deletion automatically cleans up attached relationships."""
        n1 = self.canvas.add_node({"type": "note.blank"})
        n2 = self.canvas.add_node({"type": "note.blank"})

        conn = self.canvas.connect_nodes(n1.id, n2.id, relationship_type="uses")
        self.assertEqual(len(self.canvas.connectors()), 1)

        # Delete n1
        self.canvas.remove_node(n1.id)
        self.assertEqual(len(self.canvas.connectors()), 0)

    def test_multi_node_copy_paste_remapping(self):
        """Verify copying connected nodes copies relationship and remaps node IDs."""
        n1 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 0, "y": 0, "width": 100, "height": 100}})
        n2 = self.canvas.add_node({"type": "note.blank", "transform": {"x": 200, "y": 0, "width": 100, "height": 100}})
        self.canvas.connect_nodes(n1.id, n2.id, relationship_type="alternative")

        self.canvas.set_selected_nodes([n1, n2])
        self.canvas.copy_selection()
        pasted = self.canvas.paste()
        self.assertEqual(len(pasted), 2)
        self.assertEqual(len(self.canvas.connectors()), 2)

    def test_board_persistence_versioning(self):
        """Verify saving and reloading board persistence preserves relationship attributes."""
        n1 = self.canvas.add_node({"type": "note.blank"})
        n2 = self.canvas.add_node({"type": "note.blank"})
        self.canvas.connect_nodes(
            n1.id,
            n2.id,
            relationship_type="decision",
            title="Chosen for Production",
            notes="BT decision rationale"
        )

        svc = LabService()
        class MockProj:
            location = self.temp_dir

        proj = MockProj()
        items_data = [it.to_dict() for it in self.canvas._items_map.values()]
        conn_data = [c.to_dict() for c in self.canvas.connectors()]
        svc.save_items(proj, items_data, connectors_list=conn_data, board_id_or_name="Main")

        loaded = svc.load_board(proj, "Main")
        self.assertEqual(len(loaded["connectors"]), 1)
        c0 = loaded["connectors"][0]
        self.assertEqual(c0["relationship_type"], "decision")
        self.assertEqual(c0["title"], "Chosen for Production")
        self.assertEqual(c0["notes"], "BT decision rationale")

    def test_performance_benchmark_500_nodes_1000_relationships(self):
        """Performance Benchmark: Create 500 nodes & 1000 relationships and verify O(1)/O(k) index performance."""
        nodes = []
        t0 = time.time()
        for i in range(500):
            n = self.canvas.add_node({"type": "note.blank", "transform": {"x": (i % 25) * 100, "y": (i // 25) * 100, "width": 80, "height": 80}})
            nodes.append(n)
        t_nodes = time.time() - t0

        t1 = time.time()
        for i in range(1000):
            src = nodes[i % 500]
            tgt = nodes[(i + 1) % 500]
            self.canvas.connection_manager.create_relationship(src.id, tgt.id, relationship_type="references")
        t_rels = time.time() - t1

        self.assertEqual(len(self.canvas._items_map), 500)
        self.assertEqual(len(self.canvas.connectors()), 1000)

        # Fast O(1) index query benchmark
        t2 = time.time()
        rels = self.canvas.connection_manager.get_node_relationships(nodes[0].id)
        t_query = time.time() - t2

        self.assertLess(t_query, 0.01, f"Node relationships lookup took too long: {t_query:.5f}s")
        print(f"\n  [PERF BENCHMARK] 500 Nodes created in {t_nodes:.3f}s, 1000 Relationships in {t_rels:.3f}s, O(1) index lookup in {t_query * 1000:.3f}ms")


if __name__ == "__main__":
    unittest.main()
