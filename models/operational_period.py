class OperationalPeriod:
    def __init__(self, id, mission_id, number, start_time, end_time):
        self.id = id
        self.mission_id = mission_id
        self.number = number  # OP number, e.g., 1, 2, 3...
        self.start_time = start_time
        self.end_time = end_time

    def __str__(self):
        return f"OP {self.number} ({self.start_time} → {self.end_time})"
