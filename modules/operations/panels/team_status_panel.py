from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QMenu,
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QHeaderView,
    QMessageBox,
    QStyledItemDelegate,
)
from PySide6.QtCore import Qt, QTimer, QRect, QRectF, QEvent, QByteArray
from PySide6.QtGui import QPainter, QPixmap, QColor, QBrush, QImage
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QStyleOptionViewItem, QToolTip
from utils.styles import team_status_colors, subscribe_theme, get_palette
from utils.audit import write_audit
from datetime import datetime, timezone
from typing import Callable, Any, Optional
import math
import logging
import re
from pathlib import Path

from .team_alerts import (
    AlertKind,
    TeamAlertState,
    compute_alert_kind,
    get_checkin_thresholds,
)


logger = logging.getLogger(__name__)


_ALERT_DATA_ROLE = Qt.UserRole + 10
_TINT_TARGET_PATTERN = re.compile(r"#000(?:000)?\b", re.IGNORECASE)


class AssistanceIconDelegate(QStyledItemDelegate):
    ICON_FILES = {
        AlertKind.EMERGENCY: "emergency.svg",
        AlertKind.NEEDS_ASSISTANCE: "assist_triangle.svg",
        AlertKind.CHECKIN_OVERDUE: "clock_red.svg",
        AlertKind.CHECKIN_WARNING: "clock_yellow.svg",
    }

    def __init__(
        self,
        parent: QTableWidget,
        *,
        now_provider: Callable[[], datetime],
        thresholds,
    ) -> None:
        super().__init__(parent)
        self._now_provider = now_provider
        self._thresholds = thresholds
        self._asset_dir = Path(__file__).resolve().parent.parent / "assets"
        self._icon_cache: dict[tuple[str, int, int], QPixmap] = {}

    def set_thresholds(self, thresholds) -> None:
        self._thresholds = thresholds

    def on_theme_changed(self) -> None:
        self._icon_cache.clear()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        super().paint(painter, option, index)
        alert_kind, _, _, _, _ = self._evaluate_alert(index)
        if alert_kind == AlertKind.NONE:
            return
        color = self._color_for_alert(alert_kind)
        if color is None:
            return
        size = max(12, min(option.rect.width(), option.rect.height()) - 8)
        widget = option.widget
        dpr = widget.devicePixelRatioF() if widget is not None else 1.0
        pixmap = self._pixmap_for(alert_kind, size, dpr, color)
        if pixmap.isNull():
            return
        width = pixmap.width() / dpr
        height = pixmap.height() / dpr
        rect = option.rect
        target = QRect(
            int(rect.x() + (rect.width() - width) / 2),
            int(rect.y() + (rect.height() - height) / 2),
            int(width),
            int(height),
        )
        painter.save()
        painter.drawPixmap(target, pixmap)
        painter.restore()

    def helpEvent(self, event, view, option, index) -> bool:
        if event.type() != QEvent.ToolTip:
            return super().helpEvent(event, view, option, index)
        alert_kind, _, _, elapsed_minutes, _ = self._evaluate_alert(index)
        if alert_kind == AlertKind.NONE:
            return False
        text = self._tooltip_text(alert_kind, elapsed_minutes)
        if not text:
            return False
        QToolTip.showText(event.globalPos(), text, view)
        return True

    def _evaluate_alert(self, index):
        payload = index.data(_ALERT_DATA_ROLE)
        state = self._state_from_payload(payload)
        if state is None:
            return AlertKind.NONE, None, None, None, None
        try:
            now = self._now_provider()
        except Exception:
            now = datetime.now(timezone.utc)
        try:
            alert_kind = compute_alert_kind(state, now=now, thresholds=self._thresholds)
        except ValueError:
            logger.warning("now_provider returned naive datetime; skipping alert rendering")
            return AlertKind.NONE, state, now, None, None
        reference = state.last_checkin_at or state.reference_time
        elapsed = None
        if (
            reference is not None
            and isinstance(reference, datetime)
            and reference.tzinfo is not None
            and reference.utcoffset() is not None
        ):
            elapsed = max(0.0, (now - reference).total_seconds() / 60.0)
        return alert_kind, state, now, elapsed, reference

    def _state_from_payload(self, payload: Any) -> Optional[TeamAlertState]:
        if not isinstance(payload, dict):
            return None
        last_checkin = self._parse_datetime(payload.get("last_checkin_at"))
        reference_time = self._parse_datetime(payload.get("reference_time"))
        team_status = payload.get("team_status")
        emergency_flag = bool(payload.get("emergency_flag"))
        assistance_flag = bool(payload.get("needs_assistance_flag"))
        return TeamAlertState(
            emergency_flag=emergency_flag,
            needs_assistance_flag=assistance_flag,
            last_checkin_at=last_checkin,
            team_status=str(team_status) if team_status is not None else None,
            reference_time=reference_time,
        )

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except Exception:
            logger.warning("Failed to parse timestamp '%s' for team alert state", value)
            return None

    def _color_for_alert(self, alert_kind: str) -> Optional[QColor]:
        palette = get_palette()
        if alert_kind in {AlertKind.EMERGENCY, AlertKind.CHECKIN_OVERDUE}:
            return QColor(palette["error"])
        if alert_kind in {AlertKind.NEEDS_ASSISTANCE, AlertKind.CHECKIN_WARNING}:
            return QColor(palette["warning"])
        return None

    def _pixmap_for(self, alert_kind: str, size: int, dpr: float, color: QColor) -> QPixmap:
        key = (alert_kind, int(size * dpr), color.rgba())
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached
        pixmap = self._render_pixmap(alert_kind, size, dpr, color)
        self._icon_cache[key] = pixmap
        return pixmap

    def _render_pixmap(self, alert_kind: str, size: int, dpr: float, color: QColor) -> QPixmap:
        icon_px = max(1, int(round(size * dpr)))
        filename = self.ICON_FILES.get(alert_kind, "")
        path = self._asset_dir / filename if filename else None
        blank = QPixmap(icon_px, icon_px)
        blank.fill(Qt.transparent)
        blank.setDevicePixelRatio(dpr)
        if not path or not path.exists():
            logger.warning("Missing alert icon asset: %s", path)
            return blank
        try:
            svg_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Unable to read alert icon asset %s: %s", path, exc)
            return blank

        tint = QColor(color)
        tint.setAlpha(255)
        color_hex = tint.toRgb().name(QColor.HexRgb)
        tinted_svg = _TINT_TARGET_PATTERN.sub(color_hex, svg_text)
        renderer = QSvgRenderer(QByteArray(tinted_svg.encode("utf-8")))
        if not renderer.isValid():
            logger.warning("Invalid alert icon asset: %s", path)
            return blank

        image = QImage(icon_px, icon_px, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter, QRectF(0, 0, icon_px, icon_px))
        painter.end()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(dpr)
        return pixmap

    def _tooltip_text(self, alert_kind: str, elapsed_minutes: Optional[float]) -> Optional[str]:
        if alert_kind == AlertKind.EMERGENCY:
            return "Emergency declared"
        if alert_kind == AlertKind.NEEDS_ASSISTANCE:
            return "Needs assistance flag is ON"
        if alert_kind == AlertKind.CHECKIN_OVERDUE:
            if elapsed_minutes is None:
                return "Check-in overdue"
            minutes = max(1, int(math.floor(elapsed_minutes)))
            return f"Check-in overdue: last update {minutes} min ago"
        if alert_kind == AlertKind.CHECKIN_WARNING:
            if elapsed_minutes is None:
                return "Check-in due soon"
            remaining = max(0, math.ceil(self._thresholds.overdue_minutes - elapsed_minutes))
            return f"Check-in due soon: {remaining} min remaining"
        return None


