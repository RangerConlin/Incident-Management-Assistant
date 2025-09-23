from __future__ import annotations

"""Repository managing ICS-203 units, positions, and assignments."""

from typing import Iterable, List, Optional

from .db import ensure_incident_schema, get_incident_connection
from .models import Assignment, OrgUnit, Position, AgencyRepresentative


class ICS203Repository:
    """Data access helper scoped to a single incident."""

    def __init__(self, incident_id: str | int):
        self.incident_id = str(incident_id)
        ensure_incident_schema(self.incident_id)

    # ------------------------------------------------------------------
    # Unit helpers
    # ------------------------------------------------------------------
    def list_units(self) -> List[OrgUnit]:
        sql = (
            "SELECT id, incident_id, unit_type, name, parent_unit_id, sort_order "
            "FROM org_units WHERE incident_id=? ORDER BY sort_order, name"
        )
        with get_incident_connection(self.incident_id) as conn:
            rows = conn.execute(sql, (self.incident_id,)).fetchall()
        return [OrgUnit(**dict(row)) for row in rows]

    def get_unit(self, unit_id: int) -> Optional[OrgUnit]:
        sql = "SELECT * FROM org_units WHERE id=? AND incident_id=?"
        with get_incident_connection(self.incident_id) as conn:
            row = conn.execute(sql, (unit_id, self.incident_id)).fetchone()
        return OrgUnit(**dict(row)) if row else None

    def upsert_unit(self, unit: OrgUnit) -> int:
        values = (
            self.incident_id,
            unit.unit_type,
            unit.name,
            unit.parent_unit_id,
            unit.sort_order,
        )
        with get_incident_connection(self.incident_id) as conn:
            if unit.id is None:
                cur = conn.execute(
                    """
                    INSERT INTO org_units (
                        incident_id, unit_type, name, parent_unit_id, sort_order
                    ) VALUES (?,?,?,?,?)
                    """,
                    values,
                )
                conn.commit()
                return int(cur.lastrowid)
            conn.execute(
                """
                UPDATE org_units
                SET unit_type=?, name=?, parent_unit_id=?, sort_order=?
                WHERE id=? AND incident_id=?
                """,
                (
                    unit.unit_type,
                    unit.name,
                    unit.parent_unit_id,
                    unit.sort_order,
                    unit.id,
                    self.incident_id,
                ),
            )
            conn.commit()
            return int(unit.id)

    def delete_unit(self, unit_id: int) -> None:
        with get_incident_connection(self.incident_id) as conn:
            conn.execute(
                "DELETE FROM org_units WHERE id=? AND incident_id=?",
                (unit_id, self.incident_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------
    def list_positions(self, unit_id: int | None = None) -> List[Position]:
        sql = (
            "SELECT id, incident_id, title, unit_id, sort_order FROM org_positions "
            "WHERE incident_id=?"
        )
        params: list[object] = [self.incident_id]
        if unit_id is None:
            sql += " AND unit_id IS NULL"
        else:
            sql += " AND unit_id=?"
            params.append(unit_id)
        sql += " ORDER BY sort_order, title"
        with get_incident_connection(self.incident_id) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [Position(**dict(row)) for row in rows]

    def list_all_positions(self) -> List[Position]:
        sql = (
            "SELECT id, incident_id, title, unit_id, sort_order FROM org_positions "
            "WHERE incident_id=? ORDER BY sort_order, title"
        )
        with get_incident_connection(self.incident_id) as conn:
            rows = conn.execute(sql, (self.incident_id,)).fetchall()
        return [Position(**dict(row)) for row in rows]

    def get_position(self, position_id: int) -> Optional[Position]:
        sql = "SELECT * FROM org_positions WHERE id=? AND incident_id=?"
        with get_incident_connection(self.incident_id) as conn:
            row = conn.execute(sql, (position_id, self.incident_id)).fetchone()
        return Position(**dict(row)) if row else None

    def upsert_position(self, position: Position) -> int:
        with get_incident_connection(self.incident_id) as conn:
            if position.id is None:
                cur = conn.execute(
                    """
                    INSERT INTO org_positions (
                        incident_id, title, unit_id, sort_order
                    ) VALUES (?,?,?,?)
                    """,
                    (
                        self.incident_id,
                        position.title,
                        position.unit_id,
                        position.sort_order,
                    ),
                )
                conn.commit()
                return int(cur.lastrowid)
            conn.execute(
                """
                UPDATE org_positions
                SET title=?, unit_id=?, sort_order=?
                WHERE id=? AND incident_id=?
                """,
                (
                    position.title,
                    position.unit_id,
                    position.sort_order,
                    position.id,
                    self.incident_id,
                ),
            )
            conn.commit()
            return int(position.id)

    def delete_position(self, position_id: int) -> None:
        with get_incident_connection(self.incident_id) as conn:
            conn.execute(
                "DELETE FROM org_positions WHERE id=? AND incident_id=?",
                (position_id, self.incident_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Assignment helpers
    # ------------------------------------------------------------------
    def list_assignments(self, position_id: int | None = None) -> List[Assignment]:
        sql = "SELECT * FROM org_assignments WHERE incident_id=?"
        params: list[object] = [self.incident_id]
        if position_id is not None:
            sql += " AND position_id=?"
            params.append(position_id)
        sql += " ORDER BY id"
        with get_incident_connection(self.incident_id) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [Assignment(**dict(row)) for row in rows]

    def upsert_assignment(self, assignment: Assignment) -> int:
        payload = (
            self.incident_id,
            assignment.position_id,
            assignment.person_id,
            assignment.display_name,
            assignment.callsign,
            assignment.phone,
            assignment.agency,
            assignment.start_utc,
            assignment.end_utc,
            assignment.notes,
        )
        with get_incident_connection(self.incident_id) as conn:
            if assignment.id is None:
                cur = conn.execute(
                    """
                    INSERT INTO org_assignments (
                        incident_id, position_id, person_id, display_name,
                        callsign, phone, agency, start_utc, end_utc, notes
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    payload,
                )
                conn.commit()
                return int(cur.lastrowid)
            conn.execute(
                """
                UPDATE org_assignments
                SET position_id=?, person_id=?, display_name=?, callsign=?,
                    phone=?, agency=?, start_utc=?, end_utc=?, notes=?
                WHERE id=? AND incident_id=?
                """,
                (
                    assignment.position_id,
                    assignment.person_id,
                    assignment.display_name,
                    assignment.callsign,
                    assignment.phone,
                    assignment.agency,
                    assignment.start_utc,
                    assignment.end_utc,
                    assignment.notes,
                    assignment.id,
                    self.incident_id,
                ),
            )
            conn.commit()
            return int(assignment.id)

    def delete_assignment(self, assignment_id: int) -> None:
        with get_incident_connection(self.incident_id) as conn:
            conn.execute(
                "DELETE FROM org_assignments WHERE id=? AND incident_id=?",
                (assignment_id, self.incident_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Agency representatives
    # ------------------------------------------------------------------
    def list_agency_reps(self) -> List[AgencyRepresentative]:
        sql = "SELECT * FROM org_agency_reps WHERE incident_id=? ORDER BY name"
        with get_incident_connection(self.incident_id) as conn:
            rows = conn.execute(sql, (self.incident_id,)).fetchall()
        return [AgencyRepresentative(**dict(row)) for row in rows]

    def upsert_agency_rep(self, rep: AgencyRepresentative) -> int:
        payload = (
            self.incident_id,
            rep.name,
            rep.agency,
            rep.phone,
            rep.email,
            rep.notes,
        )
        with get_incident_connection(self.incident_id) as conn:
            if rep.id is None:
                cur = conn.execute(
                    """
                    INSERT INTO org_agency_reps (
                        incident_id, name, agency, phone, email, notes
                    ) VALUES (?,?,?,?,?,?)
                    """,
                    payload,
                )
                conn.commit()
                return int(cur.lastrowid)
            conn.execute(
                """
                UPDATE org_agency_reps
                SET name=?, agency=?, phone=?, email=?, notes=?
                WHERE id=? AND incident_id=?
                """,
                (
                    rep.name,
                    rep.agency,
                    rep.phone,
                    rep.email,
                    rep.notes,
                    rep.id,
                    self.incident_id,
                ),
            )
            conn.commit()
            return int(rep.id)

    def delete_agency_rep(self, rep_id: int) -> None:
        with get_incident_connection(self.incident_id) as conn:
            conn.execute(
                "DELETE FROM org_agency_reps WHERE id=? AND incident_id=?",
                (rep_id, self.incident_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------
    def apply_batch(self, items: Iterable[tuple[str, OrgUnit | Position]]) -> None:
        """Apply a batch of seed/template items to the incident."""

        created_unit_ids: list[int] = []
        with get_incident_connection(self.incident_id) as conn:
            for kind, obj in items:
                if kind == "unit" and isinstance(obj, OrgUnit):
                    parent_id = obj.parent_unit_id
                    if isinstance(parent_id, int) and parent_id < 0:
                        ref_index = abs(parent_id) - 1
                        if 0 <= ref_index < len(created_unit_ids):
                            parent_id = created_unit_ids[ref_index]
                        else:
                            parent_id = None
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO org_units (
                            incident_id, unit_type, name, parent_unit_id, sort_order
                        ) VALUES (?,?,?,?,?)
                        """,
                        (
                            self.incident_id,
                            obj.unit_type,
                            obj.name,
                            parent_id,
                            obj.sort_order,
                        ),
                    )
                    if cur.lastrowid:
                        created_unit_ids.append(int(cur.lastrowid))
                    else:
                        row = conn.execute(
                            "SELECT id FROM org_units WHERE incident_id=? AND unit_type=? AND name=?",
                            (self.incident_id, obj.unit_type, obj.name),
                        ).fetchone()
                        if row:
                            created_unit_ids.append(int(row["id"]))
                        else:
                            created_unit_ids.append(-1)
                elif kind == "position" and isinstance(obj, Position):
                    unit_id = obj.unit_id
                    if isinstance(unit_id, int) and unit_id < 0:
                        ref_index = abs(unit_id) - 1
                        if 0 <= ref_index < len(created_unit_ids):
                            mapped = created_unit_ids[ref_index]
                            unit_id = None if mapped < 0 else mapped
                        else:
                            unit_id = None
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO org_positions (
                            incident_id, title, unit_id, sort_order
                        ) VALUES (?,?,?,?)
                        """,
                        (
                            self.incident_id,
                            obj.title,
                            unit_id,
                            obj.sort_order,
                        ),
                    )
            conn.commit()
