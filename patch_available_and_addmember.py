# -*- coding: utf-8 -*-
import io,re
p='modules/operations/teams/panels/team_detail_window.py'
s=io.open(p,'r',encoding='utf-8').read()
# Patch availableMembers to read from check-in roster (unassigned only)
av_start=r"@Slot\(result='QVariant'\)\s*def availableMembers\(self\) -> list\[dict\]:"
av_body=r"@Slot\(result='QVariant'\)\s*def availableMembers\(self\) -> list\[dict\]:[\s\S]*?@Slot\(result='QVariant'\)\s*def availableAircraft\(self\) -> list\[dict\]:"
new_av='''@Slot(result='QVariant')
    def availableMembers(self) -> list[dict]:
        # Prefer the Check-In roster; fall back to legacy query if needed
        try:
            from modules.logistics.checkin import repository as ci_repo
            from modules.logistics.checkin.models import RosterFilters
            rows = ci_repo.fetch_roster(RosterFilters())
            out: list[dict] = []
            for r in rows:
                team_id = getattr(r, 'team_id', None)
                if team_id in (None, '', '-'):  # treat missing/placeholder as unassigned
                    out.append({
                        'id': getattr(r, 'person_id', None),
                        'name': getattr(r, 'name', ''),
                        'role': getattr(r, 'role', ''),
                        'callsign': getattr(r, 'callsign', ''),
                        'phone': getattr(r, 'phone', ''),
                    })
            if out:
                return out
        except Exception:
            pass
        try:
            return list_available_personnel() or []
        except Exception:
            return []

    @Slot(result='QVariant')
    def availableAircraft(self) -> list[dict]:
'''
s=re.sub(av_body,new_av,s,flags=re.S)
# Patch addMember to be resilient when personnel.team_id is missing; update check-in record
add_pat=r"@Slot\('QVariant'\)\s*def addMember\(self, person_id: Any = None\) -> None:[\s\S]*?@Slot\(int\)\s*def removeMember\(self, person_id: int\) -> None:"
new_add='''@Slot('QVariant')
    def addMember(self, person_id: Any = None) -> None:
        """Assign a person to this team; also sync Check-In record for robustness."""
        try:
            if not self._team.team_id:
                raise RuntimeError("No team id")
            if person_id is None:
                return
            pid = int(person_id)
            updated_personnel = True
            try:
                set_person_team(pid, int(self._team.team_id))
            except Exception:
                updated_personnel = False
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
                if not updated_personnel:
                    raise
            app_signals.teamAssetsChanged.emit(int(self._team.team_id))
        except Exception as e:
            self.error.emit(f"Failed to add member: {e}")

    @Slot(int)
    def removeMember(self, person_id: int) -> None:
'''
s=re.sub(add_pat,new_add,s,flags=re.S)
io.open(p,'w',encoding='utf-8',newline='').write(s)
print('PATCHED')
