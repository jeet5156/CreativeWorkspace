import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer

from ui.main_window import MainWindow
from core.app_context import AppContext
from services.project_service import ProjectService
from services.lab_service import LabService
from ui.panels.lab_panel import LabPanel
from core.canvas_command import CanvasCommand

app = QApplication.instance() or QApplication(sys.argv)


class TestLabPersistence(unittest.TestCase):
    """Comprehensive regression test suite for Lab Canvas Persistence, Flush-Before-Clear, and Guards."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pending_timer_flush_before_clear_nodes(self):
        """Verify pending debounced _item_save_timer is flushed synchronously before clearing nodes on show_project."""
        context = AppContext()
        ps = ProjectService()
        lab_svc = LabService(project_service=ps)
        context.project_service = ps
        context.lab_service = lab_svc

        proj_dir = str(Path(self.temp_dir) / "FlushProj")
        project = ps.create_project(name="FlushProj", project_type="game", location=proj_dir, description="Test")

        lab_panel = LabPanel(context)
        lab_panel.show_project(project, board_name="Main")

        n = lab_panel.canvas.add_node({"id": "pending_n1", "type": "note.blank", "transform": {"x": 10, "y": 10, "width": 200, "height": 150}})
        lab_panel._on_node_changed()
        self.assertTrue(lab_panel._item_save_timer.isActive())

        # Immediately call show_project while timer is active
        lab_panel.show_project(project, board_name="Main")

        # Allow Qt event loop to process any pending timers
        loop = QEventLoop()
        QTimer.singleShot(600, loop.quit)
        loop.exec()

        board_path = lab_svc.get_board_path(project, "Main")
        self.assertTrue(board_path.exists())

        with open(board_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        items_on_disk = data.get("items", [])
        self.assertEqual(len(items_on_disk), 1)
        self.assertEqual(items_on_disk[0]["id"], "pending_n1")

    def test_lab_persistence_across_app_restart_disk_verification(self):
        """Verify actual .lab.json file on disk contains nodes after close and loads correctly on restart."""
        w1 = MainWindow()
        proj_dir = str(Path(self.temp_dir) / "RestartProj")
        p1 = w1.context.project_service.create_project(name="RestartProj", project_type="game", location=proj_dir, description="Desc")
        w1.register_and_open_project(p1)

        w1.workspace_manager.show_module("lab")
        lab1 = w1.workspace_manager.lab_panel

        n1 = lab1.canvas.add_node({"id": "persist_1", "type": "note.blank", "transform": {"x": 10, "y": 10, "width": 200, "height": 150}, "payload": {"content": "Node 1"}})
        n2 = lab1.canvas.add_node({"id": "persist_2", "type": "frame.section", "transform": {"x": 0, "y": 0, "width": 400, "height": 300}, "payload": {"title": "Frame 2"}})
        n3 = lab1.canvas.add_node({"id": "persist_3", "type": "image", "transform": {"x": 500, "y": 0, "width": 300, "height": 200}, "payload": {"image_path": "References/art.png"}})

        # Flush pending saves and close window
        lab1.flush_pending_saves()
        w1.close()

        # LITERALLY open and inspect .lab.json on disk
        board_path = w1.context.lab_service.get_board_path(p1)
        self.assertTrue(board_path.exists())

        with open(board_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)

        disk_items = disk_data.get("items", [])
        self.assertEqual(len(disk_items), 3)

        ids_on_disk = {it["id"] for it in disk_items}
        self.assertEqual(ids_on_disk, {"persist_1", "persist_2", "persist_3"})

        # Simulate App Restart
        w2 = MainWindow()
        p2 = [p for p in w2.context.project_service.all_projects() if p.name == "RestartProj"][0]
        w2.project_selected(p2, "lab")
        w2.workspace_manager.show_module("lab")
        lab2 = w2.workspace_manager.lab_panel

        self.assertEqual(len(lab2.canvas._items_map), 3)
        self.assertIsNotNone(lab2.canvas.find_node("persist_1"))
        self.assertIsNotNone(lab2.canvas.find_node("persist_2"))
        self.assertIsNotNone(lab2.canvas.find_node("persist_3"))
        w2.close()

    def test_race_condition_create20_duplicate5_switch_project(self):
        """Race condition test: Create 20 nodes, Duplicate 5, switch project in <500ms, return, verify all 25 exist."""
        w = MainWindow()
        p1_dir = str(Path(self.temp_dir) / "RaceP1")
        p2_dir = str(Path(self.temp_dir) / "RaceP2")

        p1 = w.context.project_service.create_project(name="RaceP1", project_type="game", location=p1_dir, description="P1")
        p2 = w.context.project_service.create_project(name="RaceP2", project_type="game", location=p2_dir, description="P2")

        w.register_and_open_project(p1)
        w.workspace_manager.show_module("lab")
        lab = w.workspace_manager.lab_panel

        # Create 20 nodes
        created_nodes = []
        for i in range(20):
            n = lab.canvas.add_node({"id": f"race_n_{i}", "type": "note.blank", "transform": {"x": i * 30, "y": i * 20, "width": 100, "height": 80}})
            created_nodes.append(n)

        # Select 5 nodes and duplicate
        lab.canvas.set_selected_nodes(created_nodes[:5])
        lab.canvas.execute_command(CanvasCommand.DUPLICATE)

        self.assertEqual(len(lab.canvas._items_map), 25)

        # Immediately switch to P2 in <500ms (without waiting for timer)
        w.register_and_open_project(p2)
        w.workspace_manager.show_module("lab")

        # Return to P1
        w.project_selected(p1, "lab")
        w.workspace_manager.show_module("lab")

        board_path_p1 = w.context.lab_service.get_board_path(p1)
        self.assertTrue(board_path_p1.exists())

        with open(board_path_p1, "r", encoding="utf-8") as f:
            p1_data = json.load(f)

        self.assertEqual(len(p1_data.get("items", [])), 25)
        self.assertEqual(len(w.workspace_manager.lab_panel.canvas._items_map), 25)
        w.close()

    def test_loading_and_switching_guards_prevent_empty_overwrites(self):
        """Verify _is_loading and _is_switching_board flags prevent accidental empty overwrites."""
        context = AppContext()
        ps = ProjectService()
        lab_svc = LabService(project_service=ps)
        context.project_service = ps
        context.lab_service = lab_svc

        proj_dir = str(Path(self.temp_dir) / "GuardProj")
        project = ps.create_project(name="GuardProj", project_type="game", location=proj_dir, description="Test")

        lab_panel = LabPanel(context)
        lab_panel.show_project(project, board_name="Main")

        # Add node and persist
        lab_panel.canvas.add_node({"id": "g1", "type": "note.blank", "transform": {"x": 0, "y": 0, "width": 200, "height": 150}})
        lab_panel._persist_items()

        # Set loading guard
        lab_panel._is_loading = True
        lab_panel.canvas.clear_nodes()

        # Attempting to persist items while loading MUST be rejected by guard
        lab_panel._persist_items()

        board_path = lab_svc.get_board_path(project, "Main")
        with open(board_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # File on disk MUST remain 1 item, NOT overwritten to 0
        self.assertEqual(len(data.get("items", [])), 1)


if __name__ == "__main__":
    unittest.main()
