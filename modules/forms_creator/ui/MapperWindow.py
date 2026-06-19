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
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

from modules.forms_creator.form_set_registry import FormSetRegistry
from modules.forms_creator.services.pdf_fields import PDFFormFieldExtractor, DetectedPDFField
from modules.forms_creator.services.rasterizer import Rasterizer, RasterizerError
from .CanvasView import CanvasView

_BINDING_CATALOG_PATH = Path(__file__).resolve().parents[3] / "forms" / "binding_catalog.json"


def _rename_pdf_fields(pdf_path: Path, rename_map: dict[str, str]) -> None:
    """Rewrite /T annotation keys in pdf_path according to rename_map, in-place."""
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        annots = page.get("/Annots")
        if not annots:
            continue
        for ref in annots:
            obj = ref.get_object()
            t = obj.get("/T")
            if t is None:
                continue
            current = t if isinstance(t, str) else t.get_object() if hasattr(t, "get_object") else str(t)
            if current in rename_map:
                obj[NameObject("/T")] = TextStringObject(rename_map[current])
    tmp = pdf_path.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as fh:
        writer.write(fh)
    tmp.replace(pdf_path)

_TRANSFORMS      = ["", "date_short", "time_short", "datetime_short", "upper", "lower"]
_TRANSFORM_LABELS = ["None", "date_short", "time_short", "datetime_short", "upper", "lower"]

_COLOR_MAPPED   = QColor(30, 150, 30, 160)
_COLOR_UNMAPPED = QColor(200, 80, 30, 160)


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------

