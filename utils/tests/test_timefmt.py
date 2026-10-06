from __future__ import annotations

from utils import timefmt


class _Settings:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self, key: str, default=None):
        assert key == timefmt.DISPLAY_TIMEZONE_SETTING
        return self.value or default


def test_format_display_datetime_uses_configured_timezone(monkeypatch) -> None:
    monkeypatch.setattr(
        "utils.settingsmanager.SettingsManager",
        lambda: _Settings("America/Los_Angeles"),
    )

    text = timefmt.format_display_datetime(
        "2026-10-03T11:00:00+00:00",
        include_seconds=True,
    )

    assert text == "10/03/2026 04:00:00"


def test_format_display_datetime_can_show_timezone_abbreviation(monkeypatch) -> None:
    monkeypatch.setattr(
        "utils.settingsmanager.SettingsManager",
        lambda: _Settings("America/New_York"),
    )

    text = timefmt.format_display_datetime(
        "2026-10-03T11:00:00Z",
        include_seconds=True,
        include_timezone=True,
    )

    assert text == "10/03/2026 07:00:00 EDT"


def test_invalid_display_timezone_falls_back_to_system(monkeypatch) -> None:
    monkeypatch.setattr(
        "utils.settingsmanager.SettingsManager",
        lambda: _Settings("Not/AZone"),
    )

    assert timefmt.get_display_timezone_key() == timefmt.SYSTEM_TIMEZONE_KEY
