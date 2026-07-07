"""Connection settings page (cloud fallback server / reverse-tunnel router)."""

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QWidget

from ..binding import bind_lineedit


class ConnectionPage(QWidget):
    """Cloud fallback configuration used when no LAN server is discovered.

    The cloud server URL may point directly at a SARApp server, or at a cloud
    reverse-tunnel router. When a connect code is set, startup connectivity
    appends the router's /r/<code> tunnel path to the URL. Changes apply on
    the next launch or connection retry; SARAPP_CLOUD_URL overrides both.
    """

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        cloud_url = QLineEdit()
        cloud_url.setPlaceholderText("https://cloud-router.example (blank = built-in default)")
        bind_lineedit(cloud_url, bridge, "cloudServerUrl", "")
        layout.addRow("Cloud server URL:", cloud_url)

        connect_code = QLineEdit()
        connect_code.setPlaceholderText("e.g. ABCD-1234 (blank = connect to URL directly)")
        bind_lineedit(connect_code, bridge, "cloudConnectCode", "", normalize=str.upper)
        layout.addRow("Connect code:", connect_code)

        note = QLabel(
            "The connect code identifies one incident command post's server on the "
            "cloud router — get it from the IC or the SARApp Server Console. "
            "Changes take effect on the next launch or connection retry."
        )
        note.setWordWrap(True)
        layout.addRow(note)
