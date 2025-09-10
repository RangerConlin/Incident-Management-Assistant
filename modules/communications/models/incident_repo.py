from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
from datetime import datetime

from utils.state import AppState

from .db import ensure_incident_schema, incident_cursor
from .master_repo import MasterRepository
from ..util import geo_line_rules


@dataclass
class ValidationMessage:
    level: str
    text: str


@dataclass
class ValidationReport:
    messages: List[ValidationMessage] = field(default_factory=list)

    @property
    def conflicts(self) -> int:
        return sum(1 for m in self.messages if m.level == 'conflict')

    @property
    def warnings(self) -> int:
        return sum(1 for m in self.messages if m.level == 'warning')


class IncidentRepository:
    def __init__(self, incident_number: str | int):
        self.incident_number = incident_number
        ensure_incident_schema(incident_number)

    # ------------------------------------------------------------------
    def list_plan(self) -> List[Dict[str, Any]]:
        with incident_cursor(self.incident_number) as cur:
            rows = cur.execute(
                'SELECT * FROM incident_channels ORDER BY sort_index, id'
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    def add_from_master(self, master_row: Dict[str, Any], defaults: Dict[str, Any] | None = None) -> Dict[str, Any]:
        defaults = defaults or {}
        now = datetime.utcnow().isoformat()
        band = self._infer_band(master_row)
        rx_freq = master_row.get('rx_freq')
        tx_freq = master_row.get('tx_freq')
        repeater = 1 if rx_freq and tx_freq and rx_freq != tx_freq else 0
        offset = (tx_freq - rx_freq) if repeater else None
        squelch_type, squelch_value = self._synth_squelch(master_row.get('rx_tone'))
        fields = {
            'master_id': master_row.get('id'),
            'channel': master_row.get('name'),
            'function': master_row.get('function', 'Tactical'),
            'band': band,
            'system': master_row.get('system'),
            'mode': master_row.get('mode'),
            'rx_freq': rx_freq,
            'tx_freq': tx_freq,
            'rx_tone': master_row.get('rx_tone'),
            'tx_tone': master_row.get('tx_tone'),
            'squelch_type': squelch_type,
            'squelch_value': squelch_value,
            'repeater': repeater,
            'offset': offset,
            'line_a': master_row.get('line_a', 0),
            'line_c': master_row.get('line_c', 0),
            'encryption': 'None',
            'priority': 'Normal',
            'include_on_205': 1,
            'remarks': master_row.get('notes'),
            'sort_index': 1000,
            'created_at': now,
            'updated_at': now,
        }
        fields.update(defaults)
        cols = ','.join(fields.keys())
        placeholders = ','.join('?' for _ in fields)
        with incident_cursor(self.incident_number) as cur:
            cur.execute(
                f'INSERT INTO incident_channels ({cols}) VALUES ({placeholders})',
                tuple(fields.values()),
            )
            row_id = cur.lastrowid
        return self.get_row(row_id)

    # ------------------------------------------------------------------
    def get_row(self, row_id: int) -> Dict[str, Any] | None:
        with incident_cursor(self.incident_number) as cur:
            row = cur.execute('SELECT * FROM incident_channels WHERE id=?', (row_id,)).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    def update_row(self, row_id: int, patch: Dict[str, Any]) -> None:
        if not patch:
            return
        patch['updated_at'] = datetime.utcnow().isoformat()
        sets = ','.join(f"{k}=?" for k in patch)
        with incident_cursor(self.incident_number) as cur:
            cur.execute(
                f'UPDATE incident_channels SET {sets} WHERE id=?',
                tuple(patch.values()) + (row_id,),
            )

    # ------------------------------------------------------------------
    def delete_row(self, row_id: int) -> None:
        with incident_cursor(self.incident_number) as cur:
            cur.execute('DELETE FROM incident_channels WHERE id=?', (row_id,))

    # ------------------------------------------------------------------
    def reorder(self, row_id: int, direction: str) -> None:
        delta = -1 if direction == 'up' else 1
        with incident_cursor(self.incident_number) as cur:
            cur.execute('SELECT sort_index FROM incident_channels WHERE id=?', (row_id,))
            row = cur.fetchone()
            if not row:
                return
            new_index = row['sort_index'] + delta
            cur.execute('UPDATE incident_channels SET sort_index=? WHERE id=?', (new_index, row_id))

    # ------------------------------------------------------------------
    def validate_plan(self) -> ValidationReport:
        report = ValidationReport()
        rows = self.list_plan()
        seen = {}
        for r in rows:
            key = (r['band'], r['mode'], r['rx_freq'], r['tx_freq'], r.get('rx_tone'), r.get('tx_tone'))
            if key in seen:
                report.messages.append(ValidationMessage('conflict', f"Duplicate freq for {r['channel']} and {seen[key]}"))
            else:
                seen[key] = r['channel']
            if r['function'] == 'Tactical' and not (r.get('assignment_division') and r.get('assignment_team')):
                report.messages.append(ValidationMessage('warning', f"{r['channel']} missing assignment"))
            if r.get('line_a') and not geo_line_rules.is_line_a_applicable(r):
                report.messages.append(ValidationMessage('warning', f"{r['channel']} requires Line A coordination"))
            if r.get('line_c') and not geo_line_rules.is_line_c_applicable(r):
                report.messages.append(ValidationMessage('warning', f"{r['channel']} requires Line C coordination"))
        return report

    # ------------------------------------------------------------------
    def preview_rows(self) -> List[Dict[str, Any]]:
        rows = self.list_plan()
        preview = []
        for r in rows:
            assignment = ' / '.join(filter(None, [r.get('assignment_division'), r.get('assignment_team')]))
            tone = r.get('rx_tone') or ''
            preview.append(
                {
                    'Function': r.get('function'),
                    'Channel': r.get('channel'),
                    'Assignment': assignment,
                    'RX': r.get('rx_freq'),
                    'TX': r.get('tx_freq'),
                    'ToneNAC': tone,
                    'Mode': r.get('mode'),
                    'Encryption': r.get('encryption'),
                    'Notes': r.get('remarks'),
                }
            )
        return preview

    # ------------------------------------------------------------------
    def _infer_band(self, row: Dict[str, Any]) -> str:
        f = row.get('rx_freq') or row.get('tx_freq') or 0
        try:
            f = float(f)
        except Exception:
            return 'Other'
        if 3 <= f < 30:
            return 'HF'
        if 30 <= f < 54:
            return 'VHF-LOW'
        if 118 <= f <= 137:
            return 'Air'
        if 156 <= f <= 163:
            return 'Marine'
        if 54 <= f < 300:
            return 'VHF'
        if 300 <= f < 700:
            return 'UHF'
        if 700 <= f <= 869:
            return '700/800'
        return 'Other'

    def _synth_squelch(self, tone: Any) -> tuple[str | None, str | None]:
        if tone is None:
            return None, None
        if tone == 'CSQ' or tone == '' or tone is None:
            return 'None', None
        try:
            float(tone)
            return 'CTCSS', str(tone)
        except Exception:
            if isinstance(tone, str) and tone.upper().startswith('F') or tone.isdigit():
                return 'DCS', str(tone)
        return None, None
