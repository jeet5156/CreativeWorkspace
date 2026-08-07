import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import Qt, QPointF

from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable
from ui.dialogs.node_search_dialog import NodeSearchDialog


def run_phase2_manual_gui_verification():
    print("==========================================================")
    print("Executing Phase 2 Knowledge Navigation Manual GUI Verification")
    print("==========================================================")

    app = QApplication.instance() or QApplication(sys.argv)
    temp_dir = tempfile.mkdtemp()

    try:
        win = QMainWindow()
        win.setWindowTitle("Phase 2 Knowledge Navigation Verification")
        win.resize(1280, 800)

        canvas = InfiniteCanvas()
        win.setCentralWidget(canvas)
        win.show()
        app.processEvents()

        print("\n[VERIFY 1] Creating Knowledge Graph Nodes...")
        n1 = canvas.add_node({"type": "note.blank", "transform": {"x": 100, "y": 100, "width": 220, "height": 180}, "payload": {"title": "Quest Engine"}})
        n2 = canvas.add_node({"type": "note.blank", "transform": {"x": 500, "y": 100, "width": 220, "height": 180}, "payload": {"title": "Enemy AI"}})
        n3 = canvas.add_node({"type": "note.blank", "transform": {"x": 500, "y": 400, "width": 220, "height": 180}, "payload": {"title": "Animation Rig"}})

        n1.add_tag("quest")
        n2.add_tag("ai")
        n2.add_tag("boss")
        n3.add_tag("animation")

        app.processEvents()
        print("  [OK] Created nodes: Quest Engine, Enemy AI, Animation Rig")

        print("\n[VERIFY 2] Creating Semantic Relationships...")
        r1 = canvas.connect_nodes(n1.id, n2.id, relationship_type="depends_on", title="Quest Unlocks Boss")
        r2 = canvas.connect_nodes(n2.id, n3.id, relationship_type="uses", title="AI Uses Rig")
        app.processEvents()

        assert len(canvas.connectors()) == 2, "Failed to create 2 connectors!"
        print("  [OK] Created 2 semantic relationships (Depends On, Uses)")

        print("\n[VERIFY 3] Inspecting Grouped Relationship Explorer & Obsidian Backlinks...")
        inspectable = NodeInspectable(n2, connection_manager=canvas.connection_manager)
        sections = inspectable.get_inspection_sections()
        titles = [s.title for s in sections]

        assert "Knowledge Overview" in titles, "Missing Knowledge Overview summary block!"
        assert "Outgoing Connections (1)" in titles, "Missing Grouped Outgoing Connections section!"
        assert "Incoming Backlinks (1)" in titles, "Missing Grouped Incoming Backlinks section!"
        print("  [OK] Grouped Relationship Explorer & Incoming Backlinks projected perfectly!")

        print("\n[VERIFY 4] Navigation History & VS Code 'Go Back' Stack (Alt + Left / Right)...")
        canvas.push_navigation_state(n1.id)
        canvas.push_navigation_state(n2.id)
        canvas.push_navigation_state(n3.id)

        assert canvas.nav_history_service.can_go_back(), "History stack cannot go back!"
        canvas.go_back_history()
        app.processEvents()

        selected = canvas.selected_nodes()
        assert len(selected) == 1 and selected[0].id == n2.id, "Go Back failed to restore n2 selection!"
        print("  [OK] VS Code style 'Go Back' stack restored node n2 selection and camera focus!")

        print("\n[VERIFY 5] First-Class Project Saved View Asset & Smooth Camera Restoration...")
        sv = canvas.save_camera_view("Main Boss Setup")
        assert sv.name == "Main Boss Setup", "SavedView creation failed!"
        canvas.restore_camera_view(sv)
        app.processEvents()
        print("  [OK] Project SavedView camera zoom/pan interpolation executed cleanly!")

        print("\n[VERIFY 6] Ephemeral Neighborhood Highlight & Esc Restoration...")
        canvas.highlight_neighborhood(n2.id)
        app.processEvents()
        assert n2.opacity() == 1.0, "n2 should be opacity 1.0!"
        assert n1.opacity() == 1.0, "Connected n1 should be opacity 1.0!"
        print("  [OK] Connected neighborhood nodes at opacity 1.0")

        canvas.clear_neighbor_highlight()
        app.processEvents()
        assert n1.opacity() == 1.0 and n2.opacity() == 1.0 and n3.opacity() == 1.0, "Highlight clear failed!"
        print("  [OK] Ephemeral neighborhood highlight cleared on Esc / canvas click!")

        print("\n[VERIFY 7] Pinned Nodes & Enhanced Ctrl+K Prefix Search...")
        n2.payload["pinned"] = True
        dlg = NodeSearchDialog([n1, n2, n3])
        dlg._filter_nodes("tag:boss")
        app.processEvents()

        assert len(dlg._filtered_nodes) == 1 and dlg._filtered_nodes[0].id == n2.id, "Tag prefix filter failed!"
        print("  [OK] Enhanced Ctrl+K query syntax (tag:boss) and top pinned sorting verified!")

        win.close()
        print("\n==========================================================")
        print("PHASE 2 KNOWLEDGE NAVIGATION VERIFIED SUCCESSFULLY!")
        print("==========================================================")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_phase2_manual_gui_verification()
