"""Client-side, display-only progress/failure aggregation over an already
fetched checklist's ``sections``.

This mirrors the arithmetic in the server's
``sarapp_db.services.checklist_service.compute_progress`` /
``build_completion_summary`` (same "applicable = total minus N/A" rule) so
the list and execution widgets can render progress/failure counts without
an extra network round trip per row — the data is already present in the
checklist payload the list/get endpoints return.

This is display aggregation only. It never gates any action: completion
is always validated server-side via the `validate-completion`/`complete`
endpoints, which remain the sole authority on whether a checklist may be
finalized.
"""

from __future__ import annotations

from typing import Any


def iter_items(sections: list[dict] | None):
    for section in sections or []:
        for item in section.get("items") or []:
            yield section, item


def is_failed(item: dict) -> bool:
    response = item.get("response")
    return bool(
        response
        and not response.get("na")
        and item.get("item_type") == "pass_fail_na"
        and response.get("value") == "fail"
    )


def summarize(sections: list[dict] | None) -> dict[str, Any]:
    total_items = 0
    na_items = 0
    answered_items = 0
    unanswered_required: list[str] = []
    failed_items: list[dict[str, str]] = []

    for _section, item in iter_items(sections):
        total_items += 1
        response = item.get("response")
        if response is not None:
            answered_items += 1
            if response.get("na"):
                na_items += 1
        elif item.get("required"):
            unanswered_required.append(item.get("id", ""))
        if is_failed(item):
            failed_items.append({"item_id": item.get("id", ""), "label": item.get("label", "")})

    applicable_items = total_items - na_items
    answered_applicable_items = answered_items - na_items

    return {
        "total_items": total_items,
        "na_items": na_items,
        "applicable_items": applicable_items,
        "answered_applicable_items": answered_applicable_items,
        "unanswered_required": unanswered_required,
        "failed_items": failed_items,
    }


def progress_text(sections: list[dict] | None) -> str:
    summary = summarize(sections)
    return f"{summary['answered_applicable_items']}/{summary['applicable_items']}"
