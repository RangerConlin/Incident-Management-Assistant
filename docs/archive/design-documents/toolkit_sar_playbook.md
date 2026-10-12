# SAR Toolkit Playbook

## Purpose
The SAR Toolkit supports search-focused incidents where teams need to move from intake to search strategy to field execution with as little friction as possible.

## What This Module Provides
The SAR Toolkit is the search-specific operational workspace inside the app. Its job is to bring together the parts of a SAR incident that are unique to missing person and field search work, and present them in one coherent flow.

At a high level, this module should provide:
- SAR-specific search planning tools
- search planning support
- search execution support
- search progress and coverage review
- SAR-specific decision support such as behavior profile and POD

This module should help users answer:
- Who are we looking for?
- What do we currently know?
- Where should we search next?
- Which teams are doing what right now?
- How effective has the search been so far?
- What needs to change for the next operational period?

## What This Module Does Not Need To Own
The SAR Toolkit should not try to replace the rest of the app. It should use and coordinate with broader systems where they already exist.

It should generally not own:
- missing person intake
- general dashboards already covered elsewhere
- timeline and investigation workflows
- clue management
- generic incident command functions
- the master personnel system
- the communications plan itself
- full GIS authoring
- general document storage for the whole incident
- non-SAR workflows that belong to other modules

Instead, it should surface SAR-relevant slices of those systems and connect SAR work back into them.

## Relationship To Initial Response
Missing person intake should live under the Initial Response module, not inside the SAR Toolkit.

That means Initial Response should own:
- the first missing person report
- reporting party capture
- immediate urgency factors
- the earliest narrative of circumstances

The SAR Toolkit should then consume that intake and build on it by supporting:
- search planning
- search execution support
- search reassessment

## Relationship To Intel
Timeline, investigation, and clue management should remain under the Intel module rather than being reimplemented in SAR.

That means Intel should own:
- timeline development
- witness and interview tracking
- clue intake and validation
- investigative notes

The SAR Toolkit should consume Intel outputs such as:
- validated clues
- timeline-derived planning inputs
- refined LKP/PLS information
- investigative findings relevant to search planning

## Current Repo Signals
- Placeholder panels already exist for:
  - Missing Person Toolkit
  - POD Calculator
- The active app wiring imports SAR tools from the root-level package `modules.sartoolkit`.
- `modules/toolkits/sar` appears to be older scaffolding and should not drive new design decisions.

## Primary Users
- Incident Commander
- Planning Section
- Operations Section
- Ground team leaders
- Search managers
- Investigations or interview staff

## Operational Goals
- capture the subject profile quickly
- convert clues into operational planning inputs
- track search assignments and search progress
- surface urgency, survivability, and high-value search actions
- maintain a clean chain from missing person information to field tasking

## Candidate Tool Set
- Subject Profile / Behavior Profile
- Search Strategy Summary
- Probability of Detection
- Search Segment Manager
- Search Assignment Planner
- Search Execution Tracker
- Search Coverage Review
- Search Debrief / Reassessment
- Map and area references

## Proposed Submodules
The SAR Toolkit should be broken into a small set of submodules that match how search incidents are actually worked.

### 1. Search Planning
Purpose:
Support the planning team in deciding where and how to search.

What it provides:
- subject behavior profile
- lost person behavior analysis
- Mattson and related search evaluations
- planning assumptions
- search strategy summary
- priority area logic
- POD support
- search segment planning
- general search segment management

What this submodule is for:
This is the analytical heart of the SAR toolkit. It turns the current picture of the incident into an actual search plan. It should help planners explain why resources are going to certain areas, which assumptions are driving that plan, and how search effectiveness is being judged.

It should support:
- maintaining the search-planning view of the subject profile
- conducting lost person behavior analysis
- capturing Mattson and similar evaluative search-planning methods
- selecting and prioritizing search areas
- maintaining the general search segment list and segment planning status
- documenting planning assumptions
- behavior-based reasoning
- choosing search methods for conditions and terrain
- estimating and revising POD
- preparing the next operational period’s search strategy

