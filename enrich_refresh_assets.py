import io,re
s=io.open(r"modules/operations/teams/panels/team_detail_window.py","r",encoding="utf-8").read()
pattern=r"def _refresh_assets\(self\) -> None:[\s\S]*?self\._aircraft = fetch_team_aircraft\(tid\)[\s\S]*?except Exception:[\s\S]*?pass"
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
            members_ids: list[int] = []
            try:
                members_ids = [int(x) for x in (self._team.members or [])]
            except Exception:
                members_ids = []
            people: list[dict[str, Any]] = []
            if members_ids:
                # Probe incident personnel table once
                try:
                    from models.queries import get_db_connection as _dbc
                    conn = _dbc()
                    cols = {r[1] for r in conn.execute("PRAGMA table_info(personnel)").fetchall()}
                    want = ['id','name','role','phone']
                    if 'callsign' in cols: want.append('callsign')
                    if 'rank' in cols: want.append('rank')
                    if 'organization' in cols: want.append('organization')
                    if 'is_medic' in cols: want.append('is_medic')
                    col_list = ", ".join(want)
                    placeholders = ",".join(["?"]*len(members_ids))
                    rows = {}
                    if members_ids:
                        cur = conn.execute(f"SELECT {col_list} FROM personnel WHERE id IN ({placeholders})", tuple(members_ids))
                        for row in cur.fetchall():
                            d = dict(row)
                            rows[str(d.get('id'))] = d
                except Exception:
                    rows = {}
                for pid in members_ids:
                    base = None
                    try:
                        rec = rows.get(str(pid)) if 'rows' in locals() else None
                        if rec:
                            base = {
                                'id': int(pid),
                                'name': rec.get('name'),
                                'role': rec.get('role'),
                                'phone': rec.get('phone'),
                                'callsign': rec.get('callsign') if 'callsign' in rec else None,
                                'identifier': rec.get('callsign') if 'callsign' in rec else None,
                                'rank': rec.get('rank') if 'rank' in rec else None,
                                'organization': rec.get('organization') if 'organization' in rec else None,
                                'is_medic': rec.get('is_medic') if 'is_medic' in rec else None,
                            }
                    except Exception:
                        base = None
                    if base is None:
                        # Fall back to Check-In identity
                        try:
                            from modules.logistics.checkin import repository as ci_repo
                            ident = ci_repo.get_person_identity(str(pid))
                        except Exception:
                            ident = None
                        if ident:
                            base = {
                                'id': int(pid),
                                'name': getattr(ident,'name',''),
                                'role': getattr(ident,'primary_role', None),
                                'phone': getattr(ident,'phone', None),
                                'callsign': getattr(ident,'callsign', None),
                                'identifier': getattr(ident,'callsign', None) or None,
                                'rank': None,
                                'organization': getattr(ident,'home_unit', None),
                                'is_medic': None,
                            }
                    if base is None:
                        base = {'id': int(pid), 'name': f'Personnel {pid}', 'role': None, 'phone': None, 'callsign': None, 'identifier': None, 'rank': None, 'organization': None, 'is_medic': None}
                    people.append(base)
                self._personnel = people
            else:
                # Fallback to DB-derived composition (legacy)
                self._personnel = fetch_team_personnel(tid)
            self._vehicles = fetch_team_vehicles(tid)
            self._equipment = fetch_team_equipment(tid)
            self._aircraft = fetch_team_aircraft(tid)
        except Exception:
            # Keep previous values on error
            pass'''
ns=re.sub(pattern,replacement,s,flags=re.S)
io.open(r"modules/operations/teams/panels/team_detail_window.py","w",encoding="utf-8",newline="").write(ns)
print('REFRESH_ASSETS_ENRICHED')
