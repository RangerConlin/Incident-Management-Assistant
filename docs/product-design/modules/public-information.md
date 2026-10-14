# Public Information

## Purpose

Draft, review, approve, publish, and archive public-facing incident information.

Public Information is the workspace for PIO releases, messaging, media coordination concepts, and approved public statements.

## Users

- Public Information Officer and PIO staff.
- Command staff approving releases.
- Liaison/external agency users coordinating joint messages.
- Planning/operations staff providing facts for public release.

## Current Features

- Desktop Public Information window with overview and section buttons.
- Section window pattern for opening Public Information subsections independently.
- Overview panel exists.
- Messages / Releases section opens a Release Manager panel.
- Release editor dialog supports release type, title, subtitle, dateline, body, next update, boilerplate, preview, close, and lifecycle controls.
- Release lifecycle supports states and actions such as draft/new, review, approved, published, archived, approve, publish/release, return/revise, and archive.
- Release preview widget/service exists.
- Public-information constants include release types, talking point statuses, media/contact/public-message vocabulary, and templates.

## Core Workflows

- Open the Public Information workspace.
- Review PIO overview.
- Create or edit a public release/message.
- Preview release content.
- Move a release through approval, publication, revision, archive, or related lifecycle states.
- Use templates or release types to standardize public messaging.

## Build Status

Partial.

The release/message workflow has real desktop UI and a lifecycle model. Public Information is not just a placeholder. However, the broader PIO module appears less complete than command, logistics, or tasking. The overview and release manager exist, while other PIO concepts such as media log, talking points, inquiries, distribution, monitoring, and joint-agency coordination need verification or future buildout.

No dedicated mobile Public Information workspace was identified.

## Screens And UI Inventory

- Desktop: Public Information main window.
- Desktop: PIO Overview panel.
- Desktop: Messages / Releases section.
- Desktop: Release Manager panel.
- Desktop: Release Editor dialog.
- Desktop: Release Preview widget/dialog.
- Desktop: Release Lifecycle panel.
- Desktop: dashboard/message/simple panels for supporting PIO sections.
- Mobile: no dedicated public information screen identified.

## Links To Other Modules

- Command: command approval is central to public-release lifecycle.
- Planning: SITREPs, operational summaries, and planning products may feed releasable facts.
- Intel: subject/contact/witness information may need privacy review before release.
- Safety: safety messages may become public-facing updates.
- Communications: release distribution and message coordination overlap with communications channels.
- Forms/Documentation: releases are incident documentation outputs.

## Desktop Experience

Desktop is the only current PIO authoring surface.

The experience centers on releases/messages. The release editor has a clear writing-and-preview workflow with lifecycle controls. The main Public Information window acts as a launcher for PIO subsections.

## Mobile Experience

No mobile PIO workspace was identified.

Field users may indirectly contribute facts through tasks, logs, messages, intel, and SITREPs, but mobile does not appear to support PIO drafting, review, or approval.

## Current Gaps

- Public Information appears release-focused; full PIO operations need design.
- No mobile PIO workflow.
- Approval authority, reviewer roles, and publication destinations need clearer product design.
- Media log, public inquiries, rumor control, talking points, and joint release workflows need verification/buildout.
- Relationship between SITREP facts and public release facts is not yet explicit.

## Design Questions

- What is the canonical lifecycle of a public release?
- Who can draft, review, approve, publish, revise, or archive a release?
- Should releases be linked to SITREPs, tasks, media inquiries, public tips, or command approvals?
- What public information records need privacy/sensitivity checks?
- Which channels are supported: email, web, print, social, agency partner, press briefing?

## Future Design Ideas

- PIO dashboard with draft releases, pending approvals, published releases, inquiries, and talking points.
- Public release packet with approvals, distribution record, and source facts.
- Talking-points manager tied to approved-to-say / do-not-release status.
- Media inquiry tracker with due dates and assigned responder.
- Joint-agency review workflow.
