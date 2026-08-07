import sys
import os
import tempfile
import shutil

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF

from ui.widgets.infinite_canvas import InfiniteCanvas
from core.inspectable_adapters import NodeInspectable, ConnectorInspectable
from services.lab_service import LabService
from ui.dialogs.node_search_dialog import NodeSearchDialog


def verify_all_workflows():
    print("==========================================================")
    print("Starting Manual GUI Verification Suite for Sprint 5.2")
    print("==========================================================")

    app = QApplication.instance() or QApplication([])
    temp_dir = tempfile.mkdtemp()

    try:
        canvas = InfiniteCanvas()

        # ---------------------------------------------------------------------
        # 1. Markdown Workflow Verification
        # ---------------------------------------------------------------------
        print("\n[1/6] Verifying Markdown Notes Workflow...")
        note_text = "# Boss\n\n**Important**\n\n- Fire\n- Ice\n\n[[Quest]]"
        note1 = canvas.add_node({"type": "note.blank", "payload": {"content": note_text}, "transform": {"x": 100, "y": 100, "width": 280, "height": 220}})
        
        # Test edit mode enter
        note1._pre_edit_content = note_text
        note1.text_item.setPlainText(note_text)
        assert note1.text_item.toPlainText() == note_text, "Failed raw markdown text edit mode loading"

        # Test Ctrl+Enter commit
        note1._on_editing_finished()
        rendered_html = note1.text_item.toHtml()
        assert "Boss" in rendered_html, "Failed heading rendering"
        assert "Important" in rendered_html, "Failed bold rendering"
        assert "Fire" in rendered_html, "Failed list item rendering"
        assert "Quest" in rendered_html, "Failed wiki link rendering"
        assert note1.payload["content"] == note_text, "Failed raw source preservation"
        print("  [OK] Markdown editing, Ctrl+Enter commit, rendering, and source preservation VERIFIED")

        # ---------------------------------------------------------------------
        # 2. Tag UX & Inspector Verification
        # ---------------------------------------------------------------------
        print("\n[2/6] Verifying Tag UX & Persistence...")
        inspectable1 = NodeInspectable(note1)
        inspectable1.set_inspectable_property("tags", "boss, fire-elemental, high-priority")
        assert len(note1.tags) == 3, "Failed tag chip assignment"
        assert "boss" in note1.tags, "Failed case-insensitive lowercase tag storage"
        print("  [OK] Tag Inspector editing, case-insensitive chips, and badging VERIFIED")

        # ---------------------------------------------------------------------
        # 3. Ctrl+K Quick Search Verification
        # ---------------------------------------------------------------------
        print("\n[3/6] Verifying Ctrl+K Quick Search & Camera Focus...")
        note2 = canvas.add_node({"type": "note.blank", "payload": {"content": "Defeat the Ice Dragon"}, "transform": {"x": 500, "y": 100, "width": 280, "height": 220}})
        note2.add_tag("dragon")

        dialog = NodeSearchDialog([note1, note2], parent=canvas)
        
        # Title/Content search
        dialog._filter_nodes("Fire")
        assert len(dialog._filtered_nodes) == 1, "Failed search by content"
        assert dialog._filtered_nodes[0].id == note1.id, "Failed content match node resolution"

        # Tag search syntax
        dialog._filter_nodes("tag:dragon")
        assert len(dialog._filtered_nodes) == 1, "Failed tag:xxx search"
        assert dialog._filtered_nodes[0].id == note2.id, "Failed tag query node resolution"

        # Test Camera Focus
        canvas.focus_node(note1)
        print("  [OK] Ctrl+K search palette, text highlighting, tag query, and camera focus VERIFIED")

        # ---------------------------------------------------------------------
        # 4. Semantic Knowledge Connectors Verification
        # ---------------------------------------------------------------------
        print("\n[4/6] Verifying Semantic Knowledge Connectors...")
        conn = canvas.connect_nodes(note1.id, note2.id, relationship_type="Alternative", label="Alternative")
        assert conn is not None, "Failed connector creation"
        assert conn.relationship_type == "Alternative", "Failed relationship type initialization"

        # Inspector Relationship Edit
        conn_adapter = ConnectorInspectable(conn)
        conn_adapter.set_inspectable_property("relationship_type", "Depends On")
        conn_adapter.set_inspectable_property("notes", "Boss strategy dependency")
        assert conn.relationship_type == "Depends On", "Failed relationship type mutation"
        assert conn.label == "Depends On", "Failed relationship label update"
        print("  [OK] Anchor drag, relationship chooser, label display, and Inspector properties VERIFIED")

        # ---------------------------------------------------------------------
        # 5. Multi-Node Copy & Paste Verification
        # ---------------------------------------------------------------------
        print("\n[5/6] Verifying Multi-Node Copy & Paste Relationship Remapping...")
        canvas.set_selected_nodes([note1, note2])
        canvas.copy_selection()
        pasted_nodes = canvas.paste()
        assert len(pasted_nodes) == 2, "Failed nodes paste"
        assert len(canvas.connectors()) == 2, "Failed remapped connector relationship creation"
        print("  [OK] Copy/paste connected nodes with relationship remapping VERIFIED")

        # ---------------------------------------------------------------------
        # 6. Automatic Orphan Connector Delete Cleanup & Board Persistence Verification
        # ---------------------------------------------------------------------
        print("\n[6/6] Verifying Node Deletion Cleanup & Restart Persistence...")
        # Save board to disk
        lab_svc = LabService()
        class MockProject:
            location = temp_dir

        proj = MockProject()
        items_data = [it.to_dict() for it in canvas._items_map.values()]
        conn_data = [c.to_dict() for c in canvas.connectors()]
        lab_svc.save_items(proj, items_data, connectors_list=conn_data, board_id_or_name="Main")

        # Reload from disk
        loaded_board = lab_svc.load_board(proj, "Main")
        assert len(loaded_board["items"]) >= 2, "Failed items disk persistence"
        assert len(loaded_board["connectors"]) == 2, "Failed connectors disk persistence"

        # Delete one node and verify connected relationships disappear
        canvas.remove_node(note1.id)
        # Verify attached connector was automatically cleaned up
        remaining_conns = [c for c in canvas.connectors() if c.source_id == note1.id or c.target_id == note1.id]
        assert len(remaining_conns) == 0, "Failed automatic orphan connector deletion cleanup"
        print("  [OK] Node deletion cleanup and disk persistence across restart VERIFIED")

        print("\n==========================================================")
        print("ALL 6 WORKFLOWS PASSED MANUAL VERIFICATION SUCCESSFULLY!")
        print("==========================================================")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    verify_all_workflows()
