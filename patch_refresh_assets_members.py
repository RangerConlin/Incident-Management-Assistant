import io,re
s=io.open(r"modules/operations/teams/panels/team_detail_window.py","r",encoding="utf-8").read()
pattern=r"def _refresh_assets\(self\) -> None:[\s\S]*?@Slot\(int\)\s*def _on_assets_changed"
replacement='''def _refresh_assets(self) -> None:
        try:
            tid = int(self._team.team_id) if self._team.team_id is not None else None
            if not tid:
                self._personnel = []
                self._vehicles = []
                self._equipment = []
                self._aircraft = []
                return
            # Prefer members_json list for personnel composition
            members_ids = []
            try:
                members_ids = [int(x) for x in (self._team.members or [])]
            except Exception:
                members_ids = []
            if members_ids:
                people: list[dict[str, Any]] = []
                for pid in members_ids:
                    row = None
                    try:
                        from modules.logistics.checkin import repository as ci_repo
                        ident = ci_repo.get_person_identity(str(pid))
                        if ident:
                            row = {
                                'id': int(pid),
                                'name': ident.name,
                                'role': getattr(ident, 'primary_role', None),
                                'phone': getattr(ident, 'phone', None),
                                'callsign': getattr(ident, 'callsign', None),
                                'identifier': getattr(ident, 'callsign', None) or None,
                                'rank': None,
                                'organization': None,
                                'is_medic': None,
                            }
                    except Exception:
                        row = None
                    if row is None:
                        row = {'id': int(pid), 'name': f'Personnel {pid}', 'role': None, 'phone': None, 'callsign': None, 'identifier': None, 'rank': None, 'organization': None, 'is_medic': None}
                    people.append(row)
                self._personnel = people
            else:
                # Fallback to DB-derived composition
                self._personnel = fetch_team_personnel(tid)
            self._vehicles = fetch_team_vehicles(tid)
            self._equipment = fetch_team_equipment(tid)
            self._aircraft = fetch_team_aircraft(tid)
        except Exception:
            # Keep previous values on error
            pass

    @Slot(int)
    def _on_assets_changed'''
ns=re.sub(pattern,replacement,s,flags=re.S)
io.open(r"modules/operations/teams/panels/team_detail_window.py","w",encoding="utf-8",newline="").write(ns)
print('PATCHED_REFRESH_ASSETS')
