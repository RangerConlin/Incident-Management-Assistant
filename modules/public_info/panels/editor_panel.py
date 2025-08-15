from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QPushButton,
    QMessageBox,
)

from ..models.repository import PublicInfoRepository


class EditorPanel(QWidget):
    """Editor panel for creating and managing a PIO message."""

    def __init__(self, mission_id: str, current_user: dict, message_id: int | None = None, parent=None):
        super().__init__(parent)
        self.repo = PublicInfoRepository(mission_id)
        self.current_user = current_user
        self.message_id = message_id
        self.message = self.repo.get_message(message_id) if message_id else None

        layout = QVBoxLayout(self)

        self.title_edit = QLineEdit()
        layout.addWidget(QLabel("Title"))
        layout.addWidget(self.title_edit)

        self.type_combo = QComboBox()
        for t in ["PressRelease", "Advisory", "SituationUpdate"]:
            self.type_combo.addItem(t, t)
        layout.addWidget(QLabel("Type"))
        layout.addWidget(self.type_combo)

        self.audience_combo = QComboBox()
        for a in ["Public", "Agency", "Internal"]:
            self.audience_combo.addItem(a, a)
        layout.addWidget(QLabel("Audience"))
        layout.addWidget(self.audience_combo)

        self.tags_edit = QLineEdit()
        layout.addWidget(QLabel("Tags"))
        layout.addWidget(self.tags_edit)

        self.body_edit = QTextEdit()
        layout.addWidget(QLabel("Body"))
        layout.addWidget(self.body_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save)
        btn_layout.addWidget(self.save_btn)

        self.submit_btn = QPushButton("Submit for Review")
        self.submit_btn.clicked.connect(self.submit_for_review)
        btn_layout.addWidget(self.submit_btn)

        self.approve_btn = QPushButton("Approve")
        self.approve_btn.clicked.connect(self.approve)
        btn_layout.addWidget(self.approve_btn)

        self.publish_btn = QPushButton("Publish")
        self.publish_btn.clicked.connect(self.publish)
        btn_layout.addWidget(self.publish_btn)

        self.archive_btn = QPushButton("Archive")
        self.archive_btn.clicked.connect(self.archive)
        btn_layout.addWidget(self.archive_btn)

        layout.addLayout(btn_layout)

        if self.message:
            self.load_message()
        self.update_buttons()

    def load_message(self):
        msg = self.message
        self.title_edit.setText(msg["title"])
        self.body_edit.setPlainText(msg["body"])
        self.type_combo.setCurrentText(msg["type"])
        self.audience_combo.setCurrentText(msg["audience"])
        self.tags_edit.setText(msg.get("tags") or "")

    def gather_data(self):
        return {
            "title": self.title_edit.text(),
            "body": self.body_edit.toPlainText(),
            "type": self.type_combo.currentData(),
            "audience": self.audience_combo.currentData(),
            "tags": self.tags_edit.text() or None,
            "created_by": self.current_user["id"],
        }

    def save(self):
        data = self.gather_data()
        if self.message_id:
            self.message = self.repo.update_message(self.message_id, data, self.current_user["id"], "Saved")
        else:
            self.message = self.repo.create_message(data)
            self.message_id = self.message["id"]
        QMessageBox.information(self, "Saved", "Message saved")
        self.update_buttons()

    def submit_for_review(self):
        if not self.message_id:
            return
        self.message = self.repo.submit_for_review(self.message_id, self.current_user["id"])
        self.update_buttons()

    def approve(self):
        if not self.message_id:
            return
        self.message = self.repo.approve_message(self.message_id, self.current_user)
        self.update_buttons()

    def publish(self):
        if not self.message_id:
            return
        self.message = self.repo.publish_message(self.message_id, self.current_user)
        self.update_buttons()

    def archive(self):
        if not self.message_id:
            return
        self.message = self.repo.archive_message(self.message_id, self.current_user["id"])
        self.update_buttons()

    def update_buttons(self):
        status = self.message["status"] if self.message else "Draft"
        self.submit_btn.setEnabled(status == "Draft")
        self.approve_btn.setEnabled(status == "InReview" and any(r in self.current_user.get("roles", []) for r in ["PIO", "LeadPIO", "IC"]))
        self.publish_btn.setEnabled(status == "Approved" and any(r in self.current_user.get("roles", []) for r in ["LeadPIO", "IC"]))
        self.archive_btn.setEnabled(status == "Published")
