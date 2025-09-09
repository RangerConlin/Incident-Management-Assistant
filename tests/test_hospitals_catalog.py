import sqlite3
from pathlib import Path
import sys

import pytest

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bridge.catalog_bridge import CatalogBridge


def _create_tables(conn):
    conn.execute(
        """
        CREATE TABLE hospitals (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            contact_name TEXT,
            phone_er TEXT,
            phone_switchboard TEXT,
            travel_time_min INTEGER,
            helipad INTEGER,
            trauma_level TEXT,
            burn_center INTEGER,
            pediatric_capability INTEGER,
            bed_available INTEGER,
            diversion_status TEXT,
            ambulance_radio_channel TEXT,
            notes TEXT,
            lat REAL,
            lon REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE ems (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT,
            phone TEXT,
            fax TEXT,
            email TEXT,
            contact TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            notes TEXT,
            is_active INTEGER DEFAULT 1
        )
        """
    )
    conn.commit()


def test_catalog_bridge_hospital_isolated(tmp_path):
    db = tmp_path / "test.db"
    con = sqlite3.connect(db)
    _create_tables(con)
    bridge = CatalogBridge(str(db))

    new_id = bridge.createHospital({"name": "General Hospital"})
    assert new_id > 0

    hospitals = bridge.listHospitals("")
    assert hospitals and hospitals[0]["name"] == "General Hospital"

    ems_rows = bridge.listEms("")
    assert ems_rows == []
