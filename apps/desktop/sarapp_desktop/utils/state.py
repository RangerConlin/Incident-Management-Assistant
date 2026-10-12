
# utils/state.py

import logging


logger = logging.getLogger(__name__)


class AppState:
    _active_incident_number = None
    _active_op_period_id = None
    _active_user_id = None
    _active_user_display = None
    _active_user_role = None
    _active_session_id = None
    _active_api_session_id = None

    @classmethod
    def set_active_incident(cls, incident_number):
        logger.debug(
            "[state] set_active_incident(%s) (from %s)",
            incident_number,
            getattr(cls, "_active_incident_number", None),
        )
        cls._active_incident_number = incident_number
        normalized_incident_id = None if incident_number is None else str(incident_number)
        # Persist the last selected incident for startup behavior features
        try:
            if normalized_incident_id is not None:
                # Lazy import to avoid any heavy deps on import time
                from utils.settingsmanager import SettingsManager  # type: ignore
                SettingsManager().set("""lastIncidentNumber""", normalized_incident_id)
        except Exception as e:
            logger.warning("""[state] failed to persist lastIncidentNumber: %s""", e)
        # Keep incident_context (DB path provider) in sync
        try:
            from utils import incident_context
            incident_context.set_active_incident(normalized_incident_id)  # type: ignore[arg-type]
        except Exception as e:
            # Non-fatal: selection UI should still work; DB-backed views may error until set
            logger.warning("[state] failed to sync incident_context: %s", e)
        # Emit Qt signal for interested panels
        try:
            from utils.app_signals import app_signals
            if normalized_incident_id is not None:
                app_signals.incidentChanged.emit(normalized_incident_id)
        except Exception as e:
            logger.warning("[state] failed to emit incidentChanged: %s", e)
        # Reload IncidentCache snapshot and reconnect its WebSocket for the new incident
        try:
            from utils import incident_cache_loader
            incident_cache_loader.activate_incident(normalized_incident_id)
        except Exception as e:
            logger.warning("[state] failed to activate IncidentCache: %s", e)
        # Catch up this incident's personnel copies against the master roster
        # (push-down sync on edit only reaches the incident active at the time)
        try:
            if normalized_incident_id is not None:
                from utils.api_client import api_client
                api_client.post(
                    f"/api/incidents/{normalized_incident_id}/operations/personnel/sync-from-master"
                )
        except Exception as e:
            logger.warning("[state] failed to sync incident personnel from master: %s", e)

    @classmethod
    def get_active_incident(cls):
        return cls._active_incident_number

    @classmethod
    def set_active_op_period(cls, op_period_id):
        """Store the active OP identifier.
    
        Accepts either a plain int (OP number, for backward compatibility)
        or a dict with keys: number, id, status, start_time, end_time.
        """
        cls._active_op_period_id = op_period_id
        payload = op_period_id
        if isinstance(op_period_id, dict):
            payload = dict(op_period_id)
        elif isinstance(op_period_id, int):
            payload = {"number": op_period_id, "id": None, "status": "Active"}
        try:
            from utils.app_signals import app_signals
            app_signals.opPeriodChanged.emit(payload)
        except Exception as e:
            logger.warning("[state] failed to emit opPeriodChanged: %s", e)

    @classmethod
    def get_active_op_period(cls):
        """Return the stored active OP value (int or dict, depending on caller)."""
        return cls._active_op_period_id

    @classmethod
    def get_active_op_period_dict(cls) -> dict | None:
        """Return a dict representation of the active OP, or None."""
        from typing import Mapping
        value = cls._active_op_period_id
        if value is None:
            return None
        if isinstance(value, Mapping):
            return dict(value)
        # Legacy: plain int
        return {"number": int(value), "id": None, "status": "Active"}

    @classmethod
    def set_active_user_id(cls, user_id):
        cls._active_user_id = user_id
        try:
            from utils.app_signals import app_signals
            app_signals.userChanged.emit(
                cls._active_user_id, cls._active_user_role
            )
        except Exception as e:
            logger.warning("[state] failed to emit userChanged: %s", e)

    @classmethod
    def get_active_user_id(cls):
        return cls._active_user_id

    @classmethod
    def set_active_user_display(cls, user_display):
        """Store the human-readable person_id/username for UI display.

        `active_user_id` is the internal person_record used for DB writes
        and audit trails; it must never be shown to the user. This holds
        the visible login id (e.g. the value they typed) for the title
        bar / status bar instead.
        """
        cls._active_user_display = user_display

    @classmethod
    def get_active_user_display(cls):
        return cls._active_user_display

    @classmethod
    def set_active_user_role(cls, user_role):
        cls._active_user_role = user_role
        try:
            from utils.app_signals import app_signals
            app_signals.userChanged.emit(
                cls._active_user_id, cls._active_user_role
            )
        except Exception as e:
            logger.warning("[state] failed to emit userChanged: %s", e)

    @classmethod
    def get_active_user_role(cls):
        return cls._active_user_role

    @classmethod
    def set_active_session_id(cls, session_id):
        cls._active_session_id = session_id

    @classmethod
    def get_active_session_id(cls):
        return cls._active_session_id

    @classmethod
    def set_active_api_session_id(cls, session_id):
        cls._active_api_session_id = session_id

    @classmethod
    def get_active_api_session_id(cls):
        return cls._active_api_session_id

    # Aliases for legacy names
    @classmethod
    def set_active_op_period_id(cls, op_period_id):
        cls.set_active_op_period(op_period_id)

    @classmethod
    def get_active_op_period_id(cls):
        return cls.get_active_op_period()