This submodule should not try to replace full GIS, but it should be able to reference segments, map products, and area priorities clearly.

Typical outputs:
- lost person behavior summary
- Mattson or equivalent planning evaluation summary
- search strategy summary
- prioritized segment list
- maintained search segment plan
- planning rationale for briefing
- POD update notes
- recommended search assignments for operations

What it should not own:
- generic incident objectives
- clue validation
- generic task board behavior already handled elsewhere
- team roster management
- map authoring

#### Search Planning Internal Components
Search Planning is substantial enough that it should be treated as a planning workspace made up of several focused internal components.

##### 1. Lost Person Behavior Assessment
Purpose:
Help SAR planners turn subject profile, circumstances, and known lost person behavior references into explicit planning assumptions.

What it provides:
- guided worksheet for the current incident
- reference guidance by subject category
- planner-authored behavior assessment
- confidence and applicability notes
- behavior-driven impacts on search priorities, segment focus, search methods, and urgency

What it consumes:
- missing person intake from Initial Response
- timeline, LKP/PLS, witness notes, and validated facts from Intel
- environment, terrain, weather, and map context where relevant

What it produces:
- behavior assessment summary
- applicable behavior factors
- non-applicable or rejected behavior factors
- planning assumptions
- survivability concerns
- priority area impacts
- search method impacts

Design principle:
The tool can suggest and organize behavior guidance, but the planner decides what applies. The assessment is a transparent planning artifact, not an automated answer.

What it should not do:
- replace confirmed facts from Intel
- present speculative conclusions as verified information
- become a generic subject record editor

##### 2. Segment Evaluation
Purpose:
Let the planning group rate search segments and establish consensus POA or priority values.

What it provides:
- simple segment-by-evaluator rating worksheet
- evaluation rounds
- evaluator prompts or requests
- comparison of evaluator ratings
- final consensus or planner-approved value
- optional lightweight factors reference table

Core workflow:
1. Planning creates or selects segments in Search Segment Management.
2. Planning opens a Segment Evaluation round.
3. Planning selects evaluators.
4. Each evaluator rates each segment.
5. The worksheet displays all ratings in one chart.
6. Planning discusses differences and records consensus or final POA.
7. Final values feed Search Segment Management, Search Strategy, and Search Review.

Worksheet shape:
- `segment_id`
- `segment_name`
- `evaluator`
- `rating`
- `notes`

Displayed chart/table:
- one row per segment
- one column per evaluator
- consensus or final POA column
- optional notes column

Optional factor table:
- distance from LKP/PLS
- terrain
- travel corridors
- attraction points
- containment or barriers
- clue relationship
- previous search
- accessibility
- hazards

Design principle:
The evaluation worksheet should stay simple. Factors are supporting prompts, not mandatory detailed scoring fields.

Boundary:
Search Segment Management owns segment records. Segment Evaluation owns evaluation rounds, evaluator worksheets, and final consensus values.

##### 3. Search Segment Management
Purpose:
Maintain the canonical SAR search segment list used by planning, evaluation, operations, probability calculations, and review.

Core principle:
A segment does not require GIS geometry. It can be created from a paper map, verbal boundary, grid reference, landmark description, or GIS feature. GIS linkage is optional.

What it owns:
- segment IDs and names
- segment descriptions
- boundary descriptions
- map references
- optional GIS references
- terrain, access, and hazard notes
- segment grouping
- parent/child segment relationships
- planning readiness state
- references to evaluations, assignments, probability history, and review outcomes

Suggested segment fields:
- `segment_id`
- `name`
- `description`
- `boundary_description`
- `map_reference`
- `gis_reference`
- `parent_segment_id`
- `terrain_notes`
- `access_notes`
- `hazards`
- `size_estimate`
- `planning_status`
- `search_status`
- `review_status`
- `created_by`
- `created_at`
- `updated_at`

Status fields:
- `planning_status`: draft, ready for evaluation, evaluated, ready for assignment, deferred
- `search_status`: unsearched, assigned, in progress, searched, partially searched
- `review_status`: pending review, needs re-search, closed

