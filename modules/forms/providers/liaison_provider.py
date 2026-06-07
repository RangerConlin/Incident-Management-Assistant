from .base_provider import StaticContextProvider


class LiaisonProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('liaison', [])
