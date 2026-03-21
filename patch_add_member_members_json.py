import io,re
s=io.open(r"modules/operations/teams/panels/team_detail_window.py","r",encoding="utf-8").read()
pattern=r"@Slot\('QVariant'\)\s*def addMember\(self, person_id: Any = None\) -> None:[\s\S]*?@Slot\(int\)\s*def removeMember\(self, person_id: int\) -> None:"
replacement='''@Slot('QVariant')
    def addMember(self, person_id: Any = None) -> None:
        """Add a person to this team by updating teams.members_json; also sync Check-In."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if person_id in (None, ""):
                return
            pid = int(person_id)
            # Update team.members list
            members = list(getattr(self._team, 'members', []) or [])
            if pid not in members:
                members.append(pid)
                self._team.members = members
                try:
                    team_repo.save_team(self._team)
                except Exception:
                    pass
            # Best-effort: keep Check-In record aligned so other views remain consistent
            try:
                from modules.logistics.checkin import repository as ci_repo
                from modules.logistics.checkin.models import CheckInRecord, CIStatus, PersonnelStatus, Location
                now_iso = datetime.now().astimezone().isoformat()
                rec = ci_repo.fetch_checkin(str(pid))
                if rec is None:
                    ident = None
                    try:
                        ident = ci_repo.get_person_identity(str(pid))
                    except Exception:
                        ident = None
                    rec = CheckInRecord(
                        person_id=str(pid),
                        ci_status=CIStatus.CHECKED_IN,
                        personnel_status=PersonnelStatus.ASSIGNED,
                        arrival_time=now_iso,
                        location=Location.ICP,
                        incident_callsign=(getattr(ident, 'callsign', None) if ident else None),
                        incident_phone=(getattr(ident, 'phone', None) if ident else None),
                        team_id=str(self._team.team_id),
                        role_on_team=(getattr(ident, 'primary_role', None) if ident else None),
                    )
                else:
                    rec.team_id = str(self._team.team_id)
                    try:
                        rec.updated_at = now_iso
                    except Exception:
                        pass
                ci_repo.save_checkin(rec)
            except Exception:
                pass
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add member: {e}")

    @Slot(int)
    def removeMember(self, person_id: int) -> None:
'''
ns=re.sub(pattern,replacement,s,flags=re.S)
io.open(r"modules/operations/teams/panels/team_detail_window.py","w",encoding="utf-8",newline="").write(ns)
print('PATCHED_ADD_MEMBER_TO_MEMBERS_JSON')
