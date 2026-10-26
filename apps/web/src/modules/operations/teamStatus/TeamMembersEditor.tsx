import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";
import type { CheckinRosterRow } from "../../../api/types";

interface Props {
  incidentId: string;
  memberIds: number[];
  leaderId: number | string | null | undefined;
  onSave: (next: { member_person_records: number[]; leader_person_record: number | null }) => void;
}

// Team personnel are tracked as master-personnel IDs (`member_person_records`)
// — the shared API rejects a plain members_json string array (HTTP 422, "Use
// member_person_records for team personnel"). Crucially, the board's Team
// Leader column resolves a name via the INCIDENT's own check-in roster
// (incident_personnel, populated by the Check-In save flow), not the master
// personnel catalog — the same way desktop's Add Personnel dialog only lists
// people from the check-in roster (ci_repo.fetch_roster), never the master
// catalog directly. Searching master personnel here (as an earlier version
// of this component did) let you add/lead with someone who was never
// checked into this incident, and the board would then have nothing to
// resolve their name from and render the Leader column blank.
export default function TeamMembersEditor({ incidentId, memberIds, leaderId, onSave }: Props) {
  const roster = useQuery({
    queryKey: ["incident", incidentId, "checkin_roster"],
    queryFn: () => api.fetchCheckinRoster(incidentId),
    refetchInterval: 20_000,
  });
  const byId = useMemo(() => {
    const map = new Map<number, CheckinRosterRow>();
    for (const r of roster.data ?? []) map.set(r.person_record, r);
    return map;
  }, [roster.data]);

  const leaderNum = leaderId == null ? null : Number(leaderId);
  const available = (roster.data ?? []).filter((p) => !memberIds.includes(p.person_record));

  const addMember = (id: number) => {
    if (memberIds.includes(id)) return;
    onSave({ member_person_records: [...memberIds, id], leader_person_record: leaderNum });
  };
  const removeMember = (id: number) => {
    onSave({
      member_person_records: memberIds.filter((m) => m !== id),
      leader_person_record: leaderNum === id ? null : leaderNum,
    });
  };
  const setLeader = (id: number) => onSave({ member_person_records: memberIds, leader_person_record: id });

  return (
    <div>
      {roster.isPending && <p style={{ opacity: 0.6 }}>Loading incident roster…</p>}
      {roster.isError && <p className="error">Could not load the check-in roster.</p>}
      {memberIds.length === 0 && <p style={{ opacity: 0.6 }}>No personnel assigned.</p>}
      {memberIds.map((id) => {
        const person = byId.get(id);
        const isLeader = leaderNum === id;
        return (
          <div key={id} className="list-item">
            <span>
              {person ? `${person.name} (${person.person_id})` : `Person #${id} — not on this incident's check-in roster`}
              {isLeader && " — Leader"}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              {!isLeader && (
                <button className="secondary" style={{ width: "auto" }} onClick={() => setLeader(id)}>
                  Set as Leader
                </button>
              )}
              <button className="danger" style={{ width: "auto" }} onClick={() => removeMember(id)}>
                Remove
              </button>
            </div>
          </div>
        );
      })}

      <h4 style={{ marginTop: 16 }}>Add from check-in roster</h4>
      {!roster.isPending && available.length === 0 && (
        <p style={{ opacity: 0.6 }}>
          Everyone on this incident's check-in roster is already assigned, or no one has checked in yet.
        </p>
      )}
      {available.map((p) => (
        <div key={p.person_record} className="list-item">
          <span>
            {p.name} ({p.person_id}){p.role ? ` — ${p.role}` : ""}
            {p.checked_in ? "" : " (not checked in)"}
          </span>
          <button style={{ width: "auto" }} onClick={() => addMember(p.person_record)}>
            Add
          </button>
        </div>
      ))}
    </div>
  );
}
