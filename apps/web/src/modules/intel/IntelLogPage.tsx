import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { useSession } from "../../auth/SessionContext";
import { formatDateTime } from "../../utils/formatDateTime";
import { useIntelLog } from "./hooks";
import type { IntelLogEntry } from "../../api/types";

// Matches desktop's modules/intel/tabs/log_tab.py (IntelLogTab):
// chronological, row-tinted by entity type, with Entity/Event filters. The
// double-click-to-open-record interaction maps each entity_type to its own
// detail route below instead of desktop's single navigate_to_record signal.
const ENTITY_TYPES = ["Subject", "Lead", "Intel Item", "Assessment", "Observation", "Attachment", "Report", "Form"];
const ENTITY_TYPE_TO_FILTER_VALUE: Record<string, string> = {
  Subject: "subject",
  Lead: "lead",
  "Intel Item": "item",
  Assessment: "assessment",
  Observation: "observation",
  Attachment: "attachment",
  Report: "report",
  Form: "form",
};

function detailPath(entry: IntelLogEntry): string | null {
  switch (entry.entity_type) {
    case "subject":
      return `/intel/subjects/${entry.entity_id}`;
    case "lead":
      return `/intel/leads/${entry.entity_id}`;
    case "item":
    case "observation":
      // An observation's entity_id is its parent item's id, matching
      // desktop's navigate_to_record("observation", item_id) handling.
      return `/intel/items/${entry.entity_id}`;
    case "assessment":
      return `/intel/assessments/${entry.entity_id}`;
    default:
      return null;
  }
}

export default function IntelLogPage() {
  const { incidentId } = useSession();
  const [entityFilter, setEntityFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");

  const { data: entries = [], isLoading, error } = useIntelLog(incidentId!, {
    entity_type: entityFilter || undefined,
    event_type: eventFilter || undefined,
    limit: 200,
  });

  const eventTypes = useMemo(() => Array.from(new Set(entries.map((e) => e.event_type))).sort(), [entries]);

  if (!incidentId) return null;

  return (
    <div>
      <h2>Intel Log</h2>

      <div style={{ display: "flex", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <select value={entityFilter} onChange={(e) => setEntityFilter(e.target.value)}>
          <option value="">All entities</option>
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={ENTITY_TYPE_TO_FILTER_VALUE[t]}>
              {t}
            </option>
          ))}
        </select>
        <select value={eventFilter} onChange={(e) => setEventFilter(e.target.value)}>
          <option value="">All events</option>
          {eventTypes.map((t) => (
            <option key={t} value={t}>
              {t.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="error">Could not load the Intel log.</p>}
      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <DataTable<IntelLogEntry>
          tableId="intel-log"
          columns={
            [
              { key: "timestamp", header: "Time", render: (e) => formatDateTime(e.timestamp), defaultWidth: 150 },
              { key: "entity_type", header: "Entity", render: (e) => e.entity_type, defaultWidth: 110 },
              { key: "event_type", header: "Event", render: (e) => e.event_type.replace(/_/g, " "), defaultWidth: 140 },
              {
                key: "summary",
                header: "Summary",
                render: (e) => {
                  const path = detailPath(e);
                  return path ? (
                    <>
                      {e.summary} — <Link to={path}>view</Link>
                    </>
                  ) : (
                    e.summary
                  );
                },
                defaultWidth: 380,
              },
              { key: "actor", header: "Actor", render: (e) => e.actor || "—", defaultWidth: 130 },
            ] as ColumnDef<IntelLogEntry>[]
          }
          rows={entries}
          rowKey={(e) => e.id}
          emptyMessage="No log entries yet."
        />
      )}
    </div>
  );
}
