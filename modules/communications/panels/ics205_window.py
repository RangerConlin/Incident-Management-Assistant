from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QListView, QTableView, QFormLayout,
    QLineEdit, QComboBox, QCheckBox, QLabel, QGroupBox, QToolBar,
    QApplication, QMessageBox
)
from PySide6.QtGui import QAction

from utils.state import AppState

from ..controller import ICS205Controller, PLAN_COLUMNS
from ..views.preview_dialog import PreviewDialog
from ..views.new_channel_dialog import NewChannelDialog
from ..views.import_ics217_dialog import ImportICS217Dialog


class ICS205Window(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle('ICS 205 Communications Plan')
        self.setWindowFlag(Qt.Window, True)
        self.controller = ICS205Controller()
        incident = AppState.get_active_incident()
        if incident is None:
            layout = QVBoxLayout(self)
            label = QLabel('Select or create an incident to edit ICS-205.')
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            return
        self._build_ui()
        self.controller.statusLineChanged.connect(self.status_label.setText)
        self.controller.refreshMaster()
        self.controller.refreshPlan()

    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar()
        layout.addWidget(self.toolbar)

        self.btn_new = QAction('New Channel', self)
        self.btn_new.triggered.connect(self._new_channel)
        self.toolbar.addAction(self.btn_new)

        self.btn_import = QAction('Import from ICS-217', self)
        self.btn_import.triggered.connect(self._import_217)
        self.toolbar.addAction(self.btn_import)

        self.btn_validate = QAction('Validate', self)
        self.btn_validate.triggered.connect(self.controller.runValidation)
        self.toolbar.addAction(self.btn_validate)

        self.btn_preview = QAction('Preview', self)
        self.btn_preview.triggered.connect(self._preview)
        self.toolbar.addAction(self.btn_preview)

        splitter = QSplitter()
        layout.addWidget(splitter, 1)

        # Master list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.master_search = QLineEdit()
        self.master_search.setPlaceholderText('Search...')
        self.master_search.textChanged.connect(lambda t: self.controller.setFilter('search', t))
        left_layout.addWidget(self.master_search)
        self.master_list = QListView()
        self.master_list.setModel(self.controller.masterModel)
        self.master_list.doubleClicked.connect(self._add_master_selection)
        left_layout.addWidget(self.master_list, 1)
        splitter.addWidget(left_widget)

        # Plan table
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.plan_table = QTableView()
        self.plan_table.setModel(self.controller.planModel)
        self.plan_table.selectionModel().selectionChanged.connect(self._on_plan_selection)
        right_layout.addWidget(self.plan_table, 1)
        splitter.addWidget(right_widget)

        splitter.setSizes([200, 500])

        # Details box
        self.details = QGroupBox('Details / Editor')
        form = QFormLayout(self.details)
        self.fields: dict[str, Any] = {}
        for key, label in [
            ('channel', 'Channel'),
            ('function', 'Function'),
            ('assignment_division', 'Division'),
            ('assignment_team', 'Team'),
            ('priority', 'Priority'),
        ]:
            le = QLineEdit()
            le.editingFinished.connect(lambda k=key, w=le: self._field_changed(k, w.text()))
            self.fields[key] = le
            form.addRow(label, le)
        self.include_chk = QCheckBox('Include on ICS-205')
        self.include_chk.stateChanged.connect(lambda s: self._field_changed('include_on_205', 1 if s else 0))
        form.addRow(self.include_chk)
        self.remarks = QLineEdit()
        self.remarks.editingFinished.connect(lambda: self._field_changed('remarks', self.remarks.text()))
        form.addRow('Remarks', self.remarks)
        layout.addWidget(self.details)

        # Status
        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    # ------------------------------------------------------------------
    def _add_master_selection(self, index):
        row = self.controller.masterModel.data(index, Qt.UserRole)
        self.controller.addMasterIdToPlan(row['id'])

    def _on_plan_selection(self, selected, _deselected):
        indexes = self.plan_table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        data = self.controller.planModel.rows[row]
        for key, widget in self.fields.items():
            widget.blockSignals(True)
            widget.setText(str(data.get(key, '')))
            widget.blockSignals(False)
        self.include_chk.blockSignals(True)
        self.include_chk.setChecked(bool(data.get('include_on_205')))
        self.include_chk.blockSignals(False)
        self.remarks.blockSignals(True)
        self.remarks.setText(data.get('remarks', '') or '')
        self.remarks.blockSignals(False)
        self.current_row = row

    def _field_changed(self, key, value):
        if getattr(self, 'current_row', None) is None:
            return
        col = [k for k, _ in PLAN_COLUMNS].index(key)
        self.controller.updatePlanCell(self.current_row, col, value)

    def _preview(self):
        rows = self.controller.getPreviewRows()
        dlg = PreviewDialog(rows, self)
        dlg.exec()

    def _new_channel(self):
        dlg = NewChannelDialog(self.controller, self)
        dlg.exec()
        self.controller.refreshPlan()

    def _import_217(self):
        dlg = ImportICS217Dialog(self.controller, self)
        dlg.exec()
        self.controller.refreshPlan()


# convenience factory

def create_window(parent=None):
    return ICS205Window(parent)
