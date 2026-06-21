# ===== Part 1: Imports & Logging ============================================
import json
import os
import re
import sys
import logging
from functools import lru_cache
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,

    QMenu,
    QLabel,
    QWidget,
    QVBoxLayout,
    QMessageBox,
    QDialog,
    QListWidget,
    QPushButton,
    QHBoxLayout,
    QInputDialog,
    QFileDialog,
)
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QPalette, QColor
from PySide6.QtCore import Qt, QUrl, QSettings, QTimer, QObject, QEvent
from PySide6QtAds import (
    CDockManager,
    CDockWidget,
    LeftDockWidgetArea,
    RightDockWidgetArea,
    TopDockWidgetArea,
    BottomDockWidgetArea,
    CenterDockWidgetArea,
)


# Respect saved dock layouts (ADS perspectives) across sessions
# Set to True only for one-off debugging to reset layout on startup.
FORCE_DEFAULT_LAYOUT = False

# ==== DEBUG LOGIN BYPASS (set to True to skip login) ====
DEBUG_BYPASS_LOGIN = False  # <--- Toggle this to True to skip login dialog
DEBUG_INCIDENT_ID = "2025-FAIR"
DEBUG_USER_ID = "405021"
DEBUG_ROLE = "Incident Commander"
# =========================================================


from utils.state import AppState
from bridge.settings_bridge import SettingsBridge
from utils.settingsmanager import SettingsManager
from bridge.catalog_bridge import CatalogBridge
from bridge.incident_bridge import IncidentBridge
from models.sqlite_table_model import SqliteTableModel
# 'os' imported earlier for env setup
from utils.theme_manager import ThemeManager
from bridge.theme_bridge import ThemeBridge
from styles.qss_helpers import global_qss, ads_qss
from utils.audit import fetch_last_audit_rows, write_audit
from utils.session import end_session
from utils.constants import TEAM_STATUSES
from notifications.services import get_notifier
from ui.settings import SettingsWindow
from utils.profile_manager import profile_manager, ProfileMeta

try:
    from modules.ui_customization import (
        UICustomizationRepository,
        services as ui_customization_services,
        get_layout_manager_panel,
        get_dashboard_designer_panel,
        get_theme_editor_panel,
    )
except Exception:  # pragma: no cover - customization optional at runtime
    UICustomizationRepository = None  # type: ignore[assignment]
    ui_customization_services = None  # type: ignore[assignment]
    get_layout_manager_panel = None  # type: ignore[assignment]
    get_dashboard_designer_panel = None  # type: ignore[assignment]
    get_theme_editor_panel = None  # type: ignore[assignment]

# Configure basic logging early
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Development mode toggle (prevents NameError later);
# enable with env var IMA_DEV_MODE=true/1/on
DEV_MODE = str(os.getenv("IMA_DEV_MODE", "")).strip().lower() in {"1", "true", "yes", "on"}


_SIZE_RE = re.compile(r"\s+\d+×\d+$")
_orig_set_window_title = QWidget.setWindowTitle


def _set_window_title_with_size(widget: QWidget, title: str) -> None:
    """Store clean base title and render it with current window dimensions."""
    base = _SIZE_RE.sub("", title)
    widget.__dict__["_title_base"] = base
    w, h = widget.width(), widget.height()
    _orig_set_window_title(widget, f"{base}  {w}×{h}" if w and h else base)


def _patch_set_window_title() -> None:
    """Override setWindowTitle on QWidget so the base title is always stored."""
    def setWindowTitle(self, title: str) -> None:  # noqa: N802
        _set_window_title_with_size(self, title)

    QWidget.setWindowTitle = setWindowTitle


_patch_set_window_title()


class _WindowSizeTitleFilter(QObject):
    """Application-level event filter: updates title bar size on every top-level resize."""

    def eventFilter(self, obj, event) -> bool:
        if (
            event.type() == QEvent.Type.Resize
            and isinstance(obj, QWidget)
            and obj.isWindow()
        ):
            base = obj.__dict__.get("_title_base")
            if not base:
                # Title was set by C++ (e.g. ADS floating container) — read and store it now
                raw = obj.windowTitle()
                if raw:
                    base = _SIZE_RE.sub("", raw)
                    obj.__dict__["_title_base"] = base
            if base:
                _orig_set_window_title(obj, f"{base}  {obj.width()}×{obj.height()}")
        return False


def _get_incident_by_number(number: str | None) -> dict | None:
    """Look up a single incident by its number via the API. Returns None on miss."""
    if not number:
        return None
    try:
        from utils.api_client import api_client
        results = api_client.get("/api/incidents", params={"number": str(number)}) or []
        return results[0] if results else None
    except Exception:
        return None


@lru_cache(maxsize=1)
def _incident_type_sets() -> tuple[set[str], set[str]]:
    """Return empty sets — classification falls through to keyword detection."""
    return set(), set()


def _classify_incident_category(incident: Optional[dict]) -> Optional[str]:
    """Map an incident record to a toolkit category."""
    if not incident:
        return None
    raw_type = incident.get("type")
    if raw_type is None:
        return None
    type_name = str(raw_type).strip()
    if not type_name:
        return None
    lowered = type_name.lower()
    planned_types, sar_types = _incident_type_sets()
    if lowered in planned_types:
        return "planned"
    if lowered in sar_types:
        return "sar"
    planned_keywords = (
        "planned",
        "event",
        "parade",
        "festival",
        "fair",
        "concert",
        "marathon",
        "race",
        "demonstration",
        "rally",
        "show",
        "exercise",
        "drill",
        "clinic",
    )
    if any(keyword in lowered for keyword in planned_keywords):
        return "planned"
    if any(keyword in lowered for keyword in ("missing", "sar", "search", "elt")):
        return "sar"
    return "disaster"


