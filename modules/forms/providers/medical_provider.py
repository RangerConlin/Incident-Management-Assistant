from .base_provider import StaticContextProvider


class MedicalProvider(StaticContextProvider):
    def __init__(self) -> None:
        super().__init__('medical', ['hospital.name', 'hospital.address', 'hospital.phone', 'medical_unit.location'])
