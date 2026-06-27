try:  # pragma: no cover - exercised when PySide6 is available
    from .windows import get_facilities_manager_panel
    from .widgets import FacilityPicker, PersonnelPicker
except Exception:  # pragma: no cover - headless test fallback
    def get_facilities_manager_panel(*_args, **_kwargs):  # type: ignore[override]
        raise RuntimeError("Facilities UI requires PySide6")
    def FacilityPicker(*_args, **_kwargs):  # type: ignore[override]
        raise RuntimeError("Facilities UI requires PySide6")
    def PersonnelPicker(*_args, **_kwargs):  # type: ignore[override]
        raise RuntimeError("Facilities UI requires PySide6")

__all__ = ["FacilityPicker", "PersonnelPicker", "get_facilities_manager_panel"]
