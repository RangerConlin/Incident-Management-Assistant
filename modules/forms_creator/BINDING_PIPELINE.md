# Form Data Binding Pipeline

This is the reference name for the system that lets stored data (MongoDB
collections under `sarapp_incident_<id>` and `sarapp_master`) get pulled
live into a fillable PDF form. Use this name consistently in commits, PRs,
and conversation - "the binding pipeline" or "form bindings" - instead of
ad-hoc names like "the mapping system" or "the catalog thing."

Read this whole document before adding support for a new data domain
(Medical/Safety, Intel, Liaison, Logistics, PIO, etc.). It explains the
three layers, the conventions that keep them consistent, the mistakes
already found and fixed once, gives a worked example to copy, and tracks
conversion status collection-by-collection so work doesn't get repeated or
forgotten between sessions.

## Definitions

Use these exact terms. Don't invent synonyms for them in commits/PRs/chat.

- **The binding pipeline** (or **form bindings**) - the whole system,
  all three layers together. This document's subject.
- **Layer 1 / the data context / `FormDataContext`** - the Python class
  in `modules/forms_creator/context.py` that calls the live API and
  assembles the nested data dict. This is the only layer that does real
  work; everything else is either metadata about it or consumes its
  output.
- **A builder** (or **`_build_<domain>` method** / **`build_<thing>`
  method**) - one method on `FormDataContext` that produces one top-level
  key of that dict, e.g. `_build_teams` produces `data["teams"]`. "Wiring
  up a builder" = writing one of these.
- **The data dict** / **the context dict** - the actual `dict` object
  `FormDataContext.build()` returns at runtime. Never stored; rebuilt
  fresh on every form generation.
- **A binding path** (or just **a path**) - one dotted string like
  `incident.name` or `debrief.ground.assignment_summary` that locates one
  value inside the data dict.
- **Layer 2 / the catalog / `binding_catalog.json`** - the JSON file at
  `forms/binding_catalog.json`. A flat list of reference entries, each
  describing one binding path for the human-facing mapper UI. Inert by
  itself - never fetches anything.
- **A catalog entry** - one object in that JSON list:
  `{path, label, category, source_type, table, column}`.
- **A category** - the `category` field on a catalog entry, used purely
  to group entries in the mapper UI's picker (e.g. `"Debriefing -
  Ground"`). Not a code concept, just a label.
- **Layer 3 / a form mapping / `mapping.json`** - the per-PDF file at
  `forms/sets/<set_id>/<form_id>/mapping.json`. Ties one real PDF's
  AcroForm field names to binding paths. One of these exists per
  (form, form-set) pair.
- **A form set** (`set_id`) - the jurisdiction/edition implementing a
  form, e.g. `sar`, `cap`, `fema`, `uscg`, `ics_canada`. Lives under
  `forms/sets/<set_id>/`.
