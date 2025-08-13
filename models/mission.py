from dataclasses import dataclass
from typing import Optional


@dataclass
class Mission:
    id: Optional[int]
    number: str
    name: str
    type: str  # e.g., "Search and Rescue", "Disaster Relief"
    description: str
    status: str  # e.g., "Active", "Closed", etc.
    icp_location: str
    start_time: Optional[str]
    end_time: Optional[str]
    is_training: bool  # Boolean

    def __str__(self):
        return f"{self.name} ({self.status})"

