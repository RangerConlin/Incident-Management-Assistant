"""Login & incident selection dialog (PySide6 Widgets).

This modal dialog is shown on startup to ensure the user selects/creates an
incident and provides credentials plus a role for audit/documentation.
Nothing else in the app should be accessible until this dialog is completed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
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
from utils.styles import get_palette, subscribe_theme

_BRAND_DIR = Path(__file__).resolve().parent.parent / "assets" / "branding"
_BRAND_MARK_PATH = _BRAND_DIR / "arc_horizon_mark.png"
_BRAND_WORDMARK_PATH = _BRAND_DIR / "arc_horizon_wordmark.png"


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


class RemoteServerDialog(QDialog):
    """Modal for entering a cloud router URL + connect code from the login screen.

    Mirrors the fields/wording of Settings -> Connection
    (ui/settings/pages/connection_page.py) but writes directly to the shared
    SettingsManager, since the SettingsBridge used by the Settings dialog
    isn't constructed yet at login time.
    """

    def __init__(self, parent: QWidget | None, settings_manager) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect to Remote Server")
        self.setModal(True)
        self._settings_manager = settings_manager

        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText(
            "https://cloud-router.example (blank = built-in default)"
        )
        self.connect_code_edit = QLineEdit()
        self.connect_code_edit.setPlaceholderText(
            "e.g. ABCD-1234 (both blank = built-in default)"
        )
        self.connect_code_edit.textChanged.connect(self._normalize_connect_code)

        self.server_url_edit.setText(str(settings_manager.get("cloudServerUrl") or ""))
        self.connect_code_edit.setText(str(settings_manager.get("cloudConnectCode") or ""))

        form = QFormLayout()
        form.addRow("Cloud server URL:", self.server_url_edit)
        form.addRow("Connect code:", self.connect_code_edit)

        note = QLabel(
            "The connect code identifies one incident command post's server on the "
            "cloud router — get it from the IC or the SARApp Server Console. "
            "Changes take effect on the next launch or connection retry."
        )
        note.setWordWrap(True)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(self.buttons)

    def _normalize_connect_code(self, text: str) -> None:
        upper = text.upper()
        if upper != text:
            cursor = self.connect_code_edit.cursorPosition()
            self.connect_code_edit.blockSignals(True)
            self.connect_code_edit.setText(upper)
            self.connect_code_edit.setCursorPosition(cursor)
            self.connect_code_edit.blockSignals(False)

    def _on_accept(self) -> None:
        self._settings_manager.set("cloudServerUrl", self.server_url_edit.text().strip())
        self._settings_manager.set("cloudConnectCode", self.connect_code_edit.text().strip())
        self.accept()


class CreateProfileDialog(QDialog):
    """Collects the name for a login ID that has no personnel record yet."""

    def __init__(self, parent: QWidget | None, person_id: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Your Profile")
        self.setModal(True)

        note = QLabel(
            f"No personnel record matches ID \"{person_id}\". Enter your name to "
            "create one and continue signing in."
        )
        note.setWordWrap(True)
        self.first_name_edit = QLineEdit()
        self.last_name_edit = QLineEdit()

        form = QFormLayout()
        form.addRow("First name", self.first_name_edit)
        form.addRow("Last name", self.last_name_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

    def names(self) -> tuple[str, str]:
        return self.first_name_edit.text().strip(), self.last_name_edit.text().strip()

    def _on_accept(self) -> None:
        if not all(self.names()):
            QMessageBox.warning(self, "Missing Info", "Enter both a first and last name.")
            return
        self.accept()


def _resolve_person_record(parent: QWidget | None, person_id: str) -> str | None:
    """Match a login ID to a personnel record, creating one if needed.

    Returns the person's display name, or None when sign-in should stop
    (unknown/ambiguous ID the user declined to fix, or a server error).
    """

    from utils.api_client import api_client

    try:
        result = api_client.get("/api/auth/lookup", params={"person_id": person_id}) or {}
    except Exception as exc:
        QMessageBox.warning(parent, "Login Failed", f"Could not check this ID with the server: {exc}")
        return None

    status = result.get("status")
    if status == "found":
        return str((result.get("person") or {}).get("name") or person_id)
    if status == "ambiguous":
        QMessageBox.warning(
            parent,
            "Login Failed",
            "More than one personnel record uses this ID. Ask an administrator to fix the roster.",
        )
        return None

    dialog = CreateProfileDialog(parent, person_id)
    if dialog.exec() != QDialog.Accepted:
        return None
    first_name, last_name = dialog.names()
    try:
        created = api_client.post(
            "/api/auth/register",
            json={"person_id": person_id, "first_name": first_name, "last_name": last_name},
        ) or {}
    except Exception as exc:
        QMessageBox.warning(parent, "Login Failed", f"Could not create your profile: {exc}")
        return None
    return str((created.get("person") or {}).get("name") or f"{first_name} {last_name}")


def _finish_session(
    *,
    parent: QWidget | None,
    username: str,
    role: str,
    incident_id,
    display_name: str,
    incidents: List[IncidentItem],
    strict: bool = True,
) -> tuple[str, str, str] | None:
    """Apply the active incident/user/role, start the session, and audit it.

    Returns (incident_id, person_record, role) on success. When `strict` is
    True and the server fails to resolve a person record, warns and returns
    None instead.
    """

    AppState.set_active_incident(incident_id)
    AppState.set_active_user_id("")
    AppState.set_active_user_role(role)

    selected = next((item for item in incidents if item.incident_id == str(incident_id)), None)
    incident_number = selected.number if selected is not None else str(incident_id)

    sid = None
    try:
        sid = start_session(
            username,
            username=username,
            display_name=display_name,
            role=role,
            incident_id=str(incident_id),
            mode="cloud",
        )
        write_audit("session.start", {"session_id": sid}, prefer_mission=False)
        write_audit("login.success", {"role": role, "person_id": username}, prefer_mission=False)
        write_audit("incident.select", {"id": incident_id, "number": incident_number})
    except Exception:
        pass

    person_record = AppState.get_active_user_id()
    if strict and (not sid or person_record in (None, "")):
        QMessageBox.warning(parent, "Login Failed", "The login server could not resolve this personnel ID.")
        return None
    return str(incident_id), str(person_record or ""), role


class QuickResumeDialog(IncidentSelectionDialog):
    """Incident picker shown when a remembered login bypasses full sign-in."""

    switchAccountRequested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        display_name: str,
        default_incident_number: str | None = None,
        api_available: bool = True,
    ) -> None:
        super().__init__(
            parent,
            default_incident_number=default_incident_number,
            api_available=api_available,
        )
        self.setWindowTitle("Select Incident")

        welcome = QLabel(f"Signed in as {display_name}")
        self.layout().insertWidget(0, welcome)

        self.btn_switch_account = QPushButton("Sign in as someone else")
        self.layout().insertWidget(self.layout().count() - 1, self.btn_switch_account)
        self.btn_switch_account.clicked.connect(self._on_switch_account)

    def _on_switch_account(self) -> None:
        self.switchAccountRequested.emit()
        self.reject()


def attempt_remembered_login(
    *,
    settings_manager,
    api_available: bool,
    parent: QWidget | None = None,
) -> tuple[str, str, str] | None:
    """Try to resume a remembered sign-in, skipping straight to incident
    selection. Returns (incident_id, person_record, role) on success, or
    None if there's no remembered login, the user declines, or resolution
    fails — in every None case the caller should fall back to the full
    LoginDialog.
    """

    if settings_manager is None or not api_available:
        return None
    if not settings_manager.get("rememberLogin"):
        return None
    username = str(settings_manager.get("rememberedUsername") or "").strip()
    role = str(settings_manager.get("rememberedRole") or "").strip()
    if not username or not role:
        return None

    display_name = _resolve_person_record(parent, username)
    if display_name is None:
        return None

    dialog = QuickResumeDialog(
        parent,
        display_name=display_name,
        default_incident_number=settings_manager.get("lastIncidentNumber"),
        api_available=api_available,
    )
    forgotten = False

    def _on_switch_account() -> None:
        nonlocal forgotten
        forgotten = True

    dialog.switchAccountRequested.connect(_on_switch_account)
    if dialog.exec() != QDialog.Accepted:
        if forgotten:
            settings_manager.set("rememberLogin", False)
        return None

    incident_id = dialog.selected_incident_id()
    if not incident_id:
        return None

    return _finish_session(
        parent=parent,
        username=username,
        role=role,
        incident_id=incident_id,
        display_name=display_name,
        incidents=dialog._incidents,
    )


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
        settings_manager=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("LoginDialog")
        self.setWindowTitle("SARApp")
        self.setModal(True)
        self._demo_mode = demo_mode
        self._default_incident_number = default_incident_number
        self._api_available = api_available
        self._offline_starting = False
        self._settings_manager = settings_manager

        self.incident_combo = QComboBox()
        self.btn_new_incident = QPushButton("New")
        self.btn_new_incident.setObjectName("secondaryButton")
        self.role_combo = QComboBox()
        self.role_combo.addItems(STATIC_ROLES)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Personnel ID")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Password")
        self.org_code_edit = QLineEdit()
        self.org_code_edit.setPlaceholderText("e.g. ORK-SAR")
        self.register_name_edit = QLineEdit()
        self.register_username_edit = QLineEdit()
        self.register_password_edit = QLineEdit()
        self.register_password_edit.setEchoMode(QLineEdit.Password)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_continue = self.buttons.button(QDialogButtonBox.Ok)
        self.btn_continue.setText("Continue")
        self.btn_continue.setObjectName("primaryButton")
        self.btn_continue.setEnabled(False)
        self.btn_cancel = self.buttons.button(QDialogButtonBox.Cancel)
        self.btn_cancel.setObjectName("secondaryButton")

        self.btn_tab_login = QPushButton("Log in")
        self.btn_tab_login.setObjectName("tabButton")
        self.btn_tab_login.setCheckable(True)
        self.btn_tab_login.setChecked(True)
        self.btn_tab_register = QPushButton("Register")
        self.btn_tab_register.setObjectName("tabButton")
        self.btn_tab_register.setCheckable(True)

        self.btn_start_offline = QPushButton("Start Offline")
        self.btn_start_offline.setObjectName("secondaryButton")
        self.btn_connect_remote = QPushButton("Connect to Remote Server...")
        self.btn_connect_remote.setObjectName("secondaryButton")
        self.btn_submit_register = QPushButton("Submit Registration")
        self.btn_submit_register.setObjectName("primaryButton")
        self.btn_back_to_login = QPushButton("Back to Login")
        self.btn_back_to_login.setObjectName("secondaryButton")

        self.chk_remember = QCheckBox("Remember me on this device")
        self.chk_remember.setObjectName("rememberCheck")

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_login_page())
        self.stack.addWidget(self._build_register_page())

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_branding_panel())
        root.addWidget(self._build_content_panel(), 1)
        self.setMinimumSize(760, 560)

        self.btn_tab_login.clicked.connect(lambda: self._select_tab(0))
        self.btn_tab_register.clicked.connect(lambda: self._select_tab(1))
        self.btn_back_to_login.clicked.connect(lambda: self._select_tab(0))
        self.btn_submit_register.clicked.connect(self._submit_registration)
        self.btn_start_offline.clicked.connect(self._request_offline_start)
        self.btn_connect_remote.clicked.connect(self._on_connect_remote)
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
        self._prefill_remembered_login()
        self._update_continue_enabled()

        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())

    def _select_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.btn_tab_login.setChecked(index == 0)
        self.btn_tab_register.setChecked(index == 1)

    def _build_branding_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("brandingPanel")
        panel.setFixedWidth(260)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        layout.addWidget(self._build_brand_lockup())
        layout.addStretch(1)

        self._status_label = QLabel()
        self._status_label.setObjectName("brandStatus")
        self._status_label.setWordWrap(True)

        audit_label = QLabel(
            "Sessions are audited for accountability and recordkeeping."
        )
        audit_label.setObjectName("brandStatus")
        audit_label.setWordWrap(True)

        layout.addWidget(self._status_label)
        layout.addWidget(audit_label)
        self._update_status_label()
        return panel

    def _build_brand_lockup(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        mark_label = QLabel()
        mark_pixmap = QPixmap(str(_BRAND_MARK_PATH))
        if not mark_pixmap.isNull():
            mark_label.setPixmap(
                mark_pixmap.scaledToHeight(56, Qt.SmoothTransformation)
            )

        wordmark_label = QLabel()
        wordmark_pixmap = QPixmap(str(_BRAND_WORDMARK_PATH))
        if not wordmark_pixmap.isNull():
            wordmark_label.setPixmap(
                wordmark_pixmap.scaledToWidth(190, Qt.SmoothTransformation)
            )

        layout.addWidget(mark_label)
        layout.addWidget(wordmark_label)
        return wrap

    def _update_status_label(self) -> None:
        if self._api_available:
            self._status_label.setText("Online services available")
        else:
            self._status_label.setText("Working offline - local data only")

    def _build_content_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("contentPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(44, 36, 44, 36)
        layout.setSpacing(0)

        tab_selector = QFrame()
        tab_selector.setObjectName("tabSelector")
        tab_row = QHBoxLayout(tab_selector)
        tab_row.setContentsMargins(3, 3, 3, 3)
        tab_row.setSpacing(4)
        tab_row.addWidget(self.btn_tab_login)
        tab_row.addWidget(self.btn_tab_register)

        tab_header = QHBoxLayout()
        tab_header.addWidget(tab_selector)
        tab_header.addStretch(1)

        layout.addLayout(tab_header)
        layout.addSpacing(20)
        layout.addWidget(self.stack)
        return panel

    def _labeled_field(self, label_text: str, field: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(field)
        return wrap

    def _build_divider(self, text: str) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(10)
        line_left = QFrame()
        line_left.setFrameShape(QFrame.HLine)
        line_left.setObjectName("dividerLine")
        line_right = QFrame()
        line_right.setFrameShape(QFrame.HLine)
        line_right.setObjectName("dividerLine")
        label = QLabel(text)
        label.setObjectName("dividerLabel")
        row.addWidget(line_left, 1)
        row.addWidget(label)
        row.addWidget(line_right, 1)
        return wrap

    def _build_login_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._labeled_field("Username", self.username_edit))
        layout.addWidget(self._labeled_field("Password", self.password_edit))

        incident_row = QHBoxLayout()
        incident_row.addWidget(self.incident_combo, 1)
        incident_row.addWidget(self.btn_new_incident)
        layout.addWidget(self._labeled_field("Incident", self._wrap(incident_row)))
        layout.addWidget(self._labeled_field("Role", self.role_combo))

        layout.addWidget(self.chk_remember)
        layout.addWidget(self.buttons)
        layout.addWidget(self._build_divider("or"))

        secondary_row = QHBoxLayout()
        secondary_row.addWidget(self.btn_connect_remote)
        secondary_row.addWidget(self.btn_start_offline)
        layout.addLayout(secondary_row)
        layout.addStretch(1)
        return page

    def _build_register_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._labeled_field("Org Code", self.org_code_edit))
        layout.addWidget(self._labeled_field("Name", self.register_name_edit))

        creds_row = QHBoxLayout()
        creds_row.addWidget(self._labeled_field("Username", self.register_username_edit))
        creds_row.addWidget(self._labeled_field("Password", self.register_password_edit))
        layout.addLayout(creds_row)

        layout.addWidget(self.btn_submit_register)

        back_row = QHBoxLayout()
        back_row.addStretch(1)
        back_row.addWidget(self.btn_back_to_login)
        layout.addLayout(back_row)
        layout.addStretch(1)
        return page

    def _wrap(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _apply_styles(self) -> None:
        pal = get_palette()
        bg_window = pal["bg_window"].name()
        bg_panel = pal["bg_panel"].name()
        bg_raised = pal["bg_raised"].name()
        divider = pal["divider"].name()
        ctrl_border = pal["ctrl_border"].name()
        ctrl_hover = pal["ctrl_hover"].name()
        ctrl_focus = pal["ctrl_focus"].name()
        fg_primary = pal["fg_primary"].name()
        fg_muted = pal["fg_muted"].name()
        btn_focus = pal["btn_focus"].name()
        btn_focus_hover = pal["btn_focus"].darker(110).name()
        btn_bg = pal["btn_bg"].name()
        btn_border = pal["btn_border"].name()
        btn_disabled = pal["btn_disabled"].name()

        self.setStyleSheet(f"""
            QDialog#LoginDialog {{ background: {bg_window}; }}
            QWidget#contentPanel {{ background: {bg_window}; }}
            QFrame#brandingPanel {{
                background: {bg_panel};
                border-right: 1px solid {divider};
            }}
            QLabel#brandStatus {{
                color: {fg_muted};
                font-size: 12px;
            }}
            QFrame#tabSelector {{
                background: {bg_raised};
                border-radius: 8px;
            }}
            QPushButton#tabButton {{
                border: none;
                background: transparent;
                color: {fg_muted};
                font-size: 13px;
                font-weight: 500;
                padding: 7px 18px;
                border-radius: 6px;
            }}
            QPushButton#tabButton:checked {{
                background: {btn_bg};
                color: {fg_primary};
            }}
            QLabel#fieldLabel {{
                color: {fg_muted};
                font-size: 12px;
            }}
            QLineEdit, QComboBox {{
                background: {bg_raised};
                border: 1px solid {ctrl_border};
                border-radius: 6px;
                padding: 0 10px;
                min-height: 32px;
                color: {fg_primary};
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {ctrl_focus};
            }}
            QFrame#dividerLine {{
                background: {divider};
                max-height: 1px;
                border: none;
            }}
            QLabel#dividerLabel {{
                color: {fg_muted};
                font-size: 11px;
            }}
            QPushButton#primaryButton {{
                background: {btn_focus};
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 500;
                min-height: 34px;
                padding: 0 16px;
            }}
            QPushButton#primaryButton:hover {{
                background: {btn_focus_hover};
            }}
            QPushButton#primaryButton:disabled {{
                background: {btn_disabled};
                color: {fg_muted};
            }}
            QPushButton#secondaryButton {{
                background: transparent;
                border: 1px solid {ctrl_border};
                border-radius: 6px;
                color: {fg_muted};
                font-size: 12px;
                min-height: 30px;
                padding: 0 12px;
            }}
            QPushButton#secondaryButton:hover {{
                background: {ctrl_hover};
            }}
            QCheckBox#rememberCheck {{
                color: {fg_muted};
                font-size: 12px;
            }}
        """)
        self._update_status_label()

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

    def _on_connect_remote(self) -> None:
        settings_manager = self._settings_manager
        if settings_manager is None:
            from utils.settingsmanager import SettingsManager
            settings_manager = SettingsManager()
            self._settings_manager = settings_manager

        dlg = RemoteServerDialog(self, settings_manager)
        if dlg.exec() == QDialog.Accepted:
            QMessageBox.information(
                self,
                "Remote Server Saved",
                "Remote server settings were saved. They will take effect on "
                "the next launch or connection retry.",
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

    def _ensure_profile(self, person_id: str) -> str | None:
        """Match the login ID to a personnel record, creating one if needed.

        Returns the person's display name, or None when sign-in should stop
        (unknown/ambiguous ID the user declined to fix, or a server error).
        """

        return _resolve_person_record(self, person_id)

    def _prefill_remembered_login(self) -> None:
        """Pre-fill username/role/remember-me when falling back to the full
        form after a remembered sign-in (e.g. quick resume failed offline)."""

        if self._settings_manager is None:
            return
        if not self._settings_manager.get("rememberLogin"):
            return
        username = str(self._settings_manager.get("rememberedUsername") or "").strip()
        role = str(self._settings_manager.get("rememberedRole") or "").strip()
        if username:
            self.username_edit.setText(username)
        if role:
            idx = self.role_combo.findText(role)
            if idx >= 0:
                self.role_combo.setCurrentIndex(idx)
        self.chk_remember.setChecked(True)

    def _save_remember_preference(self, username: str, role: str) -> None:
        if self._settings_manager is None:
            return
        if self.chk_remember.isChecked():
            self._settings_manager.set("rememberLogin", True)
            self._settings_manager.set("rememberedUsername", username)
            self._settings_manager.set("rememberedRole", role)
        elif self._settings_manager.get("rememberLogin"):
            self._settings_manager.set("rememberLogin", False)

    def _accept(self) -> None:
        incident_id = self.incident_combo.currentData()
        # Users log in with the visible personnel ID.  Resolve it once to the
        # internal person_record; never expose that record key as login input.
        username = self.username_edit.text().strip() or ""
        role = self.role_combo.currentText().strip() or ""

        if not self._demo_mode:
            if not incident_id or not username or not role or not self.password_edit.text().strip():
                QMessageBox.warning(self, "Missing Info", "Please sign in, select an incident, and enter Username, Password, and Role.")
                return

        display_name = username
        if username and not self._demo_mode:
            resolved_name = self._ensure_profile(username)
            if resolved_name is None:
                return
            display_name = resolved_name

        result = _finish_session(
            parent=self,
            username=username,
            role=role,
            incident_id=incident_id,
            display_name=display_name,
            incidents=self._incidents,
            strict=bool(username) and not self._demo_mode,
        )
        if result is None:
            return
        incident_id_str, person_record, role = result

        if username and not self._demo_mode:
            self._save_remember_preference(username, role)

        self.sessionReady.emit(incident_id_str, person_record, role)
        self.accept()


__all__ = [
    "IncidentSelectionDialog",
    "LoginDialog",
    "QuickResumeDialog",
    "RemoteServerDialog",
    "STATIC_ROLES",
    "attempt_remembered_login",
]
