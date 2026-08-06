from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QFormLayout,
    QTextEdit,
)
from PySide6.QtCore import Qt
from models.client import Client, CLIENT_STATUSES, CLIENT_TYPES, CLIENT_PRIORITIES


class ClientDialog(QDialog):
    """Client creation and editing dialog. Single reused dialog class for both modes."""

    def __init__(self, parent=None, client: Optional[Client] = None):
        super().__init__(parent)
        self.client = client

        is_edit = client is not None
        self.setWindowTitle("Edit Client" if is_edit else "New Client")
        self.resize(420, 480)
        self.setModal(True)

        layout = QVBoxLayout(self)

        title_text = "Edit Client Workspace" if is_edit else "Create New Client Workspace"
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #F1F5F9;")
        layout.addWidget(title_lbl)

        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Epic Games")
        form.addRow("Client Name *:", self.name_edit)

        self.company_edit = QLineEdit()
        self.company_edit.setPlaceholderText("e.g. Epic Games Entertainment")
        form.addRow("Company Entity:", self.company_edit)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(CLIENT_PRIORITIES)
        self.priority_combo.setCurrentText("Medium")
        form.addRow("Priority:", self.priority_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItems(CLIENT_TYPES)
        form.addRow("Client Type:", self.type_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(CLIENT_STATUSES)
        self.status_combo.setCurrentText("Active")
        form.addRow("Status:", self.status_combo)

        self.industry_edit = QLineEdit()
        self.industry_edit.setPlaceholderText("e.g. Interactive Entertainment")
        form.addRow("Industry:", self.industry_edit)

        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("e.g. epicgames.com")
        form.addRow("Website:", self.website_edit)

        self.country_edit = QLineEdit()
        self.country_edit.setPlaceholderText("e.g. USA")
        form.addRow("Country:", self.country_edit)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("comma-separated tags...")
        form.addRow("Tags:", self.tags_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Client notes or description...")
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        # Pre-populate if editing an existing client
        if is_edit and client:
            self.name_edit.setText(client.name or "")
            self.company_edit.setText(client.company or "")
            self.priority_combo.setCurrentText(client.priority or "Medium")
            self.type_combo.setCurrentText(client.client_type or "Game Studio")
            self.status_combo.setCurrentText(client.status or "Active")
            self.industry_edit.setText(client.industry or "")
            self.website_edit.setText(client.website or "")
            self.country_edit.setText(client.country or "")
            self.tags_edit.setText(", ".join(client.tags) if client.tags else "")
            self.notes_edit.setPlainText(client.notes or "")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        btn_text = "Save Changes" if is_edit else "Create Client"
        self.create_btn = QPushButton(btn_text)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        self.create_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.create_btn)

        layout.addLayout(btn_layout)

    def get_client_data(self) -> dict:
        tags_raw = self.tags_edit.text().strip()
        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        return {
            "name": self.name_edit.text().strip(),
            "company": self.company_edit.text().strip(),
            "priority": self.priority_combo.currentText(),
            "client_type": self.type_combo.currentText(),
            "status": self.status_combo.currentText(),
            "industry": self.industry_edit.text().strip(),
            "website": self.website_edit.text().strip(),
            "country": self.country_edit.text().strip(),
            "tags": tags_list,
            "notes": self.notes_edit.toPlainText().strip(),
        }