# Use incident DB only (no sample fallback)
try:
    from modules.operations.data.repository import fetch_team_assignment_rows, set_team_assignment_status  # type: ignore
except Exception:
    fetch_team_assignment_rows = None  # type: ignore[assignment]
    set_team_assignment_status = None  # type: ignore[assignment]



class TeamStatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        # Header actions
        header_bar = QWidget()
        hb = QHBoxLayout(header_bar)
        try:
            hb.setContentsMargins(0, 0, 0, 0)
            hb.setSpacing(6)
        except Exception:
            pass
        btn_open = QPushButton("Open Detail")
        btn_new = QPushButton("New Team")
        btn_open.clicked.connect(lambda: self._on_open_detail())
        btn_new.clicked.connect(lambda: self._on_new_team())
        hb.addWidget(btn_open)
        hb.addWidget(btn_new)

        self.table = QTableWidget()
        # Make table read-only; edits go through context menus / detail windows
        try:
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        except Exception:
            pass
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        try:
            # On double click, open Team Detail placeholder
            self.table.itemDoubleClicked.connect(lambda item: self.view_team_detail(item.row()))
        except Exception:
            pass
        layout.addWidget(header_bar)
        layout.addWidget(self.table)

        self._now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
        self._thresholds = get_checkin_thresholds()
        self._icon_delegate = AssistanceIconDelegate(
            self.table,
            now_provider=self._now_provider,
            thresholds=self._thresholds,
        )
        try:
            self.table.setItemDelegateForColumn(0, self._icon_delegate)
        except Exception:
            pass

        # Set column headers: Needs Assistance at far left; Last Update at far right
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Needs Assistance", "Sortie #", "Team Name", "Team Leader", "Contact #",
            "Status", "Assignment", "Location", "Last Update"
        ])
        try:
            hdr = self.table.horizontalHeader()
            hdr.setSectionsMovable(True)
            hdr.setStretchLastSection(False)
            hdr.setSectionResizeMode(0, QHeaderView.Fixed)
            hdr.resizeSection(0, 56)
        except Exception:
            pass
        try:
            self.table.setColumnWidth(0, 56)
        except Exception:
            pass
        # Initial load
        self.reload()
        # Start a 1s timer to refresh the Last Update column
        try:
            self._last_update_timer = QTimer(self)
            self._last_update_timer.setInterval(1000)
            self._last_update_timer.timeout.connect(self._refresh_last_update_column)
            self._last_update_timer.start()
        except Exception:
            pass
        # React to incident changes
        try:
            from utils.app_signals import app_signals
            app_signals.incidentChanged.connect(lambda *_: self.reload())
            # Listen for comms messages and external team status updates
            try:
                app_signals.messageLogged.connect(self._on_message_logged)
            except Exception:
                pass
            try:
                app_signals.teamStatusChanged.connect(self._on_team_status_changed)
            except Exception:
                pass
        except Exception:
            pass
        # Theme changes recolor rows
        try:
            subscribe_theme(self, self._on_theme_changed)
        except Exception:
            pass

    def _on_theme_changed(self, *_: Any) -> None:
        try:
            if hasattr(self, "_icon_delegate") and self._icon_delegate is not None:
                self._icon_delegate.on_theme_changed()
        except Exception:
            pass
        self._recolor_all()
        try:
            self.table.viewport().update()
        except Exception:
            pass

    def _update_thresholds_from_config(self) -> None:
        thresholds = get_checkin_thresholds()
        self._thresholds = thresholds
        try:
            if hasattr(self, "_icon_delegate") and self._icon_delegate is not None:
                self._icon_delegate.set_thresholds(thresholds)
        except Exception:
            pass

    def add_team(self, team):
        data = {
            "sortie": getattr(team, "sortie", ""),
            "name": getattr(team, "name", ""),
            "leader": getattr(team, "leader", getattr(team, "team_leader", "")),
            "contact": getattr(team, "contact", getattr(team, "team_leader_phone", "")),
            "status": getattr(team, "status", ""),
            "assignment": getattr(team, "assignment", ""),
            "location": getattr(team, "location", ""),
            "needs_attention": getattr(team, "needs_attention", False),
            "needs_assistance_flag": getattr(team, "needs_attention", False),
            "emergency_flag": getattr(team, "emergency_flag", False),
            "last_checkin_at": self._normalize_iso(getattr(team, "last_checkin_at", None)),
            "checkin_reference_at": self._normalize_iso(getattr(team, "checkin_reference_at", None)),
            "team_status_updated": self._normalize_iso(getattr(team, "last_update_ts", None)),
            "last_updated": self._normalize_iso(getattr(team, "last_update_ts", None)),
            "team_id": getattr(team, "team_id", None),
            "task_id": getattr(team, "current_task_id", None),
            "tt_id": getattr(team, "tt_id", None),
        }
        self._add_team_row(data)

    @staticmethod
    def _normalize_iso(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        return str(value)

    def _format_elapsed(self, iso_ts: str | None) -> str:
        if not iso_ts:
            return ""
        try:
            # Accept naive UTC ISO or with tz
            try:
                dt = datetime.fromisoformat(str(iso_ts))
            except Exception:
                return str(iso_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now - dt
            seconds = int(max(delta.total_seconds(), 0))
            # Format as HH:MM:SS (elapsed). Cap at 99:59:59 for very long durations.
            hours = min(seconds // 3600, 99)
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        except Exception:
            return ""

    def _add_team_row(self, data: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        status_raw = data.get("status", "")
        status_key = str(status_raw or "").strip().lower()
        status_display = status_key.title() if status_key else ""

        icon_item = QTableWidgetItem("")
        icon_item.setFlags(icon_item.flags() & ~Qt.ItemIsEditable)
        icon_item.setTextAlignment(Qt.AlignCenter)
        self._apply_identity_roles(icon_item, data)
        alert_payload = self._build_alert_payload(data, status_key)
        icon_item.setData(_ALERT_DATA_ROLE, alert_payload)
        self.table.setItem(row, 0, icon_item)

        last_up = self._format_elapsed(data.get("last_updated"))
        column_texts = [
            str(data.get("sortie", "")),
            str(data.get("name", "")),
            str(data.get("leader", "")),
            str(data.get("contact", "")),
            status_display,
            str(data.get("assignment", "")),
            str(data.get("location", "")),
            last_up,
        ]
        for offset, text in enumerate(column_texts, start=1):
            item = QTableWidgetItem(text)
            if offset == 8:
                try:
                    item.setData(Qt.UserRole, str(data.get("last_updated") or ""))
                except Exception:
                    pass
            self.table.setItem(row, offset, item)

        self.set_row_color_by_status(row, status_key)

    def _apply_identity_roles(self, item: QTableWidgetItem, data: dict) -> None:
        role_keys = (
            (Qt.UserRole, "tt_id"),
            (Qt.UserRole + 1, "task_id"),
            (Qt.UserRole + 2, "team_id"),
        )
        for role, key in role_keys:
            value = data.get(key)
            if value is None:
                continue
            try:
                item.setData(role, int(value))
            except Exception:
                pass

    def _build_alert_payload(self, data: dict, status_key: str) -> dict:
        team_status_value = data.get("team_status") or data.get("status") or status_key
        reference_time = (
            data.get("checkin_reference_at")
            or data.get("team_status_updated")
            or data.get("last_updated")
        )
        return {
            "emergency_flag": bool(data.get("emergency_flag", False)),
            "needs_assistance_flag": bool(
                data.get("needs_assistance_flag", data.get("needs_attention", False))
            ),
            "last_checkin_at": data.get("last_checkin_at"),
            "team_status": team_status_value,
            "reference_time": reference_time,
        }

    def _row_has_emergency(self, row: int) -> bool:
        try:
            item = self.table.item(row, 0)
        except Exception:
            item = None
        if not item:
            return False
        payload = item.data(_ALERT_DATA_ROLE)
        if isinstance(payload, dict):
            try:
                return bool(payload.get("emergency_flag"))
            except Exception:
                return False
        return False

    @staticmethod
    def _blend_colors(base: QColor, overlay: QColor, ratio: float) -> QColor:
        ratio = max(0.0, min(1.0, float(ratio)))
        base_color = QColor(base)
        overlay_color = QColor(overlay)
        r = int(base_color.red() * (1 - ratio) + overlay_color.red() * ratio)
        g = int(base_color.green() * (1 - ratio) + overlay_color.green() * ratio)
        b = int(base_color.blue() * (1 - ratio) + overlay_color.blue() * ratio)
        blended = QColor(max(0, min(r, 255)), max(0, min(g, 255)), max(0, min(b, 255)))
        blended.setAlpha(255)
        return blended

    def _refresh_last_update_column(self) -> None:
        try:
            col = 8  # Last Update is rightmost
            rows = self.table.rowCount()
            for r in range(rows):
                item = self.table.item(r, col)
                if not item:
                    continue
                iso_ts = item.data(Qt.UserRole)
                text = self._format_elapsed(iso_ts)
                if text != item.text():
                    item.setText(text)
        except Exception:
            pass

    def _on_message_logged(self, sender: str, recipient: str) -> None:
        """Reset Last Update baseline for rows matching sender or recipient label.

        Matches against the displayed team label in columns 1 (Sortie #) and 2 (Team Name),
        case-insensitive.
        """
        try:
            if sender is None and recipient is None:
                return
            labels = {str(sender or "").strip().lower(), str(recipient or "").strip().lower()}
            if not any(labels):
                return
            rows = self.table.rowCount()
            for r in range(rows):
                name_item = self.table.item(r, 2)
                sortie_item = self.table.item(r, 1)
                name = (name_item.text().strip().lower() if name_item else "")
                sortie = (sortie_item.text().strip().lower() if sortie_item else "")
                if name in labels or sortie in labels:
                    self._reset_last_update_row(r)
        except Exception:
            pass

    def _on_team_status_changed(self, team_id: int) -> None:
        """Reset Last Update baseline for the row with the given team_id."""
        try:
            rows = self.table.rowCount()
            for r in range(rows):
                # team_id is stored on first column (Needs Attention) item, UserRole+2
                item0 = self.table.item(r, 0)
                val = None
                if item0 is not None:
                    try:
                        val = int(item0.data(Qt.UserRole + 2))
                    except Exception:
                        val = None
                if val is not None and int(val) == int(team_id):
                    self._reset_last_update_row(r)
                    break
        except Exception:
            pass

    def set_row_color_by_status(self, row, status):  # ✅ Now correctly placed
        status_key = str(status or "").lower()
        style = team_status_colors().get(status_key)
        palette_colors = get_palette()
        default_bg = QColor(palette_colors["bg"])
        default_fg = QBrush(QColor(palette_colors["fg"]))
        danger = QColor(palette_colors["error"])
        highlight = self._row_has_emergency(row)

        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if not item:
                continue
            if style:
                base_color = QColor(style["bg"].color())
                item.setForeground(style["fg"])
            else:
                base_color = QColor(default_bg)
                item.setForeground(default_fg)

            if highlight:
                tinted = self._blend_colors(base_color, danger, 0.25)
                item.setBackground(QBrush(tinted))
            elif style:
                item.setBackground(style["bg"])
            else:
                item.setBackground(QBrush(base_color))

    def _recolor_all(self) -> None:
        try:
            status_col = 5
            rows = self.table.rowCount()
            for r in range(rows):
                item = self.table.item(r, status_col)
                status = (item.text() if item else "").strip().lower()
                self.set_row_color_by_status(r, status)
        except Exception:
            pass

    def show_context_menu(self, position):
        row = self.table.indexAt(position).row()
        if row < 0:
            return

        menu = QMenu(self)

        # Top-level actions
        menu.addAction("View Team Detail", lambda: self.view_team_detail(row))
        menu.addAction("View Task Detail (Widget)", lambda: self.view_task_detail(row))

        # Add separator
        menu.addSeparator()

        # Flat list of status options
        for status in team_status_colors():
            menu.addAction(status.title(), lambda s=status: self.change_status(row, s))

        # Timer utilities
        menu.addSeparator()
        menu.addAction("Reset Timer", lambda: self._reset_last_update_row(row))

        # Show the menu
        menu.exec(self.table.viewport().mapToGlobal(position))

    def view_team_detail(self, row):
        try:
            item = self.table.item(row, 0)
            team_id = int(item.data(Qt.UserRole + 2)) if item and item.data(Qt.UserRole + 2) is not None else None
            from modules.operations.teams.windows import open_team_detail_window
            open_team_detail_window(team_id)
        except Exception as e:
            print(f"Failed to open Team Detail Window: {e}")

    def view_task_detail(self, row):
        try:
            # Use stored linked task id from first column
            item = self.table.item(row, 0)
            task_id = int(item.data(Qt.UserRole + 1)) if item and item.data(Qt.UserRole + 1) is not None else None
            if task_id is None:
                raise RuntimeError("No linked task id for this team assignment")
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(task_id)
        except Exception as e:
            print(f"Failed to open Task Detail Window: {e}")

    # QML variant removed

    def change_status(self, row, new_status):
        try:
            # Persist to DB using team_id; also stamps audit if currently assigned
            item = self.table.item(row, 0)
            team_id = int(item.data(Qt.UserRole + 2)) if item and item.data(Qt.UserRole + 2) is not None else None
            if not team_id:
                raise RuntimeError("No team id associated with row")
            item_status = self.table.item(row, 5)
            old_status = (item_status.text() if item_status else "").strip().lower()
            try:
                from modules.operations.data.repository import set_team_status  # local import to avoid cycles
            except Exception:
                set_team_status = None  # type: ignore[assignment]
            if not set_team_status:
                raise RuntimeError("DB repository not available")
            set_team_status(team_id, str(new_status))
            # Update UI
            display = str(new_status).title()
            # Status column index is 5 after adding Needs Attention at 0
            self.table.item(row, 5).setText(display)
            self.set_row_color_by_status(row, str(new_status))
            write_audit("status.change", {"panel": "team", "id": team_id, "old": old_status, "new": str(new_status)})
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.critical(self, "Update Failed", f"Unable to update team status in DB:\n{e}")
        else:
            # Any status change resets the Last Update timer baseline
            self._reset_last_update_row(row)

    def _reset_last_update_row(self, row: int) -> None:
        """Reset the Last Update timer baseline for a given row to now."""
        try:
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            item_last = self.table.item(row, 8)
            if item_last:
                item_last.setData(Qt.UserRole, now_iso)
                item_last.setText(self._format_elapsed(now_iso))
        except Exception:
            pass

    def _on_open_detail(self) -> None:
        row = self.table.currentRow()
        if row < 0 and self.table.selectedIndexes():
            row = self.table.selectedIndexes()[0].row()
        if row < 0:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.information(self, "Open Detail", "Select a team row first.")
            return
        self.view_team_detail(row)

    def _on_new_team(self) -> None:
        try:
            from modules.operations.taskings.repository import create_team
            new_id = create_team(None)
            # Reload and open team detail placeholder
            self.reload()
            from modules.operations.teams.windows import open_team_detail_window
            open_team_detail_window(new_id)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.critical(self, "New Team", f"Failed to create new team:\n{e}")

    def reload(self) -> None:
        # Clear and load fresh data from incident DB
        try:
            self._update_thresholds_from_config()
            self.table.setRowCount(0)
            if not fetch_team_assignment_rows:
                raise RuntimeError("DB repository not available")
            rows = fetch_team_assignment_rows()
            for data in rows:
                self._add_team_row(data)
        except Exception as e:
            from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHBoxLayout, QPushButton, QHeaderView, QMessageBox
            QMessageBox.critical(self, "Team Board Error", f"Failed to load team assignments from incident DB:\n{e}")



