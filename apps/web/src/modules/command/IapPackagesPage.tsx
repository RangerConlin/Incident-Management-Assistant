import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../../auth/SessionContext";
import type { IapPackage } from "../../api/types";
import DataTable, { type ColumnDef } from "../../components/table/DataTable";
import { formatDateTime } from "../../utils/formatDateTime";
import { useIapPackages } from "./hooks";
import "./command.css";
export default function IapPackagesPage(){const{incidentId}=useSession();const q=useIapPackages(incidentId!);const nav=useNavigate();const rows=q.data??[];const next=Math.max(0,...rows.map(x=>x.op_number))+1;const columns:ColumnDef<IapPackage>[]=[{key:"op",header:"Operational period",render:p=><Link to={`/command/iap/${p.op_number}`}>Period {p.op_number}</Link>,sortValue:p=>p.op_number},{key:"status",header:"Status"},{key:"start",header:"Starts",render:p=>formatDateTime(p.op_start)},{key:"end",header:"Ends",render:p=>formatDateTime(p.op_end)},{key:"forms",header:"Forms",render:p=>p.forms.length},{key:"version",header:"Version",render:p=>p.version_tag??"—"}];return <div className="command-page"><div className="command-heading"><div><h2>Incident Action Plans</h2><p>Assemble and track the form package for each operational period.</p></div><Link to={`/command/iap/${next}`}>New IAP package</Link></div>{q.isPending?<p>Loading IAP packages…</p>:q.isError?<p className="error">Could not load IAP packages.</p>:<DataTable tableId="command-iap" columns={columns} rows={rows} rowKey={p=>p.op_number} onRowActivate={p=>nav(`/command/iap/${p.op_number}`)} emptyMessage="No IAP packages have been created."/>}</div>}
