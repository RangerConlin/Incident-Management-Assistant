from __future__ import annotations

from typing import Dict


class PermissionError(Exception):
    pass


def dispatch(action: str, payload: Dict):
    """Route quick entry actions to modules. Replace with real integrations.

    Do not hide options by role; raise PermissionError at action time when needed.
    """
    # TODO: integrate with actual panels/modules
    # For now, just simulate success for known actions
    allowed = {
        "tasks.create",
        "logs.createActivity",
        "comms.createLogEntry",
        "logistics.createResourceRequest",
        "comms.createMessage",
        "safety.createReport",
        "files.upload",
    }
    if action not in allowed:
        raise PermissionError(f"Action not permitted or unknown: {action}")
    # In a real implementation, open the relevant wizard/panel here
    return True


def execute_cli(command: str) -> str:
    """Very small command router. Records would be audited in a real system."""
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
        dispatch("tasks.create", {"title": text, **kv})
        return f"Task created: {text}"
    if domain == "log" and verb == "new":
        dispatch("logs.createActivity", {"text": text, **kv})
        return "Log entry created"
    if domain == "comms" and verb in {"add", "new"}:
        dispatch("comms.createLogEntry", {"text": text, **kv})
        return "Comms log entry created"
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

