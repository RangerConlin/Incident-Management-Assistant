from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(slots=True)
class ImportResult:
    inserted: int
    skipped_duplicates: List[str]
    errors: List[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.inserted or self.errors)


class ApiBaseLookupRepository:
    """MongoDB-backed lookup repository via the SARApp API server."""

    _endpoint: str = ""
    export_headers: list[str] = []

    def ensure_schema(self) -> None:
        pass

    def _api_get(self, path: str, **params):
        from utils.api_client import api_client
        return api_client.get(self._endpoint + path, params=params if params else None)

    def _api_post(self, path: str, body: dict):
        from utils.api_client import api_client
        return api_client.post(self._endpoint + path, json=body)

    def _api_put(self, path: str, body: dict):
        from utils.api_client import api_client
        return api_client.put(self._endpoint + path, json=body)

    def _api_patch(self, path: str):
        from utils.api_client import api_client
        return api_client.patch(self._endpoint + path)

    def _api_delete(self, path: str):
        from utils.api_client import api_client
        return api_client.delete(self._endpoint + path)

    def list(self, filter_text: str = "", include_inactive: bool = False) -> list[dict]:
        return self._api_get(
            "",
            filter_text=filter_text,
            include_inactive=str(include_inactive).lower(),
        )

    def get(self, record_id: int) -> Optional[dict]:
        try:
            return self._api_get(f"/{record_id}")
        except Exception:
            return None

    def exists_with_name(self, name: str, exclude_id: Optional[int] = None) -> bool:
        params: dict = {"name": name}
        if exclude_id is not None:
            params["exclude_id"] = exclude_id
        from utils.api_client import api_client
        result = api_client.get(self._endpoint + "/exists", params=params)
        return bool(result.get("exists", False))

    def create(self, data: dict) -> int:
        result = self._api_post("", data)
        return int(result["id"])

    def update(self, record_id: int, data: dict) -> None:
        self._api_put(f"/{record_id}", data)

    def soft_delete(self, record_id: int) -> None:
        self._api_delete(f"/{record_id}")

    def restore(self, record_id: int) -> None:
        self._api_patch(f"/{record_id}/restore")

    def export_csv(self, path: Path, rows: Optional[Iterable[dict]] = None) -> Path:
        output_path = Path(path)
        if not output_path.suffix:
            output_path = output_path.with_suffix(".csv")
        headers = self.export_headers
        if rows is None:
            rows = self.list(include_inactive=True)
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in headers})
        return output_path

    def import_csv(self, path: Path) -> ImportResult:
        inserted = 0
        skipped: list[str] = []
        errors: list[str] = []
        with Path(path).open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                return ImportResult(0, [], ["CSV file missing header row"])
            for idx, raw in enumerate(reader, start=2):
                try:
                    payload = self._map_csv_row(raw)
                    if not payload.get("name"):
                        skipped.append(f"Row {idx}: missing name")
                        continue
                    if self.exists_with_name(payload["name"]):
                        skipped.append(payload["name"])
                        continue
                    self.create(payload)
                    inserted += 1
                except Exception as exc:
                    errors.append(f"Row {idx}: {exc}")
        return ImportResult(inserted, skipped, errors)

    def _map_csv_row(self, row: dict) -> dict:
        raise NotImplementedError


class ApiTaskTypesRepository(ApiBaseLookupRepository):
    _endpoint = "/api/lookup/task-types"
    export_headers = [
        "name", "category", "default_priority", "description",
        "is_active", "created_at", "updated_at",
    ]

    def _map_csv_row(self, row: dict) -> dict:
        norm = {k.lower().strip(): v for k, v in row.items()}
        is_active_value = norm.get("is active") or norm.get("active") or "1"
        try:
            is_active = 1 if str(is_active_value).strip().lower() in {"1", "true", "yes", "active"} else 0
        except Exception:
            is_active = 1
        default_priority = norm.get("default priority") or norm.get("priority") or "Normal"
        return {
            "name": norm.get("name", "").strip(),
            "category": norm.get("category", "").strip(),
            "default_priority": default_priority.strip().title(),
            "description": norm.get("description", "").strip(),
            "is_active": is_active,
        }


class ApiTeamTypesRepository(ApiBaseLookupRepository):
    _endpoint = "/api/lookup/team-types"
    export_headers = ["name", "category", "description", "is_active", "created_at", "updated_at"]

    def _map_csv_row(self, row: dict) -> dict:
        norm = {k.lower().strip(): v for k, v in row.items()}
        is_active_value = norm.get("is active") or norm.get("active") or "1"
        try:
            is_active = 1 if str(is_active_value).strip().lower() in {"1", "true", "yes", "active"} else 0
        except Exception:
            is_active = 1
        return {
            "name": norm.get("name", "").strip(),
            "category": norm.get("category", "").strip(),
            "description": norm.get("description", "").strip(),
            "is_active": is_active,
        }
