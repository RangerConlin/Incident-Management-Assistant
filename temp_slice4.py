
    def _update_aircraft_assignment_display(self) -> None:
        if not hasattr(self, "_aircraft_combo"):
            return
        self._refreshing_aircraft = True
        try:
            self._aircraft_combo.blockSignals(True)
            self._aircraft_combo.clear()
            self._aircraft_combo.addItem("No Aircraft Assigned", None)
            current_id: Optional[int] = None
            if self._is_air:
                self._aircraft_combo.setEnabled(True)
                current_record = None
                for rec in self._asset_cache:
                    if rec.get("id") is not None:
                        current_record = rec
                        break
                if current_record:
                    current_id = current_record.get("id")
                    label = self._format_aircraft_label(current_record)
                    self._aircraft_combo.addItem(label, current_id)
                    self._aircraft_combo.setCurrentIndex(1)
                else:
                    self._aircraft_combo.setCurrentIndex(0)
            else:
                self._aircraft_combo.setEnabled(False)
                self._aircraft_combo.setCurrentIndex(0)
            self._current_aircraft_id = (
                int(current_id) if current_id is not None and str(current_id) != "" else None
            )
        finally:
            self._aircraft_combo.blockSignals(False)
            self._refreshing_aircraft = False

    def _refresh_aircraft_options(self) -> None:
        if not self._is_air or not hasattr(self, "_aircraft_combo"):
            return
        try:
            options = self._bridge.availableAircraft() if hasattr(self._bridge, "availableAircraft") else []
        except Exception:
            options = []
        current_id = self._current_aircraft_id
        self._refreshing_aircraft = True
        try:
            self._aircraft_combo.blockSignals(True)
            self._aircraft_combo.clear()
            self._aircraft_combo.addItem("No Aircraft Assigned", None)
            seen: set[str] = set()
            for opt in options or []:
                opt_id = opt.get("id")
                label = self._format_aircraft_label(opt)
                self._aircraft_combo.addItem(label, opt_id)
                if opt_id is not None and str(opt_id) != "":
                    seen.add(str(opt_id))
            if current_id is not None and str(current_id) not in seen:
                for rec in self._asset_cache:
                    if str(rec.get("id")) == str(current_id):
                        label = self._format_aircraft_label(rec)
                        self._aircraft_combo.addItem(label, current_id)
                        break
            target = current_id if current_id is not None else None
            idx = self._aircraft_combo.findData(target)
            if idx >= 0:
                self._aircraft_combo.setCurrentIndex(idx)
            else:
                self._aircraft_combo.setCurrentIndex(0)
        finally:
            self._aircraft_combo.blockSignals(False)
            self._refreshing_aircraft = False

    def _handle_aircraft_selected(self, index: int) -> None:
        if self._updating or self._refreshing_aircraft or not hasattr(self, "_aircraft_combo"):
            return
        data = self._aircraft_combo.itemData(index)
        target = data if data not in ("", None) else None
        if self._current_aircraft_id is None and target is None:
            return
        if target is not None and self._current_aircraft_id is not None:
            try:
                if int(target) == int(self._current_aircraft_id):
