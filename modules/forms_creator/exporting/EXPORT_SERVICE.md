# Prompt: Finish a form builder

Paste this whole file's content (or tell Claude to read this file) at the
start of a new chat to continue the form-builder work started on
2026-07-27/28 (SAR 104). It is meant to need almost no manual input beyond
picking a form.

## Step 0 — Orient yourself

Read, in order:

1. `modules/forms_creator/BINDING_PIPELINE.md` — how `context.py` +
   `binding_catalog.json` + `mapping.json` turn a MongoDB value into text
   on a PDF field. This is the foundation everything below sits on.
2. `form_builder_inventory.md` (repo root) — the audited, per-form-set
   binding-completeness table. **Bound** means every real fillable PDF
   field resolves to a value; **Partial (X%)** means some do; **Not
   Bound**/**Template**/**Mapping** mean there's real work to do before a
   builder is even worth writing. Read the Methodology and Revision
   History sections at the bottom — the first two audit passes in that
   history were wrong (didn't know about row_groups, didn't exclude
   AcroForm parent/group nodes from the count) before landing on the
   correct leaf-fields-only approach. Don't repeat those mistakes if you
   re-audit a form.
3. The "Architecture reference" section below (same content this file
   used to be, kept for background) — the pieces (`ExportRequest`,
   `ExportBuilder`, `PreparedExport`, `ExportRegistry`, `ExportService`),
   and the worked ICS-205 and SAR 104 examples.

## Step 1 — Ask which form, then get out of the way

Ask the user exactly one question: **which form should this session
complete?** Point them at `form_builder_inventory.md` if they want to pick
by completeness (e.g. "lowest Bound %" or "next Not Bound one"). Once
they answer, do not ask for anything else you can determine yourself —
resolve the form set(s), the underlying data domain, and existing
patterns to copy from the codebase directly.

## Step 2 — Re-audit that form's actual binding, don't trust the table blindly

The inventory table is a snapshot from 2026-07-27. Before touching code,
re-verify the chosen form's binding percentage yourself:

1. Load `template.pdf`'s AcroForm with `pypdf.PdfReader.get_fields()`.
2. Count only **leaf fields** — `/FT` is set (an actual `/Tx`, `/Btn`, or
   `/Ch` widget). Exclude parent/group nodes (`/FT` is `None`) — those are
   naming containers (e.g. `POD.h` grouping `POD.h.responsive` /
   `.unresponsive` / `.clues`), never real fields.
3. A leaf field counts as bound if `mapping.json` gives it a non-empty
   `source`, OR its name matches a `row_groups[].col_patterns` regex
   (populated dynamically from a repeating array, not a per-field
   `source`).
4. For anything that comes up unbound or wrong, don't assume the field
   list is complete either — check for PDF leaf fields that don't appear
   in `mapping.json` at all (a `pypdf` field-name diff catches these).

If you need a throwaway script for this, write it to the scratchpad
directory, not into the repo.

For every unbound/wrong field you find, sort it into one of two buckets
before moving on — this distinction matters for the final report in
Step 7:

- **Fixable now**: the data already exists somewhere reachable (a
  repository function, an existing API endpoint, another form's context)
  and this is just a missing or wrong `mapping.json`/`transform` wire-up.
  Fix it in Step 3.
- **No data source exists yet**: the field wants information the program
  doesn't currently track anywhere — no collection, no API field, no UI
  to enter it. Don't invent a fake source or leave a silent blank to paper
  over this. Note the field name, what it appears to want (label/position
  on the form), and that it has nowhere to pull from. This goes in the
  final report's "fields with no data source" list — do not build new
  data-model plumbing to fill these in unless the user explicitly asks.

## Step 3 — Fix the bindings, verified against real data

For every field that's unbound, wrongly bound, or unformatted:

- Trace where the underlying value actually comes from (usually a
  `repository.py` context-builder function feeding `mapping.json`'s
  `source` paths — see BINDING_PIPELINE.md for the full chain).
- Prefer fixing formatting/composition at the `mapping.json` layer using
  `pdf_filler.py`'s existing `transform` mechanism (`date_short`,
  `time_short`, `datetime_short`, `datetime_human`, `freq_mhz`, `join`,
  `first_of`, `checkbox`, etc.) over writing pre-formatted strings in
  Python — that keeps formatting decisions in one place. Add a new
  transform to `_apply_transform` in `pdf_filler.py` if none of the
  existing ones fit; don't hand-roll formatting inline in
  `repository.py`.
