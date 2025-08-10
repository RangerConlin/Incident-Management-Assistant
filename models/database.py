import sqlite3

DB_PATH = 'data/master.db'


def get_connection():
    return sqlite3.connect(DB_PATH)


def get_all_sqlite_sequence():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sqlite_sequence')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_ranks():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ranks')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_roles():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM roles')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_equipment():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM equipment')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_form_templates():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM form_templates')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_form_fields():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM form_fields')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_agency_contacts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM agency_contacts')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_task_templates():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM task_templates')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_settings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM settings')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_audit_log():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM audit_log')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_comms_resources():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM comms_resources')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_login():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM login')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_operationalperiods():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM operationalperiods')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_incident_objectives():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM incident_objectives')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_personnel():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM personnel')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_mission_types():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM mission_types')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_certification_types():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM certification_types')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_personnel_certifications():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM personnel_certifications')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_missions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM missions')
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_vehicles():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM vehicles')
    results = cursor.fetchall()
    conn.close()
    return results

def insert_new_mission(number, name, type, description, icp_location, is_training):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO missions (number, name, type, description, status, icp_location, start_time, end_time, is_training)
        VALUES (?, ?, ?, ?, 'Active', ?, datetime('now'), NULL, ?)
    ''', (number, name, type, description, icp_location, int(is_training)))
    conn.commit()
    mission_id = cursor.lastrowid
    conn.close()
    return mission_id

def get_all_active_missions():
    conn = get_connection()
    conn.row_factory = sqlite3.Row  # Makes rows behave like dictionaries
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM missions WHERE status = 'Active'")
    results = cursor.fetchall()
    conn.close()
    rows = [dict(row) for row in results]
    print("DEBUG ACTIVE MISSIONS:", rows[0] if rows else "None")
    return rows

def get_mission_by_id(mission_id):
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row #Allows access like a dictionary
    cursor = conn.cursor

    cursor.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
    row = cursor.fetchone()

    conn.close()
    if row:
        keys = [desc[0] for desc in cursor.description]
        return dict(zip(keys, row))
    return None

