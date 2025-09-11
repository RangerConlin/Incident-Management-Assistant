"""Medical & Safety module exposing panel factory helpers."""


def get_dashboard_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.safety_dashboard_panel import SafetyDashboardPanel
    return SafetyDashboardPanel()


def get_208_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.safety_message_panel import SafetyMessagePanel
    return SafetyMessagePanel()


def get_215A_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.iap_safety_analysis_panel import IapSafetyAnalysisPanel
    return IapSafetyAnalysisPanel()


def get_hazard_log_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.hazard_log_panel import HazardLogPanel
    return HazardLogPanel()


def get_briefings_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.safety_briefings_panel import SafetyBriefingsPanel
    return SafetyBriefingsPanel()


def get_incidents_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.safety_incidents_panel import SafetyIncidentsPanel
    return SafetyIncidentsPanel()


def get_ppe_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.ppe_advisories_panel import PpeAdvisoriesPanel
    return PpeAdvisoriesPanel()


def get_cap_forms_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.cap_forms_panel import CapFormsPanel
    return CapFormsPanel()


def get_cap_form_editor_panel(*_args, **_kwargs):
    from modules.medical_safety.panels.cap_form_editor_panel import CapFormEditorPanel
    return CapFormEditorPanel()
