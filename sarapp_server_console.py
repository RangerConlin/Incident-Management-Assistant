"""Entry point for the SARApp Server Console Qt Widgets application."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from server.server_console.console_window import ServerConsoleWindow


def main() -> int:
    """Start the console without assuming any specific working directory."""

    app = QApplication(sys.argv)
    window = ServerConsoleWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
