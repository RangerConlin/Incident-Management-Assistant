// Single source of truth for the sidebar nav. Grouped by the ICS-section
// taxonomy in docs/archive/design-documents/designplan.md's Module Overview / product_structure.md's
// Module Inventory. Every future module's first pass starts by flipping its
// entry here from "planned" to "live" and pointing `path` at its route — no
// other shell code changes.

import type { LucideIcon } from "lucide-react";
import {
  Shield,
  ClipboardList,
  Activity,
  Target,
  Truck,
  Radio,
  HeartPulse,
  Search,
  Handshake,
  BookOpen,
  FileText,
  CircleDollarSign,
  Megaphone,
  Map,
  Wrench,
  Settings as SettingsIcon,
} from "lucide-react";

export interface ModuleEntry {
  key: string;
  label: string;
  path: string;
  status: "live" | "planned";
}

export interface ModuleSection {
  section: string;
  /** Sidebar icon for this section group. */
  icon: LucideIcon;
  modules: ModuleEntry[];
}

export const MODULE_REGISTRY: ModuleSection[] = [
  {
    section: "Command",
    icon: Shield,
    modules: [
      { key: "command-dashboard", label: "Command Dashboard", path: "/command", status: "live" },
      { key: "incident-overview", label: "Incident Overview", path: "/command/overview", status: "live" },
      { key: "incident-organization", label: "Incident Organization", path: "/command/organization", status: "live" },
      // Filed under Command, not Planning, to match desktop's actual module
      // placement (modules/command/panels/incident_objectives_panel.py) —
      // web had this miscategorized under Planning.
      { key: "strategic-objectives", label: "Incident Objectives", path: "/command/objectives", status: "live" },
      { key: "situation-reports", label: "Situation Reports", path: "/command/sitreps", status: "live" },
      { key: "iap-builder", label: "IAP Builder", path: "/command/iap", status: "live" },
    ],
  },
  {
    section: "Planning",
    icon: ClipboardList,
    modules: [
      { key: "planning-dashboard", label: "Planning Dashboard", path: "/planning", status: "live" },
      { key: "operational-periods", label: "Operational Periods", path: "/planning/operational-periods", status: "live" },
      { key: "meetings", label: "Meetings", path: "/planning/meetings", status: "live" },
      { key: "approvals", label: "Approvals", path: "/planning/approvals", status: "live" },
      { key: "demobilization", label: "Demobilization", path: "/planning/demobilization", status: "live" },
    ],
  },
  {
    section: "Operations",
    icon: Activity,
    modules: [
      { key: "team-status-board", label: "Team Status Board", path: "/ops/teams", status: "live" },
      { key: "task-status-board", label: "Task Status Board", path: "/ops/tasks", status: "live" },
    ],
  },
  {
    // Promoted out of Planning to its own root-level section, between
    // Operations and Logistics — it spans both (tactical assignment
    // planning plus the resourcing/gap side) rather than belonging under
    // either one. "Work Assignments" renamed to "Assignment Board" to
    // match.
    section: "Tactics & Resource Planning",
    icon: Target,
    modules: [{ key: "assignment-board", label: "Assignment Board", path: "/tactics/assignments", status: "live" }],
  },
  {
    section: "Logistics",
    icon: Truck,
    modules: [
      { key: "logistics-dashboard", label: "Logistics", path: "/logistics", status: "live" },
      { key: "resource-status-board", label: "Resource Status Board", path: "/logistics/resources", status: "live" },
      { key: "resource-requests", label: "Resource Requests", path: "/logistics/resource-requests", status: "live" },
      { key: "checkin", label: "Check-In", path: "/logistics/checkin", status: "live" },
      { key: "personnel-manager", label: "Personnel Manager", path: "/logistics/personnel", status: "live" },
      { key: "facilities", label: "Facilities", path: "/logistics/facilities", status: "live" },
    ],
  },
  {
    section: "Communications",
    icon: Radio,
    modules: [
      { key: "comms-plan", label: "Communications Plan", path: "/comms/plan", status: "live" },
      { key: "comms-log", label: "Traffic Log", path: "/comms/log", status: "live" },
    ],
  },
  {
    // Order matches desktop's actual combined "Medical & Safety" menu
    // (main.py): Medical Plan ICS 206, Safety Message 208, Incident Safety
    // Analysis 215A / Incident Hazard Register, Safety Incident Reports
    // (IWI), Weather — with the two dashboard landing pages (no desktop
    // equivalent) leading their own group, and CAP ORM Worksheet (no
    // desktop menu slot either) placed next to Hazard Dashboard since it's
    // hazard-related.
    section: "Medical & Safety",
    icon: HeartPulse,
    modules: [
      { key: "medical-dashboard", label: "Medical Dashboard", path: "/medical", status: "live" },
      { key: "ics206-builder", label: "ICS 206 Builder", path: "/medical/206", status: "live" },
      { key: "medical-reports", label: "Medical Reports", path: "/medical/reports", status: "live" },
      { key: "safety-dashboard", label: "Safety Dashboard", path: "/safety", status: "live" },
      { key: "safety-message", label: "Safety Message", path: "/safety/208", status: "live" },
      { key: "hazard-dashboard", label: "Hazard Dashboard", path: "/safety/hazards", status: "live" },
      { key: "cap-orm-worksheet", label: "CAP ORM Worksheet", path: "/safety/orm", status: "live" },
      { key: "iwi-dashboard", label: "IWI Dashboard", path: "/safety/iwi", status: "live" },
      { key: "safety-reports", label: "Safety Reports", path: "/safety/reports", status: "live" },
      { key: "weather", label: "Weather", path: "/weather", status: "live" },
    ],
  },
  {
    section: "Intel",
    icon: Search,
    modules: [{ key: "intel", label: "Intel", path: "/intel", status: "live" }],
  },
  {
    section: "Liaison",
    icon: Handshake,
    modules: [
      { key: "liaison-overview", label: "Liaison Overview", path: "/liaison", status: "live" },
      { key: "liaison-agencies", label: "Agency Directory", path: "/liaison/agencies", status: "live" },
      { key: "liaison-requests", label: "Requests / Offers", path: "/liaison/requests", status: "live" },
      { key: "liaison-reporting", label: "Reporting Board", path: "/liaison/reporting", status: "live" },
      { key: "liaison-interactions", label: "Interaction Log", path: "/liaison/interactions", status: "live" },
    ],
  },
  {
    section: "Reference Library",
    icon: BookOpen,
    modules: [{ key: "reference-library", label: "Reference Library", path: "/reference-library", status: "live" }],
  },
  {
    section: "ICS Forms & Documentation",
    icon: FileText,
    modules: [{ key: "forms", label: "Forms", path: "/forms", status: "live" }],
  },
  {
    section: "Finance/Admin",
    icon: CircleDollarSign,
    modules: [{ key: "finance", label: "Finance/Admin", path: "/finance", status: "live" }],
  },
  {
    section: "Public Information",
    icon: Megaphone,
    modules: [
      { key: "pio-overview", label: "PIO Dashboard", path: "/pio", status: "live" },
      { key: "pio-releases", label: "Messages / Releases", path: "/pio/releases", status: "live" },
      { key: "pio-misinformation", label: "Misinformation / Rumors", path: "/pio/misinformation", status: "live" },
      { key: "pio-media", label: "Media Log", path: "/pio/media", status: "live" },
      { key: "pio-talking-points", label: "Talking Points", path: "/pio/talking-points", status: "live" },
      { key: "pio-templates", label: "Letterhead / Templates", path: "/pio/templates", status: "live" },
      { key: "pio-distribution", label: "Distribution Log", path: "/pio/distribution", status: "live" },
    ],
  },
  {
    // Not a page inside this shell — the single link below opens
    // IncidentMapPage, a standalone route (see App.tsx) that isn't nested
    // under AppShell, so navigating here leaves the sidebar/topbar chrome
    // entirely, the closest web equivalent to desktop's Incident Map
    // opening as its own top-level window.
    section: "Incident Map",
    icon: Map,
    modules: [{ key: "incident-map", label: "Incident Map", path: "/incident-map", status: "live" }],
  },
  {
    section: "Toolkits",
    icon: Wrench,
    modules: [
      { key: "sar-toolkit", label: "SAR Toolkit", path: "/toolkits/sar", status: "live" },
      { key: "disaster-toolkit", label: "Disaster Response Toolkit", path: "/toolkits/disaster", status: "live" },
      { key: "planned-event-toolkit", label: "Planned Event Toolkit", path: "/toolkits/planned-event", status: "live" },
      { key: "initial-response-toolkit", label: "Initial Response Toolkit", path: "/toolkits/initial-response", status: "live" },
    ],
  },
  {
    section: "Admin",
    icon: SettingsIcon,
    modules: [
      { key: "admin-catalogs", label: "Admin Catalogs", path: "/admin/catalogs", status: "live" },
      { key: "ui-customization", label: "UI Customization", path: "/admin/ui-customization", status: "live" },
    ],
  },
];

/** The section (if any) whose modules include this pathname — drives the
 * sidebar's expanded-group and active-link state. */
export function findSectionForPath(pathname: string): ModuleSection | undefined {
  return MODULE_REGISTRY.find((section) => section.modules.some((m) => pathname.startsWith(m.path)));
}

export function findLiveModule(pathname: string): ModuleEntry | undefined {
  return MODULE_REGISTRY.flatMap(section => section.modules)
    .filter(module => module.status === "live" && (pathname === module.path || pathname.startsWith(`${module.path}/`)))
    .sort((a, b) => b.path.length - a.path.length)[0];
}
