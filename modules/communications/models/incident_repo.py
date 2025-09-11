from __future__ import annotations

"""Repository managing incident specific communication plans (ICS‑205)."""

from datetime import datetime
from typing import Any, Dict, List

from . import db
from modules.communications.util import geo_line_rules


UTC = "%Y-%m-%dT%H:%M:%S"


def infer_band(freq: float | None) -> str:
    """Infer a band string from ``freq`` in MHz."""
    if freq is None:
        return "Other"
    f = float(freq)
    if 3 <= f < 30:
        return "HF"
    if 30 <= f < 54:
        return "VHF-LOW"
    if 118 <= f <= 137:
        return "Air"
    if 156 <= f <= 163:
        return "Marine"
    if 54 <= f < 300:
        return "VHF"
    if 300 <= f < 700:
        return "UHF"
    if 700 <= f <= 869:
        return "700/800"
    return "Other"


def _now() -> str:
    return datetime.utcnow().strftime(UTC)


def _squelch(tone: str | None) -> tuple[str | None, str | None]:
    if tone in (None, "", "CSQ"):
        return "None", None
    try:
        float(tone)
        return "CTCSS", tone
    except (TypeError, ValueError):
        pass
    # three-digit numeric (e.g., 293) is typical DCS
    if tone and tone.isdigit() and len(tone) in (2, 3):
        return "DCS", tone
    # NAC like F7E
    if tone and tone.upper().startswith("F"):
        return "NAC", tone
    return None, None


