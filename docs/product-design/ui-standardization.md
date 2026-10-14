# UI Standardization

This document tracks UI consistency issues and standardization decisions. It should start as an audit of existing screens, then become the design reference for future UI cleanup.

## Goals

- Record where tables, forms, dialogs, dashboards, and status indicators differ today.
- Identify which existing screens should become pattern references.
- Decide which patterns should be standardized before new features expand.
- Separate desktop standardization from mobile standardization where needed.

## Areas To Audit And Standardize

### Tables

- Column resizing
- Sorting and filtering
- Selected-row appearance
- Empty states
- Row-level actions
- Timestamp display
- Status display

### Forms

- Required field indicators
- Validation behavior
- Save/cancel placement
- Dirty-state handling
- Section grouping
- Read-only vs editable views

### Dialogs

- Confirmation language
- Destructive-action handling
- Error messages
- Success feedback
- Wizard-style flows where a task has multiple steps

### Dashboards

- Summary cards
- Status counts
- Alerts or attention-needed items
- Navigation from summary to detail

### Status Indicators

- Shared labels
- Shared color meaning
- Badge and chip style
- Legend behavior
- Theme support

### Mobile Patterns

- Connection state
- Current incident identity
- Check-in state
- Location-sharing state
- Assignment or task state
- Offline or poor-network messaging

## First-Pass Audit Questions

- Which modules already feel polished and should become pattern references?
- Which modules have tables that behave differently from the rest of the app?
- Which workflows use inconsistent button labels or action placement?
- Which statuses mean similar things but use different labels?
- Which screens are too dense, too sparse, or too dependent on user memory?