Hierarchy:
Support `parent_segment_id` so broad areas can be subdivided without losing parent context.

Boundaries:
- GIS owns map authoring and geometry.
- Operations owns deployment and live accountability.
- Search Review owns final interpretation of coverage.
- Segment Management owns the segment as a SAR planning object.

##### 4. Segment Probability Management
Purpose:
Maintain the POA, POD, POS, and residual POA calculation history associated with each search segment across planning and search cycles.

Ownership:
This belongs inside Search Segment Management.

Inputs:
- consensus ratings or estimates from Segment Evaluation
- planner-approved POA values
- planned POD values from Planning
- reviewed POD or search effectiveness values from Search Review
- segment status and search history

Core values:
- `consensus_rating`
- `planning_poa`
- `planned_pod`
- `reviewed_pod`
- `pos`
- `residual_poa`
- `next_cycle_poa`

Key math:
- `POS = POA * POD`
- `Residual POA = POA * (1 - POD)`

No auto normalization:
The app should not automatically force POA totals to 100%. Some consensus methods intentionally produce values that are not normalized, or use ratings and rankings that should not be treated as directly proportional probability mass. The app may show totals and warnings, but planners control final values.

Workflow:
1. Segment Evaluation produces consensus ratings.
2. Planner converts or approves values as `planning_poa`.
3. Planning enters expected POD for proposed searches.
4. Search happens.
5. Search Review confirms or adjusts `reviewed_pod`.
6. Segment Management calculates POS and residual POA.
7. Planner approves `next_cycle_poa`.

Probability history row:
- `segment_id`
- `cycle_id`
- `starting_poa`
- `planned_pod`
- `reviewed_pod`
- `pos`
- `residual_poa`
- `next_cycle_poa`
- `source_evaluation_round`
- `source_review`
- `approved_by`
- `notes`

Design principle:
The app calculates visible values, but it does not silently turn calculations into the next official planning POA. Planner approval controls what becomes official for the next cycle.

##### 5. Search Strategy
Status:
Deferred for later design.

Current intent:
Search Strategy should likely be a versioned, planner-authored planning artifact that references Lost Person Behavior Assessment, Segment Evaluation, Search Segment Management, Segment Probability Management, Intel outputs, GIS references, and Search Review findings.

Design caution:
This section should synthesize planning judgment without owning source data already managed by other submodules.

## Boundary: Search Planning vs. Intel, GIS, and Operations
Search Planning is the analytical center of the SAR toolkit, but it should not become a catch-all for every upstream or adjacent function.

### Search Planning Should Own
These are the planning responsibilities that belong inside SAR:
- translating intake and investigative inputs into search priorities
- owning lost person behavior analysis and related SAR-specific planning frameworks
- performing Mattson and similar evaluative methods used to guide search decisions
- defining search strategy and search intent
- selecting or prioritizing segments for search
- maintaining general search segment management from a planning perspective
- documenting planning assumptions
- applying behavior-based reasoning to search decisions
- estimating and revising POD
- recommending search assignments for the next operational cycle
- identifying what information gaps matter to the search plan

### Intel Should Continue To Own
These are investigative and intelligence functions that SAR planning should consume, not replace:
- clue intake and validation
- timeline development
- witness and interview handling
- investigative analysis
- fact development around LKP, PLS, and subject movements

### GIS Should Continue To Own
These are mapping and geospatial production responsibilities that should remain outside SAR planning:
- map authoring and editing
- formal segment geometry creation if GIS already owns that workflow
- layers, overlays, and cartographic products
- geospatial analysis tooling that serves the whole incident

### Operations Should Continue To Own
These are execution-side responsibilities that planning should hand off rather than absorb:
- team deployment
- assignment lifecycle execution
- live accountability
- staging and movement status
- non-search operational coordination

### What Search Planning Consumes
Search Planning should take in structured inputs from other modules, including:
- initial intake summary from Initial Response
- validated clues and investigative findings from Intel
- LKP/PLS and timeline refinements from Intel
- map references, segment references, and terrain context from GIS
- team capability and availability context from operations or personnel systems