class IncidentRepository:
    def __init__(self, incident_number: str | int):
        self.incident = incident_number

    # Basic operations ------------------------------------------------------
    def list_plan(self) -> List[Dict[str, Any]]:
        with db.get_incident_conn(self.incident) as conn:
            rows = conn.execute(
                "SELECT * FROM incident_channels ORDER BY sort_index, id"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_from_master(self, master_row: Dict[str, Any], defaults: Dict[str, Any] | None = None) -> Dict[str, Any]:
        defaults = defaults or {}
        band = infer_band(master_row.get("rx_freq") or master_row.get("tx_freq"))
        rx_tone = master_row.get("rx_tone")
        tx_tone = master_row.get("tx_tone")
        squelch_type, squelch_value = (None, None)
        if rx_tone == tx_tone:
            squelch_type, squelch_value = _squelch(rx_tone)
        repeater = 1 if master_row.get("tx_freq") and master_row.get("rx_freq") and master_row["tx_freq"] != master_row["rx_freq"] else 0
        offset = None
        if repeater:
            try:
                offset = float(master_row["tx_freq"]) - float(master_row["rx_freq"])
            except Exception:
                offset = None
        now = _now()
        with db.get_incident_conn(self.incident) as conn:
            cur = conn.execute(
                """
                INSERT INTO incident_channels (
                    master_id, channel, function, band, system, mode,
                    rx_freq, tx_freq, rx_tone, tx_tone, squelch_type, squelch_value,
                    repeater, offset, line_a, line_c, encryption, assignment_division, assignment_team,
                    priority, include_on_205, remarks, sort_index,
                    created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    master_row.get("id"),
                    master_row.get("name"),
                    master_row.get("function", "Tactical"),
                    band,
                    master_row.get("system"),
                    master_row.get("mode"),
                    master_row.get("rx_freq"),
                    master_row.get("tx_freq"),
                    rx_tone,
                    tx_tone,
                    squelch_type,
                    squelch_value,
                    repeater,
                    offset,
                    int(master_row.get("line_a", 0) or 0),
                    int(master_row.get("line_c", 0) or 0),
                    defaults.get("encryption", "None"),
                    defaults.get("assignment_division"),
                    defaults.get("assignment_team"),
                    defaults.get("priority", "Normal"),
                    int(defaults.get("include_on_205", 1)),
                    defaults.get("remarks"),
                    int(defaults.get("sort_index", 1000)),
                    now,
                    now,
                ),
            )
            conn.commit()
            new_id = cur.lastrowid
        return self.get_row(new_id)

    def get_row(self, row_id: int) -> Dict[str, Any]:
        with db.get_incident_conn(self.incident) as conn:
            row = conn.execute(
                "SELECT * FROM incident_channels WHERE id=?", (row_id,)
            ).fetchone()
        return dict(row) if row else {}

    def update_row(self, row_id: int, patch: Dict[str, Any]) -> None:
        patch = patch.copy()
        patch["updated_at"] = _now()
        cols = ", ".join(f"{k}=?" for k in patch.keys())
        values = list(patch.values()) + [row_id]
        with db.get_incident_conn(self.incident) as conn:
            conn.execute(f"UPDATE incident_channels SET {cols} WHERE id=?", values)
            conn.commit()

    def delete_row(self, row_id: int) -> None:
        with db.get_incident_conn(self.incident) as conn:
            conn.execute("DELETE FROM incident_channels WHERE id=?", (row_id,))
            conn.commit()

    def reorder(self, row_id: int, direction: str) -> None:
        row = self.get_row(row_id)
        if not row:
            return
        delta = -1 if direction == "up" else 1
        new_index = int(row.get("sort_index", 1000)) + delta
        self.update_row(row_id, {"sort_index": new_index})

    # Validation ------------------------------------------------------------
    def validate_plan(self) -> Dict[str, Any]:
        rows = self.list_plan()
        messages: List[Dict[str, str]] = []
        # Duplicate frequency
        for i, a in enumerate(rows):
            for b in rows[i + 1 :]:
                if (
                    a.get("band") == b.get("band")
                    and a.get("mode") == b.get("mode")
                    and a.get("rx_freq") == b.get("rx_freq")
                    and (a.get("tx_freq") or 0) == (b.get("tx_freq") or 0)
                    and (a.get("rx_tone") or "") == (b.get("rx_tone") or "")
                    and (a.get("tx_tone") or "") == (b.get("tx_tone") or "")
                ):
                    messages.append(
                        {
                            "level": "conflict",
                            "text": f"Duplicate freq {a.get('rx_freq')} ({a.get('channel')} & {b.get('channel')})",
                        }
                    )
        for r in rows:
            if not r.get("function"):
                messages.append({"level": "warning", "text": f"{r.get('channel')} missing function"})
            if (r.get("function", "").lower() == "tactical") and (
                not r.get("assignment_division") or not r.get("assignment_team")
            ):
                messages.append({"level": "warning", "text": f"{r.get('channel')} missing assignment"})
            if int(r.get("repeater") or 0) == 0 and r.get("offset"):
                messages.append({"level": "warning", "text": f"{r.get('channel')} offset with no repeater"})
            inferred = infer_band(r.get("rx_freq") or r.get("tx_freq"))
            if inferred != r.get("band"):
                messages.append({"level": "warning", "text": f"{r.get('channel')} out of band"})
            if int(r.get("line_a") or 0):
                if geo_line_rules.line_a_applies(None, None):
                    messages.append({"level": "warning", "text": f"{r.get('channel')} Line A coordination"})
            if int(r.get("line_c") or 0):
                if geo_line_rules.line_c_applies(None, None):
                    messages.append({"level": "warning", "text": f"{r.get('channel')} Line C coordination"})

        conflicts = sum(1 for m in messages if m["level"] == "conflict")
        warnings = sum(1 for m in messages if m["level"] == "warning")
        return {"messages": messages, "conflicts": conflicts, "warnings": warnings}

    # Preview ---------------------------------------------------------------
    def preview_rows(self) -> List[Dict[str, Any]]:
        rows = self.list_plan()
        preview: List[Dict[str, Any]] = []
        for r in rows:
            assignment = " / ".join(
                [p for p in [r.get("assignment_division"), r.get("assignment_team")] if p]
            )
            tone = r.get("rx_tone")
            if r.get("rx_tone") == r.get("tx_tone"):
                tone = r.get("rx_tone") or ""
            else:
                tone = "/".join(filter(None, [r.get("rx_tone"), r.get("tx_tone")]))
            preview.append(
                {
                    "Function": r.get("function"),
                    "Channel": r.get("channel"),
                    "Assignment": assignment,
                    "RX": r.get("rx_freq"),
                    "TX": r.get("tx_freq"),
                    "ToneNAC": tone or "",
                    "Mode": r.get("mode"),
                    "Encryption": r.get("encryption", "None"),
                    "Notes": r.get("remarks", ""),
                }
            )
        return preview


__all__ = ["IncidentRepository", "infer_band"]

