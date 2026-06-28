from __future__ import annotations

from typing import Any


def _status_key(team: dict[str, Any]) -> str:
    return str(team.get("status") or "").strip().lower()


def _has_assignment(team: dict[str, Any]) -> bool:
    return bool(
        team.get("current_task_id")
        or team.get("task_id")
        or team.get("assignment")
        or team.get("task")
    )


def summarize_team_kpis(teams: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "teams_assigned": sum(1 for team in teams if _has_assignment(team)),
        "teams_available": sum(1 for team in teams if _status_key(team) == "available"),
        "blocking_issues": sum(
            1
            for team in teams
            if team.get("needs_attention")
            or team.get("needs_assistance")
            or team.get("emergency")
            or team.get("emergency_flag")
        ),
    }


def build_team_snapshot_rows(teams: list[dict[str, Any]], limit: int = 6) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for team in teams[:limit]:
        rows.append(
            {
                "name": str(team.get("name") or team.get("team_name") or "Team"),
                "status": str(team.get("status") or "").title(),
                "assigned": str(
                    team.get("assignment")
                    or team.get("task")
                    or team.get("current_task_id")
                    or ""
                ),
                "leader": str(team.get("leader") or team.get("leader_name") or ""),
                "last_checkin_at": str(team.get("last_checkin_at") or team.get("last_checkin_ts") or ""),
            }
        )
    return rows
