"""
Push notification send utility (Firebase Cloud Messaging).

Infrastructure only — looks up every registered token for a person and
sends via the Firebase Admin SDK, pruning tokens that come back
UNREGISTERED. Product trigger points (when to call this) are a separate,
later decision; nothing in this codebase calls send_to_person yet.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from firebase_admin import messaging

from sarapp_db.mongo.collection_names import MasterCollections
from sarapp_db.mongo.database_manager import get_master_db
from sarapp_db.services.firebase_client import get_firebase_app

logger = logging.getLogger(__name__)


def _push_tokens_col():
    return get_master_db()[MasterCollections.PUSH_TOKENS]


def send_to_person(
    person_record: int,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Send a push notification to every device registered for a person.

    Returns {"attempted": int, "sent": int, "pruned": list[str]}.

    Raises FirebaseNotConfiguredError (propagated from get_firebase_app) if
    the Admin SDK isn't configured — a deployment error the caller should
    surface. Per-token send failures are caught and logged individually so
    one bad token doesn't block the rest.
    """
    get_firebase_app()

    tokens_col = _push_tokens_col()
    docs = list(tokens_col.find({"person_record": person_record}))
    summary: dict[str, Any] = {"attempted": len(docs), "sent": 0, "pruned": []}

    for doc in docs:
        token = doc["token"]
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
        )
        try:
            messaging.send(message)
            summary["sent"] += 1
        except messaging.UnregisteredError:
            tokens_col.delete_one({"token": token})
            summary["pruned"].append(token)
        except Exception:
            logger.exception(
                "FCM send failed for token=%s person_record=%s", token, person_record
            )

    return summary
