import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";
import DataTable, { type ColumnDef } from "../../../components/table/DataTable";
import { useSession } from "../../../auth/SessionContext";
import ApprovalPanel from "../../../components/approvals/ApprovalPanel";
import type { IncidentChannel } from "../../../api/types";
import {
  CHANNEL_ENCRYPTION_OPTIONS,
  CHANNEL_PRIORITY_OPTIONS,
  useAddChannelFromMaster,
  useChannelsPlan,
  useCommunicationsPlan,
  useDeleteChannelPlanRow,
  useMasterChannels,
  useReorderChannelPlanRow,
  useSaveCommunicationsPlan,
  useUpdateChannelPlanRow,
} from "./hooks";

export default function CommsPlanPage() {
  const { incidentId } = useSession();
  const [opPeriodId, setOpPeriodId] = useState<string | null>(null);
  const [librarySearch, setLibrarySearch] = useState("");
  const [validation, setValidation] = useState<{ messages: { level: string; text: string }[] } | null>(null);

  const { data: periods = [] } = useQuery({
    queryKey: ["incident", incidentId, "operational_periods"],
    queryFn: () => api.listOperationalPeriods(incidentId!),
    enabled: Boolean(incidentId),
  });
  const { data: activePeriod } = useQuery({
    queryKey: ["incident", incidentId, "operational_periods", "active"],
    queryFn: () => api.getActiveOperationalPeriod(incidentId!),
    enabled: Boolean(incidentId),
  });

  useEffect(() => {
    if (opPeriodId === null && activePeriod) setOpPeriodId(String(activePeriod.id));
  }, [activePeriod, opPeriodId]);

  const { data: plan } = useCommunicationsPlan(incidentId!, opPeriodId);
  const savePlan = useSaveCommunicationsPlan(incidentId!);

  const { data: rows = [], isLoading } = useChannelsPlan(incidentId!);
  const { data: library = [] } = useMasterChannels(librarySearch);
  const addChannel = useAddChannelFromMaster(incidentId!);
  const updateRow = useUpdateChannelPlanRow(incidentId!);
  const deleteRow = useDeleteChannelPlanRow(incidentId!);
  const reorderRow = useReorderChannelPlanRow(incidentId!);

  const planChannelIds = useMemo(() => new Set(rows.map((r) => r.master_id)), [rows]);

  const runValidation = async () => {
    const result = await api.validateChannelsPlan(incidentId!);
    setValidation(result);
  };

  const columns: ColumnDef<IncidentChannel>[] = [
    { key: "channel", header: "Channel", sortable: true, sortValue: (r) => r.channel, defaultWidth: 150 },
    { key: "function", header: "Function", defaultWidth: 110, render: (r) => r.function ?? "—" },
    { key: "band", header: "Band", defaultWidth: 80, render: (r) => r.band ?? "—" },
    { key: "rx_freq", header: "RX", defaultWidth: 90, render: (r) => r.rx_freq ?? "—" },
    { key: "tx_freq", header: "TX", defaultWidth: 90, render: (r) => r.tx_freq ?? "—" },
    {
      key: "assignment",
      header: "Assignment (Div / Team)",
      defaultWidth: 200,
      render: (r) => (
        <div style={{ display: "flex", gap: 4 }}>
          <input
            style={{ width: "50%" }}
            defaultValue={r.assignment_division ?? ""}
            placeholder="Division"
            onBlur={(e) => updateRow.mutate({ rowId: r.id!, patch: { assignment_division: e.target.value } })}
          />
          <input
            style={{ width: "50%" }}
            defaultValue={r.assignment_team ?? ""}
            placeholder="Team"
            onBlur={(e) => updateRow.mutate({ rowId: r.id!, patch: { assignment_team: e.target.value } })}
          />
        </div>
      ),
    },
    {
      key: "priority",
      header: "Priority",
      defaultWidth: 110,
      render: (r) => (
        <select value={r.priority} onChange={(e) => updateRow.mutate({ rowId: r.id!, patch: { priority: e.target.value } })}>
          {CHANNEL_PRIORITY_OPTIONS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "encryption",
      header: "Encryption",
      defaultWidth: 110,
      render: (r) => (
        <select value={r.encryption} onChange={(e) => updateRow.mutate({ rowId: r.id!, patch: { encryption: e.target.value } })}>
          {CHANNEL_ENCRYPTION_OPTIONS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "remarks",
      header: "Remarks",
      defaultWidth: 180,
      render: (r) => (
        <input
          defaultValue={r.remarks ?? ""}
          onBlur={(e) => updateRow.mutate({ rowId: r.id!, patch: { remarks: e.target.value } })}
        />
      ),
    },
    {
      key: "row_actions",
      header: "",
      defaultWidth: 130,
      render: (r) => (
        <div style={{ display: "flex", gap: 4 }}>
          <button className="secondary" style={{ width: "auto" }} onClick={() => reorderRow.mutate({ rowId: r.id!, direction: "up" })}>
            ↑
          </button>
          <button className="secondary" style={{ width: "auto" }} onClick={() => reorderRow.mutate({ rowId: r.id!, direction: "down" })}>
            ↓
          </button>
          <button className="secondary" style={{ width: "auto" }} onClick={() => deleteRow.mutate(r.id!)}>
            Remove
          </button>
        </div>
      ),
    },
  ];

  if (!incidentId) return null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Communications Plan (ICS-205)</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select value={opPeriodId ?? ""} onChange={(e) => setOpPeriodId(e.target.value || null)}>
            <option value="">Unassigned</option>
            {periods.map((p) => (
              <option key={p.id} value={String(p.id)}>
                OP {p.number} — {p.name}
              </option>
            ))}
          </select>
          <button className="secondary" style={{ width: "auto" }} onClick={runValidation}>
            Validate
          </button>
        </div>
      </div>

      {validation && (
        <div style={{ marginBottom: 12 }}>
          {validation.messages.length === 0 ? (
            <p style={{ opacity: 0.7 }}>No conflicts or warnings.</p>
          ) : (
            validation.messages.map((m, i) => (
              <p key={i} className={m.level === "conflict" ? "error" : undefined} style={{ margin: "2px 0" }}>
                {m.level === "conflict" ? "⚠" : "•"} {m.text}
              </p>
            ))
          )}
        </div>
      )}

      <div className="field" style={{ marginBottom: 16 }}>
        <label>Special Instructions</label>
        <textarea
          defaultValue={plan?.special_instructions ?? ""}
          key={plan?.plan_id}
          onBlur={(e) =>
            savePlan.mutate({ op_period_id: opPeriodId, special_instructions: e.target.value, notes: plan?.notes ?? "" })
          }
        />
      </div>

      <ApprovalPanel
        incidentId={incidentId}
        entityType="ics_205"
        entityId={plan?.plan_id ?? null}
        startLabel="Submit for Approval (Communications Unit Leader)"
      />

      <div style={{ display: "flex", gap: 24 }}>
        <div style={{ flex: 1 }}>
          <h3>Active Plan</h3>
          {isLoading ? (
            <p>Loading…</p>
          ) : (
            <DataTable
              tableId="comms-channels-plan"
              columns={columns}
              rows={rows}
              rowKey={(r) => r.channel_id}
              emptyMessage="No channels on this plan yet. Add one from the library."
            />
          )}
        </div>

        <div style={{ width: 300 }}>
          <h3>Channel Library</h3>
          <input
            placeholder="Search channels…"
            value={librarySearch}
            onChange={(e) => setLibrarySearch(e.target.value)}
            style={{ marginBottom: 8 }}
          />
          {library.map((ch) => {
            const already = ch.id != null && planChannelIds.has(String(ch.id));
            return (
              <div key={ch.id} className="list-item" style={{ cursor: "default" }}>
                <div>
                  <div style={{ fontWeight: 600 }}>{ch.display_name}</div>
                  <div style={{ fontSize: "0.85rem", opacity: 0.7 }}>
                    {ch.function} · {ch.rx_freq} {ch.band}
                  </div>
                </div>
                <button
                  className={already ? "secondary" : undefined}
                  style={{ width: "auto" }}
                  disabled={already || ch.id == null || addChannel.isPending}
                  onClick={() => ch.id != null && addChannel.mutate({ masterId: ch.id })}
                >
                  {already ? "Added" : "Add"}
                </button>
              </div>
            );
          })}
          {library.length === 0 && <p style={{ opacity: 0.6 }}>No matches.</p>}
        </div>
      </div>
    </div>
  );
}
