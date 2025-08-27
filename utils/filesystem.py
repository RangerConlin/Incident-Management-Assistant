import os

def ensure_incident_dir():
    incident_dir = os.path.abspath("data/incidents")
    if not os.path.exists(incident_dir):
        os.makedirs(incident_dir)
    return incident_dir
