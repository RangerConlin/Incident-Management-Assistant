from __future__ import annotations

import argparse
import json
from pathlib import Path

from .render import render_form


def main() -> None:
    parser = argparse.ArgumentParser(description="Render ICS forms to PDF")
    parser.add_argument("--form", required=True, help="Form id, e.g., ics_205")
    parser.add_argument("--version", required=True, help="Template version, e.g., 2023.10")
    parser.add_argument("--infile", dest="in_file", required=True, help="Input JSON file")
    parser.add_argument("--out", dest="out_file", required=True, help="Output PDF path")
    parser.add_argument("--no-flatten", dest="flatten", action="store_false", help="Do not flatten form fields")
    args = parser.parse_args()

    data = json.loads(Path(args.in_file).read_text())
    pdf_bytes = render_form(args.form, args.version, data, options={"flatten": args.flatten})
    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pdf_bytes)


if __name__ == "__main__":
    main()
