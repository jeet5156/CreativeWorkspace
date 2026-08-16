"""AI Configuration & Provider Settings Widget for CreativeWorkspace.

Allows users to:
1. Enable / Disable AI capabilities globally.
2. Select and configure AI providers (OpenAI, Gemini, Claude, Local / OpenAI-Compatible, Mock).
3. Securely set API keys with password masking and show/hide toggle.
4. Customize endpoints and model overrides with dynamic model discovery.
5. Discover current Google Gemini models dynamically via Google's Models API.
6. Perform non-blocking asynchronous connection tests.
7. Display real-time AI readiness status (Ready, Not Configured, Disabled, Error).
"""

import time
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QFrame,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
)

from models.ai import AIRequest, AIResponse
from services.ai_service import AIService, AIWorker, ModelDiscoveryWorker


PROVIDER_MODEL_SUGGESTIONS: Dict[str, List[str]] = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o3-mini"],
    "gemini": [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
    "claude": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
    "local": ["llama3", "mistral", "qwen2.5", "deepseek-r1", "phi3"],
    "mock": ["mock-model-v1"],
}

PROVIDER_DISPLAY_NAMES: Dict[str, str] = {
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "claude": "Anthropic Claude",
    "local": "Local / OpenAI-Compatible (Ollama, LM Studio)",
    "mock": "Mock Provider (Testing)",
}


