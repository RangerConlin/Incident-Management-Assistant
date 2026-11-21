import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";
import type { CheckinRosterRow, MasterPersonnelSummary } from "../../../api/types";

interface Props {
  incidentId: string;
  memberIds: number[];
  leaderId: number | string | null | undefined;
  onSave: (next: { member_person_records: number[]; leader_person_record: number | null }) => void;
}

// Team personnel are tracked as master-personnel IDs (`member_person_records`)
// — the shared API rejects a plain members_json string array (HTTP 422, "Use
// member_person_records for team personnel"). The board's Team Leader column
// resolves a name via the INCIDENT's own check-in roster (incident_personnel),
// not the master personnel catalog directly, so a catalog pick that has never
// touched this incident is registered into the roster first (status
// "Pending", the same shape the Check-In save flow writes) before being
// added as a member — otherwise the board has nothing to resolve their name
// from and the Leader column renders blank.
export default function TeamMembersEditor({ incidentId, memberIds, leaderId, onSave }: Props) {
  const queryClient = useQueryClient();
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

  const [catalogSearch, setCatalogSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(catalogSearch.trim()), 300);
    return () => clearTimeout(handle);
  }, [catalogSearch]);

  const catalogResults = useQuery({
    queryKey: ["master", "personnel", "search", debouncedSearch],
    queryFn: () => api.searchPersonnel(debouncedSearch),
    enabled: debouncedSearch.length > 0,
  });

  const registerAndAdd = useMutation({
    mutationFn: async (person: MasterPersonnelSummary) => {
      if (!byId.has(person.person_record)) {
        await api.saveCheckin(incidentId, person.person_record, { status: "Pending" });
      }
      return person;
    },
    onSuccess: (person) => {
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId, "checkin_roster"] });
      addMember(person.person_record);
    },
  });

  const leaderNum = leaderId == null ? null : Number(leaderId);
  const available = (roster.data ?? []).filter((p) => !memberIds.includes(p.person_record));
  const catalogAvailable = (catalogResults.data ?? []).filter((p) => !memberIds.includes(p.person_record));

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

      <h4 style={{ marginTop: 16 }}>Add from personnel catalog</h4>
      <input
        placeholder="Search all personnel…"
        value={catalogSearch}
        onChange={(e) => setCatalogSearch(e.target.value)}
      />
      {debouncedSearch && catalogResults.isFetching && <p style={{ opacity: 0.6 }}>Searching…</p>}
      {debouncedSearch && !catalogResults.isFetching && catalogAvailable.length === 0 && (
        <p style={{ opacity: 0.6 }}>No matching personnel.</p>
      )}
      {catalogAvailable.map((p) => {
        const onRoster = byId.has(p.person_record);
        return (
          <div key={p.person_record} className="list-item">
            <span>
              {p.name} ({p.person_id}){p.primary_role ? ` — ${p.primary_role}` : ""}
              {onRoster ? "" : " (not on this incident)"}
            </span>
            <button
              style={{ width: "auto" }}
              disabled={registerAndAdd.isPending}
              onClick={() => registerAndAdd.mutate(p)}
            >
              Add
            </button>
          </div>
        );
      })}
    </div>
  );
}
