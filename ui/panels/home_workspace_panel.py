from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
)
from PySide6.QtCore import Qt, Signal


class HomeWorkspacePanel(QWidget):
    """Home workspace shown when no project is selected.

    Contains sections: Continue Working, Quick Actions, Recent Activity, Project Statistics.
    Emits signals for user actions so MainWindow/NavigationService can handle orchestration.
    """

    new_project_requested = Signal()
    open_project_requested = Signal()
    open_recent_project = Signal(object)  # emits Project

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Home")
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title.setStyleSheet("font-size:20px; font-weight:bold; padding:8px;")
        layout.addWidget(title)

        # Continue Working (recent projects or tasks)
        cw_label = QLabel("Continue Working")
        cw_label.setStyleSheet("font-weight:bold;")
        layout.addWidget(cw_label)

        self.continue_list = QListWidget()
        self.continue_list.addItem("No recent work")
        layout.addWidget(self.continue_list)

        # Quick Actions
        qa_label = QLabel("Quick Actions")
        qa_label.setStyleSheet("font-weight:bold;")
        layout.addWidget(qa_label)

        qa_row = QHBoxLayout()
        self.new_project_btn = QPushButton("New Project")
        self.open_project_btn = QPushButton("Open Project")
        qa_row.addWidget(self.new_project_btn)
        qa_row.addWidget(self.open_project_btn)
        layout.addLayout(qa_row)

        # Recent Activity
        ra_label = QLabel("Recent Activity")
        ra_label.setStyleSheet("font-weight:bold; margin-top:8px;")
        layout.addWidget(ra_label)

        self.activity_list = QListWidget()
        self.activity_list.addItem("No recent activity")
        layout.addWidget(self.activity_list)

        # Project Statistics
        ps_label = QLabel("Project Statistics")
        ps_label.setStyleSheet("font-weight:bold; margin-top:8px;")
        layout.addWidget(ps_label)

        self.stats_label = QLabel("Projects: 0\nAssets: 0\nReferences: 0")
        self.stats_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.stats_label)

        layout.addStretch()

        # wire actions
        self.new_project_btn.clicked.connect(lambda: self.new_project_requested.emit())
        self.open_project_btn.clicked.connect(lambda: self.open_project_requested.emit())
        self.continue_list.itemDoubleClicked.connect(self._on_continue_double)

    def _on_continue_double(self, item):
        data = item.data(Qt.UserRole)
        if data:
            try:
                self.open_recent_project.emit(data)
            except Exception:
                pass

    def set_context(self, context):
        """Populate lists from context services where available."""
        self._context = context
        try:
            projects = context.project_service.all_projects()
            self.continue_list.clear()
            for p in projects[:10]:
                it_text = p.name
                it = None
                try:
                    from PySide6.QtWidgets import QListWidgetItem
                    it = QListWidgetItem(it_text)
                    it.setData(Qt.UserRole, p)
                    self.continue_list.addItem(it)
                except Exception:
                    self.continue_list.addItem(it_text)

            # stats: count projects and simple asset/reference counts across indices
            total_assets = 0
            total_refs = 0
            for p in projects:
                assets = context.asset_service._ensure_index_loaded(p)
                for a in assets:
                    cat = a.get('category','')
                    if cat.lower() == 'references':
                        total_refs += 1
                    else:
                        total_assets += 1
            self.stats_label.setText(f"Projects: {len(projects)}\nAssets: {total_assets}\nReferences: {total_refs}")
        except Exception:
            pass

        try:
            acts = context.activity_service.recent(10)
            self.activity_list.clear()
            for a in acts:
                ts = a.get('timestamp','')
                action = a.get('action','')
                details = a.get('details',{})
                self.activity_list.addItem(f"{ts} — {action} {details.get('label','')}")
        except Exception:
            pass
