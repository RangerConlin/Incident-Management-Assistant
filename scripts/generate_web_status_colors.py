"""Generate web_client/src/styles/statusColors.css from the Python source of truth.

styles/profiles/dark.py and light.py are the canonical status color
definitions (TEAM_STATUS, TASK_STATUS, RESOURCE_STATUS, TEAM_TYPE_COLORS).
Previously, web_client/src/styles/statusColors.css duplicated those values by
hand with a comment promising to "mirror" changes manually — which silently
drifted (TEAM_TYPE_COLORS' "K9" and "UTIL" entries existed on desktop but
were never added to the web copy). This script makes the Python dicts the
actual single source: run it any time a color changes in profiles/dark.py or
light.py, and it regenerates the CSS file deterministically. Never hand-edit
statusColors.css directly — edit the Python source and regenerate instead.

Usage: python scripts/generate_web_status_colors.py [--check]
  --check: exit non-zero if the generated output differs from the file on
  disk, without writing (for a pre-commit/CI drift check).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from styles.profiles import dark as dark_profile  # noqa: E402
from styles.profiles import light as light_profile  # noqa: E402

OUTPUT_PATH = REPO_ROOT / "web_client" / "src" / "styles" / "statusColors.css"

# (Python dict name, CSS var prefix) for the status-pair dicts (bg/fg).
STATUS_DICTS = [
    ("TEAM_STATUS", "team"),
    ("TASK_STATUS", "task"),
    ("RESOURCE_STATUS", "resource"),
    ("OBJECTIVE_STATUS", "objective"),
    ("OBJECTIVE_PRIORITY", "objective-priority"),
    ("OPERATIONAL_PERIOD_STATUS", "op-period"),
    ("MEETING_STATUS", "meeting"),
    ("SITREP_STATUS", "sitrep"),
]

# Hand-kept values with no Python dict equivalent (UI chrome, not a status
# vocabulary) — generated alongside the derived blocks so the file stays one
# piece, but these specific lines are not sourced from profiles/*.py.
SELECTED_OUTLINE = {"dark": "#5b9bd5", "light": "#1565c0"}
ALERT_ATTENTION = {"dark": "#a88f1a", "light": "#ffc107"}


def _slug(key: str) -> str:
    return key.strip().lower().replace(" ", "-").replace("/", "-")


def _hex(color: str) -> str:
    # profiles/light.py and dark.py mix #RRGGBB casing inconsistently;
    # normalize so the generated file doesn't vary by source-file whim.
    return color.lower()


def _status_block(profile_module, dict_name: str, css_prefix: str) -> list[str]:
    data: dict[str, dict[str, str]] = getattr(profile_module, dict_name)
    lines = [f"  /* {dict_name} */"]
    for key, colors in data.items():
        slug = _slug(key)
        lines.append(
            f"  --status-{css_prefix}-{slug}-bg: {_hex(colors['bg'])}; "
            f"--status-{css_prefix}-{slug}-fg: {_hex(colors['fg'])};"
        )
    return lines


def _team_type_block(profile_module) -> list[str]:
    data: dict[str, str] = profile_module.TEAM_TYPE_COLORS
    lines = ["  /* TEAM_TYPE_COLORS (single swatch, no fg pair) */"]
    for key, color in data.items():
        lines.append(f"  --team-type-{_slug(key)}: {_hex(color)};")
    return lines


def _theme_block(profile_module, theme: str) -> str:
    lines: list[str] = [f':root[data-theme="{theme}"] {{']
    for dict_name, css_prefix in STATUS_DICTS:
        lines.extend(_status_block(profile_module, dict_name, css_prefix))
        lines.append("")
    lines.extend(_team_type_block(profile_module))
    lines.append("")
    lines.append("  /* Selected-row outline (agents.md hard rule: every table needs one) */")
    lines.append(f"  --color-selected-outline: {SELECTED_OUTLINE[theme]};")
    lines.append("")
    lines.append("  /* Cross-cutting alert accent (needs-attention/overdue), not a status value */")
    lines.append(f"  --status-alert-attention-bg: {ALERT_ATTENTION[theme]};")
    lines.append("}")
    return "\n".join(lines)


def generate() -> str:
    header = '''/*
 * Status color tokens — GENERATED from styles/profiles/dark.py and light.py
 * by scripts/generate_web_status_colors.py. Do not hand-edit: edit the
 * Python source and re-run that script. This used to be a hand-maintained
 * duplicate with no shared source, which silently drifted (TEAM_TYPE_COLORS'
 * K9/UTIL entries existed on desktop but were missing here until this
 * generator was added). Multi-word status keys use hyphens in the variable
 * name (e.g. "out of service" -> --status-team-out-of-service-bg);
 * src/styles/statusColors.ts does the same substitution when looking a key
 * up.
 */
'''
    dark_block = _theme_block(dark_profile, "dark")
    light_block = _theme_block(light_profile, "light")
    return header + "\n" + dark_block + "\n\n" + light_block + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    content = generate()

    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if current != content:
            print(f"DRIFT: {OUTPUT_PATH} is stale — run scripts/generate_web_status_colors.py", file=sys.stderr)
            return 1
        print("statusColors.css is up to date.")
        return 0

    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
