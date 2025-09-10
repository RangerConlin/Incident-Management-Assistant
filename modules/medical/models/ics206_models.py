"""Dataclasses representing ICS 206 resources.

The structures mirror the tables used by :mod:`bridge.medical_bridge` and are
simple containers intended for JSON serialisation when exposed to QML.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Return a JSON-serialisable ``dict`` for *obj*."""
    return asdict(obj)


@dataclass
class AidStation:
    id: Optional[int]
    op_period: int
    name: str = ""
    type: str = ""
    level: str = ""
    is_24_7: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - simple proxy
        return _to_dict(self)


@dataclass
class AmbulanceService:
    id: Optional[int]
    op_period: int
    name: str = ""
    type: str = ""
    phone: str = ""
    location: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - simple proxy
        return _to_dict(self)


@dataclass
class Hospital:
    id: Optional[int]
    op_period: int
    name: str = ""
    address: str = ""
    phone: str = ""
    helipad: bool = False
    burn_center: bool = False
    level: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - simple proxy
        return _to_dict(self)


@dataclass
class AirAmbulance:
    id: Optional[int]
    op_period: int
    name: str = ""
    phone: str = ""
    base: str = ""
    contact: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - simple proxy
        return _to_dict(self)


@dataclass
class MedicalCommunication:
    id: Optional[int]
    op_period: int
    channel: str = ""
    function: str = ""
    frequency: str = ""
    mode: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - simple proxy
        return _to_dict(self)


@dataclass
class Procedure:
    id: Optional[int]
    op_period: int
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - simple proxy
        return _to_dict(self)


@dataclass
class Ics206Signature:
    id: Optional[int]
    op_period: int
    prepared_by: str = ""
    position: str = ""
    approved_by: str = ""
    date: str = ""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - simple proxy
        return _to_dict(self)


__all__ = [
    "AidStation",
    "AmbulanceService",
    "Hospital",
    "AirAmbulance",
    "MedicalCommunication",
    "Procedure",
    "Ics206Signature",
]
