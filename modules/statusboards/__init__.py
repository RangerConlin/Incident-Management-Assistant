"""Status Boards — shared client-side join/cache layer for status board UI.

Boards (Team Status, Task Status, etc.) should be dumb: they hold no fetch
or join logic of their own. They read current rows from a "desk" in this
module and re-render when the desk tells them something changed. Desks are
the only thing that reads `utils.incident_cache` for this domain; they exist
to replicate, client-side, the same row-shaping a server endpoint used to do
on every request.
"""
