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
| ICS 203 | Partial (87.1%)¶ | Partial (96.2%)¶ | Partial (76.2%)¶ | - | - | Precise ICS-203 builder exists (`Ics203FormBuilder`) |
| ICS 204 | Partial (11.7%) | Not Bound | - | - | - | Generic + work-assignment builders exist |
| ICS 205 | Bound | Bound | Bound | - | - | Generic exists; precise possible |
| ICS 205A | Mapping | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 206 | Bound | Bound | - | - | - | Precise medical-plan builder exists |
| ICS 207 | Partial (65.9%) | Partial (21.3%) | Partial (36.6%) | - | - | Generic exists; precise possible |
| ICS 208 | Partial (57.1%) | Partial (66.7%) | - | - | - | Generic exists; precise possible |
| ICS 209 | Mapping | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 210 | Mapping | Not Bound | - | - | - | Generic exists; precise possible via ICS Canada |
| ICS 211 | Partial (65.6%)‖ | Not Bound | - | - | - | Generic exists; precise possible |
| ICS 213 | Partial (6.7%) | Not Bound | - | - | - | Generic exists; precise possible |
| ICS 213RR | Partial (40.5%)§ | Not Bound | - | - | - | Precise resource-request builder exists |
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

§ `forms/sets/fema/ics_213rr/mapping.json` was rebuilt 2026-09-14: the previous mapping mixed the
real FEMA field names (mostly unbound) with a second block of ~30 stray field names
(`IncidentName`, `ResourceType1..6`, `organization.logistics_section_chief.name`, etc.) that don't
exist in `template.pdf` at all — leftovers copied from an unrelated form/domain. That block was
removed and the real fields wired to `modules.logistics.resource_requests` via
`modules.forms_creator.exporting.builders.resource_requests.ResourceRequestFormBuilder`. The
remaining unbound leaf fields have no current data source: per-item `Type`/`Cost`/arrival-date
columns (the `RequestItem` model only tracks kind/description/quantity/unit), the requestor's
name/position (only a `created_by_id`, no personnel lookup wired), substitute-sources text, the
logistics order number and supplier contact info, the finance reply/section chief/log-rep
signature fields (three are `/Sig` widgets anyway, not fillable text), and the "Low" priority
checkbox (the app's `Priority` enum is `IMMEDIATE`/`HIGH`/`ROUTINE`, which doesn't line up 1:1 with
the form's `Urgent`/`Routine`/`Low` — `HIGH` currently renders as no checkbox at all). ICS Canada's
`ics_213rr` mapping was not touched in this pass.

¶ ICS 203 re-audited and largely rebuilt 2026-09-14 (see `BINDING_PIPELINE.md`'s checklist for the
per-field detail):
- **FEMA** (87.1%, unchanged number): fixed one real bug found in passing — the `Service Branch
  Director` field was bound to `organization.service_branch_director.title` (the position's own
  title text) instead of `.name` (the assigned person), the only field on this form still doing
  that after the earlier `ics_203` resolution session. Bound-field count didn't change since the
  field already counted as "bound" (wrongly) before the fix. The remaining 15 unbound leaf fields
  are all fields already documented as unresolved/no-data-source in the "ics_203 resolution"
  section of `BINDING_PIPELINE.md` from the earlier session (`Operations Section Alternate`,
  `Air Ops Branch Director 2/3`, `Branch Director Deputy 1/3/5`, etc.) — nothing new found.
- **ICS Canada** (22.6% → 96.2%): the mapping was built against a differently-renamed copy of this
  PDF — almost every `organization.*`/branch/division field name was missing the real template's
  numeric/lettered section prefix (`5. `, `7. `, `8. `, `9. `, `a.`, `b.`, `c.`, `d. `), and the
  `org_branches` row-group used a single `{n}`-substitution pattern that can't express this
  template's real (irregular) division-supervisor field naming across the three branches. Rebuilt
  field-by-field against the real template's AcroForm names; org_branches now uses explicit
  `org_branches.<0-2>.*` entries instead of a row_groups pattern (see BINDING_PIPELINE.md's ICS-203
  section for why, mirroring the earlier FEMA case). Also dropped ~55 dead/duplicate mapping
  entries (empty-source placeholders, and entries referencing field names that don't exist in this
  template at all). The remaining 4 unbound fields (`d. AIR OPERATIONS BRANCH Position1/2`,
  `Row1/2`) have no printed label anywhere on the form to key off of — left unresolved, same
  ambiguity as FEMA's analogous fields.
- **USCG** (69.7% → 76.2%): most of the pre-existing bindings were already accurate, but ~50 of the
  mapping's `fields[]` entries were dead weight — either references to field names that don't exist
  anywhere in this template (leftover from an unrelated form/version), or redundant empty-source
  placeholders for fields the `org_branches`/`planning_tech_specialists` row_groups already cover.
  Those placeholders were silently shadowing the row-groups' real values in `PDFFiller.fill()`'s
  warnings output (the row-group fill still ran and produced a correct PDF, but every test-fill
  logged dozens of false "no value resolved" warnings for fields that were actually filled) — a
  real test-fill went from 82 warnings to 37. Also split the `planning_tech_specialists` row_group
  in two (name: 3 rows, specialty: 2 rows — the template only has `tech_specialty1`/`2`, not `3`),
  and fixed `Date/Time0`/`Date/Time1` (operational period) from raw ISO timestamps to the
  `datetime_human` transform per this repo's human-readable-timestamp rule. Checking real widget
  `/Rect` positions (not just field names) found `DivisionGroup_6`/`_12` are branch 1/2's 6th
  division/group slot (immediately below their `div_5_name{1,2}` row, same row spacing) — bound to
  `org_branches.<0,1>.divisions.5.name`. The remaining `DivisionGroup_13`-`_18` sit in a visually
  separate block (a ~56pt gap versus the ~14.5pt spacing used everywhere else, containing the
  Logistics/Intelligence section headers) with no `branch_id3` field printed for a third branch —
  confirmed with the user these are the Intelligence/Investigations Section's own Division/Group
  list (USCG gives Intel more emphasis than FEMA/ICS-Canada do), printed without a repeated
  Branch/Director/Deputy header since Intel's Chief/Deputy already have their own fields elsewhere
  (`Chief_3`/`Deputy_5`). `_build_org_branches` isn't scoped to Operations Section - it returns
  every `classification == "branch"` unit incident-wide - so an Intel branch lands in the same
  `org_branches` list positionally; bound to `org_branches.2.divisions.<0-5>.name`.

‖ `forms/sets/fema/ics_211/mapping.json` rebuilt 2026-09-14 (2.5% → 65.6%): the old mapping mixed
the real per-row field names (`R1 State`, `R2 Category`, etc. — all with empty `source`) with ~90
stray entries (`IncidentName`, `Name1`-`Name20`, `Agency1`-`Agency20`, `RadioID1`-`RadioID20`,
`PreparedBy`, `CheckInDateTime`, `CheckInLocation`, etc.) that don't exist anywhere in this
template — the same leftover-mapping pattern seen in the `ics_213rr` and `ics_221` cases. Those
stray entries were removed. The 8-row repeating check-in table (18 columns x 8 rows, real field
names irregular per row — e.g. row 1 is `R1 Order Request`, row 2 is `R2 Order Request Row2`) is
now filled from a new `context.py` builder, `_build_checkin_list`, exposed as `data["checkin_list"]`
and wired via the `pdf_filler.py` row_groups `row_fields` mechanism (explicit per-row field-name
list — same lesson as the FEMA/ICS-Canada `ics_203` cases: irregular per-row naming can't use a
`{n}`-substitution `col_patterns` pattern). `row_fields` gained `transform` support in this pass
(previously only the top-level `fields[]` mechanism supported it) so `Date/Time Check In` can use
the existing `datetime_human` transform instead of a hand-rolled format.

`_build_checkin_list` flattens every currently-checked-in resource (any type) from the unified
`resource_status` collection, joined against the per-type master record for agency/kind/type, plus
checked-in teams (from `/checkin/teams/checked-state`) as separate Strike Team/Task Force rows.
Nine of the eighteen per-row columns still have no real data anywhere in the app and are left
blank: State, Order/Request #, Home Unit (vehicle/aircraft/equipment — personnel's `home_unit`
master field is wired), Departure Point, Method of Travel, Other Qualifications, and Date
Resources Returned to Unit. See this session's final report for the full "no data source" list and
the Agency-vs-Home-Unit field-mapping judgment call.

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
