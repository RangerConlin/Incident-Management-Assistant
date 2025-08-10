import os

def ensure_mission_dir():
    mission_dir = os.path.abspath("data/missions")
    if not os.path.exists(mission_dir):
        os.makedirs(mission_dir)
    return mission_dir