- **A form ID** (`form_id`) - the form's identity independent of which
  set implements it, e.g. `sar_110`, `ics_214`. Must have an entry in
  `forms/catalog.json` (this is a different file from
  `binding_catalog.json` - don't confuse the two).
  - `forms/catalog.json` = "what forms exist" (id/number/title/category).
  - `forms/binding_catalog.json` = "what data is available to put on
    them." Always say "the form catalog" vs. "the binding catalog" to
    keep these apart in conversation.
- **A computed binding** - a catalog entry with `"source_type":
  "computed"`, meaning its value is derived by real Python code in
  `context.py` rather than being a raw 1:1 stored field. See "Computed
  values" below for the full explanation and two unrelated things in this
  codebase that are also called "computed" but aren't this.
- **`PDFFiller`** (`modules/forms_creator/pdf_filler/pdf_filler.py`) -
  the class that actually opens a PDF, resolves every mapping's `source`
  against the data dict, and writes the filled output. "Filling a form" =
  calling `PDFFiller.fill()` (usually via `engine.generate()`).
- **`engine.generate()`** (`modules/forms_creator/engine.py`) - the single
  public entry point: given a form ID and incident ID, builds the data
  dict, resolves the mapping, fills the PDF. Accepts `extra_data` to
  overlay one specific record (see "Singular vs list data" below).
- **A wired domain** - a data domain (e.g. "debrief") where both layer 1
  (a real builder exists) and layer 2 (real catalog entries exist and
  resolve) are done. See the status table below for what counts.
- **An orphaned / stale / inert entry** - a layer-2 catalog entry that
  has no real layer-1 builder behind it, so it always resolves to
  empty. A known existing problem, not something to add more of.
- **A collection** - a MongoDB collection name, as defined in
  `data/db/sarapp_db/mongo/collection_names.py`. The status table below
  is organized one row per collection - that's the unit of tracking.

## Goal

Every piece of data stored in the app (with the sole exception of
MongoDB's internal `_id` field) should eventually be retrievable through
this pipeline and placeable onto a form. Most modules are not there yet -
see the status table near the bottom.

## The three layers

```
MongoDB (via FastAPI /api/... endpoints)
        |
        v
modules/forms_creator/context.py   <-- Layer 1: FormDataContext
        |  builds a nested dict, e.g. data["incident"]["name"]
        v
forms/binding_catalog.json          <-- Layer 2: the catalog
        |  a flat list of {path, label, category} entries used by the
        |  mapper UI (MapperWindow) so a human can pick "Incident Name"
        |  from a dropdown instead of typing "incident.name" by hand
        v
forms/sets/<set>/<form_id>/mapping.json   <-- Layer 3: per-form wiring
        |  {"pdf_field": "...", "source": "incident.name"}
        |  ties one specific PDF form's AcroForm field to one catalog path
        v
modules/forms_creator/pdf_filler/pdf_filler.py (PDFFiller.fill)
        resolves every "source" against the Layer-1 dict and writes the PDF
```

**Layer 1 (`context.py`) is the only layer that does real work.** It is
the live half: every time a form is generated, `FormDataContext.build()`
calls the app's own API endpoints fresh and assembles a dict. Nothing is
cached or stored - the data is always whatever the database says *right
now*.

**Layer 2 (`binding_catalog.json`) is just a reference list**, consumed by
`modules/forms_creator/ui/MapperWindow.py` so a human mapping a new PDF can
search/pick a path instead of memorizing dotted keys. It is metadata, not
code - an entry existing here means nothing unless layer 1 actually
produces that path.

**Layer 3 (`mapping.json` per form)** is the only layer tied to one
specific PDF. It is the file that gets hand-written (or written by us)
once per form, mapping that PDF's literal AcroForm field names to paths
from layer 1.

If you only add a catalog entry (layer 2) without also making `context.py`
(layer 1) produce that path, the entry is **inert** - it shows up in the
picker but never resolves to a real value. This already happened for
~190 existing entries (`hospitals`, `ems_agencies`, `narrative`,
`team_members`) - see "Known stale entries" below. Don't
repeat that mistake: always wire layer 1 first, or in the same change.

## Conventions

### Path naming

Dotted, lowercase, snake_case segments: `incident.name`,
`teams.0.leader_name`, `assignment.ground.expected_pod.responsive.high`.

- **Singular record, one at a time** (the record currently being
  filled/exported): use a bare key, no index - e.g. `debrief.*`,
  `assignment.*`, `subject.*`. The caller supplies this record's data via
  `extra_data` at generate-time (see "Singular vs list data" below).
- **Whole-incident lists** (every team, every task, every channel): use a
  numeric index per slot - `teams.0.name`, `teams.1.name`, ... This only
  works because those forms have a fixed number of row-slots on the page
  (e.g. ICS 211 has 10 check-in rows). The catalog pre-generates one entry
  per slot, up to that form's max row count.

### `source_type` / `table` / `column` in the catalog

Every catalog entry carries `source_type` (`"incident_db"` or
`"master_db"`), plus `table` and `column`. **These are not live SQL
references** - nothing reads them to fetch data. The app migrated off
SQLite to MongoDB; layer 1 already calls the Mongo-backed API directly.
These three fields are accuracy-as-documentation only: `table` should be
the real Mongo collection name (from
`data/db/sarapp_db/mongo/collection_names.py`), `column` should be the
real field name (or dotted sub-path) inside that collection's documents.
Get them right because they're the only "where does this actually come
from" breadcrumb in the catalog, but never expect code to execute them.

Use `"incident_db"` for anything scoped to the active incident
(`sarapp_incident_<id>`), `"master_db"` for agency-wide reference data
(`sarapp_master`).

### Singular vs list data, and how "the current record" gets in

`FormDataContext.build(incident_id)` only takes an incident ID - it has no
concept of "which task" or "which debrief" is being filled out right now.
For whole-incident lists (teams, tasks, channels...) that's fine, the
whole list is just always there. For a single specific record (the
debrief someone just finished editing, the task being assigned, the
subject being interviewed), do this instead:

1. Give `FormDataContext` a `build_<thing>(<thing>_id, incident_id=None)`
   method that fetches and flattens just that one record (see
   `build_debrief` for the exact pattern).
2. Always default `data["<thing>"]` to an **empty shape** inside `build()`
   (e.g. `self._empty_debrief_shape()`) so every catalog path under that
   key resolves to `""`/`[]`/`False` instead of raising, even when nobody
   has picked a specific record.
3. Whoever triggers the actual export calls:
   ```python
   from modules.forms_creator.engine import generate
   from modules.forms_creator.context import FormDataContext

   ctx_overlay = FormDataContext().build_debrief(debrief_id, incident_id)
   generate(form_id, output_path, incident_id, extra_data={"debrief": ctx_overlay})
   ```
   `engine.generate()` already supports `extra_data` (a shallow
   `dict.update()` onto the built context) for exactly this purpose - it's
   not new machinery, just an existing hook nobody had used yet for this
   kind of per-record data.

### Empty values, checkboxes, and transforms

`PDFFiller._resolve_value` (in `pdf_filler.py`) accepts a `source` that is
either a plain dotted-path string, or a dict with one of: `"literal"`,
`"first_of"` (list of fallback paths), `"join"` (list + `"separator"`),
or `"key"` (a path, optionally with `"checkbox": true` and
`"checked_value"`/`"unchecked_value"` overrides, and/or `"transform"`).

- For a boolean/0-1 field that should print `"X"` in a text box (not a
  real PDF checkbox widget - inspect the PDF's `/FT` to tell which it is):
  ```json
  { "key": "debrief.ground.att_map", "checkbox": true, "checked_value": "X", "unchecked_value": "" }
  ```
- For a real `/Btn` checkbox widget, the default `checked_value`/
  `unchecked_value` are `"/Yes"`/`"/Off"` - but **verify against the
  actual PDF's export states first** (`reader.get_fields()[name]["/_States_"]`
  via `pypdf`); some templates use `"/On"` instead of `"/Yes"`.
- Available `transform` values: `upper`, `lower`, `date_short`,
  `time_short`, `datetime_short` (see `_apply_transform`). There is no
  built-in boolean-to-"X" transform - use the `checkbox` mechanism above
  instead, it already does this generically.

### Multi-line text boxes split into `...Row1`, `...Row2`, ... fields

Some PDF templates were authored with one AcroForm field per visual line
of a paragraph box (e.g. `"10 HOW WAS VISIBILITY DISTANCE DETERMINEDRow1"`
through `Row4`). **Established convention in this repo: map only `Row1`**
to the real source value, and leave `Row2`+ out of the mapping entirely
(don't even include them with an empty source). See `capf_104`,
`sar_100a`, and the `sar_11x` debrief forms for the precedent. There is a
separate, more powerful `row_groups` mechanism in `pdf_filler.py` for
*genuinely repeating* data (one row per list item, with overflow/
continuation pages) - that's a different feature, only use it when the
data is actually a list, not a single long answer.

### Computed values (derived fields, e.g. "total time" from time-in/time-out)

There are **three different "computed" things** in this codebase. Don't
confuse them - they don't share an implementation:

1. **Catalog `source_type: "computed"`** - this is the real mechanism for
   the binding pipeline, already established with 65 existing entries
   (e.g. `prepared_by.name`, `task.assignment`, `team.resource_type`).
   It means exactly one thing: *"this path's value is not a raw 1:1
   database column - some Python code in `context.py` derives it."*
   There is no formula/expression syntax in the catalog or in
   `mapping.json` - the actual math/logic always lives in a real Python
   method. Marking a catalog entry `"computed"` is just honest labeling
   of that fact for the mapper UI; it does not implement anything by
   itself.
2. **`PDFFiller._resolve_computed`** in `pdf_filler.py` - a *completely
   unrelated* mechanism, only for `row_groups` pagination headers
   (`{"computed": "page_number"}` / `"total_pages"` / `"page_of_total"`).
   Has nothing to do with deriving values from incident data. Don't reach
   for this when you mean #1.
3. **`modules/forms_creator/bindings.py` / `form_registry.py`** (the
   `ALLOWED_BINDING_SOURCES` set with `"mission"`/`"personnel"`/`"env"`/
   `"computed"`) - this is dead code. No other file in the repo imports
   `bindings.py`. It predates (or was an abandoned parallel to) the
   current `context.py` + `binding_catalog.json` pipeline. Ignore it;
   don't try to wire a new computed value into it.

**To add a real computed value**, decide which of these two applies:

- **Compute it once, at data-entry time, and store the result.** Use this
  whenever the calculation only ever needs to happen when the user enters
  the raw values, and the result itself is meaningful to store (so other
  things - reports, the debrief table column, a future audit - can read
  it without recomputing). This is the existing pattern for
  `debrief.ground.time_spent`: in
  `modules/operations/taskings/task_detail_widget.py`, the Ground
  debrief's "Time Entered"/"Time Exited" fields each fire a `_recalc()`
  handler on `textChanged` that computes the HH:MM difference and writes
  it straight into the (already-readonly) "Time Spent" field, which then
  gets saved to MongoDB like any other field. The binding pipeline
  doesn't need to know it's derived at all - by the time it reaches
  `debrief.ground.time_spent`, it's just a normal stored string.
  **Prefer this option** when the source fields and the derived field
  both live in the same form/editor.
- **Compute it at form-fill time, in a `context.py` builder.** Use this
  only when the calculation needs inputs that live in different,
  unrelated places (so there's no single editor UI where "compute on
  change" would make sense), or when storing the derived value would be
  redundant/risk going stale relative to its inputs. Implementation: do
  the math directly in the relevant `_build_<domain>` or `build_<thing>`
  method, assign the result into the dict under a new key, and give that
  key a catalog entry with `"source_type": "computed"`. There's no
  special framework for this - it's just `result["total_sortie_time"] =
  some_function(result["act_time_started"], result["act_time_ended"])`
  before returning.

If you genuinely need the *same* derived value usable from multiple
different forms/contexts, factor the actual calculation into a small
shared helper function (e.g. a module-level function in `context.py`) and
call it from each builder that needs it, rather than duplicating the
formula. Don't invent a declarative "formula" mini-language in JSON for
this - every other part of this pipeline keeps logic in Python and data
in JSON, stay consistent with that.

**Known concrete gap matching this pattern**: the Air SAR Worksheet
debrief tab (`debrief.air_sar.*`) has `act_time_started`,
`act_time_ended`, and `act_total_sortie_time` as three independent
manually-typed fields - unlike the Ground tab, nothing computes
`act_total_sortie_time` from the other two. Whoever picks up Air SAR
debrief wiring should add an entry-time `_recalc()` (first choice, matches
the Ground precedent) or, if that turns out not to fit, a `context.py`
computed builder (second choice) - not both.

### Building a new form folder

Each form is `forms/sets/<set_id>/<form_id>/template.pdf` +
`forms/sets/<set_id>/<form_id>/mapping.json`. `<form_id>` must also
already exist as an entry in `forms/catalog.json` under `"forms"`
(id/number/title/category) - that's the form's identity, independent of
which set implements it. `.raster/` subfolders are cached preview
thumbnails for the mapper UI; not required for filling to work.

To find the real AcroForm field names for a new PDF (don't guess - they
are frequently not what the printed label says):
```python
from pypdf import PdfReader
fields = PdfReader("path/to/template.pdf").get_fields() or {}
for name, f in fields.items():
    print(repr(name), f.get("/FT"), f.get("/_States_"))
```
`/FT` of `None` means it's a parent/group node, not a real fillable field
- skip those. `/FT == "/Btn"` is a checkbox/radio; check `/_States_` for
its real on/off export values.

### Always test-fill before calling a mapping done

```python
from modules.forms_creator.pdf_filler.pdf_filler import PDFFiller
filler = PDFFiller("forms/sets/sar/sar_110/mapping.json")
warnings = filler.fill(sample_data_dict, "forms/sets/sar/sar_110/template.pdf",
                        "/tmp/out.pdf", strict=False)
print(warnings)  # must be empty - any warning means a typo'd pdf_field
                  # name or a source path that doesn't resolve
```
Delete the test output afterward; never commit scratch PDFs.

## Known stale entries (don't repeat this mistake)

These catalog (layer 2) entries already exist but resolve to nothing
because layer 1 was never wired for them - `context.py` hardcodes the key
to `[]`/`{}` instead of calling an API:

- `narrative` (100 entries) - should come from `unit_logs`/`ics_214_logs`, currently a hardcoded `[]`.
- `team_members` (32 entries) - currently a hardcoded `[]`.
- `assignment.*` / `task.*` (the SAR 104 ground/air POD-matrix paths) - no `_build_assignment` exists in `context.py` at all yet; these resolve via `extra_data` only if a caller builds and passes that dict themselves (nobody does yet).

If you're touching any of these domains, fix the layer-1 builder as part
of that work instead of leaving the orphaned entries in place.

## Conversion status by collection

This is the tracker. One row per MongoDB collection (the unit defined in
`data/db/sarapp_db/mongo/collection_names.py`). **Update this table in the
same change** that wires (or partially wires) a collection - that's the
whole point of it living here instead of in chat history.

Status values:
- **Wired** - layer 1 builder exists and is real (not a stub), layer 2
  has matching catalog entries, both verified to resolve.
- **Partial** - some fields/aspects covered, gaps noted.
- **Stub (orphaned)** - layer 2 catalog entries exist but layer 1 returns
  `[]`/`{}` - actively misleading, fix before adding more here.
- **Not started** - neither layer touches it.
- **N/A** - system/internal data, not a form-fill candidate (listed for
  completeness per the "every datapoint" goal, not because it needs work).

Field-by-field detail is **only** maintained inline here for collections
that are Wired or actively in progress - see "Worked example" for the
debrief entry's full field list. For Not Started collections, field-level
detail isn't tracked yet; pull the field list from the relevant Pydantic
schema (`data/db/sarapp_db/schemas/`) or router when you start that work,
and replace this row's one-line status with a real per-field breakdown at
that point (follow the debrief table's format below as the template).

### Command / Planning

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `incident_profile` | `incident` | Wired | name, number, type, description, icp_location, start_time |
| `operational_periods` | `op_period` | Wired | number, start/end, formatted date/time |
| `incident_objectives` | `objectives` | Wired | id, description, status, priority, section, due_time, code |
| `strategies` | - | Not started | |
| `objective_strategy_task_links` | - | Not started | |
| `org_positions` | `organization`, `uc_commanders`, `org_branches`, `planning_tech_specialists` | Wired | `_build_organization` joins `/org/positions` + `/org/assignments` by `position_id` to resolve each role's title (previously broken - see "ics_203 resolution" below); `_build_uc_commanders` finds all assignments under "Incident Commander"-titled position(s); `_build_org_branches` walks `/org/units` (branch/division/group classifications) + assignments into a nested branch->divisions tree; `_build_planning_tech_specialists` finds positions titled "Technical Specialist[ - <specialty>]" |
| `org_assignments` | same four keys as above | Wired | see `org_positions` row - same builders join both collections together |
| `org_history` | - | Not started | |
| `org_templates` | - | Not started | |
| `org_snapshots` | - | Not started | |
| `incident_organization` | - | Not started | distinct from `org_positions`/`org_assignments` above (different collection); not yet identified what, if anything, still needs this one |
| `incident_journal` | - | Not started | |
| `work_assignments` | `assignment` (catalog only) | Stub (orphaned) | catalog has `assignment.*`/`task.*` entries (SAR 104 POD matrix etc.) but no `_build_assignment` exists in context.py at all |

### Operations

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `teams` | `teams` | Wired | raw passthrough |
| `tasks` | `tasks` | Partial | raw passthrough + derived date/time; no separate `narrative` extraction (the top-level `narrative` key is a hardcoded `[]` stub - see Communications section) |
| `task_debriefs` | `debrief` | **Wired** | see "Worked example" below for full field list |
| `resource_requests` | - | Not started | (incident-level; distinct from `logistics_resource_requests`, see Logistics) |
| `check_in_out` | - | Not started | |
| `checkins` | - | Not started | |
| `checkin_history` | - | Not started | |
| `incident_personnel` | - | Not started | assigned/checked-in roster; also backs the `team_members` stub below |

### Logistics

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `logistics_resource_requests` | - | Not started | distinct from incident `resource_requests` |
| `logistics_resource_status_items` | `vehicles` (partial overlap) | Partial | `_build_incident_vehicles` pulls `/api/incidents/{id}/resources`, which may not be this exact collection - verify before assuming coverage when you pick this up |

### Communications

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `incident_channels` | `channels` | Wired | full incident-channel payload exposed, including ICS-205-relevant fields (`system`, assignment division/team, include_on_205, sort/line flags) plus compatibility aliases (`name`, `assignment`, `remarks`) |
| `communications_log` | `comm_log` | Wired | full communications log entry payload exposed for layer 1/2; audit trail and saved filters remain intentionally separate collections |
| `comms_log_audit` | - | Not started | |
| `comms_log_filters` | - | Not started | |
| `ics_213_messages` | `message` | Stub (orphaned) | `data["message"] = {}` hardcoded |
| `ics_214_logs` | `narrative` | Wired | ICS 214 stream entries are flattened into the legacy narrative shape (`timestamp`, `narrative`, `entered_by`, `team_num`, `critical`) with extra source metadata preserved alongside |
| `ics_205_instances` | - | Not started | only live channel rows are exposed via `channels`, not the versioned ICS-205 plan document itself |
| `unit_logs` | `narrative` | Partial | no dedicated unit-log builder yet; current narrative coverage comes from ICS 214 streams, which unblocks the form mappings that were previously orphaned |

### Medical & Safety

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `ics_206_aid_stations` | `ics_206_aid_stations` | Wired | op-scoped aid station rows exposed with name, type, level, 24/7 flag, and notes |
| `ics_206_ambulance_services` | `ics_206_ambulance_services` | Wired | op-scoped ambulance services exposed with name, type, phone, location, notes, plus computed `service_level` / `service_level_label` |
| `ics_206_hospitals` | `ics_206_hospitals` | Wired | op-scoped ICS 206 hospitals exposed separately from master hospitals, with computed trauma display from adult/pediatric levels |
| `ics_206_air_ambulance` | `ics_206_air_ambulance` | Wired | op-scoped air ambulance rows exposed with name, phone, base, contact, and notes |
| `ics_206_medical_comms` | `ics_206_medical_comms` | Wired | op-scoped medical comms rows exposed with channel, function, frequency, mode, and notes |
| `ics_206_procedures` | `ics_206_procedures` | Wired | op-scoped ICS 206 procedures exposed as a singular content record |
| `ics_206_signatures` | `ics_206_signatures` | Wired | op-scoped ICS 206 prepared-by / approved-by signature block exposed as a singular record |
| `hazards` | `hazards` | Wired | generic incident snapshot-backed read exposes planning/tactics hazard entries with normalized safety fields (`hazard_type_text`, risk/likelihood/severity, controls, PPE, safety message, resolved flag, notes) |
| `safety_reports` | `safety_reports` | Wired | incident safety report list exposed with time/location/severity/flagged metadata |
| `medical_incidents` | - | Not started | |
| `triage_entries` | - | Not started | |
| `hazard_zones` | `hazard_zones` | Wired | zone name, geometry JSON, severity, description, timestamps |
| `cap_orm_summaries` | `cap_orm_summaries` | Wired | legacy CAP ORM summary records exposed as list entries |
| `cap_orm_forms` | `cap_orm_form` | Wired | current operational period ORM form exposed as a singular record |
| `cap_orm_hazards` | `cap_orm_hazards` | Wired | current operational period ORM hazard rows exposed as list entries; also drives CAPF 160 repeating hazard rows |
| `cap_orm_audit` | `cap_orm_audit` | Wired | ORM audit rows exposed, filtered to the current operational period form when available |
| `planning_work_assignments` | `ics_215a_rows` | Partial | computed repeating rows flatten current operational period work assignments plus embedded hazards for ICS 215A-style forms; sourced from work assignments rather than a dedicated collection |
| `ics_208_instances` | `ics_208` | Wired | current operational period ICS 208 instance exposed as a singular record |
| `iwi_reports` | `iwi_reports` | Wired | safety incident / IWI reports exposed with status, occurrence/location, narrative, factors, notifications, corrective actions, witnesses, and signoffs |

### Intel

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `intel_clues` | `debrief.linked_clue_ids` / `linked_clues_summary` (via `task_debriefs`) | Partial | clue **links from a debrief** are wired (titles resolved into `debrief.linked_clues_summary`); clue records are not bindable as their own form data yet |
| `intel_subjects` | `subject` (stub) / `debrief.linked_subject_ids` (via `task_debriefs`) | Partial | the standalone `subject` top-level key is a static empty-dict stub, unrelated to the real `intel_subjects` collection; subject **links from a debrief** are wired the same way as clues above |
| `intel_items` | (same as `intel_clues` - a Clue is an `IntelItem` with `item_type="Clue"`) | Partial | see `intel_clues` row; non-Clue item types (hazard reports, road closures, etc.) have no binding at all |
| `intel_leads` | - | Not started | |
| `intel_assessments` | - | Not started | |
| `intel_log` | - | Not started | |
| `intel_reports` | - | Not started | |
| `intel_env_snapshots` | - | Not started | legacy collection, confirm still in use before wiring |
| `intel_form_entries` | - | Not started | legacy collection, confirm still in use before wiring |

### Liaison

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `liaison_agencies` | `liaison_agencies`, `agency_contacts` | Wired | `context.py` now exposes raw agency rows plus agency-name lookup for the rest of the liaison builders |
| `liaison_contacts` | `liaison_contacts`, `agency_contacts` | Wired | raw contact rows exposed under `liaison_contacts`; existing 60 `agency_contacts.*` entries continue to resolve via the flattened compatibility list |
| `liaison_interactions` | `liaison_interactions` | Wired | raw passthrough with current UI fields (`followup_action`, `followup_assigned_to`, `followup_due`) |
| `liaison_agency_requests` | `liaison_agency_requests` | Wired | normalized to current UI field names (`description`, `requested_by`, `due_date`) with fallback from legacy SQLite names |
| `liaison_resource_offers` | `liaison_resource_offers` | Wired | normalized to current UI field names (`description`, `offered_by`, `available_from`) with fallback from legacy SQLite names |
| `liaison_feedback` | `liaison_feedback` | Wired | raw passthrough |
| `liaison_followup_actions` | `liaison_followup_actions` | Wired | sourced from per-agency detail endpoint; catalog uses legacy collection field names |
| `liaison_restrictions` | `liaison_restrictions` | Wired | sourced from per-agency detail endpoint |
| `liaison_agreements` | `liaison_agreements` | Wired | sourced from per-agency detail endpoint |

### Personnel

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `incident_personnel` | `team_members` | Stub (orphaned) | catalog has 32 `team_members.*` entries ("SAR 104 Team Members"); context.py hardcodes `data["team_members"] = []` |

### Reference Library / Forms infra

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `forms` (instances) | - | Not started | ironic gap: the form-fill system itself doesn't expose prior filled-form data back into new form contexts |
| `form_instance_revisions` | - | Not started | |
| `form_instance_audit` | - | Not started | |
| `form_instance_exports` | - | Not started | |
| `form_instance_links` | - | Not started | |

### Public Information

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `pio_messages` | - | Not started | |
| `pio_message_revisions` | - | Not started | |
| `pio_approvals` | - | Not started | |
| `pio_media_log` | - | Not started | |
| `pio_misinformation_items` | - | Not started | |
| `pio_misinformation_timeline` | - | Not started | |
| `pio_talking_points` | - | Not started | |
| `pio_templates` | - | Not started | |
| `pio_template_versions` | - | Not started | |
| `pio_distribution_log` | - | Not started | |
| `pio_generated_documents` | - | Not started | |

### Initial Response Toolkit

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `initial_response_overview` | - | Not started | |
| `initial_hasty_tasks` | - | Not started | |
| `initial_reflex_actions` | - | Not started | |

### Planned Event Toolkit

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `planned_campaigns` | - | Not started | |
| `planned_event_schedules` | - | Not started | |
| `planned_vendors` | - | Not started | |
| `planned_permits` | - | Not started | |
| `planned_safety_reports` | - | Not started | planned toolkit domain, intentionally outside this safety pass |
| `planned_tasks` | - | Not started | |
| `planned_quick_assignments` | - | Not started | |
| `planned_health_inspections` | - | Not started | |
| `planned_schedule_triggers` | - | Not started | |
| `planned_notifications` | - | Not started | |

### Advanced GIS

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `spatial_features` | - | Not started | |
| `spatial_feature_links` | - | Not started | |

### Status Boards

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `status_board_snapshots` | - | Not started | |

### Cross-cutting / supporting

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `meetings` | `meetings` | Wired | raw passthrough |
| `approval_instances` | - | Not started | |
| `approval_records` | - | Not started | |
| `notifications` | - | N/A (likely) | alert history; revisit if a form ever needs it |
| `attachments` | - | N/A (likely) | file metadata; revisit if a form ever needs it |
| `audit_logs` (incident) | - | N/A (likely) | audit trail; revisit if a form ever needs it |

### Master data (`sarapp_master`)

| Collection | Context key(s) | Status | Notes |
|---|---|---|---|
| `personnel` | `personnel` | Wired | raw passthrough |
| `vehicles` | `master_vehicles` | Wired | raw passthrough |
| `aircraft` | `aircraft` | Wired | raw passthrough |
| `equipment` | `equipment` | Wired | raw passthrough |
| `resource_types` | `resource_types` | Wired | raw passthrough |
| `resource_capabilities` | `resource_types` (partial overlap, unconfirmed) | Partial | verify before assuming full coverage |
| `radio_channels` | `comms_resources` | Wired | raw passthrough via `/api/comms/channels` |
| `hospitals` | `hospitals` | Wired | master hospital catalog exposed with contact, phone variants, helipad/burn flags, adult/pediatric trauma level fields, and computed `trauma_level_display` |
| `ems_agencies` | `ems_agencies` | Wired | master EMS agencies exposed with radio/address fields plus computed highest-service `service_level` / `service_level_label` |
| `hazard_types` | `hazard_types` | Wired | master hazard library exposed with defaults, aliases, mitigations, PPE items, and resource defaults |
| `safety_analysis_templates` | `safety_analysis_templates` | Wired | master safety analysis templates exposed with target forms and hazard entries |
| `incident_types` | - | Not started | |
| `agency_directory` | `agency_contacts` (historical overlap only) | N/A for current liaison wiring | current `agency_contacts` bindings now resolve from incident-scoped liaison agencies/contacts, not master `agency_directory` |
| `task_types` | - | Not started | |
| `team_types` | - | Not started | |
| `objective_templates` | - | Not started | |
| `canned_comm_entries` | - | Not started | |
| `certification_types` | - | Not started | |
| `certification_tags` | - | Not started | |
| `personnel_certifications` | - | Not started | |
| `organization_types` | - | Not started | |
| `rank_structures` | - | Not started | |
| `organizations` | - | Not started | |
| `ranks` | - | Not started | |
| `organization_rank_structure_overrides` | - | Not started | |
| `organization_audit_log` | - | N/A (likely) | audit trail |
| `rank_structure_audit_log` | - | N/A (likely) | audit trail |
| `form_families` | - | N/A | forms-infra metadata, not incident data |
| `form_templates` | - | N/A | forms-infra metadata |
| `form_template_versions` | - | N/A | forms-infra metadata |
| `incident_templates` | - | N/A | template metadata |
| `meeting_templates` | - | N/A | template metadata |
| `users` / `user_sessions` / `user_profiles` / `role_templates` | - | N/A | auth/account data, not form-fill candidates |

### System (`sarapp_system`)

| Collection | Status | Notes |
|---|---|---|
| `app_settings`, `server_identity`, `workstations`, `sync_state`, `active_incident`, `audit_global`, `incidents` | N/A | app/server configuration, never form-fill data |

## Form template / mapping checklist

This is the layer-3 tracker - one row per `(set, form_id)` folder under
`forms/sets/`. Update it whenever you add a template, write or extend a
mapping, or discover a problem with one. Don't let it go stale; it's the
fastest way to answer "is this form actually usable yet" without manually
re-deriving it every session.

**How "Template fields" / "Mapping fields" / "Overlap" were computed**
(re-run this if the table looks stale): for each folder, count the real
AcroForm field names in `template.pdf` (via `pypdf`), count the distinct
`pdf_field` names listed in `mapping.json`'s `fields` list, and count how
many of those mapping names actually exist in the template. A fully
correct mapping has `Overlap == Template fields` (every real field in the
PDF has a mapping) - but **this number alone cannot tell the difference
between "fields genuinely missing a mapping" and "fields intentionally
left out per the `Row1`-only convention"** (see Conventions above). Forms
marked "Mapped, not yet test-fill verified" below have a real gap by this
count, but might be completely fine - the only way to know for sure is to
actually run `PDFFiller.fill()` with sample data and confirm zero
warnings (see "Always test-fill before calling a mapping done"). Forms
marked plain **Wired** below were either confirmed that way in this
session via a real test-fill, or have `Overlap == Template fields`
(no ambiguity possible).

Status meanings:
- **Wired** - template present and fillable, mapping present, full field
  coverage confirmed (either by overlap count or by an actual test-fill
  run - see note above).
- **Mapped, not yet test-fill verified** - template and mapping both
  present, but overlap is short of the template's full field count.
  Could be intentional `Row1`-only omissions (fine) or a real gap
  (not fine) - run a test-fill to find out before assuming either way.
- **Needs mapping** - template present and fillable, no `mapping.json`
  at all.
- **Needs template (mapping orphaned)** - `mapping.json` exists, no
  `template.pdf` at all. The field names in the mapping don't match any
  file currently in the repo - see "Orphaned mappings" note below.
- **Broken template (missing `/AcroForm`)** - `template.pdf` exists, has
  zero readable fields, but the page still has annotation widgets
  present. The file's `/AcroForm` catalog entry is missing/stripped, so
  no tool that reads `/AcroForm/Fields` (which is everything here) can
  see the fields. See "ics_203 resolution" below for how this was
  diagnosed and fixed in one real case.
- **Non-fillable source PDF** - `template.pdf` exists but has zero
  fields and zero annotations. Not corruption - this file was never a
  fillable AcroForm to begin with (likely a scan or a flattened/printed
  export). Needs a different, genuinely fillable source PDF before any
  mapping work can start.
- **Empty mapping stub** - both files exist but `mapping.json` has no
  real entries yet (a placeholder).

### `ics_203` resolution (worked example: diagnosing + fixing a broken template)

**The corruption.** `forms/sets/fema/ics_203/template.pdf` read as 0
fields via `PdfReader.get_fields()`, but `page.get("/Annots")` on page 0
returned 116 annotation objects - one of which, inspected directly, had
`/T: "1 Incident Name"` and `/FT: "/Tx"` (i.e. it *was* a real text field
widget, just not reachable through the normal AcroForm field list).
Diagnostic:
```python
from pypdf import PdfReader
r = PdfReader("forms/sets/fema/ics_203/template.pdf")
print("/AcroForm" in r.trailer["/Root"])   # False - this was the bug
print(len(r.pages[0].get("/Annots") or [])) # 116 - the widgets were still there
```
This happens when a PDF gets resaved/exported through a tool (print-to-PDF,
certain flatten/merge operations) that drops the document-level
`/AcroForm` catalog reference while leaving the per-page widget
annotations physically in place. Checked git history first (the most
reliable recovery path): both prior commits touching this file were
already broken the same way, so there was no earlier good version to
restore. Fix: replaced `template.pdf` with the user's raw, never-bound
copy of the same form, which had a real `/AcroForm` and all 116 fields
readable again.

**The mapping mismatch.** That raw copy's field *count* matched the
broken file (116), but the existing `mapping.json` had 175 entries,
referencing some field names that simply don't exist on this form. Of
those:
- ~28 were dead boilerplate (`IncidentName`, `OperationsChief`,
  `PreparedBy`, etc.) - present in most ICS form mappings in this repo,
  unused everywhere, not specific to this form. Deleted.
- ~93 were speculative snake_case aliases (`uc_agency1`, `rep_agency1`,
  `tech_name1`, `branch_id1`, `div_1_name1`, etc.) tied to an unused
  `row_groups` mechanism with `col_patterns` pointing at field names that
  never existed on any version of this PDF. The real fields exist under
  different native names. Resolved by walking the actual rendered PDF
  page with the user, field name by field name, instead of guessing from
  names/positions alone - see the table below for the final correspondence.
  The `row_groups` mechanism was dropped in favor of plain indexed
  `fields` entries (`org_branches.0.divisions.0.name`, etc.) because the
  real numbering is irregular (sequential `Branch Director 1-6` across 3
  branches, not reset-per-branch; `Technical SpecialistsRow1-3` offset by
  +7 from their paired `5 Planning SectionRow8-10` name fields) - the
  `{n}`-substitution pattern can't express that, a fixed small list of
  explicit entries can.

| Real PDF field(s) | What it actually is | Bound to |
|---|---|---|
| `ICUCs` | 1st Incident Commander/UC, name only | `organization.incident_commander.name` |
| `ICUCsRow1` + `...Row2` | 2nd UC: agency (narrow, left) + name (wide, right) | `uc_commanders.1.agency` / `.name` |
| `ICUCsRow2` + `...Row3` | 3rd UC: agency + name, same pairing | `uc_commanders.2.agency` / `.name` |
| `AgencyOrganizationRow1-6` + `NameRow1-6` | Agency Rep rows 1-6: agency + name | `org_agency_reps.<0-5>.agency` / `.name` |
| `Planning Section Technical Specialists` | 1st (head) tech specialist, name only | `planning_tech_specialists.0.name` |
| `Technical SpecialistsRow1-3` + `5 Planning SectionRow8-10` | Specialists 2-4: specialty (narrow, left) + name (wide, right) | `planning_tech_specialists.<1-3>.specialty` / `.name` |
| `Branch Director 1/3/5` | the branch's own name/identifier (not a person) | `org_branches.<0-2>.name` |
| `Branch Director 2/4/6` | the branch director's name | `org_branches.<0-2>.director_name` |
| `Branch Director Deputy 1/3/5` | unused on this form | left as `""`, intentionally |
| `Branch Director Deputy 2/4/6` | the branch's deputy director's name | `org_branches.<0-2>.deputy_name` |
| `Division/Group Identifier N` | the division/group's own name | `org_branches.<branch>.divisions.<slot>.name` |
| `DivisionGroup Name N` | the division/group's supervisor's name | `org_branches.<branch>.divisions.<slot>.supervisor_name` |
| `Operations Section Alternate(/1/2)` | unknown - no printed label found anywhere on the form | left as `""`, unresolved |
| `Air Ops Branch Director 2/3` pairs | unclear, possibly additional branch directors | left as `""`, unresolved |

Result: **116/116 template fields now have exactly one mapping entry,
every entry resolves to a real field, zero "field not found" warnings on
test-fill.**

**Update - the data side got built too, same session.** While fixing this
form the underlying `organization.<role>.name` lookup was found to be
silently broken everywhere (not just here) - `_build_organization` joined
on `row.get("position_title")`, a field that doesn't exist on an
`/org/assignments` record (only `position_id` does), so it never matched
anything and every named-position field on every form using
`organization.*` always resolved empty. Fixed by first fetching
`/org/positions` and joining `position_id -> title` before matching
against `_ORG_POSITIONS`. Real builders were also added for
`uc_commanders` (all assignments under any position titled "Incident
Commander" - supports multiple, i.e. true Unified Command), `org_branches`
(walks `/org/units` for branch/division/group positions + their
assignments into a nested tree), and `planning_tech_specialists` (positions
titled `Technical Specialist` or `Technical Specialist - <specialty>`).
`org_agency_reps` reuses the already-wired `agency_contacts` builder
directly (Liaison agencies/contacts). All four were verified end-to-end
with a realistic nested test dict (3 UCs, a branch with a division, two
tech specialists) and the corresponding fields filled correctly with zero
warnings. See the updated `org_positions`/`org_assignments` rows in
"Conversion status by collection" above.

**Known, accepted limitation - more than 3 branches or 15 total divisions
silently drops data.** The mapping only has PDF field slots for
`org_branches.0` through `.2` (3 branches x 5 divisions each, matching
the fixed row count printed on this one-page form) because that's all
the physical space `ics_203`'s real template has - there is no
`Branch Director 7/8` field to bind a 4th branch to even if one existed.
`_build_org_branches` itself has no such limit and will return however
many branches the incident actually has; the mapping just never
references anything past index 2, so branch 4+ (or division 16+) is
silently absent from the filled PDF - no warning, no error. This mirrors
how the real paper form works too (a large incident needs a continuation
sheet or multiple ICS 203 copies in practice) - no continuation template
for this form exists in this repo yet. Decided 2026-06-23: leave this as
silent truncation for now rather than adding an overflow warning or a
continuation page - revisit if it becomes a real problem.

### Orphaned mappings (concrete example)

Several forms have a real, substantial `mapping.json` already written,
but **no `template.pdf` at all** - and if you compare the mapping's
expected field names against any raw/unbound copy of that same form you
might have lying around, they won't match. Example, `ics_221`:

| Mapping expects (`mapping.json`) | Raw PDF actually has |
|---|---|
| `IncidentName` | `1 Incident Name_25` |
| `IncidentNumber` | `2 Incident Number_12` |
| `DemobGroupName` | `4 Resource or Personnel Released` |
| `ResourceLeader` | `RemarksSupply Unit` |
| `PreparedBy` | `Signature1` |

The mapping was written against a version of this PDF where the fields
had already been renamed to short, clean, semantic names (`IncidentName`,
not `1 Incident Name_25`). That renamed PDF is the one that should be
`template.pdf` - but it was never saved into the repo, only the mapping
that resulted from working with it. Dropping in a raw/unrenamed copy of
the form will not satisfy this mapping; `PDFFiller` would report a
"field not found" warning for every single entry. These forms need
whichever already-renamed file produced the existing mapping, not a
fresh raw copy.

### The checklist

| Set | Form ID | Template fields | Mapping fields | Overlap | Status |
|---|---|---|---|---|---|
| cap | capf_104 | 207 | 130 | 130 | Mapped, not yet test-fill verified |
| cap | capf_104a | 72 | (none) | - | Needs mapping |
| cap | capf_160 | 131 | 31 | 131 | Wired - header uses `cap_orm_form` and `prepared_by`; body uses repeating `cap_orm_hazards` rows with `continuation.pdf` as the 11-row overflow sheet; test-fill verified zero warnings (signature widgets intentionally left blank) |
| cap | capf_106 | 40 | 40 | 40 | Wired |
| cap | capf_109 | 109 | 244 | 109 | Wired (mapping has ~135 extra entries beyond the template's 109 fields - likely stale/leftover, not harmful; low-priority cleanup) |
| cap | ics_309 | 103 | 106 | 103 | Wired |
| cap | miwgf_52 | 69 | (none) | - | Needs mapping |
| fema | ics_201 | 178 | 226 | 178 | Wired |
| fema | ics_202 | 35 | 35 | 35 | Wired |
| fema | ics_203 | 116 | 116 | 116 | **Wired, end-to-end** - both field names and data builders done this session, see "ics_203 resolution" above; verified with a realistic nested test dict, zero warnings |
| fema | ics_204 | 77 | 106 | 77 | Wired |
| fema | ics_205 | 99 | 108 | 99 | Wired |
| fema | ics_205a | (none) | 56 | - | Needs template (mapping orphaned) |
| fema | ics_206 | 118 | 122 | 118 | Wired |
| fema | ics_207 | 41 | 70 | 41 | Wired |
| fema | ics_208 | 14 | 28 | 14 | Wired |
| fema | ics_209 | (none) | 32 | - | Needs template (mapping orphaned) |
| fema | ics_210 | (none) | 56 | - | Needs template (mapping orphaned) |
| fema | ics_211 | 157 | 223 | 157 | Wired |
| fema | ics_213 | 15 | 28 | 15 | Wired |
| fema | ics_213rr | (none) | 29 | - | Needs template (mapping orphaned) |
| fema | ics_214 | 84 | 86 | 84 | Wired |
| fema | ics_215 | (none) | 50 | - | Needs template (mapping orphaned) |
| fema | ics_215a | 55 | 13 | 55 | Wired - raw FEMA template added; uses repeating `ics_215a_rows`; test-fill verified zero warnings |
| fema | ics_217 | 202 | 209 | 202 | Wired |
| fema | ics_218 | 152 | 215 | 152 | Wired |
| fema | ics_220 | (none) | 45 | - | Needs template (mapping orphaned) |
| fema | ics_221 | (none) | 10 | - | Needs template (mapping orphaned) - see orphaned-mapping example above |
| fema | ics_225 | 100 | (none) | - | Needs mapping |
| fema | ics_230 | 44 | (none) | - | Needs mapping |
| fema | ics_233 | 378 | (none) | - | Needs mapping |
| fema | ics_309 | 0 | (none) | - | Non-fillable source PDF, no mapping started - source file has 0 fields and 0 annotations (not corruption, never a fillable AcroForm) |
| ics_canada | ics_201 | 160 | 169 | 160 | Wired |
| ics_canada | ics_203 | 117 | 195 | 69 | Mapped, not yet test-fill verified |
| ics_canada | ics_205 | 85 | 7 | 85 | Wired - row-group coverage fills the 13 channel rows; test-fill verified zero warnings |
| ics_canada | ics_207 | 114 | 120 | 98 | Mapped, not yet test-fill verified |
| ics_canada | ics_208 | 13 | 14 | 13 | Wired |
| ics_canada | ics_214 | 148 | 84 | 78 | Mapped, not yet test-fill verified |
| ics_canada | ics_309 | 183 | 188 | 183 | Wired |
| sar | ics_309 | 88 | 93 | 88 | Wired |
| sar | sar_100 | 14 | 14 | 14 | Wired |
| sar | sar_100a | 30 | 29 | 29 | Wired |
| sar | sar_100b | 0 | 0 | 0 | Non-fillable source PDF (mapping.json present but empty - matches the source having no fields) |
| sar | sar_102 | 0 | 0 | 0 | Non-fillable source PDF (same as above) |
| sar | sar_104 | 85 | 85 | 85 | Wired |
| sar | sar_110 | 54 | 28 | 28 | **Wired** - test-fill verified zero warnings this session; the gap is entirely `Row2`-`Row4` fields intentionally left out per convention, not a real gap |
| sar | sar_112 | 38 | 13 | 13 | **Wired** - test-fill verified, same `RowN` convention as above |
| sar | sar_115 | 32 | 11 | 11 | **Wired** - test-fill verified, same `RowN` convention as above |
| sar | sar_116 | 30 | 12 | 12 | **Wired** - test-fill verified, same `RowN` convention as above |
| sar | sar_119 | 4 | 3 | 3 | **Wired** - test-fill verified, same `RowN` convention as above |
| sar | sar_125 | 131 | (none) | - | Needs mapping |
| sar | sar_125a | 228 | (none) | - | Needs mapping |
| sar | sar_131 | 39 | (none) | - | Needs mapping |
| sar | sar_132 | 0 | (none) | - | Non-fillable source PDF, no mapping started |
| sar | sar_134 | 227 | 234 | 227 | Wired |
| sar | sar_135 | 50 | 55 | 50 | Wired |
| sar | sar_301 | 0 | (none) | - | Non-fillable source PDF, no mapping started |
| sar | sar_301a | 43 | (none) | - | Needs mapping |
| sar | sar_302 | 346 | (none) | - | Needs mapping |
| sar | sar_304 | 15 | (none) | - | Needs mapping |
| sar | sar_305 | 0 | (none) | - | Non-fillable source PDF, no mapping started |
| sar | sar_306 | 0 | (none) | - | Non-fillable source PDF, no mapping started |
| sar | sar_307 | 510 | (none) | - | Needs mapping |
| uscg | ics_201 | 256 | 259 | 256 | Wired |
| uscg | ics_202 | 14 | 14 | 14 | Wired |
| uscg | ics_203 | 122 | 141 | 122 | Wired |
| uscg | ics_207 | 71 | 71 | 71 | Wired |
| uscg | ics_214 | 57 | 59 | 57 | Wired |
| uscg | ics_205 | 150 | 10 | 150 | Wired - mapped this session from the provided USCG PDF; test-fill verified zero warnings |
| uscg | ics_233 | 239 | (none) | - | Needs mapping |

Forms registered in `forms/catalog.json` with **no folder under
`forms/sets/` at all yet** (no template, no mapping, in any set):
`ics_301`, `ics_308` (intentionally held - see chat history), plus
anything added to the catalog after this table was last regenerated.
Cross-check `forms/catalog.json`'s `"forms"` list against
`forms/sets/<any set>/` if you need the fully current list.

## Worked example: the debrief wiring (copy this pattern)

1. **Layer 1** - `FormDataContext._empty_debrief_shape()` and
   `FormDataContext.build_debrief(debrief_id, incident_id=None)` in
   `modules/forms_creator/context.py`. `build()` seeds
   `data["debrief"] = self._empty_debrief_shape()` unconditionally so the
   paths always resolve. `build_debrief()` is the real fetch - it calls
   `GET /api/incidents/{id}/operations/debriefs/{debrief_id}`, flattens
   the per-type `forms.<type>.<field>` sub-documents into
   `debrief.<type>.<field>`, and resolves linked clue/subject IDs into
   human-readable summary strings via the intel repositories.

   Full field list produced (this is the level of detail every Wired
   row above should eventually have, inline, once you pick it up):
   `sortie_number`, `debriefer_id`, `status`, `flagged_for_review`,
   `types`, `created_at`, `updated_at`, `linked_clue_ids`,
   `linked_clues_summary`, `linked_subject_ids`,
   `linked_subjects_summary`, plus six nested sub-dicts -
   `ground.*` (assignment_summary, efforts, unable, clues, hazards,
   suggestions, time_entered, time_exited, time_spent, clouds,
   precipitation, light, visibility, terrain, ground_cover, wind_speed,
   att_map, att_brief, att_supp, att_interviews, att_other),
   `area.*` (num_searchers, time_spent, search_speed, area_size, spacing,
   visibility_distance, visibility_how, skipped_types, direction_pattern,
   comments),
   `tracking.*` (likelihood_tracks, existing_traps, erase_traps,
   new_traps, route_tracks, why_discontinue, att_individual_sketches,
   att_trap_summary),
   `hasty.*` (visibility, attract, hear, trail_cond, offtrail_cond,
   map_accuracy, features, tracking_cond, hazards_attract),
   `air_general.*` (flight_plan_closed, atd, ata, hobbs_start, hobbs_end,
   hobbs_to_from, hobbs_in_area, hobbs_total, tach_start, tach_end,
   fuel_used_gal, oil_used_qt, fuel_oil_cost, receipt_no, summary,
   results, weather, remarks, sortie_effectiveness, reason_not_success,
   att_capf104a, att_capf104b, att_ics214, att_receipts, att_aif_orm),
   `air_sar.*` (area_name, area_grid, area_nw, area_ne, area_sw, area_se,
   act_pattern, act_visibility_nm, act_altitude_agl, act_speed_kts,
   act_track_spacing_nm, act_terrain, act_cover, act_turbulence, act_pod,
   act_time_to_search, act_time_started, act_time_ended,
   act_time_in_area, act_time_from_area, act_total_sortie_time,
   remarks_effectiveness, remarks_visibility).

2. **Layer 2** - 118 entries in `forms/binding_catalog.json` under
   categories `"Debriefing - Ground"` and `"Debriefing - Air"`, each
   `source_type: "incident_db"`, `table: "task_debriefs"` (the real Mongo
   collection name), `column` set to the dotted field path.
3. **Layer 3** - `forms/sets/sar/sar_110/mapping.json` (Ground),
   `sar_112` (Area Search), `sar_115` (Tracking), `sar_116` (Hasty),
   `sar_119` (generic supplement) - each a real PDF's AcroForm fields
   mapped to `debrief.<type>.*` paths, verified against the actual
   templates with zero `PDFFiller.fill()` warnings before being
   considered done.

No PDF exists yet for Air General/Air SAR Worksheet debrief content, so
those catalog entries (layer 2) are intentionally still inert - that's
expected and fine; they're ready for whenever that form gets built.

Two known gaps surfaced while mapping the real PDFs against this data
(left unmapped rather than guessed):
- SAR 115 (Tracking Team Debrief) asks separately about on-trail vs.
  off-trail likelihood of finding sign; `debrief.tracking.likelihood_tracks`
  only covers one of those - the editor UI needs a second field before the
  off-trail PDF field can be mapped.
- SAR 119 (generic Debriefing Supplement) has one freeform `Text1` box
  with no clear semantic match in the debrief schema.

## Mistakes already made once - don't repeat them

- **Dataclass `to_api_dict()` silently dropping fields.** `IntelItem` and
  `Subject` (in `modules/intel/models/`) both omitted `linked_task_ids`
  (and similar link fields) from their `to_api_dict()` output, even though
  the server's Pydantic models accepted them - so any code trying to
  write those fields via `update()` silently lost the data. When you add
  a model used by this pipeline, double check `to_api_dict()` includes
  every field the server actually accepts, not just the ones obviously
  exercised by existing call sites.
- **Adding a catalog entry without a real builder.** See "Known stale
  entries" above. The catalog has no validation step that checks a path
  actually resolves - that's on you to verify with a real `build()` call
  before considering the work done.
