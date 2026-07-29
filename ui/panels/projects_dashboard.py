from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt


class ProjectsDashboard(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)

        title = QLabel("Projects")
        title.setStyleSheet("font-weight:bold; font-size:18px; padding:6px;")
        layout.addWidget(title)

        # Quick actions
        qa_layout = QHBoxLayout()
        self.new_btn = QPushButton("New Project")
        self.open_btn = QPushButton("Open Project")
        qa_layout.addWidget(self.new_btn)
        qa_layout.addWidget(self.open_btn)
        layout.addLayout(qa_layout)

        stats = QLabel("Project Statistics")
        stats.setStyleSheet("font-weight:bold; margin-top:8px;")
        layout.addWidget(stats)

        self.stats_label = QLabel("Loading...")
        layout.addWidget(self.stats_label)

        recent = QLabel("Recent Projects")
        recent.setStyleSheet("font-weight:bold; margin-top:8px;")
        layout.addWidget(recent)

        self.recent_list = QListWidget()
        layout.addWidget(self.recent_list)

        layout.addStretch()

    def refresh(self):
        try:
            projects = self.context.project_service.all_projects()
            self.stats_label.setText(f"Total projects: {len(projects)}")
            self.recent_list.clear()
            for p in projects[:10]:
                self.recent_list.addItem(p.name)
        except Exception:
            pass