- Timestamps: use `datetime_human` (or extend `time_short`) — both
  already convert to local time and append the abbreviated timezone via
  `utils/timefmt.py`'s `to_datetime()`/`abbreviate_tz_name()`. Don't
  invent a second timezone-handling path.
- **Do not silently "fix" a value by padding/reformatting past what the
  database actually stores** (e.g. don't force a frequency to a fixed
  decimal count if the source data has more or fewer significant digits
  than that) — display what's really there, and flag the root-cause data
  problem separately if the stored value itself looks wrong.
- **Test against real data, not just fixtures.** MongoDB is running
  locally (`mongodb://localhost:27017`, database naming
  `sarapp_incident_<incident-number>` / `sarapp_master`). Wire the
  in-process FastAPI app so `api_client` never needs a real server
  process:

  ```python
  import os
  os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")
  from utils import incident_context
  from utils.api_client import api_client
  from data.db.sarapp_db.api.app import create_app

  incident_context.set_active_incident("<incident-number>")  # e.g. "2025-FAIR"
  api_client.configure_test_transport(create_app())
  ```

  Then call the builder/context function directly, inspect the resolved
  values, and actually generate a PDF via
  `modules.forms_creator.pdf_filler.pdf_filler.PDFFiller` (or the
  registered `ExportBuilder`, once Step 5 exists) — don't just eyeball
  `mapping.json`. Query Mongo directly first to find a real
  incident/task/team/record with enough data to exercise the form
  meaningfully (empty test fixtures won't catch real layout or data
  problems).
- When something in the rendered PDF looks wrong (duplicated values,
  misplaced fields, wrong precision), check the PDF's actual field
  geometry (`/Rect` on each annotation) before assuming the binding is
  wrong — form templates sometimes have irregular field naming (see the
  SAR 104 "row 1 has different field names than the rest of the roster
  table" case in this session's history) that isn't a mapping bug at all.
  If you're not sure what a field actually is, generate a diagnostic copy
  of the template with every field filled with its own field name and
  send that to the user rather than guessing from coordinates.
- Update/add `pytest` coverage for whatever you change (see
  `tests/test_sar104_assignment_export.py` for the pattern: fixture-based
  context tests, plus a `PDFFiller._resolve_value` sweep asserting nothing
  resolves to `None`). Run the relevant suite
  (`modules/forms_creator/tests/`, plus whatever `tests/test_<form>_*.py`
  exists) after every change, not just at the end.
- If you hit a binding decision you're not confident about — the source
  data's meaning is ambiguous, two plausible fields could feed one box,
  the form's intent isn't clear from the template alone, or fixing it
  correctly would require a judgment call about how the app *should*
  behave rather than how it currently does — don't guess and move on.
  Make the best call you can to keep moving, but write the question down
  for the final report's "open questions" list in Step 7. (This session's
  SAR 104 work had exactly this kind of case: whether the personnel
  table's `*` column should show a computed value or something else
  needed to be resolved with the user before the fix was correct.)

## Step 4 — Build the precise `ExportBuilder`, if one doesn't exist yet

Follow "Adding a new form to this layer" in the Architecture reference
below. Reuse `_active_incident_id`/`_output_path` helpers already in
`builders/ics.py` / `builders/work_assignments.py` /
`builders/task_assignments.py` rather than reimplementing them. Only
write a dedicated builder class when the generic passthrough
(`GenericFormBuilder`/`IcsFormBuilder`) genuinely isn't enough — most
forms need a builder because they're scoped to one task/team/strategy
record, not because of anything exotic.

Register it in `builders/__init__.py`, and remove the form's ID from
`generic.py`'s fallback list if it was there. Add/extend
`modules/forms_creator/tests/test_exporting.py` covering the registry
lookup and the builder's `extra_data` shape (see the SAR 104 tests added
this session for the pattern).

