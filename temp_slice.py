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
    def removeMember(self, person_id: int) -> None:
        """Unassign a person from this team (set team_id = NULL)."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            set_person_team(int(person_id), None)
            # Clear leader if removing current leader
            if self._team.team_leader_id == int(person_id):
                set_team_leader(int(self._team.team_id), None)
                self._team.team_leader_id = None
                app_signals.teamLeaderChanged.emit(int(self._team.team_id))
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to remove member: {e}")

    @Slot(int, bool)
    def setMedic(self, person_id: int, is_medic: bool) -> None:
        try:
            set_person_medic(int(person_id), bool(is_medic))
            if self._team.team_id:
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to set medic: {e}")

    @Slot('QVariant')
    def addVehicle(self, vehicle_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if vehicle_id is not None and str(vehicle_id) != "":
                set_vehicle_team(int(vehicle_id), int(self._team.team_id))
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add vehicle: {e}")

    # Convenience for QML unified action in Vehicles/Aircraft tab
    @Slot('QVariant')
    def addAsset(self, asset_id: Any = None) -> None:
        try:
            code = (self._team.team_type or "").upper()
            if code == "AIR":
                self.addAircraft(asset_id)
            else:
                self.addVehicle(asset_id)
        except Exception as e:
            self.error.emit(f"Failed to add asset: {e}")

    @Slot('QVariant')
    def removeVehicle(self, vehicle_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            set_vehicle_team(int(vehicle_id), None)
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to remove vehicle: {e}")

    # Convenience for QML unified action in Vehicles/Aircraft tab
    @Slot('QVariant')
    def removeAsset(self, asset_id: Any) -> None:
        try:
            code = (self._team.team_type or "").upper()
            if code == "AIR":
                self.removeAircraft(asset_id)
            else:
                self.removeVehicle(asset_id)
        except Exception as e:
            self.error.emit(f"Failed to remove asset: {e}")

    @Slot('QVariant')
    def addEquipment(self, eq_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if eq_id is not None and str(eq_id) != "":
                set_equipment_team(int(eq_id), int(self._team.team_id))
                app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add equipment: {e}")

    @Slot('QVariant')
    def removeEquipment(self, eq_id: Any) -> None:
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            set_equipment_team(int(eq_id), None)
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to remove equipment: {e}")