class AISettingsWidget(QWidget):
    """Integrated Settings panel for configuring AI providers and testing connections."""

    configuration_changed = Signal()

    def __init__(self, ai_service: Optional[AIService] = None, parent=None):
        super().__init__(parent)
        self.ai_service = ai_service
        self._active_test_worker: Optional[AIWorker] = None
        self._active_discovery_worker: Optional[ModelDiscoveryWorker] = None
        self._last_test_error: Optional[str] = None
        self._last_test_success: bool = False
        self._is_populating = False

        self._setup_ui()
        self.reload_from_service()

        if self.ai_service:
            try:
                self.ai_service.ai_status_changed.connect(self._on_service_status_changed)
            except Exception:
                pass

    def set_ai_service(self, ai_service: AIService):
        self.ai_service = ai_service
        self.reload_from_service()

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 1. Header with Title and Live Status Badge
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title_lbl = QLabel("✨ AI & Machine Intelligence")
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title_lbl.setStyleSheet("color: #F1F5F9;")
        header_row.addWidget(title_lbl)

        header_row.addStretch()

        status_prefix = QLabel("AI Status:")
        status_prefix.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")
        header_row.addWidget(status_prefix)

        self.status_badge = QLabel("🟡 Not Configured")
        self.status_badge.setStyleSheet("""
            background-color: #282C40;
            color: #CBD5E1;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        """)
        header_row.addWidget(self.status_badge)

        layout.addLayout(header_row)

        desc_lbl = QLabel(
            "Configure generative AI providers for note summarization, tag suggestions, "
            "and creative workflows. API keys are stored locally and never synced to projects."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(desc_lbl)

        # 2. Main Config Card
        self.card_frame = QFrame()
        self.card_frame.setStyleSheet("""
            QFrame#ai_card {
                background-color: #141620;
                border: 1px solid #282C40;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.card_frame.setObjectName("ai_card")
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(12)

        # Enable AI Toggle Row
        self.enable_checkbox = QCheckBox("Enable AI Features")
        self.enable_checkbox.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.enable_checkbox.setCursor(QCursor(Qt.PointingHandCursor))
        self.enable_checkbox.setStyleSheet("""
            QCheckBox {
                color: #F1F5F9;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #3E4564;
                background-color: #1E2235;
            }
            QCheckBox::indicator:checked {
                background-color: #6366F1;
                border-color: #818CF8;
            }
        """)
        self.enable_checkbox.toggled.connect(self._on_enable_toggled)
        card_layout.addWidget(self.enable_checkbox)

        # Provider Form Container
        self.form_container = QWidget()
        form_layout = QFormLayout(self.form_container)
        form_layout.setContentsMargins(0, 8, 0, 0)
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignLeft)

        # Provider Dropdown
        self.provider_combo = QComboBox()
        self.provider_combo.setStyleSheet(self._input_style())
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form_layout.addRow("Active Provider:", self.provider_combo)

        # Model Selector / Edit with Refresh Models Button
        self.model_row_widget = QWidget()
        model_row_layout = QVBoxLayout(self.model_row_widget)
        model_row_layout.setContentsMargins(0, 0, 0, 0)
        model_row_layout.setSpacing(4)

        model_controls_row = QHBoxLayout()
        model_controls_row.setContentsMargins(0, 0, 0, 0)
        model_controls_row.setSpacing(6)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setStyleSheet(self._input_style())
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_controls_row.addWidget(self.model_combo, 1)

        self.btn_refresh_models = QPushButton("🔄 Refresh Models")
        self.btn_refresh_models.setToolTip("Query Google's Models API for currently available models")
        self.btn_refresh_models.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_refresh_models.setStyleSheet("""
            QPushButton {
                background-color: #1E2235;
                color: #38BDF8;
                border: 1px solid #283556;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #7DD3FC;
                border-color: #38BDF8;
            }
            QPushButton:disabled {
                background-color: #161822;
                color: #475569;
                border-color: #232738;
            }
        """)
        self.btn_refresh_models.clicked.connect(self.refresh_models)
        model_controls_row.addWidget(self.btn_refresh_models)

        model_row_layout.addLayout(model_controls_row)

        # Discovery status & spinner indicator
        refresh_feedback_row = QHBoxLayout()
        refresh_feedback_row.setContentsMargins(0, 0, 0, 0)
        refresh_feedback_row.setSpacing(6)

        self.refresh_spinner = QProgressBar()
        self.refresh_spinner.setRange(0, 0)
        self.refresh_spinner.setFixedHeight(4)
        self.refresh_spinner.setStyleSheet("""
            QProgressBar {
                background-color: #1E2235;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #38BDF8;
            }
        """)
        self.refresh_spinner.setVisible(False)
        refresh_feedback_row.addWidget(self.refresh_spinner, 1)

        self.refresh_status_label = QLabel("")
        self.refresh_status_label.setWordWrap(True)
        self.refresh_status_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.refresh_status_label.setVisible(False)
        refresh_feedback_row.addWidget(self.refresh_status_label)

        model_row_layout.addLayout(refresh_feedback_row)

        form_layout.addRow("Model:", self.model_row_widget)

        # API Key Field with Show/Hide Toggle
        self.api_key_widget = QWidget()
        key_layout = QHBoxLayout(self.api_key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(6)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Enter API Key (e.g. sk-...)")
        self.api_key_edit.setStyleSheet(self._input_style())
        self.api_key_edit.textChanged.connect(self._on_api_key_changed)
        key_layout.addWidget(self.api_key_edit, 1)

        self.btn_toggle_key_vis = QPushButton("👁️")
        self.btn_toggle_key_vis.setFixedSize(32, 28)
        self.btn_toggle_key_vis.setToolTip("Show / Hide API Key")
        self.btn_toggle_key_vis.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_toggle_key_vis.setStyleSheet("""
            QPushButton {
                background-color: #1E2235;
                border: 1px solid #2E3650;
                border-radius: 4px;
                color: #CBD5E1;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #283556;
                color: #FFFFFF;
            }
        """)
        self.btn_toggle_key_vis.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.btn_toggle_key_vis)

        self.api_key_label = QLabel("API Key:")
        form_layout.addRow(self.api_key_label, self.api_key_widget)

        # Endpoint Field (for Local / Custom)
        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.setPlaceholderText("http://localhost:11434/v1")
        self.endpoint_edit.setStyleSheet(self._input_style())
        self.endpoint_edit.textChanged.connect(self._on_endpoint_changed)
        self.endpoint_label = QLabel("Base Endpoint:")
        form_layout.addRow(self.endpoint_label, self.endpoint_edit)

        card_layout.addWidget(self.form_container)

        # 3. Connection Test Action & Result Area
        test_section = QFrame()
        test_section.setStyleSheet("""
            QFrame {
                background-color: #0E1017;
                border: 1px solid #232738;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        test_layout = QVBoxLayout(test_section)
        test_layout.setContentsMargins(10, 8, 10, 8)
        test_layout.setSpacing(8)

        test_btn_row = QHBoxLayout()
        self.btn_test_conn = QPushButton("🔌 Test Connection")
        self.btn_test_conn.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_test_conn.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
            QPushButton:disabled {
                background-color: #282C40;
                color: #64748B;
            }
        """)
        self.btn_test_conn.clicked.connect(self.test_connection)
        test_btn_row.addWidget(self.btn_test_conn)

        self.test_spinner = QProgressBar()
        self.test_spinner.setRange(0, 0)
        self.test_spinner.setFixedHeight(6)
        self.test_spinner.setStyleSheet("""
            QProgressBar {
                background-color: #1E2235;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #6366F1;
            }
        """)
        self.test_spinner.setVisible(False)
        test_btn_row.addWidget(self.test_spinner, 1)

        test_btn_row.addStretch()
        test_layout.addLayout(test_btn_row)

        self.test_feedback_label = QLabel("")
        self.test_feedback_label.setWordWrap(True)
        self.test_feedback_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.test_feedback_label.setVisible(False)
        test_layout.addWidget(self.test_feedback_label)

        card_layout.addWidget(test_section)
        layout.addWidget(self.card_frame)
        layout.addStretch()

    def _input_style(self) -> str:
        return """
            QLineEdit, QComboBox {
                background-color: #1A1C28;
                color: #F1F5F9;
                border: 1px solid #2E3650;
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #6366F1;
            }
        """

    # -------------------------------------------------------------------------
    # Data Synchronization
    # -------------------------------------------------------------------------

    def reload_from_service(self):
        """Populate controls from current AIService configuration."""
        if not self.ai_service:
            self._update_status_badge("disabled", "No AI Service Available")
            return

        self._is_populating = True

        cfg = self.ai_service.get_config()
        self.enable_checkbox.setChecked(bool(cfg.enabled))

        # Populate provider dropdown
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()

        available = self.ai_service.get_available_providers()
        active_id = self.ai_service.get_active_provider_id()

        active_idx = 0
        for i, prov in enumerate(available):
            pid = prov["id"]
            dname = PROVIDER_DISPLAY_NAMES.get(pid, prov.get("name", pid.capitalize()))
            self.provider_combo.addItem(dname, pid)
            if pid == active_id:
                active_idx = i

        self.provider_combo.setCurrentIndex(active_idx)
        self.provider_combo.blockSignals(False)

        self._update_provider_fields(active_id)
        self._is_populating = False

        self._refresh_status()

    def _update_provider_fields(self, provider_id: str):
        """Update form fields based on active provider."""
        if not self.ai_service:
            return

        is_local = (provider_id == "local")

        # Discovery button visibility (e.g. Gemini supports dynamic discovery)
        supports_discovery = (provider_id == "gemini")
        self.btn_refresh_models.setVisible(supports_discovery)
        self.refresh_status_label.setVisible(False)
        self.refresh_spinner.setVisible(False)

        # Model options: check cache first, then default suggestions
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        cached = self.ai_service.get_cached_models(provider_id)
        suggestions = cached if cached else PROVIDER_MODEL_SUGGESTIONS.get(provider_id, [])
        for m in suggestions:
            self.model_combo.addItem(m)

        current_model = self.ai_service.get_model(provider_id)
        if current_model:
            self.model_combo.setEditText(current_model)
        elif suggestions:
            self.model_combo.setEditText(suggestions[0])
        self.model_combo.blockSignals(False)

        # API Key
        self.api_key_edit.blockSignals(True)
        stored_key = self.ai_service.get_api_key(provider_id)
        self.api_key_edit.setText(stored_key)
        self.api_key_edit.blockSignals(False)

        # Endpoint
        self.endpoint_edit.blockSignals(True)
        stored_endpoint = self.ai_service.get_endpoint(provider_id)
        self.endpoint_edit.setText(stored_endpoint)
        self.endpoint_edit.blockSignals(False)

        # Visibility rules
        if is_local:
            self.endpoint_label.setVisible(True)
            self.endpoint_edit.setVisible(True)
            self.api_key_label.setText("API Key (Optional):")
            self.api_key_edit.setPlaceholderText("Optional for local servers")
        else:
            self.endpoint_label.setVisible(False)
            self.endpoint_edit.setVisible(False)
            self.api_key_label.setText("API Key *:")
            self.api_key_edit.setPlaceholderText(f"Enter {PROVIDER_DISPLAY_NAMES.get(provider_id, provider_id)} API Key")

    def _refresh_status(self):
        """Derive and display real-time status badge."""
        if not self.ai_service:
            self._update_status_badge("disabled", "AI Service Unavailable")
            return

        is_enabled = self.ai_service.is_enabled()
        active_id = self.ai_service.get_active_provider_id()

        if not is_enabled:
            self._update_status_badge("disabled", "🟡 Disabled")
            return

        if self._last_test_error:
            self._update_status_badge("error", "🔴 Error")
            return

        is_cfg = self.ai_service.is_provider_configured(active_id)
        if is_cfg:
            self._update_status_badge("ready", "🟢 Ready")
        else:
            self._update_status_badge("not_configured", "🟡 Not Configured")

    def _update_status_badge(self, state: str, text: str):
        self.status_badge.setText(text)
        if state == "ready":
            self.status_badge.setStyleSheet("""
                background-color: #064E3B;
                color: #34D399;
                padding: 3px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            """)
        elif state == "error":
            self.status_badge.setStyleSheet("""
                background-color: #4C1D24;
                color: #F87171;
                padding: 3px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            """)
        else:  # disabled / not_configured
            self.status_badge.setStyleSheet("""
                background-color: #282C40;
                color: #CBD5E1;
                padding: 3px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            """)

    # -------------------------------------------------------------------------
    # Field Modification Handlers
    # -------------------------------------------------------------------------

    def _on_enable_toggled(self, enabled: bool):
        if self._is_populating or not self.ai_service:
            return
        self.ai_service.set_enabled(enabled)
        self._refresh_status()
        self.configuration_changed.emit()

    def _on_provider_changed(self, index: int):
        if self._is_populating or not self.ai_service:
            return
        provider_id = self.provider_combo.itemData(index)
        if provider_id:
            self.ai_service.set_active_provider(provider_id)
            self._update_provider_fields(provider_id)
            self._last_test_error = None
            self._last_test_success = False
            self.test_feedback_label.setVisible(False)
            self._refresh_status()
            self.configuration_changed.emit()

    def _on_model_changed(self, model: str):
        if self._is_populating or not self.ai_service:
            return
        active_id = self.ai_service.get_active_provider_id()
        if active_id and model.strip():
            self.ai_service.set_model_override(active_id, model.strip())
            self.configuration_changed.emit()

    def _on_api_key_changed(self, key_text: str):
        if self._is_populating or not self.ai_service:
            return
        active_id = self.ai_service.get_active_provider_id()
        if active_id:
            self.ai_service.set_api_key(active_id, key_text)
            self._last_test_error = None
            self._refresh_status()
            self.configuration_changed.emit()

    def _on_endpoint_changed(self, endpoint_text: str):
        if self._is_populating or not self.ai_service:
            return
        active_id = self.ai_service.get_active_provider_id()
        if active_id:
            self.ai_service.set_endpoint(active_id, endpoint_text)
            self._last_test_error = None
            self._refresh_status()
            self.configuration_changed.emit()

    def _toggle_key_visibility(self):
        if self.api_key_edit.echoMode() == QLineEdit.Password:
            self.api_key_edit.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key_vis.setText("🔒")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key_vis.setText("👁️")

    def _on_service_status_changed(self, enabled: bool, provider_id: str):
        self._refresh_status()

    # -------------------------------------------------------------------------
    # Dynamic Model Discovery (Refresh Models)
    # -------------------------------------------------------------------------

    def refresh_models(self):
        """Asynchronously query Google's Models API for currently available models."""
        if not self.ai_service:
            return

        active_id = self.ai_service.get_active_provider_id()
        if active_id == "gemini":
            key = self.ai_service.get_api_key("gemini")
            if not key or not key.strip():
                self.refresh_status_label.setVisible(True)
                self.refresh_status_label.setStyleSheet("color: #F87171; font-size: 11px;")
                self.refresh_status_label.setText("⚠️ Gemini API key is missing. Enter your API key first.")
                return

        self.btn_refresh_models.setEnabled(False)
        self.refresh_spinner.setVisible(True)
        self.refresh_status_label.setVisible(True)
        self.refresh_status_label.setStyleSheet("color: #818CF8; font-size: 11px;")
        self.refresh_status_label.setText("Querying Google Models API...")

        def _on_models_discovered(pid: str, models: List[str], err: str):
            self.btn_refresh_models.setEnabled(True)
            self.refresh_spinner.setVisible(False)
            if models and not err:
                curr_text = self.model_combo.currentText().strip()
                self.model_combo.blockSignals(True)
                self.model_combo.clear()
                for m in models:
                    self.model_combo.addItem(m)
                if curr_text in models:
                    self.model_combo.setEditText(curr_text)
                elif models:
                    self.model_combo.setEditText(models[0])
                    self.ai_service.set_model_override(pid, models[0])
                self.model_combo.blockSignals(False)

                self.refresh_status_label.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;")
                self.refresh_status_label.setText(f"✓ Discovered {len(models)} models")
                self.configuration_changed.emit()
            else:
                self.refresh_status_label.setStyleSheet("color: #F87171; font-size: 11px;")
                safe_err = err or "Failed to retrieve models"
                self.refresh_status_label.setText(f"⚠️ {safe_err}")

        def _on_error(err_msg: str):
            self.btn_refresh_models.setEnabled(True)
            self.refresh_spinner.setVisible(False)
            self.refresh_status_label.setVisible(True)
            self.refresh_status_label.setStyleSheet("color: #F87171; font-size: 11px;")
            self.refresh_status_label.setText(f"⚠️ Failed to retrieve models: {err_msg}")

        try:
            self._active_discovery_worker = self.ai_service.discover_models_async(
                active_id,
                on_finished=_on_models_discovered,
                on_error=_on_error,
            )
        except Exception as e:
            self.btn_refresh_models.setEnabled(True)
            self.refresh_spinner.setVisible(False)
            self.refresh_status_label.setStyleSheet("color: #F87171; font-size: 11px;")
            self.refresh_status_label.setText(f"⚠️ Error: {str(e)}")

    # -------------------------------------------------------------------------
    # Test Connection
    # -------------------------------------------------------------------------

    def test_connection(self):
        """Execute a lightweight real or mock provider test request asynchronously."""
        if not self.ai_service:
            return

        active_id = self.ai_service.get_active_provider_id()
        provider = self.ai_service.get_active_provider()
        if not provider:
            self._set_test_result(False, f"Provider '{active_id}' is not registered.")
            return

        # Check if credentials exist before initiating network request
        if not self.ai_service.is_provider_configured(active_id) and active_id != "mock":
            if active_id == "local":
                self._set_test_result(False, "Endpoint URL is required for local server connection.")
            else:
                self._set_test_result(False, f"{PROVIDER_DISPLAY_NAMES.get(active_id, active_id)} API key is not configured.")
            return

        # Start non-blocking UI state
        self.btn_test_conn.setEnabled(False)
        self.test_spinner.setVisible(True)
        self.test_feedback_label.setVisible(True)
        self.test_feedback_label.setStyleSheet("color: #818CF8; font-size: 11px;")
        self.test_feedback_label.setText(f"Testing connection to {PROVIDER_DISPLAY_NAMES.get(active_id, active_id)}...")

        effective_model = self.model_combo.currentText().strip() or self.ai_service.get_model(active_id)
        test_req = AIRequest(
            prompt="CreativeWorkspace AI Connection Test. Reply with 'OK'.",
            max_tokens=15,
            temperature=0.0,
            model=effective_model,
        )

        start_time = time.time()

        def _on_test_finished(req: AIRequest, resp: AIResponse):
            latency_ms = int((time.time() - start_time) * 1000)
            self.btn_test_conn.setEnabled(True)
            self.test_spinner.setVisible(False)

            if resp.success:
                msg = f"✓ Connected successfully! Model: {resp.model} ({latency_ms}ms)"
                self._set_test_result(True, msg)
            else:
                err = resp.error_message or "Connection failed."
                self._set_test_result(False, f"Connection failed: {err}")

        def _on_test_error(err_msg: str):
            self.btn_test_conn.setEnabled(True)
            self.test_spinner.setVisible(False)
            self._set_test_result(False, f"Connection failed: {err_msg}")

        # Temporarily enable during test call if disabled
        was_enabled = self.ai_service.is_enabled()
        if not was_enabled:
            self.ai_service._config.enabled = True

        try:
            self._active_test_worker = self.ai_service.generate_async(
                test_req,
                on_finished=lambda req, resp: (
                    self._restore_enabled(was_enabled),
                    _on_test_finished(req, resp),
                ),
                on_error=lambda err: (
                    self._restore_enabled(was_enabled),
                    _on_test_error(err),
                ),
            )
        except Exception as e:
            self._restore_enabled(was_enabled)
            self.btn_test_conn.setEnabled(True)
            self.test_spinner.setVisible(False)
            self._set_test_result(False, f"Connection failed: {str(e)}")

    def _restore_enabled(self, was_enabled: bool):
        if self.ai_service and not was_enabled:
            self.ai_service._config.enabled = False

    def _set_test_result(self, success: bool, message: str):
        self._last_test_success = success
        self._last_test_error = None if success else message
        self.test_feedback_label.setVisible(True)

        if success:
            self.test_feedback_label.setStyleSheet("color: #34D399; font-size: 11px; font-weight: bold;")
            self.test_feedback_label.setText(message)
        else:
            self.test_feedback_label.setStyleSheet("color: #F87171; font-size: 11px;")
            self.test_feedback_label.setText(f"⚠️ {message}")

        self._refresh_status()
