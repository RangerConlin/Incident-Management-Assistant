from __future__ import annotations

from datetime import datetime
import re
from typing import Iterable

from sqlmodel import Session

from .models.comms_models import MessageLogEntry
from .repository import get_incident_engine
from modules.operations.teams.data import repository as team_repo


def _reset_comm_timers(text: str) -> None:
    """Reset communication timers for any teams matching ``text``."""
    if not text:
        return
    # Split on common delimiters but preserve full tokens for lookup
    parts = [p.strip() for p in re.split(r"[,/]", str(text)) if p.strip()]
    if not parts:
        parts = [str(text).strip()]
    for label in parts:
        for team_id in team_repo.find_team_ids_by_label(label):
            team_repo.reset_team_comm_timer(team_id)


def log_radio_entry(
    incident_id: str,
    sender: str,
    recipient: str,
    message: str,
    method: str = "radio",
) -> MessageLogEntry:
    """Persist a radio log entry and update team communication timers.

    Parameters
    ----------
    incident_id: str
        Identifier for the mission-scoped database.
    sender: str
        Free-text sender label.
    recipient: str
        Free-text recipient label.
    message: str
        Body of the radio message.
    method: str
        Communication method; defaults to ``"radio"``.
    """
    engine = get_incident_engine(str(incident_id))
    entry = MessageLogEntry(
        incident_id=str(incident_id),
        timestamp=datetime.utcnow(),
        sender=str(sender),
        recipient=str(recipient),
        method=str(method),
        message=str(message),
    )
    with Session(engine) as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)

    # Update timers for any teams mentioned
    _reset_comm_timers(sender)
    _reset_comm_timers(recipient)

    try:
        from . import notify_message_logged

        notify_message_logged(sender, recipient)
    except Exception:
        pass

    return entry
