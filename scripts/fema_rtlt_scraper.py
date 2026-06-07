#!/usr/bin/env python3
"""
Scrape FEMA NIMS Resource Typing Library Tool (RTLT).

Fetches all Resource Typing Definitions (508 series) from
rtlt.preptoolkit.fema.gov across all paginated list pages, then fetches
each individual detail page to extract kind, discipline, and description.

Saves results to data/fema_resource_types_raw.json.

Usage:
    python scripts/fema_rtlt_scraper.py
    python scripts/fema_rtlt_scraper.py --resume    # skip already-fetched IDs
    python scripts/fema_rtlt_scraper.py --list-only # only collect IDs/names, skip details
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

import httpx

BASE_URL = "https://rtlt.preptoolkit.fema.gov"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "fema_resource_types_raw.json"
TOTAL_PAGES = 25
RATE_LIMIT_SECS = 0.5


# ---------------------------------------------------------------------------
# HTML parsers
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Strips HTML tags; yields text nodes in document order."""

    SKIP_TAGS = {"script", "style", "head"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data):
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self.chunks.append(stripped)


def _strip_html(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return " ".join(p.chunks)


class _ListPageParser(HTMLParser):
    """Extract Resource Typing Definition IDs and names from a browse page."""

    RTD_PATTERN = re.compile(r"/Public/Resource/View/(\d+-508-\d+)")

    def __init__(self):
        super().__init__()
        self.entries: list[dict] = []
        self._href: str | None = None
        self._in_link = False
        self._label: str = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            m = self.RTD_PATTERN.search(href)
            if m:
                self._href = href
                self._label = ""
                self._in_link = True

    def handle_data(self, data):
        if self._in_link:
            self._label += data

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            m = self.RTD_PATTERN.search(self._href or "")
            label = self._label.strip()
            # Skip action-button links whose text is just "View", "PDF", etc.
            if m and len(label) > 4:
                self.entries.append({
                    "id": m.group(1),
                    "name": label,
                })
            self._in_link = False
            self._href = None


def _parse_list_page(html: str) -> list[dict]:
    p = _ListPageParser()
    p.feed(html)
    return p.entries


# ---------------------------------------------------------------------------
# Detail page parsing
# ---------------------------------------------------------------------------

# Labels that appear in the page followed immediately by the value.
# The parser looks for these as text chunks and grabs the next non-empty chunk.
_LABEL_MAP = {
    "Kind:": "kind",
    "Kind": "kind",
    "Resource Category:": "discipline",
    "Resource Category": "discipline",
    "Primary Core Capability:": "primary_core_capability",
    "Primary Core Capability": "primary_core_capability",
}


def _parse_detail_page(html: str, resource_id: str) -> dict:
    """Return a dict with kind, discipline, description, type_levels from the detail page."""

    text = _strip_html(html)
    chunks = text.split()

    result: dict = {
        "id": resource_id,
        "kind": "",
        "discipline": "",
        "primary_core_capability": "",
        "description": "",
        "type_levels": [],
    }

    # ---- Label-value extraction using the full text ----
    # Build a version with normalized spacing for regex
    norm = " ".join(chunks)

    # Field extraction — labels appear directly adjacent to values with a single space.
    # Pattern: "Resource Kind Equipment Overall Function ..."
    for pattern, field in [
        (r"Resource Kind\s+([A-Za-z][A-Za-z ]{1,30}?)(?:\s{2,}|Overall Function|Composition|Component|\Z)", "kind"),
        (r"Resource Category\s+([A-Za-z/,& ]+?)(?:Primary Core Capability|Secondary Core Capability|Resource Kind|Status|\Z)", "discipline"),
        (r"Primary Core Capability\s+([A-Za-z/,& ]+?)(?:Secondary Core Capability|Resource Kind|Status|\Z)", "primary_core_capability"),
    ]:
        m = re.search(pattern, norm, re.IGNORECASE)
        if m:
            result[field] = m.group(1).strip().rstrip(":")

    # ---- Type level detection ----
    type_levels_raw = re.findall(r"\bType\s+([1-4]|I{1,3}V?|IV)\b", norm, re.IGNORECASE)
    # Normalise to "Type I", "Type II", etc.
    roman_map = {"1": "Type I", "2": "Type II", "3": "Type III", "4": "Type IV",
                 "I": "Type I", "II": "Type II", "III": "Type III", "IV": "Type IV"}
    seen: dict = {}
    for raw in type_levels_raw:
        key = roman_map.get(raw.upper(), f"Type {raw}")
        seen[key] = True
    result["type_levels"] = list(seen.keys())

    # ---- Description: grab the first long sentence-like text ----
    # Look for the block that follows "Description" label in the text
    desc_m = re.search(
        r"Description[:\s]+(.{30,300}?)(?:\s{2,}|Type\s+[1-4]|Core Capability|Personnel|Minimum)",
        norm, re.IGNORECASE | re.DOTALL,
    )
    if desc_m:
        result["description"] = desc_m.group(1).strip()

    return result


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch(client: httpx.Client, url: str) -> str:
    resp = client.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# Main scrape logic
# ---------------------------------------------------------------------------

def scrape(resume: bool = False, list_only: bool = False) -> list[dict]:
    existing: dict[str, dict] = {}
    if resume and OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            for rec in json.load(f):
                existing[rec["id"]] = rec
        print(f"Resuming: {len(existing)} records already cached.")

    headers = {
        "User-Agent": "SARA-App/1.0 FEMA-RTLT-Data-Collector (emergency-management-software)",
        "Accept": "text/html,application/xhtml+xml",
    }

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        # Phase 1 — collect all RTD IDs/names from browse pages
        all_entries: list[dict] = []
        for page_num in range(1, TOTAL_PAGES + 1):
            # The server ignores ?p=1; use the bare URL for page 1.
            url = (f"{BASE_URL}/Public/Combined"
                   if page_num == 1
                   else f"{BASE_URL}/Public/Combined?p={page_num}")
            print(f"  List page {page_num:2d}/{TOTAL_PAGES} ... ", end="", flush=True)
            try:
                html = _fetch(client, url)
                entries = _parse_list_page(html)
                all_entries.extend(entries)
                print(f"{len(entries)} RTDs")
            except Exception as exc:
                print(f"ERROR: {exc}")
            time.sleep(RATE_LIMIT_SECS)

        # Deduplicate by ID (the same ID can appear across pages due to server-side filtering)
        seen_ids: set[str] = set()
        unique_entries: list[dict] = []
        for e in all_entries:
            if e["id"] not in seen_ids:
                seen_ids.add(e["id"])
                unique_entries.append(e)

        print(f"\nTotal unique Resource Typing Definitions: {len(unique_entries)}")

        if list_only:
            return unique_entries

        # Phase 2 — fetch each detail page
        results: list[dict] = []
        for i, entry in enumerate(unique_entries, 1):
            rid = entry["id"]
            name = entry["name"]

            if resume and rid in existing:
                print(f"  [{i:3d}/{len(unique_entries)}] {rid:15s} SKIP (cached)")
                results.append(existing[rid])
                continue

            url = f"{BASE_URL}/Public/Resource/View/{rid}"
            print(f"  [{i:3d}/{len(unique_entries)}] {rid:15s} ", end="", flush=True)
            try:
                html = _fetch(client, url)
                detail = _parse_detail_page(html, rid)
                detail["name"] = name
                detail["reference_url"] = url
                results.append(detail)
                print(f"kind={detail['kind'] or '?':12s}  discipline={detail['discipline'] or '?'}")
            except Exception as exc:
                print(f"ERROR: {exc}")
                results.append({
                    "id": rid,
                    "name": name,
                    "reference_url": url,
                    "error": str(exc),
                    "kind": "",
                    "discipline": "",
                    "type_levels": [],
                    "description": "",
                })
            time.sleep(RATE_LIMIT_SECS)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape FEMA RTLT Resource Typing Definitions")
    parser.add_argument("--resume", action="store_true",
                        help="Skip IDs already present in the output file")
    parser.add_argument("--list-only", action="store_true",
                        help="Only collect IDs and names; skip individual detail pages")
    args = parser.parse_args()

    print("FEMA RTLT Scraper")
    print("=" * 60)
    print(f"Output: {OUTPUT_PATH}\n")

    results = scrape(resume=args.resume, list_only=args.list_only)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    success = sum(1 for r in results if "error" not in r)
    errors = len(results) - success
    print(f"\nDone. {success} records saved, {errors} errors.")
    print(f"Output: {OUTPUT_PATH}")

    if errors:
        print("\nFailed IDs:")
        for r in results:
            if "error" in r:
                print(f"  {r['id']}: {r['error']}")


if __name__ == "__main__":
    main()
