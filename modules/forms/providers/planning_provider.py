from .base_provider import StaticContextProvider


class PlanningProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('planning', ['objectives.current'])
