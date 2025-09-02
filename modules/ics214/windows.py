from pathlib import Path

__all__ = ["get_ics214_panel"]


def get_ics214_panel(incident_id: object | None = None):
    """Return QWidget hosting the ICS-214 Activity Log QML panel."""
    from models.qmlwindow import QmlWindow

    qml_path = Path(__file__).resolve().parent / "qml" / "Ics214Home.qml"
    return QmlWindow(str(qml_path), "ICS-214 Activity Log")
