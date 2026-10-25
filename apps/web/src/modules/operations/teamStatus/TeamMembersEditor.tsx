import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";
import { WORKSPACES } from "../../workspaces/config";
import type { RecordData } from "../../workspaces/config";

interface Props {
  memberIds: number[];
  leaderId: number | string | null | undefined;
  onSave: (next: { member_person_records: number[]; leader_person_record: number | null }) => void;
}

// Team personnel are tracked as master-personnel IDs (`member_person_records`)
// — the shared API rejects a plain members_json string array (HTTP 422, "Use
// member_person_records for team personnel"). This searches the same master
// roster the desktop client's Add Personnel dialog uses instead of free text.
export default function TeamMembersEditor({ memberIds, leaderId, onSave }: Props) {
  const [query, setQuery] = useState("");
  const rosterDataset = WORKSPACES.find((w) => w.path === "/personnel")!.datasets[0];
  const roster = useQuery({
    queryKey: ["master", "personnel", "roster-all"],
    queryFn: () => api.listWorkspaceRecords(rosterDataset, ""),
    refetchInterval: 20_000,
  });
  const search = useQuery({
    queryKey: ["master", "personnel", "search", query],
    queryFn: () => api.searchPersonnel(query),
    enabled: query.trim().length > 1,
  });
  const byId = useMemo(() => {
    const map = new Map<number, RecordData>();
    for (const r of roster.data ?? []) {
      if (r.person_record != null) map.set(Number(r.person_record), r);
    }
    return map;
  }, [roster.data]);

  const leaderNum = leaderId == null ? null : Number(leaderId);

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
      <div className="field" style={{ flexDirection: "row", gap: 8 }}>
        <input
          placeholder="Search personnel by name or ID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {query.trim().length > 1 && (
        <div>
          {search.isPending && <p style={{ opacity: 0.6 }}>Searching…</p>}
          {!search.isPending && (search.data ?? []).filter((p) => !memberIds.includes(p.person_record)).length === 0 && (
            <p style={{ opacity: 0.6 }}>No matching personnel.</p>
          )}
          {(search.data ?? [])
            .filter((p) => !memberIds.includes(p.person_record))
            .map((p) => (
              <div key={p.person_record} className="list-item">
                <span>
                  {p.name} ({p.person_id}){p.primary_role ? ` — ${p.primary_role}` : ""}
                </span>
                <button
                  style={{ width: "auto" }}
                  onClick={() => {
                    addMember(p.person_record);
                    setQuery("");
                  }}
                >
                  Add
                </button>
              </div>
            ))}
        </div>
      )}
      {memberIds.length === 0 && <p style={{ opacity: 0.6 }}>No personnel assigned.</p>}
      {memberIds.map((id) => {
        const person = byId.get(id);
        const isLeader = leaderNum === id;
        return (
          <div key={id} className="list-item">
            <span>
              {person ? `${String(person.name)} (${String(person.person_id ?? id)})` : `Person #${id}`}
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
    </div>
  );
}
