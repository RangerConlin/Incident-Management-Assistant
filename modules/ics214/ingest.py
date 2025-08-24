"""Event ingestion wiring."""
from __future__ import annotations

import asyncio
from typing import List

from modules._infra.event_bus import bus
from .services import ingest_event_to_entries

TOPICS: List[str] = [
    "operations.team_status_change",
    "operations.task_status_change",
    "operations.team_assignment",
    "personnel.checkin",
    "personnel.checkout",
    "personnel.role_change",
    "communications.ics213_sent",
    "communications.alert_broadcast",
    "communications.channel_plan_update",
    "logistics.request_status_change",
    "logistics.equipment_checkout",
    "medical.incident_logged",
    "safety.report_flagged",
    "planning.op_rollover",
    "planning.objective_approved",
    "planning.sitrep_posted",
    "finance.time_milestone",
    "liaison.external_contact",
    "gis.hazard_update",
    "intel.clue_logged",
]

async def _worker(topic: str) -> None:
    queue = bus.subscribe(topic)
    while True:
        event = await queue.get()
        await asyncio.to_thread(ingest_event_to_entries, event)

async def start() -> None:
    for t in TOPICS:
        asyncio.create_task(_worker(t))
