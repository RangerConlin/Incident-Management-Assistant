"""Background loop draining the local sync outbox and pulling down changes
made centrally. Same daemon-thread shape as `lan_server/
notification_trigger_loop.py::NotificationTriggerLoop` — owned/started/
stopped by each server runtime's manager, not a FastAPI lifespan hook.

No-ops entirely (does nothing each tick) when `SARAPP_CENTRAL_MASTER_URL`
isn't set, so starting this loop unconditionally on every server runtime is
safe and costs nothing for deployments that haven't opted into central sync.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class CentralSyncLoop:
    def __init__(self, *, interval_seconds: float | None = None) -> None:
        from sarapp_db.sync import config

        self.interval_seconds = interval_seconds or config.sync_interval_seconds()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="sarapp-central-sync-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                run_one_tick()
            except Exception:
                logger.exception("Central sync loop tick failed.")
            self._stop_event.wait(self.interval_seconds)


def run_one_tick() -> None:
    """One drain-outbox-then-pull-changes pass. Exposed as a standalone
    function (not just a loop-internal method) so tests and a manual
    "sync now" admin action can trigger exactly one pass deterministically.
    """
    from sarapp_db.sync import config

    if not config.sync_enabled():
        return
    drain_outbox()
    for collection in config.SYNCABLE_MASTER_COLLECTIONS:
        pull_and_apply(collection)


def drain_outbox(*, local_master_db=None) -> None:
    """`local_master_db` is injectable for tests, which need it to mean
    something other than whatever `get_master_db()` resolves to in-process
    (e.g. a test simulating both the local server and the central database
    in one process can't disambiguate the two through one env-var-driven
    function). Production code always calls this with no arguments."""
    from sarapp_db.mongo.database_manager import get_master_db, get_system_db
    from sarapp_db.sync import config, outbox
    from sarapp_db.sync.central_client import push_delete, push_one

    system_db = get_system_db()
    master_db = local_master_db if local_master_db is not None else get_master_db()
    base_url, token = config.central_master_url(), config.sync_token()

    for entry in outbox.list_pending(system_db):
        collection, doc_id = entry["collection"], entry["doc_id"]

        if entry.get("op") == "delete":
            if push_delete(base_url, token, collection=collection, doc_id=doc_id, deleted_at=entry.get("deleted_at")):
                outbox.mark_sent(system_db, entry["_id"])
            else:
                outbox.record_failure(system_db, entry["_id"], "delete push failed")
            continue

        doc = master_db[collection].find_one({"_id": doc_id})
        if doc is None:
            # Document was deleted locally since being queued (and that
            # delete queued its own separate "delete" outbox entry) —
            # nothing left to send for this now-superseded "upsert" entry.
            outbox.mark_sent(system_db, entry["_id"])
            continue
        if push_one(base_url, token, collection=collection, doc=doc):
            outbox.mark_sent(system_db, entry["_id"])
        else:
            outbox.record_failure(system_db, entry["_id"], "push failed")


def pull_and_apply(collection: str, *, local_master_db=None) -> None:
    """See `drain_outbox` for why `local_master_db` is injectable."""
    from sarapp_db.mongo.database_manager import get_master_db, get_system_db
    from sarapp_db.sync import checkpoint, config
    from sarapp_db.sync.central_client import pull_since
    from sarapp_db.sync.relay import apply_incoming

    system_db = get_system_db()
    since = checkpoint.get_last_pulled_at(system_db, collection)
    docs = pull_since(config.central_master_url(), config.sync_token(), collection=collection, since=since)
    if docs is None:
        return  # pull failed — leave checkpoint alone, retry next tick.

    latest = since
    master_db = local_master_db if local_master_db is not None else get_master_db()
    for doc in docs:
        apply_incoming(master_db, collection, doc)
        updated_at = str(doc.get("updated_at") or "")
        if latest is None or updated_at > latest:
            latest = updated_at
    if latest and latest != since:
        checkpoint.set_last_pulled_at(system_db, collection, latest)
