"""Developer-only Certification Catalog Editor (Qt Widgets).

Allows developers to view and edit the hardcoded certification catalog in
memory and regenerate the `modules/personnel/models/cert_catalog.py` file.
In production builds this panel should not be exposed by menus.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Any, List
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QLineEdit, QLabel,
    QToolBar, QFormLayout, QSpinBox, QLineEdit as QLE, QComboBox, QPushButton,
    QMessageBox
)

from modules.personnel.models import cert_catalog
from modules.personnel.models.cert_catalog import CertType
from modules.personnel.services import cert_seeder
from utils.app_settings import DEV_MODE


CATEGORY_BUCKETS = {
    "ICS/NIMS": 1000,
    "Medical": 2000,
    "SAR": 3000,
    "Radio": 4000,
    "Safety": 5000,
}


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
        tb.addAction(act_new)
        tb.addAction(act_dup)
        tb.addAction(act_save)
        tb.addAction(act_delete)
        tb.addSeparator()
        act_gen = QAction("Generate Code", self)
        tb.addAction(act_gen)
        act_sync = QAction("Sync to DB", self)
        tb.addAction(act_sync)
        v.addWidget(tb)

        body = QHBoxLayout()
        # Left: category tree + search
        left = QVBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search...")
        self.txt_search.textChanged.connect(self._rebuild_tree)
        left.addWidget(self.txt_search)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Certification Catalog"])
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        left.addWidget(self.tree)
        body.addLayout(left, 2)

        # Right: details form
        right = QVBoxLayout()
        form = QFormLayout()
        self.spn_id = QSpinBox()
        self.spn_id.setRange(1, 999999)
        self.le_code = QLE()
        self.le_name = QLE()
        self.cmb_cat = QComboBox()
        for cat in CATEGORY_BUCKETS.keys():
            self.cmb_cat.addItem(cat)
        self.le_org = QLE()
        self.spn_parent = QSpinBox()
        self.spn_parent.setRange(0, 999999)
        self.le_tags = QLE()
        self.le_tags.setPlaceholderText("Comma-separated tags, e.g. LSAR_TL, OPERATIONS")
        form.addRow("ID:", self.spn_id)
        form.addRow("Code:", self.le_code)
        form.addRow("Name:", self.le_name)
        form.addRow("Category:", self.cmb_cat)
        form.addRow("Issuing Org:", self.le_org)
        form.addRow("Parent ID:", self.spn_parent)
        form.addRow("Tags:", self.le_tags)
        right.addLayout(form)

        body.addLayout(right, 3)
        v.addLayout(body)

        # Wire toolbar actions
        act_new.triggered.connect(self._on_new)
        act_dup.triggered.connect(self._on_duplicate)
        act_save.triggered.connect(self._on_save)
        act_delete.triggered.connect(self._on_delete)
        act_gen.triggered.connect(self._on_generate)
        act_sync.triggered.connect(self._on_sync)

        self._rebuild_tree()

    # ----- Tree / selection ------------------------------------------------
    def _rebuild_tree(self) -> None:
        self.tree.clear()
        q = (self.txt_search.text() or "").strip().lower()
        cats: dict[str, QTreeWidgetItem] = {}
        for i, item in enumerate(self._items):
            text = f"{item['code']} - {item['name']}"
            if q and (q not in item['code'].lower() and q not in item['name'].lower()):
                continue
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
        self.le_org.setText(str(item["issuing_org"]))
        self.spn_parent.setValue(int(item.get("parent_id") or 0))
        self.le_tags.setText(
            ", ".join([str(t) for t in (item.get("tags") or [])])
        )

    def _collect_from_form(self) -> Dict[str, Any]:
        tags = [t.strip().upper().replace(" ", "_") for t in self.le_tags.text().split(",") if t.strip()]
        parent_id = self.spn_parent.value() or None
        return {
            "id": int(self.spn_id.value()),
            "code": self.le_code.text().strip(),
            "name": self.le_name.text().strip(),
            "category": self.cmb_cat.currentText(),
            "issuing_org": self.le_org.text().strip(),
            "parent_id": int(parent_id) if parent_id else None,
            "tags": tuple(tags),
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
        }
        self._items.append(new_item)
        self._items.sort(key=lambda x: (x["category"], x["code"]))
        self._rebuild_tree()

    def _on_duplicate(self) -> None:
        if self._selected_index is None:
            return
        src = dict(self._items[self._selected_index])
        src["id"] = self._next_id_for_category(src["category"])  # new ID
        src["code"] = f"{src['code']}-COPY"
        self._items.append(src)
        self._items.sort(key=lambda x: (x["category"], x["code"]))
        self._rebuild_tree()

    def _on_save(self) -> None:
        if self._selected_index is None:
            return
        updated = self._collect_from_form()
        # Basic validation
        if not updated["code"] or not updated["name"]:
            QMessageBox.warning(self, "Validation", "Code and Name are required.")
            return
        # Warn if ID changed for an existing entry
        prev_id = int(self._items[self._selected_index]["id"])
        if prev_id != int(updated["id"]):
            QMessageBox.information(
                self,
                "ID Change",
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

    def _on_generate(self) -> None:
        # Render a minimal code template for cert_catalog.py
        lines: List[str] = []
        lines.append('"""Generated certification catalog. Edit via Dev Editor."""')
        lines.append("from __future__ import annotations")
        lines.append("from dataclasses import dataclass")
        lines.append("from typing import Optional, List, Tuple")
        lines.append("")
        lines.append(f"CATALOG_VERSION = \"{cert_catalog.CATALOG_VERSION}\"")
        lines.append("")
        lines.append("@dataclass(frozen=True)")
        lines.append("class CertType:")
        lines.append("    id: int")
        lines.append("    code: str")
        lines.append("    name: str")
        lines.append("    category: str")
        lines.append("    issuing_org: str")
        lines.append("    parent_id: Optional[int] = None")
        lines.append("    tags: Tuple[str, ...] = tuple()")
        lines.append("")
        lines.append("CATALOG: List[CertType] = [")
        # Order by category, then code
        for it in sorted(self._items, key=lambda x: (x["category"], x["code"])):
            pid = it["parent_id"]
            pid_str = f", parent_id={pid}" if pid else ""
            tags = tuple(str(t) for t in (it.get("tags") or ()))
            tags_str = f", tags={tags!r}" if tags else ""
            lines.append(
                f"    CertType({int(it['id'])}, {it['code']!r}, {it['name']!r}, {it['category']!r}, {it['issuing_org']!r}{pid_str}{tags_str}),"
            )
        lines.append("]")
        lines.append("")
        out_path = os.path.join("modules", "personnel", "models", "cert_catalog.py")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            QMessageBox.critical(self, "Generate Code", f"Failed to write file:\n{e}")
            return
        QMessageBox.information(self, "Generate Code", f"Wrote {out_path}")

    def _on_sync(self) -> None:
        changed, msg = cert_seeder.sync()
        QMessageBox.information(self, "Catalog Seeder", msg)


__all__ = ["DevCertCatalogEditor"]

