from dataclasses import dataclass


@dataclass
class Team:
    sortie: str        # e.g. "G-023"
    name: str          # e.g. "GT-Bravo"
    leader: str        # e.g. "Weeter, Danielle"
    contact: str       # e.g. "555-1234"
    status: str        # e.g. "Enroute"
    assignment: str = ""  # e.g. "Ramp Check"
    location: str = ""    # e.g. "KTEW"

    def __str__(self):
        return f"{self.name} ({self.sortie})"
