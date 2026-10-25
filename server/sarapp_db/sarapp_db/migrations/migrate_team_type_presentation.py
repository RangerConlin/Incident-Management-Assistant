"""Convert Team Type Catalog presentation fields to the canonical shape.

Run against the central catalog before deploying clients that expect direct
hex colors. The migration is idempotent and removes the retired scope and
theme-key fields after converting their values.
"""
from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime, timezone

from pymongo.database import Database

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db

log = logging.getLogger(__name__)

_COLORS = {
    "team_type_search_rescue": "#228b22", "team_type_fire": "#c62828",
    "team_type_ems": "#00838f", "team_type_law_enforcement": "#1565c0",
    "team_type_aviation": "#00a8ff", "team_type_emergency_management": "#8e24aa",
    "team_type_public_works": "#ef6c00", "team_type_planned_event": "#008f6a",
    "team_type_general": "#7a7a7a", "team_type_default": "#7a7a7a",
}
_TEXT = {
    "team_text_white": "#ffffff", "team_text_light": "#f5f5f5",
    "team_text_black": "#000000", "team_text_dark": "#202020",
    "team_text_red": "#f44336", "team_text_blue": "#2196f3",
    "team_text_green": "#4caf50", "team_text_amber": "#ffc107",
    "team_text_cyan": "#00bcd4", "team_text_magenta": "#e040fb",
    "team_text_auto": "#ffffff",
}
_ICONS = {
    "direction_finding": "df", "fixed_wing": "fixed_wing", "helicopter": "helo",
    "utilities": "util", "support": "util", "engine": "truck", "brush": "pickup",
    "ambulance": "van", "patrol": "car",
}
_VALID_ICONS = {"team", "df", "car", "pickup", "van", "truck", "util", "k9", "uas", "fixed_wing", "helo"}


def _color(value: str, aliases: dict[str, str], default: str) -> str:
    resolved = aliases.get(value, value).lower()
    return resolved if re.fullmatch(r"#[0-9a-f]{6}", resolved) else default


def migrate(*, db: Database | None = None, dry_run: bool = False) -> dict[str, int]:
    collection = (db if db is not None else get_master_db())[MasterCollections.TEAM_TYPES]
    changed = 0
    for row in collection.find({}):
        background = str(row.get("background_color") or row.get("color_key") or "#7a7a7a")
        text = str(row.get("text_color") or row.get("text_color_key") or "#ffffff")
        icon = _ICONS.get(str(row.get("icon_key") or "team"), str(row.get("icon_key") or "team"))
        desired = {
            "background_color": _color(background, _COLORS, "#7a7a7a"),
            "text_color": _color(text, _TEXT, "#ffffff"),
            "icon_key": icon if icon in _VALID_ICONS else "team",
        }
        retired = ("scope", "organization_id", "color_key", "text_color_key")
        if all(row.get(key) == value for key, value in desired.items()) and not any(key in row for key in retired):
            continue
        update = {
            "$set": {
                **desired,
                "version": int(row.get("version") or 1) + 1,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$unset": {key: "" for key in retired},
        }
        changed += 1
        if not dry_run:
            collection.update_one({"_id": row["_id"]}, update)
    result = {"team_types_converted": changed}
    log.info("Team type presentation migration%s: %s", " (dry run)" if dry_run else "", result)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
