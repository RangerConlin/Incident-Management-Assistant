"""Development launcher for the Forms Creator hub."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.HubWindow import HubWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = HubWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - manual launch helper
    raise SystemExit(main())