# ===== Part 2: Main Window & Physical Menus (visible UI only) ===============
class MainWindow(QMainWindow):
    """
    Menu-first structure. Every visible menu item has a corresponding handler method,
    and ALL handlers follow the same pattern:
      - import module
      - incident_id = AppState.get_active_incident()
      - panel = module.get_*_panel(incident_id)
      - self._open_dock_widget(panel, title="...")
    Placeholders are fine if a real module/factory doesn't exist yet.
    """
    def __init__(self, settings_manager: SettingsManager | None = None,
                 settings_bridge: SettingsBridge | None = None):
        super().__init__()
        self._ems_window = None
        self._settings_window = None
        # Theme wiring is applied after settings bridge is available

        if settings_manager is None:
            settings_manager = SettingsManager()
        if settings_bridge is None:
            settings_bridge = SettingsBridge(settings_manager)
        self.settings_manager = settings_manager
        self.settings_bridge = settings_bridge

        self.customization_repo = None
        if UICustomizationRepository is not None:
            try:
                self.customization_repo = UICustomizationRepository()
            except Exception as exc:
                logger.warning("Failed to initialize customization repository: %s", exc)

        # Initialize theme manager/bridge using persisted setting
        try:
            app = QApplication.instance()
            saved_theme = str(self.settings_bridge.getSetting('themeName') or 'system').lower()
            if saved_theme == 'system':
                from styles.profiles import get_profile_name
                saved_theme = get_profile_name()
            elif saved_theme not in {"light", "dark"}:
                saved_theme = "light"
            self.theme_manager = ThemeManager(app, initial_theme=saved_theme)
            self.theme_bridge = ThemeBridge(self.theme_manager.tokens())
            # Apply initial QSS derived from tokens
            if app is not None:
                app.setStyleSheet(global_qss(self.theme_manager.tokens()))
            # Keep QSS and legacy UI bridge in sync with theme changes
            self.theme_manager.themeChanged.connect(lambda _:
                (self.theme_bridge.updateTokens(self.theme_manager.tokens()),
                 app.setStyleSheet(global_qss(self.theme_manager.tokens())) if app is not None else None)
            )
            # React to settings changes (persisted toggle) to drive ThemeManager
            try:
                def _on_window_theme_changed(key, value, _tm=self.theme_manager):
                    if key != 'themeName':
                        return
                    theme = str(value).lower()
                    if theme == 'system':
                        from styles.profiles import get_profile_name
                        theme = get_profile_name()
                    _tm.setTheme(theme)
                self.settings_bridge.settingChanged.connect(_on_window_theme_changed)
            except Exception:
                pass
        except Exception:
            # Non-fatal; app will still run
            self.theme_manager = None  # type: ignore[assignment]
            self.theme_bridge = None   # type: ignore[assignment]

        if self.customization_repo and ui_customization_services and getattr(self, "theme_manager", None):
            try:
                ui_customization_services.ensure_active_theme(
                    self.customization_repo,
                    self.theme_manager,
                    self.settings_bridge,
                )
            except Exception as exc:
                logger.warning("Failed to apply customized theme: %s", exc)

        # Prepare a Mission Status label (will live inside a dock, not fixed)
        self.active_incident_label = QLabel()
        self.update_active_incident_label()

        # Connection status line — sits below the incident label in Mission Status dock
        self.connection_status_label = QLabel()
        self._wire_connection_status_label()

        # Title includes active incident (if any)
        active_number = AppState.get_active_incident()
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        suffix = f" — User: {user_id or ''} ({user_role or ''})" if (user_id or user_role) else ""
        if active_number:
            incident = _get_incident_by_number(active_number)
            if incident:
                title = f"SARApp - {incident['number']} | {incident['name']}{suffix}"
            else:
                title = f"SARApp - No Incident Loaded{suffix}"
        else:
            title = f"SARApp - No Incident Loaded{suffix}"
        self.setWindowTitle(title)
        # Widen default window to accommodate richer objectives panel
        self.resize(1600, 950)

        # Central widget with persistent header and ADS dock manager
        central = QWidget()
        central_layout = QVBoxLayout(central)
        try:
            central_layout.setContentsMargins(0, 0, 0, 0)
            central_layout.setSpacing(0)
        except Exception:
            pass
        # Only a dock container in the central area; status goes to a dock
        self._dock_container = QWidget()
        central_layout.addWidget(self._dock_container)
        try:
            cont_layout = QVBoxLayout(self._dock_container)
            cont_layout.setContentsMargins(0, 0, 0, 0)
            cont_layout.setSpacing(0)
        except Exception:
            pass
        self.setCentralWidget(central)

        self.dock_manager = CDockManager(self._dock_container)
        # If CDockManager is a QWidget, add to container layout to fill area
        try:
            cont_layout.addWidget(self.dock_manager)  # type: ignore[name-defined]
        except Exception:
            pass

        # ADS appends its own rules to QApplication.styleSheet() during construction.
        # Re-applying our full stylesheet now ensures our ads-- rules come last and win.
        # We also set the stylesheet directly on the dock_manager as a belt-and-suspenders
        # measure (widget-level CSS beats application-level CSS in Qt's cascade).
        from PySide6QtAds import CDockWidgetTab

        _GRADIENT_ROLES = (
            QPalette.ColorRole.Button,
            QPalette.ColorRole.Light,
            QPalette.ColorRole.Midlight,
            QPalette.ColorRole.Mid,
            QPalette.ColorRole.Dark,
            QPalette.ColorRole.Shadow,
            QPalette.ColorRole.Window,
            QPalette.ColorRole.Base,
        )

        class _TabPaletteFilter(QObject):
            """App-level event filter that flattens the ADS tab gradient palette
            on every Polish event, which fires whenever Qt finalizes a widget's style."""
            def __init__(self, tokens: dict, parent=None):
                super().__init__(parent)
                self._tokens = tokens

            def update_tokens(self, tokens: dict) -> None:
                self._tokens = tokens

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Polish and isinstance(obj, CDockWidgetTab):
                    flat = QColor(self._tokens.get("bg_panel", "#151821"))
                    text = QColor(self._tokens.get("fg_primary", "#ECEFF4"))
                    p = obj.palette()
                    for role in _GRADIENT_ROLES:
                        p.setColor(role, flat)
                    p.setColor(QPalette.ColorRole.ButtonText, text)
                    p.setColor(QPalette.ColorRole.WindowText, text)
                    p.setColor(QPalette.ColorRole.Text, text)
                    obj.setPalette(p)
                return False

        _tab_filter = _TabPaletteFilter(
            self.theme_manager.tokens() if getattr(self, "theme_manager", None) else {},
            parent=self,
        )
        QApplication.instance().installEventFilter(_tab_filter)

        def _apply_full_theme(tokens: dict) -> None:
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(global_qss(tokens))
            try:
                self.dock_manager.setStyleSheet(ads_qss(tokens))
            except Exception:
                pass
            _tab_filter.update_tokens(tokens)
            # Re-polish all existing tabs so the filter fires immediately for them.
            for tab in self.dock_manager.findChildren(CDockWidgetTab):
                tab.style().unpolish(tab)
                tab.style().polish(tab)

        try:
            if getattr(self, "theme_manager", None):
                _tokens = self.theme_manager.tokens()
                _apply_full_theme(_tokens)
                self.theme_manager.themeChanged.connect(
                    lambda _: _apply_full_theme(self.theme_manager.tokens())
                )
        except Exception:
            pass

        # Load persisted perspectives if available (unless forced default)
        self._perspective_file = os.path.join("settings", "ads_perspectives.ini")
        # Ensure settings directory exists for INI persistence
        try:
            os.makedirs(os.path.dirname(self._perspective_file), exist_ok=True)
        except Exception:
            pass
        opened_default = False
        if FORCE_DEFAULT_LAYOUT:
            # Clear any saved layout and seed defaults immediately
            try:
                settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                settings_obj.clear()
            except Exception:
                pass
            self._reset_layout()
            opened_default = True
        else:
            try:
                # First, ensure a baseline set of docks exist so a saved perspective
                # can re-arrange them. ADS cannot create missing widgets on restore.
                self._create_default_docks()

                settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                self.dock_manager.loadPerspectives(settings_obj)
                # Attempt to apply the saved 'default' perspective to the created docks
                try:
                    rv = self.dock_manager.openPerspective("default")
                    opened_default = bool(rv) if rv is not None else True
                except Exception:
                    opened_default = False

                # If 'default' does not exist yet, persist current as 'default' for next time
                if not opened_default:
                    try:
                        self.dock_manager.addPerspective("default")
                        self.dock_manager.savePerspectives(settings_obj)
                        try:
                            self.dock_manager.openPerspective("default")
                            opened_default = True
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("Failed to load ADS perspectives: %s", e)

        if self.customization_repo and ui_customization_services:
            try:
                applied = ui_customization_services.ensure_active_layout(
                    self.customization_repo,
                    self.dock_manager,
                    self._perspective_file,
                )
                if applied:
                    opened_default = True
            except Exception as exc:
                logger.warning("Failed to apply customized layout: %s", exc)

        # Load profiles and prepare profile menu actions
        profile_manager.load_all_profiles("profiles")
        self._profile_actions: list[QAction] = []

        # Build the physical menu bar (visible UI)
        self.init_module_menus()

        # Fill the empty right portion of the menu bar so it paints the same
        # background color as the rest of the bar (Windows 11 leaves it white).
        _mb_corner = QWidget()
        _mb_corner.setObjectName("MenuBarCorner")
        _mb_corner.setAutoFillBackground(True)
        try:
            _mb_color = (self.theme_manager.tokens().get("menu_bar_bg", "#1313AB")
                         if getattr(self, "theme_manager", None) else "#1313AB")
            _mb_corner.setStyleSheet(f"background: {_mb_color};")
        except Exception:
            _mb_corner.setStyleSheet("background: #1313AB;")
        self.menuBar().setCornerWidget(_mb_corner, Qt.TopRightCorner)

        # If no saved layout was opened, create some default docks to play with
        # Seed defaults if not forced and no perspective opened or nothing is docked
        if not FORCE_DEFAULT_LAYOUT:
            # Baseline docks were created above; no need to seed again here.
            pass

        self._init_notifications()
        self._init_status_bar()

    # ----- Part 2.A: Physical Menu Builder ----------------------------------
    def _add_action(self, menu: QMenu, text: str, keyseq: str | None, module_key: str):
        """Create a QAction, attach module_key, connect to router, and add to menu."""
        act = QAction(text, self)
        if keyseq:
            act.setShortcut(QKeySequence(keyseq))
        act.setData({"module_key": module_key})
        act.triggered.connect(lambda: self.open_module(module_key))
        menu.addAction(act)
        return act

    def _set_theme_from_menu(self, theme_name: str, combo_index: int) -> None:
        """Persist theme selection from the View → Theme menu."""
        bridge = getattr(self, "settings_bridge", None)
        if bridge is None:
            return
        try:
            bridge.setSetting("themeIndex", combo_index)
        except Exception:
            pass
        try:
            bridge.setSetting("themeName", theme_name)
        except Exception:
            pass

    def _init_profiles_menu(self, profiles_menu: QMenu) -> None:
        """Populate the Profiles submenu with available profiles."""
        group = QActionGroup(self)
        group.setExclusive(True)
        active = profile_manager.get_active_profile_id()
        self._profile_actions.clear()
        for meta in profile_manager.list_profiles():
            act = QAction(meta.name, self)
            act.setCheckable(True)
            act.setData(meta.id)
            if meta.id == active:
                act.setChecked(True)
            act.triggered.connect(lambda checked=False, m=meta: self._on_profile_selected(m))
            group.addAction(act)
            profiles_menu.addAction(act)
            self._profile_actions.append(act)

        # Management entry
        profiles_menu.addSeparator()
        act_manage = QAction("Manage Profiles…", self)
        act_manage.triggered.connect(self.open_manage_profiles)
        profiles_menu.addAction(act_manage)

    def _add_weather_menu_items(self, parent_menu: QMenu, prefix: str) -> None:
        """Add Weather submenu entries under the given parent menu.

        The `prefix` determines routing keys, e.g. "planning.weather" or
        "safety.weather" to match handlers in `open_module`.
        """
        weather_menu = parent_menu.addMenu("Weather")
        self._add_action(weather_menu, "Current & Forecast", None, f"{prefix}.current")
        self._add_action(weather_menu, "Safety Summary", None, f"{prefix}.summary")
        self._add_action(weather_menu, "Timeline", None, f"{prefix}.timeline")
        self._add_action(weather_menu, "Aviation", None, f"{prefix}.aviation")
        self._add_action(weather_menu, "Advisories & Lightning", None, f"{prefix}.advisories")
        self._add_action(weather_menu, "Hazard Outlook (HWO)", None, f"{prefix}.hwo")
        self._add_action(weather_menu, "Sun & Moon Times", None, f"{prefix}.sun_times")
        weather_menu.addSeparator()
        self._add_action(weather_menu, "Settings", None, f"{prefix}.settings")
        self._add_action(weather_menu, "Export Briefing", None, f"{prefix}.export")

    def _on_profile_selected(self, meta: ProfileMeta) -> None:
        """Attempt to switch to the chosen profile and show result to user."""
        prev = profile_manager.get_active_profile_id()
        try:
            profile_manager.set_active_profile(meta.id)
        except Exception as e:
            QMessageBox.critical(self, "Profile Error", str(e))
            for act in self._profile_actions:
                act.setChecked(act.data() == prev)
            return
        try:
            notifier = get_notifier()
            notifier.showToast.emit({
                "title": "Profile",
                "message": f"Profile switched to {meta.name}",
            })
        except Exception:
            pass

    def open_manage_profiles(self) -> None:
        """Open the Manage Profiles dialog (non-dev menu access)."""
        try:
            from modules.devtools.panels.profile_manager_panel import ProfileManagerPanel
        except Exception as e:
            QMessageBox.critical(self, "Profiles", f"Failed to load Profile Manager panel:\n{e}")
            return

        panel = ProfileManagerPanel(parent=self)
        dlg = QDialog(self)
        dlg.setWindowTitle("Manage Profiles")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(panel)

        dlg.adjustSize()
        dlg.exec()

    def init_module_menus(self):
        """Build the entire menu tree in one place; handlers live below."""
        mb = self.menuBar()

        # ----- Menu -----
        m_menu = mb.addMenu("Menu")
        self._add_action(m_menu, "New Incident", "Ctrl+N", "menu.new_incident")
        self._add_action(m_menu, "Open Incident", "Ctrl+O", "menu.open_incident")
        self._add_action(m_menu, "Save Incident", "Ctrl+S", "menu.save_incident")
        self._add_action(m_menu, "Settings", None, "menu.settings")
        profiles_menu = m_menu.addMenu("Profiles")
        self._init_profiles_menu(profiles_menu)
        if any(
            func is not None
            for func in (
                get_layout_manager_panel,
                get_dashboard_designer_panel,
                get_theme_editor_panel,
            )
        ) or self.customization_repo is not None:
            m_customization = m_menu.addMenu("Customization")
            added_editor = False
            if get_layout_manager_panel is not None:
                act_layout_manager = QAction("Layout Templates…", self)
                act_layout_manager.triggered.connect(self.open_customization_layout_manager)
                m_customization.addAction(act_layout_manager)
                added_editor = True
            if get_dashboard_designer_panel is not None:
                act_dashboard = QAction("Dashboard Designer…", self)
                act_dashboard.triggered.connect(self.open_customization_dashboard_designer)
                m_customization.addAction(act_dashboard)
                added_editor = True
            if get_theme_editor_panel is not None:
                act_theme = QAction("Theme Designer…", self)
                act_theme.triggered.connect(self.open_customization_theme_editor)
                m_customization.addAction(act_theme)
                added_editor = True

            if self.customization_repo is not None:
                if added_editor and m_customization.actions():
                    m_customization.addSeparator()
                act_export_bundle = QAction("Export Customizations…", self)
                act_export_bundle.triggered.connect(self.export_customizations_bundle)
                m_customization.addAction(act_export_bundle)
                act_import_bundle = QAction("Import Customizations…", self)
                act_import_bundle.triggered.connect(self.import_customizations_bundle)
                m_customization.addAction(act_import_bundle)
        m_menu.addSeparator()
        self._add_action(m_menu, "Exit", "Ctrl+Q", "menu.exit")

        # ----- Edit -----
        m_edit = mb.addMenu("Edit")
        self._add_action(m_edit, "Aircraft", None, "edit.aircraft")
        self._add_action(m_edit, "Canned Communication Entries", None, "edit.canned_comm_entries")
        self._add_action(m_edit, "Communications Resources (ICS-217)", None, "communications.217")
        self._add_action(m_edit, "EMS Agencies", None, "edit.ems")
        self._add_action(m_edit, "Equipment", None, "edit.equipment")
        self._add_action(m_edit, "Hazard Type Library", None, "edit.hazard_types")
        self._add_action(m_edit, "Hospitals…", "Ctrl+H", "edit.hospitals")
        self._add_action(m_edit, "Objectives", None, "edit.objectives")
        self._add_action(m_edit, "Personnel", None, "edit.personnel")
        self._add_action(m_edit, "Resource Type Library", None, "edit.resource_types")
        self._add_action(m_edit, "Safety Analysis Templates", None, "edit.safety_templates")
        self._add_action(m_edit, "Task Types", None, "edit.task_types")
        self._add_action(m_edit, "Team Types", None, "edit.team_types")
        self._add_action(m_edit, "Units and Organizations", None, "edit.units_organizations")
        self._add_action(m_edit, "Vehicles", None, "edit.vehicles")

        # ----- View (moved under Menu) -----
        m_view = m_menu.addMenu("View")
        theme_menu = m_view.addMenu("Theme")
        # Use an exclusive action group so the menu shows radio options
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        act_light = QAction("Light", self)
        act_light.setCheckable(True)
        theme_group.addAction(act_light)

        act_dark = QAction("Dark", self)
        act_dark.setCheckable(True)
        theme_group.addAction(act_dark)

        def _update_theme_menu(theme_name: str) -> None:
            name = (theme_name or "light").lower()
            act_light.setChecked(name == "light")
            act_dark.setChecked(name == "dark")

        try:
            current_theme = self.theme_manager.theme if self.theme_manager else "light"
        except Exception:
            current_theme = "light"
        _update_theme_menu(current_theme)

        # Persist selection via settings bridge which drives ThemeManager
        act_light.triggered.connect(lambda: self._set_theme_from_menu("light", 2))
        act_dark.triggered.connect(lambda: self._set_theme_from_menu("dark", 1))

        if hasattr(self.settings_bridge, "settingChanged"):
            try:
                self.settings_bridge.settingChanged.connect(
                    lambda key, value: _update_theme_menu(str(value)) if key == "themeName" else None
                )
            except Exception:
                pass

        theme_menu.addAction(act_light)
        theme_menu.addAction(act_dark)
        if get_theme_editor_panel is not None:
            theme_menu.addSeparator()
            act_theme_designer = QAction("Theme Designer…", self)
            act_theme_designer.triggered.connect(self.open_customization_theme_editor)
            theme_menu.addAction(act_theme_designer)

        # ----- Command -----
        m_cmd = mb.addMenu("Command")
        self._add_action(m_cmd, "Incident Command Dashboard", None, "command.incident_dashboard")
        self._add_action(m_cmd, "Command Unit Log ICS-214", None, "command.unit_log")
        m_cmd.addSeparator()
        self._add_action(m_cmd, "Incident Overview", None, "command.incident_overview")
        self._add_action(m_cmd, "Incident Action Plan Builder", None, "command.iap")
        self._add_action(m_cmd, "Incident Objectives (ICS-202)", None, "command.objectives")
        self._add_action(m_cmd, "Incident Organization", None, "command.staff_org")
        self._add_action(m_cmd, "Situation Report (ICS-209)", None, "command.sitrep")
        m_cmd.addSeparator()
        self._add_action(m_cmd, "Set ICP Location", None, "command.icp_location")

        # ----- Planning -----
        m_plan = mb.addMenu("Planning")
        self._add_action(m_plan, "Planning Dashboard", "Ctrl+Alt+D", "planning.glance")
        self._add_action(m_plan, "Planning Unit Log ICS-214", None, "planning.unit_log")
        m_plan.addSeparator()
        self._add_action(m_plan, "Operational Period Manager", None, "planning.op_manager")
        self._add_action(m_plan, "Demobilization Planner", None, "planning.demobilization")
        self._add_action(m_plan, "Meeting Planner", None, "planning.meetings")
        self._add_action(m_plan, "Situation Report", None, "planning.sitrep")
        m_plan.addSeparator()
        self._add_action(m_plan, "Tactics and Resources Planner", None, "planning.tactics_planner")
        self._add_weather_menu_items(m_plan, prefix="planning.weather")

        # ----- Operations -----
        m_ops = mb.addMenu("Operations")
        self._add_action(m_ops, "Operations Dashboard", "Ctrl+1", "operations.dashboard")
        self._add_action(m_ops, "Operations Unit Log ICS-214", None, "operations.unit_log")
        m_ops.addSeparator()
        self._add_action(m_ops, "Tactics and Resources Planner", None, "planning.tactics_planner")
        m_ops.addSeparator()
        self._add_action(m_ops, "Operations Section Organization", None, "operations.section_org")
        self._add_action(m_ops, "Team Assignments", None, "operations.team_assignments")
        self._add_action(m_ops, "Team Status Board", None, "operations.team_status")
        self._add_action(m_ops, "Task Board", None, "operations.task_board")

        # ----- Logistics -----
        m_log = mb.addMenu("Logistics")
        self._add_action(m_log, "Logistics Dashboard", "Ctrl+L", "logistics.dashboard")
        self._add_action(m_log, "Logistics Unit Log ICS-214", None, "logistics.unit_log")
        m_log.addSeparator()
        self._add_action(m_log, "Tactics and Resources Planner", None, "planning.tactics_planner")
        m_log.addSeparator()
        self._add_action(m_log, "Check-In ICS-211", None, "logistics.211")
        self._add_action(m_log, "Resource Status Board", None, "logistics.resource_status")
        self._add_action(m_log, "Resource Requests (ICS-213RR)", None, "logistics.213rr")

        # ----- Communications -----
        m_comms = mb.addMenu("Communications")
        self._add_action(m_comms, "Communications Dashboard", None, "comms.traffic_log")
        self._add_action(m_comms, "Communications Unit Log ICS-214", None, "comms.unit_log")
        m_comms.addSeparator()
        self._add_action(m_comms, "Communications Plan ICS-205", None, "comms.205")
        self._add_action(m_comms, "Communications Log (ICS-309)", None, "comms.log_board")
        self._add_action(m_comms, "Log & Entry", None, "comms.log_entry")
        self._add_action(m_comms, "Quick Entry", None, "comms.quick_entry")
        self._add_action(m_comms, "Chat Messaging", None, "comms.chat")
        self._add_action(m_comms, "ICS 213 Messages", None, "comms.213")
        m_comms.addSeparator()
        self._add_action(m_comms, "Notification Feed", None, "comms.notifications")
        self._add_action(m_comms, "Notification Settings", None, "comms.notification_settings")


        # ----- Intel -----
        m_intel = mb.addMenu("Intel")
        self._add_action(m_intel, "Intel Dashboard", None, "intel.dashboard")
        self._add_action(m_intel, "Intel Unit Log ICS-214", None, "intel.unit_log")
        m_intel.addSeparator()
        self._add_action(m_intel, "Subjects", None, "intel.subjects")
        self._add_action(m_intel, "Leads", None, "intel.leads")
        self._add_action(m_intel, "Intel Items", None, "intel.items")
        self._add_action(m_intel, "Assessments", None, "intel.assessments")
        self._add_action(m_intel, "Intel Log", None, "intel.log")
        self._add_action(m_intel, "Forms", None, "intel.forms")

        # ----- Medical & Safety -----
        m_med = mb.addMenu("Medical && Safety")
        self._add_action(m_med, "Medical Unit Log ICS-214", None, "medical.unit_log")
        self._add_action(m_med, "Safety Unit Log ICS-214", None, "safety.unit_log")
        m_med.addSeparator()
        self._add_action(m_med, "Medical Plan ICS 206", None, "medical.206")
        self._add_action(m_med, "Safety Message ICS-208", None, "safety.208")
        self._add_action(m_med, "Incident Safety Analysis ICS-215A", None, "safety.215A")
        self._add_action(m_med, "CAP ORM CAPF-160", None, "safety.caporm")
        self._add_action(m_med, "Safety Incident Reports (IWI)", None, "safety.iwi")
        m_med.addSeparator()
        self._add_weather_menu_items(m_med, prefix="safety.weather")
        # ----- Liaison -----
        m_lia = mb.addMenu("Liaison")
        self._add_action(m_lia, "Liaison Unit Log ICS-214", None, "liaison.unit_log")
        m_lia.addSeparator()
        self._add_action(m_lia, "Agency Directory", None, "liaison.agencies")
        self._add_action(m_lia, "External Coordination", None, "liaison.requests")

        # ----- Public Information -----
        m_pub = mb.addMenu("Public Information")
        self._add_action(m_pub, "Public Information Dashboard", None, "public.dashboard")
        self._add_action(m_pub, "Public Information Unit Log ICS-214", None, "public.unit_log")
        m_pub.addSeparator()
        self._add_action(m_pub, "Messages / Releases", None, "public.media_releases")
        self._add_action(m_pub, "Rumor / Misinformation", None, "public.misinformation")
        self._add_action(m_pub, "Media Log", None, "public.inquiries")
        self._add_action(m_pub, "Talking Points", None, "public.talking_points")
        self._add_action(m_pub, "Letterhead / Templates", None, "public.templates")
        self._add_action(m_pub, "Distribution Log", None, "public.distribution")

        # ----- Finance/Admin -----
        m_fin = mb.addMenu("Finance/Admin")
        # Primary dashboard entry
        self._add_action(m_fin, "Finance/Admin Dashboard", None, "finance.dashboard")
        self._add_action(m_fin, "Finance Unit Log ICS-214", None, "finance.unit_log")
        m_fin.addSeparator()
        self._add_action(m_fin, "Time Tracking", None, "finance.time")
        self._add_action(m_fin, "Expenses && Procurement", None, "finance.procurement")
        self._add_action(m_fin, "Cost Summary", None, "finance.summary")

        # ----- Toolkits -----
        m_tool = mb.addMenu("Toolkits")
        sar_menu = m_tool.addMenu("SAR Toolkit")
        self._add_action(m_tool, "Projection Dashboard", None, "toolkit.projection_dashboard")
        self._add_action(sar_menu, "Missing Person Toolkit", None, "toolkit.sar.missing_person")
        self._add_action(sar_menu, "POD Calculator", None, "toolkit.sar.pod")

        dis_menu = m_tool.addMenu("Disaster Toolkit")
        self._add_action(dis_menu, "Damage Assessment", None, "toolkit.disaster.damage")
        self._add_action(dis_menu, "Urban Interview Log", None, "toolkit.disaster.urban_interview")
        self._add_action(dis_menu, "Damage Photos", None, "toolkit.disaster.photos")

        plan_menu = m_tool.addMenu("Planned Event Toolkit")
        self._add_action(plan_menu, "External Messaging", None, "planned.promotions")
        self._add_action(plan_menu, "Vendors && Permits", None, "planned.vendors")
        self._add_action(plan_menu, "Public Safety", None, "planned.safety")
        self._add_action(plan_menu, "Quick Assignments", None, "planned.tasking")
        self._add_action(plan_menu, "Health && Sanitation", None, "planned.health_sanitation")

        init_menu = m_tool.addMenu("Initial Response")
        self._add_action(init_menu, "Initial Information", None, "toolkit.initial.overview")
        self._add_action(init_menu, "Early Tasking", None, "toolkit.initial.hasty")

        # ----- Reference Library & Forms -----
        m_reference = self.menuBar().addMenu("Reference Library")
        self._add_action(m_reference, "Browse Library", None, "library")

        m_reference.addSeparator()
        self._add_action(m_reference, "User Guide", None, "help.user_guide")

        # ----- Help -----
        m_help = self.menuBar().addMenu("Help")
        self._add_action(m_help, "About", None, "help.about")
        self._add_action(m_help, "User Guide", None, "help.user_guide")

        # ----- Window -----
        m_window = self.menuBar().addMenu("Window")
        self._add_action(m_window, "Home Dashboard", "Ctrl+H", "window.home_dashboard")

        # Templates submenu — presets + user-saved templates
        m_layouts = m_window.addMenu("Templates")
        m_layouts.aboutToShow.connect(lambda: self._rebuild_layouts_menu(m_layouts))
        # Seed the menu so it isn't empty before first hover
        self._rebuild_layouts_menu(m_layouts)

        m_window.addSeparator()

        # Widgets submenu: list all registry widgets for ad-hoc placement
        try:
            from ui.widgets import registry as W
        except Exception:
            W = None  # type: ignore
        m_widgets = m_window.addMenu("Widgets")
        if W and hasattr(W, "REGISTRY"):
            for wid, spec in sorted(W.REGISTRY.items(), key=lambda kv: kv[1].title.lower()):
                if wid == "quickEntryCLI":
                    # CLI is embedded inside Quick Entry per spec; skip standalone menu item
                    continue
                self._add_action(m_widgets, spec.title, None, f"widgets.{wid}")

        # Templates manager for saving/loading/deleting ADS perspectives
        act_templates = QAction("Display Templates...", self)
        act_templates.triggered.connect(self.open_display_templates_dialog)
        m_window.addAction(act_templates)

        # Save current layout as the default perspective
        act_set_default = QAction("Set Current Layout as Default", self)
        act_set_default.triggered.connect(self.set_current_layout_as_default)
        m_window.addAction(act_set_default)

        # Lock/Unlock docking interactions
        self.act_lock_docking = QAction("Lock Docking", self)
        self.act_lock_docking.setCheckable(True)
        self.act_lock_docking.setChecked(False)
        self.act_lock_docking.toggled.connect(self.toggle_dock_lock)
        m_window.addAction(self.act_lock_docking)

        m_window.addSeparator()

        # Existing: open a new floating workspace window
        act_new_ws = QAction("New Workspace Window", self)
        act_new_ws.triggered.connect(self.open_new_workspace_window)
        m_window.addAction(act_new_ws)

        # ----- Debug -----
        self.menuDebug = self.menuBar().addMenu("Debug")
        act = QAction("Print Active Incident", self)
        act.triggered.connect(lambda: print(f"[debug] active incident={AppState.get_active_incident()!r}"))
        self.menuDebug.addAction(act)

        # Quick way to add sample docks to play with ADS
        act_defaults = QAction("Open Default Docks", self)
        act_defaults.triggered.connect(self._create_default_docks)
        self.menuDebug.addAction(act_defaults)

        act_reset = QAction("Reset Layout (Default)", self)
        act_reset.triggered.connect(self._reset_layout)
        self.menuDebug.addAction(act_reset)

        # legacy UI debug openers removed to allow running without legacy UI assets

        act_audit = QAction("Audit Console", self)
        def _show_audit():
            try:
                rows = fetch_last_audit_rows()
                for row in rows:
                    print(dict(row))
            except Exception as e:
                print(f"[debug] failed to fetch audit logs: {e}")
        act_audit.triggered.connect(_show_audit)
        self.menuDebug.addAction(act_audit)

        # Debug: Open Team Detail by ID
        act_team_detail = QAction("Open Team Detail (Team ID…)", self)
        def _open_team_detail_prompt():
            try:
                from PySide6.QtWidgets import QInputDialog
                team_id, ok = QInputDialog.getInt(self, "Open Team Detail", "Team ID:", 1, 1, 10_000_000, 1)
                if ok:
                    from modules.operations.teams.windows import open_team_detail_window
                    open_team_detail_window(int(team_id))
            except Exception as e:
                print(f"[debug] failed to open Team Detail: {e}")
        act_team_detail.triggered.connect(_open_team_detail_prompt)
        self.menuDebug.addAction(act_team_detail)

        self._refresh_toolkit_menu_gates()
        # you can toggle feature availability here, e.g.: {"planned.promotions": False}

    def _gate_menus_by_availability(self, enabled_map: dict[str, bool]):
        """Grey-out actions whose module keys are disabled in enabled_map."""
        for menu in self.menuBar().findChildren(QMenu):
            for act in menu.actions():
                data = act.data()
                if isinstance(data, dict) and "module_key" in data:
                    key = data["module_key"]
                    if key in enabled_map:
                        act.setEnabled(bool(enabled_map[key]))

    def _refresh_toolkit_menu_gates(self, incident: Optional[dict] = None) -> None:
        """Enable/disable toolkit menu entries based on incident type."""
        try:
            if incident is None:
                incident_id = AppState.get_active_incident()
                if incident_id:
                    incident = _get_incident_by_number(incident_id)
                else:
                    incident_number = AppState.get_active_incident()
                    incident = (
                        _get_incident_by_number(incident_number)
                        if incident_number
                        else None
                    )
        except Exception:
            incident = None

        category = _classify_incident_category(incident)
        enabled = {
            "toolkit.sar.missing_person": category == "sar",
            "toolkit.sar.pod": category == "sar",
            "toolkit.disaster.damage": category == "disaster",
            "toolkit.disaster.urban_interview": category == "disaster",
            "toolkit.disaster.photos": category == "disaster",
            "planned.promotions": True,
            "planned.vendors": True,
            "planned.safety": True,
            "planned.tasking": True,
            "planned.health_sanitation": True,
            "toolkit.initial.hasty": category in {"sar", "disaster"},
        }
        if category is None:
            for key in enabled:
                enabled[key] = False
        self._gate_menus_by_availability(enabled)

    # ===== Part 3: Central Router (module_key -> handler) ====================
    def open_module(self, key: str):
        """Central router: call explicit handler for every menu item (panel pattern)."""
        # Dynamic widget openers
        if key.startswith("widgets."):
            widget_id = key.split(".", 1)[1]
            return self.open_widget_with_id(widget_id)
        handlers: dict[str, Callable[[], None]] = {
            # ----- Menu -----
            "menu.new_incident": self.open_menu_new_incident,
            "menu.open_incident": self.open_menu_open_incident,
            "menu.save_incident": self.open_menu_save_incident,
            "menu.settings": self.open_menu_settings,
            "menu.exit": self.open_menu_exit,  # special-case: still exits

            # ----- Edit -----
            "edit.ems": self.open_edit_ems,
            "edit.hospitals": self.open_edit_hospitals,
            "edit.canned_comm_entries": self.open_edit_canned_comm_entries,
            "edit.personnel": self.open_edit_personnel,
            "edit.objectives": self.open_edit_objectives,
            "edit.task_types": self.open_edit_task_types,
            "edit.team_types": self.open_edit_team_types,
            "edit.vehicles": self.open_edit_vehicles,
            "edit.aircraft": self.open_edit_aircraft,
            "edit.equipment": self.open_edit_equipment,
            "edit.resource_types": self.open_edit_resource_types,
            "edit.hazard_types": self.open_edit_hazard_types,
            "communications.217": self.open_edit_comms_resources,
            "edit.safety_templates": self.open_edit_safety_templates,
            "edit.units_organizations": self.open_edit_units_organizations,

            # ----- Command -----
            "command.unit_log": self.open_command_unit_log,
            "command.incident_dashboard": self.open_command_incident_dashboard,
            "command.incident_overview": self.open_command_incident_overview,
            "command.iap": self.open_command_iap,
            "command.objectives": self.open_command_objectives,
            "command.staff_org": self.open_command_staff_org,
            "command.sitrep": self.open_command_sitrep,
            "command.icp_location": self.open_command_icp_location,

            # ----- Planning -----
            "planning.unit_log": self.open_planning_unit_log,
            "planning.glance": self.open_planning_glance,
            "planning.approvals": self.open_planning_approvals,
            "planning.op_manager": self.open_planning_op_manager,
            "planning.demobilization": self.open_planning_demobilization,
            "planning.meetings": self.open_planning_meetings,
            "planning.sitrep": self.open_planning_sitrep,
            "planning.tactics_planner": self.open_tactics_resources_planner,

            "planning.weather.summary": self.open_weather_safety_summary,
            "planning.weather.current": self.open_weather_current_forecast,
            "planning.weather.timeline": self.open_weather_timeline,
            "planning.weather.aviation": self.open_weather_aviation,
            "planning.weather.advisories": self.open_weather_advisories,
            "planning.weather.hwo": self.open_weather_hwo,
            "planning.weather.sun_times": self.open_weather_sun_times,
            "planning.weather.settings": self.open_weather_settings,
            "planning.weather.export": self.open_weather_export,
            # ----- Operations -----
            "operations.unit_log": self.open_operations_unit_log,
            "operations.dashboard": self.open_operations_dashboard,
            "operations.section_org": self.open_operations_section_org,
            "operations.team_assignments": self.open_operations_team_assignments,
            "operations.team_status": self.open_operations_team_status,
            "operations.task_board": self.open_operations_task_board,
            "operations.narrative": self.open_operations_narrative,

            # ----- Logistics -----
            "logistics.unit_log": self.open_logistics_unit_log,
            "logistics.dashboard": self.open_logistics_dashboard,
            "logistics.211": self.open_logistics_211,
            "logistics.resource_status": self.open_logistics_resource_status,
            "logistics.requests": self.open_logistics_requests,
            "logistics.213rr": self.open_logistics_213rr,

            # ----- Communications -----
            "comms.unit_log": self.open_comms_unit_log,
            "comms.traffic_log": self.open_comms_traffic_log,
            "comms.log_board": self.open_comms_log_board,
            "comms.log_entry": self.open_comms_log_entry,
            "comms.quick_entry": self.open_comms_quick_entry,
            "comms.chat": self.open_comms_chat,
            "comms.213": self.open_comms_213,
            "comms.205": self.open_comms_205,
            "comms.notifications": self.open_notifications_panel,

            # ----- Intel -----
            "intel.unit_log": self.open_intel_unit_log,
            "intel.dashboard": lambda: self.open_intel_module(tab="dashboard"),
            "intel.subjects": lambda: self.open_intel_module(tab="subjects"),
            "intel.leads": lambda: self.open_intel_module(tab="leads"),
            "intel.items": lambda: self.open_intel_module(tab="items"),
            "intel.assessments": lambda: self.open_intel_module(tab="assessments"),
            "intel.log": lambda: self.open_intel_module(tab="log"),
            "intel.forms": lambda: self.open_intel_module(tab="forms"),

            # ----- Medical & Safety -----
            "medical.unit_log": self.open_medical_unit_log,
            "safety.unit_log": self.open_safety_unit_log,
            "medical.206": self.open_medical_206,
            "safety.208": self.open_safety_208,
            "safety.215A": self.open_safety_215A,
            "safety.caporm": self.open_safety_caporm,
            "safety.iwi": self.open_safety_iwi,

            "safety.weather.summary": self.open_weather_safety_summary,
            "safety.weather.current": self.open_weather_current_forecast,
            "safety.weather.timeline": self.open_weather_timeline,
            "safety.weather.aviation": self.open_weather_aviation,
            "safety.weather.advisories": self.open_weather_advisories,
            "safety.weather.hwo": self.open_weather_hwo,
            "safety.weather.sun_times": self.open_weather_sun_times,
            "safety.weather.settings": self.open_weather_settings,
            "safety.weather.export": self.open_weather_export,
            # ----- Liaison -----
            "liaison.unit_log": self.open_liaison_unit_log,
            "liaison.agencies": self.open_liaison_agencies,
            "liaison.requests": self.open_liaison_requests,

            # ----- Public Information -----
            "public.dashboard":       self.open_public_dashboard,
            "public.unit_log":        self.open_public_unit_log,
            "public.media_releases":  self.open_public_media_releases,
            "public.misinformation":  self.open_public_misinformation,
            "public.inquiries":       self.open_public_inquiries,
            "public.talking_points":  self.open_public_talking_points,
            "public.templates":       self.open_public_templates,
            "public.distribution":    self.open_public_distribution,

            # ----- Finance/Admin -----
            "finance.dashboard": self.open_finance_admin_dashboard,
            "finance.unit_log": self.open_finance_unit_log,
            "finance.time": self.open_finance_time,
            "finance.procurement": self.open_finance_procurement,
            "finance.summary": self.open_finance_summary,

            # ----- Toolkits -----
            "toolkit.sar.missing_person": self.open_toolkit_sar_missing_person,
            "toolkit.sar.pod": self.open_toolkit_sar_pod,
            "toolkit.disaster.damage": self.open_toolkit_disaster_damage,
            "toolkit.disaster.urban_interview": self.open_toolkit_disaster_urban_interview,
            "toolkit.disaster.photos": self.open_toolkit_disaster_photos,
            "planned.promotions": self.open_planned_promotions,
            "toolkit.projection_dashboard": self.open_toolkit_projection_dashboard,
            "planned.vendors": self.open_planned_vendors,
            "planned.safety": self.open_planned_safety,
            "planned.tasking": self.open_planned_tasking,
            "planned.health_sanitation": self.open_planned_health_sanitation,
            "toolkit.initial.overview": self.open_toolkit_initial_overview,
            "toolkit.initial.hasty": self.open_toolkit_initial_hasty,

            # ----- Reference Library & Forms -----
            "library": self.open_reference_library,

            "help.user_guide": self.open_help_user_guide,

            # ----- Help -----
            "help.about": self.open_help_about,

            # ----- Window -----
            "window.home_dashboard": self.open_home_dashboard,
        }

        handler = handlers.get(key)
        if handler:
            handler()
        else:
            print(f"[OpenModule] no handler for {key}")

