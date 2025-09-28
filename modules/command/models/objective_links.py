from __future__ import annotations

"""Utility helpers for working with objective-task links."""

from collections import defaultdict
from typing import Dict, Iterable, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from .objectives import (
    ObjectiveStrategy,
    ObjectiveStrategyTaskLink,
    _OPEN_TASK_STATUSES,
)

try:  # pragma: no cover - optional at design time
    from modules.operations.taskings.repository import get_task  # type: ignore
except Exception:  # pragma: no cover
    def get_task(task_id: int):  # type: ignore[override]
        raise RuntimeError("Operations tasking repository unavailable")


def list_links_for_objective(session: Session, objective_id: int) -> list[ObjectiveStrategyTaskLink]:
    """Return all task links for the supplied objective."""

    return (
        session.execute(
            select(ObjectiveStrategyTaskLink).where(
                ObjectiveStrategyTaskLink.objective_id == objective_id
            )
        )
        .scalars()
        .all()
    )


def strategy_task_counts(session: Session, strategy_ids: Iterable[int]) -> Dict[int, Tuple[int, int]]:
    """Return ``{strategy_id: (open_tasks, total_tasks)}`` counts."""

    strategy_ids = list(strategy_ids)
    if not strategy_ids:
        return {}
    rows = (
        session.execute(
            select(
                ObjectiveStrategyTaskLink.strategy_id,
                ObjectiveStrategyTaskLink.task_id,
            ).where(ObjectiveStrategyTaskLink.strategy_id.in_(strategy_ids))
        )
        .all()
    )
    rollup: Dict[int, Tuple[int, int]] = {sid: (0, 0) for sid in strategy_ids}
    for strategy_id, task_id in rows:
        open_count, total_count = rollup[strategy_id]
        status_key = ""
        try:
            task = get_task(int(task_id))
            status_key = str(getattr(task, "status", "")).strip().lower()
        except Exception:
            status_key = ""
        if status_key in _OPEN_TASK_STATUSES:
            open_count += 1
        total_count += 1
        rollup[strategy_id] = (open_count, total_count)
    return rollup


def objective_task_counts(session: Session, objective_id: int) -> Tuple[int, int]:
    """Return ``(open, total)`` counts for an objective."""

    links = list_links_for_objective(session, objective_id)
    open_total = 0
    total = 0
    for link in links:
        total += 1
        try:
            task = get_task(int(link.task_id))
            status_key = str(getattr(task, "status", "")).strip().lower()
        except Exception:
            status_key = ""
        if status_key in _OPEN_TASK_STATUSES:
            open_total += 1
    return open_total, total


def bulk_strategy_counts(session: Session, objective_ids: Iterable[int]) -> Dict[int, Dict[int, Tuple[int, int]]]:
    """Return ``{objective_id: {strategy_id: (open, total)}}``."""

    rows = (
        session.execute(
            select(
                ObjectiveStrategyTaskLink.objective_id,
                ObjectiveStrategyTaskLink.strategy_id,
                ObjectiveStrategyTaskLink.task_id,
            ).where(ObjectiveStrategyTaskLink.objective_id.in_(list(objective_ids)))
        )
        .all()
    )
    strategies = (
        session.execute(
            select(ObjectiveStrategy.id, ObjectiveStrategy.objective_id)
            .where(ObjectiveStrategy.id.in_({row[1] for row in rows}))
        )
        .all()
    )
    strategy_to_objective = {strategy_id: objective_id for strategy_id, objective_id in strategies}
    rollup: Dict[int, Dict[int, Tuple[int, int]]] = defaultdict(dict)
    for objective_id, strategy_id, task_id in rows:
        counts = rollup[objective_id].get(strategy_id, (0, 0))
        open_count, total_count = counts
        status_key = ""
        try:
            task = get_task(int(task_id))
            status_key = str(getattr(task, "status", "")).strip().lower()
        except Exception:
            status_key = ""
        if status_key in _OPEN_TASK_STATUSES:
            open_count += 1
        total_count += 1
        rollup[objective_id][strategy_id] = (open_count, total_count)
    for strategy_id, objective_id in strategy_to_objective.items():
        rollup.setdefault(objective_id, {}).setdefault(strategy_id, (0, 0))
    return rollup
