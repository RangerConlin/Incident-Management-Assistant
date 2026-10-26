import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import * as api from "../../../api/endpoints";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import StatusPill from "../../../components/table/StatusPill";
import type { CheckinRosterRow, MasterAircraft, MasterEquipment, MasterPersonnelSummary, MasterVehicle } from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { useCheckInResource } from "../resourceStatus/hooks";
import { PERSONNEL_STATUS_OPTIONS, useCheckinRoster, useSaveCheckin, useSetCheckinStatus } from "./hooks";

type ResourceKind = "vehicle" | "aircraft" | "equipment";

const RESOURCE_KIND_TABS: { key: ResourceKind; label: string }[] = [
  { key: "vehicle", label: "Vehicles" },
  { key: "aircraft", label: "Aircraft" },
  { key: "equipment", label: "Equipment" },
];

export default function CheckInPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"personnel" | ResourceKind>("personnel");

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Check-In</h2>
        <button className="secondary" style={{ width: "auto" }} onClick={() => navigate("/logistics/resources")}>
          Resource Status Board
        </button>
      </div>

      <div className="detail-tabs">
        <button className={`detail-tab ${tab === "personnel" ? "active" : ""}`} onClick={() => setTab("personnel")}>
          Personnel
        </button>
        {RESOURCE_KIND_TABS.map((t) => (
          <button key={t.key} className={`detail-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "personnel" ? (
        <PersonnelCheckIn incidentId={incidentId} />
      ) : (
        <ResourceCheckIn incidentId={incidentId} kind={tab} />
      )}
    </div>
  );
}

function PersonnelCheckIn({ incidentId }: { incidentId: string }) {
  const [search, setSearch] = useState("");
  const { data: roster = [], isLoading } = useCheckinRoster(incidentId, { q: search });
  const { data: searchResults = [] } = useQuery({
    queryKey: ["incident", incidentId, "checkin-personnel-search", search],
    queryFn: () => api.searchCheckinPersonnel(incidentId, search),
    enabled: search.trim().length > 0,
  });
  const setStatus = useSetCheckinStatus(incidentId);
  const saveCheckinMutation = useSaveCheckin(incidentId);

  const rosterRecords = new Set(roster.map((r) => r.person_record));
  const notYetCheckedIn = searchResults.filter((p) => !rosterRecords.has(p.person_record));

  const columns: ColumnDef<CheckinRosterRow>[] = [
    { key: "name", header: "Name", sortable: true, sortValue: (r) => r.name, defaultWidth: 180 },
    { key: "person_id", header: "Person ID", defaultWidth: 110 },
    { key: "role", header: "Role", defaultWidth: 130, render: (r) => r.role ?? "—" },
    { key: "team", header: "Team", defaultWidth: 130 },
    {
      key: "status",
      header: "Status",
      sortable: true,
      sortValue: (r) => r.status,
      render: (r) => <StatusPill domain="resource" statusKey={r.status} />,
      defaultWidth: 150,
    },
    { key: "phone", header: "Phone", defaultWidth: 130 },
    {
      key: "actions",
      header: "Set Status",
      defaultWidth: 180,
      render: (r) => (
        <select
          value=""
          onChange={(e) => {
            if (!e.target.value) return;
            setStatus.mutate({ personRecord: r.person_record, status: e.target.value });
          }}
        >
          <option value="">Change status…</option>
          {PERSONNEL_STATUS_OPTIONS.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
      ),
    },
  ];

  return (
    <div>
      <div className="field" style={{ maxWidth: 360, marginBottom: 16 }}>
        <label>Search personnel by name, ID, or callsign</label>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…" />
      </div>

      {search.trim() && notYetCheckedIn.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <h3>Not Yet Checked In</h3>
          {notYetCheckedIn.map((p: MasterPersonnelSummary) => (
            <div key={p.person_record} className="list-item" style={{ cursor: "default" }}>
              <div>
                <div style={{ fontWeight: 600 }}>{p.name}</div>
                <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                  {p.person_id} · {p.primary_role ?? "—"}
                </div>
              </div>
              <button
                style={{ width: "auto" }}
                disabled={saveCheckinMutation.isPending}
                onClick={() =>
                  saveCheckinMutation.mutate({
                    personRecord: p.person_record,
                    body: { status: "Checked In", location: "ICP" },
                  })
                }
              >
                Check In
              </button>
            </div>
          ))}
        </div>
      )}

      <h3>Roster</h3>
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="checkin-personnel-roster"
          columns={columns}
          rows={roster}
          rowKey={(r) => r.person_record}
          emptyMessage="No one checked in yet. Search above to check someone in."
        />
      )}
    </div>
  );
}

function ResourceCheckIn({ incidentId, kind }: { incidentId: string; kind: ResourceKind }) {
  const [search, setSearch] = useState("");
  const checkIn = useCheckInResource(incidentId);

  const { data: results = [], isLoading } = useQuery<(MasterVehicle | MasterAircraft | MasterEquipment)[]>({
    queryKey: ["master", kind, "search", search],
    queryFn: async () => {
      if (kind === "vehicle") return api.searchMasterVehicles(search);
      if (kind === "aircraft") return api.searchMasterAircraft(search);
      return api.searchMasterEquipment(search);
    },
  });

  const { data: checkedIn = [] } = useQuery({
    queryKey: ["incident", incidentId, "resource_status", kind],
    queryFn: () => api.listResourceStatus(incidentId, kind),
  });
  const checkedInIds = new Set(checkedIn.map((r) => String(r.record_id)));

  const recordIdOf = (item: MasterVehicle | MasterAircraft | MasterEquipment): string => {
    if ("vehicle_record" in item) return String(item.vehicle_record);
    if ("aircraft_record" in item) return String(item.aircraft_record);
    return String(item.equipment_record);
  };

  const labelOf = (item: MasterVehicle | MasterAircraft | MasterEquipment): string => {
    if ("vehicle_record" in item) return item.vehicle_id || `${item.make} ${item.model}`.trim();
    if ("aircraft_record" in item) return item.callsign || item.tail_number || item.aircraft_id;
    return item.name || item.equipment_id;
  };

  return (
    <div>
      <div className="field" style={{ maxWidth: 360, marginBottom: 16 }}>
        <label>Search {kind} catalog</label>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…" />
      </div>

      {isLoading ? (
        <p>Loading…</p>
      ) : results.length === 0 ? (
        <p style={{ opacity: 0.6 }}>No matches.</p>
      ) : (
        results.map((item) => {
          const recordId = recordIdOf(item);
          const already = checkedInIds.has(recordId);
          return (
            <div key={recordId} className="list-item" style={{ cursor: "default" }}>

              <div style={{ fontWeight: 600 }}>{labelOf(item)}</div>
              <button
                className={already ? "secondary" : undefined}
                style={{ width: "auto" }}
                disabled={already || checkIn.isPending}
                onClick={() => checkIn.mutate({ resourceType: kind, recordId })}
              >
                {already ? "Checked In" : "Check In"}
              </button>
            </div>
          );
        })
      )}
    </div>
  );
}