# ===== Part 4: Handlers in Menu Order (panel-factory pattern) ============
# --- 4.1 Menu ------------------------------------------------------------
    def open_menu_new_incident(self) -> None:
        from modules.incidents.new_incident_dialog import NewIncidentDialog

        dlg = NewIncidentDialog(self)
        dlg.created.connect(self._on_incident_created)
        dlg.show()

    def _on_incident_created(self, meta, incident_id: str) -> None:
        """Handle mission creation from the New Incident dialog."""
        # Set as the active incident immediately
        try:
            from utils import incident_context
            AppState.set_active_incident(meta.number)
            incident_context.set_active_incident(str(meta.number))
            self.update_title_with_active_incident()
        except Exception:
            logger.exception("Failed to set active incident context")

        QMessageBox.information(
            self,
            "Mission Created",
            f"Mission '{meta.name}' created and activated.",
        )

        # 4) If the incident selection window is open, refresh it and select
        if hasattr(self, "incident_selection_window") and hasattr(
            self.incident_selection_window, "reload_missions"
        ):
            try:
                self.incident_selection_window.reload_missions(select_slug=meta.slug())
            except Exception:
                logger.exception("Failed to refresh incident selection window")

        # --- 4.1 Menu ------------------------------------------------------------
    def open_menu_open_incident(self) -> None:
        """Launch the Incident Selection window."""
        from ui_bootstrap.incident_select_bootstrap import show_incident_selector
        def _apply_active(number: int) -> None:
            print(f"[main] on_select callback received: {number}")
            AppState.set_active_incident(number)
            self.update_title_with_active_incident()

        show_incident_selector(on_select=_apply_active)

    def open_menu_save_incident(self) -> None:
        from ui_bootstrap.incident_select_bootstrap import show_incident_selector
        show_incident_selector()

    def open_menu_settings(self) -> None:
        """Open the widget-based Settings window."""
        window = getattr(self, "_settings_window", None)
        if window is None or not isinstance(window, SettingsWindow):
            window = SettingsWindow(self.settings_bridge, parent=self)
            window.setAttribute(Qt.WA_DeleteOnClose, True)
            window.destroyed.connect(lambda: setattr(self, "_settings_window", None))
            self._settings_window = window

        window.show()
        window.raise_()
        window.activateWindow()

    def open_menu_exit(self) -> None:
        # Exit remains a direct action rather than opening a panel.
        QApplication.instance().quit()

