# Product Design Overview

Incident-Management-Assistant is a desktop-first incident management suite with a growing mobile companion app and web client. These documents are a current-state design map, not a finished product narrative.

The purpose of this document set is to help us answer a few practical questions:

- What features exist right now?
- Which features are usable, partial, rough, duplicated, or broken?
- Which workflows cross module boundaries?
- Where do desktop and mobile overlap?
- What should be redesigned or standardized next?

## Product Surfaces

### Desktop

The desktop app is the primary command-post surface. It contains the broadest feature set and should be treated as the main source for current module capability.

### Mobile

The mobile app is a companion surface. It should be documented by what it can do today, what field workflows it is meant to support, and where it depends on desktop-created incident data.

### Web

The web client is a browser-based client surface. It can be documented in this set once its module coverage is being reviewed alongside desktop and mobile.

## Design Review Principles

- Current state comes first.
- Build status should be explicit.
- Future design ideas should be marked as future design ideas.
- Intermodule links should be described as workflows, not code dependencies.
- UI standardization should be based on real screens, not abstract preferences.

## Current Documentation Focus

The first pass through these documents should capture the current state:

- What users can do today.
- Which workflows appear complete.
- Which workflows are present but unfinished.
- Where mobile and desktop experiences connect.
- Where UI inconsistency slows users down.
- Which design questions should be settled before deeper development resumes.
