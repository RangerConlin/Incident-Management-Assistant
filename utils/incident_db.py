from pathlib import Path

_active_incident_id = None


def set_active_incident_id(value: str):
    global _active_incident_id
    _active_incident_id = value


def get_active_incident_id():
    return _active_incident_id


def create_incident_database(incident_number: str) -> Path:
    """Create an incident database named after the incident number.

    The file will be created at data/incidents/<incident_number>.db. If a file
    with that name already exists, a FileExistsError is raised and nothing is
    modified.
    """
    base = Path("data") / "incidents"
    base.mkdir(parents=True, exist_ok=True)
    # Use the raw number to keep 1:1 mapping; light sanitation for filesystem
    safe_number = str(incident_number).strip().replace("/", "-")
    db_path = base / f"{safe_number}.db"
    if db_path.exists():
        raise FileExistsError(f"Incident database already exists: {db_path}")
    db_path.touch()
    return db_path
