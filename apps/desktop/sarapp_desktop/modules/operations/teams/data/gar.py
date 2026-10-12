"""GAR (Green-Amber-Red) risk assessment model.

A GAR assessment is scored against an admin-editable template (see
``modules/admin/gar_templates/``) rather than a fixed set of factors —
different organizations score risk differently, so the rubric itself is
data, not code. An assessment is scoped to one Team, not a Task: a task can
carry multiple teams, each with its own risk posture. Assessments are
normally made once per operational period (at team briefing/activation) but
can be redone any time conditions change — every save appends a new entry
rather than overwriting, so this model is also used to represent one entry
in that history list.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GarSelection:
    """One resolved row selection within an assessment — denormalized at
    save time so history reads correctly even if the template is edited
    later."""

    group_id: str = ""
    group_name: str = ""
    row_id: str = ""
    row_label: str = ""
    option_id: str = ""
    option_label: str = ""
    points: int = 0
    no_go: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "GarSelection":
        data = data or {}
        return cls(
            group_id=data.get("group_id") or "",
            group_name=data.get("group_name") or "",
            row_id=data.get("row_id") or "",
            row_label=data.get("row_label") or "",
            option_id=data.get("option_id") or "",
            option_label=data.get("option_label") or "",
            points=int(data.get("points") or 0),
            no_go=bool(data.get("no_go")),
        )


@dataclass
class GarAssessment:
    """One GAR assessment snapshot for a team. Score/band/required_reviewer/
    operational_period_id are always server-computed; this is a
    display/transport model only."""

    template_id: int | None = None
    template_name: str = ""
    selections: list[GarSelection] = field(default_factory=list)
    score: int = 0
    band: str = ""
    required_reviewer: str = ""
    no_go: bool = False
    notes: str = ""
    assessed_by: str = ""
    assessed_at: str = ""
    operational_period_id: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "GarAssessment":
        data = data or {}
        return cls(
            template_id=data.get("template_id"),
            template_name=data.get("template_name") or "",
            selections=[GarSelection.from_dict(s) for s in (data.get("selections") or [])],
            score=int(data.get("score") or 0),
            band=data.get("band") or "",
            required_reviewer=data.get("required_reviewer") or "",
            no_go=bool(data.get("no_go")),
            notes=data.get("notes") or "",
            assessed_by=data.get("assessed_by") or "",
            assessed_at=data.get("assessed_at") or "",
            operational_period_id=data.get("operational_period_id"),
        )
