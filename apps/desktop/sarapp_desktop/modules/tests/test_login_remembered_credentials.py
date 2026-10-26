from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from modules.login_dialog import LoginDialog
from utils.secure_storage import decrypt_secret, dpapi_available


class _Settings:
    def __init__(self, values: dict | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value) -> None:
        self.values[key] = value


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_remember_login_defaults_on_for_new_and_upgraded_users() -> None:
    app = _app()
    settings = _Settings()

    dialog = LoginDialog(api_available=False, settings_manager=settings)

    assert dialog.chk_remember.isChecked()
    dialog.close()
    app.processEvents()


def test_explicit_remember_login_opt_out_is_preserved() -> None:
    app = _app()
    settings = _Settings({"rememberLogin": False})

    dialog = LoginDialog(api_available=False, settings_manager=settings)

    assert not dialog.chk_remember.isChecked()
    dialog.close()
    app.processEvents()


@pytest.mark.skipif(not dpapi_available(), reason="Windows DPAPI is unavailable")
def test_successful_login_preference_encrypts_and_restores_password() -> None:
    app = _app()
    settings = _Settings()
    first = LoginDialog(api_available=False, settings_manager=settings)

    first._save_remember_preference("person-7", "Planning Staff", "correct horse")

    assert settings.get("rememberLogin") is True
    assert settings.get("rememberedPassword") != "correct horse"
    assert decrypt_secret(settings.get("rememberedPassword")) == "correct horse"

    second = LoginDialog(api_available=False, settings_manager=settings)
    assert second.username_edit.text() == "person-7"
    assert second.password_edit.text() == "correct horse"
    assert second.role_combo.currentText() == "Planning Staff"

    first.close()
    second.close()
    app.processEvents()
