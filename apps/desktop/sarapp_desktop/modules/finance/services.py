from __future__ import annotations

from typing import Any

from .models.schemas import (
    ActualCostDocumentCreate,
    ActualCostDocumentRead,
    ActualCostLineCreate,
    ActualCostLineRead,
    ApprovalRecordCreate,
    ApprovalRecordRead,
    AttachmentCreate,
    AttachmentRead,
    BudgetSet,
    BudgetSummaryRead,
    CalculatedEstimateCreate,
    EstimateRead,
    FinanceDashboardSnapshot,
    ManualEstimateCreate,
    PendingApprovalRow,
    RateTableEntryCreate,
    RateTableEntryRead,
    RateTableEntryUpdate,
    RateTableTemplateRead,
    TaskFinanceSummaryRead,
)


def _client():
    from utils.api_client import api_client

    return api_client


def _base(incident_id: str) -> str:
    return f"/api/incidents/{incident_id}/finance"


def _cached_docs(incident_id: str, collection: str) -> list[dict[str, Any]] | None:
    """Return cached incident-scoped docs for ``collection``, or None if the
    incident cache isn't loaded for this incident."""
    from utils.incident_cache import incident_cache

    if incident_cache.incident_id != str(incident_id):
        return None
    return incident_cache.get_all(collection)


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    """Mirror the server's ``_strip``: expose ``int_id`` as ``id``."""
    return {**doc, "id": doc.get("id") or doc.get("int_id")}


def _sort_key(value: Any) -> tuple[bool, Any]:
    """Sort ``None`` last regardless of the other values' type."""
    return (value is None, value if value is not None else "")


def _sorted_by(docs: list[dict[str, Any]], fields: tuple[tuple[str, bool], ...]) -> list[dict[str, Any]]:
    """Sort by multiple (field, descending) pairs, matching Mongo's compound sort."""
    result = list(docs)
    for field, descending in reversed(fields):
        result.sort(key=lambda d: _sort_key(d.get(field)), reverse=descending)
    return result


def _cached_doc_by_int_id(incident_id: str, collection: str, int_id: int) -> dict[str, Any] | None:
    cached = _cached_docs(incident_id, collection)
    if cached is None:
        return None
    for doc in cached:
        if doc.get("int_id") == int_id:
            return doc
    return None


