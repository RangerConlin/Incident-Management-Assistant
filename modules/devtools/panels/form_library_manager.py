from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
)

from ..services.form_catalog import FormCatalog, FormEntry, TemplateEntry
from ..services.fema_fetch import FORM_IDS, fetch_latest
from ..services.binding_library import (
    BindingOption,
    delete_binding_option,
    load_binding_library,
    save_binding_option,
)
from ..services.pdf_mapgen import extract_acroform_fields
from modules.forms_creator.services import FormService
from modules.forms_creator.services.template_importer import (
    TemplateImportError,
    TemplateImportResult,
    import_pdf_template,
)
from modules.forms_creator.ui.MainWindow import MainWindow, ProfileTemplateContext
from utils.profile_manager import ProfileMeta, profile_manager


def _sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", value.strip())
    return cleaned or "default"


def _relative_template_dir(form_id: str, version: str) -> Path:
    return Path("templates") / _sanitize_component(form_id) / _sanitize_component(version)


def _default_pdf_relative_path(form_id: str, version: str) -> Path:
    directory = _relative_template_dir(form_id, version)
    filename = f"{_sanitize_component(form_id)}_{_sanitize_component(version)}.pdf"
    return directory / filename


def _default_mapping_relative_path(form_id: str, version: str) -> Path:
    return _relative_template_dir(form_id, version) / "bindings.json"


def _to_posix(path: Path) -> str:
    return path.as_posix()


_DEFAULT_SOURCES = [
    "constants",
    "incident",
    "operations",
    "planning",
    "logistics",
    "finance",
    "personnel",
    "computed",
    "form",
]


_NAMESPACE_GUIDE = [
    {
        "namespace": "incident",
        "source": "incident",
        "title": "Incident overview",
        "description": "General incident metadata such as the incident name, number, type, operational period, or location.",
        "keywords": ("incident", "name", "number", "type", "period", "location", "date"),
    },
    {
        "namespace": "operations",
        "source": "operations",
        "title": "Operations & assignments",
        "description": "Active operations section data such as ICS 204 assignments, tasking, and field team status values.",
        "keywords": ("operation", "assignment", "team", "division", "branch", "task", "tactical"),
    },
    {
        "namespace": "planning",
        "source": "planning",
        "title": "Planning products",
        "description": "Planning section information, IAP preparation details, situation updates, and map products.",
        "keywords": ("plan", "planning", "iap", "briefing", "situation", "map"),
    },
    {
        "namespace": "logistics",
        "source": "logistics",
        "title": "Logistics & support",
        "description": "Facilities, equipment, supply status, transportation, or staging resources managed by logistics.",
        "keywords": ("logistic", "supply", "equipment", "facility", "transport", "staging"),
    },
    {
        "namespace": "finance",
        "source": "finance",
        "title": "Finance & admin",
        "description": "Finance or administrative tracking such as timekeeping, expenses, and cost summaries.",
        "keywords": ("finance", "time", "cost", "expense", "admin", "pay"),
    },
    {
        "namespace": "personnel",
        "source": "personnel",
        "title": "Personnel directory",
        "description": "Roster entries, contact information, qualifications, and team member lookups.",
        "keywords": ("personnel", "contact", "phone", "email", "leader", "roster"),
    },
    {
        "namespace": "computed",
        "source": "computed",
        "title": "Calculated values",
        "description": "Numbers the app calculates for you, such as totals, durations, and other derived metrics.",
        "keywords": ("total", "count", "duration", "calculated", "computed", "average"),
    },
    {
        "namespace": "form",
        "source": "form",
        "title": "Form-specific fields",
        "description": "Information captured only on this form during editing, like free-form notes or reviewer signatures.",
        "keywords": ("note", "review", "signature", "form", "entered", "captured"),
    },
    {
        "namespace": "",
        "source": "constants",
        "title": "Static placeholder",
        "description": "Values stored in the profile constants catalogue. Keep the namespace that matches where the text is normally referenced and we'll mark the source as constants.",
        "keywords": ("static", "placeholder", "constant", "always", "fixed"),
    },
]


_NAMESPACE_DESCRIPTIONS: Dict[str, str] = {
    "incident": "Overall incident record: name, number, type, operational period, and location.",
    "operations": "Operations section data: assignments, tactics, team status, and tasking details.",
    "planning": "Planning section: situation reports, IAP preparation notes, objectives, and map products.",
    "logistics": "Logistics tracking: supply requests, equipment, transport, and facilities.",
    "finance": "Finance and administrative records such as timekeeping, expenses, and reimbursements.",
    "personnel": "Personnel directory with contact information, roles, and qualifications.",
    "computed": "Calculated values the app derives (totals, durations, metrics).",
    "form": "Information typed directly into this form while editing, such as notes or signatures.",
    "constants": "Use sparingly. Keep the namespace that matches where the text is referenced even if the source is constants.",
    "": "No namespace yet. The binding key will start with the cleaned field label until you choose one.",
}


_SOURCE_DESCRIPTIONS: Dict[str, str] = {
    "incident": "Read from the main incident record (name, objectives, operational period, etc.).",
    "operations": "Pull assignments, tactics, and team data recorded under Operations.",
    "planning": "Use Planning datasets such as situation updates, resource status, and map notes.",
    "logistics": "Gather logistics information like supplies, equipment, transport, and facilities.",
    "finance": "Use Finance/Admin timekeeping, expense, and reimbursement records.",
    "personnel": "Look up roster and qualification data from the personnel directory.",
    "constants": "Keep a fixed phrase from the profile constants catalogue so every form shows the same text.",
    "computed": "Run a calculation (totals, durations, metrics) when the PDF is generated.",
    "form": "Use the value entered while editing this form (review notes, signatures, etc.).",
}


def _describe_namespace(namespace: str) -> str:
    key = (namespace or "").strip().lower()
    if key in _NAMESPACE_DESCRIPTIONS:
        return _NAMESPACE_DESCRIPTIONS[key]
    if key:
        return (
            "Custom namespace. Use it when the value belongs to a specialised data set or plugin outside the standard "
            "incident sections."
        )
    return _NAMESPACE_DESCRIPTIONS[""]


def _describe_source(source: str, namespace: str) -> str:
    source_key = (source or "").strip().lower()
    namespace_key = (namespace or "").strip().lower()
    description = _SOURCE_DESCRIPTIONS.get(
        source_key,
        "Custom data provider. Use this label to remind editors where the app pulls the value from.",
    )

    if namespace_key and source_key == namespace_key:
        return (
            f"{description} It matches the namespace, so the app reads the value directly from that incident section."
        )
    if source_key == "constants":
        if namespace_key:
            return (
                f"{description} The binding key still starts with '{namespace}', but the text comes from the constants catalogue."
            )
        return description + " Use this when the same phrase should appear on every generated form."
    if source_key == "computed":
        return description + " The wizard runs the calculation each time the form is produced."
    if namespace_key and source_key:
        return (
            f"{description} The key keeps the namespace '{namespace}', but the data is fetched from the {source} provider."
        )
    if not source_key:
        return (
            "No source selected yet. The wizard will default to constants so the text stays the same for every form until you "
            "choose another option."
        )
    return description


def _collect_lines(widget: QPlainTextEdit) -> List[str]:
    return [line.strip() for line in widget.toPlainText().splitlines() if line.strip()]


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _pattern_from_phrase(phrase: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".*", phrase.lower())
    normalized = normalized.strip(".*")
    if not normalized:
        return ""
    return f"^{normalized}$"


def _pattern_from_key(key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".?", key.lower())
    normalized = normalized.strip(".?")
    if not normalized:
        return ""
    return f"^{normalized}$"


