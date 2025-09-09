-- Optional placeholder tables for master.db

-- ems
CREATE TABLE IF NOT EXISTS ems (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT,
  phone TEXT, fax TEXT, email TEXT, contact TEXT,
  address TEXT, city TEXT, state TEXT, zip TEXT,
  notes TEXT,
  is_active INTEGER DEFAULT 1
);

-- hospitals
CREATE TABLE IF NOT EXISTS hospitals (
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
);

-- canned_comm_entries
CREATE TABLE IF NOT EXISTS canned_comm_entries (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  category TEXT,
  body TEXT NOT NULL,
  delivery_channels TEXT,
  notes TEXT,
  is_active INTEGER DEFAULT 1
);

-- task_types
CREATE TABLE IF NOT EXISTS task_types (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  category TEXT,
  description TEXT,
  is_active INTEGER DEFAULT 1
);

-- team_types
CREATE TABLE IF NOT EXISTS team_types (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  is_active INTEGER DEFAULT 1
);

-- safety_templates
CREATE TABLE IF NOT EXISTS safety_templates (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  operational_context TEXT,
  hazard TEXT NOT NULL,
  controls TEXT NOT NULL,
  residual_risk TEXT,
  ppe TEXT,
  notes TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

