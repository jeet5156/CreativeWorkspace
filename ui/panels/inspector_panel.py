from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QFormLayout,
)
from PySide6.QtCore import Qt


class InspectorPanel(QWidget):
    def __init__(self):
        super().__init__()

        self._context = None
        self._project = None

        layout = QVBoxLayout(self)

        title = QLabel("Inspector")
        title.setStyleSheet("font-weight:bold;padding:6px;font-size:14px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.filename = QLabel("-")
        self.type = QLabel("-")
        self.category = QLabel("-")
        self.size = QLabel("-")
        self.date_added = QLabel("-")
        self.path = QLabel("-")
        self.tags = QLabel("-")
        self.notes = QLabel("-")

        form.addRow("Filename:", self.filename)
        form.addRow("Type:", self.type)
        form.addRow("Category:", self.category)
        form.addRow("Size:", self.size)
        form.addRow("Date Added:", self.date_added)
        form.addRow("Path:", self.path)
        form.addRow("Tags:", self.tags)
        form.addRow("Notes:", self.notes)

        layout.addLayout(form)

        layout.addStretch()

    def set_context(self, context):
        self._context = context

    def show_asset(self, project, asset_id):
        if not self._context:
            return
        asset = self._context.asset_service.get_asset(project, asset_id)
        if not asset:
            self._clear()
            return

        self._project = project
        self.filename.setText(asset.get('filename','-'))
        self.type.setText(asset.get('friendly_type','-'))
        self.category.setText(asset.get('category','-'))
        self.size.setText(self._format_size(asset.get('size',0)))
        self.date_added.setText(self._format_date(asset.get('date_added')))
        self.path.setText(asset.get('relative_path','-'))
        self.tags.setText(', '.join(asset.get('tags',[])) or '-')
        self.notes.setText(asset.get('notes') or '-')

    def _clear(self):
        self.filename.setText('-')
        self.type.setText('-')
        self.category.setText('-')
        self.size.setText('-')
        self.date_added.setText('-')
        self.path.setText('-')
        self.tags.setText('-')
        self.notes.setText('-')

    def _format_size(self, size_bytes):
        try:
            size = int(size_bytes)
        except Exception:
            return '-' 
        for unit in ['B','KB','MB','GB','TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

    def _format_date(self, iso_str):
        if not iso_str:
            return '-'
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(iso_str)
            today = datetime.now()
            delta = today.date() - dt.date()
            days = delta.days
            if days == 0:
                return "Today"
            if days == 1:
                return "Yesterday"
            if days < 7:
                return f"{days} days ago"
            return dt.strftime("%d %b %Y")
        except Exception:
            return iso_str