def _load_catalog_raw() -> dict:
    try:
        raw = json.loads(_BINDING_CATALOG_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
        return {"bindings": raw, "array_sources": []}
    except Exception:
        return {"bindings": [], "array_sources": []}


def _load_catalog() -> list[dict]:
    return _load_catalog_raw().get("bindings", [])


# Prefixes whose second path segment is a meaningful sub-object (not just a dict key).
# task.team.leader → group "task.team"; organization.incident_commander.name → group "organization".
_SUB_NAMESPACE_PREFIXES: frozenset[str] = frozenset({"capf_104", "teams"})


def _build_group_map(entries: list[dict], array_sources: list[dict] | None = None) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for entry in entries:
        path     = entry.get("path", "")
        label    = entry.get("label", path)
        category = entry.get("category", "")
        if entry.get("source_type") not in ("incident_db", "master_db", "computed"):
            continue
        parts = path.split(".")
        if len(parts) < 2:
            continue

        # Indexed group: tasks.0.title → group=tasks, indexed, suffix=title
        if len(parts) >= 3 and parts[1].isdigit():
            group   = parts[0]
            indexed = True
            suffix  = ".".join(parts[2:])
        # Sub-namespace: task.team.leader → group=task.team, suffix=leader
        # Only applies to prefixes that have genuine sub-objects (task, capf_104).
        # Other 3-part paths like organization.incident_commander.name stay under
        # their root group so they don't create dozens of same-labelled entries.
        elif len(parts) >= 3 and parts[0] in _SUB_NAMESPACE_PREFIXES:
            group   = f"{parts[0]}.{parts[1]}"
            indexed = False
            suffix  = ".".join(parts[2:])
        # Simple or deep non-sub-namespace: incident.name / organization.ic.name
        else:
            group   = parts[0]
            indexed = False
            suffix  = ".".join(parts[1:])

        if not suffix:
            continue
        if group not in groups:
            groups[group] = {
                "label":   category or group.replace("_", " ").title(),
                "indexed": indexed,
                "fields":  {},
            }
        if suffix not in groups[group]["fields"]:
            clean = re.sub(r"^[^—]*—\s*", "", label) or label
            groups[group]["fields"][suffix] = clean

    # Fold in array_sources — these don't appear as individual binding entries
    for src in (array_sources or []):
        group = src.get("data_key") or src.get("id", "")
        if not group or group in groups:
            continue
        fields = {
            col["source_key"]: col.get("label", col["source_key"])
            for col in src.get("columns", [])
            if col.get("source_key")
        }
        groups[group] = {
            "label":        src.get("label", group.replace("_", " ").title()),
            "indexed":      True,
            "array_source": True,
            "fields":       fields,
        }

    return groups


# ---------------------------------------------------------------------------
# Canvas item
# ---------------------------------------------------------------------------

class MapperFieldItem(QGraphicsRectItem):
    def __init__(self, pdf_field_name: str, rect: QRectF, mapped: bool = False,
                 binding_label: str = "") -> None:
        super().__init__(rect)
        self.pdf_field_name = pdf_field_name
        self._mapped = mapped
        self._binding_label = binding_label
        self.setFlags(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setToolTip(pdf_field_name if not binding_label else f"{pdf_field_name}\n→ {binding_label}")
        self._refresh_style()

    def set_mapped(self, mapped: bool, binding_label: str = "") -> None:
        self._mapped = mapped
        self._binding_label = binding_label
        self.setToolTip(self.pdf_field_name if not binding_label
                        else f"{self.pdf_field_name}\n→ {binding_label}")
        self._refresh_style()
        self.update()

    def _refresh_style(self) -> None:
        color = _COLOR_MAPPED if self._mapped else _COLOR_UNMAPPED
        self.setPen(QPen(color.darker(130), 1.5))
        fill = QColor(color)
        fill.setAlpha(50)
        self.setBrush(fill)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        if bool(option.state & QStyle.StateFlag.State_Selected):
            painter.save()
            painter.fillRect(self.rect(), QColor(80, 160, 255, 90))
            painter.setPen(QPen(QColor(40, 100, 220), 2.0))
            painter.drawRect(self.rect())
            painter.restore()
        if self._binding_label:
            r = self.rect().adjusted(3, 1, -2, -1)
            if r.height() < 6 or r.width() < 8:
                return
            from PySide6.QtGui import QFontMetricsF
            painter.save()
            font = painter.font()
            font.setItalic(True)
            size = max(8.0, r.height() * 0.7)
            font.setPointSizeF(size)
            painter.setFont(font)
            color = _COLOR_MAPPED.darker(160) if self._mapped else _COLOR_UNMAPPED.darker(160)
            painter.setPen(QPen(color))
            painter.setClipRect(r)
            painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             self._binding_label)
            painter.restore()


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

        self._rg_loading = False
        self._build_ui()
        self._reload_group_map()
        self._load_mapping()
        self._load_pdf()
        self._populate_rg_list()

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
        self._canvas.setDragMode(CanvasView.DragMode.RubberBandDrag)
        self._canvas.zoomChanged.connect(lambda z: self._zoom_label.setText(f"{int(z * 100)}%"))
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

        # Zoom controls
        zoom_out = QPushButton("−")
        zoom_out.setFixedWidth(28)
        zoom_out.setToolTip("Zoom out  (Ctrl+Scroll)")
        zoom_out.clicked.connect(self._zoom_out)
        h.addWidget(zoom_out)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(46)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self._zoom_label)

        zoom_in = QPushButton("+")
        zoom_in.setFixedWidth(28)
        zoom_in.setToolTip("Zoom in  (Ctrl+Scroll)")
        zoom_in.clicked.connect(self._zoom_in)
        h.addWidget(zoom_in)

        zoom_fit = QPushButton("Fit")
        zoom_fit.setFixedWidth(36)
        zoom_fit.setToolTip("Fit page width")
        zoom_fit.clicked.connect(self._zoom_fit)
        h.addWidget(zoom_fit)

        zoom_reset = QPushButton("1:1")
        zoom_reset.setFixedWidth(34)
        zoom_reset.setToolTip("Reset to 100%")
        zoom_reset.clicked.connect(self._zoom_reset)
        h.addWidget(zoom_reset)

        h.addSpacing(8)
        self._pdf_path_label = QLabel(self._template_pdf.name)
        h.addWidget(self._pdf_path_label)
        btn = QPushButton("Change PDF…")
        btn.clicked.connect(self._on_change_pdf)
        h.addWidget(btn)
        return w

    def _zoom_in(self) -> None:
        self._canvas.zoom_step(1.25)
        self._update_zoom_label()

    def _zoom_out(self) -> None:
        self._canvas.zoom_step(0.8)
        self._update_zoom_label()

    def _zoom_fit(self) -> None:
        if self._scene.items():
            self._canvas.fitInView(self._scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._canvas.sync_zoom_from_transform()
        self._update_zoom_label()

    def _zoom_reset(self) -> None:
        self._canvas.reset_zoom()
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        self._zoom_label.setText(f"{int(self._canvas.current_zoom() * 100)}%")

    def _build_binding_panel(self) -> QWidget:
        """Right pane: tabbed between per-field binding and form-level arrays."""
        tabs = QTabWidget()
        tabs.setMinimumWidth(270)
        tabs.setMaximumWidth(360)
        tabs.addTab(self._build_field_tab(), "Field")
        tabs.addTab(self._build_arrays_tab(), "Arrays")
        return tabs

    def _build_field_tab(self) -> QWidget:
        """Per-field binding editor (original binding panel content)."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ── Field name / rename ──────────────────────────────────────
        self._selected_label = QLabel("<i>No field selected</i>")
        self._selected_label.setWordWrap(True)
        self._selected_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._selected_label)

        name_row = QHBoxLayout()
        name_row.setSpacing(4)
        self._field_name_edit = QLineEdit()
        self._field_name_edit.setPlaceholderText("field name")
        self._field_name_edit.setEnabled(False)
        self._field_name_edit.returnPressed.connect(self._on_rename_field)
        name_row.addWidget(self._field_name_edit)
        rename_btn = QPushButton("Rename")
        rename_btn.setFixedWidth(56)
        rename_btn.clicked.connect(self._on_rename_field)
        name_row.addWidget(rename_btn)
        layout.addLayout(name_row)

        # ── Batch actions (shown when multiple fields selected) ───────
        self._batch_rename_widget = QGroupBox("Batch actions")
        br = QVBoxLayout(self._batch_rename_widget)
        br.setSpacing(6)

        unmap_btn = QPushButton("Set All Selected → Unmapped")
        unmap_btn.clicked.connect(self._on_batch_set_unmapped)
        br.addWidget(unmap_btn)

        self._apply_all_btn = QPushButton("Apply Current Binding to All Selected")
        self._apply_all_btn.setStyleSheet("font-weight: bold;")
        self._apply_all_btn.clicked.connect(self._on_apply_to_all_selected)
        br.addWidget(self._apply_all_btn)

        sep_br = QFrame()
        sep_br.setFrameShape(QFrame.Shape.HLine)
        sep_br.setFrameShadow(QFrame.Shadow.Sunken)
        br.addWidget(sep_br)

        br.addWidget(QLabel("Batch rename:"))
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("Prefix:"))
        self._batch_prefix_edit = QLineEdit()
        self._batch_prefix_edit.setPlaceholderText("e.g. ChannelNameRow")
        self._batch_prefix_edit.textChanged.connect(self._update_batch_preview)
        prefix_row.addWidget(self._batch_prefix_edit)
        br.addLayout(prefix_row)
        start_row = QHBoxLayout()
        start_row.addWidget(QLabel("Start #:"))
        self._batch_start_spin = QSpinBox()
        self._batch_start_spin.setRange(0, 999)
        self._batch_start_spin.setValue(1)
        self._batch_start_spin.valueChanged.connect(self._update_batch_preview)
        start_row.addWidget(self._batch_start_spin)
        start_row.addStretch()
        br.addLayout(start_row)
        self._batch_preview_label = QLabel()
        self._batch_preview_label.setStyleSheet("font-size: 11px; color: #888;")
        self._batch_preview_label.setWordWrap(True)
        br.addWidget(self._batch_preview_label)
        apply_btn = QPushButton("Apply rename")
        apply_btn.clicked.connect(self._on_apply_batch_rename)
        br.addWidget(apply_btn)
        self._batch_rename_widget.setVisible(False)
        layout.addWidget(self._batch_rename_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Binding type ──────────────────────────────────────────────
        layout.addWidget(QLabel("Binding Type"))
        self._source_type_combo = QComboBox()
        self._source_type_combo.addItem("Data Path",        "data_path")
        self._source_type_combo.addItem("First Of…",        "first_of")
        self._source_type_combo.addItem("Join / Combine",   "join")
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
        self._field_combo = QComboBox()
        self._field_combo.setEditable(True)
        self._field_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._field_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self._field_combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
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

        # ── First-Of section ──────────────────────────────────────────
        self._first_of_widget = QWidget()
        fo = QVBoxLayout(self._first_of_widget)
        fo.setContentsMargins(0, 0, 0, 0)
        fo.setSpacing(4)
        fo.addWidget(QLabel("Try each path in order — use first non-empty:"))
        self._first_of_list = QListWidget()
        self._first_of_list.setMaximumHeight(100)
        self._first_of_list.currentRowChanged.connect(self._on_fo_selection_changed)
        fo.addWidget(self._first_of_list)
        fo_btn_row = QHBoxLayout()
        self._fo_add_btn = QPushButton("+ Add Path")
        self._fo_add_btn.clicked.connect(self._on_fo_add)
        fo_btn_row.addWidget(self._fo_add_btn)
        self._fo_remove_btn = QPushButton("Remove")
        self._fo_remove_btn.setEnabled(False)
        self._fo_remove_btn.clicked.connect(self._on_fo_remove)
        fo_btn_row.addWidget(self._fo_remove_btn)
        fo_btn_row.addStretch()
        fo.addLayout(fo_btn_row)
        layout.addWidget(self._first_of_widget)

        # ── Join / Combine section ────────────────────────────────────
        self._join_widget = QWidget()
        jw = QVBoxLayout(self._join_widget)
        jw.setContentsMargins(0, 0, 0, 0)
        jw.setSpacing(4)
        jw.addWidget(QLabel("Combine these paths into one field:"))
        self._join_list = QListWidget()
        self._join_list.setMaximumHeight(100)
        self._join_list.currentRowChanged.connect(self._on_join_selection_changed)
        jw.addWidget(self._join_list)
        join_btn_row = QHBoxLayout()
        self._join_add_btn = QPushButton("+ Add Path")
        self._join_add_btn.clicked.connect(self._on_join_add)
        join_btn_row.addWidget(self._join_add_btn)
        self._join_remove_btn = QPushButton("Remove")
        self._join_remove_btn.setEnabled(False)
        self._join_remove_btn.clicked.connect(self._on_join_remove)
        join_btn_row.addWidget(self._join_remove_btn)
        join_btn_row.addStretch()
        jw.addLayout(join_btn_row)
        sep_row = QHBoxLayout()
        sep_row.addWidget(QLabel("Separator:"))
        self._join_sep_edit = QLineEdit(", ")
        self._join_sep_edit.setMaximumWidth(80)
        self._join_sep_edit.setToolTip('Text placed between values, e.g. ", " or " / " or " "')
        self._join_sep_edit.textChanged.connect(self._on_binding_control_changed)
        sep_row.addWidget(self._join_sep_edit)
        sep_row.addStretch()
        jw.addLayout(sep_row)
        layout.addWidget(self._join_widget)

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
        self._cb_field_combo = QComboBox()
        self._cb_field_combo.setEditable(True)
        self._cb_field_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._cb_field_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self._cb_field_combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
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

    def _build_arrays_tab(self) -> QWidget:
        """Form-level array configuration — checklist popup to add/remove, detail below."""
        outer = QWidget()
        vbox  = QVBoxLayout(outer)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)

        # ── Button row ────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._rg_pick_btn = QPushButton("Add Array…")
        self._rg_pick_btn.clicked.connect(self._show_rg_picker)
        btn_row.addWidget(self._rg_pick_btn)

        edit_catalog_btn = QPushButton("Edit Catalog…")
        edit_catalog_btn.setToolTip("Add, edit, or remove array sources in the binding catalog")
        edit_catalog_btn.clicked.connect(self._open_array_catalog_editor)
        btn_row.addWidget(edit_catalog_btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)

        # ── Mapped-array list ─────────────────────────────────────────
        self._rg_mapped_list = QListWidget()
        self._rg_mapped_list.setMinimumHeight(80)
        self._rg_mapped_list.setMaximumHeight(160)
        self._rg_mapped_list.currentRowChanged.connect(self._on_rg_selected)
        vbox.addWidget(self._rg_mapped_list)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        vbox.addWidget(sep)

        # ── Detail area ───────────────────────────────────────────────
        self._rg_empty_label = QLabel("Select an array above to configure it.")
        self._rg_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rg_empty_label.setStyleSheet("color: #888; font-size: 12px;")
        vbox.addWidget(self._rg_empty_label)

        self._rg_settings = QWidget()
        sv = QVBoxLayout(self._rg_settings)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(4)

        title_row = QHBoxLayout()
        self._rg_title_label = QLabel()
        self._rg_title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        title_row.addWidget(self._rg_title_label)
        title_row.addStretch()
        sv.addLayout(title_row)

        self._rg_data_key_label = QLabel()
        self._rg_data_key_label.setStyleSheet("font-size: 11px; color: #888;")
        sv.addWidget(self._rg_data_key_label)

        col_hdr = QLabel("Ctrl-click fields on canvas, then click ← Map to assign a column.")
        col_hdr.setStyleSheet("font-size: 11px; margin-top: 6px;")
        col_hdr.setWordWrap(True)
        sv.addWidget(col_hdr)

        self._rg_col_widget = QWidget()
        self._rg_col_layout = QVBoxLayout(self._rg_col_widget)
        self._rg_col_layout.setContentsMargins(0, 0, 0, 0)
        self._rg_col_layout.setSpacing(3)
        sv.addWidget(self._rg_col_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        sv.addWidget(sep2)

        sv.addWidget(QLabel("Overflow:"))
        self._rg_overflow_combo = QComboBox()
        self._rg_overflow_combo.addItem("Continuation page",      "continuation")
        self._rg_overflow_combo.addItem("Repeat template",        "repeat")
        self._rg_overflow_combo.addItem("Truncate (no overflow)", "truncate")
        self._rg_overflow_combo.currentIndexChanged.connect(self._on_rg_changed)
        self._rg_overflow_combo.currentIndexChanged.connect(self._on_rg_overflow_changed)
        sv.addWidget(self._rg_overflow_combo)

        # Continuation source (only visible when overflow = continuation)
        self._rg_cont_widget = QWidget()
        cont_v = QVBoxLayout(self._rg_cont_widget)
        cont_v.setContentsMargins(0, 0, 0, 0)
        cont_v.setSpacing(4)

        # Mode toggle: separate file vs page-in-template
        mode_row = QHBoxLayout()
        self._rg_cont_file_btn = QPushButton("Separate File")
        self._rg_cont_file_btn.setCheckable(True)
        self._rg_cont_file_btn.setChecked(True)
        self._rg_cont_file_btn.clicked.connect(lambda: self._on_rg_cont_mode("file"))
        self._rg_cont_page_btn = QPushButton("Page in Template")
        self._rg_cont_page_btn.setCheckable(True)
        self._rg_cont_page_btn.clicked.connect(lambda: self._on_rg_cont_mode("page"))
        mode_row.addWidget(self._rg_cont_file_btn)
        mode_row.addWidget(self._rg_cont_page_btn)
        mode_row.addStretch()
        cont_v.addLayout(mode_row)

        # Separate-file sub-row
        self._rg_cont_file_row = QWidget()
        cont_h = QHBoxLayout(self._rg_cont_file_row)
        cont_h.setContentsMargins(0, 0, 0, 0)
        cont_h.setSpacing(4)
        self._rg_cont_label = QLabel("—")
        self._rg_cont_label.setStyleSheet("font-size: 11px; color: #555;")
        self._rg_cont_label.setWordWrap(True)
        cont_h.addWidget(self._rg_cont_label, 1)
        cont_browse_btn = QPushButton("Upload…")
        cont_browse_btn.setFixedWidth(64)
        cont_browse_btn.clicked.connect(self._on_rg_cont_browse)
        cont_h.addWidget(cont_browse_btn)
        cont_v.addWidget(self._rg_cont_file_row)

        # Page-in-template sub-row
        self._rg_cont_page_row = QWidget()
        page_h = QHBoxLayout(self._rg_cont_page_row)
        page_h.setContentsMargins(0, 0, 0, 0)
        page_h.setSpacing(4)
        page_h.addWidget(QLabel("Page number:"))
        self._rg_cont_page_spin = QSpinBox()
        self._rg_cont_page_spin.setMinimum(1)
        self._rg_cont_page_spin.setMaximum(99)
        self._rg_cont_page_spin.setValue(2)
        self._rg_cont_page_spin.valueChanged.connect(self._on_rg_cont_page_changed)
        page_h.addWidget(self._rg_cont_page_spin)
        page_h.addStretch()
        cont_v.addWidget(self._rg_cont_page_row)

        sv.addWidget(QLabel("Continuation source:"))
        sv.addWidget(self._rg_cont_widget)

        sv.addWidget(QLabel("Rows/page:"))
        rows_h = QHBoxLayout()
        rows_h.setSpacing(4)
        rows_h.addWidget(QLabel("p1:"))
        self._rg_rows_p1 = QSpinBox()
        self._rg_rows_p1.setRange(1, 500)
        self._rg_rows_p1.valueChanged.connect(self._on_rg_changed)
        rows_h.addWidget(self._rg_rows_p1)
        rows_h.addWidget(QLabel("cont:"))
        self._rg_rows_cont = QSpinBox()
        self._rg_rows_cont.setRange(0, 500)
        self._rg_rows_cont.setToolTip("0 = same as p1")
        self._rg_rows_cont.valueChanged.connect(self._on_rg_changed)
        rows_h.addWidget(self._rg_rows_cont)
        rows_h.addWidget(QLabel("start n:"))
        self._rg_row_offset = QSpinBox()
        self._rg_row_offset.setRange(0, 9999)
        self._rg_row_offset.setToolTip(
            "Row offset: 0 = start numbering at 1 (first page). "
            "Set to 5 on a continuation page if page 1 has 5 rows — "
            "fields will be renamed starting at 6 and data is read from row 6 onward."
        )
        self._rg_row_offset.valueChanged.connect(self._on_rg_changed)
        rows_h.addWidget(self._rg_row_offset)
        rows_h.addStretch()
        sv.addLayout(rows_h)
        sv.addStretch()

        save_btn = QPushButton("Save & Apply to Canvas")
        save_btn.clicked.connect(self._on_rg_save_apply)
        sv.addWidget(save_btn)

        self._rg_cont_widget.setVisible(False)
        self._rg_cont_page_row.setVisible(False)
        self._rg_settings.setVisible(False)
        vbox.addWidget(self._rg_settings, 1)
        return outer

    def _open_array_catalog_editor(self) -> None:
        from .ArrayCatalogEditorWindow import ArrayCatalogEditorWindow
        if not hasattr(self, "_catalog_editor") or not self._catalog_editor.isVisible():
            self._catalog_editor = ArrayCatalogEditorWindow(parent=self)
            self._catalog_editor.destroyed.connect(self._on_catalog_editor_closed)
        self._catalog_editor.show()
        self._catalog_editor.raise_()

    def _on_catalog_editor_closed(self) -> None:
        # Reload sources in case the catalog was changed
        self._populate_rg_list()

    def _populate_rg_list(self) -> None:
        """Load all array_sources; populate the mapped list from mapping.json."""
        self._rg_sources = {
            src["id"]: src
            for src in _load_catalog_raw().get("array_sources", [])
            if src.get("id")
        }
        self._rg_rebuild_mapped_list()

    def _rg_rebuild_mapped_list(self) -> None:
        self._rg_mapped_list.blockSignals(True)
        self._rg_mapped_list.clear()
        for rg in self._mapping.get("row_groups", []):
            ref = rg.get("ref", "")
            src = self._rg_sources.get(ref, {})
            label = src.get("label", ref)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ref)
            self._rg_mapped_list.addItem(item)
        self._rg_mapped_list.blockSignals(False)
        has_items = self._rg_mapped_list.count() > 0
        self._rg_empty_label.setVisible(not has_items)
        self._rg_settings.setVisible(False)
        if has_items:
            self._rg_mapped_list.setCurrentRow(0)

    def _show_rg_picker(self) -> None:
        """Open a modal dialog to add / remove arrays for this form."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Add / Remove Arrays")
        dlg.setMinimumWidth(360)
        dlg.setMaximumHeight(520)

        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(12, 12, 12, 8)
        vbox.setSpacing(6)

        vbox.addWidget(QLabel("Select arrays to include on this form:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        cb_container = QWidget()
        cb_layout = QVBoxLayout(cb_container)
        cb_layout.setContentsMargins(4, 4, 4, 4)
        cb_layout.setSpacing(4)

        mapped_ids = {r.get("ref", "") for r in self._mapping.get("row_groups", [])}
        checkboxes: dict[str, QCheckBox] = {}
        for src_id, src in self._rg_sources.items():
            cb = QCheckBox(src.get("label", src_id))
            cb.setChecked(src_id in mapped_ids)
            cb_layout.addWidget(cb)
            checkboxes[src_id] = cb
        cb_layout.addStretch()

        scroll.setWidget(cb_container)
        vbox.addWidget(scroll, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        vbox.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Index existing row_groups by ref so we preserve their config when re-checked
        existing = {r.get("ref"): r for r in self._mapping.get("row_groups", [])}
        new_row_groups = []
        for src_id, cb in checkboxes.items():
            if cb.isChecked():
                if src_id in existing:
                    new_row_groups.append(existing[src_id])
                else:
                    src = self._rg_sources.get(src_id, {})
                    new_row_groups.append({
                        "ref": src_id,
                        "data_key": src.get("data_key", src_id),
                        "overflow_mode": "truncate",
                        "rows_per_page": [1],
                        "col_patterns": {},
                    })
        self._mapping["row_groups"] = new_row_groups
        self._save_timer.start()
        self._rg_rebuild_mapped_list()

    def _on_rg_selected(self, row: int) -> None:
        if row < 0:
            self._rg_settings.setVisible(False)
            self._rg_empty_label.setVisible(True)
            return

        item   = self._rg_mapped_list.item(row)
        src_id = item.data(Qt.ItemDataRole.UserRole) if item else ""
        src    = self._rg_sources.get(src_id, {})
        mapping_rg = next(
            (r for r in self._mapping.get("row_groups", []) if r.get("ref") == src_id), {}
        )

        self._rg_loading = True
        self._rg_empty_label.setVisible(False)
        self._rg_settings.setVisible(True)
        self._rg_title_label.setText(src.get("label", src_id))
        self._rg_data_key_label.setText(f"data key: {src.get('data_key', src_id)}")

        # Rebuild column pattern rows
        while self._rg_col_layout.count():
            child = self._rg_col_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._rg_col_labels: dict[str, QLabel] = {}
        self._rg_col_cb_btns: dict[str, QPushButton] = {}
        col_patterns   = mapping_rg.get("col_patterns", {})
        col_checkboxes = set(mapping_rg.get("col_checkboxes", []))
        for col in src.get("columns", []):
            col_id = col.get("id", col.get("source_key", ""))
            if not col_id:
                continue
            is_cb_col = col_id in col_checkboxes or col.get("type") == "checkbox"
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(4)
            lbl = QLabel(col.get("label", col_id) + ":")
            lbl.setFixedWidth(90)
            lbl.setStyleSheet("font-size: 11px;")
            row_h.addWidget(lbl)
            pattern_lbl = QLabel(col_patterns.get(col_id, "—"))
            pattern_lbl.setStyleSheet("font-size: 11px; color: #555;")
            row_h.addWidget(pattern_lbl, 1)
            cb_btn = QPushButton("☑" if is_cb_col else "☐")
            cb_btn.setFixedWidth(28)
            cb_btn.setToolTip("Toggle: treat this column as a checkbox (X / blank)")
            cb_btn.setCheckable(True)
            cb_btn.setChecked(is_cb_col)
            cb_btn.clicked.connect(lambda _c, cid=col_id: self._on_rg_col_cb_toggled(cid))
            row_h.addWidget(cb_btn)
            map_btn = QPushButton("← Map")
            map_btn.setFixedWidth(54)
            map_btn.setToolTip("Ctrl-click fields on canvas, then click to assign and rename them")
            map_btn.clicked.connect(lambda _checked, cid=col_id: self._on_rg_map_selected(cid))
            row_h.addWidget(map_btn)
            self._rg_col_labels[col_id] = pattern_lbl
            self._rg_col_cb_btns[col_id] = cb_btn
            self._rg_col_layout.addWidget(row_w)

        overflow = mapping_rg.get("overflow_mode", "truncate")
        idx = self._rg_overflow_combo.findData(overflow)
        self._rg_overflow_combo.blockSignals(True)
        self._rg_overflow_combo.setCurrentIndex(idx if idx >= 0 else 2)
        self._rg_overflow_combo.blockSignals(False)
        self._rg_cont_widget.setVisible(overflow == "continuation")
        cont_page = mapping_rg.get("continuation_page")
        cont_tmpl = mapping_rg.get("continuation_template", "")
        if cont_page is not None:
            self._set_rg_cont_mode("page")
            self._rg_cont_page_spin.blockSignals(True)
            self._rg_cont_page_spin.setValue(int(cont_page))
            self._rg_cont_page_spin.blockSignals(False)
        else:
            self._set_rg_cont_mode("file")
            self._rg_cont_label.setText(cont_tmpl if cont_tmpl else "—")

        rows_per_page = mapping_rg.get("rows_per_page", [1])
        self._rg_rows_p1.setValue(rows_per_page[0] if rows_per_page else 1)
        self._rg_rows_cont.setValue(rows_per_page[1] if len(rows_per_page) > 1 else 0)
        self._rg_row_offset.blockSignals(True)
        self._rg_row_offset.setValue(mapping_rg.get("row_offset", 0))
        self._rg_row_offset.blockSignals(False)
        self._rg_loading = False

    def _on_rg_save_apply(self) -> None:
        """Immediately save array settings and recheck every canvas field."""
        self._on_rg_changed()          # flush current edits into self._mapping
        self._save_timer.stop()
        self._persist_mapping()        # write to disk without requiring a selected field
        for field in self._fields:
            self._refresh_field_row(field.name)

    def _on_rg_add(self) -> None:
        pass  # handled via picker toggle

    def _on_rg_remove(self) -> None:
        pass  # handled via picker toggle

    def _on_rg_changed(self, _=None) -> None:
        if getattr(self, "_rg_loading", False):
            return
        item = self._rg_mapped_list.currentItem()
        if not item:
            return
        src_id     = item.data(Qt.ItemDataRole.UserRole)
        mapping_rg = next(
            (r for r in self._mapping.get("row_groups", []) if r.get("ref") == src_id), None
        )
        if mapping_rg is None:
            return
        mapping_rg["overflow_mode"] = self._rg_overflow_combo.currentData()
        p1   = self._rg_rows_p1.value()
        cont = self._rg_rows_cont.value()
        mapping_rg["rows_per_page"] = [p1, cont] if cont else [p1]
        offset = self._rg_row_offset.value()
        if offset:
            mapping_rg["row_offset"] = offset
        else:
            mapping_rg.pop("row_offset", None)
        # col_patterns are set directly by _on_rg_map_selected; don't overwrite them here
        self._save_timer.start()

    def _on_rg_col_cb_toggled(self, col_id: str) -> None:
        item = self._rg_mapped_list.currentItem()
        if not item:
            return
        src_id = item.data(Qt.ItemDataRole.UserRole)
        mapping_rg = next(
            (r for r in self._mapping.get("row_groups", []) if r.get("ref") == src_id), None
        )
        if mapping_rg is None:
            return
        cbs: list = mapping_rg.setdefault("col_checkboxes", [])
        btn = self._rg_col_cb_btns.get(col_id)
        if btn and btn.isChecked():
            if col_id not in cbs:
                cbs.append(col_id)
            btn.setText("☑")
        else:
            mapping_rg["col_checkboxes"] = [c for c in cbs if c != col_id]
            if btn:
                btn.setText("☐")
        self._save_timer.stop()
        self._persist_mapping()

    def _on_rg_overflow_changed(self) -> None:
        is_cont = self._rg_overflow_combo.currentData() == "continuation"
        self._rg_cont_widget.setVisible(is_cont)

    def _set_rg_cont_mode(self, mode: str) -> None:
        is_page = mode == "page"
        self._rg_cont_file_btn.setChecked(not is_page)
        self._rg_cont_page_btn.setChecked(is_page)
        self._rg_cont_file_row.setVisible(not is_page)
        self._rg_cont_page_row.setVisible(is_page)

    def _on_rg_cont_mode(self, mode: str) -> None:
        self._set_rg_cont_mode(mode)
        item = self._rg_mapped_list.currentItem()
        if not item:
            return
        src_id = item.data(Qt.ItemDataRole.UserRole)
        mapping_rg = next(
            (r for r in self._mapping.get("row_groups", []) if r.get("ref") == src_id), None
        )
        if mapping_rg is None:
            return
        if mode == "page":
            mapping_rg.pop("continuation_template", None)
            mapping_rg["continuation_page"] = self._rg_cont_page_spin.value()
        else:
            mapping_rg.pop("continuation_page", None)
        self._save_timer.stop()
        self._persist_mapping()

    def _on_rg_cont_page_changed(self, value: int) -> None:
        item = self._rg_mapped_list.currentItem()
        if not item:
            return
        src_id = item.data(Qt.ItemDataRole.UserRole)
        mapping_rg = next(
            (r for r in self._mapping.get("row_groups", []) if r.get("ref") == src_id), None
        )
        if mapping_rg is not None:
            mapping_rg["continuation_page"] = value
            self._save_timer.start()

    def _on_rg_cont_browse(self) -> None:
        item = self._rg_mapped_list.currentItem()
        if not item:
            return
        src_id = item.data(Qt.ItemDataRole.UserRole)
        mapping_rg = next(
            (r for r in self._mapping.get("row_groups", []) if r.get("ref") == src_id), None
        )
        if mapping_rg is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Continuation Template PDF", "", "PDF Files (*.pdf)"
        )
        if not path:
            return
        import shutil as _shutil
        src_path = Path(path)
        dest = self._form_dir / src_path.name
        if dest != src_path:
            _shutil.copy2(src_path, dest)
        rel = dest.name
        mapping_rg["continuation_template"] = rel
        self._rg_cont_label.setText(rel)
        self._save_timer.stop()
        self._persist_mapping()

    def _on_rg_map_selected(self, col_id: str) -> None:
        """Rename the canvas-selected fields to {col_id}1, {col_id}2... and set the col_pattern."""
        item = self._rg_mapped_list.currentItem()
        if not item:
            return
        src_id = item.data(Qt.ItemDataRole.UserRole)
        mapping_rg = next(
            (r for r in self._mapping.get("row_groups", []) if r.get("ref") == src_id), None
        )
        if mapping_rg is None:
            return

        # Collect selected field items sorted top-to-bottom by scene Y position
        selected = [
            i for i in self._canvas.scene().selectedItems()
            if isinstance(i, MapperFieldItem)
        ]
        if not selected:
            self.statusBar().showMessage("No fields selected on canvas.", 3000)
            return
        selected.sort(key=lambda i: i.sceneBoundingRect().top())

        row_offset = mapping_rg.get("row_offset", 0)
        pattern = f"{col_id}{{n}}"
        rename_map = {
            item.pdf_field_name: f"{col_id}{row_offset + idx + 1}"
            for idx, item in enumerate(selected)
        }

        # Check for conflicts with existing field names outside this rename set
        existing = {f.name for f in self._fields}
        new_names = set(rename_map.values())
        conflicts = (new_names & existing) - set(rename_map.keys())
        if conflicts:
            self.statusBar().showMessage(
                f"Name conflict: {', '.join(sorted(conflicts))}", 4000
            )
            return

        # Set col_pattern before _apply_rename so it gets written to disk with the rename
        mapping_rg.setdefault("col_patterns", {})[col_id] = pattern
        lbl = self._rg_col_labels.get(col_id)
        if lbl:
            lbl.setText(pattern)

        self._save_timer.stop()
        self._apply_rename(rename_map)  # writes mapping + reloads canvas

    # ------------------------------------------------------------------
    # Group map
    # ------------------------------------------------------------------

    def _reload_group_map(self) -> None:
        raw = _load_catalog_raw()
        self._group_map = _build_group_map(raw.get("bindings", []), raw.get("array_sources", []))
        for combo in (self._group_combo, self._cb_group_combo):
            combo.blockSignals(True)
            combo.clear()
            for key, meta in self._group_map.items():
                if not meta.get("array_source"):
                    combo.addItem(meta["label"], key)
            combo.blockSignals(False)

    def _refresh_field_combo(
        self,
        group_key: str,
        field_combo: QComboBox,
        preserve_selection: str | None = None,
    ) -> None:
        field_combo.blockSignals(True)
        field_combo.clear()
        for suffix, label in self._group_map.get(group_key, {}).get("fields", {}).items():
            field_combo.addItem(label, suffix)
        if preserve_selection:
            idx = field_combo.findData(preserve_selection)
            if idx >= 0:
                field_combo.setCurrentIndex(idx)
            else:
                field_combo.setCurrentIndex(-1)
                field_combo.clearEditText()
        else:
            field_combo.setCurrentIndex(-1)
            field_combo.clearEditText()
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
                if name and name != "row_groups":
                    self._mapping[name] = fe.get("source", "")
            if "row_groups" in data:
                self._mapping["row_groups"] = data["row_groups"]
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
                field.name, QRectF(x, page_y + y, w, h),
                self._is_mapped(field.name),
                self._binding_label_for(field.name),
            )
            canvas_item.setZValue(1)
            self._scene.addItem(canvas_item)
            self._field_items[field.name] = canvas_item

        # Default to fit-in-view after every canvas rebuild
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._zoom_fit)

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
        if len(selected) > 1:
            self._show_batch_rename(selected)
        elif selected:
            self._batch_rename_widget.setVisible(False)
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

        # Update field label + rename edit
        field = next((f for f in self._fields if f.name == name), None)
        ftype = field.template_type if field else "unknown"
        self._selected_label.setText(
            f"<b>{name}</b><br><span style='color:#888;font-size:11px'>{ftype}</span>"
        )
        self._field_name_edit.blockSignals(True)
        self._field_name_edit.setText(name)
        self._field_name_edit.setEnabled(True)
        self._field_name_edit.blockSignals(False)

        self._set_panel_enabled(True)
        self._load_binding_for_field(name, ftype == "checkbox")

    # ------------------------------------------------------------------
    # Binding load  (field → controls)
    # ------------------------------------------------------------------

    def _load_binding_for_field(self, name: str, is_checkbox: bool = False) -> None:
        # Always ensure field combos are populated for the current group before
        # _populate_from_source runs — if source is empty it returns early and
        # never calls _refresh_field_combo, leaving the combo blank.
        self._refresh_field_combo(self._group_combo.currentData() or "", self._field_combo)
        self._refresh_field_combo(self._cb_group_combo.currentData() or "", self._cb_field_combo)

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
            if "first_of" in source:
                self._set_source_type("first_of")
                self._first_of_list.blockSignals(True)
                self._first_of_list.clear()
                for path in source.get("first_of", []):
                    self._fo_add_item(path)
                self._first_of_list.blockSignals(False)
                self._fo_remove_btn.setEnabled(False)
                return
            if "join" in source:
                self._set_source_type("join")
                self._join_list.blockSignals(True)
                self._join_list.clear()
                for path in source.get("join", []):
                    self._join_add_item(str(path))
                self._join_list.blockSignals(False)
                self._join_remove_btn.setEnabled(False)
                self._join_sep_edit.blockSignals(True)
                self._join_sep_edit.setText(source.get("separator", ", "))
                self._join_sep_edit.blockSignals(False)
                return
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
        group_combo = self._cb_group_combo if cb else self._group_combo
        index_spin  = self._cb_index_spin  if cb else self._index_spin
        field_combo = self._cb_field_combo if cb else self._field_combo

        if not path:
            return

        parts = path.split(".")

        # Resolve group key: use 2-part sub-namespace only for known prefixes.
        if len(parts) >= 3 and not parts[1].isdigit() and parts[0] in _SUB_NAMESPACE_PREFIXES:
            group_key = f"{parts[0]}.{parts[1]}"
            suffix    = ".".join(parts[2:])
        elif len(parts) >= 3 and parts[1].isdigit():
            group_key = parts[0]
            suffix    = None  # handled below via indexed logic
        else:
            group_key = parts[0]
            suffix    = ".".join(parts[1:])

        meta = self._group_map.get(group_key, {})

        gi = group_combo.findData(group_key)
        if gi >= 0:
            group_combo.blockSignals(True)
            group_combo.setCurrentIndex(gi)
            group_combo.blockSignals(False)

        self._refresh_field_combo(group_key, field_combo)

        if meta.get("indexed") and len(parts) >= 3:
            try:
                index_spin.blockSignals(True)
                index_spin.setValue(int(parts[1]))
                index_spin.blockSignals(False)
                suffix = ".".join(parts[2:])
            except ValueError:
                suffix = ".".join(parts[1:])
        elif suffix is None:
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
        is_fo     = type_key == "first_of"
        is_join   = type_key == "join"
        is_lit    = type_key == "literal"
        is_cb     = type_key == "checkbox"
        cb_truthy = is_cb and self._checkbox_combo.currentData() == "data_path"

        self._data_path_widget.setVisible(is_data or is_join)
        self._first_of_widget.setVisible(is_fo)
        self._join_widget.setVisible(is_join)
        self._literal_widget.setVisible(is_lit)
        self._checkbox_widget.setVisible(is_cb)
        self._cb_truthy_widget.setVisible(cb_truthy)

        # Index row inside data-path widget
        if is_data or is_join:
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
        self._first_of_widget.setEnabled(enabled)
        self._join_widget.setEnabled(enabled)
        self._literal_widget.setEnabled(enabled)
        self._checkbox_widget.setEnabled(enabled)
        if not enabled:
            self._field_name_edit.clear()
            self._field_name_edit.setEnabled(False)
            self._batch_rename_widget.setVisible(False)
            self._data_path_widget.setVisible(False)
            self._first_of_widget.setVisible(False)
            self._join_widget.setVisible(False)
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
        self._refresh_field_combo(key, self._field_combo)
        indexed = self._group_map.get(key, {}).get("indexed", False)
        self._index_row.setVisible(indexed)
        # Reset transform so previous field's setting doesn't bleed onto a new binding
        self._transform_combo.blockSignals(True)
        self._transform_combo.setCurrentIndex(0)
        self._transform_combo.blockSignals(False)
        self._on_binding_control_changed()

    def _on_cb_group_changed(self, _=None) -> None:
        key = self._cb_group_combo.currentData() or ""
        self._refresh_field_combo(key, self._cb_field_combo)
        indexed = self._group_map.get(key, {}).get("indexed", False)
        self._cb_index_row.setVisible(indexed)
        self._on_binding_control_changed()

    def _fo_add_item(self, path: str) -> None:
        item = QListWidgetItem(path)
        item.setData(Qt.ItemDataRole.UserRole, path)
        self._first_of_list.addItem(item)

    def _on_fo_selection_changed(self, row: int) -> None:
        self._fo_remove_btn.setEnabled(row >= 0)

    def _on_fo_add(self) -> None:
        group_key = self._group_combo.currentData() or ""
        field_key = self._field_combo.currentData() or ""
        if not field_key:
            return
        meta = self._group_map.get(group_key, {})
        if meta.get("indexed"):
            path = f"{group_key}.{self._index_spin.value()}.{field_key}"
        else:
            path = f"{group_key}.{field_key}" if group_key else field_key
        # Prevent duplicates
        existing = [
            self._first_of_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._first_of_list.count())
        ]
        if path not in existing:
            self._fo_add_item(path)
            self._on_binding_control_changed()

    def _on_fo_remove(self) -> None:
        row = self._first_of_list.currentRow()
        if row >= 0:
            self._first_of_list.takeItem(row)
            self._fo_remove_btn.setEnabled(self._first_of_list.currentRow() >= 0)
            self._on_binding_control_changed()

    # ── Join helpers ──────────────────────────────────────────────────

    def _join_add_item(self, path: str) -> None:
        item = QListWidgetItem(path)
        item.setData(Qt.ItemDataRole.UserRole, path)
        self._join_list.addItem(item)

    def _on_join_selection_changed(self, row: int) -> None:
        self._join_remove_btn.setEnabled(row >= 0)

    def _on_join_add(self) -> None:
        group_key = self._group_combo.currentData() or ""
        field_key = self._field_combo.currentData() or ""
        if not field_key:
            return
        meta = self._group_map.get(group_key, {})
        if meta.get("indexed"):
            path = f"{group_key}.{self._index_spin.value()}.{field_key}"
        else:
            path = f"{group_key}.{field_key}" if group_key else field_key
        existing = [
            self._join_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._join_list.count())
        ]
        if path not in existing:
            self._join_add_item(path)
            self._on_binding_control_changed()

    def _on_join_remove(self) -> None:
        row = self._join_list.currentRow()
        if row >= 0:
            self._join_list.takeItem(row)
            self._join_remove_btn.setEnabled(self._join_list.currentRow() >= 0)
            self._on_binding_control_changed()

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
        elif type_key == "first_of":
            paths = [
                self._first_of_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self._first_of_list.count())
            ]
            self._path_preview.setText(" | ".join(paths) if paths else "")
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
        if type_key == "first_of":
            paths = [
                self._first_of_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self._first_of_list.count())
            ]
            return {"first_of": paths}
        if type_key == "join":
            paths = [
                self._join_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self._join_list.count())
            ]
            sep = self._join_sep_edit.text()
            result: dict = {"join": paths}
            if sep != " ":
                result["separator"] = sep
            return result
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
        if self._current_field:
            self._mapping[self._current_field] = self._build_source_for_current()
            self._refresh_field_row(self._current_field)
        self._persist_mapping()

    def _persist_mapping(self) -> None:
        existing_names = {f.name for f in self._fields}
        fields_out = [
            {"pdf_field": f.name, "source": self._mapping.get(f.name, "")}
            for f in self._fields
        ]
        for name, sv in self._mapping.items():
            if name not in existing_names and name != "row_groups":
                fields_out.append({"pdf_field": name, "source": sv})

        data = {"description": self._build_description(), "fields": fields_out}
        if "row_groups" in self._mapping:
            data["row_groups"] = self._mapping["row_groups"]
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
            ci.set_mapped(mapped, self._binding_label_for(name))
            ci.update()

    def _binding_label_for(self, name: str) -> str:
        """Short human-readable label for what a field is bound to, or '' if unmapped."""
        source = self._mapping.get(name)
        if source is not None and source != "":
            if isinstance(source, str):
                return source
            if isinstance(source, dict):
                if "first_of" in source:
                    paths = source["first_of"]
                    return " | ".join(paths) if paths else ""
                if "literal" in source:
                    return f'"{source["literal"]}"'
                if "computed" in source:
                    return source["computed"]
                key = source.get("key", "")
                return key
        # Check row-group patterns
        import re as _re
        rg_sources = getattr(self, "_rg_sources", {})
        for rg in self._mapping.get("row_groups", []):
            for col_id, pattern in rg.get("col_patterns", {}).items():
                if not pattern:
                    continue
                regex = _re.escape(pattern).replace(r"\{n\}", r"(\d+)") + "$"
                m = _re.match(regex, name, _re.IGNORECASE)
                if m:
                    n = m.group(1)
                    src = rg_sources.get(rg.get("ref", ""), {})
                    col_label = next(
                        (c.get("label", col_id) for c in src.get("columns", [])
                         if c.get("id") == col_id), col_id
                    )
                    return f"{src.get('label', rg.get('ref', ''))}[{n}].{col_label}"
        return ""

    def _is_mapped(self, name: str) -> bool:
        source = self._mapping.get(name)
        if source is not None and source != "":
            if isinstance(source, dict):
                return source not in ({"literal": ""}, {})
            return bool(str(source))
        # Check whether this field is covered by any row-group col_pattern
        import re as _re
        for rg in self._mapping.get("row_groups", []):
            for pattern in rg.get("col_patterns", {}).values():
                if not pattern:
                    continue
                # Convert {n} pattern to regex and test
                regex = _re.escape(pattern).replace(r"\{n\}", r"\d+") + "$"
                if _re.match(regex, name, _re.IGNORECASE):
                    return True
        return False

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
            from modules.forms_creator.engine import generate
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
    # Field rename
    # ------------------------------------------------------------------

    def _on_rename_field(self) -> None:
        if not self._current_field:
            return
        new_name = self._field_name_edit.text().strip()
        if not new_name or new_name == self._current_field:
            return
        if any(f.name == new_name for f in self._fields):
            QMessageBox.warning(self, "Rename", f"A field named '{new_name}' already exists.")
            return
        self._apply_rename({self._current_field: new_name})

    def _on_batch_set_unmapped(self) -> None:
        selected = [i for i in self._scene.selectedItems() if isinstance(i, MapperFieldItem)]
        if not selected:
            return
        for item in selected:
            self._mapping[item.pdf_field_name] = ""
            self._refresh_field_row(item.pdf_field_name)
        self._persist_mapping()
        self.statusBar().showMessage(f"Cleared {len(selected)} field(s).", 2000)

    def _on_apply_to_all_selected(self) -> None:
        selected = [i for i in self._scene.selectedItems() if isinstance(i, MapperFieldItem)]
        if not selected:
            return
        source = self._build_source_for_current()
        for item in selected:
            self._mapping[item.pdf_field_name] = source
            self._refresh_field_row(item.pdf_field_name)
        self._persist_mapping()
        self.statusBar().showMessage(f"Applied binding to {len(selected)} field(s).", 2000)

    def _show_batch_rename(self, items: list) -> None:
        self._batch_rename_widget.setVisible(True)
        self._selected_label.setText(f"<b>{len(items)} fields selected</b>")
        self._field_name_edit.setEnabled(False)
        self._batch_prefix_edit.clear()
        self._batch_start_spin.setValue(1)
        self._batch_preview_label.clear()
        # Load the anchor (first) field's binding into the panel so the user
        # can inspect or change it before applying to all selected fields.
        anchor = items[0].pdf_field_name
        self._current_field = anchor
        field = next((f for f in self._fields if f.name == anchor), None)
        ftype = field.template_type if field else "unknown"
        self._set_panel_enabled(True)
        self._field_name_edit.setEnabled(False)
        self._load_binding_for_field(anchor, ftype == "checkbox")

    def _update_batch_preview(self) -> None:
        selected = [i for i in self._scene.selectedItems() if isinstance(i, MapperFieldItem)]
        prefix = self._batch_prefix_edit.text()
        start  = self._batch_start_spin.value()
        if not prefix or not selected:
            self._batch_preview_label.clear()
            return
        names = [f"{prefix}{start + i}" for i in range(min(len(selected), 3))]
        ellipsis = "…" if len(selected) > 3 else ""
        self._batch_preview_label.setText("→ " + ", ".join(names) + ellipsis)

    def _on_apply_batch_rename(self) -> None:
        selected = [i for i in self._scene.selectedItems() if isinstance(i, MapperFieldItem)]
        prefix = self._batch_prefix_edit.text().strip()
        start  = self._batch_start_spin.value()
        if not prefix or not selected:
            return
        rename_map = {
            item.pdf_field_name: f"{prefix}{start + i}"
            for i, item in enumerate(selected)
        }
        conflicts = [n for n in rename_map.values()
                     if any(f.name == n and f.name not in rename_map for f in self._fields)]
        if conflicts:
            QMessageBox.warning(self, "Rename", f"Name conflict: {conflicts[0]}")
            return
        self._apply_rename(rename_map)

    def _apply_rename(self, rename_map: dict[str, str]) -> None:
        """Rename PDF fields in-place and update all in-memory references."""
        try:
            _rename_pdf_fields(self._template_pdf, rename_map)
        except Exception as exc:
            QMessageBox.critical(self, "Rename failed", str(exc))
            return

        # Update DetectedPDFField list
        for field in self._fields:
            if field.name in rename_map:
                field.name = rename_map[field.name]

        # Update mapping keys
        for old, new in rename_map.items():
            if old in self._mapping:
                self._mapping[new] = self._mapping.pop(old)
        self._write_mapping()

        # Rebuild canvas + field list
        self._load_pdf()
        if len(rename_map) == 1:
            new_name = next(iter(rename_map.values()))
            self._select_field(new_name, from_list=False)
        else:
            self._batch_rename_widget.setVisible(False)

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
