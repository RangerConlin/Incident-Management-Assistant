from pathlib import Path

_active_incident_id = None


def set_active_incident_id(value: str):
    global _active_incident_id
    _active_incident_id = value


def get_active_incident_id():
    return _active_incident_id


def create_incident_database(incident_name: str) -> Path:
    base = Path("data") / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    db_path = base / f"{incident_name}.db"
    if not db_path.exists():
        db_path.touch()
    return db_path
