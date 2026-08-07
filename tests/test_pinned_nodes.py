import unittest
from PySide6.QtWidgets import QApplication

from ui.lab.nodes.node_registry import NodeRegistry
from ui.lab.nodes.note_node_item import NoteNodeItem
from ui.lab.nodes.image_node_item import ImageNodeItem
from ui.lab.nodes.frame_node_item import FrameNodeItem
from services.find_service import FindService

app = QApplication.instance() or QApplication([])


class MockProject:
    def __init__(self, name, is_pinned=False, description=""):
        self.name = name
        self.is_pinned = is_pinned
        self.description = description


class MockProjectService:
    def __init__(self, projects):
        self.projects = projects

    def all_projects(self):
        return self.projects


class MockContext:
    def __init__(self, projects):
        self.project_service = MockProjectService(projects)
        self.asset_service = type("MockAssetService", (), {"_ensure_index_loaded": lambda self, p: []})()


class TestPinnedNodes(unittest.TestCase):

    def test_node_pin_and_unpin_toggling(self):
        """Verify toggle_pinned() and set_pinned() update is_pinned and metadata['pinned']."""
        note = NodeRegistry.create_node("note.blank")
        image = NodeRegistry.create_node("image.reference")
        frame = NodeRegistry.create_node("frame.section")

        for node in (note, image, frame):
            self.assertFalse(node.is_pinned)
            self.assertFalse(node.metadata.get("pinned", False))

            # Pin node
            node.toggle_pinned()
            self.assertTrue(node.is_pinned)
            self.assertTrue(node.metadata.get("pinned", False))

            # Unpin node
            node.toggle_pinned()
            self.assertFalse(node.is_pinned)
            self.assertFalse(node.metadata.get("pinned", False))

    def test_node_pin_serialization(self):
        """Verify pinned state persists in .lab.json metadata dictionary block across reloads."""
        note = NodeRegistry.create_node("note.blank")
        note.set_pinned(True)

        data = note.to_dict()
        self.assertIn("metadata", data)
        self.assertIn("pinned", data["metadata"])
        self.assertTrue(data["metadata"]["pinned"])

        # Reload from dict
        reloaded = NodeRegistry.create_node("note.blank")
        reloaded.from_dict(data)
        self.assertTrue(reloaded.is_pinned)
        self.assertTrue(reloaded.metadata.get("pinned"))

    def test_find_service_pin_ranking(self):
        """Verify FindService ranks pinned items before unpinned items for search queries."""
        p_unpinned = MockProject("Alpha Project", is_pinned=False)
        p_pinned = MockProject("Alpha Draft", is_pinned=True)

        ctx = MockContext([p_unpinned, p_pinned])
        finder = FindService(ctx)

        results = finder.search("Alpha")
        proj_results = results.get("projects", [])
        self.assertEqual(len(proj_results), 2)
        # Pinned project should be ranked first
        self.assertEqual(proj_results[0]["project"].name, "Alpha Draft")
        self.assertTrue(proj_results[0]["project"].is_pinned)


if __name__ == "__main__":
    unittest.main()
