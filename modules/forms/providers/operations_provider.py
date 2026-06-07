from .base_provider import StaticContextProvider


class OperationsProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('operations', ['task.title', 'task.description', 'task.priority', 'task.location', 'task.primary_team.name', 'task.primary_team.leader', 'task.primary_team.leader_phone', 'task.assigned_personnel', 'task.assigned_vehicles'])
