from .base_provider import StaticContextProvider


class IntelProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('intel', [])
