from __future__ import annotations

from collections.abc import Callable
from typing import Dict


class QuickEntryPermissionError(Exception):
    """Raised when a quick entry action is not permitted."""

    pass


ActionDispatcher = Callable[[str, Dict], object]


def dispatch(action: str, payload: Dict):
    """Reject unbound quick-entry calls instead of pretending they succeeded.

    The desktop main window supplies the real dispatcher because it owns the
    panel factories and ADS docking lifecycle.
    """
    raise RuntimeError(f"Quick Entry action is not connected: {action}")


def execute_cli(command: str, dispatcher: ActionDispatcher = dispatch) -> str:
    """Parse a command and send it through the real Quick Entry dispatcher."""
    # Examples:
    # task new "Ground Sweep Alpha" priority=High team=G-2
    # log new "Team B departed ICP"
    # comms add "CH5 secure traffic"
    tokens = _tokenize(command)
    if not tokens:
        return ""
    domain = tokens[0]
    verb = tokens[1] if len(tokens) > 1 else ""
    args = tokens[2:]
    kv = {k: v for k, v in (a.split("=", 1) for a in args if "=" in a)}
    text = next((a for a in args if "=" not in a), "")

    if domain == "task" and verb == "new":
        dispatcher("tasks.create", {"title": text, **kv})
        return f"Task created: {text}"
    if domain == "log" and verb == "new":
        dispatcher("logs.createActivity", {"text": text, **kv})
        return "Opened the ICS-214 activity log"
    if domain == "comms" and verb in {"add", "new"}:
        dispatcher("comms.createLogEntry", {"text": text, **kv})
        return "Opened Communications Quick Entry"
    return f"Unknown command: {command}"


def _tokenize(s: str) -> list[str]:
    out: list[str] = []
    cur = []
    quote = None
    for ch in s:
        if quote:
            if ch == quote:
                out.append("".join(cur))
                cur = []
                quote = None
            else:
                cur.append(ch)
        else:
            if ch in ('"', "'"):
                if cur:
                    out.append("".join(cur))
                    cur = []
                quote = ch
            elif ch.isspace():
                if cur:
                    out.append("".join(cur))
                    cur = []
            else:
                cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out
