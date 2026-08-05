import unittest
from PySide6.QtWidgets import QApplication
from models.project import Project
from ui.widgets.project_tree_card import ProjectTreeCard

app = QApplication.instance() or QApplication([])


class TestProjectTreeCard(unittest.TestCase):

    def setUp(self):
        self.project = Project(
            name="Hero Game Project",
            project_type="game",
            location="/tmp/hero_game",
            description="A test game project",
        )
        self.card = ProjectTreeCard(self.project)

    def test_initialization(self):
        """Verify initial project title, subtitle, and fixed 38px height."""
        self.assertEqual(self.card.title_label.text(), "Hero Game Project")
        self.assertEqual(self.card.subtitle_label.text(), "Game")
        self.assertEqual(self.card.height(), ProjectTreeCard.FIXED_HEIGHT)
        self.assertFalse(self.card.is_selected())

    def test_size_hint(self):
        """Verify sizeHint returns fixed 38px height."""
        self.assertEqual(self.card.sizeHint().height(), ProjectTreeCard.FIXED_HEIGHT)
        self.card.set_expanded(True)
        self.assertEqual(self.card.sizeHint().height(), ProjectTreeCard.FIXED_HEIGHT)

    def test_selection_state(self):
        """Verify set_selected updates visual selection state."""
        self.card.set_selected(True)
        self.assertTrue(self.card.is_selected())

        self.card.set_selected(False)
        self.assertFalse(self.card.is_selected())

    def test_update_project(self):
        """Verify dynamically updating project model attributes."""
        updated_project = Project(
            name="New Audio Suite",
            project_type="audio",
            location="/tmp/audio_suite",
            description="Audio tools",
        )
        setattr(updated_project, "priority", "high")
        self.card.update_project(updated_project)

        self.assertEqual(self.card.title_label.text(), "New Audio Suite")
        self.assertEqual(self.card.subtitle_label.text(), "Audio")

    def test_clicked_signal(self):
        """Verify emitting clicked signal when card receives left click."""
        received = []
        self.card.clicked.connect(lambda p: received.append(p))

        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import Qt, QPointF
        press_event = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(10, 10), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        self.card.mousePressEvent(press_event)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].name, "Hero Game Project")


if __name__ == "__main__":
    unittest.main()
