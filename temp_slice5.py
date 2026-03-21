        self._name_field.blockSignals(False)

        assignment = team.get("assignment") or ""
        self._assignment_field.blockSignals(True)
        self._assignment_field.setText(str(assignment or ""))
        self._assignment_field.blockSignals(False)

    def _update_last_contact(self, team: Dict[str, Any]) -> None:
        ts = team.get("last_comm_ts") or team.get("last_contact_ts") or team.get("last_update_ts")
        label = "–"
        if ts:
            try:
                dt = datetime.fromisoformat(str(ts))
                label = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                label = str(ts)
        self._last_contact_value.setText(label)

    def _update_task_widgets(self, team: Dict[str, Any]) -> None:
        task_id = team.get("current_task_id") or team.get("primary_task_id")
        task_display = ""
        if task_id:
            try:
                from modules.operations.taskings.repository import get_task  # type: ignore
                t = get_task(int(task_id))
                title = (t.title or "").strip()
                number = (t.task_id or "").strip()
                if title and number:
                    task_display = f"{title} ({number})"
                else:
                    task_display = title or number or str(task_id)
            except Exception:
                task_display = str(task_id)
        self._task_field.setText(task_display)
        if task_id:
            self._task_button.setText("Open")
            self._unlink_task_button.setVisible(True)
        else:
            self._task_button.setText("Link…")
            self._unlink_task_button.setVisible(False)
        self._view_task_button.setEnabled(bool(task_id))

    def _update_notes_field(self, team: Dict[str, Any]) -> None:
        notes = team.get("notes") or ""
        self._notes_timer.stop()
        self._notes_edit.blockSignals(True)
        self._notes_edit.setPlainText(str(notes))
        self._notes_edit.blockSignals(False)

    def _populate_personnel_table(self, members: List[Dict[str, Any]]) -> None:
        if self._is_air:
            headers = [
                "ID",
                "Name",
                "Rank",
                "Organization",
                "Role",
                "Phone",
                "Certifications",
                "PIC",
