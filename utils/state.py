
# utils/state.py

class AppState:
    _active_incident_number = None
    _active_op_period_id = None
    _active_user_id = None
    _active_user_role = None
    _active_session_id = None

    @classmethod
    def set_active_incident(cls, incident_number):
        print(f"[state] set_active_incident({incident_number}) (from {getattr(cls, '_active_incident_number', None)})")
        cls._active_incident_number = incident_number
        # Keep incident_context (DB path provider) in sync
        try:
            from utils import incident_context
            incident_context.set_active_incident(incident_number)  # type: ignore[arg-type]
        except Exception as e:
            # Non-fatal: selection UI should still work; DB-backed views may error until set
            print(f"[state] warning: failed to sync incident_context: {e}")
        # Emit Qt signal for interested panels
        try:
            from utils.app_signals import app_signals
            if incident_number is not None:
                app_signals.incidentChanged.emit(str(incident_number))
        except Exception as e:
            print(f"[state] warning: failed to emit incidentChanged: {e}")

    @classmethod
    def get_active_incident(cls):
        print(f"[state] get_active_incident -> {getattr(cls, '_active_incident_number', None)}")
        return cls._active_incident_number

    @classmethod
    def set_active_op_period(cls, op_period_id):
        cls._active_op_period_id = op_period_id
        try:
            from utils.app_signals import app_signals
            app_signals.opPeriodChanged.emit(op_period_id)
        except Exception:
            pass

    @classmethod
    def get_active_op_period(cls):
        return cls._active_op_period_id

    @classmethod
    def set_active_user_id(cls, user_id):
        cls._active_user_id = user_id
        try:
            from utils.app_signals import app_signals
            app_signals.userChanged.emit(cls._active_user_id, cls._active_user_role)
        except Exception:
            pass

    @classmethod
    def get_active_user_id(cls):
        return cls._active_user_id

    @classmethod
    def set_active_user_role(cls, user_role):
        cls._active_user_role = user_role
        try:
            from utils.app_signals import app_signals
            app_signals.userChanged.emit(cls._active_user_id, cls._active_user_role)
        except Exception:
            pass

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
