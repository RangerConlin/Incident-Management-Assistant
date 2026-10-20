"""Bundle existing ICS PDF assets for headless servers; --check detects drift."""
from __future__ import annotations
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORMS = {"ics_202": "fema", "ics_204": "fema", "ics_209": "ics_canada", "ics_211": "fema", "ics_213rr": "fema", "ics_215": "ics_canada", "ics_215a": "fema", "ics_230": "fema"}
FORMS["ics_203"] = "fema"

def sync(check: bool = False) -> int:
    target = ROOT / "server/sarapp_db/sarapp_db/form_exports/assets"
    stale = []
    for form, form_set in FORMS.items():
        source = ROOT / "apps/desktop/sarapp_desktop/forms/sets" / form_set / form / "template.pdf"
        destination = target / f"{form}.pdf"
        content = source.read_bytes()
        if not destination.exists() or destination.read_bytes() != content:
            stale.append(form)
            if not check:
                target.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
        if form == "ics_203":
            mapping = source.with_name("mapping.json").read_bytes()
            bundled_mapping = target / "ics_203.json"
            if not bundled_mapping.exists() or bundled_mapping.read_bytes() != mapping:
                stale.append("ics_203 mapping")
                if not check:
                    bundled_mapping.write_bytes(mapping)
    for form_set in ("ics_canada", "uscg"):
        source = ROOT / "apps/desktop/sarapp_desktop/forms/sets" / form_set / "ics_203"
        for extension, name in (("pdf", "template.pdf"), ("json", "mapping.json")):
            content = (source / name).read_bytes()
            destination = target / f"ics_203_{form_set}.{extension}"
            if not destination.exists() or destination.read_bytes() != content:
                stale.append(f"ics_203 {form_set} {extension}")
                if not check:
                    destination.write_bytes(content)
    if check and stale:
        print("Stale server templates: " + ", ".join(stale))
        return 1
    print("Server ICS templates are current.")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    raise SystemExit(sync(parser.parse_args().check))