## Step 5 — Find existing export buttons, but don't wire them yet

Search the codebase for anywhere already generating this form, e.g.:

```bash
grep -rn "generate_form_pdf\|engine\.generate\|export_assignment_forms\|default_export_service\|ExportService" modules/ --include="*.py"
```

Also check for form-specific button/menu wiring in each module's panel
files (button labels, checkbox lists like the SAR 104/ICS 204/CAPF 109
"Generate Forms" dialog in
`modules/operations/taskings/task_detail_widget.py`). For each one you
find, note the file, function/method, and what it currently calls to
generate the form (which repository function / which `generate()` call
path) — this becomes the final report's "existing export locations" list
in Step 7.

**Do not modify any of them or wire them to the new `ExportBuilder`/
wrapper function unless explicitly asked.** The point of this step is an
inventory of "here's what already generates this form and how," so the
user can decide whether to migrate each call site onto the new builder.
Present it as a list, not a diff.

## Step 6 — Generate a real sample and hand it off

Using a real Mongo-backed incident/task/team (per Step 3's test-transport
setup), generate one actual PDF through the full pipeline (builder →
`engine.generate()`, or `PDFFiller` directly if no builder was needed)
and send it to the user for visual review before considering the form
done. Don't rely on "the mapping/tests pass" alone — the SAR 104 work
this session found multiple real defects (duplicated leader row, wrong
timestamp precision, missing timezone, wrong resource-type formatting)
that only showed up in the rendered output, not in the field-binding
audit or the unit tests.

## Step 7 — Close the loop

Update `form_builder_inventory.md`'s row for the form you worked on with
the corrected Bound/Partial percentage and, if you built one, note the
precise builder now exists (the "Builder Level We Can Create" column).
Run the full relevant test suite one more time before ending the session.

Then give the user a final report with exactly three lists — this is the
required output of every session run from this prompt, not optional
wrap-up chatter:

1. **Fields with no data source.** Every PDF field from Step 2/3's "no
   data source exists yet" bucket: field name, what it appears to be for
   (label/position on the form), and, if you can tell, what would need to
   exist (a new collection field, a new API endpoint, a new UI input) to
   fill it. Say explicitly if this list is empty — don't omit the section.
2. **Existing export locations.** The full list gathered in Step 5: file,
   function/button, and current call path for every place in the program
   that already generates this form. Say explicitly if none were found.
3. **Open questions about bindings.** Every judgment call from Step 3 you
   flagged rather than guessed through: what's ambiguous, what you did in
   the meantime, and what you need the user to confirm. Say explicitly if
   this list is empty.

---

## Architecture reference

Read `modules/forms_creator/BINDING_PIPELINE.md` first if you haven't -
that document explains how `context.py` + `binding_catalog.json` +
`mapping.json` get a value from MongoDB onto a PDF field. **This section
is about a different, thinner layer that sits on top of that pipeline**:
the code a UI button actually calls to trigger one specific export,
instead of every panel hand-rolling its own call to
`modules.forms_creator.engine.generate()`.

If the binding pipeline answers "how does `incident.name` become the text
in this PDF field", this layer answers "what does a button click actually
run, and where does it get the one record/plan/assignment it needs before
handing off to that pipeline."

### Why this exists

Before this layer, every panel that needed to export a form wrote its own
version of: resolve the active incident, build an output path under
`forms_generated/`, gather whatever data that one form needs, and call
`engine.generate()` directly. That data-gathering step is exactly where
bugs like the stale ICS-205 gap (see "Worked example" below) crept in -
each panel re-implemented it slightly differently, and some panels never
updated it when the underlying data model changed.

The export service factors "gather the data for form X, given a request"
into one small object per form (a **builder**), registered once, and
callable identically from any button anywhere in the app.

### The pieces (`modules/forms_creator/exporting/`)

- **`ExportRequest`** (`models.py`) - the input. A frozen dataclass:
  `form_key`, optional `target_type`/`target_id`, `incident_id`,
  `form_set_id`, and a free-form `options` dict for anything
  builder-specific (e.g. `op_period_id`, a manual `extra_data` overlay).
  This is what a button constructs and hands to the service - it never
  touches the API or the filesystem itself.
