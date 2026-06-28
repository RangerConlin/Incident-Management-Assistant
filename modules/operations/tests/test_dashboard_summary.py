from modules.operations.data.dashboard_summary import (
    build_team_snapshot_rows,
    summarize_team_kpis,
)


def test_summarize_team_kpis_counts_only_available_status_as_available() -> None:
    teams = [
        {"name": "Alpha", "status": "Available"},
        {"name": "Bravo", "status": "Assigned", "current_task_id": 12},
        {"name": "Charlie", "status": "En Route"},
        {"name": "Delta", "status": "Available", "current_task_id": 7},
    ]

    summary = summarize_team_kpis(teams)

    assert summary["teams_available"] == 2
    assert summary["teams_assigned"] == 2


def test_summarize_team_kpis_counts_attention_flags() -> None:
    teams = [
        {"name": "Alpha", "status": "Available", "needs_attention": True},
        {"name": "Bravo", "status": "Assigned", "emergency_flag": True},
        {"name": "Charlie", "status": "Available"},
    ]

    summary = summarize_team_kpis(teams)

    assert summary["blocking_issues"] == 2


def test_build_team_snapshot_rows_uses_operations_team_fields() -> None:
    teams = [
        {
            "name": "Alpha",
            "status": "available",
            "current_task_id": 42,
            "leader_name": "A. Lead",
            "last_checkin_at": "2026-06-28T11:00:00+00:00",
        }
    ]

    rows = build_team_snapshot_rows(teams)

    assert rows == [
        {
            "name": "Alpha",
            "status": "Available",
            "assigned": "42",
            "leader": "A. Lead",
            "last_checkin_at": "2026-06-28T11:00:00+00:00",
        }
    ]
