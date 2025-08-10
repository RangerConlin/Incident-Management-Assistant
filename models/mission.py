class Mission:
    def __init__(self, id, number, name, type, description, status, icp_location, start_time, end_time, is_training):
        self.id = id
        self.number = number
        self.name = name
        self.type = type  # e.g., "Search and Rescue", "Disaster Relief"
        self.description = description
        self.status = status  # e.g., "Active", "Closed", etc.
        self.icp_location = icp_location
        self.start_time = start_time
        self.end_time = end_time
        self.is_training = is_training  # Boolean

    def __str__(self):
        return f"{self.name} ({self.status})"
