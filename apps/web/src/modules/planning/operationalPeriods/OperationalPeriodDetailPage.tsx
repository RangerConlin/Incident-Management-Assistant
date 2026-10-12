import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import StatusPill from "../../../components/table/StatusPill";
import * as api from "../../../api/endpoints";
import { useSession } from "../../../auth/SessionContext";
import { useSetActiveOperationalPeriod, useUpdateOperationalPeriod } from "./hooks";

export default function OperationalPeriodDetailPage() {
  const { periodId } = useParams();
  const { incidentId } = useSession();
  const navigate = useNavigate();
  const id = Number(periodId);

  const { data: period, isLoading, error } = useQuery({
    queryKey: ["incident", incidentId, "operational_periods", id],
    queryFn: () => api.getOperationalPeriod(incidentId!, id),
    enabled: Boolean(incidentId),
  });
  const updatePeriod = useUpdateOperationalPeriod(incidentId!);
  const setActive = useSetActiveOperationalPeriod(incidentId!);

  if (!incidentId) return null;
  if (isLoading) return <p>Loading operational period…</p>;
  if (error || !period) return <p className="error">Could not load this operational period.</p>;

  const save = (body: Record<string, unknown>) => updatePeriod.mutate({ periodId: id, body });

  return (
    <div className="detail-page">
      <button
        className="secondary"
        style={{ width: "auto", marginBottom: 12 }}
        onClick={() => navigate("/planning/operational-periods")}
      >
        ← Operational Periods
      </button>
      <h2>
        OP {period.number}
        {period.name ? ` — ${period.name}` : ""}
      </h2>

      <div className="detail-header">
        <div className="field">
          <label>Status</label>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <StatusPill domain="op-period" statusKey={period.status} />
            {period.status !== "Active" && (
              <button style={{ width: "auto" }} onClick={() => setActive.mutate(id)}>
                Set Active
              </button>
            )}
          </div>
        </div>
        <div className="field">
          <label htmlFor="op-name-field">Name</label>
          <input id="op-name-field" defaultValue={period.name} onBlur={(e) => save({ name: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="op-start-field">Start Time</label>
          <input
            id="op-start-field"
            type="datetime-local"
            defaultValue={period.start_time?.slice(0, 16)}
            onBlur={(e) => save({ start_time: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="op-end-field">End Time</label>
          <input
            id="op-end-field"
            type="datetime-local"
            defaultValue={period.end_time?.slice(0, 16)}
            onBlur={(e) => save({ end_time: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="op-briefing-field">Briefing Time</label>
          <input
            id="op-briefing-field"
            type="datetime-local"
            defaultValue={period.briefing_time?.slice(0, 16)}
            onBlur={(e) => save({ briefing_time: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="op-debrief-field">Debrief Time</label>
          <input
            id="op-debrief-field"
            type="datetime-local"
            defaultValue={period.debrief_time?.slice(0, 16)}
            onBlur={(e) => save({ debrief_time: e.target.value })}
          />
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="op-objectives-field">Objectives</label>
          <textarea
            id="op-objectives-field"
            defaultValue={period.objectives}
            onBlur={(e) => save({ objectives: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="op-weather-field">Weather Summary</label>
          <textarea
            id="op-weather-field"
            defaultValue={period.weather_summary}
            onBlur={(e) => save({ weather_summary: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor="op-safety-field">Safety Message</label>
          <textarea
            id="op-safety-field"
            defaultValue={period.safety_message}
            onBlur={(e) => save({ safety_message: e.target.value })}
          />
        </div>
      </div>
    </div>
  );
}