def _humanize_field_name(field_name: str) -> str:
    text = str(field_name or "")
    if not text:
        return ""
    text = text.replace("\\", " ")
    text = re.sub(r"[\[\]{}]", " ", text)
    text = re.sub(r"[._]+", " ", text)
    text = re.sub(r"[-/:]+", " ", text)
    text = re.sub(r"(?<!^)(?=[A-Z])", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().title()


def _auto_binding_option_from_field(
    field_name: str,
    *,
    namespace: str,
    source: str,
    seen_keys: Set[str],
    origin_profile: Optional[str],
    pdf_name: Optional[str] = None,
) -> Optional[Tuple[BindingOption, str]]:
    raw_name = str(field_name or "").strip()
    if not raw_name:
        return None

    namespace_value = (namespace or "").strip()
    source_value = (source or "").strip()

    human_label = _humanize_field_name(raw_name)
    fallback_slug = _slugify(raw_name)
    slug_source = human_label or raw_name
    slug = _slugify(slug_source) or fallback_slug
    stem = slug or fallback_slug or "field"

    base_key = ".".join(part for part in (namespace_value, slug) if part)
    if not base_key:
        base_key = ".".join(part for part in (namespace_value, stem) if part)
    if not base_key:
        base_key = stem
    if not base_key:
        return None

    candidate = base_key
    counter = 2
    while candidate in seen_keys:
        suffix = f"_{counter}"
        candidate = ".".join(part for part in (namespace_value, f"{stem}{suffix}") if part)
        counter += 1
    seen_keys.add(candidate)

    synonyms_candidates = [
        raw_name,
        re.sub(r"[._]+", " ", raw_name).strip(),
        human_label,
        human_label.lower() if human_label else "",
        stem.replace("_", " ") if stem else "",
    ]
    synonyms: List[str] = []
    seen_synonyms: Set[str] = set()
    for candidate_syn in synonyms_candidates:
        text = (candidate_syn or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen_synonyms:
            continue
        seen_synonyms.add(lowered)
        synonyms.append(text)

    patterns: Set[str] = set()
    key_pattern = _pattern_from_key(candidate)
    if key_pattern:
        patterns.add(key_pattern)
    for synonym in synonyms:
        pattern = _pattern_from_phrase(synonym)
        if pattern:
            patterns.add(pattern)

    base_desc = human_label or raw_name or "PDF field"
    description = f"Auto-generated binding for {base_desc}"
    if raw_name and raw_name.lower() != base_desc.lower():
        description += f" (PDF field '{raw_name}')"
    if pdf_name:
        description += f" — imported from {pdf_name}"

    option = BindingOption(
        key=candidate,
        source=source_value or (namespace_value or "constants"),
        description=description,
        synonyms=synonyms,
        patterns=sorted(patterns),
        origin_profile=origin_profile,
        is_defined_in_active=True,
        extra={"pdf_field": raw_name},
    )

    preview_label = human_label or raw_name
    return option, preview_label


class BindingEditorDialog(QDialog):
    """Interactive helper for creating or editing a binding entry."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        option: Optional[BindingOption] = None,
        namespaces: Sequence[str] = (),
        active_profile: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binding Editor")
        self._option = option
        self._active_profile = active_profile
        self._original_key = option.key if option else None
        self._extra = dict(option.extra) if option else {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Bindings map PDF fields to canonical keys used across the incident. "
            "Provide a descriptive key, optional synonyms for search, and "
            "regex patterns that help the auto-mapper spot the field."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if option and not option.is_defined_in_active:
            inherit_note = QLabel(
                "This binding is inherited from profile "
                f"<b>{option.origin_profile or 'unknown'}</b>. "
                "Saving will create an override in the active profile."
            )
            inherit_note.setWordWrap(True)
            layout.addWidget(inherit_note)

        form = QFormLayout()

        self.txt_key = QLineEdit(option.key if option else "")
        self.txt_key.setPlaceholderText("e.g., incident.name")
        form.addRow("Key", self.txt_key)

        self.cbo_source = QComboBox()
        self.cbo_source.setEditable(True)
        for src in _DEFAULT_SOURCES:
            self.cbo_source.addItem(src)
        if option:
            self.cbo_source.setCurrentText(option.source or "constants")
        else:
            self.cbo_source.setCurrentText("constants")
        form.addRow("Source", self.cbo_source)

        self.txt_desc = QLineEdit(option.description if option else "")
        self.txt_desc.setPlaceholderText("Short description shown to authors")
        form.addRow("Description", self.txt_desc)

        self.txt_synonyms = QPlainTextEdit()
        self.txt_synonyms.setPlaceholderText("One synonym per line")
        if option and option.synonyms:
            self.txt_synonyms.setPlainText("\n".join(option.synonyms))
        form.addRow("Synonyms", self.txt_synonyms)

        self.txt_patterns = QPlainTextEdit()
        self.txt_patterns.setPlaceholderText("One regex pattern per line")
        if option and option.patterns:
            self.txt_patterns.setPlainText("\n".join(option.patterns))
        form.addRow("Patterns", self.txt_patterns)

        layout.addLayout(form)

        helper_box = QGroupBox("Binding Helper")
        helper_layout = QVBoxLayout(helper_box)

        helper_form = QFormLayout()
        self.cbo_namespace = QComboBox()
        self.cbo_namespace.setEditable(True)
        unique_namespaces = sorted({ns for ns in namespaces if ns})
        for ns in unique_namespaces:
            self.cbo_namespace.addItem(ns)
        if option and option.key:
            ns_guess = option.key.split(".")[0]
            self.cbo_namespace.setCurrentText(ns_guess)
        helper_form.addRow("Namespace", self.cbo_namespace)

        self.txt_helper_label = QLineEdit()
        self.txt_helper_label.setPlaceholderText("Label on the PDF (e.g., Incident Name)")
        helper_form.addRow("Field label", self.txt_helper_label)
        helper_layout.addLayout(helper_form)

        helper_actions = QHBoxLayout()
        self.btn_generate = QPushButton("Build key & synonyms")
        self.btn_generate.clicked.connect(self._apply_helper)
        helper_actions.addWidget(self.btn_generate)

        self.btn_patterns = QPushButton("Generate patterns from synonyms")
        self.btn_patterns.clicked.connect(self._generate_patterns_from_synonyms)
        helper_actions.addWidget(self.btn_patterns)

        helper_actions.addStretch(1)
        helper_layout.addLayout(helper_actions)

        helper_hint = QLabel(
            "Use the helper to convert a plain-language label into a canonical key. "
            "Synonyms feed the search experience and patterns help auto-mapping."
        )
        helper_hint.setWordWrap(True)
        helper_layout.addWidget(helper_hint)

        layout.addWidget(helper_box)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Binding preview")
        layout.addWidget(self.preview)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.txt_key.textChanged.connect(self._update_state)
        self.cbo_source.editTextChanged.connect(self._update_state)
        self.txt_desc.textChanged.connect(self._update_state)
        self.txt_synonyms.textChanged.connect(self._update_state)
        self.txt_patterns.textChanged.connect(self._update_state)

        self._update_state()

    def _apply_helper(self) -> None:
        namespace = self.cbo_namespace.currentText().strip()
        label = self.txt_helper_label.text().strip()
        if not label:
            QMessageBox.information(self, "Binding Helper", "Enter a field label to build from.")
            return

        slug = _slugify(label)
        key_parts = [namespace, slug] if namespace else [slug]
        key = ".".join(part for part in key_parts if part)
        if key:
            self.txt_key.setText(key)

        if not self.txt_desc.text().strip():
            self.txt_desc.setText(label)

        synonyms = set(_collect_lines(self.txt_synonyms))
        synonyms.add(label)
        synonyms.add(label.title())
        synonyms.add(label.lower())
        self.txt_synonyms.setPlainText("\n".join(sorted(s.strip() for s in synonyms if s.strip())))

        if namespace and namespace in _DEFAULT_SOURCES:
            self.cbo_source.setCurrentText(namespace)

        self._generate_patterns_from_synonyms()

    def _generate_patterns_from_synonyms(self) -> None:
        patterns = set(_collect_lines(self.txt_patterns))
        key_pattern = _pattern_from_key(self.txt_key.text())
        if key_pattern:
            patterns.add(key_pattern)
        for synonym in _collect_lines(self.txt_synonyms):
            pat = _pattern_from_phrase(synonym)
            if pat:
                patterns.add(pat)
        self.txt_patterns.setPlainText("\n".join(sorted(patterns)))

    def _update_state(self) -> None:
        option = self._build_option()
        payload = option.to_payload()
        preview_data = {"key": option.key, **payload}
        try:
            preview_text = json.dumps(preview_data, indent=2, ensure_ascii=False)
        except Exception:
            preview_text = str(preview_data)
        self.preview.setPlainText(preview_text)

        error = self._validate()
        ok_button = self.buttons.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setEnabled(error is None)

    def _validate(self) -> Optional[str]:
        key = self.txt_key.text().strip()
        if not key:
            return "Key is required."
        if any(ch.isspace() for ch in key):
            return "Key cannot contain whitespace."
        return None

    def _build_option(self) -> BindingOption:
        key = self.txt_key.text().strip()
        source = self.cbo_source.currentText().strip() or "constants"
        description = self.txt_desc.text().strip()
        synonyms = _collect_lines(self.txt_synonyms)
        patterns = _collect_lines(self.txt_patterns)
        origin = self._active_profile or (self._option.origin_profile if self._option else None)
        return BindingOption(
            key=key,
            source=source,
            description=description,
            synonyms=synonyms,
            patterns=patterns,
            origin_profile=origin,
            is_defined_in_active=True,
            extra=dict(self._extra),
        )

    def _on_accept(self) -> None:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Binding Editor", error)
            return
        self.accept()

    def result_option(self) -> BindingOption:
        return self._build_option()

    @property
    def original_key(self) -> Optional[str]:
        return self._original_key

class BindingWizard(QWizard):
    """Guided flow for creating a binding option."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        namespaces: Sequence[str] = (),
        active_profile: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binding Wizard")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setMinimumSize(820, 640)
        self.resize(1040, 760)
        self._active_profile = active_profile
        self._result: Optional[BindingOption] = None
        self._updating_helper = False
        self._helper_entries: List[Dict[str, Any]] = []

        namespace_choices = sorted({ns for ns in namespaces if ns} | set(_DEFAULT_SOURCES))

        self.page_intro = QWizardPage()
        self.page_intro.setTitle("Describe the field")
        self.page_intro.setSubTitle(
            "Tell us how the PDF field is labelled so we can suggest a binding key."
        )
        intro_layout = QVBoxLayout(self.page_intro)
        intro_layout.setSpacing(16)
        intro_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        intro_layout.addWidget(splitter, 1)

        details_panel = QWidget()
        details_panel_layout = QVBoxLayout(details_panel)
        details_panel_layout.setContentsMargins(0, 0, 0, 0)
        details_panel_layout.setSpacing(12)

        details_group = QGroupBox("Field details")
        details_group.setMinimumWidth(320)
        details_form = QFormLayout()
        details_form.setSpacing(12)
        details_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        details_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        details_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        details_form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        details_group.setLayout(details_form)

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Label on the PDF, e.g. Incident Name")
        details_form.addRow("Field label", self.label_edit)

        self.namespace_combo = QComboBox()
        self.namespace_combo.setEditable(True)
        self.namespace_combo.setToolTip(
            "First segment of the binding key. Choose the incident data area that owns the value, "
            "such as incident, operations, or planning."
        )
        for choice in namespace_choices:
            self.namespace_combo.addItem(choice)
        if "incident" in namespace_choices:
            self.namespace_combo.setCurrentText("incident")
        elif namespace_choices:
            self.namespace_combo.setCurrentIndex(0)
        else:
            self.namespace_combo.setEditText("incident")
        self.namespace_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        namespace_field = QWidget()
        namespace_layout = QVBoxLayout(namespace_field)
        namespace_layout.setContentsMargins(0, 0, 0, 0)
        namespace_layout.setSpacing(4)
        namespace_layout.addWidget(self.namespace_combo)
        self.namespace_hint = QLabel()
        self.namespace_hint.setWordWrap(True)
        self.namespace_hint.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.namespace_hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        namespace_layout.addWidget(self.namespace_hint)
        details_form.addRow("Namespace", namespace_field)

        self.source_combo = QComboBox()
        self.source_combo.setEditable(True)
        self.source_combo.setToolTip(
            "Describes where the value is pulled from when a form is generated. This usually matches "
            "the namespace; use constants for fixed placeholders or computed for derived metrics."
        )
        for src in _DEFAULT_SOURCES:
            self.source_combo.addItem(src)
        if "incident" in _DEFAULT_SOURCES:
            self.source_combo.setCurrentText("incident")
        self.source_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        source_field = QWidget()
        source_layout = QVBoxLayout(source_field)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(4)
        source_layout.addWidget(self.source_combo)
        self.source_hint = QLabel()
        self.source_hint.setWordWrap(True)
        self.source_hint.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.source_hint.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        source_layout.addWidget(self.source_hint)
        details_form.addRow("Source", source_field)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Short help text for other authors")
        details_form.addRow("Description", self.description_edit)

        details_panel_layout.addWidget(details_group)

        self.selection_summary_label = QLabel()
        self.selection_summary_label.setWordWrap(True)
        self.selection_summary_label.setTextFormat(Qt.RichText)
        self.selection_summary_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        details_panel_layout.addWidget(self.selection_summary_label)
        details_panel_layout.addStretch(1)

        splitter.addWidget(details_panel)

        helper_panel = QWidget()
        helper_panel_layout = QVBoxLayout(helper_panel)
        helper_panel_layout.setContentsMargins(0, 0, 0, 0)
        helper_panel_layout.setSpacing(12)

        help_tabs = QTabWidget()
        help_tabs.setDocumentMode(True)
        helper_panel_layout.addWidget(help_tabs, 1)

        guide_tab = QWidget()
        guide_layout = QVBoxLayout(guide_tab)
        guide_layout.setContentsMargins(12, 12, 12, 12)
        guide_layout.setSpacing(12)

        helper_intro = QLabel(
            "Pick the statement that matches where editors maintain this value. Namespace = data folder, Source = how the app "
            "fetches it when generating a PDF."
        )
        helper_intro.setWordWrap(True)
        guide_layout.addWidget(helper_intro)

        helper_scroll = QScrollArea()
        helper_scroll.setWidgetResizable(True)
        helper_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        guide_layout.addWidget(helper_scroll, 1)

        helper_container = QWidget()
        helper_scroll.setWidget(helper_container)
        helper_cards_layout = QVBoxLayout(helper_container)
        helper_cards_layout.setContentsMargins(0, 0, 0, 0)
        helper_cards_layout.setSpacing(12)

        self.helper_button_group = QButtonGroup(self)
        self.helper_button_group.setExclusive(True)

        for entry in _NAMESPACE_GUIDE:
            card = QWidget()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(6)

            option_button = QRadioButton(entry["title"])
            option_button.setToolTip(entry["description"])
            option_font = option_button.font()
            option_font.setBold(True)
            option_button.setFont(option_font)
            card_layout.addWidget(option_button)

            option_desc = QLabel(entry["description"])
            option_desc.setWordWrap(True)
            option_desc.setIndent(18)
            card_layout.addWidget(option_desc)

            helper_cards_layout.addWidget(card)
            self.helper_button_group.addButton(option_button)
            option_button.toggled.connect(
                lambda checked, ns=entry["namespace"], src=entry["source"]: self._on_helper_choice(ns, src, checked)
            )

            record = dict(entry)
            record["button"] = option_button
            self._helper_entries.append(record)

        helper_cards_layout.addStretch(1)

        help_tabs.addTab(guide_tab, "Namespace guide")

        basics_tab = QWidget()
        basics_layout = QVBoxLayout(basics_tab)
        basics_layout.setContentsMargins(0, 0, 0, 0)
        basics_layout.setSpacing(0)

        basics_scroll = QScrollArea()
        basics_scroll.setWidgetResizable(True)
        basics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        basics_layout.addWidget(basics_scroll)

        basics_container = QWidget()
        basics_scroll.setWidget(basics_container)
        basics_content_layout = QVBoxLayout(basics_container)
        basics_content_layout.setContentsMargins(12, 12, 12, 12)
        basics_content_layout.setSpacing(12)

        namespace_help = QLabel(
            "<b>Namespace</b>: Think of this as the folder in the incident data tree. Choose where someone keeps the value — "
            "<code>incident</code> for overall details, <code>operations</code> for assignments, <code>planning</code> for "
            "situation updates, and so on."
        )
        namespace_help.setWordWrap(True)
        namespace_help.setTextFormat(Qt.RichText)
        basics_content_layout.addWidget(namespace_help)

        source_help = QLabel(
            "<b>Source</b>: Explains how the app fills the value when a PDF is generated. Match the namespace to read directly "
            "from that section, pick <code>constants</code> for headers that never change, and use <code>computed</code> for "
            "totals or other calculated numbers."
        )
        source_help.setWordWrap(True)
        source_help.setTextFormat(Qt.RichText)
        basics_content_layout.addWidget(source_help)

        binding_recipe_help = QLabel(
            "<b>Together</b>: The binding key starts with the namespace and the wizard cleans the PDF label for the rest. "
            "Source simply tells the generator where that key gets its data."
        )
        binding_recipe_help.setWordWrap(True)
        binding_recipe_help.setTextFormat(Qt.RichText)
        basics_content_layout.addWidget(binding_recipe_help)

        examples_help = QLabel(
            "<b>Examples</b>:<ul>"
            "<li><code>incident.name</code> — namespace <code>incident</code>, source <code>incident</code>; pulls from the main incident record.</li>"
            "<li><code>operations.team_1.leader</code> — namespace <code>operations</code>, source <code>operations</code>; reads from the assignment roster.</li>"
            "<li><code>incident.footer</code> — namespace <code>incident</code>, source <code>constants</code>; prints the same footer text every time.</li>"
            "<li><code>form.reviewer_signature</code> — namespace <code>form</code>, source <code>form</code>; captured while filling out the form.</li>"
            "</ul>"
        )
        examples_help.setWordWrap(True)
        examples_help.setTextFormat(Qt.RichText)
        basics_content_layout.addWidget(examples_help)

        binding_payload_help = QLabel(
            "When you finish we store the binding key, the source, your description, plus any synonyms and patterns so other "
            "editors can auto-match this PDF field in the future."
        )
        binding_payload_help.setWordWrap(True)
        binding_payload_help.setTextFormat(Qt.RichText)
        basics_content_layout.addWidget(binding_payload_help)

        reminder_help = QLabel(
            "Need a refresher later? The wizard keeps the namespace + source breakdown below the form fields and previews the binding payload on the next step."
        )
        reminder_help.setWordWrap(True)
        basics_content_layout.addWidget(reminder_help)
        basics_content_layout.addStretch(1)

        help_tabs.addTab(basics_tab, "Binding basics")

        self.suggestion_label = QLabel()
        self.suggestion_label.setWordWrap(True)
        self.suggestion_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        helper_panel_layout.addWidget(self.suggestion_label)

        splitter.addWidget(helper_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([420, 540])

        intro_layout.addSpacing(8)

        intro_hint = QLabel(
            "Namespace is the first part of the key, source explains the data pipeline, and the preview shows every piece before you save."
        )
        intro_hint.setWordWrap(True)
        intro_layout.addWidget(intro_hint)
        intro_layout.addStretch(1)
        self.addPage(self.page_intro)

        self.page_refine = QWizardPage()
        self.page_refine.setTitle("Refine the binding")
        self.page_refine.setSubTitle("Adjust the generated key, synonyms, and patterns.")
        refine_layout = QVBoxLayout(self.page_refine)
        refine_layout.setSpacing(12)
        refine_layout.setContentsMargins(0, 0, 0, 0)
        refine_form = QFormLayout()
        refine_form.setSpacing(12)
        refine_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        refine_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("e.g. incident.name")
        refine_form.addRow("Binding key", self.key_edit)

        self.synonyms_edit = QPlainTextEdit()
        self.synonyms_edit.setPlaceholderText("One synonym per line")
        self.synonyms_edit.setMinimumHeight(110)
        refine_form.addRow("Synonyms", self.synonyms_edit)

        self.patterns_edit = QPlainTextEdit()
        self.patterns_edit.setPlaceholderText("One regex pattern per line")
        self.patterns_edit.setMinimumHeight(110)
        refine_form.addRow("Patterns", self.patterns_edit)

        refine_layout.addLayout(refine_form)
        self.btn_suggest = QPushButton("Suggest from field label")
        self.btn_suggest.clicked.connect(self._apply_suggestion)
        refine_layout.addWidget(self.btn_suggest)
        refine_hint = QLabel(
            "Use the suggestion button to auto-build keys, synonyms, and patterns from the label."
        )
        refine_hint.setWordWrap(True)
        refine_layout.addWidget(refine_hint)

        self.binding_recipe_label = QLabel()
        self.binding_recipe_label.setWordWrap(True)
        self.binding_recipe_label.setTextFormat(Qt.RichText)
        self.binding_recipe_label.setMinimumHeight(120)
        refine_layout.addWidget(self.binding_recipe_label)
        refine_layout.addStretch(1)
        self.addPage(self.page_refine)

        self.page_review = QWizardPage()
        self.page_review.setTitle("Review")
        self.page_review.setSubTitle("Confirm the binding details before saving.")
        review_layout = QVBoxLayout(self.page_review)
        review_layout.setSpacing(12)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_hint = QLabel("Click Finish to store the binding in the active profile.")
        review_hint.setWordWrap(True)
        review_layout.addWidget(review_hint)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setPlaceholderText("Binding summary will appear here.")
        self.summary.setMinimumHeight(260)
        review_layout.addWidget(self.summary)
        self.addPage(self.page_review)

        self.label_edit.textChanged.connect(self._on_label_changed)
        self.namespace_combo.editTextChanged.connect(self._on_namespace_changed)
        self.source_combo.editTextChanged.connect(self._on_source_changed)
        self.description_edit.textChanged.connect(self._update_summary)
        self.key_edit.textChanged.connect(self._update_summary)
        self.synonyms_edit.textChanged.connect(self._update_summary)
        self.patterns_edit.textChanged.connect(self._update_summary)
        self.currentIdChanged.connect(self._on_page_changed)

        self._sync_helper_buttons(
            self.namespace_combo.currentText().strip(), self.source_combo.currentText().strip()
        )
        self._update_helper_suggestion(self.label_edit.text())
        self._update_summary()

    def _on_label_changed(self, text: str) -> None:
        if not self.description_edit.text().strip():
            self.description_edit.setText(text.strip())
        self._update_helper_suggestion(text)
        self._update_summary()

    def _apply_suggestion(self) -> None:
        label = self.label_edit.text().strip()
        if not label:
            QMessageBox.information(
                self, "Binding Wizard", "Enter a field label before generating suggestions."
            )
            return
        namespace = self.namespace_combo.currentText().strip()
        slug = _slugify(label) or "field"
        key_parts = [namespace, slug] if namespace else [slug]
        key = ".".join(part for part in key_parts if part)
        self.key_edit.setText(key)

        if not self.description_edit.text().strip():
            self.description_edit.setText(label)

        synonyms = set(_collect_lines(self.synonyms_edit))
        synonyms.add(label)
        synonyms.add(label.lower())
        synonyms.add(label.title())
        synonyms.add(slug.replace("_", " "))
        self.synonyms_edit.setPlainText("\n".join(sorted(s for s in synonyms if s.strip())))


        if namespace and namespace in _DEFAULT_SOURCES:
            self.source_combo.setCurrentText(namespace)

        patterns = set(_collect_lines(self.patterns_edit))
        key_pattern = _pattern_from_key(key)
        if key_pattern:
            patterns.add(key_pattern)
        for synonym in _collect_lines(self.synonyms_edit):
            pattern = _pattern_from_phrase(synonym)
            if pattern:
                patterns.add(pattern)
        self.patterns_edit.setPlainText("\n".join(sorted(patterns)))

        self._update_summary()

    def _on_page_changed(self, _page_id: int) -> None:
        if self.currentPage() is self.page_review:
            self._update_summary()

    def _update_summary(self) -> None:
        self._update_namespace_source_summary()
        option = self._build_option()
        if not option.key:
            self.summary.setPlainText("Provide a binding key to see the preview.")
            self._update_recipe_description()
            return
        payload = option.to_payload()
        preview = {"key": option.key, **payload}
        try:
            self.summary.setPlainText(json.dumps(preview, indent=2, ensure_ascii=False))
        except Exception:
            self.summary.setPlainText(str(preview))
        self._update_recipe_description()

    def _update_namespace_source_summary(self) -> None:
        namespace_text = self.namespace_combo.currentText().strip()
        source_text = self.source_combo.currentText().strip() or "constants"
        label_text = self.label_edit.text().strip()

        namespace_description = _describe_namespace(namespace_text)
        source_description = _describe_source(source_text, namespace_text)

        if hasattr(self, "namespace_hint"):
            self.namespace_hint.setText(namespace_description)
        if hasattr(self, "source_hint"):
            self.source_hint.setText(source_description)

        if hasattr(self, "selection_summary_label"):
            namespace_display = namespace_text or "(none yet)"
            source_display = source_text or "constants"
            namespace_label_html = escape(namespace_display)
            source_label_html = escape(source_display)
            namespace_desc_html = escape(namespace_description)
            source_desc_html = escape(source_description)
            summary_parts = [
                f"<b>Namespace</b> = <code>{namespace_label_html}</code>: {namespace_desc_html}",
                f"<b>Source</b> = <code>{source_label_html}</code>: {source_desc_html}",
            ]
            if label_text:
                slug = _slugify(label_text) or "field"
                key_preview = ".".join(part for part in (namespace_text, slug) if part)
                key_preview_html = escape(key_preview)
                summary_parts.append(
                    f"<b>Preview key</b>: <code>{key_preview_html}</code> (namespace + cleaned field label)."
                )
            else:
                summary_parts.append("Add the PDF field label so we can preview the binding key.")
            self.selection_summary_label.setText("<br>".join(summary_parts))

    def _update_recipe_description(self) -> None:
        if not hasattr(self, "binding_recipe_label"):
            return

        option = self._build_option()
        namespace_text = self.namespace_combo.currentText().strip()
        label_text = self.label_edit.text().strip()
        key_text = option.key.strip()

        if key_text:
            key_parts = key_text.split(".")
            if len(key_parts) > 1:
                namespace_part = key_parts[0]
                field_part = ".".join(key_parts[1:])
            else:
                namespace_part = ""
                field_part = key_parts[0]
            example_key = key_text
        else:
            slug = _slugify(label_text) or "field"
            namespace_part = namespace_text
            field_part = slug
            example_key = ".".join(part for part in (namespace_part, field_part) if part)

        namespace_display = namespace_part or namespace_text
        namespace_label = namespace_display or "(none yet)"
        namespace_description = _describe_namespace(namespace_display)
        namespace_sentence = (
            f"<li><b>Step 1:</b> Namespace = <code>{escape(namespace_label)}</code>. {escape(namespace_description)}</li>"
        )

        if label_text:
            label_sentence = f" from the label “{escape(label_text)}”"
        else:
            label_sentence = ""

        field_sentence = (
            f"<li><b>Step 2:</b> Field name = <code>{escape(field_part)}</code>{label_sentence}. "
            "We turn the PDF field label into a short key you can reuse."
            "</li>"
        )

        if example_key:
            combine_sentence = (
                f"<li><b>Step 3:</b> Join the pieces → <code>{escape(example_key)}</code>. "
                "This is the binding key shown on the next page."
                "</li>"
            )
        else:
            combine_sentence = (
                "<li><b>Step 3:</b> Add a field name so we can show the finished binding key.</li>"
            )

        source_text = option.source.strip() or "constants"
        source_sentence = _describe_source(source_text, namespace_display)
        source_sentence_html = escape(source_sentence)

        message = (
            "<p><b>How this binding comes together</b></p>"
            "<ol>"
            f"{namespace_sentence}"
            f"{field_sentence}"
            f"{combine_sentence}"
            "</ol>"
            f"<p><b>Source</b> = <code>{escape(source_text)}</code>. {source_sentence_html}</p>"
            "<p>When you finish, we save the binding key, source, description, and any synonyms or patterns so other editors can auto-map this PDF field.</p>"
        )

        self.binding_recipe_label.setText(message)

    def _on_namespace_changed(self, text: str) -> None:
        if not self._updating_helper:
            self._sync_helper_buttons(text, self.source_combo.currentText())
        self._update_summary()
        self._update_helper_suggestion(self.label_edit.text())

    def _on_source_changed(self, text: str) -> None:
        if not self._updating_helper:
            self._sync_helper_buttons(self.namespace_combo.currentText(), text)
        self._update_summary()
        self._update_helper_suggestion(self.label_edit.text())

    def _on_helper_choice(self, namespace: str, source: str, checked: bool) -> None:
        if self._updating_helper or not checked:
            return
        self._updating_helper = True
        try:
            if namespace:
                self.namespace_combo.setCurrentText(namespace)
            if source:
                self.source_combo.setCurrentText(source)
        finally:
            self._updating_helper = False
        self._sync_helper_buttons(
            self.namespace_combo.currentText().strip(), self.source_combo.currentText().strip()
        )
        self._update_summary()
        self._update_helper_suggestion(self.label_edit.text())

    def _sync_helper_buttons(self, namespace: str, source: str) -> None:
        if not self._helper_entries:
            return
        ns_value = (namespace or "").strip().lower()
        src_value = (source or "").strip().lower()
        self._updating_helper = True
        try:
            for entry in self._helper_entries:
                button = entry.get("button")
                if not isinstance(button, QRadioButton):
                    continue
                entry_ns = (entry.get("namespace") or "").strip().lower()
                entry_src = (entry.get("source") or "").strip().lower()
                matches = False
                if entry_ns:
                    matches = ns_value == entry_ns
                    if matches and entry_src:
                        matches = src_value == entry_src or (
                            not src_value and entry_src == entry_ns
                        )
                elif entry_src:
                    matches = src_value == entry_src
                button.setChecked(matches)
        finally:
            self._updating_helper = False

    def _update_helper_suggestion(self, label: Optional[str] = None) -> None:
        if not hasattr(self, "suggestion_label"):
            return
        label_text = (label or "").strip().lower()
        active_entry: Optional[Dict[str, Any]] = None
        for entry in self._helper_entries:
            button = entry.get("button")
            if isinstance(button, QRadioButton) and button.isChecked():
                active_entry = entry
                break
        if active_entry:
            ns = (active_entry.get("namespace") or "").strip()
            src = (active_entry.get("source") or "").strip()
            description = active_entry.get("description", "")
            if ns:
                message = (
                    f"Using {active_entry.get('title', ns)} — namespace '{ns}', source '{src}'. "
                    f"{description}"
                )
            else:
                message = (
                    f"Using {active_entry.get('title', src)} — source '{src}'. {description}"
                )
            self.suggestion_label.setText(message)
            return

        suggestion: Optional[Dict[str, Any]] = None
        if label_text:
            for entry in self._helper_entries:
                keywords = entry.get("keywords", ()) or ()
                for keyword in keywords:
                    if keyword and keyword.lower() in label_text:
                        suggestion = entry
                        break
                if suggestion:
                    break

        if suggestion:
            ns = (suggestion.get("namespace") or "").strip()
            src = (suggestion.get("source") or "").strip()
            description = suggestion.get("description", "")
            if ns:
                message = (
                    f"Suggestion: {suggestion.get('title', ns)} — use namespace '{ns}' and source '{src}'. "
                    f"{description}"
                )
            else:
                message = (
                    f"Suggestion: {suggestion.get('title', src)} — keep your namespace and set the source to '{src}'. "
                    f"{description}"
                )
            self.suggestion_label.setText(message)
        else:
            self.suggestion_label.setText(
                "Need a starting point? Namespace is the data folder (incident, operations, planning). Source tells the wizard "
                "where to fetch the value — match the namespace for live data or choose constants/computed when the text is "
                "fixed or calculated."
            )

    def _build_option(self) -> BindingOption:
        key = self.key_edit.text().strip()
        source = self.source_combo.currentText().strip() or "constants"
        description = self.description_edit.text().strip()
        synonyms = _collect_lines(self.synonyms_edit)
        patterns = _collect_lines(self.patterns_edit)
        return BindingOption(
            key=key,
            source=source,
            description=description,
            synonyms=synonyms,
            patterns=patterns,
            origin_profile=self._active_profile,
            is_defined_in_active=True,
            extra={},
        )

    def validateCurrentPage(self) -> bool:
        current = self.currentPage()
        if current is self.page_intro:
            if not self.label_edit.text().strip():
                QMessageBox.warning(
                    self, "Binding Wizard", "Please provide the label from the PDF form."
                )
                return False
        elif current is self.page_refine:
            key = self.key_edit.text().strip()
            if not key:
                QMessageBox.warning(
                    self, "Binding Wizard", "Enter a binding key before continuing."
                )
                return False
            if any(ch.isspace() for ch in key):
                QMessageBox.warning(
                    self, "Binding Wizard", "Binding keys cannot contain whitespace."
                )
                return False
        return super().validateCurrentPage()

    def accept(self) -> None:
        option = self._build_option()
        if not option.key:
            QMessageBox.warning(self, "Binding Wizard", "Binding key is required.")
            return
        self._result = option
        super().accept()

    def result_option(self) -> Optional[BindingOption]:
        return self._result

class NewFormDialog(QDialog):
    """Collect the metadata required to register a new form."""

    def __init__(self, existing_ids: Iterable[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Form")
        self._existing = {str(fid).strip().lower() for fid in existing_ids}
        self._result: Optional[Tuple[str, str]] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        layout.addLayout(form)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g. ICS_205")
        form.addRow("Form ID", self.id_edit)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Human-readable title")
        form.addRow("Title", self.title_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        form_id = self.id_edit.text().strip()
        if not form_id:
            QMessageBox.warning(self, "New Form", "Form ID is required.")
            return
        if form_id.lower() in self._existing:
            QMessageBox.warning(self, "New Form", "A form with that ID already exists.")
            return
        title = self.title_edit.text().strip() or form_id
        self._result = (form_id, title)
        self.accept()

    def result(self) -> Optional[Tuple[str, str]]:
        return self._result


class AddVersionDialog(QDialog):
    """Dialog used to capture version metadata and select a PDF."""

    def __init__(
        self,
        form_id: str,
        existing_versions: Iterable[str],
        profiles: Sequence[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add Version — {form_id}")
        self._existing = {str(v).strip().lower() for v in existing_versions}
        self._pdf_path: Optional[Path] = None
        self._result: Optional[Tuple[str, str, Path]] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        layout.addLayout(form)

        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("e.g. 2025.09")
        form.addRow("Version", self.version_edit)

        self.profile_combo = QComboBox()
        for pid in profiles:
            self.profile_combo.addItem(pid)
        form.addRow("Profile", self.profile_combo)

        file_row = QHBoxLayout()
        self.pdf_label = QLabel("No file selected")
        self.pdf_label.setMinimumWidth(260)
        file_row.addWidget(self.pdf_label, 1)
        browse = QPushButton("Choose PDF…")
        browse.clicked.connect(self._choose_pdf)
        file_row.addWidget(browse)
        layout.addLayout(file_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_pdf(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Add Version", "Please choose a PDF file.")
            return
        self._pdf_path = path
        self.pdf_label.setText(path.name)

    def _on_accept(self) -> None:
        version = self.version_edit.text().strip()
        if not version:
            QMessageBox.warning(self, "Add Version", "Version is required.")
            return
        if version.lower() in self._existing:
            QMessageBox.warning(self, "Add Version", "A template for that version already exists.")
            return
        profile_id = self.profile_combo.currentText().strip()
        if not profile_id:
            QMessageBox.warning(self, "Add Version", "Select a profile to store the template.")
            return
        if self._pdf_path is None:
            QMessageBox.warning(self, "Add Version", "Choose a PDF to continue.")
            return
        self._result = (version, profile_id, self._pdf_path)
        self.accept()

    def result(self) -> Optional[Tuple[str, str, Path]]:
        return self._result


class ProfileSelectionDialog(QDialog):
    """Multi-select helper for assigning template versions to profiles."""

    def __init__(
        self,
        form_id: str,
        version: str,
        profiles: Sequence[str],
        selected: Sequence[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Profiles — {form_id} {version}")

        layout = QVBoxLayout(self)

        intro = QLabel("Select incident profiles that should use this form version.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        selected_set = {s for s in selected}
        for pid in profiles:
            item = QListWidgetItem(pid)
            if pid in selected_set:
                item.setSelected(True)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_profiles(self) -> List[str]:
        return [item.text() for item in self.list_widget.selectedItems()]


class BindingLibraryEditorDialog(QDialog):
    """Expanded editor for managing binding entries."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binding Library")
        self.resize(840, 520)

        self._options: List[BindingOption] = []
        self._filtered: List[BindingOption] = []
        self._active: Optional[str] = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Bindings connect PDF form fields to incident data keys. Use the guided wizard if you're not sure which key to use."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        search_row = QHBoxLayout()
        search_label = QLabel("Filter")
        search_row.addWidget(search_label)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by key, description, synonym, or profile…")
        search_row.addWidget(self.search_edit, 1)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Key", "Source", "Description", "Defined In"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table)

        details_group = QGroupBox("Binding Details", self)
        details_layout = QFormLayout(details_group)
        self.details_key = QLabel("—")
        self.details_key.setTextFormat(Qt.PlainText)
        details_layout.addRow("Key", self.details_key)
        self.details_source = QLabel("—")
        self.details_source.setTextFormat(Qt.PlainText)
        details_layout.addRow("Source", self.details_source)
        self.details_origin = QLabel("—")
        self.details_origin.setTextFormat(Qt.PlainText)
        details_layout.addRow("Defined In", self.details_origin)
        self.details_description = QLabel("—")
        self.details_description.setTextFormat(Qt.PlainText)
        self.details_description.setWordWrap(True)
        details_layout.addRow("Description", self.details_description)
        self.details_synonyms = QLabel("—")
        self.details_synonyms.setTextFormat(Qt.PlainText)
        self.details_synonyms.setWordWrap(True)
        details_layout.addRow("Synonyms", self.details_synonyms)
        self.details_patterns = QLabel("—")
        self.details_patterns.setTextFormat(Qt.PlainText)
        self.details_patterns.setWordWrap(True)
        details_layout.addRow("Patterns", self.details_patterns)
        layout.addWidget(details_group)

        button_row = QHBoxLayout()
        self.btn_generate_pdf = QPushButton("Generate from PDF…")
        self.btn_wizard = QPushButton("Wizard…")
        self.btn_add = QPushButton("Advanced Editor…")
        self.btn_edit = QPushButton("Edit…")
        self.btn_delete = QPushButton("Delete")
        button_row.addWidget(self.btn_generate_pdf)
        button_row.addWidget(self.btn_wizard)
        button_row.addWidget(self.btn_add)
        button_row.addWidget(self.btn_edit)
        button_row.addWidget(self.btn_delete)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        close_box.accepted.connect(self.reject)
        layout.addWidget(close_box)

        self.search_edit.textChanged.connect(self._on_filter_changed)
        self.btn_generate_pdf.clicked.connect(self._generate_from_pdf)
        self.btn_wizard.clicked.connect(self._launch_wizard)
        self.btn_add.clicked.connect(self._add_option)
        self.btn_edit.clicked.connect(self._edit_option)
        self.btn_delete.clicked.connect(self._delete_option)

        self._reload()
        self._update_buttons()

    def _on_filter_changed(self, _text: str) -> None:
        self._populate_table()

    def _populate_table(self) -> None:
        selected_key: Optional[str] = None
        current = self._selected_option()
        if current:
            selected_key = current.key

        filter_text = self.search_edit.text().strip().lower()
        terms = [term for term in filter_text.split() if term]

        self.table.setRowCount(0)
        self._filtered = []

        for opt in self._options:
            haystack_parts = [
                opt.key,
                opt.source or "",
                opt.description or "",
                " ".join(opt.synonyms),
                " ".join(opt.patterns),
                opt.origin_profile or "",
            ]
            haystack = " ".join(haystack_parts).lower()
            if terms and not all(term in haystack for term in terms):
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(opt.key))
            self.table.setItem(row, 1, QTableWidgetItem(opt.source or ""))
            self.table.setItem(row, 2, QTableWidgetItem(opt.description or ""))
            if opt.is_defined_in_active:
                origin_text = self._active or opt.origin_profile or ""
            else:
                origin_source = opt.origin_profile or "Unknown"
                origin_text = f"{origin_source} (inherited)"
            self.table.setItem(row, 3, QTableWidgetItem(origin_text))
            self.table.item(row, 0).setData(Qt.UserRole, opt)
            self._filtered.append(opt)

        if self.table.rowCount() == 0:
            self.table.clearSelection()
            self._on_selection_changed()
            return

        target_row = 0
        if selected_key:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.text() == selected_key:
                    target_row = row
                    break
        if self.table.currentRow() != target_row:
            self.table.selectRow(target_row)
        else:
            self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        self._update_buttons()
        self._refresh_details()

    def _refresh_details(self) -> None:
        option = self._selected_option()
        if option is None:
            self.details_key.setText("—")
            self.details_source.setText("—")
            self.details_origin.setText("—")
            self.details_description.setText("—")
            self.details_synonyms.setText("—")
            self.details_patterns.setText("—")
            return
        self.details_key.setText(option.key or "—")
        self.details_source.setText(option.source or "—")
        if option.is_defined_in_active:
            origin_text = self._active or option.origin_profile or "Active profile"
        else:
            origin_source = option.origin_profile or "Unknown"
            origin_text = f"{origin_source} (inherited)"
        self.details_origin.setText(origin_text)
        self.details_description.setText(option.description or "—")
        self.details_synonyms.setText("\n".join(option.synonyms) if option.synonyms else "—")
        self.details_patterns.setText("\n".join(option.patterns) if option.patterns else "—")

    def _namespaces(self) -> List[str]:
        namespaces = set()
        for opt in self._options:
            if opt.key and "." in opt.key:
                namespaces.add(opt.key.split(".", 1)[0])
        return sorted(namespaces)

    def _guess_default_namespace(self) -> str:
        option = self._selected_option()
        if option and option.key and "." in option.key:
            return option.key.split(".", 1)[0]
        namespaces = self._namespaces()
        if namespaces:
            return namespaces[0]
        return "incident"

    def _reload(self) -> None:
        try:
            result = load_binding_library()
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Unable to load bindings:\n{exc}")
            self._options = []
            self._filtered = []
            self._active = None
            self.table.setRowCount(0)
            self._refresh_details()
            return
        self._options = list(result.options)
        self._active = result.active_profile_id
        self._populate_table()

    def _selected_option(self) -> Optional[BindingOption]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        opt = item.data(Qt.UserRole)
        return opt if isinstance(opt, BindingOption) else None

    def _add_option(self) -> None:
        active = getattr(self, "_active", None)
        dialog = BindingEditorDialog(self, option=None, namespaces=self._namespaces(), active_profile=active)
        if dialog.exec() != QDialog.Accepted:
            return
        option = dialog.result_option()
        try:
            save_binding_option(option)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Failed to save binding:\n{exc}")
            return
        self._reload()

    def _edit_option(self) -> None:
        option = self._selected_option()
        if option is None:
            return
        active = getattr(self, "_active", None)
        dialog = BindingEditorDialog(self, option=option, namespaces=self._namespaces(), active_profile=active)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            save_binding_option(dialog.result_option(), original_key=option.key)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Failed to update binding:\n{exc}")
            return
        self._reload()

    def _delete_option(self) -> None:
        option = self._selected_option()
        if option is None:
            return
        if QMessageBox.question(
            self,
            "Binding Library",
            f"Remove binding '{option.key}'?",
        ) != QMessageBox.Yes:
            return
        try:
            delete_binding_option(option.key)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Failed to delete binding:\n{exc}")
            return
        self._reload()

    def _generate_from_pdf(self) -> None:
        target_profile = self._active or profile_manager.get_active_profile_id()
        if not target_profile:
            QMessageBox.warning(
                self,
                "Generate from PDF",
                "Select an active profile before generating bindings.",
            )
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Fillable PDF",
            "",
            "PDF Files (*.pdf)",
        )
        if not filename:
            return

        pdf_path = Path(filename)
        if pdf_path.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Generate from PDF", "Please choose a PDF file.")
            return

        try:
            fields = extract_acroform_fields(pdf_path)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(
                self,
                "Generate from PDF",
                f"Unable to read the PDF fields:\n{exc}",
            )
            return

        if not fields:
            QMessageBox.information(
                self,
                "Generate from PDF",
                "No fillable fields were found in the selected PDF.",
            )
            return

        namespace_guess = self._guess_default_namespace()
        namespace_text, ok = QInputDialog.getText(
            self,
            "Default Namespace",
            "Namespace for generated bindings:",
            text=namespace_guess,
        )
        if not ok:
            return
        namespace = namespace_text.strip()

        default_source = namespace or "constants"
        source_choices = list(dict.fromkeys([default_source, *_DEFAULT_SOURCES]))
        try:
            default_index = source_choices.index(default_source)
        except ValueError:
            default_index = 0
        source_text, ok = QInputDialog.getItem(
            self,
            "Default Source",
            "Source for generated bindings:",
            source_choices,
            default_index,
            True,
        )
        if not ok:
            return
        source = source_text.strip() or default_source

        existing_keys = {opt.key for opt in self._options}
        seen_keys: Set[str] = set(existing_keys)
        generated: List[Tuple[BindingOption, str, str]] = []
        skipped: List[str] = []

        for field in fields:
            raw_name = getattr(field, "name", "")
            result = _auto_binding_option_from_field(
                raw_name,
                namespace=namespace,
                source=source,
                seen_keys=seen_keys,
                origin_profile=target_profile,
                pdf_name=pdf_path.name,
            )
            if not result:
                if raw_name:
                    skipped.append(raw_name)
                continue
            option, label = result
            generated.append((option, raw_name or option.key, label))

        if not generated:
            message = "No new bindings could be generated."
            if skipped:
                skipped_preview = ", ".join(skipped[:5])
                if len(skipped) > 5:
                    skipped_preview += "…"
                message += f" Skipped fields: {skipped_preview}."
            QMessageBox.information(self, "Generate from PDF", message)
            return

        preview_lines = [
            f"• {opt.key} ← {label}" for opt, _field, label in generated[:8]
        ]
        confirm_message = (
            f"Generate {len(generated)} bindings from {pdf_path.name}?\n\n"
            f"Namespace: {namespace or '(none)'}\n"
            f"Source: {source or default_source}"
        )
        if preview_lines:
            confirm_message += "\n\nExamples:\n" + "\n".join(preview_lines)
        if skipped:
            skipped_preview = ", ".join(skipped[:5])
            if len(skipped) > 5:
                skipped_preview += "…"
            confirm_message += f"\n\nSkipped fields: {skipped_preview}"

        if (
            QMessageBox.question(
                self,
                "Generate from PDF",
                confirm_message,
                QMessageBox.Yes | QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return

        errors: List[str] = []
        saved = 0
        for option, field_name, _label in generated:
            try:
                save_binding_option(option, profile_id=target_profile)
            except Exception as exc:  # pragma: no cover - dialog feedback
                errors.append(f"{field_name}: {exc}")
            else:
                saved += 1

        if errors:
            error_preview = "\n".join(errors[:5])
            if len(errors) > 5:
                error_preview += "\n…"
            QMessageBox.warning(
                self,
                "Generate from PDF",
                f"Saved {saved} bindings, but {len(errors)} failed:\n{error_preview}",
            )
        else:
            QMessageBox.information(
                self,
                "Generate from PDF",
                f"Saved {saved} bindings from {pdf_path.name}.",
            )

        self._reload()

    def _launch_wizard(self) -> None:
        active = getattr(self, "_active", None)
        wizard = BindingWizard(self, namespaces=self._namespaces(), active_profile=active)
        if wizard.exec() != QDialog.Accepted:
            return
        option = wizard.result_option()
        if option is None:
            return
        try:
            save_binding_option(option)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Failed to save binding:\n{exc}")
            return
        self._reload()

    def _update_buttons(self) -> None:
        has_selection = self.table.currentRow() >= 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)
        active_profile = self._active or profile_manager.get_active_profile_id()
        self.btn_generate_pdf.setEnabled(bool(active_profile))


class FormLibraryManager(QWidget):
    """Unified panel for managing form templates, versions, and bindings."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Form Library Manager")

        self.catalog = FormCatalog()
        self.form_service = FormService()
        self._forms_cache: Dict[str, FormEntry] = {}
        self._open_editors: List[MainWindow] = []

        layout = QHBoxLayout(self)

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Form ID", "Title", "Version", "Profiles"])
        self.tree.itemSelectionChanged.connect(self._update_details)
        layout.addWidget(self.tree, 2)

        sidebar = QVBoxLayout()
        layout.addLayout(sidebar, 1)

        form_group = QGroupBox("Form Details", self)
        form_layout = QFormLayout(form_group)
        self.form_id_label = QLabel("—")
        form_layout.addRow("Form ID", self.form_id_label)
        self.form_title_edit = QLineEdit()
        self.form_title_edit.setPlaceholderText("Title shown in menus")
        form_layout.addRow("Title", self.form_title_edit)
        self.form_save_button = QPushButton("Save Form Details")
        self.form_save_button.clicked.connect(self._save_form_details)
        form_layout.addRow(self.form_save_button)
        sidebar.addWidget(form_group)

        version_group = QGroupBox("Selected Version", self)
        version_layout = QFormLayout(version_group)
        self.version_label = QLabel("—")
        version_layout.addRow("Version", self.version_label)
        self.version_profiles_label = QLabel("—")
        version_layout.addRow("Profiles", self.version_profiles_label)
        self.version_pdf_label = QLabel("—")
        self.version_pdf_label.setWordWrap(True)
        version_layout.addRow("PDF", self.version_pdf_label)
        self.version_mapping_label = QLabel("—")
        self.version_mapping_label.setWordWrap(True)
        version_layout.addRow("Mapping", self.version_mapping_label)
        sidebar.addWidget(version_group)

        actions_group = QGroupBox("Actions", self)
        actions_layout = QVBoxLayout(actions_group)
        self.btn_new_form = QPushButton("New Form")
        self.btn_new_form.clicked.connect(self._handle_new_form)
        actions_layout.addWidget(self.btn_new_form)

        self.btn_add_version = QPushButton("Add Version…")
        self.btn_add_version.clicked.connect(self._handle_add_version)
        actions_layout.addWidget(self.btn_add_version)

        self.btn_assign_profiles = QPushButton("Profiles…")
        self.btn_assign_profiles.clicked.connect(self._handle_assign_profiles)
        actions_layout.addWidget(self.btn_assign_profiles)

        self.btn_edit_template = QPushButton("Edit Template…")
        self.btn_edit_template.clicked.connect(self._handle_edit_template)
        actions_layout.addWidget(self.btn_edit_template)

        self.btn_binding_library = QPushButton("Edit Binding Library…")
        self.btn_binding_library.clicked.connect(self._handle_binding_library)
        actions_layout.addWidget(self.btn_binding_library)

        self.btn_import_fema = QPushButton("Import FEMA/ICS forms…")
        self.btn_import_fema.clicked.connect(self._handle_import_forms)
        actions_layout.addWidget(self.btn_import_fema)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_tree)
        actions_layout.addWidget(self.btn_refresh)

        sidebar.addWidget(actions_group)
        sidebar.addStretch(1)

        self._refresh_tree()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _profile_meta_map(self) -> Dict[str, ProfileMeta]:
        return {meta.id: meta for meta in profile_manager.list_profiles()}

    def _is_custom_form(self, form: FormEntry) -> bool:
        category = (form.category or "").strip().lower()
        return category == "custom"

    def _ensure_entry_paths(self, form_id: str, entry: TemplateEntry) -> TemplateEntry:
        pdf_rel = Path(entry.pdf) if entry.pdf else _default_pdf_relative_path(form_id, entry.version)
        mapping_rel = (
            Path(entry.mapping)
            if entry.mapping
            else _default_mapping_relative_path(form_id, entry.version)
        )
        return TemplateEntry(
            version=entry.version,
            pdf=_to_posix(pdf_rel),
            mapping=_to_posix(mapping_rel),
            schema=entry.schema,
            profiles=list(entry.profiles or []),
        )

    def _cleanup_closed_editors(self, *_args) -> None:
        alive: List[MainWindow] = []
        for window in self._open_editors:
            try:
                window.windowTitle()
            except RuntimeError:
                continue
            alive.append(window)
        self._open_editors = alive

    def _refresh_tree(self) -> None:
        self._cleanup_closed_editors()
        self.catalog.load()
        forms = self.catalog.list_forms()
        self._forms_cache = {f.id: f for f in forms}
        self.tree.blockSignals(True)
        self.tree.clear()
        for form in sorted(forms, key=lambda f: f.id):
            form_item = QTreeWidgetItem(self.tree, [form.id, form.title or form.id, "", ", ".join(form.profiles or [])])
            form_item.setData(0, Qt.UserRole, ("form", form.id))
            for tpl in sorted(form.templates, key=lambda t: t.version):
                tpl_norm = self._ensure_entry_paths(form.id, tpl)
                profiles = ", ".join(tpl_norm.profiles) if tpl_norm.profiles else "—"
                version_item = QTreeWidgetItem(form_item, ["", "", tpl_norm.version, profiles])
                version_item.setData(0, Qt.UserRole, ("version", form.id, tpl_norm.version))
                version_item.setData(0, Qt.UserRole + 1, tpl_norm)
                tooltip = f"PDF: {tpl_norm.pdf or '—'}\nMapping: {tpl_norm.mapping or '—'}"
                version_item.setToolTip(0, tooltip)
                version_item.setToolTip(2, tooltip)
            form_item.setExpanded(True)
        self.tree.blockSignals(False)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(2)
        self._update_details()

    def _current_form_context(self) -> Optional[Tuple[str, FormEntry]]:
        item = self.tree.currentItem()
        if not item:
            return None
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, tuple):
            return None
        if data[0] == "form":
            form_id = data[1]
        elif data[0] == "version":
            form_id = data[1]
        else:
            return None
        form = self._forms_cache.get(form_id)
        if not form:
            return None
        return form_id, form

    def _current_version_context(self) -> Optional[Tuple[FormEntry, TemplateEntry]]:
        item = self.tree.currentItem()
        if not item:
            return None
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, tuple) or data[0] != "version":
            return None
        form_id, version = data[1], data[2]
        form = self._forms_cache.get(form_id)
        if not form:
            return None
        for tpl in form.templates:
            if tpl.version == version:
                return form, self._ensure_entry_paths(form.id, tpl)
        return None

    def _select_form(self, form_id: str) -> None:
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item and item.text(0) == form_id:
                self.tree.setCurrentItem(item)
                break

    def _select_version(self, form_id: str, version: str) -> None:
        for row in range(self.tree.topLevelItemCount()):
            form_item = self.tree.topLevelItem(row)
            if form_item and form_item.text(0) == form_id:
                for child_idx in range(form_item.childCount()):
                    child = form_item.child(child_idx)
                    data = child.data(0, Qt.UserRole)
                    if isinstance(data, tuple) and data[0] == "version" and data[2] == version:
                        self.tree.setCurrentItem(child)
                        return
                break

    # Exposed for callers that need to direct the manager toward a form.
    def focus_form(self, form_id: str, version: Optional[str] = None) -> None:
        self._select_form(form_id)
        if version:
            self._select_version(form_id, version)

    def _bind_form_details(self, form: Optional[FormEntry]) -> None:
        if form is None:
            self.form_id_label.setText("—")
            self.form_title_edit.blockSignals(True)
            self.form_title_edit.clear()
            self.form_title_edit.blockSignals(False)
            self.form_title_edit.setEnabled(False)
            self.form_save_button.setEnabled(False)
            return
        self.form_id_label.setText(form.id)
        self.form_title_edit.blockSignals(True)
        self.form_title_edit.setText(form.title or form.id)
        self.form_title_edit.blockSignals(False)
        self.form_title_edit.setEnabled(True)
        self.form_save_button.setEnabled(True)

    def _bind_version_details(self, tpl: Optional[TemplateEntry]) -> None:
        if tpl is None:
            self.version_label.setText("—")
            self.version_profiles_label.setText("—")
            self.version_pdf_label.setText("—")
            self.version_mapping_label.setText("—")
            return
        self.version_label.setText(tpl.version)
        self.version_profiles_label.setText(", ".join(tpl.profiles) if tpl.profiles else "—")
        self.version_pdf_label.setText(tpl.pdf or "—")
        self.version_mapping_label.setText(tpl.mapping or "—")

    def _update_button_states(self) -> None:
        item = self.tree.currentItem()
        data = item.data(0, Qt.UserRole) if item else None
        is_form = isinstance(data, tuple) and data[0] == "form"
        is_version = isinstance(data, tuple) and data[0] == "version"
        self.btn_add_version.setEnabled(is_form or is_version)
        self.btn_assign_profiles.setEnabled(is_version)
        self.btn_edit_template.setEnabled(is_version)
        self.form_title_edit.setEnabled(is_form)
        self.form_save_button.setEnabled(is_form)

    def _update_details(self) -> None:
        context = self._current_form_context()
        form = context[1] if context else None
        version_context = self._current_version_context()
        tpl = version_context[1] if version_context else None
        self._bind_form_details(form)
        self._bind_version_details(tpl)
        self._update_button_states()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _save_form_details(self) -> None:
        ctx = self._current_form_context()
        if not ctx:
            return
        form_id, form = ctx
        new_title = self.form_title_edit.text().strip() or form_id
        form.title = new_title
        self.catalog.upsert_form(form, custom=self._is_custom_form(form))
        QMessageBox.information(self, "Form Library", "Form details updated.")
        self._refresh_tree()
        self._select_form(form_id)

    def _handle_new_form(self) -> None:
        dialog = NewFormDialog(self._forms_cache.keys(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.result()
        if not result:
            return
        form_id, title = result
        entry = FormEntry(id=form_id, title=title, category="Custom", profiles=[], templates=[])
        self.catalog.upsert_form(entry, custom=True)
        self._refresh_tree()
        self._select_form(form_id)

    def _handle_add_version(self) -> None:
        ctx = self._current_form_context()
        if not ctx:
            QMessageBox.warning(self, "Add Version", "Select a form first.")
            return
        form_id, form = ctx
        profiles = [meta.id for meta in profile_manager.list_profiles()]
        if not profiles:
            QMessageBox.warning(self, "Add Version", "No incident profiles are available. Create a profile first.")
            return
        dialog = AddVersionDialog(form_id, [tpl.version for tpl in form.templates], profiles, self)
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.result()
        if not result:
            return
        version, profile_id, pdf_path = result
        try:
            import_result, import_error = self._create_template_version(
                form, version, profile_id, pdf_path
            )
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Add Version", f"Failed to add version:\n{exc}")
            return
        self._refresh_tree()
        self._select_version(form_id, version)
        self._show_import_feedback(pdf_path, import_result, import_error)

    def _create_template_version(
        self,
        form: FormEntry,
        version: str,
        profile_id: str,
        source_pdf: Path,
    ) -> Tuple[Optional[TemplateImportResult], Optional[str]]:
        meta_map = self._profile_meta_map()
        profile = meta_map.get(profile_id)
        if profile is None:
            raise RuntimeError(f"Profile '{profile_id}' not found")
        rel_pdf = _default_pdf_relative_path(form.id, version)
        rel_mapping = _default_mapping_relative_path(form.id, version)
        dest_pdf = profile.path / rel_pdf
        dest_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_pdf, dest_pdf)
        mapping_path = profile.path / rel_mapping
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        import_result: Optional[TemplateImportResult] = None
        import_error: Optional[str] = None
        mapping_payload: Dict[str, Any] = {
            "form_id": form.id,
            "version": version,
            "profile_id": profile_id,
            "incident_class": None,
            "bindings": {},
        }
        try:
            template_title = f"{form.title or form.id} v{version}"
            import_result = import_pdf_template(
                self.form_service,
                dest_pdf,
                name=template_title,
                category=form.category or None,
                subcategory=None,
            )
        except TemplateImportError as exc:
            import_error = str(exc)
        except Exception as exc:  # pragma: no cover - defensive feedback
            import_error = str(exc)
        else:
            mapping_payload["template"] = import_result.template

        mapping_path.write_text(
            json.dumps(mapping_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tpl = TemplateEntry(
            version=version,
            pdf=_to_posix(rel_pdf),
            mapping=_to_posix(rel_mapping),
            profiles=[profile_id],
        )
        self.catalog.add_template(form.id, tpl, custom=self._is_custom_form(form))
        profiles_union = sorted(set(form.profiles or []) | {profile_id})
        form.profiles = profiles_union
        self.catalog.upsert_form(form, custom=self._is_custom_form(form))
        return import_result, import_error

    def _show_import_feedback(
        self,
        source_pdf: Path,
        result: Optional[TemplateImportResult],
        error: Optional[str],
    ) -> None:
        if error:
            QMessageBox.warning(
                self,
                "Add Version",
                (
                    f"Copied {source_pdf.name}, but automatic template preparation failed:\n"
                    f"{error}\n\nOpen the template in the Form Creator to build it manually."
                ),
            )
            return
        if result is None:
            return
        if result.field_count:
            plural = "s" if result.field_count != 1 else ""
            message = (
                f"Prepared {result.field_count} field{plural} from {source_pdf.name} "
                "and saved them to the template."
            )
        else:
            message = (
                f"Prepared a template from {source_pdf.name}, but no fillable fields were detected."
            )
        if result.warnings:
            message += "\n\n" + "\n".join(result.warnings)
        QMessageBox.information(self, "Add Version", message)

    def _handle_assign_profiles(self) -> None:
        ctx = self._current_version_context()
        if ctx is None:
            QMessageBox.warning(self, "Profiles", "Select a specific version first.")
            return
        form, tpl = ctx
        profiles = [meta.id for meta in profile_manager.list_profiles()]
        if not profiles:
            QMessageBox.warning(self, "Profiles", "No incident profiles are available.")
            return
        dlg = ProfileSelectionDialog(form.id, tpl.version, profiles, tpl.profiles, self)
        if dlg.exec() != QDialog.Accepted:
            return
        selected = dlg.selected_profiles()
        tpl.profiles = sorted({p for p in selected if p})
        if tpl.profiles:
            self._ensure_files_for_profiles(form.id, tpl, tpl.profiles[0], tpl.profiles)
        self.catalog.add_template(form.id, tpl, custom=self._is_custom_form(form))
        form.profiles = sorted(set(form.profiles or []) | set(tpl.profiles))
        self.catalog.upsert_form(form, custom=self._is_custom_form(form))
        self._refresh_tree()
        self._select_version(form.id, tpl.version)

    def _ensure_files_for_profiles(
        self,
        form_id: str,
        tpl: TemplateEntry,
        source_profile_id: str,
        targets: Iterable[str],
    ) -> None:
        meta_map = self._profile_meta_map()
        rel_pdf = Path(tpl.pdf) if tpl.pdf else _default_pdf_relative_path(form_id, tpl.version)
        rel_mapping = (
            Path(tpl.mapping)
            if tpl.mapping
            else _default_mapping_relative_path(form_id, tpl.version)
        )
        source_meta = meta_map.get(source_profile_id)
        if source_meta is None:
            return
        source_pdf = source_meta.path / rel_pdf
        source_mapping = source_meta.path / rel_mapping
        for profile_id in targets:
            meta = meta_map.get(profile_id)
            if meta is None:
                continue
            if source_pdf.exists():
                dest_pdf = meta.path / rel_pdf
                dest_pdf.parent.mkdir(parents=True, exist_ok=True)
                if not dest_pdf.exists():
                    try:
                        shutil.copy2(source_pdf, dest_pdf)
                    except Exception:
                        pass
            if source_mapping.exists():
                dest_map = meta.path / rel_mapping
                dest_map.parent.mkdir(parents=True, exist_ok=True)
                if profile_id == source_profile_id:
                    continue
                try:
                    shutil.copy2(source_mapping, dest_map)
                except Exception:
                    pass

    def _handle_edit_template(self) -> None:
        ctx = self._current_version_context()
        if ctx is None:
            QMessageBox.warning(self, "Edit Template", "Select a form version to edit.")
            return
        form, tpl = ctx
        profiles = tpl.profiles or []
        if not profiles:
            active = profile_manager.get_active_profile_id()
            if active:
                profiles = [active]
            else:
                QMessageBox.warning(
                    self,
                    "Edit Template",
                    "Assign the version to at least one profile before editing.",
                )
                return
        profile_id = profiles[0]
        if len(profiles) > 1:
            profile_id, ok = QInputDialog.getItem(
                self,
                "Choose Profile",
                "Edit template for profile:",
                profiles,
                0,
                False,
            )
            if not ok or not profile_id:
                return
        meta_map = self._profile_meta_map()
        profile_meta = meta_map.get(profile_id)
        if profile_meta is None:
            QMessageBox.warning(self, "Edit Template", f"Profile '{profile_id}' is unavailable.")
            return
        self._ensure_files_for_profiles(form.id, tpl, profile_id, [profile_id])
        context = ProfileTemplateContext(
            form_id=form.id,
            version=tpl.version,
            profile_id=profile_id,
            profile_path=profile_meta.path,
            pdf_rel=Path(tpl.pdf) if tpl.pdf else _default_pdf_relative_path(form.id, tpl.version),
            mapping_rel=Path(tpl.mapping)
            if tpl.mapping
            else _default_mapping_relative_path(form.id, tpl.version),
            assigned_profiles=list(tpl.profiles or []),
            custom=self._is_custom_form(form),
        )
        window = MainWindow(parent=self.window())
        window.apply_profile_context(context)
        window.templateSaved.connect(self._on_template_saved)
        window.destroyed.connect(self._cleanup_closed_editors)
        self._open_editors.append(window)
        window.show()

    def _on_template_saved(self, payload: Optional[dict]) -> None:
        self._refresh_tree()
        if not payload:
            return
        form_id = payload.get("form_id")
        version = payload.get("version")
        if form_id and version:
            self._select_version(str(form_id), str(version))

    def _handle_binding_library(self) -> None:
        dlg = BindingLibraryEditorDialog(self)
        dlg.exec()

    def _handle_import_forms(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Import FEMA/ICS forms",
            "Fetch the latest FEMA/ICS form PDFs now?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            results = fetch_latest(FORM_IDS)
        except Exception as exc:  # pragma: no cover - network path
            QMessageBox.critical(self, "Import FEMA/ICS forms", f"Import failed:\n{exc}")
            return
        if results:
            lines = [f"{fid} v{ver}" for fid, ver, _ in results]
            QMessageBox.information(
                self,
                "Import Complete",
                "Imported forms:\n" + "\n".join(lines),
            )
        else:
            QMessageBox.information(
                self,
                "Import Complete",
                "No new forms were imported. The catalog is already up to date.",
            )
        self._refresh_tree()


__all__ = ["FormLibraryManager"]
