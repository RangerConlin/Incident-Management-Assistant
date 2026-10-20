import { useEffect, useState } from "react";
import type { RequestItem } from "../../api/types";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { ITEM_KINDS, label, validateItems } from "./model";
export default function RequestItems({ items, disabled, save, onDirtyChange }: { onDirtyChange: (dirty: boolean) => void; items: RequestItem[]; disabled: boolean; save: (items: RequestItem[]) => Promise<unknown> }) {
  const [draft, setDraft] = useState<RequestItem[] | null>(null); const [error,setError] = useState(""); const [notice,setNotice] = useState("");
  useEffect(() => { onDirtyChange(draft !== null); }, [draft,onDirtyChange]);
  const rows = draft ?? items; const update = (id: string, key: string, value: unknown) => setDraft(old => (old ?? items).map(item => item.id === id ? { ...item, [key]: value } : item));
  const columns: ColumnDef<RequestItem>[] = [
    { key: "kind", header: "Kind", defaultWidth: 160, render: r => draft ? <select aria-label="Item kind" value={r.kind} disabled={disabled} onChange={e => update(r.id,"kind",e.target.value)}>{ITEM_KINDS.map(k => <option key={k} value={k}>{label(k)}</option>)}</select> : label(r.kind) },
    ...([ ["description", "Description"], ["quantity", "Quantity"], ["unit", "Unit"], ["special_instructions", "Instructions"] ] as const).map(([key,header]) => ({ key,header,defaultWidth: key === "description" ? 260 : 170, render: (r: RequestItem) => draft ? <input aria-label={header} type={key === "quantity" ? "number" : "text"} min={key === "quantity" ? 0.001 : undefined} step={key === "quantity" ? "any" : undefined} disabled={disabled} value={String(r[key] ?? "")} onChange={e => update(r.id,key,key === "quantity" ? Number(e.target.value) : e.target.value)} /> : String(r[key] ?? "—") })),
    { key: "remove",header: "",render: r => draft && <button className="secondary" disabled={disabled} onClick={() => setDraft(old => (old ?? []).filter(i => i.id !== r.id))}>Remove</button> },
  ];
  return <section className="logistics-panel"><h3>Requested items</h3>{error && <p className="error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <DataTable tableId="logistics-request-items" columns={columns} rows={rows} rowKey={r => r.id} emptyMessage="No line items. The request header can describe a simple need." />
    <div className="logistics-toolbar">{draft ? <><button disabled={disabled} onClick={() => setDraft(old => [...(old ?? []), { id: crypto.randomUUID(), kind: "SUPPLY", description: "", quantity: 1, unit: "unit", special_instructions: "" }])}>Add item</button>
      <button disabled={disabled} onClick={async () => { setError(""); setNotice(""); try { validateItems(draft); await save(draft); setDraft(null); setNotice("Items saved."); } catch(e) { setError(e instanceof Error ? e.message : "Could not save items."); } }}>Save items</button><button className="secondary" disabled={disabled} onClick={() => { setDraft(null); setError(""); }}>Discard item edits</button></> : <button disabled={disabled} onClick={() => { setDraft(items.map(i => ({ ...i }))); setNotice(""); }}>Edit items</button>}</div>
    {draft && <p>Unsaved item edits. Save these before changing the request lifecycle.</p>}
  </section>;
}
