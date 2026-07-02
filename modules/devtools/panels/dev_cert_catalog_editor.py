"""Developer-only Certification Catalog Editor (Qt Widgets).

Allows developers to view and edit the hardcoded certification catalog and
write changes directly to modules/personnel/models/cert_catalog.py.
In production builds this panel should not be exposed by menus.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Dict, Any, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QLineEdit, QLabel,
    QToolBar, QFormLayout, QSpinBox, QLineEdit as QLE, QComboBox, QPushButton,
    QMessageBox, QCheckBox
)

from modules.personnel.models import cert_catalog
from utils.app_settings import DEV_MODE


CATEGORY_BUCKETS = {
    "ICS/NIMS": 1000,
    "Medical": 2000,
    "SAR": 3000,
    "Aviation": 3100,
    "CAP ES": 6000,
    "Incident Staff": 4000,
    "Radio": 5000,
}

_CATALOG_PATH = os.path.join("modules", "personnel", "models", "cert_catalog.py")


def _write_catalog(items: List[Dict[str, Any]], version: str) -> None:
    """Write the catalog list back to cert_catalog.py."""
    lines: List[str] = []
    lines.append('"""Hardcoded certification catalog (authoritative in production).')
    lines.append("")
    lines.append("This module defines the certification catalog used by the application.")
    lines.append("The code catalog is the single source of truth.")
    lines.append("")
    lines.append("Notes")
    lines.append("- IDs are stable integers and MUST NOT be reused once shipped. Bump")
    lines.append("  CATALOG_VERSION any time entries change.")
    lines.append("- Tags allow grouping certifications into qualification profiles.")
    lines.append('- is_medical is the direct source of truth for the medic checkoff."""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from dataclasses import dataclass")
    lines.append("from typing import List, Optional, Tuple")
    lines.append("")
    lines.append("")
    lines.append(f"CATALOG_VERSION = {version!r}")
    lines.append("")
    lines.append("")
    lines.append("@dataclass(frozen=True)")
    lines.append("class CertType:")
    lines.append('    """Immutable certification type record."""')
    lines.append("")
    lines.append("    id: int")
    lines.append("    code: str")
    lines.append("    name: str")
    lines.append("    category: str")
    lines.append("    issuing_org: str")
    lines.append("    parent_id: Optional[int] = None")
    lines.append("    tags: Tuple[str, ...] = tuple()")
    lines.append("    is_medical: bool = False")
    lines.append("")
    lines.append("")
    lines.append("CATALOG: List[CertType] = [")

    current_cat = None
    for it in sorted(items, key=lambda x: (x["category"], x["code"])):
        cat = it["category"]
        if cat != current_cat:
            lines.append(f"    # --- {cat} ---")
            current_cat = cat
        pid = it.get("parent_id")
        pid_str = f", parent_id={pid}" if pid else ""
        tags = tuple(str(t) for t in (it.get("tags") or ()))
        tags_str = f", tags={tags!r}" if tags else ""
        med_str = ", is_medical=True" if it.get("is_medical") else ""
        lines.append(
            f"    CertType({int(it['id'])}, {it['code']!r}, {it['name']!r}, "
            f"{cat!r}, {it['issuing_org']!r}{pid_str}{tags_str}{med_str}),"
        )

    lines.append("]")
    lines.append("")
    lines.append("")
    lines.append("__all__ = [")
    lines.append('    "CATALOG_VERSION",')
    lines.append('    "CertType",')
    lines.append('    "CATALOG",')
    lines.append("]")
    lines.append("")

    with open(_CATALOG_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


class DevCertCatalogEditor(QWidget):
    """Developer editor for the hardcoded certification catalog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        if not DEV_MODE:
            raise PermissionError("Developer tools are disabled in production build")

        self.setWindowTitle("Certification Catalog Editor (Developer)")
        self._items: List[Dict[str, Any]] = [asdict(ct) for ct in cert_catalog.CATALOG]
        self._items.sort(key=lambda x: (x["category"], x["code"]))
        self._selected_index: int | None = None

        v = QVBoxLayout(self)
        tb = QToolBar()
        act_new = QAction("New", self)
        act_dup = QAction("Duplicate", self)
        act_save = QAction("Save", self)
        act_delete = QAction("Delete", self)
        act_write = QAction("Write to File", self)
        tb.addAction(act_new)
        tb.addAction(act_dup)
        tb.addAction(act_save)
        tb.addAction(act_delete)
        tb.addSeparator()
        tb.addAction(act_write)
        v.addWidget(tb)

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search code, name, category, org, or tags...")
        self.txt_search.textChanged.connect(self._rebuild_tree)
        left.addWidget(self.txt_search)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Certification Catalog"])
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        left.addWidget(self.tree)
        body.addLayout(left, 2)

        right = QVBoxLayout()
        form = QFormLayout()
        self.spn_id = QSpinBox()
        self.spn_id.setRange(1, 999999)
        self.le_code = QLE()
        self.le_name = QLE()
        self.cmb_cat = QComboBox()
        self.le_cat_custom = QLE()
        self.le_cat_custom.setPlaceholderText("Or type a custom category")
        for cat in sorted(set(it["category"] for it in self._items)):
            self.cmb_cat.addItem(cat)
        self.le_org = QLE()
        self.spn_parent = QSpinBox()
        self.spn_parent.setRange(0, 999999)
        self.le_tags = QLE()
        self.le_tags.setPlaceholderText("Comma-separated tags, e.g. LSAR_TL, OPERATIONS")
        self.chk_medical = QCheckBox("Counts as medical for medic checkoff")
        form.addRow("ID:", self.spn_id)
        form.addRow("Code:", self.le_code)
        form.addRow("Name:", self.le_name)
        form.addRow("Category:", self.cmb_cat)
        form.addRow("", self.le_cat_custom)
        form.addRow("Issuing Org:", self.le_org)
        form.addRow("Parent ID:", self.spn_parent)
        form.addRow("Tags:", self.le_tags)
        form.addRow("Medical:", self.chk_medical)
        right.addLayout(form)

        body.addLayout(right, 3)
        v.addLayout(body)

        act_new.triggered.connect(self._on_new)
        act_dup.triggered.connect(self._on_duplicate)
        act_save.triggered.connect(self._on_save)
        act_delete.triggered.connect(self._on_delete)
        act_write.triggered.connect(self._on_write)

        self._rebuild_tree()

    # ----- Tree / selection ------------------------------------------------
    def _rebuild_tree(self) -> None:
        self.tree.clear()
        q = (self.txt_search.text() or "").strip().lower()
        cats: dict[str, QTreeWidgetItem] = {}
        for i, item in enumerate(self._items):
            tags_text = ",".join([str(t) for t in item.get("tags") or []])
            haystack = " ".join([
                str(item.get("code") or ""),
                str(item.get("name") or ""),
                str(item.get("category") or ""),
                str(item.get("issuing_org") or ""),
                tags_text,
                "medical" if item.get("is_medical") else "",
            ]).lower()
            if q and q not in haystack:
                continue
            suffix = " (medical)" if item.get("is_medical") else ""
            text = f"{item['code']} - {item['name']}{suffix}"
            cat = item["category"]
            parent = cats.get(cat)
            if parent is None:
                parent = QTreeWidgetItem([cat])
                parent.setFirstColumnSpanned(True)
                self.tree.addTopLevelItem(parent)
                cats[cat] = parent
            node = QTreeWidgetItem([text])
            node.setData(0, Qt.UserRole, i)
            parent.addChild(node)
        self.tree.expandAll()

    def _on_tree_selection(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            self._selected_index = None
            return
        idx = items[0].data(0, Qt.UserRole)
        if idx is None:
            self._selected_index = None
            return
        self._selected_index = int(idx)
        self._load_to_form(self._items[self._selected_index])

    # ----- CRUD -------------------------------------------------------------
    def _load_to_form(self, item: Dict[str, Any]) -> None:
        self.spn_id.setValue(int(item["id"]))
        self.le_code.setText(str(item["code"]))
        self.le_name.setText(str(item["name"]))
        self.cmb_cat.setCurrentText(str(item["category"]))
        self.le_cat_custom.clear()
        self.le_org.setText(str(item["issuing_org"]))
        self.spn_parent.setValue(int(item.get("parent_id") or 0))
        self.le_tags.setText(", ".join([str(t) for t in (item.get("tags") or [])]))
        self.chk_medical.setChecked(bool(item.get("is_medical")))

    def _collect_from_form(self) -> Dict[str, Any]:
        tags = [t.strip().upper().replace(" ", "_") for t in self.le_tags.text().split(",") if t.strip()]
        parent_id = self.spn_parent.value() or None
        cat = self.le_cat_custom.text().strip() or self.cmb_cat.currentText()
        return {
            "id": int(self.spn_id.value()),
            "code": self.le_code.text().strip(),
            "name": self.le_name.text().strip(),
            "category": cat,
            "issuing_org": self.le_org.text().strip(),
            "parent_id": int(parent_id) if parent_id else None,
            "tags": tuple(tags),
            "is_medical": self.chk_medical.isChecked(),
        }

    def _next_id_for_category(self, category: str) -> int:
        base = CATEGORY_BUCKETS.get(category, 9000)
        used = [int(it["id"]) for it in self._items if it["category"] == category]
        n = base + 1
        while n in used:
            n += 1
        return n

    def _on_new(self) -> None:
        cat = self.cmb_cat.currentText() or "SAR"
        new_item = {
            "id": self._next_id_for_category(cat),
            "code": "NEW-CERT",
            "name": "New Certification",
            "category": cat,
            "issuing_org": "",
            "parent_id": None,
            "tags": tuple(),
            "is_medical": False,
        }
        self._items.append(new_item)
        self._items.sort(key=lambda x: (x["category"], x["code"]))
        self._rebuild_tree()

    def _on_duplicate(self) -> None:
        if self._selected_index is None:
            return
        src = dict(self._items[self._selected_index])
        src["id"] = self._next_id_for_category(src["category"])
        src["code"] = f"{src['code']}-COPY"
        self._items.append(src)
        self._items.sort(key=lambda x: (x["category"], x["code"]))
        self._rebuild_tree()

    def _on_save(self) -> None:
        if self._selected_index is None:
            return
        updated = self._collect_from_form()
        if not updated["code"] or not updated["name"]:
            QMessageBox.warning(self, "Validation", "Code and Name are required.")
            return
        prev_id = int(self._items[self._selected_index]["id"])
        if prev_id != int(updated["id"]):
            QMessageBox.information(
                self, "ID Change",
                "Changing IDs can break references. Proceeding with the new ID.",
            )
        self._items[self._selected_index] = updated
        self._items.sort(key=lambda x: (x["category"], x["code"]))
        self._rebuild_tree()

    def _on_delete(self) -> None:
        if self._selected_index is None:
            return
        item = self._items[self._selected_index]
        if QMessageBox.question(self, "Delete", f"Delete {item['code']} - {item['name']}?") != QMessageBox.Yes:
            return
        self._items.pop(self._selected_index)
        self._selected_index = None
        self._rebuild_tree()

    def _on_write(self) -> None:
        try:
            _write_catalog(self._items, cert_catalog.CATALOG_VERSION)
        except Exception as e:
            QMessageBox.critical(self, "Write to File", f"Failed to write {_CATALOG_PATH}:\n{e}")
            return
        QMessageBox.information(self, "Write to File", f"Saved to {_CATALOG_PATH}")


__all__ = ["DevCertCatalogEditor"]
