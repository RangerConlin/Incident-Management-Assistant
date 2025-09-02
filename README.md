# Incident Management Assistant

This project provides tooling and user interface components for incident management workflows.

## Team Communication Timers

Radio traffic can be logged using the communications module. When a radio log entry references a known team in the `sender` or `recipient` fields, that team's `last_comm_ping` timestamp is updated. This timer allows operators to track when each team last made contact over the radio.

The helper `log_radio_entry` in `modules/communications/radio_log.py` persists a message and performs the timer update automatically.
