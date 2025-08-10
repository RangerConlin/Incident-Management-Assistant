class Team:
    def __init__(self, sortie, name, leader, contact, status, assignment="", location=""):
        self.sortie = sortie        # e.g. "G-023"
        self.name = name            # e.g. "GT-Bravo"
        self.leader = leader        # e.g. "Weeter, Danielle"
        self.contact = contact      # e.g. "555-1234"
        self.status = status        # e.g. "Enroute"
        self.assignment = assignment  # e.g. "Ramp Check"
        self.location = location      # e.g. "KTEW"

    def __str__(self):
        return f"{self.name} ({self.sortie})"
