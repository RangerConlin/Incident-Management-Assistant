"""Former hardcoded validation profiles — now a one-time migration seed only.

As of 2026-10-10 the qualification catalog lives in Mongo
(`MasterCollections.QUALIFICATION_TYPES`, see
`data/db/sarapp_db/api/routers/qualification_types.py`), a central-catalog
-authoritative "lockdown" collection like `certification_types`. This module
is kept only as the source `PROFILES` that
`data/db/sarapp_db/migrations/seed_qualification_types_from_hardcoded_profiles.py`
seeded that collection from. No application code imports `PROFILES`/
`get_profile` anymore — see `Design Documents/legacycode.md`.

Profiles declare tags that qualify a person for a role. The catalog computes
whether a person meets a profile by checking the highest level per cert
and enforcing the profile's minimum level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple


PROFILES_VERSION = "1.0.0"


@dataclass(frozen=True)
class QualProfile:
    code: str
    name: str
    any_tags: Tuple[str, ...] = tuple()
    all_tags: Tuple[str, ...] = tuple()
    min_level: int = 2


PROFILES: Tuple[QualProfile, ...] = (
    QualProfile("LSAR_TEAM_LEADER", "LSAR Team Leader", any_tags=("LSAR_TL",), min_level=2),
    QualProfile("MEDICAL_PROVIDER", "Medical Provider (Field)", any_tags=("MEDIC",), min_level=2),
    QualProfile("COMMS_OPERATOR", "Communications Operator", any_tags=("RADIO",), min_level=2),
)


def get_profile(code: str) -> QualProfile | None:
    for p in PROFILES:
        if p.code == code:
            return p
    return None


__all__ = ["PROFILES_VERSION", "QualProfile", "PROFILES", "get_profile"]
