from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget

from ui.panels.dashboard_panel import DashboardPanel
from ui.panels.notes_panel import NotesPanel


class WorkspacePanel(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget()

        self.dashboard = DashboardPanel()
        self.notes = NotesPanel()

        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.notes)

        layout.addWidget(self.stack)

    def show_dashboard(self, project):

        self.dashboard.show_project(project)
        self.stack.setCurrentWidget(self.dashboard)

    def show_notes(self, project):

        self.notes.show_project(project)
        self.stack.setCurrentWidget(self.notes)