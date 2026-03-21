    @Slot(int)
    def _on_leader_changed(self, team_id: int) -> None:
        try:
            if self._team.team_id and int(team_id) == int(self._team.team_id):
                lid = fetch_team_leader_id(int(team_id))
                self._team.team_leader_id = int(lid) if lid is not None else None
                self.teamChanged.emit()
        except Exception:
            pass
    def _auto_set_pilot(self) -> None:
        """Ensure team_leader_id remains valid and pick a default.

        For aircraft teams, prefer a member whose check-in role contains
        "pilot". For all teams, if the existing leader is missing or no
        suitable pilot is found, fall back to the first member.
        """
        try:
            members: list[int] = []
            for raw in getattr(self._team, "members", []) or []:
                try:
                    members.append(int(raw))
                except (TypeError, ValueError):
                    continue
            if not members:
                for rec in self._personnel or []:
                    pid = rec.get("id")
                    try:
                        if pid is not None:
                            members.append(int(pid))
                    except (TypeError, ValueError):
                        continue
                if members:
                    # Cache for future loads so we keep the derived order
                    self._team.members = members
            if not members:
                return
            try:
                current_leader = int(self._team.team_leader_id)
            except Exception:
                current_leader = None
            if current_leader is not None and current_leader in members:
                return
            self._team.team_leader_id = None
            if self.isAircraftTeam:
                try:
                    from modules.logistics.checkin import repository as checkin_repo
                    for pid in members:
                        rec = checkin_repo.find_personnel_by_id(str(pid))
                        role = (rec.get("role") or "").lower() if rec else ""
                        if "pilot" in role:
                            self._team.team_leader_id = int(pid)
                            break
                except Exception:
                    pass
            if self._team.team_leader_id is None:
                self._team.team_leader_id = members[0]
        except Exception:
            pass

    def _persist_needs_attention(self, active: bool) -> None:
        if not self._team.team_id:
            return
        try:
            with team_repo._incident_connect() as con:  # type: ignore[attr-defined]
                try:
                    con.execute(
                        "UPDATE teams SET needs_attention=? WHERE id=?",
                        (1 if active else 0, int(self._team.team_id)),
                    )
                    con.commit()
                except Exception:
                    pass
        except Exception:
            pass

    def _emit_incident_refresh(self) -> None:
        try:
            inc = incident_context.get_active_incident_id()
            if inc:
                from utils.app_signals import app_signals as _sig

                _sig.incidentChanged.emit(str(inc))
        except Exception:
            pass

    # ---- Member/asset management ----
    def _is_member_role_valid(self, person_id: int) -> bool:
        """Validate a person's role against the team type.

        Ground teams should not have aircrew and vice versa. The check is
        intentionally lightweight and falls back to True if lookup fails.
        """
        try:
            from modules.logistics.checkin import repository as checkin_repo
            rec = checkin_repo.find_personnel_by_id(str(person_id))
            role = (rec.get("role") or "").lower() if rec else ""
            if self.isAircraftTeam:
                return "air" in role or "pilot" in role
            return not ("air" in role or "pilot" in role)
        except Exception:
            return True

    @Slot('QVariant')
    def addMember(self, person_id: Any = None) -> None:
        """Assign a person to this team by setting their team_id."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if person_id is None:
                # No-op placeholder for UI without selector wired yet
                return
            if not self._is_member_role_valid(int(person_id)):
                self.error.emit("Selected person role not valid for this team")
                return
            set_person_team(int(person_id), int(self._team.team_id))
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add member: {e}")

    @Slot(int)
