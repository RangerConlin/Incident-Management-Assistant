from .base_provider import StaticContextProvider


class IncidentProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('incident', ['name', 'number', 'type', 'icp_location', 'operational_period.current.name', 'operational_period.current.start', 'operational_period.current.end'])
