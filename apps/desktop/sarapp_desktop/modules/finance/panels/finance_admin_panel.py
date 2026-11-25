from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.finance import services
from modules.finance.models.schemas import (
    ActualCostDocumentCreate,
    ActualCostLineCreate,
    ActualCostLineLink,
    BudgetSet,
    CalculatedEstimateCreate,
    CloseReason,
    ManualEstimateCreate,
)
from utils.table_view_styles import apply_statusboard_table_behavior

CLOSE_REASONS = list(CloseReason.__args__)


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _set_table_style(table: QTableWidget) -> None:
    apply_statusboard_table_behavior(table, stretch_last_section=True)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)


class _MetricCard(QFrame):
    def __init__(self, accent: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setProperty("accent", accent)
        self.value_label = QLabel("$0.00")
        self.value_label.setObjectName("MetricValue")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("MetricDetail")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str | None = None) -> None:
        self.value_label.setText(value)
        if detail is not None:
            self.detail_label.setText(detail)


class CloseEstimateDialog(QDialog):
    """Closing an estimate without an actual cost requires a reason."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Close Estimate")
        layout = QFormLayout(self)
        self.reason = QComboBox()
        self.reason.addItems(CLOSE_REASONS[:-1])  # "Actual cost received" is system-set only
        self.detail = QLineEdit()
        layout.addRow("Closed Reason", self.reason)
        layout.addRow("Detail (optional)", self.detail)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_reason(self) -> str:
        return self.reason.currentText()

    def selected_detail(self) -> str | None:
        return self.detail.text() or None


class LinkActualLineDialog(QDialog):
    """Pick an open estimate and how much of this line to apply to it."""

    def __init__(self, incident_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.setWindowTitle("Link to Estimate")
        layout = QFormLayout(self)
        self.estimate_combo = QComboBox()
        self._estimates = [e for e in services.list_estimates(incident_id, include_closed=False)]
        for estimate in self._estimates:
            self.estimate_combo.addItem(
                f"#{estimate.id} — {estimate.description} (remaining {_money(estimate.remaining_amount)})",
                estimate.id,
            )
        self.amount = QDoubleSpinBox()
        self.amount.setMaximum(1_000_000.0)
        self.amount.setDecimals(2)
        layout.addRow("Estimate", self.estimate_combo)
        layout.addRow("Amount to apply", self.amount)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_link(self) -> dict | None:
        if self.estimate_combo.count() == 0:
            return None
        return {"estimate_id": self.estimate_combo.currentData(), "amount": self.amount.value()}


class FinanceAdminPanel(QWidget):
    NAV_ITEMS = [
        ("dashboard", "Dashboard"),
        ("estimates", "Estimates"),
        ("actual_costs", "Actual Costs"),
        ("approvals", "Approvals"),
        ("reports", "Reports"),
    ]

    def __init__(self, incident_id: str, default_tab: str = "dashboard", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self.metric_cards: dict[str, _MetricCard] = {}
        self.page_index = {key: idx for idx, (key, _) in enumerate(self.NAV_ITEMS)}

        self._build_ui()
        self._apply_styles()
        self.refresh_all()
        self._select_page(default_tab)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar, 0)

        self.main_shell = QFrame()
        self.main_shell.setObjectName("MainShell")
        main_layout = QVBoxLayout(self.main_shell)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(16)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Finance/Admin")
        title.setObjectName("HeaderTitle")
        context = QLabel(f"Incident: {self.incident_id}")
        context.setObjectName("HeaderContext")
        title_block.addWidget(title)
        title_block.addWidget(context)
        header.addLayout(title_block)
        header.addStretch(1)

        self.btn_new_estimate = QPushButton("+ New Estimate")
        self.btn_new_estimate.clicked.connect(lambda: self._select_page("estimates"))
        self.btn_new_actual_cost = QPushButton("+ New Actual Cost")
        self.btn_new_actual_cost.setProperty("variant", "success")
        self.btn_new_actual_cost.clicked.connect(lambda: self._select_page("actual_costs"))
        header.addWidget(self.btn_new_estimate)
        header.addWidget(self.btn_new_actual_cost)
        main_layout.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard_page())
        self.pages.addWidget(self._build_estimates_page())
        self.pages.addWidget(self._build_actual_costs_page())
        self.pages.addWidget(self._build_approvals_page())
        self.pages.addWidget(self._build_reports_page())
        main_layout.addWidget(self.pages, 1)

        root.addWidget(self.main_shell, 1)

    def _build_sidebar(self) -> QWidget:
        shell = QFrame()
        shell.setObjectName("Sidebar")
        shell.setFixedWidth(170)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(12)

        brand = QLabel("SARApp")
        brand.setObjectName("BrandTitle")
        layout.addWidget(brand)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        self.nav_list.setSpacing(6)
        for key, label in self.NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.nav_list.addItem(item)
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list, 1)
        return shell

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        card_grid = QGridLayout()
        card_grid.setHorizontalSpacing(12)
        card_grid.setVerticalSpacing(12)
        card_specs = [
            ("total_budget", "#2f6fed", "Total Budget"),
            ("open_estimated_cost", "#8e63e6", "Open Estimated Cost"),
            ("open_committed_cost", "#f39c12", "Open Committed Cost"),
            ("actual_cost", "#27ae60", "Actual Cost"),
            ("projected_incident_cost", "#2463eb", "Projected Incident Cost"),
            ("remaining_budget", "#2ca05a", "Remaining Budget"),
            ("projected_budget_variance", "#ef5a5a", "Projected Variance"),
        ]
        for idx, (key, accent, title) in enumerate(card_specs):
            card = _MetricCard(accent, title)
            self.metric_cards[key] = card
            card_grid.addWidget(card, idx // 4, idx % 4)
        layout.addLayout(card_grid)

        budget_form = self._wrap_section("Set Budget", self._build_budget_form())
        layout.addWidget(budget_form)

        self.dashboard_pending = QTableWidget(0, 4)
        self.dashboard_pending.setHorizontalHeaderLabels(["Type", "Description", "Amount", "Status"])
        _set_table_style(self.dashboard_pending)
        layout.addWidget(self._wrap_section("Pending Approvals / Verification", self.dashboard_pending))
        return page

    def _build_budget_form(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        self.budget_total = QDoubleSpinBox()
        self.budget_total.setMaximum(100_000_000.0)
        self.budget_total.setDecimals(2)
        self.budget_notes = QLineEdit()
        save_button = QPushButton("Save Budget")
        save_button.setProperty("variant", "success")
        save_button.clicked.connect(self._save_budget)
        form.addRow("Total Budget", self.budget_total)
        form.addRow("Notes", self.budget_notes)
        form.addRow("", save_button)
        return box

    def _build_estimates_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        form_box = self._wrap_section("New Estimate", self._build_estimate_form())
        layout.addWidget(form_box)

        buttons = QHBoxLayout()
        commit_btn = QPushButton("Commit Selected")
        close_btn = QPushButton("Close Selected")
        commit_btn.clicked.connect(self._commit_selected_estimate)
        close_btn.clicked.connect(self._close_selected_estimate)
        buttons.addWidget(commit_btn)
        buttons.addWidget(close_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.estimates_table = QTableWidget(0, 9)
        self.estimates_table.setHorizontalHeaderLabels(
            ["ID", "Description", "Category", "Task", "Original", "Satisfied", "Remaining", "Status", "Closed"]
        )
        _set_table_style(self.estimates_table)
        layout.addWidget(self.estimates_table, 1)
        return page

    def _build_estimate_form(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        self.estimate_description = QLineEdit()
        self.estimate_category = QComboBox()
        self.estimate_category.addItems(
            ["personnel", "aircraft", "vehicle", "equipment", "fuel", "lodging", "meals", "rentals", "contracted_services", "other"]
        )
        self.estimate_task_id = QLineEdit()
        self.estimate_quantity = QDoubleSpinBox()
        self.estimate_quantity.setDecimals(2)
        self.estimate_quantity.setValue(1.0)
        self.estimate_quantity.setMaximum(1_000_000.0)
        self.estimate_rate_entry_id = QLineEdit()
        self.estimate_rate_entry_id.setPlaceholderText("Rate Table entry ID (leave blank for manual amount)")
        self.estimate_amount = QDoubleSpinBox()
        self.estimate_amount.setDecimals(2)
        self.estimate_amount.setMaximum(1_000_000.0)
        self.estimate_status = QComboBox()
        self.estimate_status.addItems(["estimated", "committed"])
        self.estimate_notes = QLineEdit()
        form.addRow("Description", self.estimate_description)
        form.addRow("Category", self.estimate_category)
        form.addRow("Linked Task ID", self.estimate_task_id)
        form.addRow("Quantity", self.estimate_quantity)
        form.addRow("Rate Table Entry ID", self.estimate_rate_entry_id)
        form.addRow("Manual Amount (if no rate entry)", self.estimate_amount)
        form.addRow("Status", self.estimate_status)
        form.addRow("Notes", self.estimate_notes)
        save_button = QPushButton("Create Estimate")
        save_button.setProperty("variant", "success")
        save_button.clicked.connect(self._save_estimate)
        form.addRow("", save_button)
        return box

    def _build_actual_costs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        form_box = self._wrap_section("New Actual Cost Document", self._build_actual_cost_doc_form())
        layout.addWidget(form_box)

        self.actual_docs_table = QTableWidget(0, 6)
        self.actual_docs_table.setHorizontalHeaderLabels(["ID", "Vendor", "Date", "Total", "Verification", "Paid"])
        _set_table_style(self.actual_docs_table)
        self.actual_docs_table.itemSelectionChanged.connect(self._load_actual_lines_for_selected_doc)
        layout.addWidget(self._wrap_section("Actual Cost Documents", self.actual_docs_table))

        line_form_box = self._wrap_section("Add Line to Selected Document", self._build_actual_cost_line_form())
        layout.addWidget(line_form_box)

        self.actual_lines_table = QTableWidget(0, 6)
        self.actual_lines_table.setHorizontalHeaderLabels(["ID", "Description", "Category", "Qty", "Subtotal", "Linked Estimates"])
        _set_table_style(self.actual_lines_table)
        layout.addWidget(self._wrap_section("Lines on Selected Document", self.actual_lines_table), 1)

        link_btn = QPushButton("Link Selected Line to Another Estimate")
        link_btn.clicked.connect(self._link_selected_line)
        layout.addWidget(link_btn)
        return page

    def _build_actual_cost_doc_form(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        self.doc_vendor = QLineEdit()
        self.doc_number = QLineEdit()
        self.doc_date = QLineEdit()
        self.doc_date.setPlaceholderText("YYYY-MM-DD")
        self.doc_subtotal = QDoubleSpinBox()
        self.doc_subtotal.setDecimals(2)
        self.doc_subtotal.setMaximum(1_000_000.0)
        self.doc_tax = QDoubleSpinBox()
        self.doc_tax.setDecimals(2)
        self.doc_tax.setMaximum(1_000_000.0)
        self.doc_shipping = QDoubleSpinBox()
        self.doc_shipping.setDecimals(2)
        self.doc_shipping.setMaximum(1_000_000.0)
        form.addRow("Vendor/Payee", self.doc_vendor)
        form.addRow("Document Number", self.doc_number)
        form.addRow("Document Date", self.doc_date)
        form.addRow("Subtotal", self.doc_subtotal)
        form.addRow("Tax", self.doc_tax)
        form.addRow("Shipping/Fees", self.doc_shipping)
        save_button = QPushButton("Create Document")
        save_button.setProperty("variant", "success")
        save_button.clicked.connect(self._save_actual_cost_document)
        form.addRow("", save_button)
        return box

    def _build_actual_cost_line_form(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        self.line_description = QLineEdit()
        self.line_category = QLineEdit()
        self.line_quantity = QDoubleSpinBox()
        self.line_quantity.setDecimals(2)
        self.line_quantity.setValue(1.0)
        self.line_quantity.setMaximum(1_000_000.0)
        self.line_unit_price = QDoubleSpinBox()
        self.line_unit_price.setDecimals(2)
        self.line_unit_price.setMaximum(1_000_000.0)
        self.line_estimate_id = QLineEdit()
        self.line_estimate_id.setPlaceholderText("Estimate ID to satisfy (optional)")
        self.line_link_amount = QDoubleSpinBox()
        self.line_link_amount.setDecimals(2)
        self.line_link_amount.setMaximum(1_000_000.0)
        form.addRow("Description", self.line_description)
        form.addRow("Category", self.line_category)
        form.addRow("Quantity", self.line_quantity)
        form.addRow("Unit Price", self.line_unit_price)
        form.addRow("Link to Estimate ID", self.line_estimate_id)
        form.addRow("Amount to Apply", self.line_link_amount)
        add_button = QPushButton("Add Line")
        add_button.setProperty("variant", "success")
        add_button.clicked.connect(self._add_actual_cost_line)
        form.addRow("", add_button)
        return box

    def _build_approvals_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        self.pending_approvals_table = QTableWidget(0, 4)
        self.pending_approvals_table.setHorizontalHeaderLabels(["Type", "Description", "Amount", "Status"])
        _set_table_style(self.pending_approvals_table)
        layout.addWidget(self._wrap_section("Committed Estimates & Unverified Documents", self.pending_approvals_table))
        return page

    def _build_reports_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)
        self.report_task_id = QLineEdit()
        self.report_task_id.setPlaceholderText("Task ID")
        run_button = QPushButton("Run Task Finance Summary")
        run_button.clicked.connect(self._run_task_report)
        row = QHBoxLayout()
        row.addWidget(self.report_task_id)
        row.addWidget(run_button)
        layout.addLayout(row)
        self.report_output = QTextEdit()
        self.report_output.setReadOnly(True)
        layout.addWidget(self.report_output, 1)
        return page

    def _wrap_section(self, title: str, child: QWidget) -> QWidget:
        frame = QFrame()
        frame.setObjectName("SectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        layout.addWidget(label)
        layout.addWidget(child)
        return frame

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #edf3fb; color: #13253f; font-size: 13px; }
            QFrame#Sidebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10233f, stop:1 #0c1930);
            }
            QLabel#BrandTitle { color: white; font-size: 20px; font-weight: 700; padding: 4px 2px 12px 2px; }
            QListWidget#NavList { background: transparent; border: none; color: #d5e1f5; outline: none; }
            QListWidget#NavList::item { border-radius: 10px; padding: 12px 14px; margin: 2px 0px; }
            QListWidget#NavList::item:selected { background: #1e4f95; color: white; }
            QFrame#MainShell {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f7fbff, stop:1 #eef4fb);
            }
            QLabel#HeaderTitle { font-size: 24px; font-weight: 700; color: #12233d; }
            QLabel#HeaderContext, QLabel#MutedLabel { color: #69809f; }
            QPushButton { background: white; border: 1px solid #d3dfef; border-radius: 10px; padding: 9px 14px; font-weight: 600; }
            QPushButton:hover { border-color: #9cb6d7; }
            QPushButton[variant="success"] { background: #21a365; color: white; border-color: #1d8b57; }
            QFrame#MetricCard { background: white; border: 1px solid #dbe4f0; border-radius: 14px; }
            QLabel#MetricTitle { color: #5f7391; font-weight: 600; }
            QLabel#MetricValue { font-size: 24px; font-weight: 700; color: #10233f; }
            QLabel#MetricDetail { color: #2f6fed; font-size: 12px; }
            QFrame#SectionFrame { background: white; border: 1px solid #dbe4f0; border-radius: 14px; }
            QLabel#SectionTitle { font-size: 15px; font-weight: 700; color: #12233d; }
            QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QTableWidget, QListWidget {
                background: white; border: 1px solid #d5e0ed; border-radius: 10px; padding: 7px 9px;
            }
            QHeaderView::section { background: #f5f8fc; border: none; border-bottom: 1px solid #dbe4f0; padding: 8px; font-weight: 700; color: #5b7191; }
            QTableWidget { gridline-color: #ebf0f6; alternate-background-color: #fafcff; }
            """
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_nav_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            return
        key = current.data(Qt.UserRole)
        self.pages.setCurrentIndex(self.page_index.get(key, 0))

    def _select_page(self, key: str) -> None:
        row = self.page_index.get(key, 0)
        self.nav_list.setCurrentRow(row)
        self.pages.setCurrentIndex(row)

    def _selected_id(self, table: QTableWidget) -> int | None:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        return int(item.text()) if item else None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh_all(self) -> None:
        self._load_dashboard()
        self._load_estimates()
        self._load_actual_cost_documents()
        self._load_pending_approvals()

    def _load_dashboard(self) -> None:
        summary = services.get_budget(self.incident_id)
        self.budget_total.setValue(summary.total_budget)
        self.budget_notes.setText(summary.notes or "")
        self.metric_cards["total_budget"].set_value(_money(summary.total_budget))
        self.metric_cards["open_estimated_cost"].set_value(_money(summary.open_estimated_cost))
        self.metric_cards["open_committed_cost"].set_value(_money(summary.open_committed_cost))
        self.metric_cards["actual_cost"].set_value(_money(summary.actual_cost))
        self.metric_cards["projected_incident_cost"].set_value(_money(summary.projected_incident_cost))
        self.metric_cards["remaining_budget"].set_value(_money(summary.remaining_budget))
        variance_detail = "Over budget" if summary.projected_budget_variance < 0 else "Under budget"
        self.metric_cards["projected_budget_variance"].set_value(_money(summary.projected_budget_variance), variance_detail)

    def _load_estimates(self) -> None:
        rows = services.list_estimates(self.incident_id)
        self.estimates_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                item.id, item.description, item.category, item.task_id or "-",
                _money(item.original_amount), _money(item.satisfied_amount), _money(item.remaining_amount),
                item.status, "Yes" if item.closed else "No",
            ]
            for col, value in enumerate(values):
                self.estimates_table.setItem(row_index, col, QTableWidgetItem(str(value)))

    def _load_actual_cost_documents(self) -> None:
        rows = services.list_actual_cost_documents(self.incident_id)
        self.actual_docs_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [item.id, item.vendor, item.document_date, _money(item.total), item.verification_status, "Yes" if item.paid else "No"]
            for col, value in enumerate(values):
                self.actual_docs_table.setItem(row_index, col, QTableWidgetItem(str(value)))

    def _load_actual_lines_for_selected_doc(self) -> None:
        document_id = self._selected_id(self.actual_docs_table)
        if document_id is None:
            self.actual_lines_table.setRowCount(0)
            return
        rows = services.list_actual_cost_lines(self.incident_id, document_id)
        self.actual_lines_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                item.id, item.description, item.category, f"{item.quantity:g}",
                _money(item.line_subtotal), ", ".join(str(i) for i in item.linked_estimate_ids) or "-",
            ]
            for col, value in enumerate(values):
                self.actual_lines_table.setItem(row_index, col, QTableWidgetItem(str(value)))

    def _load_pending_approvals(self) -> None:
        rows = services.list_pending_approvals(self.incident_id)
        for table in (self.dashboard_pending, self.pending_approvals_table):
            table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                values = [item.record_type.replace("_", " ").title(), item.description, _money(item.amount), item.status]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(str(value))
                    if col == 0:
                        cell.setData(Qt.UserRole, (item.record_type, item.record_id))
                    table.setItem(row_index, col, cell)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _save_budget(self) -> None:
        try:
            services.set_budget(
                self.incident_id,
                BudgetSet(total_budget=self.budget_total.value(), notes=self.budget_notes.text() or None),
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Budget", str(exc))

    def _save_estimate(self) -> None:
        try:
            if not self.estimate_description.text().strip():
                raise ValueError("Description is required.")
            rate_entry_text = self.estimate_rate_entry_id.text().strip()
            if rate_entry_text:
                services.create_calculated_estimate(
                    self.incident_id,
                    CalculatedEstimateCreate(
                        description=self.estimate_description.text(),
                        rate_table_entry_id=int(rate_entry_text),
                        task_id=self.estimate_task_id.text() or None,
                        quantity=self.estimate_quantity.value(),
                        status=self.estimate_status.currentText(),
                        notes=self.estimate_notes.text() or None,
                        created_by="Finance/Admin",
                    ),
                )
            else:
                services.create_manual_estimate(
                    self.incident_id,
                    ManualEstimateCreate(
                        description=self.estimate_description.text(),
                        category=self.estimate_category.currentText(),
                        task_id=self.estimate_task_id.text() or None,
                        quantity=self.estimate_quantity.value(),
                        amount=self.estimate_amount.value(),
                        status=self.estimate_status.currentText(),
                        notes=self.estimate_notes.text() or None,
                        created_by="Finance/Admin",
                    ),
                )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Estimate", str(exc))

    def _commit_selected_estimate(self) -> None:
        estimate_id = self._selected_id(self.estimates_table)
        if estimate_id is None:
            return
        try:
            services.commit_estimate(self.incident_id, estimate_id, "Finance/Admin")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Estimate", str(exc))

    def _close_selected_estimate(self) -> None:
        estimate_id = self._selected_id(self.estimates_table)
        if estimate_id is None:
            return
        dialog = CloseEstimateDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            services.close_estimate(
                self.incident_id, estimate_id, dialog.selected_reason(),
                changed_by="Finance/Admin", detail=dialog.selected_detail(),
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Estimate", str(exc))

    def _save_actual_cost_document(self) -> None:
        try:
            if not self.doc_vendor.text().strip():
                raise ValueError("Vendor/payee is required.")
            if not self.doc_date.text().strip():
                raise ValueError("Document date is required.")
            services.create_actual_cost_document(
                self.incident_id,
                ActualCostDocumentCreate(
                    vendor=self.doc_vendor.text(),
                    document_number=self.doc_number.text() or None,
                    document_date=self.doc_date.text(),
                    subtotal=self.doc_subtotal.value(),
                    tax=self.doc_tax.value(),
                    shipping_fees=self.doc_shipping.value(),
                    entered_by="Finance/Admin",
                ),
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Actual Cost Document", str(exc))

    def _add_actual_cost_line(self) -> None:
        document_id = self._selected_id(self.actual_docs_table)
        if document_id is None:
            QMessageBox.information(self, "Actual Cost Line", "Select a document first.")
            return
        try:
            links = []
            estimate_text = self.line_estimate_id.text().strip()
            if estimate_text:
                links = [ActualCostLineLink(estimate_id=int(estimate_text), amount=self.line_link_amount.value())]
            services.add_actual_cost_line(
                self.incident_id, document_id,
                ActualCostLineCreate(
                    description=self.line_description.text(),
                    category=self.line_category.text() or "other",
                    quantity=self.line_quantity.value(),
                    unit_price=self.line_unit_price.value(),
                    links=links,
                ),
            )
            self.refresh_all()
            self._load_actual_lines_for_selected_doc()
        except Exception as exc:
            QMessageBox.warning(self, "Actual Cost Line", str(exc))

    def _link_selected_line(self) -> None:
        row = self.actual_lines_table.currentRow()
        if row < 0:
            return
        line_id = int(self.actual_lines_table.item(row, 0).text())
        dialog = LinkActualLineDialog(self.incident_id, self)
        if dialog.exec() != QDialog.Accepted:
            return
        link = dialog.selected_link()
        if link is None:
            QMessageBox.information(self, "Link Estimate", "No open estimates to link.")
            return
        try:
            services.link_more_estimates(self.incident_id, line_id, [link])
            self.refresh_all()
            self._load_actual_lines_for_selected_doc()
        except Exception as exc:
            QMessageBox.warning(self, "Link Estimate", str(exc))

    def _run_task_report(self) -> None:
        task_id = self.report_task_id.text().strip()
        if not task_id:
            return
        try:
            summary = services.get_task_finance_summary(self.incident_id, task_id)
            self.report_output.setPlainText(
                f"Task {summary.task_id}\n"
                f"Estimated total: {_money(summary.estimated_total)}\n"
                f"Committed total: {_money(summary.committed_total)}\n"
                f"Remaining open estimate: {_money(summary.remaining_open_estimate)}\n"
                f"Actual total: {_money(summary.actual_total)}\n"
                f"Shared actual total: {_money(summary.shared_actual_total)}\n"
            )
        except Exception as exc:
            QMessageBox.warning(self, "Task Finance Summary", str(exc))
