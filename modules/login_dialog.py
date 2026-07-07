"""Login & incident selection dialog (PySide6 Widgets).

This modal dialog is shown on startup to ensure the user selects/creates an
incident and provides credentials plus a role for audit/documentation.
Nothing else in the app should be accessible until this dialog is completed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from utils.state import AppState
from modules.incidents.new_incident_dialog import NewIncidentDialog
from utils.audit import write_audit
from utils.session import start_session


# Static list of roles (not used for permissions, only for logging/documentation)
STATIC_ROLES = [
    "Incident Commander",
    "Operations Section Chief",
    "Planning Section Chief",
    "Logistics Section Chief",
    "Finance/Admin Section Chief",
    "Safety Officer",
    "PIO",
    "Liaison Officer",
    "Planning Staff",
    "Operations Staff",
    "Logistics Staff",
]


@dataclass
class IncidentItem:
    incident_id: str
    number: str
    name: str


class IncidentSelectionDialog(QDialog):
    """Widget-based incident picker for switching the active incident."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        default_incident_number: str | None = None,
        api_available: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Incident")
        self.setModal(True)
        self._default_incident_number = default_incident_number
        self._api_available = api_available

        self.incident_combo = QComboBox(self)
        self.btn_new_incident = QPushButton("Create New Incident", self)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.btn_continue = self.buttons.button(QDialogButtonBox.Ok)
        self.btn_continue.setText("Open")
        self.btn_continue.setEnabled(False)
        self._incidents: List[IncidentItem] = []

        form = QFormLayout()
        row_inc = QHBoxLayout()
        row_inc.addWidget(self.incident_combo, 1)
        row_inc.addWidget(self.btn_new_incident)
        form.addRow("Incident", self._wrap(row_inc))

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        self.btn_new_incident.clicked.connect(self._on_create_new_incident)
        self.incident_combo.currentIndexChanged.connect(self._update_continue_enabled)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self._load_incidents()
        if self._default_incident_number:
            self._select_incident(self._default_incident_number)
        self._update_continue_enabled()

    def _wrap(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget(self)
        w.setLayout(layout)
        return w

    def _load_incidents(self) -> None:
        self.incident_combo.clear()
        self._incidents.clear()
        if not self._api_available:
            self.incident_combo.addItem("Connect or start offline to load incidents", userData=None)
            return
        try:
            from utils.api_client import api_client
            docs = api_client.get("/api/incidents") or []
            for doc in docs:
                self._incidents.append(
                    IncidentItem(
                        incident_id=doc.get("incident_id") or doc.get("id", ""),
                        number=str(doc.get("number", "")),
                        name=str(doc.get("name", "")),
                    )
                )
        except Exception as e:
            QMessageBox.warning(self, "Database Error", f"Failed to load incidents: {e}")
            self._incidents = []

        for it in self._incidents:
            label = f"{it.name or '(unnamed)'} - #{it.number}"
            self.incident_combo.addItem(label, userData=it.incident_id)

    def _select_incident(self, incident_key: str) -> None:
        idx = self.incident_combo.findData(incident_key)
        if idx >= 0:
            self.incident_combo.setCurrentIndex(idx)
            return
        for row, item in enumerate(self._incidents):
            if item.number == incident_key or item.incident_id == incident_key:
                self.incident_combo.setCurrentIndex(row)
                return

    def _on_create_new_incident(self) -> None:
        dlg = NewIncidentDialog(self)

        def _created(meta, incident_id: str):
            try:
                write_audit("incident.create", {"number": meta.number, "name": meta.name})
            except Exception:
                pass
            self._load_incidents()
            self._select_incident(incident_id)
            self._update_continue_enabled()

        dlg.created.connect(_created)
        dlg.exec()

    def _update_continue_enabled(self) -> None:
        self.btn_continue.setEnabled(self.incident_combo.currentData() is not None)

    def selected_incident_id(self) -> str | None:
        value = self.incident_combo.currentData()
        return str(value) if value is not None else None


class LoginDialog(QDialog):
    """Modal startup splash for online sign-in, registration, or offline launch."""

    sessionReady = Signal(str, str, str)  # (incident_id, user_id, role)
    startOfflineRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        demo_mode: bool = False,
        default_incident_number: str | None = None,
        api_available: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SARApp")
        self.setModal(True)
        self._demo_mode = demo_mode
        self._default_incident_number = default_incident_number
        self._api_available = api_available
        self._offline_starting = False

        self.incident_combo = QComboBox()
        self.btn_new_incident = QPushButton("Create New Incident")
        self.role_combo = QComboBox()
        self.role_combo.addItems(STATIC_ROLES)

        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.org_code_edit = QLineEdit()
        self.register_name_edit = QLineEdit()
        self.register_username_edit = QLineEdit()
        self.register_password_edit = QLineEdit()
        self.register_password_edit.setEchoMode(QLineEdit.Password)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_continue = self.buttons.button(QDialogButtonBox.Ok)
        self.btn_continue.setText("Continue")
        self.btn_continue.setEnabled(False)
        self.btn_show_login = QPushButton("Log In")
        self.btn_show_register = QPushButton("Create Account / Register")
        self.btn_start_offline = QPushButton("Start Offline")
        self.btn_submit_register = QPushButton("Submit Registration")
        self.btn_back_to_login = QPushButton("Back to Login")

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_login_page())
        self.stack.addWidget(self._build_register_page())

        layout = QVBoxLayout(self)
        title = QLabel("SARApp Incident Management")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        subtitle = QLabel("Sign in to cloud services, register with an organization code, or work locally.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.stack)
        layout.addStretch(1)
        layout.addWidget(self.btn_start_offline, alignment=Qt.AlignCenter)

        self.btn_show_register.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_show_login.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_back_to_login.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_submit_register.clicked.connect(self._submit_registration)
        self.btn_start_offline.clicked.connect(self._request_offline_start)
        self.btn_new_incident.clicked.connect(self._on_create_new_incident)
        self.incident_combo.currentIndexChanged.connect(self._update_continue_enabled)
        self.username_edit.textChanged.connect(self._update_continue_enabled)
        self.password_edit.textChanged.connect(self._update_continue_enabled)
        self.role_combo.currentIndexChanged.connect(self._update_continue_enabled)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)

        self._incidents: List[IncidentItem] = []
        self._load_incidents()
        try:
            if self._default_incident_number:
                self._select_incident(self._default_incident_number)
        except Exception:
            pass
        self._update_continue_enabled()

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        form = QFormLayout()
        form.addRow("Username", self.username_edit)
        form.addRow("Password", self.password_edit)
        row_inc = QHBoxLayout()
        row_inc.addWidget(self.incident_combo, 1)
        row_inc.addWidget(self.btn_new_incident)
        form.addRow(QLabel("Incident"), self._wrap(row_inc))
        form.addRow("Role", self.role_combo)
        page_layout.addLayout(form)
        page_layout.addWidget(self.buttons)
        page_layout.addWidget(self.btn_show_register)
        return page

    def _build_register_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        form = QFormLayout()
        form.addRow("Org Code", self.org_code_edit)
        form.addRow("Name", self.register_name_edit)
        form.addRow("Username", self.register_username_edit)
        form.addRow("Password", self.register_password_edit)
        page_layout.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(self.btn_back_to_login)
        row.addWidget(self.btn_submit_register)
        page_layout.addLayout(row)
        return page

    def _wrap(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _load_incidents(self) -> None:
        self.incident_combo.clear()
        self._incidents.clear()
        if not self._api_available:
            self.incident_combo.addItem("Connect or start offline to load incidents", userData=None)
            return
        try:
            from utils.api_client import api_client
            docs = api_client.get("/api/incidents") or []
            for doc in docs:
                self._incidents.append(IncidentItem(
                    incident_id=doc.get("incident_id") or doc.get("id", ""),
                    number=str(doc.get("number", "")),
                    name=str(doc.get("name", "")),
                ))
        except Exception as e:
            QMessageBox.warning(self, "Database Error", f"Failed to load incidents: {e}")
            self._incidents = []

        for it in self._incidents:
            label = f"{it.name or '(unnamed)'} - #{it.number}"
            self.incident_combo.addItem(label, userData=it.incident_id)

    def _select_incident(self, incident_key: str) -> None:
        idx = self.incident_combo.findData(incident_key)
        if idx >= 0:
            self.incident_combo.setCurrentIndex(idx)
            return
        for row, item in enumerate(self._incidents):
            if item.number == incident_key or item.incident_id == incident_key:
                self.incident_combo.setCurrentIndex(row)
                return

    def _on_create_new_incident(self) -> None:
        dlg = NewIncidentDialog(self)

        def _created(meta, incident_id: str):
            try:
                write_audit("incident.create", {"number": meta.number, "name": meta.name})
            except Exception:
                pass
            self._load_incidents()
            self._select_incident(incident_id)
            self._update_continue_enabled()

        dlg.created.connect(_created)
        dlg.exec()

    def _update_continue_enabled(self) -> None:
        if self._demo_mode:
            self.btn_continue.setEnabled(True)
            return
        ok = (
            self.incident_combo.currentIndex() >= 0
            and (self.incident_combo.currentData() is not None)
            and (self.username_edit.text().strip() != "")
            and (self.password_edit.text().strip() != "")
            and (self.role_combo.currentText().strip() != "")
        )
        self.btn_continue.setEnabled(ok)

    def _submit_registration(self) -> None:
        required = [
            self.org_code_edit.text().strip(),
            self.register_name_edit.text().strip(),
            self.register_username_edit.text().strip(),
            self.register_password_edit.text().strip(),
        ]
        if not all(required):
            QMessageBox.warning(self, "Missing Info", "Enter org code, name, username, and password.")
            return
        QMessageBox.information(
            self,
            "Registration",
            "Registration will be submitted to the cloud server when the authentication API is available.",
        )

    def _request_offline_start(self) -> None:
        self.btn_start_offline.setEnabled(False)
        self.btn_start_offline.setText("Starting Offline...")
        self.startOfflineRequested.emit()

    def offline_start_failed(self) -> None:
        self.btn_start_offline.setEnabled(True)
        self.btn_start_offline.setText("Start Offline")

    def complete_offline_start(self) -> None:
        AppState.set_active_incident(None)
        AppState.set_active_user_id("")
        AppState.set_active_user_role("Offline")
        self.accept()

    def _accept(self) -> None:
        incident_id = self.incident_combo.currentData()
        # The username is the operator's person_id; keep using it as the active user identifier.
        username = self.username_edit.text().strip() or ""
        person_id = username
        role = self.role_combo.currentText().strip() or ""

        if not self._demo_mode:
            if not incident_id or not person_id or not role or not self.password_edit.text().strip():
                QMessageBox.warning(self, "Missing Info", "Please sign in, select an incident, and enter Username, Password, and Role.")
                return

        AppState.set_active_incident(incident_id)
        AppState.set_active_user_id(person_id)
        AppState.set_active_user_role(role)

        selected = next((item for item in self._incidents if item.incident_id == str(incident_id)), None)
        incident_number = selected.number if selected is not None else str(incident_id)

        try:
            sid = start_session(
                person_id,
                username=username,
                display_name=username,
                role=role,
                incident_id=str(incident_id),
                mode="cloud",
            )
            write_audit("session.start", {"session_id": sid}, prefer_mission=False)
            write_audit("login.success", {"role": role, "user_id": person_id}, prefer_mission=False)
            write_audit("incident.select", {"id": incident_id, "number": incident_number})
        except Exception:
            pass

        self.sessionReady.emit(str(incident_id), person_id, role)
        self.accept()


__all__ = ["IncidentSelectionDialog", "LoginDialog", "STATIC_ROLES"]
