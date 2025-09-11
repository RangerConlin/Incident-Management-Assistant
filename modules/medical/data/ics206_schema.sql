CREATE TABLE IF NOT EXISTS ics206_aid_stations (
    id INTEGER PRIMARY KEY,
    name TEXT,
    type TEXT,
    level TEXT CHECK(level IN('MFR','BLS','ALS')),
    is_24_7 INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS ics206_ambulance (
    id INTEGER PRIMARY KEY,
    agency TEXT,
    level TEXT CHECK(level IN('MFR','BLS','ALS')),
    et_minutes INTEGER,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS ics206_hospitals (
    id INTEGER PRIMARY KEY,
    hospital TEXT,
    trauma_center TEXT,
    bed_cap INTEGER,
    phone_er TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    helipad_lat REAL,
    helipad_lon REAL
);

CREATE TABLE IF NOT EXISTS ics206_air_ambulance (
    id INTEGER PRIMARY KEY,
    provider TEXT,
    contact TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS ics206_procedures (
    id INTEGER PRIMARY KEY CHECK(id=1),
    notes TEXT
);

CREATE TABLE IF NOT EXISTS ics206_comms (
    id INTEGER PRIMARY KEY,
    function TEXT,
    channel TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS ics206_signatures (
    id INTEGER PRIMARY KEY CHECK(id=1),
    prepared_by TEXT,
    prepared_position TEXT,
    approved_by TEXT,
    signed_at TEXT
);
