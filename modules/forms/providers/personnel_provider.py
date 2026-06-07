from .base_provider import StaticContextProvider


class PersonnelProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('personnel', ['current_user.name', 'current_user.id', 'current_user.role', 'by_id.name', 'by_id.phone', 'by_id.organization'])
