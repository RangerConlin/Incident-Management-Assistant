import { useEffect, useState } from "react";
import { useSession } from "../../auth/SessionContext";
import StatusPill from "../../components/table/StatusPill";
import { useHazards, useIcs208, useSaveIcs208 } from "./hooks";

// Matches routers/safety.py's ICS208Body exactly — a single upserted doc per
// op_period, no server-side "briefing block" generation (that's desktop-only
// assistive UI over this same hazard data). The hazard list on the left is a
// read-only reference with an "Insert" shortcut, not a separate data model.
type FormState = {
  op_period_from: string;
  op_period_to: string;
  safety_message: string;
  site_safety_plan_required: boolean;
  site_safety_plan_location: string;
  weather_summary: string;
  prepared_by_name: string;
  prepared_by_position: string;
  prepared_by_datetime: string;
};

const EMPTY_FORM: FormState = {
  op_period_from: "",
  op_period_to: "",
  safety_message: "",
  site_safety_plan_required: false,
  site_safety_plan_location: "",
  weather_summary: "",
  prepared_by_name: "",
  prepared_by_position: "",
  prepared_by_datetime: "",
};

export default function SafetyMessagePage() {
  const { incidentId, personnel } = useSession();
  const [op, setOp] = useState(1);
  const { data: doc, isLoading } = useIcs208(incidentId!, op);
  const { data: hazards = [] } = useHazards(incidentId!, op);
  const save = useSaveIcs208(incidentId!);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!doc) return;
    setForm({
      op_period_from: doc.op_period_from ?? "",
      op_period_to: doc.op_period_to ?? "",
      safety_message: doc.safety_message ?? "",
      site_safety_plan_required: Boolean(doc.site_safety_plan_required),
      site_safety_plan_location: doc.site_safety_plan_location ?? "",
      weather_summary: doc.weather_summary ?? "",
      prepared_by_name: doc.prepared_by_name ?? personnel?.name ?? "",
      prepared_by_position: doc.prepared_by_position ?? personnel?.primary_role ?? "",
      prepared_by_datetime: doc.prepared_by_datetime ?? "",
    });
    setSaved(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc, op]);

  if (!incidentId) return null;

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const insertHazardSummary = (hazardTitle: string, band: string | undefined) => {
    const line = `${hazardTitle}${band ? ` — ${band} risk` : ""}`;
    set("safety_message", form.safety_message ? `${form.safety_message}\n${line}` : line);
  };

  const onSave = () => {
    save.mutate(
      { op_period: op, ...form },
      { onSuccess: () => setSaved(true) }
    );
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
        <h2 style={{ margin: 0 }}>Safety Message — ICS 208</h2>
        <label className="field" style={{ margin: 0, flexDirection: "row", alignItems: "center", gap: 6 }}>
          Op. Period
          <input type="number" min={1} step={1} value={op} onChange={(e) => setOp(Math.max(1, Number(e.target.value) || 1))} style={{ width: 70 }} />
        </label>
      </div>

      {isLoading ? (
        <p>Loading…</p>
      ) : (
        <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 320px", minWidth: 280 }}>
            <h3>Current Hazards (OP {op})</h3>
            {hazards.length === 0 ? (
              <p className="muted">No hazards recorded for this operational period.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {hazards.map((h) => (
                  <div key={h.id} className="entry-card">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                      <strong>{h.title}</strong>
                      {h.default_spe && <StatusPill domain="spe-band" statusKey={h.default_spe.band} label={h.default_spe.band} />}
                    </div>
                    {h.description && <p style={{ margin: "4px 0" }}>{h.description}</p>}
                    <button type="button" className="secondary" style={{ width: "auto" }} onClick={() => insertHazardSummary(h.title, h.default_spe?.band)}>
                      Insert into message
                    </button>
                  </div>
                ))}
              </div>
            )}

            <h3 style={{ marginTop: 20 }}>Operational Period</h3>
            <div className="detail-header">
              <div className="field"><label>From</label><input value={form.op_period_from} onChange={(e) => set("op_period_from", e.target.value)} placeholder="e.g. 2026-06-23T06:00" /></div>
              <div className="field"><label>To</label><input value={form.op_period_to} onChange={(e) => set("op_period_to", e.target.value)} placeholder="e.g. 2026-06-23T18:00" /></div>
              <div className="field"><label>Prepared By</label><input value={form.prepared_by_name} onChange={(e) => set("prepared_by_name", e.target.value)} /></div>
              <div className="field"><label>Position</label><input value={form.prepared_by_position} onChange={(e) => set("prepared_by_position", e.target.value)} /></div>
              <div className="field"><label>Prepared At</label><input value={form.prepared_by_datetime} onChange={(e) => set("prepared_by_datetime", e.target.value)} placeholder="e.g. 2026-06-23T07:10" /></div>
            </div>
          </div>

          <div style={{ flex: "2 1 420px", minWidth: 320 }}>
            <h3>Weather &amp; Site Safety</h3>
            <div className="field">
              <label>Weather Summary</label>
              <textarea rows={2} value={form.weather_summary} onChange={(e) => set("weather_summary", e.target.value)} />
            </div>
            <div className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                id="site-plan-required"
                checked={form.site_safety_plan_required}
                onChange={(e) => set("site_safety_plan_required", e.target.checked)}
              />
              <label htmlFor="site-plan-required" style={{ margin: 0 }}>Site safety plan required</label>
            </div>
            <div className="field">
              <label>Site Safety Plan Location</label>
              <input value={form.site_safety_plan_location} onChange={(e) => set("site_safety_plan_location", e.target.value)} />
            </div>

            <h3>Final Authored Safety Message</h3>
            <div className="field">
              <textarea
                rows={10}
                value={form.safety_message}
                onChange={(e) => set("safety_message", e.target.value)}
                placeholder="Authored safety message — not yet written"
              />
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <button type="button" style={{ width: "auto" }} disabled={save.isPending} onClick={onSave}>
                {save.isPending ? "Saving…" : "Save"}
              </button>
              {saved && <span className="muted">Saved.</span>}
              {save.isError && <span className="error">Save failed.</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