### What Search Planning Produces
Search Planning should hand off clear outputs rather than just maintain notes.

Primary outputs:
- lost person behavior assessment
- Mattson or equivalent evaluation output
- search strategy summary
- prioritized search segments or areas
- segment management state for planning
- planning assumptions and rationale
- POD estimates and revision notes
- recommended search assignments
- planning questions or information requests for Intel, GIS, or Operations

### Questions Search Planning Should Answer
Search Planning should answer:
- Based on what we know now, where should we search next?
- Why are those areas higher priority than others?
- Which search methods fit the terrain, urgency, and subject profile?
- How effective has our search effort been so far?
- What assumptions are currently driving the plan?
- What new information would materially change the next search cycle?

### Questions Search Planning Should Not Need To Answer Alone
These questions may inform planning, but another module should remain the source of truth:
- Is this clue credible?
- What exactly did the witness say?
- What does the official map product look like?
- Which team is currently checked in at staging?
- Has unit accountability been cleared incident-wide?

### Recommended Ownership Split
- `Initial Response`: initial missing person intake and earliest circumstances
- `Intel`: facts, timeline, witness information, and clue validation
- `GIS`: map products, geometry, and geospatial representation
- `Search Planning`: search prioritization, strategy, POD, and assignment recommendations
- `Search Operations`: field-facing execution of the search plan
- `Search Review`: interpretation of returned search results and planning revision

### Recommended Implementation Posture
When this is eventually built, Search Planning should reference and synthesize records from other modules rather than recreate them locally.

In practice, that likely means:
- linking to Intel-derived facts rather than copying them into SAR-owned records
- linking to GIS segments or map references rather than building a second mapping system
- producing SAR planning records that can be cited by Operations and Review

### 2. Search Operations
Purpose:
Support SAR-specific execution once search assignments are being prepared or actively worked.

What it provides:
- search assignment packaging
- segment-specific execution notes
- team departure and return awareness
- search-specific progress tracking
- segment completion or partial completion capture
- overdue or no-contact visibility for search teams

What this submodule is for:
Once planning has produced search assignments, this submodule supports the search-specific side of execution. It should help teams and leaders understand what was assigned, what search method is expected, what segment conditions matter, and what search-specific results need to come back.

It should support:
- preparing search assignments from planning outputs
- recording search method, segment intent, and hazards
- team check-out and expected return awareness
- recording completed versus partial search coverage
- highlighting overdue or no-contact search teams
- sending search results into review and reassessment

This submodule needs careful scope control. It should not replace broader operations tracking if another module already owns general tasking and live resource status. Its job is to add the SAR-specific execution layer on top of those systems.

Typical outputs:
- search assignment packet or summary
- active search execution view
- overdue search team alerts
- segment completion summaries
- search progress by segment
- search result handoff into the next planning cycle

What it should not own:
- the master operations board
- generic resource status tracking
- personnel accountability for the whole incident
- radio logging
- non-search task execution

## Boundary: Search Operations vs. Operations
This boundary needs to stay explicit so the SAR toolkit adds value without creating a second operations system.

### Search Operations Should Own
These are the search-specific execution concerns that are unique enough to belong in the SAR toolkit:
- converting a search plan into a search-ready assignment package
- attaching search method and search intent to an assignment
- defining segment-specific hazards, terrain notes, and search objectives
- capturing raw field-return information from search teams
- recording what teams report they did, observed, and completed in the field
- capturing the operational inputs that Search Review will later interpret

### Operations / Tasking Should Continue To Own
These are broader incident responsibilities that should stay in the existing operations-oriented modules:
- the incident-wide task board
- general assignment lifecycle management for all mission areas
- global team and resource status
- staging and deployment status across the whole incident
- general accountability and check-in/check-out workflows
- radio traffic logging and communications tracking
- non-search operational tasks

### Shared Workflow Between The Two
The cleanest model is for the systems to cooperate rather than compete.

