"""Light weight data models used by the check-in module.

The models intentionally mirror the placeholder database schemas and
contain only a subset of fields.  Each model is a dataclass to keep the
code concise while still being explicit about the attributes present.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Personnel:
    id: str
    first_name: str
    last_name: str
    callsign: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


@dataclass
class Equipment:
    id: str
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None


@dataclass
class Vehicle:
    id: str
    name: str
    type: Optional[str] = None
    status: Optional[str] = None
    callsign: Optional[str] = None
    assigned_to: Optional[str] = None


@dataclass
class Aircraft:
    id: str
    tail_number: str
    type: Optional[str] = None
    status: Optional[str] = None
    callsign: Optional[str] = None
    assigned_to: Optional[str] = None
