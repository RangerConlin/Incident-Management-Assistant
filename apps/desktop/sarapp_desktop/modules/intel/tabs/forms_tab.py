"""FormsTab — Intel Module forms workspace.

Displays SAR and CAP forms from the forms_creator engine as cards.
Forms with an active template record are shown as live cards.
Forms registered in catalog.json but without a template record are shown
as "Coming Soon" cards so users can see what is planned.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSizePolicy, QMessageBox,
)
from PySide6.QtCore import Qt

from modules.intel.widgets.card_widget import CardWidget


# Categories shown in the Intel Forms tab (SAR + CAP forms only)
_INTEL_FORM_CATEGORIES = {"SAR", "CAP"}

# Path to the master forms catalog
_CATALOG_PATH = Path(__file__).parent.parent.parent.parent / "forms" / "catalog.json"


def _load_catalog_forms() -> list[dict]:
    """Return all SAR and CAP form definitions from catalog.json."""
    try:
        data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        return [
            f for f in data.get("forms", [])
            if f.get("category") in _INTEL_FORM_CATEGORIES
        ]
    except Exception:
        return []


def _get_available_template_ids(incident_id: Optional[str]) -> set[str]:
    """Return the set of form IDs that have live template records in master.db.

    Uses the FormService from forms_creator.  Returns an empty set on any
    import or connection error so the tab degrades gracefully.
    """
    try:
        from modules.forms_creator.services.templates import FormService
        svc = FormService()
        templates = svc.list_templates()
        # Template category field should match the catalog category label
        return {t["category_id"] for t in templates if t.get("category_id")} | \
               {t.get("form_id", "") for t in templates if t.get("form_id")}
    except Exception:
        return set()


class _FormCard(CardWidget):
    """Card for a single form in the Intel Forms workspace."""

    def __init__(
        self,
        form_def: dict,
        is_live: bool,
        incident_id: Optional[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, padding=16, clickable=is_live)
        self._form_def = form_def
        self._is_live = is_live
        self._incident_id = incident_id

        self.setFixedWidth(180)
        self.setFixedHeight(140)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        number_lbl = QLabel(form_def.get("number", ""))
        number_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: palette(placeholderText);")

        title_lbl = QLabel(form_def.get("title", ""))
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        title_lbl.setWordWrap(True)

        if is_live:
            badge = QLabel("Available")
            badge.setStyleSheet("""
                QLabel {
                    background: #2da44e; color: #fff;
                    border-radius: 8px; padding: 1px 8px;
                    font-size: 10px; font-weight: 600;
                }
            """)
        else:
            badge = QLabel("Coming Soon")
            badge.setStyleSheet("""
                QLabel {
                    background: palette(mid); color: palette(base);
                    border-radius: 8px; padding: 1px 8px;
                    font-size: 10px; font-weight: 600;
                }
            """)
            # Visually dim the card for unavailable forms
            self.setStyleSheet(self.styleSheet() + """
                CardWidget { opacity: 0.6; border: 1px dashed palette(mid); }
            """)

        self.layout().addWidget(number_lbl)
        self.layout().addWidget(title_lbl)
        self.layout().addStretch()
        self.layout().addWidget(badge)

    def mouseDoubleClickEvent(self, event) -> None:
        if not self._is_live:
            QMessageBox.information(
                self,
                self._form_def.get("number", "Form"),
                f"{self._form_def.get('number')} — {self._form_def.get('title')}\n\n"
                "This form is registered but does not yet have a PDF template.\n"
                "Open Developer → Forms Creator to add the template.",
            )
            return
        self._launch_form()

    def _launch_form(self) -> None:
        """Create a form instance and open the fill UI."""
        try:
            from modules.forms_creator.services.templates import FormService
            svc = FormService()
            # Find the matching template by form number or id
            form_id = self._form_def.get("id", "")
            templates = svc.list_templates()
            match = next(
                (t for t in templates
                 if t.get("form_id") == form_id or t.get("category_id") == form_id),
                None,
            )
            if not match:
                QMessageBox.warning(
                    self, "Form Not Found",
                    f"No template found for {self._form_def.get('number')}.\n"
                    "Use Developer → Forms Creator to create a template.",
                )
                return
            instance_id = svc.create_instance(
                incident_id=self._incident_id or "unknown",
                template_id=match["id"],
            )
            QMessageBox.information(
                self, "Form Created",
                f"Instance #{instance_id} created for {self._form_def.get('number')}.\n"
                "Form fill UI coming in a future update.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Error", str(exc))


class FormsTab(QWidget):
    """Tab 8 — Intel Forms workspace.

    Shows SAR and CAP forms as cards.  Live forms (those with a template
    record in master.db) can be launched directly.  Coming-soon forms are
    visually marked and show an informational dialog when clicked.
    """

    def __init__(
        self,
        incident_id: Optional[str] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._incident_id = incident_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        # Toolbar
        toolbar = QHBoxLayout()
        title = QLabel("Forms")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText)")

        subtitle = QLabel("SAR and CAP forms available for this incident")
        subtitle.setStyleSheet("font-size: 12px; color: palette(placeholderText);")

        toolbar.addWidget(title)
        toolbar.addWidget(subtitle)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        # SAR forms section
        sar_lbl = QLabel("SAR Forms")
        sar_lbl.setStyleSheet("font-size: 14px; font-weight: 700; margin-top: 6px;; color: palette(windowText)")
        layout.addWidget(sar_lbl)

        self._sar_grid_container = QWidget()
        self._sar_grid = QGridLayout(self._sar_grid_container)
        self._sar_grid.setContentsMargins(0, 0, 0, 0)
        self._sar_grid.setSpacing(12)
        self._sar_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._sar_grid_container)

        # CAP forms section
        cap_lbl = QLabel("CAP Forms")
        cap_lbl.setStyleSheet("font-size: 14px; font-weight: 700; margin-top: 10px;; color: palette(windowText)")
        layout.addWidget(cap_lbl)

        self._cap_grid_container = QWidget()
        self._cap_grid = QGridLayout(self._cap_grid_container)
        self._cap_grid.setContentsMargins(0, 0, 0, 0)
        self._cap_grid.setSpacing(12)
        self._cap_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(self._cap_grid_container)

        layout.addStretch()
        self._load_forms()

    def _load_forms(self) -> None:
        """Load catalog and live template info, then render form cards."""
        forms = _load_catalog_forms()
        live_ids = _get_available_template_ids(self._incident_id)

        sar_forms = [f for f in forms if f.get("category") == "SAR"]
        cap_forms = [f for f in forms if f.get("category") == "CAP"]

        self._render_section(self._sar_grid, sar_forms, live_ids, cols=6)
        self._render_section(self._cap_grid, cap_forms, live_ids, cols=6)

    def _render_section(
        self,
        grid: QGridLayout,
        forms: list[dict],
        live_ids: set[str],
        cols: int = 6,
    ) -> None:
        for form_def in forms:
            form_id = form_def.get("id", "")
            is_live = form_id in live_ids
            card = _FormCard(form_def, is_live=is_live, incident_id=self._incident_id)
            count = grid.count()
            grid.addWidget(card, count // cols, count % cols)