# --- 4.2 Edit ------------------------------------------------------------
    def open_edit_ems(self) -> None:
        from modules.medical.panels.ems_agencies_window import EMSAgenciesWindow

        window = getattr(self, '_ems_window', None)
        if window is None or not isinstance(window, EMSAgenciesWindow):
            window = EMSAgenciesWindow(parent=self)
            window.destroyed.connect(lambda: setattr(self, '_ems_window', None))
            self._ems_window = window
        window.show()
        window.raise_()
        window.activateWindow()

    def open_edit_hospitals(self) -> None:
        from modules.medical.hospitals import HospitalManagerDialog

        win = HospitalManagerDialog(parent=self)
        self._register_child_window(win)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_edit_canned_comm_entries(self) -> None:
        # Use the QtWidgets-based window under root panels
        from panels.canned_comm_entries_window import (
            CannedCommEntriesWindow,
        )

        window = getattr(self, "_canned_comm_window", None)
        if window is None or not isinstance(window, CannedCommEntriesWindow):
            if not hasattr(self, "_catalog_bridge"):
                self._catalog_bridge = CatalogBridge(db_path="data/master.db")
            window = CannedCommEntriesWindow(
                catalog_bridge=self._catalog_bridge,
                parent=self,
            )
            window.setAttribute(Qt.WA_DeleteOnClose, True)
            window.destroyed.connect(lambda: setattr(self, "_canned_comm_window", None))
            self._canned_comm_window = window

        window.show()
        window.raise_()
        window.activateWindow()

    def open_edit_personnel(self) -> None:
        from ui.personnel import PersonnelInventoryWindow

        win = PersonnelInventoryWindow(parent=self)
        self._register_child_window(win)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_edit_objectives(self) -> None:
        try:
            from modules.planning.widgets.objectives_editor import show_objectives_editor
            editor = show_objectives_editor(None)
            self._register_child_window(editor)
            editor.raise_()
            editor.activateWindow()
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Objectives", f"Failed to open Objectives Editor:\n{exc}")

    def open_edit_task_types(self) -> None:
        from modules.common.widgets.type_editors.task_types_editor import (
            TaskTypesEditorDialog,
        )

        dialog = TaskTypesEditorDialog(parent=self)
        self._register_child_window(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def open_edit_team_types(self) -> None:
        from modules.common.widgets.type_editors.team_types_editor import (
            TeamTypesEditorDialog,
        )

        dialog = TeamTypesEditorDialog(parent=self)
        self._register_child_window(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def open_edit_vehicles(self) -> None:
        from modules.logistics.vehicle.panels.vehicle_inventory_panel import (
            VehicleInventoryDialog,
        )
        win = VehicleInventoryDialog(parent=self)
        self._register_child_window(win)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_edit_aircraft(self) -> None:
        from modules.logistics.aircraft.panels.aircraft_inventory_window import (
            AircraftInventoryWindow,
        )

        dialog = AircraftInventoryWindow(parent=self)
        self._register_child_window(dialog)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def open_edit_equipment(self) -> None:
        try:
            from panels.equipment_edit_panel import EquipmentEditPanel
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Equipment Panel Error", f"Unable to load Equipment panel.\n{exc}")
            return
        win = EquipmentEditPanel(parent=self)
        self._register_child_window(win)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_edit_resource_types(self) -> None:
        """Open the Resource Type Library from the Edit menu.

        The library window is modeless, so users can keep it open while working
        elsewhere.  The module helper stores a parent-owned reference to avoid
        Python garbage collection closing the window unexpectedly.
        """
        try:
            from modules.admin.resource_types.windows import open_resource_type_library
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Resource Type Library",
                f"Unable to load Resource Type Library.\n{exc}",
            )
            return
        open_resource_type_library(parent=self)

    def open_edit_hazard_types(self) -> None:
        """Open the Hazard Type Library from the Edit menu."""

        try:
            from modules.admin.hazard_types.windows import open_hazard_type_library
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Hazard Type Library",
                f"Unable to load Hazard Type Library.\n{exc}",
            )
            return
        open_hazard_type_library(parent=self)

    def open_edit_comms_resources(self) -> None:
        try:
            from panels.comms_resource_editor import CommsResourceEditor
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Load Failed", f"Unable to load Comms Resource Editor: {e}")
            return
        win = CommsResourceEditor(parent=self)
        self._register_child_window(win)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_edit_safety_templates(self) -> None:
        """Open the Safety Analysis Library on the Scenario Templates tab."""
        try:
            from modules.admin.hazard_types.windows import open_hazard_type_library
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Safety Analysis Library",
                f"Unable to load Safety Analysis Library.\n{exc}",
            )
            return
        open_hazard_type_library(parent=self, tab=1)

    def open_edit_units_organizations(self) -> None:
        """Open the master-data Units and Organizations editor panel."""
        try:
            from modules.personnel.units_organizations import (
                UnitsOrganizationsPanel,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Units and Organizations",
                f"Unable to load Units and Organizations panel:\n{exc}",
            )
            return

        win = UnitsOrganizationsPanel(parent=self)
        self._register_child_window(win)
        win.show()
        win.raise_()
        win.activateWindow()

# --- 4.3 Command ---------------------------------------------------------
    def open_command_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:command",
            "default_log_name": "Command",
            "default_prepared_by_position": "Incident Commander",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Command", preferred_size=(950, 600))

    def open_command_incident_dashboard(self) -> None:
        from modules import command
        incident_id = AppState.get_active_incident()
        panel = command.get_incident_dashboard_panel(incident_id)
        self._open_panel(panel, title="Incident Command Dashboard", preferred_size=(900, 700))

    def open_command_incident_overview(self) -> None:
        # Replace placeholder with real Incident Overview panel (widgets only)
        try:
            from modules.command.panels.incident_overview import (
                IncidentOverviewPanel,
                create_command_incident_overview_panel,
            )
            widget = create_command_incident_overview_panel(self.dock_manager, getattr(self, "app_context", None))
            self._open_panel(widget, title=IncidentOverviewPanel.panel_title)
        except Exception:
            # Fallback to legacy placeholder if import fails
            from modules import command
            incident_id = AppState.get_active_incident()
            panel = command.get_incident_overview_panel(incident_id)
            self._open_panel(panel, title="Incident Overview")

    def open_command_iap(self) -> None:
        from modules import command
        incident_id = AppState.get_active_incident()
        panel = command.get_iap_builder_panel(incident_id)
        self._open_panel(panel, title="Incident Action Plan Builder")

    def open_command_objectives(self) -> None:
        from modules import command
        incident_id = AppState.get_active_incident()
        panel = command.get_objectives_panel(incident_id)
        self._open_panel(panel, title="Incident Objectives (ICS 202)")

    def open_command_staff_org(self) -> None:
        from modules import command
        incident_id = AppState.get_active_incident()
        panel = command.get_staff_org_panel(incident_id)
        self._open_panel(panel, title="Incident Organization")

    def open_command_sitrep(self) -> None:
        from modules import command
        incident_id = AppState.get_active_incident()
        panel = command.get_sitrep_panel(incident_id)
        self._open_panel(panel, title="Situation Report (ICS 209)")

# --- 4.4 Planning --------------------------------------------------------
    def open_planning_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:planning",
            "default_log_name": "Planning",
            "default_prepared_by_position": "Planning Section Chief",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Planning", preferred_size=(950, 600))

    def open_planning_glance(self) -> None:
        """Open the Planning — At-a-Glance widget (compact, modeless/dock)."""
        try:
            from modules.planning.panels.plandashboard import (
                make_planning_glance_widget,
                PlanningGlanceWidget,
            )
        except Exception as e:
            try:
                QMessageBox.warning(self, "Planning At-a-Glance", f"Widget unavailable.\n{e}")
            except Exception:
                print(f"[warn] PlanningGlanceWidget unavailable: {e}")
            return

        widget: PlanningGlanceWidget = make_planning_glance_widget(self)
        # Set a reasonable auto-refresh interval; controllers can override.
        try:
            widget.setAutoRefresh(30000)
        except Exception:
            pass
        self._open_panel(widget, title="Planning — At-a-Glance")

    def open_planning_approvals(self) -> None:
        from modules.approvals.panels.approval_inbox_panel import ApprovalInboxPanel
        incident_id = AppState.get_active_incident()
        personnel_id = str(AppState.get_active_user_id() or "")
        panel = ApprovalInboxPanel(incident_id=incident_id, personnel_id=personnel_id)
        panel.load()
        panel.item_activated.connect(self._on_approval_item_activated)
        self._open_panel(panel, title="Pending Approvals")

    def open_planning_op_manager(self) -> None:
        from modules import planning
        incident_id = AppState.get_active_incident()
        panel = planning.get_op_manager_panel(incident_id)
        self._open_panel(panel, title="Operational Period Manager")

    def open_planning_demobilization(self) -> None:
        from modules import planning
        incident_id = AppState.get_active_incident()
        panel = planning.get_demobilization_panel(incident_id)
        self._open_panel(panel, title="Demobilization Planner")

    def open_planning_meetings(self) -> None:
        from modules import planning
        incident_id = AppState.get_active_incident()
        panel = planning.get_meetings_panel(incident_id)
        self._open_panel(panel, title="Meeting Planner")

    def open_planning_sitrep(self) -> None:
        from modules import planning
        incident_id = AppState.get_active_incident()
        panel = planning.get_sitrep_panel(incident_id)
        self._open_panel(panel, title="Situation Report")

    def open_tactics_resources_planner(self) -> None:
        try:
            from modules.planning.tactics_resources import open_tactics_resources_planner
            open_tactics_resources_planner(parent=self)
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Tactics and Resources Planner", f"Could not open planner:\n{exc}")