Recommended flow:
1. SAR Planning creates a recommended search assignment.
2. The broader tasking or operations system owns the official assignment record and deployment lifecycle.
3. Search Operations enriches that assignment with search-specific context.
4. Field updates and team return status may be visible from operations, but SAR captures the search-specific completion picture.
5. SAR Review consumes the returned search results and feeds the next planning cycle.

### SAR-Specific Data Added To An Otherwise General Assignment
If a general assignment already exists elsewhere, SAR should add fields or linked records such as:
- segment identifier
- search method
- search objective
- terrain notes
- search hazards
- expected coverage standard
- raw field return notes
- team-reported completion notes
- notable observations requiring review

### Questions SAR Should Answer That Operations Usually Does Not
Operations may answer "Where is Team 3?" but SAR needs to answer:
- What exactly were they supposed to search?
- What search method was used?
- What search-specific conditions affected effectiveness?
- What raw information came back from the field that planning must now interpret?

### Integration Model Recommendation
The safest architectural direction is:
- one official operations assignment lifecycle
- one SAR-specific execution layer linked to that assignment

That avoids:
- duplicate assignment IDs
- conflicting status values
- teams being "complete" in one place but still "active" in another
- split reporting responsibilities between operations and planning

### Recommended Ownership Split
- `Operations`: who is assigned, deployed, available, overdue, returned
- `Search Operations`: what search was intended and what the field team reports happened
- `Search Review`: what the returned search effort means, how complete coverage really was, and whether re-search or closure is warranted

### Recommended Implementation Posture
When this is eventually built, SAR execution records should preferably reference operations or tasking records rather than replace them.

In practice, that likely means:
- a linked SAR execution record per relevant search assignment
- SAR-specific statuses that describe search completion, not team accountability
- review outputs that feed planning rather than operational dispatch

### 3. Search Review
Purpose:
Support reassessment after assignments complete and prepare the next planning cycle.

What it provides:
- completed search summaries
- coverage gaps
- unresolved clues
- updated POD inputs
- recommendations for re-tasking

What this submodule is for:
SAR work is cyclical. Teams go out, search work gets completed, and then leadership needs to decide what those results mean. Search Review is where completed effort is interpreted, not just recorded.

It should support:
- reviewing assignment outcomes
- noting what areas remain weakly covered
- identifying whether clues were resolved or still open
- folding operational results back into planning
- deciding whether to repeat, expand, narrow, or redirect search effort

This is where the toolkit should help answer:
- What did we actually learn from the last round of searching?
- Which assumptions held up?
- Which areas still need attention?
- What should we do next?

Typical outputs:
- reassessment summary
- remaining coverage gap list
- updated planning recommendations
- next operational period priorities

What it should not own:
- raw clue intake
- generic after-action documentation
- broad incident reporting already handled elsewhere

## Recommended First-Release Submodules
For an MVP, I’d recommend the SAR toolkit start with three submodules:
- Search Planning
- Search Operations
- Search Review

Search Review can initially be lightweight and live inside the planning experience if needed.

## Submodule Responsibilities At A Glance
- `Search Planning`: decide where resources should go and why
- `Search Operations`: carry search plans into field execution without replacing broader operations systems
- `Search Review`: decide what the completed work means and what happens next

## Recommended Information Architecture
The SAR toolkit should be organized around the proposed submodules above, with one home screen plus a small set of purpose-built work areas.

### 1. Planning
- Subject Profile / Behavior Profile
- Search Strategy Summary
- Probability of Detection
- Search Segment Manager

Inputs from other modules:
- Initial Response missing person intake
- Intel timeline, clues, and investigation outputs
- GIS map references

### 2. Execution
- Search Assignment Planner
- Search Execution Tracker
- segment-specific field notes

Shared boundary:
Generic tasking and broad operations tracking should remain in the appropriate operations modules.

### 3. Review
- search progress summary
- coverage gaps
- unresolved search questions
- recommended next actions

