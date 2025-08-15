from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Task:
    number: str                  # e.g. "T-001"
    name: str                    # e.g. "Ramp Check"
    status: str                  # e.g. "In Progress"
    priority: str                # e.g. "High", "Urgent"
    assigned_teams: List[str] = field(default_factory=list)  # List of team names or IDs
    location: Optional[str] = None              # Optional text or coordinate label

    def __str__(self):
        return f"{self.number} - {self.name}"
