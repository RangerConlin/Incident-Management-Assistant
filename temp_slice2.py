                    "callsign": r.get("callsign"),
                    "name": r.get("name"),
                    "rank": r.get("rank"),
                    "organization": r.get("organization"),
                    "role": r.get("role"),
                    "phone": r.get("phone"),
                    "isLeader": (lid is not None and int(r.get("id")) == lid),
                    "isMedic": bool(r.get("is_medic")),
                }
            )
        return out

    @Slot(result='QVariant')
    def aircrewMembers(self) -> list[dict]:
        # For AIR teams show same people, flag PIC as leader and leave certs blank
        out: list[dict[str, Any]] = []
        lid = int(self._team.team_leader_id) if self._team.team_leader_id is not None else None
        for r in self._personnel:
            identifier = r.get("identifier") or r.get("callsign")
            out.append(
                {
                    "id": r.get("id"),
                    "identifier": identifier,
                    "callsign": r.get("callsign"),
                    "name": r.get("name"),
                    "rank": r.get("rank"),
                    "organization": r.get("organization"),
                    "role": r.get("role"),
                    "phone": r.get("phone"),
                    "certs": "",  # not modeled in incident db here
                    "isPIC": (lid is not None and int(r.get("id")) == lid),
                }
            )
        return out

    @Slot(result='QVariant')
    def vehicles(self) -> list[dict]:
        out: list[dict[str, Any]] = []
        for r in self._vehicles:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "callsign": r.get("callsign"),
                    "type": r.get("type"),
                    "driver": "",
                    "phone": "",
                }
            )
        return out

    @Slot(result='QVariant')
    def aircraft(self) -> list[dict]:
        out: list[dict[str, Any]] = []
        for r in self._aircraft:
            out.append(
                {
                    "id": r.get("id"),
                    "tail": r.get("tail_number"),
                    "tail_number": r.get("tail_number"),
                    "callsign": r.get("callsign"),
                    "type": r.get("type"),
                    "status": r.get("status"),
                    "base": "",
                    "comms": "",
                }
            )
        return out

    @Slot(result='QVariant')
    def availableMembers(self) -> list[dict]:
        try:
            return list_available_personnel() or []
        except Exception:
            return []

    @Slot(result='QVariant')
    def availableAircraft(self) -> list[dict]:
        """Return aircraft available for assignment; include current aircraft if any."""
        try:
            tid = int(self._team.team_id) if self._team.team_id is not None else None
            rows = list_available_aircraft(tid)
            # Normalize labels for QML display
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append({
                    "id": r.get("id"),
                    "callsign": r.get("callsign"),
                    "tail_number": r.get("tail_number"),
                    "status": r.get("status"),
                    "team_id": r.get("team_id"),
                })
            return out
        except Exception:
            return []

    @Slot(result='QVariant')
    def equipment(self) -> list[dict]:
        out: list[dict[str, Any]] = []
        for r in self._equipment:
            out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    # Provide additional fields for current QML layout
                    "qty": 1,
                    "notes": f"{r.get('type') or ''} {('('+str(r.get('serial'))+')') if r.get('serial') else ''}".strip(),
                }
            )
        return out

    @Slot(result='QVariant')
    def leaderOptions(self) -> list[dict]:
        try:
            return [
                {"id": r.get("id"), "name": r.get("name")}
                for r in (self._personnel or [])
            ]
        except Exception:
            return []