## Proposed Workflow
1. Receive intake and investigative inputs from Initial Response and Intel.
2. Build the initial search strategy and prioritize segments.
3. Prepare search assignments and support field execution.
4. Review returned search results and coverage.
5. Update planning assumptions, POD, and next assignments.

## Screen-Level Design Notes

### Subject Profile / Behavior Profile
Purpose:
Support search planning by organizing behavior and risk factors.

Key sections:
- subject category
- experience level outdoors or in environment
- attraction and aversion factors
- likely travel patterns
- survivability concerns
- planning assumptions

Design notes:
- this should support planning judgment, not pretend certainty
- keep behavior guidance separate from confirmed facts from Intel

### Search Strategy Summary
Purpose:
Provide the planning narrative that explains why teams are being sent where they are.

Key sections:
- operational objectives
- priority search areas
- exclusions and completed work
- risk considerations
- assumptions
- planning rationale
- next planning cycle notes

### Probability of Detection
Purpose:
Support planning and reassessment of search effectiveness.

Key inputs:
- segment
- terrain or environment
- search method
- team capability
- time spent
- visibility and weather factors
- estimated POD

Design notes:
- begin with a lightweight calculator
- allow notes explaining why a value changed
- show prior estimates for comparison

### Search Segment Manager
Purpose:
Maintain the list of searchable areas and their operational status.

Key fields:
- segment identifier
- description
- priority
- terrain type
- hazards
- accessibility
- assigned team
- search status
- POD history

Statuses:
- unassigned
- planned
- assigned for search
- partially searched
- search complete
- deferred

### Search Assignment Planner
Purpose:
Package planning outputs into clear search assignments.

Key fields:
- assignment number
- team
- leader
- segment or task
- departure time
- due back time
- radio channel
- safety notes
- search method
- completion criteria

Design notes:
- this should complement, not replace, the broader tasking system
- the SAR-specific value is in segment intent, search method, and expected search return

### Search Execution Tracker
Purpose:
Track SAR-specific execution progress after teams are deployed.

Key elements:
- active search teams
- expected return times
- segment progress
- partial completion notes
- notable search outcomes
- overdue or no-contact flags

## Core Records
- search segment record
- search assignment record
- POD estimate record
- search review record

## Standardized SAR Record Concepts
These should be reused where possible so the toolkit feels consistent:
- `status`
- `priority`
- `assigned_to`
- `location`
- `time_recorded`
- `search_method`
- `segment_id`
- `coverage_status`
- `result_summary`
- `notes`

## Command Briefing Outputs
The SAR toolkit should eventually be able to support:
- search strategy briefing
- active search assignment list
- search progress by segment
- overdue search team check list
- next operational period planning notes

## Important Integrations
- command objectives
- tasking and assignments
- personnel and team catalogs
- communications plan
- GIS and mapping
- Intel outputs
- Initial Response intake summary
- ICS forms where applicable

## UX Priorities
- fast entry under pressure
- strong timeline display
- clear map-linked context
- low-friction updates from field teams
- obvious distinction between confirmed facts, assumptions, and planning judgments

## Open Design Questions
- How thin or rich should Search Operations be if general tasking already exists elsewhere?
- Should POD be a lightweight calculator, a full planning worksheet, or both?
- How much of search segmentation belongs in the SAR toolkit versus GIS?
- Should Search Review be its own submodule or a mode inside Search Planning?
- What is the minimum viable SAR toolkit for first release?

## Suggested MVP
- Search Strategy Summary
- POD panel
- Search Assignment Planner
- Search Review

## Suggested Build Order
1. Search Planning
2. Search Assignment Planner
3. Search Review
4. Search Execution Tracker
5. POD Calculator

## Decisions I’d Recommend For Now
- Treat SAR as its own root-level toolkit under `modules/sartoolkit`.
- Keep the first release centered on search planning, SAR-specific execution support, and reassessment.
- Let Initial Response own intake and Intel own timeline/investigation/clues.
- Model search segments, search assignments, POD estimates, and review outputs as distinct records.
- Treat behavior profiling and POD as decision-support tools, not authoritative truth.
