        self._assignment_field = QLineEdit()
        right_form.addRow(QLabel("Assignment"), self._assignment_field)

        grid.addWidget(right_widget, 0, 1)

        notes_label = QLabel("Notes")
        self._notes_edit = QTextEdit()
        self._notes_edit.setWordWrapMode(QTextOption.WordWrap)
        self._notes_edit.setFixedHeight(90)
        overview_layout.addWidget(notes_label)
        overview_layout.addWidget(self._notes_edit)

        main_layout.addWidget(overview_frame)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        self._edit_team_button = QPushButton("Edit Team")
        actions_layout.addWidget(self._edit_team_button)
        self._needs_assist_button = QPushButton("Flag Needs Assistance")
        actions_layout.addWidget(self._needs_assist_button)
        self._status_button = QPushButton("Update Status")
        actions_layout.addWidget(self._status_button)
        self._view_task_button = QPushButton("View Task")
        actions_layout.addWidget(self._view_task_button)
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.North)
        main_layout.addWidget(self._tabs, 1)

        self._personnel_tab = QWidget()
        self._assets_tab = QWidget()
        self._equipment_tab = QWidget()
        self._logs_tab = QWidget()
        self._tabs.addTab(self._personnel_tab, "Personnel (Ground)")
        self._tabs.addTab(self._assets_tab, "Vehicles")
        self._tabs.addTab(self._equipment_tab, "Equipment")
        self._tabs.addTab(self._logs_tab, "Logs")

        personnel_layout = QVBoxLayout(self._personnel_tab)
        personnel_layout.setContentsMargins(0, 0, 0, 0)
        personnel_layout.setSpacing(8)
        member_buttons = QHBoxLayout()
        member_buttons.setSpacing(6)
        self._add_member_button = QPushButton("Add Personnel")
        member_buttons.addWidget(self._add_member_button)
        member_buttons.addStretch()
        self._member_detail_button = QPushButton("Detail")
        self._member_detail_button.setEnabled(False)
        member_buttons.addWidget(self._member_detail_button)
        personnel_layout.addLayout(member_buttons)

        self._personnel_table = QTableWidget()
        self._personnel_table.setAlternatingRowColors(True)
        self._personnel_table.verticalHeader().setVisible(False)
        self._personnel_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._personnel_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._personnel_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._personnel_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._personnel_table.customContextMenuRequested.connect(self._show_personnel_menu)
        self._personnel_table.itemSelectionChanged.connect(self._on_member_selection_changed)
        self._configure_personnel_header()
        personnel_layout.addWidget(self._personnel_table)

        assets_layout = QVBoxLayout(self._assets_tab)
        assets_layout.setContentsMargins(0, 0, 0, 0)
        assets_layout.setSpacing(8)
        asset_buttons = QHBoxLayout()
        asset_buttons.setSpacing(6)
        self._asset_add_button = QPushButton("Add Vehicle")
        asset_buttons.addWidget(self._asset_add_button)
        asset_buttons.addStretch()
        assets_layout.addLayout(asset_buttons)

        self._asset_table = QTableWidget()
        self._asset_table.setAlternatingRowColors(True)
        self._asset_table.verticalHeader().setVisible(False)
        self._asset_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._asset_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._asset_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        assets_layout.addWidget(self._asset_table)

        equipment_layout = QVBoxLayout(self._equipment_tab)
        equipment_layout.setContentsMargins(0, 0, 0, 0)
        equipment_layout.setSpacing(8)
        equipment_buttons = QHBoxLayout()
        equipment_buttons.setSpacing(6)
        self._equipment_add_button = QPushButton("Add Equipment")
        equipment_buttons.addWidget(self._equipment_add_button)
        equipment_buttons.addStretch()
        equipment_layout.addLayout(equipment_buttons)

        self._equipment_table = QTableWidget()
        self._equipment_table.setAlternatingRowColors(True)
        self._equipment_table.verticalHeader().setVisible(False)
        self._equipment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._equipment_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._equipment_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        equipment_layout.addWidget(self._equipment_table)

        # Logs tab: ICS-214 for this team
        logs_layout = QVBoxLayout(self._logs_tab)
        logs_layout.setContentsMargins(0, 0, 0, 0)
        logs_layout.setSpacing(8)
        bar = QHBoxLayout()
        self._btn_214_refresh = QPushButton("Refresh")
        self._btn_214_export = QPushButton("Export 214")
        self._btn_214_edit = QPushButton("Edit")
        self._btn_214_delete = QPushButton("Delete")
        for b in (self._btn_214_refresh, self._btn_214_export, self._btn_214_edit, self._btn_214_delete):
            bar.addWidget(b)
        bar.addStretch(1)
        logs_layout.addLayout(bar)
        self._tbl_214 = QTableView(self)
        self._model_214 = QStandardItemModel(0, 3, self)
        self._model_214.setHorizontalHeaderLabels(["Timestamp", "Entry", "Entered By"])
        self._tbl_214.setModel(self._model_214)
        try:
            self._tbl_214.setSortingEnabled(True)
        except Exception:
            pass
        logs_layout.addWidget(self._tbl_214)

        # Connections for form controls
        self._team_type_combo.currentIndexChanged.connect(self._handle_team_type_changed)
        self._status_combo.currentIndexChanged.connect(self._handle_status_changed)
        self._name_field.editingFinished.connect(self._handle_name_edited)
        self._assignment_field.editingFinished.connect(self._handle_assignment_edited)
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        self._task_button.clicked.connect(self._handle_task_button)
        self._unlink_task_button.clicked.connect(self._handle_unlink_task)
        self._edit_team_button.clicked.connect(self._handle_edit_team)
        self._needs_assist_button.clicked.connect(self._handle_needs_assist)
        self._status_button.clicked.connect(self._status_combo.showPopup)
        self._view_task_button.clicked.connect(self._handle_view_task)
        self._add_member_button.clicked.connect(self._handle_add_member)
        self._member_detail_button.clicked.connect(self._handle_member_detail)
        self._asset_add_button.clicked.connect(self._handle_add_asset)
        self._equipment_add_button.clicked.connect(self._handle_add_equipment)

        self._aircraft_combo.popupAboutToBeShown.connect(self._refresh_aircraft_options)
        self._aircraft_combo.currentIndexChanged.connect(self._handle_aircraft_selected)
        # Logs actions
        self._btn_214_refresh.clicked.connect(self._load_team_ics214)
        self._btn_214_export.clicked.connect(self._export_team_ics214)
        self._btn_214_delete.clicked.connect(self._delete_team_ics214_entry)
        self._btn_214_edit.clicked.connect(self._edit_team_ics214_entry)

    # ---- Team ICS-214 helpers ----
    def _get_team_ics214_stream(self) -> tuple[str | None, str | None]:
        try:
            inc = incident_context.get_active_incident_id()
            if not inc:
                return None, None
            from modules.ics214 import services
            from modules.ics214.schemas import StreamCreate
            team_id = int(self._team_id) if self._team_id is not None else None
            if not team_id:
                return str(inc), None
            streams = services.list_streams(str(inc))
            target = None
            for s in streams:
                try:
                    sec = getattr(s, 'section', None) or ''
                    name = getattr(s, 'name', '')
                    if (f'"ref": "team:{int(team_id)}"' in str(sec)) or (name.strip() == f"Team {int(team_id)}"):
                        target = s
                        break
                except Exception:
                    continue
            if target is None:
                section = '{"category": "team", "ref": "team:%d", "label": "Team %d"}' % (int(team_id), int(team_id))
                target = services.create_stream(StreamCreate(incident_id=str(inc), name=f"Team {int(team_id)}", section=section, kind="team"))
            return str(inc), getattr(target, 'id', None)
        except Exception:
            return None, None

    def _load_team_ics214(self) -> None:
        inc, sid = self._get_team_ics214_stream()
        if not inc or not sid:
            try:
                self._model_214.removeRows(0, self._model_214.rowCount())
            except Exception:
                pass
            return
        try:
            from modules.ics214 import services
            rows = services.list_entries(str(inc), str(sid)) or []
        except Exception:
            rows = []
        try:
            self._model_214.removeRows(0, self._model_214.rowCount())
        except Exception:
            pass
        for r in rows:
            it_ts = QStandardItem(self._fmt_ts(str(r.get("timestamp_utc") or "")))
            it_entry = QStandardItem(str(r.get("text") or ""))
            it_by = QStandardItem(str(r.get("actor_user_id") or ""))
