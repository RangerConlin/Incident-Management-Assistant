import sqlite3
from pathlib import Path

# Set up base path (adjust this if needed to match your project)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MISSIONS_DIR = BASE_DIR / "data" / "missions"
MISSIONS_DIR.mkdir(parents=True, exist_ok=True)  # Ensure /data/missions exists

def create_mission_database(mission_name: str) -> Path:
    """
    Creates a new SQLite database file for a mission inside /data/missions/.
    Also initializes the Mission and OperationalPeriod tables.
    """
    db_path = MISSIONS_DIR / f"{mission_name}.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create Mission table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Mission (
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
            mission_id TEXT,
            number TEXT,
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY (mission_id) REFERENCES Mission(id)
        );
    """)

    conn.commit()
    conn.close()
    return db_path
