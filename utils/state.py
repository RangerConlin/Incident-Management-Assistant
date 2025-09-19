
# utils/state.py

import logging


logger = logging.getLogger(__name__)


class AppState:
    _active_incident_number = None
    _active_op_period_id = None
    _active_user_id = None
    _active_user_role = None
    _active_session_id = None

    @classmethod
    def set_active_incident(cls, incident_number):
        logger.debug(
            "[state] set_active_incident(%s) (from %s)",
            incident_number,
            getattr(cls, "_active_incident_number", None),
        )
        cls._active_incident_number = incident_number
        normalized_incident_id = None if incident_number is None else str(incident_number)
        # Keep incident_context (DB path provider) in sync
        try:
            from utils import incident_context
            incident_context.set_active_incident(normalized_incident_id)  # type: ignore[arg-type]
        except Exception as e:
            # Non-fatal: selection UI should still work; DB-backed views may error until set
            logger.warning("[state] failed to sync incident_context: %s", e)
        # Keep incident_db (legacy SQLite helper) in sync
        try:
            from utils import incident_db

            incident_db.set_active_incident_id(normalized_incident_id)
        except Exception as e:
            logger.warning("[state] failed to sync incident_db: %s", e)
        # Emit Qt signal for interested panels
        try:
            from utils.app_signals import app_signals
            if normalized_incident_id is not None:
                app_signals.incidentChanged.emit(normalized_incident_id)
        except Exception as e:
            logger.warning("[state] failed to emit incidentChanged: %s", e)

    @classmethod
    def get_active_incident(cls):
        logger.debug(
            "[state] get_active_incident -> %s",
            getattr(cls, "_active_incident_number", None),
        )
        return cls._active_incident_number

    @classmethod
    def set_active_op_period(cls, op_period_id):
        cls._active_op_period_id = op_period_id
        try:
            from utils.app_signals import app_signals
            app_signals.opPeriodChanged.emit(op_period_id)
        except Exception as e:
            logger.warning("[state] failed to emit opPeriodChanged: %s", e)

    @classmethod
    def get_active_op_period(cls):
        return cls._active_op_period_id

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

    # Aliases for legacy names
    @classmethod
    def set_active_op_period_id(cls, op_period_id):
        cls.set_active_op_period(op_period_id)

    @classmethod
    def get_active_op_period_id(cls):
        return cls.get_active_op_period()
