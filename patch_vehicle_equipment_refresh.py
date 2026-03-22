import io,re
s=io.open(r"modules/operations/teams/panels/team_detail_window.py","r",encoding="utf-8").read()
# 1) Make AddVehicleDialog / AddEquipmentDialog tables non-editable and double-click to accept
s=re.sub(r"self\._tbl = QTableWidget\(self\); self\._tbl\.setColumnCount\(5\)([\s\S]*?)layout\.addWidget\(self\._tbl, 1\)",
         lambda m: m.group(0).replace("layout.addWidget(self._tbl, 1)",
         "try:\n            self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)\n        except Exception: pass\n        try:\n            self._tbl.itemDoubleClicked.connect(lambda *_: self._accept())\n        except Exception: pass\n        layout.addWidget(self._tbl, 1)"), s, count=1)

s=re.sub(r"self\._tbl = QTableWidget\(self\); self\._tbl\.setColumnCount\(4\)([\s\S]*?)layout\.addWidget\(self\._tbl, 1\)",
         lambda m: m.group(0).replace("layout.addWidget(self._tbl, 1)",
         "try:\n            self._tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)\n        except Exception: pass\n        try:\n            self._tbl.itemDoubleClicked.connect(lambda *_: self._accept())\n        except Exception: pass\n        layout.addWidget(self._tbl, 1)"), s, count=1)

# 2) Remove stray duplicate equipment handler lines
s = s.replace("\n        handler = getattr(self._bridge, \"addEquipment\", None)\n        if callable(handler):\n            handler()\n","\n")

# 3) Enrich _refresh_assets to prefer team JSON for vehicles/equipment
s=re.sub(r"def _refresh_assets\(self\) -> None:[\s\S]*?@Slot\(int\)\s*def _on_assets_changed",
'''def _refresh_assets(self) -> None:
        try:
            tid = int(self._team.team_id) if self._team.team_id is not None else None
            if not tid:
                self._personnel = []
                self._vehicles = []
                self._equipment = []
                self._aircraft = []
                return
            # Personnel from members_json (see earlier enrichment)
            members_ids: list[int] = []
            try:
                members_ids = [int(x) for x in (self._team.members or [])]
            except Exception:
                members_ids = []
            people: list[dict[str, Any]] = []
            if members_ids:
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
                        try:
                            from modules.logistics.checkin import repository as ci_repo
                            ident = ci_repo.get_person_identity(str(pid))
                        except Exception:
                            ident = None
                        if ident:
                            base = {
                                'id': int(pid), 'name': getattr(ident,'name',''),
                                'role': getattr(ident,'primary_role', None), 'phone': getattr(ident,'phone', None),
                                'callsign': getattr(ident,'callsign', None), 'identifier': getattr(ident,'callsign', None) or None,
                                'rank': None, 'organization': getattr(ident,'home_unit', None), 'is_medic': None,
                            }
                    if base is None:
                        base = {'id': int(pid), 'name': f'Personnel {pid}', 'role': None, 'phone': None, 'callsign': None, 'identifier': None, 'rank': None, 'organization': None, 'is_medic': None}
                    people.append(base)
                self._personnel = people
            else:
                self._personnel = fetch_team_personnel(tid)
            # Vehicles from team JSON when present
            veh_ids = [str(v) for v in (getattr(self._team,'vehicles',[]) or [])]
            if veh_ids:
                try:
                    from models.queries import list_incident_vehicles
                    allv = list_incident_vehicles()
                    by_id = {str(r.get('id')): r for r in allv}
                    rows = []
                    for vid in veh_ids:
                        r = by_id.get(str(vid)) or {'id': vid, 'name': f'Vehicle {vid}', 'callsign': '', 'type': ''}
                        rows.append({'id': r.get('id'), 'name': r.get('name'), 'callsign': r.get('callsign'), 'type': r.get('type')})
                    self._vehicles = rows
                except Exception:
                    self._vehicles = fetch_team_vehicles(tid)
            else:
                self._vehicles = fetch_team_vehicles(tid)
            # Equipment from team JSON when present
            eq_ids = [str(e) for e in (getattr(self._team,'equipment',[]) or [])]
            if eq_ids:
                try:
                    from models.queries import list_incident_equipment
                    alle = list_incident_equipment()
                    by_id = {str(r.get('id')): r for r in alle}
                    rows = []
                    for eid in eq_ids:
                        r = by_id.get(str(eid)) or {'id': eid, 'name': f'Equipment {eid}', 'type': ''}
                        rows.append({'id': r.get('id'), 'name': r.get('name'), 'type': r.get('type'), 'serial': r.get('serial')})
                    self._equipment = rows
                except Exception:
                    self._equipment = fetch_team_equipment(tid)
            else:
                self._equipment = fetch_team_equipment(tid)
            # Aircraft unchanged
            self._aircraft = fetch_team_aircraft(tid)
        except Exception:
            pass

    @Slot(int)
    def _on_assets_changed''', s, flags=re.S)

io.open(r"modules/operations/teams/panels/team_detail_window.py","w",encoding="utf-8",newline="").write(s)
print('ADD_VEH_EQUIP_DBLCLICK_AND_REFRESH_JSON')
