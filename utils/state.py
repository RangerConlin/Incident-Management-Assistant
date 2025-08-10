
# utils/state.py

class AppState:
    _active_mission_id = None
    _active_op_period_id = None
    _active_user_id = None
    _active_user_role = None

    @classmethod
    def set_active_mission(cls, mission_id):
        cls._active_mission_id = mission_id

    @classmethod
    def get_active_mission(cls):
        return cls._active_mission_id

    @classmethod
    def set_active_op_period(cls, op_period_id):
        cls._active_op_period_id = op_period_id

    @classmethod
    def get_active_op_period(cls):
        return cls._active_op_period_id

    @classmethod
    def set_active_user_id(cls, user_id):
        cls._active_user_id = user_id

    @classmethod
    def get_active_user_id(cls):
        return cls._active_user_id

    @classmethod
    def set_active_user_role(cls, user_role):
        cls._active_user_role = user_role

    @classmethod
    def get_active_user_role(cls):
        return cls._active_user_role
