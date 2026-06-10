"""Mapper window — visual binding editor for a single form + set combination."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QColor, QPen, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from modules.forms.form_set_registry import FormSetRegistry
from modules.forms_creator.services.pdf_fields import PDFFormFieldExtractor, DetectedPDFField
from modules.forms_creator.services.rasterizer import Rasterizer, RasterizerError
from .CanvasView import CanvasView

_BINDING_CATALOG_PATH = Path(__file__).resolve().parents[3] / "forms" / "binding_catalog.json"

_TRANSFORMS      = ["", "date_short", "time_short", "datetime_short", "upper", "lower"]
_TRANSFORM_LABELS = ["None", "date_short", "time_short", "datetime_short", "upper", "lower"]

_COLOR_MAPPED   = QColor(30, 150, 30, 160)
_COLOR_UNMAPPED = QColor(200, 80, 30, 160)


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------

def _load_catalog() -> list[dict]:
    try:
        return json.loads(_BINDING_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _build_group_map(entries: list[dict]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for entry in entries:
        path  = entry.get("path", "")
        label = entry.get("label", path)
        if entry.get("source_type") not in ("incident_db", "master_db", "computed"):
            continue
        parts = path.split(".")
        if len(parts) < 2:
            continue
        group = parts[0]
        if len(parts) >= 3 and parts[1].isdigit():
            indexed = True
            suffix  = ".".join(parts[2:])
        else:
            indexed = False
            suffix  = ".".join(parts[1:])
        if not suffix:
            continue
        if group not in groups:
            groups[group] = {
                "label":   group.replace("_", " ").title(),
                "indexed": indexed,
                "fields":  {},
            }
        if suffix not in groups[group]["fields"]:
            clean = re.sub(r"^.*? — ", "", label, count=1)
            if not indexed:
                clean = re.sub(r"^[^—]*— ", "", label, count=1) or label
            groups[group]["fields"][suffix] = clean
    return groups


# ---------------------------------------------------------------------------
# Canvas item
# ---------------------------------------------------------------------------

class MapperFieldItem(QGraphicsRectItem):
    def __init__(self, pdf_field_name: str, rect: QRectF, mapped: bool = False) -> None:
        super().__init__(rect)
        self.pdf_field_name = pdf_field_name
        self._mapped = mapped
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setToolTip(pdf_field_name)
        self._refresh_style()

    def set_mapped(self, mapped: bool) -> None:
        self._mapped = mapped
        self._refresh_style()

    def _refresh_style(self) -> None:
        color = _COLOR_MAPPED if self._mapped else _COLOR_UNMAPPED
        self.setPen(QPen(color.darker(130), 1.5))
        fill = QColor(color)
        fill.setAlpha(50)
        self.setBrush(fill)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        if bool(option.state & QStyle.StateFlag.State_Selected):
            painter.fillRect(self.rect(), QColor(80, 160, 255, 90))
            painter.setPen(QPen(QColor(40, 100, 220), 2.0))
            painter.drawRect(self.rect())


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MapperWindow(QMainWindow):

    def __init__(self, form_id: str, set_id: str, parent=None) -> None:
        super().__init__(parent)
        self._form_id = form_id
        self._set_id  = set_id

        registry          = FormSetRegistry()
        self._form_entry  = registry.get_form_definition(form_id)
        self._set_meta    = registry.get_set(set_id)
        if self._set_meta is None:
            raise ValueError(f"Unknown form set: {set_id}")

        self._form_dir     = self._set_meta.path / form_id
        self._template_pdf = self._form_dir / "template.pdf"
        self._mapping_json = self._form_dir / "mapping.json"

        title = (self._form_entry.number + " — " + self._form_entry.title) if self._form_entry else form_id
        self.setWindowTitle(f"Mapper — {title}  [{self._set_meta.display_name}]")
        self.resize(1300, 780)

        self._mapping: dict[str, Any]               = {}
        self._fields: list[DetectedPDFField]        = []
        self._field_items: dict[str, MapperFieldItem] = {}
        self._page_heights: list[float]             = []
        self._current_field: str | None             = None
        self._loading_binding                       = False
        self._group_map: dict[str, dict]            = {}

        # 300 ms debounce — avoids hammering disk on every keystroke
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._write_mapping)

        self._build_ui()
        self._reload_group_map()
        self._load_mapping()
        self._load_pdf()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)
        root.addWidget(self._build_header())

        # Three-pane splitter: field list | canvas | binding panel
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: field list
        left = QWidget()
        left.setMinimumWidth(180)
        left.setMaximumWidth(260)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(2, 2, 2, 2)
        ll.addWidget(QLabel("<b>Fields</b>"))
        self._field_list = QListWidget()
        self._field_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._field_list.currentRowChanged.connect(self._on_list_row_changed)
        ll.addWidget(self._field_list)
        splitter.addWidget(left)

        # Centre: canvas
        self._scene = QGraphicsScene()
        self._canvas = CanvasView(self._scene)
        self._canvas.setDragMode(CanvasView.DragMode.ScrollHandDrag)
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)
        splitter.addWidget(self._canvas)

        # Right: binding panel
        splitter.addWidget(self._build_binding_panel())

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 750, 300])

        root.addWidget(splitter, 1)
        self.setCentralWidget(container)

    def _build_header(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        title = (self._form_entry.number + " — " + self._form_entry.title) if self._form_entry else self._form_id
        h.addWidget(QLabel(f"<b>{title}</b>  |  Set: {self._set_meta.display_name}"))
        h.addStretch()
        self._pdf_path_label = QLabel(self._template_pdf.name)
        h.addWidget(self._pdf_path_label)
        btn = QPushButton("Change PDF…")
        btn.clicked.connect(self._on_change_pdf)
        h.addWidget(btn)
        return w

    def _build_binding_panel(self) -> QWidget:
        """Vertical binding editor — lives in the right pane of the splitter."""
        panel = QWidget()
        panel.setMinimumWidth(260)
        panel.setMaximumWidth(340)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Field info ────────────────────────────────────────────────
        self._selected_label = QLabel("<i>No field selected</i>")
        self._selected_label.setWordWrap(True)
        self._selected_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._selected_label)

        # ── Binding type ──────────────────────────────────────────────
        layout.addWidget(QLabel("Binding Type"))
        self._source_type_combo = QComboBox()
        self._source_type_combo.addItem("Data Path",        "data_path")
        self._source_type_combo.addItem("Literal (static)", "literal")
        self._source_type_combo.addItem("Checkbox",         "checkbox")
        self._source_type_combo.addItem("Unmapped",         "none")
        self._source_type_combo.currentIndexChanged.connect(self._on_source_type_changed)
        layout.addWidget(self._source_type_combo)

        # ── Data-path section ─────────────────────────────────────────
        self._data_path_widget = QWidget()
        dp = QVBoxLayout(self._data_path_widget)
        dp.setContentsMargins(0, 0, 0, 0)
        dp.setSpacing(4)

        dp.addWidget(QLabel("Group"))
        self._group_combo = QComboBox()
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        dp.addWidget(self._group_combo)

        self._index_row = QWidget()
        ir = QHBoxLayout(self._index_row)
        ir.setContentsMargins(0, 0, 0, 0)
        ir.addWidget(QLabel("Item #"))
        self._index_spin = QSpinBox()
        self._index_spin.setMinimum(0)
        self._index_spin.setMaximum(99)
        self._index_spin.valueChanged.connect(self._on_binding_control_changed)
        ir.addWidget(self._index_spin)
        ir.addStretch()
        dp.addWidget(self._index_row)

        dp.addWidget(QLabel("Field"))
        self._field_search = QLineEdit()
        self._field_search.setPlaceholderText("search fields…")
        self._field_search.textChanged.connect(self._on_field_search_changed)
        dp.addWidget(self._field_search)

        self._field_combo = QComboBox()
        self._field_combo.currentIndexChanged.connect(self._on_binding_control_changed)
        dp.addWidget(self._field_combo)

        dp.addWidget(QLabel("Transform"))
        self._transform_combo = QComboBox()
        for lbl, val in zip(_TRANSFORM_LABELS, _TRANSFORMS):
            self._transform_combo.addItem(lbl, val)
        self._transform_combo.currentIndexChanged.connect(self._on_binding_control_changed)
        dp.addWidget(self._transform_combo)

        dp.addWidget(QLabel("Default value"))
        self._default_edit = QLineEdit()
        self._default_edit.setPlaceholderText("fallback if empty")
        self._default_edit.textEdited.connect(self._on_binding_control_changed)
        dp.addWidget(self._default_edit)

        layout.addWidget(self._data_path_widget)

        # ── Literal section ───────────────────────────────────────────
        self._literal_widget = QWidget()
        lw = QVBoxLayout(self._literal_widget)
        lw.setContentsMargins(0, 0, 0, 0)
        lw.addWidget(QLabel("Static value"))
        self._literal_edit = QLineEdit()
        self._literal_edit.setPlaceholderText("text to insert verbatim")
        self._literal_edit.textEdited.connect(self._on_binding_control_changed)
        lw.addWidget(self._literal_edit)
        layout.addWidget(self._literal_widget)

        # ── Checkbox section ──────────────────────────────────────────
        self._checkbox_widget = QWidget()
        cw = QVBoxLayout(self._checkbox_widget)
        cw.setContentsMargins(0, 0, 0, 0)
        cw.setSpacing(4)

        self._checkbox_combo = QComboBox()
        self._checkbox_combo.addItem("Checked  (X)",                   "X")
        self._checkbox_combo.addItem("Unchecked  (blank)",             "")
        self._checkbox_combo.addItem("Check if data path is truthy…",  "data_path")
        self._checkbox_combo.currentIndexChanged.connect(self._on_checkbox_combo_changed)
        cw.addWidget(self._checkbox_combo)

        # Truthy sub-controls (group/index/field for checkbox data path)
        self._cb_truthy_widget = QWidget()
        ct = QVBoxLayout(self._cb_truthy_widget)
        ct.setContentsMargins(0, 4, 0, 0)
        ct.setSpacing(4)

        ct.addWidget(QLabel("Group"))
        self._cb_group_combo = QComboBox()
        self._cb_group_combo.currentIndexChanged.connect(self._on_cb_group_changed)
        ct.addWidget(self._cb_group_combo)

        self._cb_index_row = QWidget()
        ci = QHBoxLayout(self._cb_index_row)
        ci.setContentsMargins(0, 0, 0, 0)
        ci.addWidget(QLabel("Item #"))
        self._cb_index_spin = QSpinBox()
        self._cb_index_spin.setMinimum(0)
        self._cb_index_spin.setMaximum(99)
        self._cb_index_spin.valueChanged.connect(self._on_binding_control_changed)
        ci.addWidget(self._cb_index_spin)
        ci.addStretch()
        ct.addWidget(self._cb_index_row)

        ct.addWidget(QLabel("Field"))
        self._cb_field_search = QLineEdit()
        self._cb_field_search.setPlaceholderText("search fields…")
        self._cb_field_search.textChanged.connect(self._on_cb_field_search_changed)
        ct.addWidget(self._cb_field_search)

        self._cb_field_combo = QComboBox()
        self._cb_field_combo.currentIndexChanged.connect(self._on_binding_control_changed)
        ct.addWidget(self._cb_field_combo)

        cw.addWidget(self._cb_truthy_widget)

        hint = QLabel(
            "Checked writes <b>X</b>; Unchecked leaves the field blank."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        cw.addWidget(hint)

        layout.addWidget(self._checkbox_widget)

        # ── Path preview (always visible when something is selected) ──
        self._path_preview = QLabel()
        self._path_preview.setWordWrap(True)
        self._path_preview.setStyleSheet(
            "font-family: monospace; color: #4a9eff; font-size: 11px; "
            "background: #1a1a2e; padding: 4px; border-radius: 3px;"
        )
        layout.addWidget(self._path_preview)

        layout.addStretch()

        # ── Preview fill ──────────────────────────────────────────────
        preview_btn = QPushButton("Preview Fill")
        preview_btn.clicked.connect(self._on_preview_fill)
        layout.addWidget(preview_btn)

        # Start disabled
        self._set_panel_enabled(False)
        return panel

    # ------------------------------------------------------------------
    # Group map
    # ------------------------------------------------------------------

    def _reload_group_map(self) -> None:
        self._group_map = _build_group_map(_load_catalog())
        for combo in (self._group_combo, self._cb_group_combo):
            combo.blockSignals(True)
            combo.clear()
            for key, meta in self._group_map.items():
                combo.addItem(meta["label"], key)
            combo.blockSignals(False)

    def _refresh_field_combo(
        self,
        group_key: str,
        field_combo: QComboBox,
        filter_text: str = "",
        preserve_selection: str | None = None,
    ) -> None:
        field_combo.blockSignals(True)
        field_combo.clear()
        q = filter_text.lower()
        for suffix, label in self._group_map.get(group_key, {}).get("fields", {}).items():
            if not q or q in label.lower() or q in suffix.lower():
                field_combo.addItem(label, suffix)
        if preserve_selection:
            idx = field_combo.findData(preserve_selection)
            if idx >= 0:
                field_combo.setCurrentIndex(idx)
        field_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_mapping(self) -> None:
        self._mapping.clear()
        if not self._mapping_json.exists():
            return
        try:
            data = json.loads(self._mapping_json.read_text(encoding="utf-8"))
            for fe in data.get("fields", []):
                name = fe.get("pdf_field", "")
                if name:
                    self._mapping[name] = fe.get("source", "")
        except Exception:
            pass

    def _load_pdf(self) -> None:
        if not self._template_pdf.exists():
            self._scene.clear()
            self._scene.addText("No template.pdf found.")
            return
        try:
            self._page_images = Rasterizer().rasterize_pdf(
                self._template_pdf, self._form_dir / ".raster"
            )
        except RasterizerError as exc:
            self._scene.clear()
            self._scene.addText(f"Could not rasterize PDF:\n{exc}")
            return
        try:
            self._fields = PDFFormFieldExtractor().extract(self._template_pdf)
        except Exception:
            self._fields = []
        self._rebuild_canvas()
        self._populate_field_list()

    def _rebuild_canvas(self) -> None:
        self._scene.clear()
        self._field_items.clear()
        self._page_heights = []
        y_offset = 0.0
        page_pixmaps: list[tuple[float, float]] = []

        for page_path in self._page_images:
            px = QPixmap(str(page_path))
            if px.isNull():
                continue
            pi = QGraphicsPixmapItem(px)
            pi.setPos(0, y_offset)
            pi.setZValue(0)
            self._scene.addItem(pi)
            self._page_heights.append(float(px.height()))
            page_pixmaps.append((float(px.width()), float(px.height())))
            y_offset += px.height() + 10

        for field in self._fields:
            p = field.page_index
            if p >= len(page_pixmaps):
                continue
            img_w, img_h = page_pixmaps[p]
            pw = field.page_width or 1
            ph = field.page_height or 1
            llx, lly, urx, ury = field.rect
            x = llx * (img_w / pw)
            y = (ph - ury) * (img_h / ph)
            w = max(4.0, (urx - llx) * (img_w / pw))
            h = max(4.0, (ury - lly) * (img_h / ph))
            page_y = sum(self._page_heights[:p]) + p * 10
            canvas_item = MapperFieldItem(
                field.name, QRectF(x, page_y + y, w, h), self._is_mapped(field.name)
            )
            canvas_item.setZValue(1)
            self._scene.addItem(canvas_item)
            self._field_items[field.name] = canvas_item

    def _populate_field_list(self) -> None:
        self._field_list.clear()
        for field in self._fields:
            mapped = self._is_mapped(field.name)
            li = QListWidgetItem(("✓  " if mapped else "—  ") + field.name)
            li.setData(Qt.ItemDataRole.UserRole, field.name)
            li.setForeground(QColor("#2a8a2a") if mapped else QColor("#888888"))
            self._field_list.addItem(li)

    # ------------------------------------------------------------------
    # Field selection
    # ------------------------------------------------------------------

    def _on_list_row_changed(self, row: int) -> None:
        if row < 0:
            return
        item = self._field_list.item(row)
        if item:
            self._select_field(item.data(Qt.ItemDataRole.UserRole), from_list=True)

    def _on_scene_selection_changed(self) -> None:
        selected = [i for i in self._scene.selectedItems() if isinstance(i, MapperFieldItem)]
        if selected:
            self._select_field(selected[0].pdf_field_name, from_list=False)

    def _select_field(self, name: str, from_list: bool) -> None:
        self._current_field = name

        # Sync the OTHER selector without re-triggering this method
        if not from_list:
            self._field_list.blockSignals(True)
            for i in range(self._field_list.count()):
                it = self._field_list.item(i)
                if it and it.data(Qt.ItemDataRole.UserRole) == name:
                    self._field_list.setCurrentRow(i)
                    break
            self._field_list.blockSignals(False)
        else:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            ci = self._field_items.get(name)
            if ci:
                ci.setSelected(True)
                self._canvas.ensureVisible(ci)
            self._scene.blockSignals(False)

        # Update field label
        field = next((f for f in self._fields if f.name == name), None)
        ftype = field.template_type if field else "unknown"
        self._selected_label.setText(
            f"<b>{name}</b><br><span style='color:#888;font-size:11px'>{ftype}</span>"
        )

        self._set_panel_enabled(True)
        self._load_binding_for_field(name, ftype == "checkbox")

    # ------------------------------------------------------------------
    # Binding load  (field → controls)
    # ------------------------------------------------------------------

    def _load_binding_for_field(self, name: str, is_checkbox: bool = False) -> None:
        self._loading_binding = True
        try:
            self._populate_from_source(self._mapping.get(name), is_checkbox)
        finally:
            self._loading_binding = False

        # Fix visibility AFTER all controls are set (not during, when state is mid-flight)
        self._apply_visibility()
        self._update_path_preview()

    def _populate_from_source(self, source: Any, is_checkbox: bool) -> None:
        """Set control values. Called inside _loading_binding guard."""
        # ── unmapped / empty ──────────────────────────────────────────
        if source is None or source == "":
            self._set_source_type("checkbox" if is_checkbox else "none")
            if is_checkbox:
                self._checkbox_combo.setCurrentIndex(1)  # blank
            self._literal_edit.clear()
            self._transform_combo.setCurrentIndex(0)
            self._default_edit.clear()
            return

        # ── dict sources ─────────────────────────────────────────────
        if isinstance(source, dict):
            if "literal" in source:
                val = str(source["literal"])
                if is_checkbox or val in ("X", ""):
                    self._set_source_type("checkbox")
                    idx = self._checkbox_combo.findData(val)
                    self._checkbox_combo.setCurrentIndex(idx if idx >= 0 else 1)
                else:
                    self._set_source_type("literal")
                    self._literal_edit.setText(val)
                return
            # key/transform/default
            key = source.get("key", "")
            if is_checkbox:
                self._set_source_type("checkbox")
                self._checkbox_combo.setCurrentIndex(2)  # truthy
                self._set_path_on_controls(key, cb=True)
            else:
                self._set_source_type("data_path")
                self._set_path_on_controls(key, cb=False)
                ti = self._transform_combo.findData(source.get("transform", ""))
                self._transform_combo.setCurrentIndex(ti if ti >= 0 else 0)
                self._default_edit.setText(str(source.get("default", "")))
            return

        # ── plain string path ─────────────────────────────────────────
        path = str(source)
        if is_checkbox:
            self._set_source_type("checkbox")
            self._checkbox_combo.setCurrentIndex(2)
            self._set_path_on_controls(path, cb=True)
        else:
            self._set_source_type("data_path")
            self._set_path_on_controls(path, cb=False)
            self._transform_combo.setCurrentIndex(0)
            self._default_edit.clear()

    def _set_source_type(self, type_key: str) -> None:
        idx = self._source_type_combo.findData(type_key)
        if idx >= 0:
            self._source_type_combo.blockSignals(True)
            self._source_type_combo.setCurrentIndex(idx)
            self._source_type_combo.blockSignals(False)

    def _set_path_on_controls(self, path: str, cb: bool) -> None:
        group_combo  = self._cb_group_combo  if cb else self._group_combo
        index_spin   = self._cb_index_spin   if cb else self._index_spin
        field_search = self._cb_field_search if cb else self._field_search
        field_combo  = self._cb_field_combo  if cb else self._field_combo

        if not path:
            return

        parts     = path.split(".")
        group_key = parts[0]
        meta      = self._group_map.get(group_key, {})

        gi = group_combo.findData(group_key)
        if gi >= 0:
            group_combo.blockSignals(True)
            group_combo.setCurrentIndex(gi)
            group_combo.blockSignals(False)

        field_search.blockSignals(True)
        field_search.clear()
        field_search.blockSignals(False)
        self._refresh_field_combo(group_key, field_combo)

        if meta.get("indexed") and len(parts) >= 3:
            try:
                index_spin.blockSignals(True)
                index_spin.setValue(int(parts[1]))
                index_spin.blockSignals(False)
                suffix = ".".join(parts[2:])
            except ValueError:
                suffix = ".".join(parts[1:])
        else:
            suffix = ".".join(parts[1:])

        fi = field_combo.findData(suffix)
        if fi >= 0:
            field_combo.blockSignals(True)
            field_combo.setCurrentIndex(fi)
            field_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def _apply_visibility(self) -> None:
        type_key  = self._source_type_combo.currentData()
        is_data   = type_key == "data_path"
        is_lit    = type_key == "literal"
        is_cb     = type_key == "checkbox"
        cb_truthy = is_cb and self._checkbox_combo.currentData() == "data_path"

        self._data_path_widget.setVisible(is_data)
        self._literal_widget.setVisible(is_lit)
        self._checkbox_widget.setVisible(is_cb)
        self._cb_truthy_widget.setVisible(cb_truthy)

        # Index row inside data-path widget
        if is_data:
            group_key = self._group_combo.currentData() or ""
            indexed   = self._group_map.get(group_key, {}).get("indexed", False)
            self._index_row.setVisible(indexed)

        # Index row inside checkbox-truthy widget
        if cb_truthy:
            cb_key    = self._cb_group_combo.currentData() or ""
            cb_indexed = self._group_map.get(cb_key, {}).get("indexed", False)
            self._cb_index_row.setVisible(cb_indexed)

    def _set_panel_enabled(self, enabled: bool) -> None:
        self._source_type_combo.setEnabled(enabled)
        self._data_path_widget.setEnabled(enabled)
        self._literal_widget.setEnabled(enabled)
        self._checkbox_widget.setEnabled(enabled)
        if not enabled:
            self._data_path_widget.setVisible(False)
            self._literal_widget.setVisible(False)
            self._checkbox_widget.setVisible(False)
            self._path_preview.clear()

    # ------------------------------------------------------------------
    # Control interactions
    # ------------------------------------------------------------------

    def _on_source_type_changed(self, _=None) -> None:
        self._apply_visibility()
        self._on_binding_control_changed()

    def _on_group_changed(self, _=None) -> None:
        key = self._group_combo.currentData() or ""
        self._field_search.blockSignals(True)
        self._field_search.clear()
        self._field_search.blockSignals(False)
        self._refresh_field_combo(key, self._field_combo)
        # Show/hide index row
        indexed = self._group_map.get(key, {}).get("indexed", False)
        self._index_row.setVisible(indexed)
        self._on_binding_control_changed()

    def _on_cb_group_changed(self, _=None) -> None:
        key = self._cb_group_combo.currentData() or ""
        self._cb_field_search.blockSignals(True)
        self._cb_field_search.clear()
        self._cb_field_search.blockSignals(False)
        self._refresh_field_combo(key, self._cb_field_combo)
        indexed = self._group_map.get(key, {}).get("indexed", False)
        self._cb_index_row.setVisible(indexed)
        self._on_binding_control_changed()

    def _on_field_search_changed(self, text: str) -> None:
        key    = self._group_combo.currentData() or ""
        saved  = self._field_combo.currentData()
        self._refresh_field_combo(key, self._field_combo, text, preserve_selection=saved)

    def _on_cb_field_search_changed(self, text: str) -> None:
        key   = self._cb_group_combo.currentData() or ""
        saved = self._cb_field_combo.currentData()
        self._refresh_field_combo(key, self._cb_field_combo, text, preserve_selection=saved)

    def _on_checkbox_combo_changed(self, _=None) -> None:
        self._apply_visibility()
        self._on_binding_control_changed()

    def _on_binding_control_changed(self, _=None) -> None:
        if self._loading_binding or not self._current_field:
            return
        self._update_path_preview()
        self._save_timer.start()

    def _update_path_preview(self) -> None:
        type_key = self._source_type_combo.currentData()
        if type_key == "data_path":
            self._path_preview.setText(self._build_data_path(cb=False))
        elif type_key == "checkbox" and self._checkbox_combo.currentData() == "data_path":
            self._path_preview.setText(self._build_data_path(cb=True))
        elif type_key == "literal":
            self._path_preview.setText(f'"{self._literal_edit.text()}"')
        elif type_key == "checkbox":
            val = self._checkbox_combo.currentData()
            self._path_preview.setText("X  (checked)" if val == "X" else "(blank — unchecked)")
        else:
            self._path_preview.clear()

    # ------------------------------------------------------------------
    # Build source value
    # ------------------------------------------------------------------

    def _build_data_path(self, cb: bool) -> str:
        group_combo = self._cb_group_combo if cb else self._group_combo
        index_spin  = self._cb_index_spin  if cb else self._index_spin
        field_combo = self._cb_field_combo if cb else self._field_combo
        group_key   = group_combo.currentData() or ""
        suffix      = field_combo.currentData() or ""
        if self._group_map.get(group_key, {}).get("indexed"):
            return f"{group_key}.{index_spin.value()}.{suffix}" if suffix else group_key
        return f"{group_key}.{suffix}" if suffix else group_key

    def _build_source_for_current(self) -> Any:
        type_key = self._source_type_combo.currentData()
        if type_key == "none":
            return ""
        if type_key == "literal":
            return {"literal": self._literal_edit.text()}
        if type_key == "checkbox":
            val = self._checkbox_combo.currentData()
            if val == "data_path":
                return self._build_data_path(cb=True)
            return {"literal": val}   # "X" or ""
        # data_path
        path      = self._build_data_path(cb=False)
        transform = self._transform_combo.currentData()
        default   = self._default_edit.text()
        if transform and default:
            return {"key": path, "transform": transform, "default": default}
        if transform:
            return {"key": path, "transform": transform}
        if default:
            return {"key": path, "default": default}
        return path

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def _write_mapping(self) -> None:
        if not self._current_field:
            return
        self._mapping[self._current_field] = self._build_source_for_current()
        self._refresh_field_row(self._current_field)

        existing_names = {f.name for f in self._fields}
        fields_out = [
            {"pdf_field": f.name, "source": self._mapping.get(f.name, "")}
            for f in self._fields
        ]
        for name, sv in self._mapping.items():
            if name not in existing_names:
                fields_out.append({"pdf_field": name, "source": sv})

        data = {"description": self._build_description(), "fields": fields_out}
        try:
            self._mapping_json.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            self.statusBar().showMessage("Saved.", 1500)
        except Exception as exc:
            self.statusBar().showMessage(f"Save failed: {exc}", 4000)

    def _refresh_field_row(self, name: str) -> None:
        mapped = self._is_mapped(name)
        for i in range(self._field_list.count()):
            it = self._field_list.item(i)
            if it and it.data(Qt.ItemDataRole.UserRole) == name:
                it.setText(("✓  " if mapped else "—  ") + name)
                it.setForeground(QColor("#2a8a2a") if mapped else QColor("#888888"))
                break
        ci = self._field_items.get(name)
        if ci:
            ci.set_mapped(mapped)
            ci.update()

    def _is_mapped(self, name: str) -> bool:
        source = self._mapping.get(name)
        if source is None or source == "":
            return False
        if isinstance(source, dict):
            return source not in ({"literal": ""}, {})
        return bool(str(source))

    def _build_description(self) -> str:
        form_label = (self._form_entry.number + " — " + self._form_entry.title) if self._form_entry else self._form_id
        version    = self._set_meta.version if self._set_meta else ""
        return f"{form_label} — {self._set_meta.display_name}{' ' + version if version else ''}"

    # ------------------------------------------------------------------
    # Preview fill
    # ------------------------------------------------------------------

    def _on_preview_fill(self) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._write_mapping()
        try:
            from modules.forms.engine import generate
            out_path = Path(tempfile.mkdtemp()) / f"preview_{self._form_id}.pdf"
            generate(self._form_id, out_path, form_set_id=self._set_id)
            self._open_pdf(out_path)
        except Exception as exc:
            QMessageBox.critical(self, "Preview Error", f"Could not generate preview:\n{exc}")

    @staticmethod
    def _open_pdf(path: Path) -> None:
        import os
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    # ------------------------------------------------------------------
    # Change PDF / close
    # ------------------------------------------------------------------

    def _on_change_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Template PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        import shutil
        try:
            shutil.copy2(path, self._template_pdf)
        except Exception as exc:
            QMessageBox.critical(self, "Change PDF", f"Could not copy PDF:\n{exc}")
            return
        self._pdf_path_label.setText(self._template_pdf.name)
        self._load_pdf()

    def closeEvent(self, event) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._write_mapping()
        event.accept()
