"""The personal check-in QR code shown by the mobile app.

The mobile app displays a QR encoding ``SARAPP:CHECKIN:v1:<person_id>`` (see
``lib/utils/check_in_qr.dart`` in the mobile repo, which must stay in step
with this prefix).  A plain prefixed string is used instead of JSON because
hardware QR scanners commonly act as keyboards, and braces/quotes are the
characters most often mangled by keyboard layouts.  Only the visible person
ID is encoded; the desk still resolves it against the roster.
"""
from __future__ import annotations

CHECKIN_QR_PREFIX = "SARAPP:CHECKIN:v1:"


def parse_checkin_code(text: str) -> str | None:
    """Return the person ID inside a scanned check-in code, else ``None``.

    ``None`` means the text is not a check-in code (e.g. a typed name or a
    plain ID), so callers should treat it as an ordinary search term.
    """

    value = (text or "").strip()
    if not value.upper().startswith(CHECKIN_QR_PREFIX.upper()):
        return None
    person_id = value[len(CHECKIN_QR_PREFIX):].strip()
    return person_id or None
