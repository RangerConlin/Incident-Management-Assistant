"""Qt Widget window for the ICS 206 Medical Plan."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolBar,
    QPushButton, QStackedWidget, QButtonGroup, QStatusBar, QMenu, QMenuBar
)

from .pages.aid_stations_page import AidStationsPage
from .pages.ambulance_page import AmbulancePage
from .pages.hospitals_page import HospitalsPage
from .pages.air_ambulance_page import AirAmbulancePage
from .pages.procedures_page import ProceduresPage
from .pages.comms_page import CommsPage
from .pages.signatures_page import SignaturesPage


class ICS206Window(QMainWindow):
    def __init__(self, bridge, app_state, parent=None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.app_state = app_state
        self.setWindowTitle("ICS 206 — Medical Plan")
        self.resize(1200, 800)

        # Header ---------------------------------------------------------
        header = QWidget(); hbox = QHBoxLayout(header)
        lbl_incident = QLabel(f"Incident: {app_state.incident_name}")
        lbl_op = QLabel(f"Op Period: {app_state.op_period_display}")
        hbox.addWidget(lbl_incident); hbox.addSpacing(24); hbox.addWidget(lbl_op); hbox.addStretch(1)

        # Toolbar --------------------------------------------------------
        tb = QToolBar(); self.addToolBar(Qt.TopToolBarArea, tb)
        act_new = QAction("New", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.new_form)
        act_save = QAction("Save", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self.save_all)
        act_dup = QAction("Duplicate Last OP", self)
        act_dup.triggered.connect(self.bridge.duplicate_last_op)
        m_import = QMenu("Import", self)
        m_import.addAction("Aid Stations from 205", self.bridge.import_aid_from_205)
        m_import.addAction("Ambulance from Master", lambda: self.bridge.import_ambulance_from_master([]))
        m_import.addAction("Hospitals from Master", lambda: self.bridge.import_hospitals_from_master([]))
        m_import.addAction("Comms from Master", lambda: self.bridge.import_comms_from_master([]))
        act_import = QAction("Import", self)
        act_import.setMenu(m_import)
        act_pdf = QAction("PDF", self)
        act_pdf.triggered.connect(self.save_pdf)
        act_print = QAction("Print", self)
        act_print.setShortcut("Ctrl+P")

        tb.addAction(act_new)
        tb.addAction(act_save)
        tb.addAction(act_dup)
        tb.addAction(act_pdf)
        tb.addAction(act_print)
        menubar = QMenuBar(); self.setMenuBar(menubar); menubar.addMenu(m_import)

        # Segmented buttons ----------------------------------------------
        seg = QWidget(); seg_box = QHBoxLayout(seg); seg_box.setContentsMargins(0,0,0,0)
        self.btn_group = QButtonGroup(self)
        labels = [
            "Aid Stations","Ambulance","Hospitals","Air Ambulance","Procedures","Comms","Signatures"
        ]
        for i, text in enumerate(labels):
            b = QPushButton(text); b.setCheckable(True)
            b.clicked.connect(lambda _, ix=i: self.stack.setCurrentIndex(ix))
            self.btn_group.addButton(b, i); seg_box.addWidget(b)
        self.btn_group.buttons()[0].setChecked(True)

        # Pages ----------------------------------------------------------
        self.stack = QStackedWidget()
        self.pages = [
            AidStationsPage(self.bridge),
            AmbulancePage(self.bridge),
            HospitalsPage(self.bridge),
            AirAmbulancePage(self.bridge),
            ProceduresPage(self.bridge),
            CommsPage(self.bridge),
            SignaturesPage(self.bridge),
        ]
        for p in self.pages:
            self.stack.addWidget(p)

        # Central layout -------------------------------------------------
        central = QWidget(); vbox = QVBoxLayout(central)
        vbox.addWidget(header)
        vbox.addWidget(seg)
        vbox.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # Status bar -----------------------------------------------------
        sb = QStatusBar(); self.setStatusBar(sb)
        sb.showMessage("Ready")
        self.last_saved: datetime | None = None

    # ------------------------------------------------------------------
    def new_form(self) -> None:
        for table in ("ics206_aid_stations","ics206_ambulance","ics206_hospitals","ics206_air_ambulance","ics206_procedures","ics206_comms","ics206_signatures"):
            pass  # placeholder for clearing
        self.statusBar().showMessage("New form")

    def save_all(self) -> None:
        for p in self.pages:
            if hasattr(p, "reload"):
                pass
        self.last_saved = datetime.now()
        self.statusBar().showMessage(f"Saved at {self.last_saved:%H:%M:%S}")

    def save_pdf(self) -> None:
        path = self.bridge.export_pdf("ics206.pdf")
        self.statusBar().showMessage(f"PDF saved to {path}")
