from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget

from ui.panels.dashboard_panel import DashboardPanel


class WorkspacePanel(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget()

        self.dashboard = DashboardPanel()

        self.stack.addWidget(self.dashboard)

        layout.addWidget(self.stack)

    def show_dashboard(self, project):

        self.dashboard.show_project(project)

        self.stack.setCurrentWidget(self.dashboard)