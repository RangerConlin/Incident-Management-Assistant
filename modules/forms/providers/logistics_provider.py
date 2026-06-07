from .base_provider import StaticContextProvider


class LogisticsProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('logistics', ['resource_request.requestor_name'])
