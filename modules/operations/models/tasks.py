# models/tasks.py

class Task:
    def __init__(self, number, name, status, priority, assigned_teams=None, location=None):
        self.number = number                  # e.g. "T-001"
        self.name = name                      # e.g. "Ramp Check"
        self.status = status                  # e.g. "In Progress"
        self.priority = priority              # e.g. "High", "Urgent"
        self.assigned_teams = assigned_teams or []  # List of team names or IDs
        self.location = location              # Optional text or coordinate label

    def __str__(self):
        return f"{self.number} - {self.name}"
