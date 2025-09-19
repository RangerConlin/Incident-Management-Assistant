"""Development launcher for the form creator workspace."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.MainWindow import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - manual launch helper
    raise SystemExit(main())