- **`ExportBuilder`** (`builder.py`) - a `Protocol` with one method,
  `build(request) -> PreparedExport`. One concrete class per form (or
  small family of forms) that actually calls the live API, shapes the
  data, and decides the output path. This is where form-specific logic
  lives - e.g. "only include channels flagged `include_on_205`", "resolve
  the active operational period if none was given."
- **`PreparedExport`** (`models.py`) - the builder's output: `form_id`,
  `output_path`, `incident_id`, `form_set_id`, and `extra_data` (merged
  into the binding-pipeline context dict exactly like `engine.generate()`'s
  `extra_data` parameter already did - see BINDING_PIPELINE.md's "Singular
  vs list data" section; this layer is just a structured way of producing
  that same dict).
- **`ExportRegistry`** (`registry.py`) - a dict from a normalized
  `form_key` string to one `ExportBuilder` instance. Multiple keys can
  point at the same builder (e.g. `"ics_205"`, `"ics:ics_205"`,
  `"ICS 205"`, `"communications_plan"`) so callers can look it up however
  is natural to them.
- **`ExportService`** (`service.py`) - `.export(request)`: looks the
  builder up in the registry, calls `build()`, then hands the resulting
  `PreparedExport` to `modules.forms_creator.engine.generate()` (or an
  injected `generator` callable, used by tests). Returns an `ExportResult`
  (form key/id, output path, generation timestamp, metadata).
  `default_export_service()` builds one wired to the real registry - this
  is what every non-test caller should use.
- **`builders/`** - one module per form family, each exposing a
  `register_<family>_builders(registry)` function.
  `builders/__init__.py.default_registry()` calls all of them in a fixed
  order and returns the assembled registry. **Order matters**: a later
  `register_*` call can override an earlier one's key by registering the
  same string again (see the ICS-205 override below) - the registry is
  just a dict, last write wins.

### How a button uses this

Don't call `ExportService`/`ExportRequest` directly from a widget. Write a
tiny form-specific wrapper function in that form's own module (see
`modules/planning/tactics_resources/services/output_export_service.py`
for the original pattern, and
`modules/communications/services/ics205_export_service.py` for the ICS-205
one) so the widget only ever imports one function with plain keyword
arguments:

```python
from modules.communications.services.ics205_export_service import generate_ics205

result = generate_ics205(incident_id=str(incident), op_period_id=selected_op_period_id)
os.startfile(str(result.output_path))
```

That wrapper is the thing "ready to accept an export button anywhere" -
any new panel that needs an ICS-205 export button imports this one
function; it doesn't need to know a registry or a builder exist.

### Worked example: ICS-205 (`builders/communications.py`)

The generic `IcsFormBuilder` (`builders/ics.py`) is registered for every
standard ICS form ID, `ics_205` included, and does nothing form-specific -
it just resolves the incident and output path and lets
`FormDataContext.build()`'s defaults fill in the rest. For most forms
that's fine. For ICS-205 it was **wrong**: `FormDataContext._build_channels`
returns every channel row regardless of the `include_on_205` flag or which
operational period is active, and `data["channels_notes"]` is hardcoded to
`""` in `context.py` - never wired to the special-instructions text the
ICS-205 editor (`modules.communications.panels.ics205_window`) actually
saves per operational period via `PUT
/api/incidents/{id}/communications-plan`.

`Ics205FormBuilder` fixes this by building its own `extra_data` instead of
relying on the generic defaults:

1. Resolve `op_period_id` - from `request.options["op_period_id"]` if the
   caller passed one (the ICS-205 window always does, using whichever
   operational period is selected in its dropdown), otherwise falls back
   to `OperationalPeriodRepository.get_active_period()`.
2. `GET /api/incidents/{id}/channels-plan`, sort by `sort_index`, then
   filter to rows where `include_on_205` is true - matching exactly what
   the ICS-205 editor's channel table would show as "on the plan."
3. `GET /api/incidents/{id}/communications-plan?op_period_id=...` for the
   real saved `special_instructions` text.
