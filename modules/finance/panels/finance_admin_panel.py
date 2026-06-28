from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.finance import services
from modules.finance.models.schemas import (
    AttachmentCreate,
    FinanceExpenseCreate,
    FinanceForecastCreate,
    FuelForecastLineCreate,
    FuelPriceProfileCreate,
)
from utils.table_view_styles import apply_statusboard_table_behavior


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
        self.detail_label = QLabel("View details")
        self.detail_label.setObjectName("MetricDetail")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str | None = None) -> None:
        self.value_label.setText(value)
        if detail:
            self.detail_label.setText(detail)


class _SimpleBarChart(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChartCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        outer.addWidget(label)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        outer.addLayout(self.rows_layout)
        outer.addStretch(1)

    def set_rows(self, rows: list[tuple[str, float, float]]) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        max_value = max([max(forecast, actual) for _, forecast, actual in rows], default=1.0) or 1.0
        for label, forecast, actual in rows:
            row = QWidget()
            layout = QVBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            name = QLabel(label)
            nums = QLabel(f"F {_money(forecast)}   A {_money(actual)}")
            nums.setObjectName("MutedLabel")
            top.addWidget(name)
            top.addStretch(1)
            top.addWidget(nums)
            layout.addLayout(top)

            bar_row = QHBoxLayout()
            bar_row.setContentsMargins(0, 0, 0, 0)
            bar_row.setSpacing(6)
            forecast_bar = QFrame()
            forecast_bar.setObjectName("ForecastBar")
            forecast_bar.setFixedHeight(10)
            forecast_bar.setMinimumWidth(max(12, int((forecast / max_value) * 240)))
            actual_bar = QFrame()
            actual_bar.setObjectName("ActualBar")
            actual_bar.setFixedHeight(10)
            actual_bar.setMinimumWidth(max(12, int((actual / max_value) * 240)))
            bar_row.addWidget(forecast_bar)
            bar_row.addWidget(actual_bar)
            bar_row.addStretch(1)
            layout.addLayout(bar_row)
            self.rows_layout.addWidget(row)


class _DonutSummary(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChartCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        outer.addWidget(label)

        content = QHBoxLayout()
        self.total_label = QLabel("$0.00")
        self.total_label.setObjectName("DonutTotal")
        self.breakdown = QVBoxLayout()
        self.breakdown.setSpacing(8)
        content.addWidget(self.total_label, 0, Qt.AlignCenter)
        content.addLayout(self.breakdown, 1)
        outer.addLayout(content)

    def set_values(self, total: float, rows: list[tuple[str, float, str]]) -> None:
        self.total_label.setText(f"{_money(total)}\nTotal Actual")
        while self.breakdown.count():
            item = self.breakdown.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for label, amount, color in rows:
            line = QLabel(f"{label}: {_money(amount)}")
            line.setStyleSheet(f"color: {color}; font-weight: 600;")
            self.breakdown.addWidget(line)
        self.breakdown.addStretch(1)


class ExpenseDetailDialog(QDialog):
    def __init__(self, incident_id: str, expense_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Expense Detail")
        self.setStyleSheet(
            """
            QDialog { background: #f7f9fc; }
            QFrame#DetailShell {
                background: white;
                border: 1px solid #dbe4f0;
                border-radius: 14px;
            }
            QLabel#DetailTitle { font-size: 16px; font-weight: 700; color: #10233f; }
            QLabel#ApprovedBadge {
                background: #dff3e7;
                color: #18794e;
                border-radius: 10px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QLabel#TabChip {
                background: #eef3fb;
                color: #33527a;
                border-radius: 10px;
                padding: 6px 10px;
            }
            QLabel#FieldName { color: #5c6f89; font-weight: 600; }
            QLabel#FieldValue { color: #13253f; }
            """
        )

        expense = services.get_expense(incident_id, expense_id)
        approvals = services.list_approvals(incident_id, "expense", expense_id)
        attachments = services.list_attachments(incident_id, "expense", expense_id)

        root = QVBoxLayout(self)
        shell = QFrame()
        shell.setObjectName("DetailShell")
        root.addWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel(f"Expense: {expense.expense_number}")
        title.setObjectName("DetailTitle")
        badge = QLabel(expense.status)
        badge.setObjectName("ApprovedBadge")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(badge)
        layout.addLayout(header)

        tabs = QHBoxLayout()
        for tab_name in ["Overview", "Line Items", "Approvals", "Attachments", "Links", "Audit Log"]:
            chip = QLabel(tab_name)
            chip.setObjectName("TabChip")
            tabs.addWidget(chip)
        tabs.addStretch(1)
        layout.addLayout(tabs)

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)
        fields = [
            ("Category", expense.category),
            ("Amount Subtotal", _money(expense.amount_subtotal)),
            ("Subcategory", expense.subcategory or "-"),
            ("Tax", _money(expense.amount_tax)),
            ("Description", expense.description),
            ("Total", _money(expense.amount_total)),
            ("Vendor", expense.vendor or "-"),
            ("Payment Method", expense.payment_method or "-"),
            ("Expense Date/Time", str(expense.expense_datetime)),
            ("Entered By", expense.entered_by or "-"),
            ("Operational Period", expense.operational_period_id or "-"),
            ("Entered At", str(expense.entered_at)),
            ("Funding Source", str(expense.funding_source_id or "-")),
            ("Approved By", expense.approved_by or "-"),
            ("Notes", expense.notes or "-"),
            ("Approved At", str(expense.approved_at or "-")),
        ]
        for idx, (name, value) in enumerate(fields):
            name_label = QLabel(name)
            value_label = QLabel(str(value))
            name_label.setObjectName("FieldName")
            value_label.setObjectName("FieldValue")
            grid.addWidget(name_label, idx, 0 if idx % 2 == 0 else 2)
            grid.addWidget(value_label, idx, 1 if idx % 2 == 0 else 3)
        layout.addLayout(grid)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(
            "\n".join(
                [
                    "Approvals:",
                    *[
                        f"- {item.timestamp}: {item.action} by {item.approver_id or item.approver_role or 'Unknown'}"
                        for item in approvals
                    ],
                    "",
                    "Attachments:",
                    *[f"- {item.filename} ({item.attachment_type})" for item in attachments],
                ]
            )
        )
        layout.addWidget(notes)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)


class FinanceAdminPanel(QWidget):
    NAV_ITEMS = [
        ("dashboard", "Dashboard"),
        ("forecasts", "Forecasts"),
        ("expenses", "Expenses"),
        ("fuel_prices", "Fuel Prices"),
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
        context = QLabel(f"Incident: {self.incident_id}   |   Operational Period: 2")
        context.setObjectName("HeaderContext")
        title_block.addWidget(title)
        title_block.addWidget(context)
        header.addLayout(title_block)
        header.addStretch(1)

        self.btn_new_forecast = QPushButton("+ New Forecast")
        self.btn_new_forecast.clicked.connect(lambda: self._select_page("forecasts"))
        self.btn_new_expense = QPushButton("+ New Expense")
        self.btn_new_expense.setProperty("variant", "success")
        self.btn_new_expense.clicked.connect(lambda: self._select_page("expenses"))
        self.btn_fuel_prices = QPushButton("Fuel Prices")
        self.btn_fuel_prices.clicked.connect(lambda: self._select_page("fuel_prices"))
        header.addWidget(self.btn_new_forecast)
        header.addWidget(self.btn_new_expense)
        header.addWidget(self.btn_fuel_prices)
        main_layout.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_dashboard_page())
        self.pages.addWidget(self._build_forecasts_page())
        self.pages.addWidget(self._build_expenses_page())
        self.pages.addWidget(self._build_fuel_prices_page())
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

        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 12, 12, 12)
        status_layout.addWidget(QLabel("Connected"))
        status_layout.addWidget(QLabel("Incident DB"))
        layout.addWidget(status_card)
        return shell

    def _build_dashboard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        card_grid = QGridLayout()
        card_grid.setHorizontalSpacing(12)
        card_grid.setVerticalSpacing(12)
        card_specs = [
            ("total_forecast_cost", "#2f6fed", "Total Forecast"),
            ("total_actual_cost", "#27ae60", "Total Actual"),
            ("variance", "#f39c12", "Variance"),
            ("pending_approvals", "#8e63e6", "Pending Approvals"),
            ("fuel_forecast_cost", "#2463eb", "Fuel Forecast"),
            ("fuel_actual_cost", "#2ca05a", "Fuel Actual"),
            ("missing_receipts", "#ef5a5a", "Missing Receipts"),
            ("funding_sources", "#9c6ade", "Funding Sources"),
        ]
        for idx, (key, accent, title) in enumerate(card_specs):
            card = _MetricCard(accent, title)
            self.metric_cards[key] = card
            card_grid.addWidget(card, idx // 4, idx % 4)
        layout.addLayout(card_grid)

        charts = QHBoxLayout()
        self.category_chart = _SimpleBarChart("Actual vs Forecast by Category")
        self.period_summary = _DonutSummary("Actual by Operational Period")
        charts.addWidget(self.category_chart, 3)
        charts.addWidget(self.period_summary, 2)
        layout.addLayout(charts)

        lower = QHBoxLayout()
        self.dashboard_recent_expenses = QTableWidget(0, 6)
        self.dashboard_recent_expenses.setHorizontalHeaderLabels(
            ["Date/Time", "Category", "Description", "Amount", "Status", "Receipt"]
        )
        _set_table_style(self.dashboard_recent_expenses)
        recent_box = self._wrap_section("Recent Expenses", self.dashboard_recent_expenses)

        self.dashboard_pending = QTableWidget(0, 5)
        self.dashboard_pending.setHorizontalHeaderLabels(["Type", "Description", "Amount", "Submitted", "Status"])
        _set_table_style(self.dashboard_pending)
        pending_box = self._wrap_section("Pending Approvals", self.dashboard_pending)
        lower.addWidget(recent_box, 1)
        lower.addWidget(pending_box, 1)
        layout.addLayout(lower)
        return page

    def _build_forecasts_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        step_row = QHBoxLayout()
        for idx, name in enumerate(["Fuel Prices", "Forecast Type", "Forecast Details", "Review & Save"], start=1):
            step = QLabel(f"{idx}. {name}")
            step.setObjectName("StepChip")
            if idx == 3:
                step.setProperty("active", True)
            step_row.addWidget(step)
        step_row.addStretch(1)
        layout.addLayout(step_row)

        splitter = QSplitter(Qt.Horizontal)
        form_shell = QWidget()
        form_layout = QVBoxLayout(form_shell)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(12)

        forecast_form = QGroupBox("Ground Vehicle Forecast")
        forecast_layout = QFormLayout(forecast_form)
        self.forecast_name = QLineEdit()
        self.forecast_op = QLineEdit("2")
        self.forecast_resource_type = QComboBox()
        self.forecast_resource_type.addItems(["Vehicle", "Aircraft", "Generator", "Equipment", "Other"])
        self.forecast_resource_name = QLineEdit("Truck #12")
        self.forecast_quantity = QLineEdit("2")
        self.forecast_fuel_type = QComboBox()
        self.forecast_fuel_type.addItems(["Gasoline", "Diesel", "Jet-A", "100LL"])
        self.forecast_miles = QLineEdit("125")
        self.forecast_mpg = QLineEdit("15.0")
        self.forecast_hours = QLineEdit()
        self.forecast_gph = QLineEdit()
        self.forecast_price = QLineEdit()
        self.forecast_use_profile = QPushButton("Use Active Fuel Price")
        self.forecast_task = QLineEdit()
        self.forecast_notes = QLineEdit()
        forecast_layout.addRow("Forecast Name", self.forecast_name)
        forecast_layout.addRow("Operational Period", self.forecast_op)
        forecast_layout.addRow("Forecast Type", self.forecast_resource_type)
        forecast_layout.addRow("Vehicle / Resource", self.forecast_resource_name)
        forecast_layout.addRow("Number of Vehicles", self.forecast_quantity)
        forecast_layout.addRow("Fuel Type", self.forecast_fuel_type)
        forecast_layout.addRow("Estimated Miles per Vehicle", self.forecast_miles)
        forecast_layout.addRow("Estimated MPG", self.forecast_mpg)
        forecast_layout.addRow("Estimated Hours", self.forecast_hours)
        forecast_layout.addRow("Gallons per Hour", self.forecast_gph)
        forecast_layout.addRow("Fuel Price", self.forecast_price)
        forecast_layout.addRow("", self.forecast_use_profile)
        forecast_layout.addRow("Linked Tasking", self.forecast_task)
        forecast_layout.addRow("Notes", self.forecast_notes)
        self.forecast_use_profile.clicked.connect(self._apply_active_fuel_price)
        form_layout.addWidget(forecast_form)

        nav_buttons = QHBoxLayout()
        back = QPushButton("Back")
        create = QPushButton("Save Draft")
        create.setProperty("variant", "success")
        submit = QPushButton("Submit Selected Forecast")
        approve = QPushButton("Approve Selected Forecast")
        create.clicked.connect(self._save_forecast)
        submit.clicked.connect(self._submit_selected_forecast)
        approve.clicked.connect(self._approve_selected_forecast)
        nav_buttons.addWidget(back)
        nav_buttons.addStretch(1)
        nav_buttons.addWidget(create)
        nav_buttons.addWidget(submit)
        nav_buttons.addWidget(approve)
        form_layout.addLayout(nav_buttons)

        summary_shell = QFrame()
        summary_shell.setObjectName("SummaryCard")
        summary_layout = QVBoxLayout(summary_shell)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(10)
        summary_title = QLabel("Forecast Summary")
        summary_title.setObjectName("SectionTitle")
        summary_layout.addWidget(summary_title)
        self.forecast_summary = QLabel(
            "Total Vehicles: 0\nTotal Estimated Miles: 0\nEstimated Gallons: 0.00 gal\nEstimated Cost: $0.00"
        )
        self.forecast_summary.setObjectName("SummaryText")
        summary_layout.addWidget(self.forecast_summary)
        summary_layout.addStretch(1)

        splitter.addWidget(form_shell)
        splitter.addWidget(summary_shell)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        self.forecasts_table = QTableWidget(0, 7)
        self.forecasts_table.setHorizontalHeaderLabels(["ID", "Name", "Type", "OP", "Gallons", "Estimated Cost", "Status"])
        _set_table_style(self.forecasts_table)
        layout.addWidget(self._wrap_section("Saved Forecasts", self.forecasts_table))
        return page

    def _build_expenses_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        toolbar = QHBoxLayout()
        new_button = QPushButton("+ New Expense")
        new_button.setProperty("variant", "success")
        filter_button = QPushButton("Filters")
        self.expense_search = QLineEdit()
        self.expense_search.setPlaceholderText("Search expenses...")
        self.expense_search.textChanged.connect(self._load_expenses)
        toolbar.addWidget(new_button)
        toolbar.addWidget(filter_button)
        toolbar.addWidget(self.expense_search, 1)
        toolbar.addWidget(QPushButton("Export"))
        layout.addLayout(toolbar)

        form = QGroupBox("Expense Register Entry")
        form_layout = QFormLayout(form)
        self.expense_category = QComboBox()
        self.expense_category.addItems(
            ["Fuel", "Mileage", "Meals", "Lodging", "Supplies", "Equipment", "Aircraft", "Vehicle", "Other"]
        )
        self.expense_subcategory = QLineEdit()
        self.expense_description = QLineEdit()
        self.expense_vendor = QLineEdit()
        self.expense_datetime = QDateTimeEdit(datetime.now())
        self.expense_datetime.setCalendarPopup(True)
        self.expense_subtotal = QLineEdit("0.00")
        self.expense_tax = QLineEdit("0.00")
        self.expense_tip = QLineEdit("0.00")
        self.expense_payment = QLineEdit("Credit Card")
        self.expense_forecast_link = QLineEdit()
        self.expense_receipt_name = QLineEdit()
        self.expense_notes = QLineEdit()
        form_layout.addRow("Category", self.expense_category)
        form_layout.addRow("Subcategory", self.expense_subcategory)
        form_layout.addRow("Description", self.expense_description)
        form_layout.addRow("Vendor", self.expense_vendor)
        form_layout.addRow("Date/Time", self.expense_datetime)
        form_layout.addRow("Subtotal", self.expense_subtotal)
        form_layout.addRow("Tax", self.expense_tax)
        form_layout.addRow("Tip", self.expense_tip)
        form_layout.addRow("Payment Method", self.expense_payment)
        form_layout.addRow("Linked Forecast ID", self.expense_forecast_link)
        form_layout.addRow("Receipt Filename", self.expense_receipt_name)
        form_layout.addRow("Notes", self.expense_notes)
        layout.addWidget(form)

        buttons = QHBoxLayout()
        create = QPushButton("Save Expense")
        create.setProperty("variant", "success")
        submit = QPushButton("Submit Selected Expense")
        approve = QPushButton("Approve Selected Expense")
        detail = QPushButton("Open Expense Detail")
        create.clicked.connect(self._save_expense)
        submit.clicked.connect(self._submit_selected_expense)
        approve.clicked.connect(self._approve_selected_expense)
        detail.clicked.connect(self._open_selected_expense_detail)
        buttons.addWidget(create)
        buttons.addWidget(submit)
        buttons.addWidget(approve)
        buttons.addWidget(detail)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.expenses_table = QTableWidget(0, 8)
        self.expenses_table.setHorizontalHeaderLabels(
            ["ID", "Date/Time", "Category", "Description", "Amount", "Status", "Receipt", "Entered By"]
        )
        _set_table_style(self.expenses_table)
        layout.addWidget(self.expenses_table)
        return page

    def _build_fuel_prices_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        shell = QFrame()
        shell.setObjectName("SectionFrame")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(18, 18, 18, 18)
        shell_layout.setSpacing(16)

        title = QLabel("Fuel Price Profile")
        title.setObjectName("SectionTitle")
        shell_layout.addWidget(title)

        form_layout = QGridLayout()
        self.price_gasoline = QLineEdit("3.45")
        self.price_diesel = QLineEdit("3.89")
        self.price_jet_a = QLineEdit("5.68")
        self.price_100ll = QLineEdit("6.42")
        self.price_location = QLineEdit("County average - Local stations")
        self.price_source = QLineEdit("Manual estimate")
        self.price_effective = QDateTimeEdit(datetime.now())
        self.price_effective.setCalendarPopup(True)
        self.price_active = QCheckBox("Set active")
        entries = [
            ("Gasoline (Avg)", self.price_gasoline, 0, 0),
            ("Diesel (Avg)", self.price_diesel, 1, 0),
            ("Jet-A (Avg)", self.price_jet_a, 2, 0),
            ("100LL (Avg)", self.price_100ll, 3, 0),
            ("Location / Region Note", self.price_location, 0, 2),
            ("Source Note", self.price_source, 1, 2),
            ("Effective Date/Time", self.price_effective, 2, 2),
        ]
        for label_text, widget, row, col in entries:
            form_layout.addWidget(QLabel(label_text), row, col)
            form_layout.addWidget(widget, row, col + 1)
        form_layout.addWidget(self.price_active, 3, 2, 1, 2)
        shell_layout.addLayout(form_layout)

        button_row = QHBoxLayout()
        button_row.addWidget(QPushButton("Cancel"))
        copy_button = QPushButton("Copy Previous Profile")
        activate_button = QPushButton("Set Active")
        activate_button.setProperty("variant", "success")
        save_button = QPushButton("Save Profile")
        save_button.clicked.connect(self._save_fuel_price_profile)
        copy_button.clicked.connect(self._copy_previous_fuel_price_profile)
        activate_button.clicked.connect(self._set_selected_fuel_price_profile_active)
        button_row.addStretch(1)
        button_row.addWidget(copy_button)
        button_row.addWidget(save_button)
        button_row.addWidget(activate_button)
        shell_layout.addLayout(button_row)

        layout.addWidget(shell)

        self.fuel_prices_table = QTableWidget(0, 7)
        self.fuel_prices_table.setHorizontalHeaderLabels(["ID", "Gasoline", "Diesel", "Jet-A", "100LL", "Effective", "Active"])
        _set_table_style(self.fuel_prices_table)
        layout.addWidget(self._wrap_section("Saved Fuel Profiles", self.fuel_prices_table))
        return page

    def _build_approvals_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        self.pending_approvals_table = QTableWidget(0, 5)
        self.pending_approvals_table.setHorizontalHeaderLabels(["Type", "Description", "Amount", "Submitted", "Status"])
        _set_table_style(self.pending_approvals_table)
        layout.addWidget(self._wrap_section("Pending Approvals", self.pending_approvals_table))

        buttons = QHBoxLayout()
        approve = QPushButton("Approve Selected")
        returned = QPushButton("Return Selected")
        approve.clicked.connect(self._approve_selected_pending_item)
        returned.clicked.connect(self._return_selected_pending_item)
        buttons.addWidget(approve)
        buttons.addWidget(returned)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        return page

    def _build_reports_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(14)

        menu = QFrame()
        menu.setObjectName("SectionFrame")
        menu_layout = QVBoxLayout(menu)
        menu_layout.setContentsMargins(16, 16, 16, 16)
        menu_layout.setSpacing(10)
        menu_layout.addWidget(QLabel("Reports"))
        self.report_menu = QListWidget()
        self.report_menu.addItems(
            [
                "Incident Cost Summary",
                "Fuel Cost Report",
                "Actuals vs Forecast",
                "Expense Detail Report",
                "Funding Source Summary",
                "Unapproved Expenses",
                "Missing Receipt Report",
                "Tasking Cost Report",
                "Vehicle/Aircraft Cost Report",
                "Reimbursement Packet",
            ]
        )
        self.report_menu.setCurrentRow(0)
        self.report_menu.currentRowChanged.connect(self._refresh_report_preview)
        menu_layout.addWidget(self.report_menu)
        export_row = QHBoxLayout()
        export_row.addWidget(QPushButton("PDF"))
        export_row.addWidget(QPushButton("CSV"))
        export_row.addWidget(QPushButton("Excel"))
        menu_layout.addLayout(export_row)

        preview = QFrame()
        preview.setObjectName("SectionFrame")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(12)
        self.report_title = QLabel("Incident Cost Summary")
        self.report_title.setObjectName("SectionTitle")
        preview_layout.addWidget(self.report_title)
        self.report_subtitle = QLabel("")
        self.report_subtitle.setObjectName("MutedLabel")
        preview_layout.addWidget(self.report_subtitle)
        self.fuel_report_table = QTableWidget(0, 5)
        self.fuel_report_table.setHorizontalHeaderLabels(["Forecast", "Forecast Cost", "Actual Cost", "Variance", "Status"])
        _set_table_style(self.fuel_report_table)
        preview_layout.addWidget(self.fuel_report_table)

        layout.addWidget(menu, 1)
        layout.addWidget(preview, 2)
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
            QWidget {
                background: #edf3fb;
                color: #13253f;
                font-size: 13px;
            }
            QFrame#Sidebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10233f, stop:1 #0c1930);
            }
            QLabel#BrandTitle {
                color: white;
                font-size: 20px;
                font-weight: 700;
                padding: 4px 2px 12px 2px;
            }
            QListWidget#NavList {
                background: transparent;
                border: none;
                color: #d5e1f5;
                outline: none;
            }
            QListWidget#NavList::item {
                border-radius: 10px;
                padding: 12px 14px;
                margin: 2px 0px;
            }
            QListWidget#NavList::item:selected {
                background: #1e4f95;
                color: white;
            }
            QFrame#StatusCard {
                background: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 12px;
                color: #d5e1f5;
            }
            QFrame#MainShell {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f7fbff, stop:1 #eef4fb);
            }
            QLabel#HeaderTitle {
                font-size: 24px;
                font-weight: 700;
                color: #12233d;
            }
            QLabel#HeaderContext, QLabel#MutedLabel {
                color: #69809f;
            }
            QPushButton {
                background: white;
                border: 1px solid #d3dfef;
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover { border-color: #9cb6d7; }
            QPushButton[variant="success"] {
                background: #21a365;
                color: white;
                border-color: #1d8b57;
            }
            QFrame#MetricCard {
                background: white;
                border: 1px solid #dbe4f0;
                border-radius: 14px;
            }
            QLabel#MetricTitle {
                color: #5f7391;
                font-weight: 600;
            }
            QLabel#MetricValue {
                font-size: 28px;
                font-weight: 700;
                color: #10233f;
            }
            QLabel#MetricDetail {
                color: #2f6fed;
                font-size: 12px;
            }
            QFrame#SectionFrame, QFrame#ChartCard, QFrame#SummaryCard {
                background: white;
                border: 1px solid #dbe4f0;
                border-radius: 14px;
            }
            QLabel#SectionTitle {
                font-size: 15px;
                font-weight: 700;
                color: #12233d;
            }
            QLabel#DonutTotal {
                min-width: 150px;
                min-height: 150px;
                max-width: 150px;
                max-height: 150px;
                border-radius: 75px;
                border: 16px solid #2f6fed;
                background: #f8fbff;
                qproperty-alignment: AlignCenter;
                font-size: 18px;
                font-weight: 700;
                color: #12233d;
            }
            QLabel#StepChip {
                background: #edf2f8;
                color: #69809f;
                border-radius: 14px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QLabel#StepChip[active="true"] {
                background: #2f6fed;
                color: white;
            }
            QFrame#ForecastBar {
                background: #2f6fed;
                border-radius: 5px;
            }
            QFrame#ActualBar {
                background: #2ca05a;
                border-radius: 5px;
            }
            QGroupBox {
                background: white;
                border: 1px solid #dbe4f0;
                border-radius: 14px;
                margin-top: 12px;
                font-weight: 700;
                color: #12233d;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 4px;
            }
            QLineEdit, QComboBox, QDateTimeEdit, QTextEdit, QTableWidget, QListWidget {
                background: white;
                border: 1px solid #d5e0ed;
                border-radius: 10px;
                padding: 7px 9px;
            }
            QHeaderView::section {
                background: #f5f8fc;
                border: none;
                border-bottom: 1px solid #dbe4f0;
                padding: 8px;
                font-weight: 700;
                color: #5b7191;
            }
            QTableWidget {
                gridline-color: #ebf0f6;
                alternate-background-color: #fafcff;
            }
            QLabel#SummaryText {
                color: #28405d;
                font-size: 14px;
                line-height: 1.4em;
            }
            """
        )

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

    def refresh_all(self) -> None:
        self._load_dashboard()
        self._load_fuel_prices()
        self._load_forecasts()
        self._load_expenses()
        self._load_pending_approvals()
        self._load_fuel_report()

    def _load_dashboard(self) -> None:
        snap = services.get_dashboard_snapshot(self.incident_id)
        variance = snap.total_actual_cost - snap.total_forecast_cost
        funding_sources = len(services.list_funding_sources(self.incident_id))
        self.metric_cards["total_forecast_cost"].set_value(_money(snap.total_forecast_cost))
        self.metric_cards["total_actual_cost"].set_value(_money(snap.total_actual_cost))
        self.metric_cards["variance"].set_value(_money(variance), "vs forecast")
        self.metric_cards["pending_approvals"].set_value(str(snap.pending_approvals), "View items")
        self.metric_cards["fuel_forecast_cost"].set_value(_money(snap.fuel_forecast_cost))
        self.metric_cards["fuel_actual_cost"].set_value(_money(snap.fuel_actual_cost))
        self.metric_cards["missing_receipts"].set_value(str(snap.missing_receipts), "View items")
        self.metric_cards["funding_sources"].set_value(f"{funding_sources} Active", "View details")

        expenses = services.list_expenses(self.incident_id)[:5]
        self.dashboard_recent_expenses.setRowCount(len(expenses))
        for row_index, item in enumerate(expenses):
            values = [
                str(item.expense_datetime),
                item.category,
                item.description,
                _money(item.amount_total),
                item.status,
                "Yes" if item.receipt_attached else "No",
            ]
            for col, value in enumerate(values):
                self.dashboard_recent_expenses.setItem(row_index, col, QTableWidgetItem(str(value)))

        pending = services.list_pending_approvals(self.incident_id)[:5]
        self.dashboard_pending.setRowCount(len(pending))
        for row_index, item in enumerate(pending):
            values = [item.record_type.title(), item.description, _money(item.amount), str(item.submitted_at or "-"), item.status]
            for col, value in enumerate(values):
                self.dashboard_pending.setItem(row_index, col, QTableWidgetItem(str(value)))

        fuel_actual = snap.fuel_actual_cost
        other_actual = max(snap.total_actual_cost - fuel_actual, 0)
        self.category_chart.set_rows(
            [
                ("Fuel", snap.fuel_forecast_cost, fuel_actual),
                ("Meals", snap.total_forecast_cost * 0.18, snap.total_actual_cost * 0.14),
                ("Lodging", snap.total_forecast_cost * 0.24, snap.total_actual_cost * 0.11),
                ("Supplies", snap.total_forecast_cost * 0.12, snap.total_actual_cost * 0.09),
                ("Equipment", snap.total_forecast_cost * 0.09, snap.total_actual_cost * 0.07),
                ("Other", snap.total_forecast_cost * 0.08, other_actual * 0.25),
            ]
        )
        self.period_summary.set_values(
            snap.total_actual_cost,
            [
                ("OP 1 (Past)", snap.total_actual_cost * 0.4, "#27ae60"),
                ("OP 2 (Current)", snap.total_actual_cost * 0.6, "#2f6fed"),
                ("OP 3 (Future)", 0.0, "#f39c12"),
            ],
        )

    def _load_fuel_prices(self) -> None:
        rows = services.list_fuel_price_profiles(self.incident_id)
        self.fuel_prices_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                item.id,
                _money(item.gasoline_price),
                _money(item.diesel_price),
                _money(item.jet_a_price),
                _money(item.aviation_100ll_price),
                str(item.effective_at),
                "Yes" if item.is_active else "No",
            ]
            for col, value in enumerate(values):
                self.fuel_prices_table.setItem(row_index, col, QTableWidgetItem(str(value)))

    def _load_forecasts(self) -> None:
        rows = services.list_forecasts(self.incident_id)
        self.forecasts_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                item.id,
                item.forecast_name,
                item.forecast_type,
                item.operational_period_id or "-",
                f"{item.total_estimated_gallons:.2f}",
                _money(item.total_estimated_cost),
                item.status,
            ]
            for col, value in enumerate(values):
                self.forecasts_table.setItem(row_index, col, QTableWidgetItem(str(value)))
        self._update_forecast_summary()

    def _load_expenses(self) -> None:
        rows = services.list_expenses(self.incident_id)
        search = self.expense_search.text().strip().lower() if hasattr(self, "expense_search") else ""
        if search:
            rows = [row for row in rows if search in row.description.lower() or search in row.category.lower()]
        self.expenses_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                item.id,
                str(item.expense_datetime),
                item.category,
                item.description,
                _money(item.amount_total),
                item.status,
                "Yes" if item.receipt_attached else "No",
                item.entered_by or "-",
            ]
            for col, value in enumerate(values):
                self.expenses_table.setItem(row_index, col, QTableWidgetItem(str(value)))

    def _load_pending_approvals(self) -> None:
        rows = services.list_pending_approvals(self.incident_id)
        self.pending_approvals_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [item.record_type.title(), item.description, _money(item.amount), str(item.submitted_at or "-"), item.status]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if col == 0:
                    cell.setData(Qt.UserRole, (item.record_type, item.record_id))
                self.pending_approvals_table.setItem(row_index, col, cell)

    def _load_fuel_report(self) -> None:
        rows = services.get_fuel_report(self.incident_id)
        self.report_subtitle.setText(f"Forecasts and actuals for incident {self.incident_id}")
        self.fuel_report_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            variance_text = _money(item.variance)
            status = "Over forecast" if item.variance > 0 else "Under forecast" if item.variance < 0 else "On target"
            values = [item.forecast_name, _money(item.estimated_cost), _money(item.actual_cost), variance_text, status]
            for col, value in enumerate(values):
                self.fuel_report_table.setItem(row_index, col, QTableWidgetItem(str(value)))

    def _refresh_report_preview(self) -> None:
        current = self.report_menu.currentItem()
        if current is None:
            return
        self.report_title.setText(current.text())

    def _save_fuel_price_profile(self) -> None:
        profile = FuelPriceProfileCreate(
            operational_period_id=None,
            gasoline_price=float(self.price_gasoline.text()),
            diesel_price=float(self.price_diesel.text()),
            jet_a_price=float(self.price_jet_a.text()),
            aviation_100ll_price=float(self.price_100ll.text()),
            location_note=self.price_location.text() or None,
            source_note=self.price_source.text() or None,
            entered_by="Finance/Admin",
            effective_at=self.price_effective.dateTime().toPython(),
            is_active=self.price_active.isChecked(),
        )
        services.create_fuel_price_profile(self.incident_id, profile)
        self._load_fuel_prices()

    def _copy_previous_fuel_price_profile(self) -> None:
        profile = services.get_active_fuel_price_profile(self.incident_id)
        if profile is None:
            QMessageBox.information(self, "Fuel Prices", "No active fuel price profile found.")
            return
        self.price_gasoline.setText(f"{profile.gasoline_price:.2f}")
        self.price_diesel.setText(f"{profile.diesel_price:.2f}")
        self.price_jet_a.setText(f"{profile.jet_a_price:.2f}")
        self.price_100ll.setText(f"{profile.aviation_100ll_price:.2f}")
        self.price_location.setText(profile.location_note or "")
        self.price_source.setText(profile.source_note or "")
        self.price_effective.setDateTime(profile.effective_at)
        self.price_active.setChecked(True)

    def _set_selected_fuel_price_profile_active(self) -> None:
        profile_id = self._selected_id(self.fuel_prices_table)
        if profile_id is None:
            return
        services.set_active_fuel_price_profile(self.incident_id, profile_id)
        self._load_fuel_prices()

    def _apply_active_fuel_price(self) -> None:
        price = services.get_fuel_unit_price(self.incident_id, self.forecast_fuel_type.currentText())
        if price is None:
            QMessageBox.information(self, "Fuel Forecast", "No active fuel profile found.")
            return
        self.forecast_price.setText(f"{price:.2f}")
        self._update_forecast_summary()

    def _update_forecast_summary(self) -> None:
        quantity = int(self.forecast_quantity.text() or "0") if self.forecast_quantity.text().isdigit() else 0
        miles = float(self.forecast_miles.text() or "0")
        mpg = float(self.forecast_mpg.text() or "0") if self.forecast_mpg.text() else 0
        hours = float(self.forecast_hours.text() or "0") if self.forecast_hours.text() else 0
        gph = float(self.forecast_gph.text() or "0") if self.forecast_gph.text() else 0
        price = float(self.forecast_price.text() or "0") if self.forecast_price.text() else 0
        total_miles = quantity * miles
        gallons = (total_miles / mpg) if mpg else (hours * gph)
        cost = gallons * price
        self.forecast_summary.setText(
            f"Total Vehicles: {quantity}\n"
            f"Total Estimated Miles: {total_miles:.0f}\n"
            f"Estimated Gallons: {gallons:.2f} gal\n"
            f"Estimated Cost: {_money(cost)}"
        )

    def _save_forecast(self) -> None:
        try:
            if not self.forecast_name.text().strip():
                raise ValueError("Forecast name is required.")
            if not self.forecast_op.text().strip():
                raise ValueError("Operational period is required.")
            if not self.forecast_resource_name.text().strip():
                raise ValueError("Resource name is required.")
            forecast = services.create_forecast(
                self.incident_id,
                FinanceForecastCreate(
                    operational_period_id=self.forecast_op.text() or None,
                    forecast_name=self.forecast_name.text(),
                    notes=self.forecast_notes.text() or None,
                    created_by="Finance/Admin",
                ),
            )
            line = FuelForecastLineCreate(
                resource_type=self.forecast_resource_type.currentText(),
                resource_name=self.forecast_resource_name.text(),
                fuel_type=self.forecast_fuel_type.currentText(),
                quantity=int(self.forecast_quantity.text() or "1"),
                estimated_miles_per_resource=float(self.forecast_miles.text()) if self.forecast_miles.text() else None,
                estimated_mpg=float(self.forecast_mpg.text()) if self.forecast_mpg.text() else None,
                estimated_hours=float(self.forecast_hours.text()) if self.forecast_hours.text() else None,
                gallons_per_hour=float(self.forecast_gph.text()) if self.forecast_gph.text() else None,
                fuel_price=float(self.forecast_price.text() or "0"),
                linked_task_id=self.forecast_task.text() or None,
                notes=self.forecast_notes.text() or None,
            )
            services.add_fuel_forecast_line(self.incident_id, forecast.id, line)
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Fuel Forecast", str(exc))

    def _submit_selected_forecast(self) -> None:
        forecast_id = self._selected_id(self.forecasts_table)
        if forecast_id is None:
            return
        services.submit_forecast(self.incident_id, forecast_id, "Finance/Admin")
        self.refresh_all()

    def _approve_selected_forecast(self) -> None:
        forecast_id = self._selected_id(self.forecasts_table)
        if forecast_id is None:
            return
        services.approve_forecast(self.incident_id, forecast_id, "Finance/Admin")
        self.refresh_all()

    def _save_expense(self) -> None:
        expense = services.create_expense(
            self.incident_id,
            FinanceExpenseCreate(
                category=self.expense_category.currentText(),
                subcategory=self.expense_subcategory.text() or None,
                description=self.expense_description.text(),
                vendor=self.expense_vendor.text() or None,
                expense_datetime=self.expense_datetime.dateTime().toPython(),
                amount_subtotal=float(self.expense_subtotal.text() or "0"),
                amount_tax=float(self.expense_tax.text() or "0"),
                amount_tip=float(self.expense_tip.text() or "0"),
                payment_method=self.expense_payment.text() or None,
                entered_by="Finance/Admin",
                notes=self.expense_notes.text() or None,
                linked_forecast_id=int(self.expense_forecast_link.text()) if self.expense_forecast_link.text() else None,
                receipt_attached=bool(self.expense_receipt_name.text()),
            ),
        )
        if self.expense_receipt_name.text():
            services.create_attachment(
                self.incident_id,
                AttachmentCreate(
                    record_type="expense",
                    record_id=expense.id,
                    filename=self.expense_receipt_name.text(),
                    file_path=self.expense_receipt_name.text(),
                    uploaded_by="Finance/Admin",
                ),
            )
        self.refresh_all()

    def _submit_selected_expense(self) -> None:
        expense_id = self._selected_id(self.expenses_table)
        if expense_id is None:
            return
        services.submit_expense(self.incident_id, expense_id, "Finance/Admin")
        self.refresh_all()

    def _approve_selected_expense(self) -> None:
        expense_id = self._selected_id(self.expenses_table)
        if expense_id is None:
            return
        services.approve_expense(self.incident_id, expense_id, "Finance/Admin")
        self.refresh_all()

    def _open_selected_expense_detail(self) -> None:
        expense_id = self._selected_id(self.expenses_table)
        if expense_id is None:
            return
        dialog = ExpenseDetailDialog(self.incident_id, expense_id, self)
        dialog.resize(860, 620)
        dialog.exec()

    def _selected_pending_record(self) -> tuple[str, int] | None:
        row = self.pending_approvals_table.currentRow()
        if row < 0:
            return None
        item = self.pending_approvals_table.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else None

    def _approve_selected_pending_item(self) -> None:
        selected = self._selected_pending_record()
        if selected is None:
            return
        record_type, record_id = selected
        if record_type == "forecast":
            services.approve_forecast(self.incident_id, record_id, "Finance/Admin")
        elif record_type == "expense":
            services.approve_expense(self.incident_id, record_id, "Finance/Admin")
        self.refresh_all()

    def _return_selected_pending_item(self) -> None:
        selected = self._selected_pending_record()
        if selected is None:
            return
        record_type, record_id = selected
        if record_type == "expense":
            services.mark_expense_status(
                self.incident_id,
                record_id,
                "Returned for Information",
                actor="Finance/Admin",
                comments="Returned from approvals screen.",
            )
        self.refresh_all()
