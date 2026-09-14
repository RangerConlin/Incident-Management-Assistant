# Form Builder Inventory

Bound means `template.pdf` and `mapping.json` both exist. **Partial (X%)** means at least one
real fillable field is bound but not all of them are — X is the percentage of the PDF's actual
fillable fields (leaf AcroForm fields only; see Methodology) that resolve to a real value, either
directly in `mapping.json` or via a `row_groups` repeating-table pattern. **Not Bound** means the
PDF/mapping pair exists but zero real fields resolve to a value (including forms whose
`template.pdf` has no fillable AcroForm fields at all). Audited 2026-07-27, corrected same day
after the first two passes miscounted — see Revision History.

| Form | FEMA | ICS Canada | USCG | SAR | CAP | Builder Level We Can Create |
|---|---:|---:|---:|---:|---:|---|
| ICS 201 | Partial (42.1%) | Partial (50.3%) | Partial (41.4%) | - | - | Generic exists; precise possible |
| ICS 202 | Bound | Not Bound | Bound | - | - | Generic exists; precise possible |
| ICS 203 | Partial (87.1%) | Partial (22.6%) | Partial (69.7%) | - | - | Generic exists; precise possible |
| ICS 204 | Partial (11.7%) | Not Bound | - | - | - | Generic + work-assignment builders exist |
| ICS 205 | Bound | Bound | Bound | - | - | Generic exists; precise possible |
| ICS 205A | Mapping | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 206 | Bound | Bound | - | - | - | Precise medical-plan builder exists |
| ICS 207 | Partial (65.9%) | Partial (21.3%) | Partial (36.6%) | - | - | Generic exists; precise possible |
| ICS 208 | Partial (57.1%) | Partial (66.7%) | - | - | - | Generic exists; precise possible |
| ICS 209 | Mapping | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 210 | Mapping | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 211 | Partial (2.5%) | Not Bound | - | - | - | Generic exists; precise possible |
| ICS 213 | Partial (6.7%) | Not Bound | - | - | - | Generic exists; precise possible |
| ICS 213RR | Partial (2.4%) | Not Bound | - | - | - | Generic + work-assignment builders exist |
| ICS 214 | Partial (98.8%) | Partial (53.8%) | Partial (94.7%) | - | - | Generic exists; precise possible |
| ICS 215 | Mapping | Not Bound | - | - | - | Generic + work-assignment builders exist |
| ICS 215A | Bound | Not Bound | - | - | - | Generic + work-assignment builders exist |
| ICS 217 | Partial (69.3%) | Not Bound | - | - | - | Generic exists; precise possible |
| ICS 218 | Partial (59.2%) | Not Bound | - | - | - | Generic exists; precise possible |
| ICS 220 | Mapping | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 221 | Partial (5.5%) | Not Bound | - | - | - | Generic exists; precise possible |
| ICS 225 | Template | - | - | - | - | Generic exists; binding needed |
| ICS 230 | Template | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 233 | Template | Not Bound† | Template | - | - | Generic exists; precise possible via ICS Canada |
| ICS 309 | Template | Partial (83.6%) | - | Partial (98.9%) | Partial (70.9%) | Generic exists; precise possible |
| SAR 100 | - | - | - | Partial (85.7%) | - | Generic exists; precise possible |
| SAR 100A | - | - | - | Partial (96.7%) | - | Generic exists; precise possible |
| SAR 100B | - | - | - | Not Bound‡ | - | Generic exists; precise possible |
| SAR 102 | - | - | - | Not Bound‡ | - | Generic exists; precise possible |
| SAR 104 | - | - | - | Bound | - | Generic exists; precise possible |
| SAR 110 | - | - | - | Partial (65.1%) | - | Generic exists; precise possible |
| SAR 112 | - | - | - | Partial (34.2%) | - | Generic exists; precise possible |
| SAR 115 | - | - | - | Partial (34.4%) | - | Generic exists; precise possible |
| SAR 116 | - | - | - | Partial (40.0%) | - | Generic exists; precise possible |
| SAR 119 | - | - | - | Partial (75.0%) | - | Generic exists; precise possible |
| SAR 125 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 125A | - | - | - | Template | - | Generic exists; binding needed |
| SAR 131 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 132 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 134 | - | - | - | Partial (43.2%) | - | Generic exists; precise possible |
| SAR 135 | - | - | - | Bound | - | Precise SAR 135 clue builder exists |
| SAR 301 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 301A | - | - | - | Template | - | Generic exists; binding needed |
| SAR 302 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 304 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 305 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 306 | - | - | - | Template | - | Generic exists; binding needed |
| SAR 307 | - | - | - | Template | - | Generic exists; binding needed |
| CAPF 104 | - | - | - | - | Partial (62.8%) | Generic exists; precise possible |
| CAPF 104A | - | - | - | - | Template | Generic exists; binding needed |
| CAPF 106 | - | - | - | - | Partial (17.5%) | Generic exists; precise possible |
| CAPF 109 | - | - | - | - | Bound | Precise task-assignment builder exists |
| CAPF 160 | - | - | - | - | Partial (23.7%) | Generic exists; precise possible |
| MIWGF 52 | - | - | - | - | Template | Generic exists; binding needed |

