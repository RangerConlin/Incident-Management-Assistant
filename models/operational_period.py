class OperationalPeriod:
    def __init__(self, id, incident_id, number, start_time, end_time):
        self.id = id
        self.incident_id = incident_id
        self.number = number  # OP number, e.g., 1, 2, 3...
        self.start_time = start_time
        self.end_time = end_time

    def __str__(self):
        return f"OP {self.number} ({self.start_time} → {self.end_time})"
