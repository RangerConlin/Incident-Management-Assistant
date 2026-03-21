import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
pattern=r"@Slot\('QVariant'\)\s*def addMember\(self, person_id: Any = None\) -> None:\n[\s\S]*?self\.error\.emit\(f\"Failed to add member: \{e\}\"\)\n"
replacement='''@Slot('QVariant')
    def addMember(self, person_id: Any = None) -> None:
        """Assign a person to this team by setting their team_id and syncing check-in."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if person_id is None:
                return
            pid = int(person_id)
            if not self._is_member_role_valid(pid):
                self.error.emit("Selected person role not valid for this team")
                return
            set_person_team(pid, int(self._team.team_id))
            # Update or create check-in record to reflect team assignment
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
'''
ns=re.sub(pattern,replacement,s,flags=re.S)
if ns==s:
    print('ADD_MEMBER_PATTERN_NOT_FOUND')
else:
    io.open(p,'w',encoding='utf-8',newline='').write(ns)
    print('ADD_MEMBER_PATCHED')