4. Returns `PreparedExport` with `extra_data = {"channels": [...],
   "channels_notes": "..."}`, which overlays those two keys onto whatever
   `FormDataContext.build()` produced (via `ctx.update(extra_data)` inside
   `engine.generate()` - same mechanism BINDING_PIPELINE.md describes for
   `extra_data`, nothing new).

It's registered under the form key `"ics_205"` (plus a few aliases) in
`builders/__init__.py`, **after** `register_ics_builders()` runs, so its
entry replaces the generic passthrough one for that key specifically -
every other standard ICS form is untouched.

#### Why one builder covers all three form sets (FEMA / ICS Canada / USCG)

`forms/sets/fema/ics_205/mapping.json`,
`forms/sets/ics_canada/ics_205/mapping.json`, and
`forms/sets/uscg/ics_205/mapping.json` all read from the same two data
keys - `channels` (as a `row_groups` repeating block) and
`channels_notes` (a single "Special Instructions" field) - they only
differ in *which PDF field names* those values get written to. That
mapping-to-field resolution is entirely `engine.generate()`'s job (layer 3
of the binding pipeline, resolved via `form_set_id`); the builder never
needs to know which set is being rendered. Pass `form_set_id="fema"` /
`"ics_canada"` / `"uscg"` on the `ExportRequest` (or via
`generate_ics205(form_set_id=...)`) to pick the variant; omit it to use
the app's configured default set and fallback chain.

### Worked example: SAR 104 (`builders/task_assignments.py`)

Task/team-scoped forms (SAR 104, and CAPF 109/ICS 204 which share the same
underlying data) follow a different shape than ICS-205's plan-scoped one:
`TaskAssignmentFormBuilder.build()` requires `request.target_id` (a task
ID) and an optional `request.options["team"]`, then calls
`modules.operations.taskings.repository._build_assignment_export_context(
task_id, team)` directly (an in-process Python call, not an HTTP request -
this repository function isn't behind the API layer) to get the full
`extra_data` dict. A manual `request.options["extra_data"]` overlay (e.g.
`{"notes": "..."}`) is merged on top afterward, which is how one-off
per-export text (like a note typed in at export time) reaches the PDF
without needing a stored field for it.

This session's SAR 104 work also fixed several defects in
`_build_assignment_export_context` itself that are worth knowing about if
you touch it again: `leader_index` must be resolved against a *confirmed*
leader name (`team_leader`/`team_leader_name`/`team_leader_id`), not a
"default to whoever's first" fallback - computing it after that fallback
made every unconfirmed-leader case spuriously look confirmed. See the
comments around `leader_index` in `repository.py` for the corrected
ordering, and `test_sar104_context_keeps_first_member_in_roster_when_leader_unconfirmed`
for the regression test.

## Adding a new form to this layer

1. Decide whether the generic `IcsFormBuilder` (or `generic.py`'s plain
   passthrough) is actually good enough - most standard ICS forms need
   nothing more, since `FormDataContext.build()` already assembles
   everything from the binding pipeline. Only write a dedicated builder
   when the export needs to filter/scope/overlay data beyond what
   `context.py`'s defaults already produce (a specific record by ID, a
   specific operational period, a subset flag like `include_on_205`).
2. If you do need one: add a small class with a `build(request) ->
   PreparedExport` method in a new or existing `builders/<family>.py`
   file, plus a `register_<family>_builders(registry)` function. Reuse
   `_active_incident_id` / `_output_path` from `builders/ics.py` rather
   than reimplementing incident resolution or filename sanitization.
3. Wire the registration call into `builders/__init__.py`'s
   `default_registry()`. If you're overriding a generic entry for one
   specific form ID (like the ICS-205 case above), register your family
   *after* the one you're overriding, and leave a comment saying so - the
   override is otherwise invisible/easy to break by reordering.
4. Write a thin wrapper function (one function, plain keyword args,
   returns a small frozen dataclass) in that domain's own module for
   panels to call - don't make callers import `ExportRequest`/
   `default_export_service` directly.
5. Add/extend a test in `modules/forms_creator/tests/test_exporting.py`
   covering the registry lookup and the builder's `extra_data` shape.
