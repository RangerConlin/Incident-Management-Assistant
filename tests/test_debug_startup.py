from __future__ import annotations


def test_debug_bypass_starts_local_server_before_incident_activation(monkeypatch, capsys):
    import main

    calls: list[tuple[str, str | None]] = []
    connection_manager = object()

    class FakeApp:
        def __init__(self) -> None:
            self._properties: dict[str, object] = {}

        def property(self, name: str) -> object | None:
            return self._properties.get(name)

    app = FakeApp()

    def fake_start_local_offline_mode(fake_app: FakeApp) -> bool:
        calls.append(("start_local", None))
        fake_app._properties["sarapp_connection_manager"] = connection_manager
        return True

    monkeypatch.setattr(main, "_start_local_offline_mode", fake_start_local_offline_mode)
    monkeypatch.setattr(
        main.AppState,
        "set_active_incident",
        staticmethod(lambda incident_id: calls.append(("incident", incident_id))),
    )
    monkeypatch.setattr(
        main.AppState,
        "set_active_user_id",
        staticmethod(lambda user_id: calls.append(("user", user_id))),
    )
    monkeypatch.setattr(
        main.AppState,
        "set_active_user_role",
        staticmethod(lambda role: calls.append(("role", role))),
    )

    result = main._activate_debug_bypass(app)  # type: ignore[arg-type]

    assert result is connection_manager
    assert calls == [
        ("start_local", None),
        ("incident", "2025-FAIR"),
        ("user", "405021"),
        ("role", "Incident Commander"),
    ]
    output = capsys.readouterr().out
    assert "Login bypass enabled" in output
    assert "Local offline startup failed" not in output