def _post(path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
    from utils.api_client import APIError

    try:
        return _client().post(path, json=json, params=params)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def _patch(path: str, *, json: Any = None) -> Any:
    from utils.api_client import APIError

    try:
        return _client().patch(path, json=json)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def _put(path: str, *, json: Any = None) -> Any:
    from utils.api_client import APIError

    try:
        return _client().put(path, json=json)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def _jsonable(data: Any, *, exclude_none: bool = False) -> dict[str, Any]:
    """Serialize a pydantic model to a JSON-safe dict (datetimes -> ISO strings)."""
    return data.model_dump(mode="json", exclude_none=exclude_none)


# ===========================================================================
# Rate Tables
# ===========================================================================

def list_rate_tables(incident_id: str, category: str | None = None, active_only: bool = False) -> list[RateTableEntryRead]:
    cached = _cached_docs(incident_id, "finance_rate_tables")
    if cached is not None:
        filtered = cached
        if category:
            filtered = [d for d in filtered if d.get("category") == category]
        if active_only:
            filtered = [d for d in filtered if d.get("is_active")]
        ordered = _sorted_by(filtered, (("category", False), ("name", False)))
        return [RateTableEntryRead(**_normalize(row)) for row in ordered]
    params = {k: v for k, v in {"category": category, "active_only": active_only}.items() if v}
    rows = _client().get(f"{_base(incident_id)}/rate-tables", params=params or None) or []
    return [RateTableEntryRead(**row) for row in rows]


def create_rate_table_entry(incident_id: str, data: RateTableEntryCreate) -> RateTableEntryRead:
    row = _post(f"{_base(incident_id)}/rate-tables", json=_jsonable(data))
    return RateTableEntryRead(**row)


def update_rate_table_entry(incident_id: str, entry_id: int, data: RateTableEntryUpdate) -> RateTableEntryRead:
    fields = _jsonable(data, exclude_none=True)
    row = _patch(f"{_base(incident_id)}/rate-tables/{entry_id}", json=fields)
    return RateTableEntryRead(**row)


def list_rate_table_templates(incident_id: str, category: str | None = None) -> list[RateTableTemplateRead]:
    params = {"category": category} if category else None
    # Templates are master-catalog, not incident-scoped — no cache lookup.
    rows = _client().get(f"{_base(incident_id)}/rate-table-templates", params=params) or []
    return [RateTableTemplateRead(**row) for row in rows]


def seed_rate_table_from_template(incident_id: str, template_id: int) -> RateTableEntryRead:
    row = _post(f"{_base(incident_id)}/rate-tables/seed-from-template/{template_id}")
    return RateTableEntryRead(**row)


# ===========================================================================
# Budget
# ===========================================================================

def get_budget(incident_id: str) -> BudgetSummaryRead:
    row = _client().get(f"{_base(incident_id)}/budget")
    return BudgetSummaryRead(**row)


def set_budget(incident_id: str, data: BudgetSet) -> BudgetSummaryRead:
    row = _put(f"{_base(incident_id)}/budget", json=_jsonable(data))
    return BudgetSummaryRead(**row)


# ===========================================================================
# Estimates
# ===========================================================================

def list_estimates(
    incident_id: str,
    task_id: str | None = None,
    resource_request_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    include_closed: bool = True,
) -> list[EstimateRead]:
    cached = _cached_docs(incident_id, "finance_estimates")
    if cached is not None:
        filtered = cached
        if task_id:
            filtered = [d for d in filtered if d.get("task_id") == task_id]
        if resource_request_id is not None:
            filtered = [d for d in filtered if d.get("resource_request_id") == resource_request_id]
        if status:
            filtered = [d for d in filtered if d.get("status") == status]
        if category:
            filtered = [d for d in filtered if d.get("category") == category]
        if not include_closed:
            filtered = [d for d in filtered if not d.get("closed")]
        ordered = _sorted_by(filtered, (("created_at", True), ("int_id", True)))
        return [EstimateRead(**_normalize(row)) for row in ordered]

    params = {
        k: v for k, v in {
            "task_id": task_id,
            "resource_request_id": resource_request_id,
            "status": status,
            "category": category,
            "include_closed": include_closed,
        }.items() if v is not None
    }
    rows = _client().get(f"{_base(incident_id)}/estimates", params=params or None) or []
    return [EstimateRead(**row) for row in rows]


def get_estimate(incident_id: str, estimate_id: int) -> EstimateRead:
    cached = _cached_doc_by_int_id(incident_id, "finance_estimates", estimate_id)
    if cached is not None:
        return EstimateRead(**_normalize(cached))
    row = _client().get(f"{_base(incident_id)}/estimates/{estimate_id}")
    return EstimateRead(**row)


def create_manual_estimate(incident_id: str, data: ManualEstimateCreate) -> EstimateRead:
    row = _post(f"{_base(incident_id)}/estimates/manual", json=_jsonable(data))
    return EstimateRead(**row)


def create_calculated_estimate(incident_id: str, data: CalculatedEstimateCreate) -> EstimateRead:
    row = _post(f"{_base(incident_id)}/estimates/calculated", json=_jsonable(data))
    return EstimateRead(**row)


def recalculate_estimate(incident_id: str, estimate_id: int, quantity: float, changed_by: str | None = None) -> EstimateRead:
    row = _post(
        f"{_base(incident_id)}/estimates/{estimate_id}/recalculate",
        json={"quantity": quantity, "changed_by": changed_by},
    )
    return EstimateRead(**row)


def commit_estimate(incident_id: str, estimate_id: int, changed_by: str | None = None) -> EstimateRead:
    row = _post(f"{_base(incident_id)}/estimates/{estimate_id}/commit", json={"changed_by": changed_by})
    return EstimateRead(**row)


def close_estimate(incident_id: str, estimate_id: int, closed_reason: str, changed_by: str | None = None, detail: str | None = None) -> EstimateRead:
    row = _post(
        f"{_base(incident_id)}/estimates/{estimate_id}/close",
        json={"closed_reason": closed_reason, "changed_by": changed_by, "detail": detail},
    )
    return EstimateRead(**row)


def refine_estimate_from_debrief(incident_id: str, **kwargs: Any) -> EstimateRead:
    row = _post(f"{_base(incident_id)}/estimates/debrief-refinement", json=kwargs)
    return EstimateRead(**row)


def flag_debrief_estimate_for_review(incident_id: str, debrief_id: str, changed_by: str | None = None) -> EstimateRead | None:
    row = _post(
        f"{_base(incident_id)}/estimates/debrief-refinement/{debrief_id}/flag-for-review",
        params={"changed_by": changed_by} if changed_by else None,
    )
    return EstimateRead(**row) if row else None


# ===========================================================================
# Actual cost documents + lines
# ===========================================================================

def list_actual_cost_documents(incident_id: str) -> list[ActualCostDocumentRead]:
    cached = _cached_docs(incident_id, "finance_actual_cost_documents")
    if cached is not None:
        ordered = _sorted_by(cached, (("document_date", True), ("int_id", True)))
        return [ActualCostDocumentRead(**_normalize(row)) for row in ordered]
    rows = _client().get(f"{_base(incident_id)}/actual-cost-documents") or []
    return [ActualCostDocumentRead(**row) for row in rows]


def create_actual_cost_document(incident_id: str, data: ActualCostDocumentCreate) -> ActualCostDocumentRead:
    row = _post(f"{_base(incident_id)}/actual-cost-documents", json=_jsonable(data))
    return ActualCostDocumentRead(**row)


def update_actual_cost_document(incident_id: str, document_id: int, **fields: Any) -> ActualCostDocumentRead:
    row = _patch(f"{_base(incident_id)}/actual-cost-documents/{document_id}", json=fields)
    return ActualCostDocumentRead(**row)


def list_actual_cost_lines(incident_id: str, document_id: int) -> list[ActualCostLineRead]:
    cached = _cached_docs(incident_id, "finance_actual_cost_lines")
    if cached is not None:
        filtered = [d for d in cached if d.get("document_id") == document_id]
        ordered = _sorted_by(filtered, (("int_id", False),))
        return [ActualCostLineRead(**_normalize(row)) for row in ordered]
    rows = _client().get(f"{_base(incident_id)}/actual-cost-documents/{document_id}/lines") or []
    return [ActualCostLineRead(**row) for row in rows]


def add_actual_cost_line(incident_id: str, document_id: int, data: ActualCostLineCreate) -> ActualCostLineRead:
    row = _post(f"{_base(incident_id)}/actual-cost-documents/{document_id}/lines", json=_jsonable(data))
    return ActualCostLineRead(**row)


def link_more_estimates(incident_id: str, line_id: int, links: list[dict[str, Any]]) -> ActualCostLineRead:
    row = _post(f"{_base(incident_id)}/actual-cost-lines/{line_id}/link", json={"links": links})
    return ActualCostLineRead(**row)


# ===========================================================================
# Attachments + approvals
# ===========================================================================

def create_attachment(incident_id: str, data: AttachmentCreate) -> AttachmentRead:
    row = _post(f"{_base(incident_id)}/attachments", json=_jsonable(data))
    return AttachmentRead(**row)


def list_attachments(incident_id: str, record_type: str, record_id: int) -> list[AttachmentRead]:
    cached = _cached_docs(incident_id, "finance_attachments")
    if cached is not None:
        filtered = [
            d for d in cached
            if d.get("record_type") == record_type and d.get("record_id") == record_id
        ]
        ordered = _sorted_by(filtered, (("uploaded_at", True), ("int_id", True)))
        return [AttachmentRead(**_normalize(row)) for row in ordered]
    rows = _client().get(
        f"{_base(incident_id)}/attachments",
        params={"record_type": record_type, "record_id": record_id},
    ) or []
    return [AttachmentRead(**row) for row in rows]


def list_approvals(incident_id: str, record_type: str, record_id: int) -> list[ApprovalRecordRead]:
    cached = _cached_docs(incident_id, "finance_approvals")
    if cached is not None:
        filtered = [
            d for d in cached
            if d.get("record_type") == record_type and d.get("record_id") == record_id
        ]
        ordered = _sorted_by(filtered, (("timestamp", True), ("int_id", True)))
        return [ApprovalRecordRead(**_normalize(row)) for row in ordered]
    rows = _client().get(
        f"{_base(incident_id)}/approvals",
        params={"record_type": record_type, "record_id": record_id},
    ) or []
    return [ApprovalRecordRead(**row) for row in rows]


def create_approval(incident_id: str, data: ApprovalRecordCreate) -> ApprovalRecordRead:
    row = _post(f"{_base(incident_id)}/approvals", json=_jsonable(data))
    return ApprovalRecordRead(**row)


# ===========================================================================
# Reporting
# ===========================================================================

def get_dashboard_snapshot(incident_id: str) -> FinanceDashboardSnapshot:
    # The projected-cost math joins budget + estimates + actual-cost lines;
    # rather than duplicate that aggregation client-side, always call the
    # API for this one (the incident cache only helps the simple list reads).
    row = _client().get(f"{_base(incident_id)}/dashboard")
    return FinanceDashboardSnapshot(**row)


def get_task_finance_summary(incident_id: str, task_id: str) -> TaskFinanceSummaryRead:
    row = _client().get(f"{_base(incident_id)}/task-summary/{task_id}")
    return TaskFinanceSummaryRead(**row)


def list_pending_approvals(incident_id: str) -> list[PendingApprovalRow]:
    rows = _client().get(f"{_base(incident_id)}/pending-approvals") or []
    return [PendingApprovalRow(**row) for row in rows]
