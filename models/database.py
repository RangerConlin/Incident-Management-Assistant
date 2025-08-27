import sqlite3
from contextlib import contextmanager

DB_PATH = 'data/master.db'


def get_connection():
    return sqlite3.connect(DB_PATH)


@contextmanager
def get_cursor():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        yield cursor


def get_all_sqlite_sequence():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM sqlite_sequence')
        return cursor.fetchall()

def get_all_ranks():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM ranks')
        return cursor.fetchall()

def get_all_roles():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM roles')
        return cursor.fetchall()

def get_all_equipment():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM equipment')
        return cursor.fetchall()

def get_all_form_templates():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM form_templates')
        return cursor.fetchall()

def get_all_form_fields():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM form_fields')
        return cursor.fetchall()

def get_all_agency_contacts():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM agency_contacts')
        return cursor.fetchall()

def get_all_task_templates():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM task_templates')
        return cursor.fetchall()

def get_all_users():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM users')
        return cursor.fetchall()

def get_all_settings():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM settings')
        return cursor.fetchall()

def get_all_audit_log():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM audit_log')
        return cursor.fetchall()

def get_all_comms_resources():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM comms_resources')
        return cursor.fetchall()

def get_all_login():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM login')
        return cursor.fetchall()

def get_all_operationalperiods():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM operationalperiods')
        return cursor.fetchall()

def get_all_incident_objectives():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM incident_objectives')
        return cursor.fetchall()

def get_all_personnel():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM personnel')
        return cursor.fetchall()

def get_all_incident_types():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM incident_types')
        return cursor.fetchall()

def get_all_certification_types():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM certification_types')
        return cursor.fetchall()

def get_all_personnel_certifications():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM personnel_certifications')
        return cursor.fetchall()

def get_all_incidents():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM incidents')
        return cursor.fetchall()

def get_all_vehicles():
    with get_cursor() as cursor:
        cursor.execute('SELECT * FROM vehicles')
        return cursor.fetchall()

def insert_new_incident(number, name, type, description, icp_location, is_training):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO incidents (number, name, type, description, status, icp_location, start_time, end_time, is_training)
        VALUES (?, ?, ?, ?, 'Active', ?, datetime('now'), NULL, ?)
    ''', (number, name, type, description, icp_location, int(is_training)))
    conn.commit()
    incident_id = cursor.lastrowid
    conn.close()
    return incident_id

def get_all_active_incidents():
    conn = get_connection()
    conn.row_factory = sqlite3.Row  # Makes rows behave like dictionaries
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE status = 'Active'")
    results = cursor.fetchall()
    conn.close()
    rows = [dict(row) for row in results]
    print("DEBUG ACTIVE INCIDENTS:", rows[0] if rows else "None")
    return rows

def get_incident_by_number(incident_number):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows access like a dictionary
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM incidents WHERE number = ?", (incident_number,))
    row = cursor.fetchone()
    description = cursor.description
    conn.close()

    if row:
        keys = [desc[0] for desc in description]
        return dict(zip(keys, row))
    return None

