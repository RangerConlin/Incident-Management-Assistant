"""One-time seed: insert the generic "Default GAR" risk-assessment template.

GAR templates (data/db/sarapp_db/api/routers/gar_templates.py) are an
admin-editable master library — there is no built-in content until one is
seeded. This script inserts one starting template with objective,
discrete-option criteria for the six standard GAR factors (Supervision,
Planning, Team Selection, Team Fitness, Environment, Event Complexity), each
broken into a couple of concrete sub-criteria rows rather than a free 1-10
dial. It is deliberately generic (not tied to any one organization's SOP) —
edit it from the GAR Template Editor once seeded, or clone it as a starting
point for an org-specific rubric (e.g. a CAP wing's own ORM form).

Idempotent: does nothing if a template named "Default GAR" already exists.

Run with SARAPP_MONGO_URI set in the environment:

    python -m sarapp_db.migrations.seed_default_gar_template

Add --dry-run to preview without writing anything.
"""
from __future__ import annotations

import argparse
import logging

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.mongo.repository import BaseRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

TEMPLATE_NAME = "Default GAR"


class _GarTemplatesRepository(BaseRepository):
    collection_name = MasterCollections.GAR_TEMPLATES
    soft_deletes = False


def _option(id_: str, label: str, points: int, *, no_go: bool = False) -> dict:
    return {"id": id_, "label": label, "points": points, "no_go": no_go}


def _row(id_: str, label: str, options: list[dict]) -> dict:
    return {"id": id_, "label": label, "options": options}


def _group(id_: str, name: str, rows: list[dict]) -> dict:
    return {"id": id_, "name": name, "rows": rows}


def build_default_template() -> dict:
    groups = [
        _group(
            "supervision",
            "Supervision",
            [
                _row(
                    "leadership",
                    "On-scene leadership",
                    [
                        _option("good", "Experienced leader on-scene", 0),
                        _option("fair", "Leader reachable by radio/phone, periodic check-ins", 5),
                        _option(
                            "poor",
                            "No qualified leader assigned, or leader unreachable",
                            10,
                            no_go=True,
                        ),
                    ],
                ),
                _row(
                    "leader_currency",
                    "Leader currency/experience in this role",
                    [
                        _option("current", "Active in this role within the last 90 days", 0),
                        _option("lapsed", "Active in this role within the last year", 5),
                        _option("new", "First assignment in this role, or no recent activity", 10),
                    ],
                ),
            ],
        ),
        _group(
            "planning",
            "Planning",
            [
                _row(
                    "assignment_clarity",
                    "Assignment clarity",
                    [
                        _option("clear", "Clear, written assignment with defined objectives", 0),
                        _option("verbal", "Verbal assignment only, objectives general", 5),
                        _option("unclear", "Assignment unclear or still being defined", 10),
                    ],
                ),
                _row(
                    "hazard_review",
                    "Hazard review / mitigation briefing",
                    [
                        _option("briefed", "Hazards identified and mitigations briefed to team", 0),
                        _option("pending", "Hazards identified, mitigations still pending", 5),
                        _option("none", "No hazard review completed for this assignment", 10),
                    ],
                ),
            ],
        ),
        _group(
            "team_selection",
            "Team Selection",
            [
                _row(
                    "qualifications",
                    "Team qualifications for this assignment",
                    [
                        _option("met", "All members meet qualification requirements", 0),
                        _option("mitigated", "Some members below preferred qualification, mitigated", 5),
                        _option("unmet", "Team lacks required qualifications for this assignment", 10),
                    ],
                ),
                _row(
                    "familiarity",
                    "Team familiarity",
                    [
                        _option("together", "Team has worked together before", 0),
                        _option("mixed", "Partially familiar / mixed team", 5),
                        _option("first_time", "First time this group has worked together", 10),
                    ],
                ),
            ],
        ),
        _group(
            "team_fitness",
            "Team Fitness",
            [
                _row(
                    "rest",
                    "Rest / fatigue level",
                    [
                        _option("rested", "Well-rested, within duty-day limits", 0),
                        _option("moderate", "Moderate fatigue, approaching duty-day limit", 5),
                        _option("fatigued", "Fatigued, or exceeding duty-day limit", 10, no_go=True),
                    ],
                ),
                _row(
                    "medical",
                    "Medical / physical readiness",
                    [
                        _option("none", "No known limitations", 0),
                        _option("minor", "Minor limitations noted, accommodated", 5),
                        _option(
                            "limiting",
                            "Known condition affecting capability to perform this assignment",
                            10,
                            no_go=True,
                        ),
                    ],
                ),
            ],
        ),
        _group(
            "environment",
            "Environment",
            [
                _row(
                    "weather",
                    "Weather conditions",
                    [
                        _option("normal", "Within normal operating range", 0),
                        _option("marginal", "Marginal (precipitation, wind, or temperature extremes)", 5),
                        _option("severe", "Severe/hazardous weather in effect", 10),
                    ],
                ),
                _row(
                    "terrain_light",
                    "Terrain / light conditions",
                    [
                        _option("favorable", "Favorable terrain, daylight", 0),
                        _option("moderate", "Moderate terrain, or low-light conditions", 5),
                        _option("adverse", "Rugged terrain, or night operations", 10),
                    ],
                ),
            ],
        ),
        _group(
            "event_complexity",
            "Event Complexity",
            [
                _row(
                    "tempo",
                    "Operational tempo",
                    [
                        _option("normal", "Normal number of concurrent resources", 0),
                        _option("elevated", "Elevated tempo, multiple concurrent operations", 5),
                        _option("high", "High tempo, many concurrent resources, limited coordination", 10),
                    ],
                ),
                _row(
                    "comms",
                    "Communications with command",
                    [
                        _option("reliable", "Reliable comms with command", 0),
                        _option("intermittent", "Intermittent comms with command", 5),
                        _option("none", "No reliable comms with command", 10, no_go=True),
                    ],
                ),
            ],
        ),
    ]

    # 12 rows total, 0/5/10 each — max possible score is 120.
    bands = [
        {"floor": 70, "label": "Red", "required_reviewer": "Incident Commander"},
        {"floor": 40, "label": "Amber", "required_reviewer": "Operations Section Chief / Safety Officer"},
        {"floor": 0, "label": "Green", "required_reviewer": "Team Leader"},
    ]

    return {
        "name": TEMPLATE_NAME,
        "source": "Generic",
        "description": (
            "Starting GAR rubric with objective, discrete-option criteria across the six "
            "standard GAR factors. Edit or clone this template to match your organization's "
            "own risk-management SOP."
        ),
        "groups": groups,
        "bands": bands,
        "active": True,
        "created_by": "",
        "updated_by": "",
    }


def seed(*, dry_run: bool = False) -> bool:
    repo = _GarTemplatesRepository(get_master_db())
    existing = repo.find_one({"name": TEMPLATE_NAME})
    if existing:
        log.info("Template '%s' already exists (id=%s) — nothing to do.", TEMPLATE_NAME, existing.get("id"))
        return False

    doc = build_default_template()
    docs = repo.find_many({"id": {"$exists": True}}, sort=[("id", -1)], limit=1)
    doc["id"] = int((docs[0] if docs else {}).get("id") or 0) + 1

    if dry_run:
        log.info("[dry-run] Would insert template '%s' with id=%s", TEMPLATE_NAME, doc["id"])
        return True

    repo.insert_one(doc)
    log.info("Inserted template '%s' with id=%s", TEMPLATE_NAME, doc["id"])
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing anything.")
    args = parser.parse_args()
    seed(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
