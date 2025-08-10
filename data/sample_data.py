# This Python file uses the following encoding: utf-8

# if __name__ == "__main__":
#     pass
from modules.operations.models.tasks import Task
from modules.operations.models.teams import Team

sample_tasks = [
    Task("T-001", "Ramp Check", "In Progress", "High", ["GT-Bravo"], "KTEW"),
    Task("T-002", "ELT Grid Search", "Planned", "Urgent", [], "NW Oakland Co"),
    Task("T-003", "Aerial Photography", "Complete", "Normal", ["CAP 2020"], "St. Claire Shoreline")
]

sample_teams = [
    Team("", "GT-Alpha", "Pheley, Brendan", "517-554-0085", "Available"),
    Team("G-023", "GT-Bravo", "Weeter, Danielle", "555-1234", "Enroute", "Ramp Check", "KTEW"),
    Team("A-026", "CAP 2020", "Orme, William", "555-1234", "Wheels Down", "Aerial Photography", "St. Claire Co Shoreline"),
    Team("G-026", "UDF Charlie", "Leannis, Lynn", "555-1234", "Arrival", "ELT Grid Search", "NW Oakland Co"),
    Team("", "GT-Delta", "Weeter, Danielle", "555-1234", "Out of Service")
]
