import sqlite3
from pathlib import Path

# Set up base path (adjust this if needed to match your project)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
INCIDENTS_DIR = BASE_DIR / "data" / "incidents"
INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)  # Ensure /data/incidents exists

def create_incident_database(incident_name: str) -> Path:
    """
    Creates a new SQLite database file for a incident inside /data/incidents/.
    Also initializes the Incident and OperationalPeriod tables.
    """
    db_path = INCIDENTS_DIR / f"{incident_name}.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create Incident table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Incident (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT,
            description TEXT,
            status TEXT,
            location TEXT,
            start_time TEXT,
            end_time TEXT,
            is_training BOOLEAN
        );
    """)

    # Create OperationalPeriod table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS OperationalPeriod (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT,
            number TEXT,
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (incident_id) REFERENCES Incident(id)
        );
    """)

    conn.commit()
    conn.close()
    return db_path
