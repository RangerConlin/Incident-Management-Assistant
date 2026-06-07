from .base_provider import StaticContextProvider


class FinanceProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('finance', [])
