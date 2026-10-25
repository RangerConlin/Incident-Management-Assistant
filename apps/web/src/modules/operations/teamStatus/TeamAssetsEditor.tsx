import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as api from "../../../api/endpoints";

type AssetKind = "vehicle" | "equipment" | "aircraft";

interface AssetOption {
  id: string;
  label: string;
}

const SEARCH_BY_KIND: Record<AssetKind, (q: string) => Promise<AssetOption[]>> = {
  vehicle: async (q) =>
    (await api.searchMasterVehicles(q)).map((v) => ({
      id: v.vehicle_id,
      label: `${v.vehicle_id} — ${[v.make, v.model].filter(Boolean).join(" ") || "Vehicle"}${v.license_plate ? ` (${v.license_plate})` : ""}`,
    })),
  equipment: async (q) =>
    (await api.searchMasterEquipment(q)).map((e) => ({
      id: e.equipment_id,
      label: `${e.equipment_id} — ${e.name || e.type || "Equipment"}`,
    })),
  aircraft: async (q) =>
    (await api.searchMasterAircraft(q)).map((a) => ({
      id: a.tail_number || a.aircraft_id,
      label: `${a.tail_number || a.aircraft_id} — ${a.callsign || [a.make, a.model].filter(Boolean).join(" ") || "Aircraft"}`,
    })),
};

function parseList(json: string): string[] {
  try {
    const parsed = JSON.parse(json || "[]");
    return Array.isArray(parsed) ? parsed.map((v) => String(v)) : [];
  } catch {
    return [];
  }
}

interface Props {
  kind: AssetKind;
  jsonValue: string;
  onSave: (nextJsonValue: string) => void;
}

const LABELS: Record<AssetKind, string> = { vehicle: "vehicles", equipment: "equipment", aircraft: "aircraft" };

// Team vehicles/equipment/aircraft are stored as a JSON array of plain
// identifier strings (the shared API's documented contract — see
// operations.py's _parse_json_list_field), but the GUI must never ask the
// user to type that identifier freehand: it searches the same master
// catalog desktop's Add Vehicle/Add Equipment dialogs search, same as the
// Personnel tab does for member_person_records.
export default function TeamAssetsEditor({ kind, jsonValue, onSave }: Props) {
  const items = parseList(jsonValue);
  const [query, setQuery] = useState("");
  const search = useQuery({
    queryKey: ["master", kind, "search", query],
    queryFn: () => SEARCH_BY_KIND[kind](query),
    enabled: query.trim().length > 0,
  });

  const commit = (next: string[]) => onSave(JSON.stringify(next));
  const add = (id: string) => {
    if (!items.includes(id)) commit([...items, id]);
    setQuery("");
  };
  const remove = (id: string) => commit(items.filter((i) => i !== id));

  const results = (search.data ?? []).filter((r) => !items.includes(r.id));

  return (
    <div>
      <div className="field" style={{ flexDirection: "row", gap: 8 }}>
        <input
          placeholder={`Search ${LABELS[kind]}…`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {query.trim() && (
        <div>
          {search.isPending && <p style={{ opacity: 0.6 }}>Searching…</p>}
          {!search.isPending && results.length === 0 && <p style={{ opacity: 0.6 }}>No matching {LABELS[kind]}.</p>}
          {results.map((r) => (
            <div key={r.id} className="list-item">
              <span>{r.label}</span>
              <button style={{ width: "auto" }} onClick={() => add(r.id)}>
                Add
              </button>
            </div>
          ))}
        </div>
      )}
      {items.length === 0 && <p style={{ opacity: 0.6 }}>None assigned.</p>}
      {items.map((id) => (
        <div key={id} className="list-item" style={{ cursor: "default" }}>
          <span>{id}</span>
          <button className="danger" style={{ width: "auto" }} onClick={() => remove(id)}>
            Remove
          </button>
        </div>
      ))}
    </div>
  );
}