† `forms/sets/ics_canada/ics_233/mapping.json` is present but empty (`"fields": []`), and
`template.pdf` has no AcroForm fields at all (not a fillable PDF).

‡ `forms/sets/sar/sar_100b/mapping.json` and `forms/sets/sar/sar_102/mapping.json` are both the
generic starter scaffold (`"fields": []`, `_comment: "Replace source values..."`), and neither
`template.pdf` has AcroForm fields either. No actual binding work has been done on either.

## Methodology

For each form marked "Bound" (both `template.pdf` and `mapping.json` present), `template.pdf`'s
AcroForm was walked with `pypdf.PdfReader.get_fields()`. Only **leaf fields** (`/FT` is set — an
actual `/Tx`, `/Btn`, or `/Ch` widget) count toward the total; hierarchical parent/group nodes
(`/FT` is `None`, e.g. `POD.h` grouping `POD.h.responsive`/`.unresponsive`/`.clues`) are excluded
entirely, since they have no value of their own and nothing ever writes to them directly. A leaf
field counts as bound if either:
- it has a matching `fields[]` entry in `mapping.json` with a non-empty `source`, or
- its name matches a `row_groups[].col_patterns` regex, meaning it's populated dynamically from a
  repeating array (e.g. `sar_104`'s `team_members_member_name{n}` fields, filled row-by-row from
  the team roster rather than bound individually).

Percentage = bound leaf fields / total leaf fields.

**This counts wiring, not correctness.** A field can have a non-empty `source` and still be wired
to the wrong data, or produce the wrong value for the form's intended behavior — that's a
per-field logic review, not something this audit checks. (One such question was raised and
resolved for `sar_104`'s POD checkbox grid during this audit: the "only one of high/medium/low
checked per row" behavior turned out to already be correctly implemented in
`modules/operations/taskings/repository.py`'s `_build_pod_matrix()`, which computes the exclusive
checkbox state before the mapping ever sees it — the mapping itself is a straight 1:1 wire.)

## Revision History

- **2026-07-27, pass 1**: Counted any `mapping.json` field with an empty `source` as unbound,
  with no PDF cross-check. Wrong on two counts: didn't verify entries actually corresponded to
  real PDF fields, and didn't know about `row_groups`.
- **2026-07-27, pass 2**: Cross-checked mapping entries against real PDF field names, but still
  counted parent/group nodes (`/FT is None`) as fields needing their own binding, and still didn't
  account for `row_groups` coverage. This undercounted every form with hierarchical field names
  (e.g. `sar_104` showed 52.9% when it's actually 100%).
- **2026-07-27, pass 3 (current)**: Leaf-fields-only, row-group aware. Matches the app's own
  `_is_mapped()` / `_count_unmapped()` logic in
  `modules/forms_creator/ui/MapperWindow.py` and `modules/forms_creator/form_set_registry.py`.

Default builder rule: use one builder per form concept, not one per form set/version. Add separate FEMA, USCG, ICS Canada, SAR, or CAP builders only when the data meaning genuinely differs.
