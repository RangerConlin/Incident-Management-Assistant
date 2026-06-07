from .base_provider import StaticContextProvider


class CommunicationsProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('communications', ['channel.name', 'channel.zone', 'channel.rx_frequency', 'channel.tx_frequency', 'channel.mode', 'channel.remarks'])