# --- 4.5 Operations ------------------------------------------------------
    def open_weather_safety_summary(self) -> None:
        """Open the dockable Weather Safety summary page."""
        from modules.intel.weather.pages.weather_summary_page import WeatherSummaryPage
        panel = WeatherSummaryPage(self)
        self._open_panel(panel, title="Weather Safety")

    def open_weather_timeline(self) -> None:
        """Open the standalone Weather Timeline window."""
        from modules.intel.weather.infra import ui_factories
        ui_factories.open_weather_timeline()

    def open_weather_aviation(self) -> None:
        """Open the standalone Aviation Weather window."""
        from modules.intel.weather.infra import ui_factories
        ui_factories.open_aviation_window()

    def open_weather_advisories(self) -> None:
        """Open the standalone Advisories & Lightning window."""
        from modules.intel.weather.infra import ui_factories
        ui_factories.open_advisories_window()

    def open_weather_hwo(self) -> None:
        """Open the standalone HWO viewer window."""
        from modules.intel.weather.infra import ui_factories
        ui_factories.open_hwo_viewer()

    def open_weather_sun_times(self) -> None:
        """Open the standalone sunrise and sunset panel."""
        from modules.intel.weather.infra import ui_factories
        ui_factories.open_sun_times_panel(self)

    def open_weather_settings(self) -> None:
        """Open the Weather Safety settings dialog."""
        from modules.intel.weather.infra import ui_factories
        ui_factories.open_settings_dialog(self)

    def open_weather_export(self) -> None:
        """Open the Weather Safety briefing export dialog."""
        from modules.intel.weather.infra import ui_factories
        ui_factories.open_export_dialog(self)

    def open_weather_current_forecast(self) -> None:
        """Open the Current & Forecast weather window."""
        try:
            from modules.intel.weather.infra import ui_factories
            ui_factories.open_current_forecast_window()
        except Exception as e:
            QMessageBox.critical(self, "Weather", f"Failed to open Current & Forecast window:\n{e}")
    def open_command_icp_location(self) -> None:
        """Open the ICP Location window for the active incident."""
        try:
            from modules.command.windows.icp_location_window import IcpLocationWindow
        except Exception as e:
            QMessageBox.critical(self, "ICP Location", f"Failed to load ICP Location window:\n{e}")
            return
        window = IcpLocationWindow(self)
        window.show()
        window.raise_()
    def open_operations_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:operations",
            "default_log_name": "Operations",
            "default_prepared_by_position": "Operations Section Chief",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Operations", preferred_size=(950, 600))

    def open_operations_dashboard(self) -> None:
        """Open the Operations Dashboard (compact) and wire live data."""
        try:
            from modules.operations.panels.opsdashboard import make_ops_glance_widget, OpsGlanceWidget
        except Exception as e:
            try:
                QMessageBox.warning(self, "Operations Dashboard", f"Widget unavailable.\n{e}")
            except Exception:
                print(f"[warn] OpsGlanceWidget unavailable: {e}")
            return

        widget: OpsGlanceWidget = make_ops_glance_widget(self)
        self._wire_ops_glance(widget)
        self._open_panel(widget, title="Operations — Dashboard")

    # ---- Ops Glance data wiring ----
    def _wire_ops_glance(self, w) -> None:
        from utils.app_signals import app_signals
        from utils.state import AppState
        from utils import incident_context
        from datetime import datetime, timedelta, timezone

        # Button/signal wiring
        def _open_task(task_id: str) -> None:
            try:
                from modules.operations.taskings.windows import open_task_detail_window
                open_task_detail_window(int(task_id))
            except Exception as exc:
                try:
                    QMessageBox.warning(self, "Open Task", f"Could not open task detail.\n{exc}")
                except Exception:
                    print(f"[warn] open_task failed: {exc}")

        w.openTaskRequested.connect(_open_task)

        def _reassign(task_id_or_none, team_name_or_none) -> None:
            # Route to relevant UI for reassignment
            try:
                if task_id_or_none:
                    from modules.operations.taskings.windows import open_task_detail_window
                    open_task_detail_window(int(task_id_or_none))
                elif team_name_or_none:
                    from modules.operations.teams.windows import open_team_detail_window
                    open_team_detail_window(None)
            except Exception as exc:
                print(f"[warn] reassign action failed: {exc}")

        w.reassignRequested.connect(_reassign)

        def _mark_complete(task_id: str) -> None:
            try:
                from modules.operations.data.repository import set_task_status
                set_task_status(int(task_id), "complete")
                _refresh()
            except Exception as exc:
                print(f"[warn] mark complete failed: {exc}")

        w.markCompleteRequested.connect(_mark_complete)

        w.openFullDashboardRequested.connect(self.open_operations_dashboard)
        w.view214LogRequested.connect(self.open_operations_unit_log)

        def _export_214() -> None:
            try:
                from modules.operations.taskings.repository import export_audit_csv
                path = export_audit_csv()
                try:
                    QMessageBox.information(self, "Exported 214", f"Audit CSV saved to:\n{path}")
                except Exception:
                    print(f"[info] Audit CSV saved to: {path}")
            except Exception as exc:
                print(f"[warn] export 214 failed: {exc}")

        w.export214Requested.connect(_export_214)

        def _print_204() -> None:
            # Open Assignments Dashboard for printing controls; specialized print flows live there
            self.open_operations_dashboard()

        w.print204Requested.connect(_print_204)

        def _ack_alerts() -> None:
            # No-op placeholder; application may implement read/unread later
            try:
                QMessageBox.information(self, "Alerts", "Acknowledged recent alerts.")
            except Exception:
                pass

        w.acknowledgeAlertsRequested.connect(_ack_alerts)
        w.refreshRequested.connect(lambda: _refresh())

        # Refresh function using live data
        def _refresh() -> None:
            # Overlay if no active incident
            try:
                active_id = incident_context.get_active_incident_id()
                w.setIncidentOverlayVisible(False if active_id else True)
            except Exception:
                w.setIncidentOverlayVisible(True)
                return

            # Context header
            try:
                op = AppState.get_active_op_period() or "—"
                role = AppState.get_active_user_role() or "—"
            except Exception:
                op, role = "—", "—"
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
            w.set_context(str(op), now_text, str(role))

            from utils.api_client import api_client
            iid = str(active_id)

            # KPIs via tasks API
            k_active = k_due = k_assigned = k_available = k_blocking = 0
            try:
                all_tasks = api_client.get(f"/api/incidents/{iid}/operations/tasks") or []
                closed = {"complete", "completed", "cancelled", "canceled"}
                def _parse(dtstr):
                    try:
                        dt = datetime.fromisoformat(str(dtstr))
                        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        return None
                open_tasks = [t for t in all_tasks if (t.get("status") or "").strip().lower() not in closed]
                k_active = len(open_tasks)
                now = datetime.now(timezone.utc)
                in2h = now + timedelta(hours=2)
                k_due = sum(1 for t in open_tasks if (p := _parse(t.get("due_time"))) and now <= p <= in2h)
            except Exception:
                open_tasks = []

            # Teams snapshot via API
            try:
                teams = api_client.get(f"/api/incidents/{iid}/teams") or []
                def _has_task(t):
                    return bool(t.get("task_id") or t.get("assignment"))
                k_assigned = sum(1 for t in teams if _has_task(t))
                k_available = sum(1 for t in teams if not _has_task(t))
                k_blocking = sum(1 for t in teams if t.get("needs_assistance") or t.get("emergency"))
                w.update_team_snapshot([
                    {
                        "name": t.get("team_name") or "Team",
                        "status": str(t.get("status") or "").title(),
                        "assigned": t.get("assignment") or "",
                        "leader": t.get("leader") or "",
                        "last_checkin_at": t.get("last_checkin_ts") or "",
                    }
                    for t in teams[:6]
                ])
            except Exception as exc:
                print(f"[warn] teams API failed: {exc}")

            w.update_kpis({
                "active_tasks": k_active,
                "due_2h": k_due,
                "teams_assigned": k_assigned,
                "teams_available": k_available,
                "blocking_issues": k_blocking,
                "new_debriefs": 0,
            })

            # Alerts (last 30 min) via API
            try:
                audit_rows = api_client.get(f"/api/incidents/{iid}/audit-log", params={"limit": 100}) or []
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
                alerts = []
                for r in audit_rows:
                    ts = r.get("ts_utc") or r.get("timestamp") or ""
                    try:
                        dt = datetime.fromisoformat(str(ts)) if ts else None
                        if dt and dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        dt = None
                    if dt is not None and dt >= cutoff:
                        msg = r.get("action") or "Audit"
                        who = r.get("changed_by_display") or ""
                        if who:
                            msg = f"{msg} — {who}"
                        alerts.append({"id": r.get("id"), "ts": ts[-8:] if ts else "", "message": msg})
                w.update_alerts(alerts[:8])
            except Exception as exc:
                print(f"[warn] audit-log API failed: {exc}")

            # Top Tasks (open, sorted by priority desc then soonest due)
            try:
                def _prio(v):
                    try: return int(v)
                    except Exception: return 0
                def _due_val(v):
                    try:
                        dt = datetime.fromisoformat(str(v)) if v else None
                        return dt or datetime.max.replace(tzinfo=None)
                    except Exception:
                        return datetime.max.replace(tzinfo=None)
                sorted_tasks = sorted(open_tasks, key=lambda t: (-_prio(t.get("priority")), _due_val(t.get("due_time"))))
                w.update_top_tasks([
                    {
                        "id": t.get("task_id") or t.get("id", ""),
                        "title": t.get("title") or "(untitled)",
                        "assignee": t.get("assignment") or "",
                        "due": (str(t.get("due_time") or ""))[-5:],
                        "priority": t.get("priority"),
                        "status": t.get("status") or "",
                    }
                    for t in sorted_tasks[:5]
                ])
            except Exception as exc:
                print(f"[warn] top tasks failed: {exc}")

            # Comms snapshot via API
            try:
                channels = api_client.get(f"/api/incidents/{iid}/channels") or []
                w.update_comms_snapshot([
                    {"name": c.get("name") or "", "role": c.get("function") or c.get("mode") or "", "status": "OK"}
                    for c in channels[:5]
                ])
            except Exception as exc:
                print(f"[warn] comms API failed: {exc}")

        # Initial refresh and subscriptions
        _refresh()
        try:
            app_signals.incidentChanged.connect(lambda *_: _refresh())
            app_signals.opPeriodChanged.connect(lambda *_: _refresh())
            app_signals.userChanged.connect(lambda *_: _refresh())
            app_signals.teamStatusChanged.connect(lambda *_: _refresh())
            app_signals.taskHeaderChanged.connect(lambda *_: _refresh())
            app_signals.messageLogged.connect(lambda *_1, _2: _refresh())
        except Exception:
            pass
        # Auto-refresh every 60s by default
        try:
            w.setAutoRefresh(60000)
        except Exception:
            pass

    def open_operations_section_org(self) -> None:
        incident_id = AppState.get_active_incident()
        if not incident_id:
            QMessageBox.warning(self, "Operations Section Organization", "No active incident.")
            return
        try:
            from modules.command.incident_organization.windows.ops_section_window import (
                OperationsSectionWindow,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Operations Section Organization", f"Could not load window.\n{exc}")
            return
        win = OperationsSectionWindow(str(incident_id), self)
        win.show()
        win.raise_()
        win.activateWindow()

    def open_operations_team_assignments(self) -> None:
        from modules import operations
        incident_id = AppState.get_active_incident()
        panel = operations.get_team_assignments_panel(incident_id)
        self._open_panel(panel, title="Team Assignments")

    def open_operations_team_status(self) -> None:

        try:
            from modules.operations.panels.team_status_panel import TeamStatusPanel
            panel = TeamStatusPanel(self)
            self._open_dock_widget(panel, title="Team Status")
            return
        except Exception as e:
            try:
                QMessageBox.warning(self, "Team Status", f"Team Status panel could not be loaded.\n{e}")
            except Exception:
                print(f"[warn] Team Status panel could not be loaded: {e}")

    def open_operations_task_board(self) -> None:

        try:
            from modules.operations.panels.task_status_panel import TaskStatusPanel
            panel = TaskStatusPanel(self)
            self._open_dock_widget(panel, title="Task Status")
            return
        except Exception as e:
            try:
                QMessageBox.warning(self, "Task Status", f"Task Status panel could not be loaded.\n{e}")
            except Exception:
                print(f"[warn] Task Status panel could not be loaded: {e}")

    def open_operations_narrative(self) -> None:
        # No separate Narrative window; use the Task Detail window's Narrative tab.
        try:
            QMessageBox.information(self, "Narrative", "Narrative is managed within each Task's detail window.")
        except Exception:
            print("[info] Narrative is managed within each Task's detail window.")

    # legacy UI debug helpers removed to allow running without legacy UI assets

# --- 4.6 Logistics -------------------------------------------------------
    def open_logistics_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:logistics",
            "default_log_name": "Logistics",
            "default_prepared_by_position": "Logistics Section Chief",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Logistics", preferred_size=(950, 600))

    def open_logistics_dashboard(self) -> None:
        """Open the Logistics Dashboard (modeless) and enable auto-refresh."""
        try:
            from modules.logistics.panels.logdashboard import (
                make_logistics_dashboard,
                LogisticsDashboardWidget,
            )
        except Exception as e:
            try:
                QMessageBox.warning(self, "Logistics Dashboard", f"Widget unavailable.\n{e}")
            except Exception:
                print(f"[warn] LogisticsDashboardWidget unavailable: {e}")
            return

        widget: LogisticsDashboardWidget = make_logistics_dashboard(self)
        # Wire signals and a basic refresh function (time/role/overlay)
        self._wire_logistics_dashboard(widget)
        # Reasonable default refresh interval
        try:
            widget.setAutoRefresh(15000)
        except Exception:
            pass
        # Show as a docked, modeless panel for consistency with app UX
        self._open_panel(widget, title="Logistics Dashboard")

    def _wire_logistics_dashboard(self, w) -> None:
        """Attach handlers and simple refresh that updates header context.

        This keeps the widget useful before full Logistics data plumbing exists.
        """
        from utils.state import AppState
        from utils import incident_context
        from datetime import datetime

        # Button/signal wiring (minimal useful mapping)
        try:
            w.new213RRRequested.connect(self.open_logistics_213rr)
        except Exception:
            pass
        try:
            w.newCheckInRequested.connect(self.open_logistics_211)
            w.open211_218Requested.connect(self.open_logistics_211)
        except Exception:
            pass
        try:
            w.openQueueRequested.connect(self.open_logistics_requests)
        except Exception:
            pass
        try:
            w.openDemobBoardRequested.connect(lambda: QMessageBox.information(self, "Demob", "Demob board not implemented yet."))
        except Exception:
            pass
        try:
            w.acknowledgeAlertsRequested.connect(lambda: QMessageBox.information(self, "Alerts", "Acknowledged recent alerts."))
        except Exception:
            pass
        try:
            w.openFullDashboardRequested.connect(self.open_logistics_dashboard)
        except Exception:
            pass

        # Refresh function focused on header + safe defaults
        def _refresh() -> None:
            try:
                active_id = incident_context.get_active_incident_id()
                w.setIncidentOverlayVisible(False if active_id else True)
            except Exception:
                w.setIncidentOverlayVisible(True)
                return

            try:
                op = AppState.get_active_op_period() or "—"
            except Exception:
                op = "—"
            try:
                role = AppState.get_active_user_role() or "—"
            except Exception:
                role = "—"
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
            try:
                w.set_context(str(op), now_text, str(role))
            except Exception:
                pass

            # Fill with safe defaults until Logistics data wiring exists
            try:
                w.update_kpis({
                    "open_requests": 0,
                    "approvals_pending": 0,
                    "low_stock_alerts": 0,
                    "checkins_today": 0,
                    "vehicles_ready": "0/0",
                    "facilities_ok": "0/0",
                })
            except Exception:
                pass

        try:
            w.refreshRequested.connect(lambda: _refresh())
        except Exception:
            pass
        # Prime the header immediately on open
        _refresh()

    def open_logistics_211(self) -> None:
        from modules import logistics
        incident_id = AppState.get_active_incident()
        panel = logistics.get_checkin_panel(incident_id)
        self._open_panel(panel, title="Check-In (ICS-211)")

    def open_logistics_requests(self) -> None:
        from modules import logistics
        incident_id = AppState.get_active_incident()
        panel = logistics.get_requests_panel(incident_id)
        self._open_panel(panel, title="Resource Requests")

    def open_logistics_resource_status(self) -> None:
        from modules import logistics
        incident_id = AppState.get_active_incident()
        panel = logistics.get_resource_status_board_panel(incident_id)
        self._open_panel(panel, title="Resource Status Board")

    def open_logistics_213rr(self) -> None:
        from modules import logistics
        incident_id = AppState.get_active_incident()
        panel = logistics.get_213rr_panel(incident_id)
        self._open_panel(panel, title="Resource Request (ICS-213RR)")

# --- 4.7 Communications --------------------------------------------------
    def open_comms_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:communications",
            "default_log_name": "Communications",
            "default_prepared_by_position": "Communications Unit Leader",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Communications", preferred_size=(950, 600))

    def open_comms_traffic_log(self) -> None:
        from modules.communications.panels import MessageLogPanel

        incident_id = AppState.get_active_incident()
        panel = MessageLogPanel(self, incident_id=incident_id)
        self._open_panel(panel, title="Communications Dashboard")

    def open_comms_chat(self) -> None:
        from modules.communications.panels import MessageLogPanel

        # TODO: incident-specific scoping for communications panels
        _incident_id = AppState.get_active_incident()
        panel = MessageLogPanel(self, incident_id=_incident_id)
        self._open_panel(panel, title="Messaging")

    def open_comms_213(self) -> None:
        from modules.communications.panels import MessageLogPanel

        # TODO: incident-specific scoping for communications panels
        _incident_id = AppState.get_active_incident()
        panel = MessageLogPanel(self, incident_id=_incident_id)
        self._open_panel(panel, title="ICS 213 Messages")

    def open_notifications_panel(self) -> None:
        from notifications.panels.notifications_panel import get_notifications_panel
        panel = get_notifications_panel(parent=self)
        self._open_dock_widget(panel, title="Notification Feed", preferred_size=(480, 600))

    def open_comms_205(self) -> None:
        # Open standalone ICS-205 window (Widgets only, non-dockable)
        from modules.communications import create_ics205_window

        # Create as standalone (no docking, no parent) per spec
        # Parent to main window to ensure proper Qt thread affinity/ownership
        win = create_ics205_window(self)
        self._register_child_window(win)
        win.show()

    def open_comms_log_board(self) -> None:
        # Dockable table-focused log board
        from modules.communications.traffic_log import create_log_board_window

        incident_id = AppState.get_active_incident()
        panel = create_log_board_window(self, incident_id=incident_id)
        self._open_panel(panel, title="Communications Log Board")

    def open_comms_log_entry(self) -> None:
        from modules.communications.traffic_log import create_log_entry_window

        incident_id = AppState.get_active_incident()
        window = create_log_entry_window(self, incident_id=str(incident_id) if incident_id else None)
        self._open_panel(window, title="Log & Entry")

    def open_comms_quick_entry(self) -> None:
        # Dockable quick entry panel
        from modules.communications.traffic_log import create_quick_entry_window

        incident_id = AppState.get_active_incident()
        panel = create_quick_entry_window(self, incident_id=incident_id)
        self._open_dock_widget(panel, title="New Communications Entry")

    def _register_child_window(self, window):
        if window is None:
            return
        try:
            if window in self._child_windows:
                return
            self._child_windows.append(window)
        except Exception:
            self._child_windows = [window]

        def _cleanup(*_args):
            try:
                self._child_windows = [w for w in self._child_windows if w is not window]
            except Exception:
                self._child_windows = []

        try:
            window.destroyed.connect(_cleanup)
        except Exception:
            pass

# --- 4.8 Intel -----------------------------------------------------------
    def open_intel_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:intel",
            "default_log_name": "Intelligence",
            "default_prepared_by_position": "Intelligence Section Chief",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Intelligence", preferred_size=(950, 600))

    def open_intel_module(self, tab: str | None = None) -> None:
        """Open (or raise) the Intel module window, optionally to a specific tab."""
        from modules.intel import open_intel_window
        open_intel_window(
            incident_id=AppState.get_active_incident(),
            tab=tab,
            parent=self,
        )

# --- 4.9 Medical & Safety -----------------------------------------------
    def open_medical_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:medical",
            "default_log_name": "Medical",
            "default_prepared_by_position": "Medical Unit Leader",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Medical", preferred_size=(950, 600))

    def open_safety_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:safety",
            "default_log_name": "Safety",
            "default_prepared_by_position": "Safety Officer",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Safety", preferred_size=(950, 600))

    def open_medical_206(self) -> None:
        from modules import medical
        incident_id = AppState.get_active_incident()
        panel = medical.get_206_panel(incident_id)
        self._open_panel(panel, title="Medical Plan (ICS-206)")

    def open_safety_208(self) -> None:
        from modules import safety
        incident_id = AppState.get_active_incident()
        panel = safety.get_208_panel(incident_id)
        self._open_panel(panel, title="Safety Message (ICS-208)")

    def open_safety_215A(self) -> None:
        from modules import safety
        incident_id = AppState.get_active_incident()
        panel = safety.get_215A_panel(incident_id)
        self._open_panel(panel, title="Incident Safety Analysis (ICS-215A)")

    def open_safety_caporm(self) -> None:
        from modules import safety
        incident_id = AppState.get_active_incident()
        panel = safety.get_caporm_panel(incident_id)
        self._open_panel(panel, title="CAP ORM")

    def open_safety_iwi(self) -> None:
        from modules import safety
        incident_id = AppState.get_active_incident()
        panel = safety.get_iwi_panel(incident_id)
        self._open_panel(panel, title="Safety Incident Reports")

# --- 4.10 Liaison --------------------------------------------------------
    def open_liaison_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:liaison",
            "default_log_name": "Liaison",
            "default_prepared_by_position": "Liaison Officer",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Liaison", preferred_size=(950, 600))

    def open_liaison_agencies(self) -> None:
        from modules import liaison
        incident_id = AppState.get_active_incident()
        panel = liaison.get_agencies_panel(incident_id)
        self._open_panel(panel, title="Agency Directory")

    def open_liaison_requests(self) -> None:
        from modules import liaison
        incident_id = AppState.get_active_incident()
        panel = liaison.get_requests_panel(incident_id)
        self._open_panel(panel, title="External Coordination")

# --- 4.11 Public Information --------------------------------------------
    def open_public_dashboard(self) -> None:
        from modules import public_information
        from utils.state import AppState
        incident_id = AppState.get_active_incident()
        try:
            uid = AppState.get_active_user_id()
        except Exception:
            uid = None
        try:
            role = AppState.get_active_user_role()
        except Exception:
            role = None
        current_user = {"id": uid, "roles": ([] if not role else [role])}
        public_information.open_pio_window(incident_id, current_user, parent=self)

    def open_public_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:public_information",
            "default_log_name": "Public Information",
            "default_prepared_by_position": "Public Information Officer",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Public Information", preferred_size=(950, 600))

    def open_public_media_releases(self) -> None:
        from modules import public_information
        from utils.state import AppState
        public_information.open_pio_window(AppState.get_active_incident(), tab="Messages / Releases", parent=self)

    def open_public_misinformation(self) -> None:
        from modules import public_information
        from utils.state import AppState
        public_information.open_pio_window(AppState.get_active_incident(), tab="Rumor / Misinformation", parent=self)

    def open_public_inquiries(self) -> None:
        from modules import public_information
        from utils.state import AppState
        public_information.open_pio_window(AppState.get_active_incident(), tab="Media Log", parent=self)

    def open_public_talking_points(self) -> None:
        from modules import public_information
        from utils.state import AppState
        public_information.open_pio_window(AppState.get_active_incident(), tab="Talking Points", parent=self)

    def open_public_templates(self) -> None:
        from modules import public_information
        from utils.state import AppState
        public_information.open_pio_window(AppState.get_active_incident(), tab="Letterhead / Templates", parent=self)

    def open_public_distribution(self) -> None:
        from modules import public_information
        from utils.state import AppState
        public_information.open_pio_window(AppState.get_active_incident(), tab="Distribution Log", parent=self)

# --- 4.12 Finance/Admin --------------------------------------------------
    def open_finance_admin_dashboard(self) -> None:
        """Open the Finance/Admin — Dashboard (modeless) and enable auto-refresh."""
        try:
            from modules.finance.panels.findashboard import (
                make_finance_admin_dashboard,
                FinanceAdminDashboardWidget,
            )
        except Exception as e:
            try:
                QMessageBox.warning(self, "Finance/Admin Dashboard", f"Widget unavailable.\n{e}")
            except Exception:
                print(f"[warn] FinanceAdminDashboardWidget unavailable: {e}")
            return

        widget: FinanceAdminDashboardWidget = make_finance_admin_dashboard()
        widget.setWindowTitle("Finance/Admin — Dashboard")
        widget.setWindowFlags(Qt.Window)
        widget.resize(1000, 800)
        # Wire signals and a basic refresh function (time/role/overlay + placeholders)
        self._wire_finance_admin_dashboard(widget)
        try:
            widget.setAutoRefresh(15000)
        except Exception:
            pass
        widget.show()

    def _wire_finance_admin_dashboard(self, w) -> None:
        """Attach handlers and simple refresh that updates context and placeholders."""
        from utils.state import AppState
        from utils import incident_context
        from datetime import datetime

        # Signal wiring
        try:
            w.openQueueRequested.connect(self.open_finance_procurement)
        except Exception:
            pass
        try:
            w.acknowledgeAlertsRequested.connect(lambda: QMessageBox.information(self, "Alerts", "Acknowledged recent alerts."))
        except Exception:
            pass
        try:
            w.openActionRequested.connect(lambda _id: self.open_finance_procurement())
            w.approveRequested.connect(lambda _id: QMessageBox.information(self, "Approve", f"Approved: {_id}"))
            w.holdRequested.connect(lambda _id: QMessageBox.information(self, "Hold", f"Placed on hold: {_id}"))
        except Exception:
            pass
        try:
            w.openTimekeepingRequested.connect(self.open_finance_time)
        except Exception:
            pass
        try:
            # No dedicated Equipment Use panel yet; route to procurement for now
            w.openEquipmentUseRequested.connect(self.open_finance_procurement)
        except Exception:
            pass
        try:
            w.openReimbursementsRequested.connect(self.open_finance_summary)
        except Exception:
            pass
        try:
            w.newPurchaseOrderRequested.connect(self.open_finance_procurement)
            w.newTimeEntryRequested.connect(self.open_finance_time)
            w.newEquipmentRecordRequested.connect(self.open_finance_procurement)
        except Exception:
            pass
        try:
            w.openBudgetRequested.connect(self.open_finance_summary)
            w.exportCostSummaryRequested.connect(lambda: QMessageBox.information(self, "Export", "Exported cost summary (placeholder)."))
            w.openFullFinanceAdminRequested.connect(self.open_finance_admin_dashboard)
        except Exception:
            pass

        def _refresh() -> None:
            # Overlay visibility based on active incident
            try:
                active_id = incident_context.get_active_incident_id()
                w.setIncidentOverlayVisible(False if active_id else True)
            except Exception:
                w.setIncidentOverlayVisible(True)
                return

            # Header context
            try:
                op = AppState.get_active_op_period() or "—"
            except Exception:
                op = "—"
            try:
                role = AppState.get_active_user_role() or "—"
            except Exception:
                role = "—"
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M")
            try:
                w.set_context(str(op), now_text, str(role))
            except Exception:
                pass

            # Placeholder data until real wiring exists
            try:
                w.update_kpis({
                    "pos_open": 0,
                    "invoices_pending": 0,
                    "reimburse_pending": 0,
                    "budget_remaining": "—",
                    "cost_op_today": "—",
                    "overtime_hours": "—",
                })
            except Exception:
                pass
            try:
                w.update_alerts([])
            except Exception:
                pass
            try:
                w.update_actions([])
            except Exception:
                pass
            try:
                w.update_finance_snapshot({
                    "ops_cost_today": "—",
                    "ops_cost_to_date": "—",
                    "budget_total": "—",
                    "budget_used": "—",
                    "budget_remaining": "—",
                    "sections_over_cap": [],
                })
            except Exception:
                pass
            try:
                w.update_time_equip({
                    "time_entries_today": 0,
                    "crews_pending": 0,
                    "equipment_hours_today": "0h",
                    "equipment_pending": 0,
                })
            except Exception:
                pass
            try:
                w.update_reimburse_queue([])
            except Exception:
                pass

        try:
            w.refreshRequested.connect(lambda: _refresh())
        except Exception:
            pass
        # Prime immediately on open
        _refresh()
    def open_finance_unit_log(self) -> None:
        from modules import ics214
        incident_id = AppState.get_active_incident()
        panel = ics214.get_ics214_panel(incident_id, launch_context={
            "default_log_for_type": "section",
            "default_log_for_ref": "section:finance_admin",
            "default_log_name": "Finance / Admin",
            "default_prepared_by_position": "Finance/Admin Section Chief",
        })
        self._open_dock_widget(panel, title="ICS-214 Activity Log — Finance/Admin", preferred_size=(950, 600))

    def open_finance_time(self) -> None:
        from modules import finance
        incident_id = AppState.get_active_incident()
        panel = finance.get_time_panel(incident_id)
        self._open_panel(panel, title="Time Tracking")

    def open_finance_procurement(self) -> None:
        from modules import finance
        incident_id = AppState.get_active_incident()
        panel = finance.get_procurement_panel(incident_id)
        self._open_panel(panel, title="Expenses && Procurement")

    def open_finance_summary(self) -> None:
        from modules import finance
        incident_id = AppState.get_active_incident()
        panel = finance.get_summary_panel(incident_id)
        self._open_panel(panel, title="Cost Summary")

# --- 4.13 Toolkits -------------------------------------------------------
    def open_toolkit_sar_missing_person(self) -> None:
        from modules.sartoolkit import sar
        incident_id = AppState.get_active_incident()
        panel = sar.get_missing_person_panel(incident_id)
        self._open_panel(panel, title="Missing Person Toolkit")

    def open_toolkit_sar_pod(self) -> None:
        from modules.sartoolkit import sar
        incident_id = AppState.get_active_incident()
        panel = sar.get_pod_panel(incident_id)
        self._open_panel(panel, title="POD Calculator")

    def open_toolkit_disaster_damage(self) -> None:
        from modules.disasterresponse import disaster
        incident_id = AppState.get_active_incident()
        panel = disaster.get_damage_panel(incident_id)
        self._open_panel(panel, title="Damage Assessment")

    def open_toolkit_disaster_urban_interview(self) -> None:
        from modules.disasterresponse import disaster
        incident_id = AppState.get_active_incident()
        panel = disaster.get_urban_interview_panel(incident_id)
        self._open_panel(panel, title="Urban Interview Log")

    def open_toolkit_disaster_photos(self) -> None:
        from modules.disasterresponse import disaster
        incident_id = AppState.get_active_incident()
        panel = disaster.get_photos_panel(incident_id)
        self._open_panel(panel, title="Damage Photos")


    def open_toolkit_projection_dashboard(self) -> None:
        from modules import projection_dashboard
        incident_id = AppState.get_active_incident()
        panel = projection_dashboard.get_projection_dashboard_panel(incident_id)
        self._open_panel(panel, title="Projection Dashboard")
    def open_planned_promotions(self) -> None:
        from modules import plannedtoolkit
        incident_id = AppState.get_active_incident()
        panel = plannedtoolkit.get_promotions_panel(incident_id)
        self._open_panel(panel, title="External Messaging")

    def open_planned_vendors(self) -> None:
        from modules import plannedtoolkit
        incident_id = AppState.get_active_incident()
        panel = plannedtoolkit.get_vendors_panel(incident_id)
        self._open_panel(panel, title="Vendors && Permits")

    def open_planned_safety(self) -> None:
        from modules import plannedtoolkit
        incident_id = AppState.get_active_incident()
        panel = plannedtoolkit.get_safety_panel(incident_id)
        self._open_panel(panel, title="Public Safety")

    def open_planned_tasking(self) -> None:
        from modules import plannedtoolkit
        incident_id = AppState.get_active_incident()
        panel = plannedtoolkit.get_tasking_panel(incident_id)
        self._open_panel(panel, title="Tasking && Assignments")

    def open_planned_health_sanitation(self) -> None:
        from modules import plannedtoolkit
        incident_id = AppState.get_active_incident()
        panel = plannedtoolkit.get_health_sanitation_panel(incident_id)
        self._open_panel(panel, title="Health && Sanitation")

    def open_toolkit_initial_hasty(self) -> None:
        from modules.initialresponse import initial
        incident_id = AppState.get_active_incident()
        panel = initial.get_hasty_panel(incident_id)
        self._open_panel(panel, title="Early Tasking", preferred_size=(1000, 800))

    def open_toolkit_initial_overview(self) -> None:
        from modules.initialresponse import initial
        incident_id = AppState.get_active_incident()
        panel = initial.get_initialresponse_panel(incident_id)
        self._open_panel(panel, title="Initial Information", preferred_size=(1000, 800))

# --- 4.14 Reference Library (Forms) -----------------------------------
    def open_reference_library(self) -> None:
        from modules import referencelibrary
        incident_id = AppState.get_active_incident()
        panel = referencelibrary.get_library_panel()
        self._open_panel(panel, title="Reference Library")

    def open_help_user_guide(self) -> None:
        from modules import referencelibrary
        incident_id = AppState.get_active_incident()
        panel = referencelibrary.get_user_guide_panel(incident_id)
        self._open_panel(panel, title="User Guide")

# --- 4.15 Help -----------------------------------------------------------
    def open_help_about(self) -> None:
        from modules import referencelibrary
        incident_id = AppState.get_active_incident()
        panel = referencelibrary.get_about_panel(incident_id)
        self._open_panel(panel, title="About SARApp")

# ===== Part 5: Shared Windows, Helpers & Utilities =======================
    def _open_panel(self, widget: QWidget, title: str, preferred_size: tuple[int, int] | None = None) -> None:
        """Open widget as a plain floating OS window — no ADS docking, no snap behaviour."""
        widget.setWindowTitle(title)
        widget.setWindowFlag(Qt.WindowType.Window, True)
        try:
            widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        except Exception:
            pass
        if preferred_size:
            try:
                widget.resize(preferred_size[0], preferred_size[1])
            except Exception:
                pass
        else:
            try:
                widget.resize(900, 650)
            except Exception:
                pass

        # Cascading placement: each window opens offset from the previous one
        try:
            geo = self.geometry()
            screen = self.screen().availableGeometry() if self.screen() else geo
            step = 32
            if not hasattr(self, "_panel_cascade_index"):
                self._panel_cascade_index = 0
            offset = self._panel_cascade_index * step
            # Reset cascade when the next window would clip off the bottom-right of the screen
            max_x = screen.x() + screen.width() - widget.width() - step
            max_y = screen.y() + screen.height() - widget.height() - step
            base_x = geo.x() + (geo.width() - widget.width()) // 2
            base_y = geo.y() + (geo.height() - widget.height()) // 2
            if base_x + offset > max_x or base_y + offset > max_y:
                self._panel_cascade_index = 0
                offset = 0
            widget.move(base_x + offset, base_y + offset)
            self._panel_cascade_index += 1
        except Exception:
            pass

        widget.show()
        try:
            widget.raise_()
            widget.activateWindow()
        except Exception:
            pass

        if not hasattr(self, "_panel_windows"):
            self._panel_windows: list[QWidget] = []
        self._panel_windows.append(widget)

        def _cleanup() -> None:
            if hasattr(self, "_panel_windows") and widget in self._panel_windows:
                self._panel_windows.remove(widget)

        widget.destroyed.connect(lambda _=None: _cleanup())

    def _open_standalone_widget(self, widget: QWidget, title: str, preferred_size: tuple[int, int] | None = None) -> None:
        widget.setWindowTitle(title)
        try:
            widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        except Exception:
            pass
        if preferred_size:
            try:
                widget.resize(preferred_size[0], preferred_size[1])
            except Exception:
                pass
        widget.show()
        try:
            widget.raise_()
            widget.activateWindow()
        except Exception:
            pass

        if not hasattr(self, "_standalone_widgets"):
            self._standalone_widgets: list[QWidget] = []
        self._standalone_widgets.append(widget)

        def _cleanup() -> None:
            if hasattr(self, "_standalone_widgets") and widget in self._standalone_widgets:
                self._standalone_widgets.remove(widget)

        widget.destroyed.connect(lambda _=None: _cleanup())

    def _open_dock_widget(self, widget: QWidget, title: str, float_on_open: bool | None = True, preferred_size: tuple[int, int] | None = None) -> None:
        """Embed widget in an ADS dock panel.
        By default, menu-launched panels open floating (undocked). Use float_on_open=False to dock.
        """
        dock = CDockWidget(self.dock_manager, title)
        dock.setWidget(widget)
        if float_on_open:
            # Preferred: directly add as floating if ADS supports it
            try:
                self.dock_manager.addDockWidgetFloating(dock)  # type: ignore[attr-defined]
                dock.show()
                if preferred_size:
                    try:
                        dock.floatingDockContainer().resize(preferred_size[0], preferred_size[1])  # type: ignore[attr-defined]
                    except Exception:
                        pass
                return
            except Exception:
                pass
            # Alternate: create an explicit floating container
            try:
                container = self.dock_manager.createFloatingDockContainer(dock)  # type: ignore[attr-defined]
                try:
                    from PySide6.QtGui import QCursor
                    container.move(QCursor.pos())  # type: ignore[attr-defined]
                except Exception:
                    pass
                if preferred_size:
                    container.resize(preferred_size[0], preferred_size[1])
                try:
                    container.show()  # type: ignore[attr-defined]
                except Exception:
                    pass
                return
            except Exception:
                # Fallback: add then toggle floating
                area = CenterDockWidgetArea if not self.findChildren(CDockWidget) else LeftDockWidgetArea
                self.dock_manager.addDockWidget(area, dock)
                try:
                    dock.setFloating(True)
                except Exception:
                    pass
                dock.show()
                return
        # Docked open
        area = CenterDockWidgetArea if not self.findChildren(CDockWidget) else LeftDockWidgetArea
        self.dock_manager.addDockWidget(area, dock)
        dock.show()




    def closeEvent(self, event) -> None:  # type: ignore[override]
        # Save perspectives via QSettings to match ADS API
        try:
            self.dock_manager.addPerspective("default")
            settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
            self.dock_manager.savePerspectives(settings_obj)
        except Exception as e:
            logger.warning("Failed to save ADS perspectives: %s", e)
        super().closeEvent(event)

    def _create_default_docks(self) -> None:
        """Create a few sample docks (Mission Status, Team Status, Task Status)."""
        # Use full-featured panels for default docks
        try:
            from modules.operations.panels.team_status_panel import TeamStatusPanel
        except Exception:
            TeamStatusPanel = None  # type: ignore
        try:
            from modules.operations.panels.task_status_panel import TaskStatusPanel
        except Exception:
            TaskStatusPanel = None  # type: ignore

        # Mission Status dock uses the active_incident_label prepared in __init__
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.addWidget(self.active_incident_label)
        status_layout.addWidget(self.connection_status_label)
        # Make Mission Status the central area so other docks can dock around the window
        status_dock = CDockWidget(self.dock_manager, "Mission Status")
        status_dock.setWidget(status_container)
        self.dock_manager.addDockWidget(CenterDockWidgetArea, status_dock)
        status_dock.show()

        # Optional sample boards: prefer QWidget panels; fallback to legacy UI
        if TeamStatusPanel:
            try:
                team_panel = TeamStatusPanel(self)
                team_dock = CDockWidget(self.dock_manager, "Team Status")
                team_dock.setWidget(team_panel)
                self.dock_manager.addDockWidget(LeftDockWidgetArea, team_dock)
                team_dock.show()
            except Exception:
                pass
        else:
            QMessageBox.warning(self, "Team Status", "Team Status is unavailable in this build.")

        if TaskStatusPanel:
            try:
                task_panel = TaskStatusPanel(self)
                task_dock = CDockWidget(self.dock_manager, "Task Status")
                task_dock.setWidget(task_panel)
                self.dock_manager.addDockWidget(BottomDockWidgetArea, task_dock)
                task_dock.show()
            except Exception:
                pass
        else:
            QMessageBox.warning(self, "Task Status", "Task Status is unavailable in this build.")

    def open_new_workspace_window(self) -> None:
        """Create a blank floating dock window you can move to another monitor.
        Other panels can be docked into it by dragging.
        """
        # Minimal placeholder instructing the user
        placeholder_widget = QWidget()
        v = QVBoxLayout(placeholder_widget)
        v.setContentsMargins(24, 24, 24, 24)
        lbl = QLabel("Drop panels here")
        v.addWidget(lbl)

        placeholder = CDockWidget(self.dock_manager, "Workspace")
        placeholder.setWidget(placeholder_widget)

        # Prefer creating a true floating dock container if ADS supports it
        try:
            container = self.dock_manager.createFloatingDockContainer(placeholder)  # type: ignore[attr-defined]
            try:
                from PySide6.QtGui import QCursor
                container.move(QCursor.pos())  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                container.show()  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            # Fallback: add and float the placeholder dock itself
            self.dock_manager.addDockWidget(LeftDockWidgetArea, placeholder)
            try:
                placeholder.setFloating(True)
            except Exception:
                pass
            placeholder.show()

    def _reset_layout(self) -> None:
        """Clear current perspectives and rebuild default docks."""
        try:
            # Try to remove perspectives by saving empty
            settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
            # Overwrite with nothing and clear the file
            settings_obj.clear()
        except Exception:
            pass
        # Remove existing dock widgets (best-effort)
        for dw in list(self.findChildren(CDockWidget)):
            try:
                dw.close()
                dw.deleteLater()
            except Exception:
                pass
        self._create_default_docks()

    def _clear_all_docks(self) -> None:
        """Close and delete every open CDockWidget without rebuilding defaults."""
        for dw in list(self.findChildren(CDockWidget)):
            try:
                dw.close()
                dw.deleteLater()
            except Exception:
                pass

    def _open_widget_in_area(self, widget_id: str, area) -> None:
        """Instantiate a registered widget and dock it in the given ADS area."""
        from ui.widgets import registry as W
        spec = W.REGISTRY.get(widget_id)
        if not spec or not spec.component:
            return
        try:
            comp = spec.component() if callable(spec.component) else spec.component
            if comp is None:
                return
        except Exception:
            return
        dock = CDockWidget(self.dock_manager, spec.title)
        dock.setWidget(comp)
        self.dock_manager.addDockWidget(area, dock)
        dock.show()

    def _apply_section_layout(self, section_id: str) -> None:
        """Clear all docks and open the preset layout for section_id."""
        from ui.widgets.section_layouts import SECTION_LAYOUTS
        _AREA_MAP = {
            "center": CenterDockWidgetArea,
            "left":   LeftDockWidgetArea,
            "right":  RightDockWidgetArea,
            "bottom": BottomDockWidgetArea,
            "top":    TopDockWidgetArea,
        }
        entry = SECTION_LAYOUTS.get(section_id)
        if not entry:
            return
        self._clear_all_docks()
        for widget_id, area_key in entry["widgets"]:
            self._open_widget_in_area(widget_id, _AREA_MAP.get(area_key, CenterDockWidgetArea))

    def _rebuild_layouts_menu(self, menu: QMenu) -> None:
        """Rebuild the Section Layouts submenu (built-ins + user-saved templates)."""
        from ui.widgets.section_layouts import SECTION_LAYOUTS
        menu.clear()
        for section_id, entry in SECTION_LAYOUTS.items():
            act = QAction(entry["label"], self)
            act.triggered.connect(lambda checked=False, s=section_id: self._apply_section_layout(s))
            menu.addAction(act)
        menu.addSeparator()
        act_save = QAction("Save Current as Template…", self)
        act_save.triggered.connect(self._save_current_as_template)
        menu.addAction(act_save)
        try:
            saved = [n for n in self.dock_manager.perspectiveNames() if n != "default"]
        except Exception:
            saved = []
        if saved:
            menu.addSeparator()
            for name in saved:
                act = QAction(name, self)
                act.triggered.connect(lambda checked=False, n=name: self.dock_manager.openPerspective(n))
                menu.addAction(act)

    def _save_current_as_template(self) -> None:
        """Prompt for a name, save current dock layout as an ADS perspective."""
        name, ok = QInputDialog.getText(self, "Save Template", "Template name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        try:
            self.dock_manager.removePerspective(name)
        except Exception:
            pass
        self.dock_manager.addPerspective(name)
        settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
        self.dock_manager.savePerspectives(settings_obj)

    def open_customization_layout_manager(self) -> None:
        if get_layout_manager_panel is None:
            QMessageBox.warning(self, "Customization", "Layout manager unavailable.")
            return
        try:
            panel = get_layout_manager_panel(self)
        except Exception as exc:
            QMessageBox.warning(self, "Customization", f"Failed to open layout manager: {exc}")
            return
        self._open_panel(panel, title="Layout Templates")

    def open_customization_dashboard_designer(self) -> None:
        if get_dashboard_designer_panel is None:
            QMessageBox.warning(self, "Customization", "Dashboard designer unavailable.")
            return
        try:
            panel = get_dashboard_designer_panel(self)
        except Exception as exc:
            QMessageBox.warning(self, "Customization", f"Failed to open dashboard designer: {exc}")
            return
        self._open_panel(panel, title="Dashboard Designer")

    def open_customization_theme_editor(self) -> None:
        if get_theme_editor_panel is None:
            QMessageBox.warning(self, "Customization", "Theme designer unavailable.")
            return
        try:
            panel = get_theme_editor_panel(self)
        except Exception as exc:
            QMessageBox.warning(self, "Customization", f"Failed to open theme designer: {exc}")
            return
        self._open_panel(panel, title="Theme Designer")

    def export_customizations_bundle(self) -> None:
        if not self.customization_repo:
            QMessageBox.warning(self, "Customization Export", "Customization services are unavailable.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Customizations",
            "customizations.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            bundle = self.customization_repo.export_bundle()
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(bundle.to_dict(), fh, indent=2)
            QMessageBox.information(self, "Customization Export", f"Exported to {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Customization Export", f"Failed to export: {exc}")

    def import_customizations_bundle(self) -> None:
        if not self.customization_repo:
            QMessageBox.warning(self, "Customization Import", "Customization services are unavailable.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Customizations",
            "",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            from modules.ui_customization.models import CustomizationBundle

            bundle = CustomizationBundle.from_dict(payload)
            self.customization_repo.import_bundle(bundle, replace=False)
            if ui_customization_services is not None:
                try:
                    dock_manager = getattr(self, "dock_manager", None)
                    perspective_file = getattr(self, "_perspective_file", None)
                    if dock_manager and perspective_file:
                        ui_customization_services.ensure_active_layout(
                            self.customization_repo,
                            dock_manager,
                            perspective_file,
                        )
                except Exception as exc:
                    logger.warning("Failed to apply imported layout: %s", exc)
                try:
                    theme_manager = getattr(self, "theme_manager", None)
                    if theme_manager is not None:
                        ui_customization_services.ensure_active_theme(
                            self.customization_repo,
                            theme_manager,
                            getattr(self, "settings_bridge", None),
                        )
                except Exception as exc:
                    logger.warning("Failed to apply imported theme: %s", exc)
            QMessageBox.information(self, "Customization Import", "Import complete.")
        except Exception as exc:
            QMessageBox.warning(self, "Customization Import", f"Failed to import: {exc}")

    def open_display_templates_dialog(self) -> None:
        """Open a modal dialog to manage dock layout templates (ADS perspectives)."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Display Templates")
        v = QVBoxLayout(dlg)

        # List available perspectives
        lst = QListWidget(dlg)
        perspective_names = []
        try:
            perspective_names = list(self.dock_manager.perspectiveNames())
        except Exception:
            perspective_names = []
        for name in perspective_names:
            lst.addItem(name)
        v.addWidget(lst)

        # Buttons: Load, Save As, Delete, Close
        btn_row = QHBoxLayout()
        btn_load = QPushButton("Load")
        btn_save = QPushButton("Save As…")
        btn_delete = QPushButton("Delete")
        btn_close = QPushButton("Close")
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        v.addLayout(btn_row)

        def refresh_list():
            lst.clear()
            try:
                names = list(self.dock_manager.perspectiveNames())
            except Exception:
                names = []
            for nm in names:
                lst.addItem(nm)

        def persist_perspectives():
            try:
                settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                self.dock_manager.savePerspectives(settings_obj)
            except Exception:
                pass

        def on_load():
            item = lst.currentItem()
            if not item:
                return
            name = item.text()
            try:
                self.dock_manager.openPerspective(name)
            except Exception:
                # Fallback: try reloading from disk first then open
                try:
                    settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                    self.dock_manager.loadPerspectives(settings_obj)
                    self.dock_manager.openPerspective(name)
                except Exception:
                    QMessageBox.warning(dlg, "Load Failed", f"Could not load template '{name}'.")

        def on_save():
            name, ok = QInputDialog.getText(dlg, "Save Template", "Template name:")
            if not ok or not str(name).strip():
                return
            name = str(name).strip()
            try:
                # If name exists, remove before adding to overwrite
                try:
                    self.dock_manager.removePerspective(name)
                except Exception:
                    pass
                self.dock_manager.addPerspective(name)
                persist_perspectives()
                refresh_list()
                # Select the saved item
                matches = lst.findItems(name, Qt.MatchExactly)
                if matches:
                    lst.setCurrentItem(matches[0])
            except Exception:
                QMessageBox.warning(dlg, "Save Failed", f"Could not save template '{name}'.")

        def on_delete():
            item = lst.currentItem()
            if not item:
                return
            name = item.text()
            try:
                self.dock_manager.removePerspective(name)
                persist_perspectives()
                refresh_list()
            except Exception:
                # Attempt manual removal via QSettings if ADS API not available
                try:
                    settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
                    settings_obj.beginGroup("perspectives")
                    settings_obj.remove(name)
                    settings_obj.endGroup()
                    persist_perspectives()
                    refresh_list()
                except Exception:
                    QMessageBox.warning(dlg, "Delete Failed", f"Could not delete template '{name}'.")

        btn_load.clicked.connect(on_load)
        btn_save.clicked.connect(on_save)
        btn_delete.clicked.connect(on_delete)
        btn_close.clicked.connect(dlg.accept)

        dlg.setModal(True)
        dlg.adjustSize()
        dlg.exec()

    def set_current_layout_as_default(self) -> None:
        """Capture current dock layout as the 'default' template and persist it."""
        try:
            # Ensure perspectives are loaded from disk first (merges with existing)
            settings_obj = QSettings(self._perspective_file, QSettings.IniFormat)
            try:
                self.dock_manager.loadPerspectives(settings_obj)
            except Exception:
                pass

            # Overwrite any existing 'default' with current layout
            try:
                self.dock_manager.removePerspective("default")
            except Exception:
                pass
            self.dock_manager.addPerspective("default")
            self.dock_manager.savePerspectives(settings_obj)
            QMessageBox.information(self, "Default Saved", "Current layout saved as 'default'.")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", f"Could not set default layout.\n{e}")

    def toggle_dock_lock(self, locked: bool) -> None:
        """Lock/unlock docking so docks can't be dragged or re-arranged."""
        # Preferred: global docking enable/disable on the manager
        try:
            if hasattr(self.dock_manager, "setDockingEnabled"):
                self.dock_manager.setDockingEnabled(not locked)
                return
        except Exception:
            pass

        # Fallback: adjust features on individual dock widgets if available
        for dw in self.findChildren(CDockWidget):
            try:
                # Try common API patterns
                if hasattr(dw, "setMovable"):
                    dw.setMovable(not locked)  # type: ignore[attr-defined]
                if hasattr(dw, "setFloatable"):
                    dw.setFloatable(not locked)  # type: ignore[attr-defined]
                if hasattr(dw, "setClosable"):
                    # Keep closable regardless of lock to avoid trapping users
                    pass
                # ADS specific: toggle features bitmask if present
                if hasattr(dw, "setFeatures") and hasattr(dw, "features"):
                    try:
                        feats = dw.features()
                        # Heuristic: features enum likely has these attributes
                        movable = getattr(type(feats), "DockWidgetMovable", None)
                        floatable = getattr(type(feats), "DockWidgetFloatable", None)
                        if movable is not None:
                            if locked and (feats & movable):
                                feats = feats & (~movable)
                            elif not locked and not (feats & movable):
                                feats = feats | movable
                        if floatable is not None:
                            if locked and (feats & floatable):
                                feats = feats & (~floatable)
                            elif not locked and not (feats & floatable):
                                feats = feats | floatable
                        dw.setFeatures(feats)
                    except Exception:
                        pass
            except Exception:
                pass


    def _wire_connection_status_label(self) -> None:
        """Register as a ConnectionManager listener and set the initial label text."""
        try:
            app = QApplication.instance()
            manager = app.property("sarapp_connection_manager") if app else None
            if manager is not None:
                manager.add_listener(self._on_connection_snapshot)
                self._on_connection_snapshot(manager.snapshot)
            else:
                self.connection_status_label.setText("Connection: —")
        except Exception:
            self.connection_status_label.setText("Connection: —")

    def _on_connection_snapshot(self, snapshot) -> None:
        """Update the connection status label from a ConnectionSnapshot (any thread)."""
        try:
            from core.networking.server_info import ConnectionState
            _STATE_LABELS = {
                ConnectionState.DISCONNECTED: "Disconnected",
                ConnectionState.DISCOVERING: "Discovering…",
                ConnectionState.CONNECTING: "Connecting…",
                ConnectionState.CONNECTED_LAN: "Connected (LAN)",
                ConnectionState.CONNECTED_CLOUD: "Connected (Cloud)",
                ConnectionState.OFFLINE: "Offline Mode",
            }
            state_text = _STATE_LABELS.get(snapshot.state, snapshot.state.value.replace("_", " ").title())
            server = snapshot.server
            if server and snapshot.state in {ConnectionState.CONNECTED_LAN, ConnectionState.CONNECTED_CLOUD}:
                detail = f" — {server.server_name} ({server.host}:{server.port})"
            else:
                detail = f" — {snapshot.message}" if snapshot.message else ""
            text = f"Connection: {state_text}{detail}"
            # Qt widgets must be updated on the main thread.
            QTimer.singleShot(0, lambda: self.connection_status_label.setText(text))
        except Exception:
            pass

    def _init_notifications(self) -> None:
        from notifications.widgets.toast_manager import ToastManager
        from notifications.services.sound_player import SoundPlayer
        toast = ToastManager(parent=self)
        toast.show()
        self._toast_widget = toast

        notifier = get_notifier()
        notifier.showToast.connect(toast.enqueue)

        # Apply persisted sound and threshold settings
        player = SoundPlayer.instance()
        sm = getattr(self, "settings_manager", None)
        if sm is not None:
            from notifications.services.sound_player import CATEGORIES, SEVERITIES, settings_key
            for cat in CATEGORIES:
                for sev in SEVERITIES:
                    val = sm.get(settings_key(cat, sev))
                    if val is not None:
                        player.set_sound(cat, sev, val or None)
                threshold = sm.get(f"notification.threshold.{cat}")
                if threshold:
                    notifier.set_threshold(cat, threshold)
            try:
                player.set_volume(int(sm.get("volume", 75) or 75))
            except Exception:
                pass

    def _on_approval_item_activated(self, entity_type: str, entity_id: str) -> None:
        """Route an inbox click to the relevant module panel."""
        _routes = {
            "ics_205": "comms.205",
            "ics_206": "medical.206",
            "iwi_report": "safety.iwi",
            "iap": "command.iap",
        }
        key = _routes.get(entity_type)
        if key:
            self.open_module(key)

    def _init_status_bar(self) -> None:
        from ui.status_bar import AppStatusBar
        bar = AppStatusBar(self)
        self.setStatusBar(bar)
        self._app_status_bar = bar

        # Wire connection status
        try:
            app = QApplication.instance()
            manager = app.property("sarapp_connection_manager") if app else None
            if manager is not None:
                manager.add_listener(bar.on_connection_snapshot)
                bar.on_connection_snapshot(manager.snapshot)
        except Exception:
            pass

        # Clicking the approvals indicator opens the inbox panel
        bar.approval_indicator_clicked.connect(self.open_planning_approvals)

        # Clicking the messages indicator opens the comms traffic log
        bar.messages_indicator_clicked.connect(self.open_comms_traffic_log)

        bar.start()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        tw = getattr(self, "_toast_widget", None)
        if tw is not None:
            try:
                tw.reflow()
            except Exception:
                pass

    def open_home_dashboard(self) -> None:
        from ui.dashboard.home_dashboard import HomeDashboard
        panel = HomeDashboard(self.settings_manager, customization_repo=self.customization_repo)
        # docked by default
        self._open_dock_widget(panel, title="Home Dashboard", float_on_open=False)

    def open_widget_with_id(self, widget_id: str) -> None:
        """Instantiate a registered widget by id and open it in a dock."""
        try:
            from ui.widgets import registry as W
            from ui.widgets.components import QuickEntryWidget
            from ui.actions.quick_entry_actions import dispatch as qe_dispatch, execute_cli as qe_cli
        except Exception as e:
            QMessageBox.critical(self, "Widgets", f"Widget system unavailable: {e}")
            return

        spec = W.REGISTRY.get(widget_id)
        if not spec:
            QMessageBox.warning(self, "Widgets", f"Unknown widget: {widget_id}")
            return

        # Construct component
        try:
            if widget_id == "quickEntry":
                comp = QuickEntryWidget(qe_dispatch, qe_cli)
            else:
                comp_factory = spec.component
                comp = comp_factory() if callable(comp_factory) else comp_factory  # type: ignore
                if comp is None:
                    raise RuntimeError("Widget component not available")
        except Exception as e:
            QMessageBox.critical(self, spec.title, f"Failed to render widget: {e}")
            return

        self._open_dock_widget(comp, title=spec.title, float_on_open=False)

    def _count_open_tasks(self) -> int:
        """Best-effort count of tasks not complete. Uses sample data fallback."""
        try:
            from data.sample_data import sample_tasks
            return sum(1 for t in sample_tasks if str(getattr(t, 'status', '')).lower() not in {"complete", "completed"})
        except Exception:
            try:
                from data.sample_data import TASK_ROWS, TASK_HEADERS
                si = TASK_HEADERS.index("Status") if "Status" in TASK_HEADERS else 2
                return sum(1 for row in TASK_ROWS if str(row[si]).lower() not in {"complete", "completed"})
            except Exception:
                return 0

    def _count_active_teams(self) -> int:
        """Best-effort count of teams considered active (not Out of Service)."""
        try:
            from data.sample_data import sample_teams
            return sum(1 for t in sample_teams if str(getattr(t, 'status', '')).lower() not in {"out of service", "offline"})
        except Exception:
            try:
                from data.sample_data import TEAM_ROWS, TEAM_HEADERS
                si = TEAM_HEADERS.index("Status") if "Status" in TEAM_HEADERS else 4
                return sum(1 for row in TEAM_ROWS if str(row[si]).lower() not in {"out of service", "offline"})
            except Exception:
                return 0

    def update_title_with_active_incident(self) -> None:
        """Refresh window title and incident label when active incident changes."""
        incident_number = AppState.get_active_incident()
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        suffix = f" — User: {user_id or ''} ({user_role or ''})" if (user_id or user_role) else ""
        if incident_number:
            incident = _get_incident_by_number(incident_number)
            if incident:
                self.setWindowTitle(f"SARApp - {incident['number']}: {incident['name']}{suffix}")
            else:
                self.setWindowTitle(f"SARApp - No Incident Loaded{suffix}")
        else:
            self.setWindowTitle(f"SARApp - No Incident Loaded{suffix}")
        self.update_active_incident_label()

    def update_active_incident_label(self) -> None:
        """Update the status label and menu gates with the current incident."""
        incident_id = AppState.get_active_incident()
        incident = _get_incident_by_number(incident_id) if incident_id else None
        user_id = AppState.get_active_user_id()
        user_role = AppState.get_active_user_role()
        if incident:
            text = f"Incident: {incident['number']} | {incident['name']}  •  User: {user_id or '-'}  •  Role: {user_role or '-'}"
        else:
            text = f"Incident: No Incident Loaded  •  User: {user_id or '-'}  •  Role: {user_role or '-'}"
        if hasattr(self, "active_incident_label"):
            self.active_incident_label.setText(text)
        try:
            self._refresh_toolkit_menu_gates(incident)
        except Exception:
            pass


# Lightweight widget used by the Widgets submenu for simple metrics
class MetricWidget(QWidget):
    """Deprecated simple widget (kept to avoid breaking imports)."""
    def __init__(self, *args, **kwargs):  # pragma: no cover
        super().__init__()
        lab = QLabel("Deprecated widget. Use Home Dashboard.")
        lay = QVBoxLayout(self)
        lay.addWidget(lab)



    # (Deprecated widget openers removed in favor of Home Dashboard)

    def _count_open_tasks(self) -> int:
        """Best-effort count of tasks not complete. Uses sample data fallback."""
        try:
            from data.sample_data import sample_tasks
            return sum(1 for t in sample_tasks if str(getattr(t, 'status', '')).lower() not in {"complete", "completed"})
        except Exception:
            try:
                from data.sample_data import TASK_ROWS, TASK_HEADERS
                si = TASK_HEADERS.index("Status") if "Status" in TASK_HEADERS else 2
                return sum(1 for row in TASK_ROWS if str(row[si]).lower() not in {"complete", "completed"})
            except Exception:
                return 0

    def _count_active_teams(self) -> int:
        """Best-effort count of teams considered active (not Out of Service)."""
        try:
            from data.sample_data import sample_teams
            return sum(1 for t in sample_teams if str(getattr(t, 'status', '')).lower() not in {"out of service", "offline"})
        except Exception:
            try:
                from data.sample_data import TEAM_ROWS, TEAM_HEADERS
                si = TEAM_HEADERS.index("Status") if "Status" in TEAM_HEADERS else 4
                return sum(1 for row in TEAM_ROWS if str(row[si]).lower() not in {"out of service", "offline"})
            except Exception:
                return 0



def _show_connection_fallback_dialog() -> str:
    """Ask the user how SARApp should continue when no server is reachable."""
    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Warning)
    dialog.setWindowTitle("SARApp Connection")
    dialog.setText(
        "No SARApp server was found on the local network, and the cloud server "
        "is unavailable.\n\nWhat would you like to do?"
    )
    start_button = dialog.addButton("Start Local Incident Server", QMessageBox.AcceptRole)
    retry_button = dialog.addButton("Retry Connection", QMessageBox.ActionRole)
    manual_button = dialog.addButton("Manual Server Address", QMessageBox.ActionRole)
    exit_button = dialog.addButton("Exit", QMessageBox.RejectRole)
    dialog.setDefaultButton(start_button)
    dialog.exec()
    clicked = dialog.clickedButton()
    if clicked == start_button:
        return "start_local"
    if clicked == retry_button:
        return "retry"
    if clicked == manual_button:
        return "manual"
    return "exit"


def _parse_manual_server_address(raw: str, default_port: int) -> tuple:
    from urllib.parse import urlparse
    value = raw.strip()
    if not value:
        raise ValueError("Enter a server host or address.")
    parsed = urlparse(value if "://" in value else f"//{value}")
    host = parsed.hostname or value
    port = parsed.port or default_port
    if not str(host).strip():
        raise ValueError("Enter a server host or address.")
    return str(host).strip(), int(port)


def _initialize_connectivity(app: QApplication) -> object | None:
    """Run SARApp's launch connectivity workflow before showing the main window.

    Connectivity is intentionally centralized in ``ConnectionManager`` so UI,
    incident modules, and future sync code can read one state object without
    knowing whether the app reached a LAN server, cloud endpoint, or Offline Mode.
    """
    if str(os.getenv("SARAPP_CONNECTIVITY_DISABLED", "")).strip().lower() in {"1", "true", "yes", "on"}:
        logger.info("SARApp connectivity startup workflow disabled by environment")
        return None

    try:
        from core.networking import (
            ConnectionManager,
            ConnectionState,
            DEFAULT_SERVER_PORT,
            LocalServerController,
            LocalServerError,
            PortUnavailableError,
        )
    except Exception as exc:
        logger.warning("Connectivity framework unavailable: %s", exc)
        return None

    # Cloud server URL — update this if the VPS address changes.
    # Long-term: move this to the Settings UI (Menu → Settings → Connection).
    _HARDCODED_CLOUD_URL = "http://srv1707346.hstgr.cloud:8765"
    cloud_url = os.getenv("SARAPP_CLOUD_URL") or _HARDCODED_CLOUD_URL
    manager = ConnectionManager(cloud_url=cloud_url)
    local_controller = LocalServerController()

    # Keep launch delay short: one broadcast interval is enough to catch an
    # already-running server, and manual connection remains a fallback later.
    snapshot = manager.startup_connect(discovery_timeout_seconds=2.5)

    while snapshot.state == ConnectionState.DISCONNECTED:
        choice = _show_connection_fallback_dialog()

        if choice == "start_local":
            try:
                local_controller.start()
            except PortUnavailableError as exc:
                QMessageBox.critical(None, "Local Server Port Unavailable", str(exc))
                continue
            except LocalServerError as exc:
                QMessageBox.critical(None, "Local Server Failed", str(exc))
                continue

            if not local_controller.wait_until_ready(timeout_seconds=15.0):
                QMessageBox.critical(
                    None,
                    "Local Server Not Ready",
                    "SARApp started the local server, but it did not become available "
                    "before the startup timeout. Check that SARAPP_MONGO_URI is set.",
                )
                continue

            snapshot = manager.connect_manual(local_controller.host, local_controller.port)
            if not snapshot.is_connected:
                QMessageBox.critical(
                    None,
                    "Local Connection Failed",
                    "The local server is running but SARApp could not connect to it.",
                )

        elif choice == "retry":
            snapshot = manager.startup_connect(discovery_timeout_seconds=2.5)
            if snapshot.state == ConnectionState.DISCONNECTED:
                QMessageBox.information(
                    None,
                    "No Server Found",
                    "SARApp still could not find a LAN server or reach the configured cloud server.",
                )

        elif choice == "manual":
            text, accepted = QInputDialog.getText(
                None,
                "Manual Server Address",
                f"Enter SARApp server host or host:port (default port {DEFAULT_SERVER_PORT}):",
            )
            if accepted and text.strip():
                try:
                    host, port = _parse_manual_server_address(text, DEFAULT_SERVER_PORT)
                except ValueError as exc:
                    QMessageBox.warning(None, "Invalid Server Address", str(exc))
                    continue
                snapshot = manager.connect_manual(host, port)
                if not snapshot.is_connected:
                    QMessageBox.warning(
                        None,
                        "Connection Failed",
                        f"SARApp could not verify a compatible server at {host}:{port}.",
                    )

        else:  # exit
            sys.exit(0)

    # Stop the local server child process when the app quits (no-op if we
    # did not start it or if an external server was reused).
    app.aboutToQuit.connect(local_controller.stop)

    app.setProperty("sarapp_connection_manager", manager)
    logger.info("SARApp connectivity startup state: %s", manager.snapshot.state.value)
    return manager


# ===== Part 6: Application Entrypoint =======================================
if __name__ == "__main__":
    import argparse
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _size_title_filter = _WindowSizeTitleFilter()
    app.installEventFilter(_size_title_filter)

    def _on_quit():
        try:
            sid = AppState.get_active_session_id()
            if sid is not None:
                end_session()
                write_audit("session.end", {"session_id": sid}, prefer_mission=False)
        except Exception:
            pass
    app.aboutToQuit.connect(_on_quit)

    # Optional demo mode: relax validation on the login dialog
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--demo", action="store_true", help="Start in demo mode (relaxed login validation)")
    try:
        args, _ = parser.parse_known_args()
    except SystemExit:
        class _Args: demo = False
        args = _Args()

    # Read startup behavior + last incident before showing login.
    # Kept outside the branch so debug bypass startup still has settings_manager.
    _early_settings = SettingsManager()

    if DEBUG_BYPASS_LOGIN:
        from utils import state
        AppState.set_active_incident(DEBUG_INCIDENT_ID)
        AppState.set_active_user_id(DEBUG_USER_ID)
        AppState.set_active_user_role(DEBUG_ROLE)
        print("[debug] Login bypass enabled: loaded test credentials.")
    else:
        # Connectivity must be established before login so the dialog can load incidents.
        _connection_manager = _initialize_connectivity(app)
        from utils.api_client import api_client as _api_client_pre
        from core.networking import ConnectionState as _ConnectionState_pre
        from core.networking.server_info import DEFAULT_SERVER_PORT as _DEFAULT_SERVER_PORT_pre
        if _connection_manager is not None:
            def _on_pre_connection_changed(snapshot) -> None:
                if snapshot.state in {_ConnectionState_pre.CONNECTED_LAN, _ConnectionState_pre.CONNECTED_CLOUD}:
                    _api_client_pre.configure(snapshot.server.base_url)
                elif snapshot.state == _ConnectionState_pre.OFFLINE:
                    _api_client_pre.configure(f"http://localhost:{_DEFAULT_SERVER_PORT_pre}")
            _connection_manager.add_listener(_on_pre_connection_changed)
            _on_pre_connection_changed(_connection_manager.snapshot)

        from modules.login_dialog import LoginDialog
        try:
            _startup_mode = int(_early_settings.get('startupBehaviorIndex', 0) or 0)
        except Exception:
            _startup_mode = 0
        _default_incident = _early_settings.get('lastIncidentNumber') if _startup_mode == 1 else None
        login = LoginDialog(demo_mode=bool(getattr(args, 'demo', False)), default_incident_number=_default_incident)
        if login.exec() != QDialog.Accepted:
            sys.exit(0)

    # Build main window after session is established
    settings_manager = _early_settings
    settings_bridge = SettingsBridge(settings_manager)

    # Wire api_client to connection state so all modules talk to the right server.
    from utils.api_client import api_client as _api_client
    if DEBUG_BYPASS_LOGIN:
        # Debug mode: start the local server automatically so API calls work.
        from core.networking.server_info import DEFAULT_SERVER_PORT as _DEFAULT_SERVER_PORT
        from core.networking import LocalServerController as _LocalServerController
        _debug_local_controller = _LocalServerController()
        _connection_manager = None
        try:
            _debug_local_controller.start()
            ready = _debug_local_controller.wait_until_ready(timeout_seconds=15.0)
            print(f"[debug] Local server ready: {ready} — {_debug_local_controller.base_url}")
        except Exception as _exc:
            print(f"[debug] Local server start failed: {_exc}")
        app.aboutToQuit.connect(_debug_local_controller.stop)
        _api_client.configure(f"http://localhost:{_DEFAULT_SERVER_PORT}")
        print(f"[debug] api_client configured: http://localhost:{_DEFAULT_SERVER_PORT}")
    elif _connection_manager is not None:
        from core.networking import ConnectionState as _ConnectionState
        from core.networking.server_info import DEFAULT_SERVER_PORT as _DEFAULT_SERVER_PORT

        def _on_connection_changed(snapshot) -> None:
            if snapshot.state in {_ConnectionState.CONNECTED_LAN, _ConnectionState.CONNECTED_CLOUD}:
                _api_client.configure(snapshot.server.base_url)
            elif snapshot.state == _ConnectionState.OFFLINE:
                _api_client.configure(f"http://localhost:{_DEFAULT_SERVER_PORT}")

        _connection_manager.add_listener(_on_connection_changed)
        _on_connection_changed(_connection_manager.snapshot)

    # Initialize theme manager/bridge at app level as well
    try:
        saved = settings_bridge.getSetting('themeName') or 'system'
        saved = str(saved).lower()
        if saved == 'system':
            from styles.profiles import get_profile_name
            saved = get_profile_name()
        elif saved not in {"light", "dark"}:
            saved = "light"
        _theme_manager = ThemeManager(app, initial_theme=saved)
        _theme_bridge = ThemeBridge(_theme_manager.tokens())
        from styles.qss_helpers import global_qss as _global_qss
        app.setStyleSheet(_global_qss(_theme_manager.tokens()))
        # Keep app QSS + bridge updated on theme changes
        _theme_manager.themeChanged.connect(lambda _:
            (_theme_bridge.updateTokens(_theme_manager.tokens()),
             app.setStyleSheet(_global_qss(_theme_manager.tokens())))
        )
        # React to settings bridge updates
        try:
            def _on_theme_setting_changed(key, value):
                if key != 'themeName':
                    return
                theme = str(value).lower()
                if theme == 'system':
                    from styles.profiles import get_profile_name
                    theme = get_profile_name()
                _theme_manager.setTheme(theme)
            settings_bridge.settingChanged.connect(_on_theme_setting_changed)
        except Exception:
            pass
    except Exception:
        _theme_manager = None  # type: ignore[assignment]
        _theme_bridge = None   # type: ignore[assignment]

    # Seed the certification catalog mirror on app start (idempotent)
    try:
        from modules.personnel.services.cert_seeder import sync as _cert_sync
        _changed, _msg = _cert_sync()
        print(f"[catalog] {_msg}")
    except Exception as e:
        print(f"[catalog] Seeder failed: {e}")

    win = MainWindow(settings_manager=settings_manager, settings_bridge=settings_bridge)
    # Share the app-level theme objects with the window (used to inject into legacy UI contexts)
    try:
        if _theme_manager:
            win.theme_manager = _theme_manager
        if _theme_bridge:
            win.theme_bridge = _theme_bridge
    except Exception:
        pass
    from modules.devtools.dev_menu import attach_dev_menu
    attach_dev_menu(win)
    win.showMaximized()
    sys.exit(app.exec())
