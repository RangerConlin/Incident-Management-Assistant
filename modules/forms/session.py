"""Dataclasses used when editing a form instance.

The :class:`FormSession` object tracks the template used for the session as
well as any user supplied values.  A key design requirement of the new export
pipeline is that a session pins the template via a globally unique
``template_uid`` so that exports are deterministic and independent from later
template changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Any


@dataclass
class FormSession:
    """State for an in-progress form editing session.

    Attributes
    ----------
    instance_id:
        Random identifier (typically :func:`uuid.uuid4`) used to track the
        session.  It is stored as a string to avoid imposing a UUID dependency
        on consumers of the class.
    template_uid:
        Identifier of the template this session is bound to, in the form
        ``"<profile>:<form_id>@<version>"``.
    values:
        Mapping of field keys to user supplied values.  Only explicit edits are
        stored here; any auto-populated values are recomputed on export.
    created_at / last_saved_at:
        Timestamps useful for draft management.
    """

    instance_id: str
    template_uid: str
    values: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_saved_at: Optional[datetime] = None


__all__ = ["FormSession"]

