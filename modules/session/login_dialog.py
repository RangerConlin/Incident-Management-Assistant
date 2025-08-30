"""Login & incident selection dialog (PySide6 Widgets).

This modal dialog is shown on startup to ensure the user selects/creates an
incident and provides a User ID and Role for audit/documentation. Nothing else
in the app should be accessible until this dialog is completed.

Integrations with existing repo:
 - Incidents are read from the master database via simple SQL (most recent first)
   using helpers in `models.database` where appropriate.
 - New incidents are created using the existing `NewIncidentDialog`, and then
   registered into `data/master.db` with `models.database.insert_new_incident`.
 - Session values are stored in `utils.state.AppState`.
 - An audit helper can log the login action (see `utils.audit`).

Stretch support:
 - Demo mode can be enabled (constructor flag), which relaxes validation so the
   Continue button is always enabled and any inputs are accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

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
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from utils.state import AppState
from models.database import get_connection, insert_new_incident
from modules.incidents.new_incident_dialog import NewIncidentDialog


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
    id: int
    number: str
    name: str


class LoginDialog(QDialog):
    """Modal startup dialog that collects incident + user context."""

    # Emit when the session is established
    sessionReady = Signal(str, str, str)  # (incident_number, user_id, role)

    def __init__(self, parent: QWidget | None = None, *, demo_mode: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Login / Select Incident")
        self.setModal(True)
        self._demo_mode = demo_mode

        # Widgets
        self.incident_combo = QComboBox()
        self.btn_new_incident = QPushButton("Create New Incident")
        self.user_id_edit = QLineEdit()
        self.role_combo = QComboBox()
        self.role_combo.addItems(STATIC_ROLES)

        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_continue = self.buttons.button(QDialogButtonBox.Ok)
        self.btn_continue.setText("Continue")
        self.btn_continue.setEnabled(False)

        # Layout
        form = QFormLayout()
        # Incidents row: dropdown + create button
        row_inc = QHBoxLayout()
        row_inc.addWidget(self.incident_combo, 1)
        row_inc.addWidget(self.btn_new_incident)
        form.addRow(QLabel("Incident"), self._wrap(row_inc))
        form.addRow("User ID", self.user_id_edit)
        form.addRow("Role", self.role_combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        # Signals
        self.btn_new_incident.clicked.connect(self._on_create_new_incident)
        self.incident_combo.currentIndexChanged.connect(self._update_continue_enabled)
        self.user_id_edit.textChanged.connect(self._update_continue_enabled)
        self.role_combo.currentIndexChanged.connect(self._update_continue_enabled)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)

        self._incidents: List[IncidentItem] = []
        self._load_incidents()
        self._update_continue_enabled()

    # ------------------------------------------------------------------
    def _wrap(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _load_incidents(self) -> None:
        """Load incidents from master.db, most recent first (id desc)."""
        self.incident_combo.clear()
        self._incidents.clear()
        try:
            con = get_connection()
            con.row_factory = None
            cur = con.cursor()
            cur.execute("SELECT id, number, name FROM incidents ORDER BY id DESC")
            rows: List[Tuple[int, str, str]] = cur.fetchall() or []
            for _id, number, name in rows:
                self._incidents.append(IncidentItem(id=int(_id), number=str(number), name=str(name or "")))
            con.close()
        except Exception as e:
            QMessageBox.warning(self, "Database Error", f"Failed to load incidents: {e}")
            self._incidents = []

        # Populate combo: show "Name — #Number"; store number as itemData
        for it in self._incidents:
            label = f"{it.name or '(unnamed)'} — #{it.number}"
            self.incident_combo.addItem(label, userData=it.number)

    def _on_create_new_incident(self) -> None:
        """Open the existing NewIncidentDialog, then register in master and refresh."""
        dlg = NewIncidentDialog(self)

        def _created(meta, db_path: str):
            try:
                # Register in master.db immediately so it appears in lists
                insert_new_incident(
                    number=meta.number,
                    name=meta.name,
                    type=meta.type,
                    description=meta.description,
                    icp_location=meta.location,
                    is_training=meta.is_training,
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to register incident: {e}")
            # Always refresh after dialog
            self._load_incidents()
            # Select the newly created incident by number if present
            idx = self.incident_combo.findData(meta.number)
            if idx >= 0:
                self.incident_combo.setCurrentIndex(idx)
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
            and (self.user_id_edit.text().strip() != "")
            and (self.role_combo.currentText().strip() != "")
        )
        self.btn_continue.setEnabled(ok)

    # ------------------------------------------------------------------
    def _accept(self) -> None:
        # Read selections
        incident_number = self.incident_combo.currentData()
        user_id = self.user_id_edit.text().strip() or ""
        role = self.role_combo.currentText().strip() or ""

        if not self._demo_mode:
            if not incident_number or not user_id or not role:
                QMessageBox.warning(self, "Missing Info", "Please select an incident and enter User ID and Role.")
                return

        # Persist to AppState (central session holder used across repo)
        AppState.set_active_incident(incident_number)
        AppState.set_active_user_id(user_id)
        AppState.set_active_user_role(role)

        try:
            # Optional: log the login event
            from utils.audit import log_action
            log_action("login", details="User opened session")
        except Exception:
            # Audit is best-effort; continue silently on failure
            pass

        # Signal and close
        self.sessionReady.emit(str(incident_number), user_id, role)
        self.accept()


__all__ = ["LoginDialog", "STATIC_ROLES"]

