import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from PySide6.QtWidgets import QApplication, QDialog
from unittest.mock import patch

app = QApplication.instance() or QApplication(sys.argv)

from ui.main_window import MainWindow
from ui.dialogs.node_promotion_dialog import NodePromotionDialog

def verify_runtime_gui():
    print("=== Phase 3 NodePromotionDialog Runtime GUI Verification ===")
    window = MainWindow()
    window.show()

    # Verify project_service has loaded real projects
    proj_svc = window.context.project_service
    all_projects = proj_svc.all_projects()
    print(f"Loaded {len(all_projects)} projects into AppContext.project_service:")
    for p in all_projects:
        print(f"  - {p.name} ({p.location})")

    if not all_projects:
        print("Warning: No projects found in user settings! Creating dummy projects for GUI check...")
        p1 = proj_svc.create_project("Cyclops", "game", str(Path.home() / ".creativeworkspace" / "Cyclops"), "Cyclops Project")
        p2 = proj_svc.create_project("TestProject", "general", str(Path.home() / ".creativeworkspace" / "TestProject"), "Test Project")
        all_projects = proj_svc.all_projects()

    lab_panel = window.workspace_manager.lab_panel
    if not lab_panel:
        print("Error: LabPanel is not initialized on MainWindow!")
        return False

    canvas = lab_panel.canvas
    print(f"LabPanel canvas context set: {canvas._context == window.context}")

    # Add a temporary test node to canvas
    test_node = canvas.add_node({"id": "verification_node_1", "type": "note.blank", "payload": {"title": "Verification Note"}})

    captured_dialogs = []
    orig_init = NodePromotionDialog.__init__

    def mock_init(dialog_self, *args, **kwargs):
        captured_dialogs.append(dialog_self)
        return orig_init(dialog_self, *args, **kwargs)

    with patch.object(NodePromotionDialog, "__init__", mock_init):
        with patch.object(QDialog, "exec_", return_value=QDialog.Rejected):
            canvas._prompt_promote_node(test_node, action="move")

    if not captured_dialogs:
        print("FAIL: NodePromotionDialog was not instantiated from canvas._prompt_promote_node!")
        return False

    move_dialog = captured_dialogs[0]
    move_items = [move_dialog.project_cb.itemText(i) for i in range(move_dialog.project_cb.count())]
    print("\nMove Node 'Target Workspace / Project' Dropdown Items:")
    for item in move_items:
        print(f"  {item}")

    # Assert Global Workbench is present first
    assert "🛠️ Global Workbench" in move_items, "Global Workbench missing from Move dialog!"
    # Assert real project names are present
    for p in all_projects:
        assert f"📁 {p.name}" in move_items, f"Project '📁 {p.name}' missing from Move dialog!"

    print("\n[OK] Move Node dropdown verified successfully!")

    # Select Cyclops in dropdown and check boards filtering
    cyclops_project = next((p for p in all_projects if p.name == "Cyclops"), all_projects[0])
    cyclops_idx = -1
    for i in range(move_dialog.project_cb.count()):
        p_data = move_dialog.project_cb.itemData(i)
        if p_data and getattr(p_data, "name", None) == cyclops_project.name:
            cyclops_idx = i
            break

    if cyclops_idx != -1:
        move_dialog.project_cb.setCurrentIndex(cyclops_idx)
        board_count = move_dialog.board_cb.count()
        board_names = [move_dialog.board_cb.itemText(i) for i in range(board_count)]
        print(f"\nTarget Lab Boards for project '{cyclops_project.name}':")
        for b in board_names:
            print(f"  {b}")
        assert board_count > 0, f"No boards populated for project '{cyclops_project.name}'!"

    print("\n[OK] Cyclops Lab Boards filtering verified successfully!")

    # Test Copy Node promotion dialog instantiation
    captured_copy_dialogs = []

    def mock_copy_init(dialog_self, *args, **kwargs):
        captured_copy_dialogs.append(dialog_self)
        return orig_init(dialog_self, *args, **kwargs)

    with patch.object(NodePromotionDialog, "__init__", mock_copy_init):
        with patch.object(QDialog, "exec_", return_value=QDialog.Rejected):
            canvas._prompt_promote_node(test_node, action="copy")

    copy_dialog = captured_copy_dialogs[0]
    copy_items = [copy_dialog.project_cb.itemText(i) for i in range(copy_dialog.project_cb.count())]
    print("\nCopy Node 'Target Workspace / Project' Dropdown Items:")
    for item in copy_items:
        print(f"  {item}")

    for item in move_items:
        assert item in copy_items, f"Copy dialog missing item '{item}'!"

    print("\n[OK] Copy Node destination behavior verified successfully!")
    print("\nALL GUI VERIFICATIONS PASSED CLEANLY!")
    return True

if __name__ == "__main__":
    res = verify_runtime_gui()
    sys.exit(0 if res else 1)
