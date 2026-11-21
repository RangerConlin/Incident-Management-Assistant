import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import "../logistics.css";
import * as api from "../../../api/endpoints";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import StatusPill from "../../../components/table/StatusPill";
import type {
  CheckinRosterRow,
  CheckinTeamRow,
  MasterAircraft,
  MasterEquipment,
  MasterPersonnelSummary,
  MasterVehicle,
} from "../../../api/types";
import { useSession } from "../../../auth/SessionContext";
import { useCheckInResource } from "../resourceStatus/hooks";
import {
  PERSONNEL_STATUS_OPTIONS,
  useCheckinRoster,
  useCheckinTeams,
  useCreateMasterRecord,
  useSaveCheckin,
  useSetCheckinStatus,
  useSetResourceStatusByEntity,
  useSetTeamPlanningStatus,
  useTeamCheckIn,
  useTeamDisband,
} from "./hooks";

type ResourceKind = "vehicle" | "aircraft" | "equipment";

const RESOURCE_KIND_TABS: { key: ResourceKind; label: string }[] = [
  { key: "vehicle", label: "Vehicles" },
  { key: "aircraft", label: "Aircraft" },
  { key: "equipment", label: "Equipment" },
];

const STATUS_ACTIONS: { status: string; label: string; danger?: boolean }[] = [
  { status: "Enroute", label: "Mark Enroute" },
  { status: "Preparing for Demobilization", label: "Prep Demob" },
  { status: "Cancelled", label: "Mark Cancelled", danger: true },
];

