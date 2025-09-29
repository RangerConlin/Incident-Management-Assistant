from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QListWidget,
    QPushButton,
    QGridLayout,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
)

from modules.public_info.models.repository import PublicInfoRepository


TYPE_VALUES = ["PressRelease", "Advisory", "SituationUpdate"]
AUDIENCE_VALUES = ["Public", "Agency", "Internal"]


class EditorPanel(QWidget):
    def __init__(
        self,
        incident_id: str,
        current_user: Dict[str, Any],
        message_id: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.incident_id = str(incident_id)
        self.current_user = current_user
        self.message_id = message_id
        self.repo = PublicInfoRepository(self.incident_id)

        self.status = "Draft"
        self.revision = 1
        self.updated_at = ""
        self.author_id = current_user.get("id")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Meta bar
        self.meta_left = QLabel("Editor — Message (<b>New</b>) | Status: <b>Draft</b>")
        self.meta_right = QLabel("Author: —  Last Updated: —  Rev: —")
        meta = QHBoxLayout()
        meta.addWidget(self.meta_left)
        meta.addStretch()
        meta.addWidget(self.meta_right)
        root.addLayout(meta)

        # Form grid
        grid = QGridLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setMaxLength(140)
        self.type_combo = QComboBox()
        self.type_combo.addItems(TYPE_VALUES)
        self.audience_combo = QComboBox()
        self.audience_combo.addItems(AUDIENCE_VALUES)
        self.tags_edit = QLineEdit()
        grid.addWidget(QLabel("Title"), 0, 0)
        grid.addWidget(self.title_edit, 0, 1, 1, 3)
        grid.addWidget(QLabel("Type"), 1, 0)
        grid.addWidget(self.type_combo, 1, 1)
        grid.addWidget(QLabel("Audience"), 1, 2)
        grid.addWidget(self.audience_combo, 1, 3)
        grid.addWidget(QLabel("Tags"), 2, 0)
        grid.addWidget(self.tags_edit, 2, 1, 1, 3)
        root.addLayout(grid)

        # Body
        self.body_edit = QTextEdit()
        root.addWidget(self.body_edit)

        # Attachments stub
        attach_row = QHBoxLayout()
        attach_row.addWidget(QLabel("Attachments:"))
        self.attach_list = QListWidget()
        btn_add = QPushButton("+ Add")
        btn_remove = QPushButton("Remove")
        attach_row.addWidget(btn_add)
        attach_row.addWidget(btn_remove)
        root.addLayout(attach_row)
        root.addWidget(self.attach_list)

        # Bottom bar
        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_submit = QPushButton("Submit for Review")
        self.btn_approve = QPushButton("Approve")
        self.btn_publish = QPushButton("Publish")
        self.btn_archive = QPushButton("Archive")
        self.btn_preview = QPushButton("Preview")
        self.btn_close = QPushButton("Close")
        for b in [
            self.btn_save,
            self.btn_submit,
            self.btn_approve,
            self.btn_publish,
            self.btn_archive,
            self.btn_preview,
            self.btn_close,
        ]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.toast_label = QLabel("")
        self.toast_label.setStyleSheet("color:#666;")
        root.addWidget(self.toast_label)

        # Connect actions
        self.btn_save.clicked.connect(self.save)
        self.btn_submit.clicked.connect(self.submit_for_review)
        self.btn_approve.clicked.connect(self.approve)
        self.btn_publish.clicked.connect(self.publish)
        self.btn_archive.clicked.connect(self.archive)
        self.btn_preview.clicked.connect(self.preview)
        self.btn_close.clicked.connect(self.close_parent)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.submit_for_review)
        QShortcut(QKeySequence("A"), self, activated=self.approve)
        QShortcut(QKeySequence("U"), self, activated=self.publish)
        QShortcut(QKeySequence("X"), self, activated=self.archive)
        QShortcut(QKeySequence("P"), self, activated=self.preview)
        QShortcut(QKeySequence("Esc"), self, activated=self.close_parent)

        # Load message if editing
        if self.message_id is not None:
            self.load_message(self.message_id)
        self.update_buttons()

    # Utility
    def toast(self, text: str) -> None:
        self.toast_label.setText(text)

    def close_parent(self) -> None:
        w = self.window()
        if w is not None:
            w.close()

    def gather_data(self) -> Dict[str, Any]:
        return {
            "title": self.title_edit.text().strip(),
            "body": self.body_edit.toPlainText().strip(),
            "type": self.type_combo.currentText(),
            "audience": self.audience_combo.currentText(),
            "tags": self.tags_edit.text().strip() or None,
            "created_by": self.current_user.get("id"),
        }

    def load_message(self, message_id: int) -> None:
        msg = self.repo.get_message(message_id)
        if not msg:
            self.toast("Message not found")
            return
        self.message_id = msg.get("id")
        self.status = msg.get("status", "Draft")
        self.revision = msg.get("revision", 1)
        self.updated_at = msg.get("updated_at", "")
        self.author_id = msg.get("created_by")

        self.title_edit.setText(msg.get("title", ""))
        t = msg.get("type", TYPE_VALUES[0])
        a = msg.get("audience", AUDIENCE_VALUES[0])
        self.type_combo.setCurrentText(t)
        self.audience_combo.setCurrentText(a)
        self.tags_edit.setText(msg.get("tags", "") or "")
        self.body_edit.setPlainText(msg.get("body", ""))

        self.meta_left.setText(
            f"Editor — Message (<b>#{self.message_id}</b>) | Status: <b>{self.status}</b>"
        )
        author_txt = str(self.author_id) if self.author_id is not None else "—"
        self.meta_right.setText(f"Author: {author_txt}  Last Updated: {self.updated_at or '—'}  Rev: {self.revision}")
        self.update_buttons()

    def update_buttons(self) -> None:
        roles = set(self.current_user.get("roles", []))
        status = self.status
        self.btn_save.setEnabled(status in {"Draft", "InReview"})
        self.btn_submit.setEnabled(status == "Draft")
        self.btn_approve.setEnabled(status == "InReview" and bool(roles.intersection({"PIO", "LeadPIO", "IC"})))
        self.btn_publish.setEnabled(status == "Approved" and bool(roles.intersection({"LeadPIO", "IC"})))
        self.btn_archive.setEnabled(status == "Published" and bool(roles.intersection({"LeadPIO", "IC"})))

    # Validation
    def _validate(self) -> Optional[str]:
        data = self.gather_data()
        if not data["title"]:
            return "Title is required"
        if not data["body"]:
            return "Body is required"
        if data["type"] not in TYPE_VALUES:
            return "Type is required"
        if data["audience"] not in AUDIENCE_VALUES:
            return "Audience is required"
        return None

    # Slots
    def save(self) -> None:
        err = self._validate()
        if err:
            self.toast(err)
            return
        try:
            if self.message_id is None:
                msg = self.repo.create_message(self.gather_data())
                self.toast("Saved new draft")
            else:
                msg = self.repo.update_message(self.message_id, self.gather_data(), self.current_user.get("id"), "Saved")
                self.toast("Saved")
            if msg:
                self.load_message(int(msg.get("id")))
        except Exception as e:
            self.toast(str(e))

    def submit_for_review(self) -> None:
        if self.message_id is None:
            self.toast("Save draft before submitting")
            return
        try:
            msg = self.repo.submit_for_review(self.message_id, self.current_user.get("id"))
            if msg:
                self.load_message(int(msg.get("id")))
            self.toast("Submitted for review")
        except Exception as e:
            self.toast(str(e))

    def approve(self) -> None:
        if self.message_id is None:
            self.toast("No message to approve")
            return
        try:
            msg = self.repo.approve_message(self.message_id, self.current_user)
            if msg:
                self.load_message(int(msg.get("id")))
            self.toast("Approved")
        except PermissionError as e:
            self.toast("Permission denied: " + str(e))
        except Exception as e:
            self.toast(str(e))

    def publish(self) -> None:
        if self.message_id is None:
            self.toast("No message to publish")
            return
        m = QMessageBox(self)
        m.setWindowTitle("Confirm Publish")
        m.setText("Publish this message to the history?")
        m.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if m.exec() != QMessageBox.Yes:
            return
        try:
            msg = self.repo.publish_message(self.message_id, self.current_user)
            if msg:
                self.load_message(int(msg.get("id")))
            self.toast("Published")
        except PermissionError as e:
            self.toast("Permission denied: " + str(e))
        except Exception as e:
            self.toast(str(e))

    def archive(self) -> None:
        if self.message_id is None:
            self.toast("No message to archive")
            return
        m = QMessageBox(self)
        m.setWindowTitle("Confirm Archive")
        m.setText("Archive this published message?")
        m.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if m.exec() != QMessageBox.Yes:
            return
        try:
            msg = self.repo.archive_message(self.message_id, self.current_user.get("id"))
            if msg:
                self.load_message(int(msg.get("id")))
            self.toast("Archived")
        except PermissionError as e:
            self.toast("Permission denied: " + str(e))
        except Exception as e:
            self.toast(str(e))

    def preview(self) -> None:
        data = self.gather_data() if self.message_id is None else self.repo.get_message(self.message_id) or {}
        title = data.get("title", "(Untitled)")
        body = data.get("body", "")
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Preview — {title}")
        v = QVBoxLayout(dlg)
        meta = QLabel(
            f"Type: {data.get('type','')}  •  Audience: {data.get('audience','')}  •  Status: {self.status}"
        )
        v.addWidget(meta)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(body)
        v.addWidget(te)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        v.addWidget(bb)
        dlg.resize(700, 500)
        dlg.exec()

