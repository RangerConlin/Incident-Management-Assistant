from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import re

from pypdf import PdfReader
import yaml


# ---------- datatypes ----------
@dataclass
class PdfField:
    name: str
    type: Optional[str]
    page: Optional[int]


# ---------- utilities ----------


def extract_acroform_fields(pdf_path: Path) -> List[PdfField]:
    reader = PdfReader(str(pdf_path))
    try:
        fld = reader.get_fields()
    except Exception:
        fld = None
    fields: List[PdfField] = []
    if not fld:
        return fields
    for name, meta in fld.items():
        ftype = None
        if isinstance(meta, dict):
            raw_ft = meta.get("/FT")
            ftype = str(raw_ft) if raw_ft is not None else None
        fields.append(PdfField(name=str(name), type=ftype, page=None))
    fields.sort(key=lambda x: x.name)
    return fields


# basic candidate extraction from sample json


def flatten_json_paths(obj, prefix="") -> List[str]:
    paths: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            newp = f"{prefix}.{k}" if prefix else k
            paths.extend(flatten_json_paths(v, newp))
    elif isinstance(obj, list):
        newp = f"{prefix}[*]" if prefix else "[*]"
        if obj:
            paths.extend(flatten_json_paths(obj[0], newp))
        else:
            paths.append(newp)
    else:
        paths.append(prefix)
    return paths


def extract_schema_paths(schema_path: Optional[Path], sample_json: Optional[Path]) -> List[str]:
    candidates: List[str] = []
    if sample_json and sample_json.exists():
        data = json.loads(sample_json.read_text(encoding="utf-8"))
        candidates = flatten_json_paths(data)
    elif schema_path and schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        def walk(s, prefix=""):
            if not isinstance(s, dict):
                return
            # Object properties
            props = s.get("properties")
            if isinstance(props, dict):
                for k, v in props.items():
                    walk(v, f"{prefix}.{k}" if prefix else k)
                return
            # Arrays
            if s.get("type") == "array":
                items = s.get("items")
                newp = f"{prefix}[*]" if prefix else "[*]"
                if isinstance(items, dict):
                    walk(items, newp)
                return
            # Primitive leaf
            if s.get("type") in ("string", "number", "integer", "boolean") and prefix:
                candidates.append(prefix)

        walk(schema)
    return sorted(set(candidates))


# matching


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def best_match(field: str, candidates: List[str]) -> Optional[str]:
    key = _norm(field)
    if not candidates:
        return None
    scored: List[Tuple[int, str]] = []
    for c in candidates:
        ck = _norm(c)
        score = 0
        if ck == key:
            score += 100
        if ck in key or key in ck:
            score += 50
        toks_f = set(re.findall(r"[a-z0-9]+", key))
        toks_c = set(re.findall(r"[a-z0-9]+", ck))
        score += len(toks_f & toks_c)
        scored.append((score, c))
    scored.sort(reverse=True)
    top = scored[0]
    return top[1] if top[0] > 0 else None


# build mapping


def generate_map(
    pdf_path: Path,
    form_id: str,
    version: str,
    out_map_path: Path,
    schema: Optional[Path],
    sample_json: Optional[Path],
) -> Dict:
    fields = extract_acroform_fields(pdf_path)
    candidates = extract_schema_paths(schema, sample_json)

    mapping: Dict = {"form": form_id, "version": version, "fields": {}}
    for f in fields:
        suggestion = best_match(f.name, candidates) if candidates else None
        mapping["fields"][f.name] = suggestion or ""

    out_map_path.parent.mkdir(parents=True, exist_ok=True)
    out_map_path.write_text(
        yaml.dump(mapping, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return mapping


# facade kept for validators


def list_fields(pdf_path: Path) -> List[PdfField]:
    return extract_acroform_fields(pdf_path)