export default function CheckInPage() {
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"personnel" | "teams" | ResourceKind>("personnel");

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
        <button className={`detail-tab ${tab === "teams" ? "active" : ""}`} onClick={() => setTab("teams")}>
          Groups / Teams
        </button>
        {RESOURCE_KIND_TABS.map((t) => (
          <button key={t.key} className={`detail-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "personnel" ? (
        <PersonnelCheckIn incidentId={incidentId} />
      ) : tab === "teams" ? (
        <TeamsCheckIn incidentId={incidentId} />
      ) : (
        <ResourceCheckIn incidentId={incidentId} kind={tab} />
      )}
    </div>
  );
}

function PersonnelCheckIn({ incidentId }: { incidentId: string }) {
  const [search, setSearch] = useState("");
  const [scannerMode, setScannerMode] = useState(false);
  const [reportingLocation, setReportingLocation] = useState("");
  const [selected, setSelected] = useState<MasterPersonnelSummary | CheckinRosterRow | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const { data: roster = [], isLoading } = useCheckinRoster(incidentId, { q: search });
  const { data: searchResults = [] } = useQuery({
    queryKey: ["incident", incidentId, "checkin-personnel-search", search],
    queryFn: () => api.searchCheckinPersonnel(incidentId, search),
    enabled: search.trim().length > 0,
  });
  const setStatus = useSetCheckinStatus(incidentId);
  const saveCheckinMutation = useSaveCheckin(incidentId);
  const setPlanningStatus = useSetResourceStatusByEntity(incidentId);
  const createPersonnel = useCreateMasterRecord("personnel");

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
      <div className="logistics-toolbar">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key !== "Enter" || !scannerMode) return;
            e.preventDefault();
            const term = search.trim().toLowerCase();
            if (!term) return;
            const match =
              notYetCheckedIn.find((p) => p.person_id?.toLowerCase() === term) ??
              (notYetCheckedIn.length === 1 ? notYetCheckedIn[0] : undefined);
            if (!match) return;
            saveCheckinMutation.mutate(
              { personRecord: match.person_record, body: { status: "Checked In", location: reportingLocation || "ICP" } },
              { onSuccess: () => setSearch("") }
            );
          }}
          placeholder="Scan badge/QR, or type name, ID, or callsign…"
          style={{ width: 260 }}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.82rem", whiteSpace: "nowrap" }}>
          <input type="checkbox" checked={scannerMode} onChange={(e) => setScannerMode(e.target.checked)} /> Scanner Mode
        </label>
        <input
          placeholder="Reporting location — e.g. ICP, Staging Area B"
          value={reportingLocation}
          onChange={(e) => setReportingLocation(e.target.value)}
          style={{ width: 240 }}
        />
        <button className="ghost" style={{ marginLeft: "auto" }} onClick={() => setShowAdd(true)}>
          + Add New Personnel Record
        </button>
      </div>
      <div className="hint">A badge/QR scan types straight into the search box like a keyboard — no separate scanner UI needed.</div>

      {search.trim() && notYetCheckedIn.length > 0 && (
        <>
          <h3 className="pm-section-label">Not Yet Checked In</h3>
          <table className="logistics-approvals-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Person ID</th>
                <th>Role</th>
                <th style={{ width: 110 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {notYetCheckedIn.map((p: MasterPersonnelSummary) => (
                <tr key={p.person_record}>
                  <td style={{ fontWeight: 600 }}>{p.name}</td>
                  <td>{p.person_id}</td>
                  <td>{p.primary_role ?? "—"}</td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="secondary" style={{ width: "auto" }} onClick={() => setSelected(p)}>
                        Select
                      </button>
                      <button
                        style={{ width: "auto" }}
                        disabled={saveCheckinMutation.isPending}
                        onClick={() =>
                          saveCheckinMutation.mutate(
                            {
                              personRecord: p.person_record,
                              body: { status: "Checked In", location: reportingLocation || "ICP" },
                            },
                            { onSuccess: () => setSearch("") }
                          )
                        }
                      >
                        Check In
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <div className="logistics-toolbar">
        <span className="muted">{selected ? `Selected: ${selected.name}` : "Select a person below to apply a status."}</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {STATUS_ACTIONS.map((a) => (
            <button
              key={a.status}
              className={a.danger ? "danger" : "secondary"}
              disabled={!selected || setPlanningStatus.isPending}
              onClick={() => {
                if (!selected) return;
                const personRecord = "person_record" in selected ? selected.person_record : null;
                if (personRecord == null) return;
                setPlanningStatus.mutate({ entityType: "personnel", recordId: personRecord, status: a.status });
              }}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>

      {showAdd && (
        <AddRecordDialog
          kind="personnel"
          onClose={() => setShowAdd(false)}
          onCreate={(body) => createPersonnel.mutate(body, { onSuccess: () => setShowAdd(false) })}
          pending={createPersonnel.isPending}
          error={createPersonnel.error instanceof Error ? createPersonnel.error.message : null}
        />
      )}

      <h3 className="pm-section-label">Roster</h3>
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable
          tableId="checkin-personnel-roster"
          columns={columns}
          rows={roster}
          rowKey={(r) => r.person_record}
          onRowClick={(r) => setSelected(r)}
          emptyMessage="No one checked in yet. Search above to check someone in."
        />
      )}
    </div>
  );
}

function ResourceCheckIn({ incidentId, kind }: { incidentId: string; kind: ResourceKind }) {
  const [search, setSearch] = useState("");
  const [reportingLocation, setReportingLocation] = useState("");
  const [selectedId, setSelectedId] = useState<string>("");
  const [showAdd, setShowAdd] = useState(false);
  const checkIn = useCheckInResource(incidentId);
  const setStatus = useSetResourceStatusByEntity(incidentId);
  const createRecord = useCreateMasterRecord(kind);

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
      <div className="logistics-toolbar">
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={`Scan asset tag, or search the ${kind} catalog…`} style={{ width: 300 }} />
        <input
          placeholder="Reporting location — e.g. Staging Area B"
          value={reportingLocation}
          onChange={(e) => setReportingLocation(e.target.value)}
          style={{ width: 240 }}
        />
        <button className="ghost" style={{ marginLeft: "auto" }} onClick={() => setShowAdd(true)}>
          + Add New {kind === "vehicle" ? "Vehicle" : kind === "aircraft" ? "Aircraft" : "Equipment"} Record
        </button>
      </div>

      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <table className="logistics-approvals-table">
          <thead>
            <tr>
              <th>Record</th>
              <th style={{ width: 150 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {results.length === 0 && (
              <tr>
                <td colSpan={2} className="muted">
                  No matches.
                </td>
              </tr>
            )}
            {results.map((item) => {
              const recordId = recordIdOf(item);
              const already = checkedInIds.has(recordId);
              return (
                <tr key={recordId}>
                  <td style={{ fontWeight: 600 }}>{labelOf(item)}</td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className={selectedId === recordId ? undefined : "secondary"} style={{ width: "auto" }} onClick={() => setSelectedId(recordId)}>
                        {selectedId === recordId ? "Selected" : "Select"}
                      </button>
                      <button
                        className={already ? "secondary" : undefined}
                        style={{ width: "auto" }}
                        disabled={already || checkIn.isPending}
                        onClick={() =>
                          checkIn.mutate({
                            resourceType: kind,
                            recordId,
                            overrides: reportingLocation ? { location: reportingLocation } : undefined,
                          })
                        }
                      >
                        {already ? "Checked In" : "Check In"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      <div className="logistics-toolbar">
        <span className="muted">{selectedId ? `Selected record: ${selectedId}` : "Select a record above to apply a status."}</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
          {STATUS_ACTIONS.map((a) => (
            <button
              key={a.status}
              className={a.danger ? "danger" : "secondary"}
              disabled={!selectedId || setStatus.isPending}
              onClick={() => setStatus.mutate({ entityType: kind, recordId: selectedId, status: a.status })}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
      {setStatus.isError && (
        <p className="error" role="alert">
          {(setStatus.error as Error).message}
        </p>
      )}

      {showAdd && (
        <AddRecordDialog
          kind={kind}
          onClose={() => setShowAdd(false)}
          onCreate={(body) => createRecord.mutate(body, { onSuccess: () => setShowAdd(false) })}
          pending={createRecord.isPending}
          error={createRecord.error instanceof Error ? createRecord.error.message : null}
        />
      )}
    </div>
  );
}

const ADD_FIELDS: Record<string, { name: string; label: string; required?: boolean }[]> = {
  personnel: [
    { name: "name", label: "Name", required: true },
    { name: "person_id", label: "ID / Local ID" },
    { name: "phone", label: "Phone" },
    { name: "role", label: "Role" },
  ],
  vehicle: [
    { name: "vehicle_id", label: "Vehicle ID", required: true },
    { name: "make", label: "Make" },
    { name: "model", label: "Model" },
    { name: "license_plate", label: "License Plate" },
  ],
  aircraft: [
    { name: "aircraft_id", label: "Tail Number", required: true },
    { name: "type", label: "Type", required: true },
    { name: "callsign", label: "Callsign" },
    { name: "base", label: "Base Location" },
  ],
  equipment: [
    { name: "name", label: "Name", required: true },
    { name: "equipment_id", label: "Equipment ID" },
    { name: "type", label: "Type" },
    { name: "serial_number", label: "Serial Number" },
  ],
};

function AddRecordDialog({
  kind,
  onClose,
  onCreate,
  pending,
  error,
}: {
  kind: "personnel" | "vehicle" | "aircraft" | "equipment";
  onClose: () => void;
  onCreate: (body: Record<string, string>) => void;
  pending: boolean;
  error: string | null;
}) {
  const fields = ADD_FIELDS[kind];
  const [values, setValues] = useState<Record<string, string>>({});
  const missing = fields.filter((f) => f.required && !values[f.name]?.trim());

  return (
    <div className="modal-backdrop open">
      <div className="modal">
        <h3>Add New {kind === "personnel" ? "Personnel" : kind === "vehicle" ? "Vehicle" : kind === "aircraft" ? "Aircraft" : "Equipment"} Record</h3>
        {fields.map((f) => (
          <div className="field" key={f.name} style={{ marginBottom: 10 }}>
            <label>
              {f.label}
              {f.required ? " *" : ""}
            </label>
            <input
              value={values[f.name] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              style={{ width: "100%" }}
            />
          </div>
        ))}
        {error && <div className="error">{error}</div>}
        <div className="modal-actions">
          <button disabled={missing.length > 0 || pending} onClick={() => onCreate(values)}>
            Create
          </button>
          <button className="ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

function TeamsCheckIn({ incidentId }: { incidentId: string }) {
  const { data: teams = [], isLoading } = useCheckinTeams(incidentId, false);
  const [selectedTeamId, setSelectedTeamId] = useState<number | "">("");
  const [showConfirm, setShowConfirm] = useState(false);
  const setPlanning = useSetTeamPlanningStatus(incidentId);

  const selectedTeam = teams.find((t) => t.int_id === selectedTeamId) ?? null;

  return (
    <div>
      <div className="logistics-toolbar">
        <select
          style={{ minWidth: 220 }}
          value={selectedTeamId}
          onChange={(e) => setSelectedTeamId(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">{isLoading ? "Loading teams…" : "Select a team"}</option>
          {teams.map((t) => (
            <option key={t.int_id} value={t.int_id}>
              {t.name || `Team ${t.int_id}`}
            </option>
          ))}
        </select>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button disabled={!selectedTeam} onClick={() => setShowConfirm(true)}>
            Open Team Check-In Confirmation
          </button>
          <button
            className="secondary"
            disabled={!selectedTeam || setPlanning.isPending}
            onClick={() => selectedTeam && setPlanning.mutate({ teamId: selectedTeam.int_id, status: "Expected" })}
          >
            Mark Team Expected
          </button>
          <button
            className="secondary"
            disabled={!selectedTeam || setPlanning.isPending}
            onClick={() => selectedTeam && setPlanning.mutate({ teamId: selectedTeam.int_id, status: "Enroute" })}
          >
            Mark Team Enroute
          </button>
        </div>
      </div>

      <table className="logistics-approvals-table">
        <tbody>
          <tr>
            <td style={{ width: 140 }} className="muted">Team</td>
            <td>{selectedTeam ? selectedTeam.name || selectedTeam.int_id : <span className="muted">Select a team not yet checked in.</span>}</td>
          </tr>
          {selectedTeam && (
            <>
              <tr>
                <td className="muted">Checked In</td>
                <td>{selectedTeam.checked_in ? "Yes" : "No"}</td>
              </tr>
              <tr>
                <td className="muted">Disbanded</td>
                <td>{selectedTeam.disbanded ? "Yes" : "No"}</td>
              </tr>
              <tr>
                <td className="muted">Status</td>
                <td>{selectedTeam.status || "—"}</td>
              </tr>
            </>
          )}
        </tbody>
      </table>

      {showConfirm && selectedTeam && (
        <TeamCheckInConfirmDialog incidentId={incidentId} team={selectedTeam} onClose={() => setShowConfirm(false)} />
      )}
    </div>
  );
}

function TeamCheckInConfirmDialog({
  incidentId,
  team,
  onClose,
}: {
  incidentId: string;
  team: CheckinTeamRow;
  onClose: () => void;
}) {
  const teamCheckIn = useTeamCheckIn(incidentId);
  const teamDisband = useTeamDisband(incidentId);
  const members = team.member_person_records ?? [];
  const vehicles = team.vehicles_json ?? [];
  const equipment = team.equipment_json ?? [];
  const aircraft = team.aircraft_json ?? [];
  const pending = teamCheckIn.isPending || teamDisband.isPending;

  return (
    <div className="modal-backdrop open">
      <div className="modal" style={{ maxWidth: 560 }}>
        <h3>Team Check-In: {team.name || team.int_id}</h3>
        <div className="hint" style={{ marginBottom: 10 }}>
          Members: {members.length} · Vehicles: {vehicles.length} · Equipment: {equipment.length} · Aircraft: {aircraft.length}
        </div>
        <table className="team-roster">
          <thead>
            <tr>
              <th>Name / Asset</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            {members.map((id) => (
              <tr key={`p-${id}`}>
                <td>Person #{id}</td>
                <td>Personnel</td>
              </tr>
            ))}
            {vehicles.map((id, i) => (
              <tr key={`v-${i}`}>
                <td>Vehicle #{String(id)}</td>
                <td>Vehicle</td>
              </tr>
            ))}
            {equipment.map((id, i) => (
              <tr key={`e-${i}`}>
                <td>Equipment #{String(id)}</td>
                <td>Equipment</td>
              </tr>
            ))}
            {aircraft.map((id, i) => (
              <tr key={`a-${i}`}>
                <td>Aircraft #{String(id)}</td>
                <td>Aircraft</td>
              </tr>
            ))}
            {members.length + vehicles.length + equipment.length + aircraft.length === 0 && (
              <tr>
                <td colSpan={2} style={{ opacity: 0.6 }}>
                  No assigned resources on this team yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="modal-actions">
          <button
            disabled={pending}
            onClick={() => teamCheckIn.mutate({ teamId: team.int_id, keepTogether: true }, { onSuccess: onClose })}
          >
            Check In as Team
          </button>
          <button
            className="secondary"
            disabled={pending}
            onClick={() =>
              teamCheckIn.mutate(
                { teamId: team.int_id, keepTogether: false },
                {
                  onSuccess: () => teamDisband.mutate({ teamId: team.int_id }, { onSuccess: onClose }),
                }
              )
            }
          >
            Resources to Staging
          </button>
          <button className="ghost" onClick={onClose} disabled={pending}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
