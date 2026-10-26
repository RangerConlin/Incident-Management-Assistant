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
  Truck,
  Radio,
  HeartPulse,
  Search,
  Handshake,
  Users,
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
      { key: "work-assignments", label: "Work Assignments", path: "/planning/work-assignments", status: "live" },
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
    section: "Logistics",
    icon: Truck,
    modules: [
      { key: "logistics-dashboard", label: "Logistics", path: "/logistics", status: "live" },
      { key: "resource-status-board", label: "Resource Status Board", path: "/logistics/resources", status: "live" },
      { key: "resource-requests", label: "Resource Requests", path: "/logistics/resource-requests", status: "live" },
      { key: "checkin", label: "Check-In", path: "/logistics/checkin", status: "live" },
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
    section: "Medical & Safety",
    icon: HeartPulse,
    modules: [
      { key: "medical", label: "Medical", path: "/medical", status: "live" },
      { key: "safety", label: "Safety / CAP ORM", path: "/safety", status: "live" },
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
    modules: [{ key: "liaison", label: "Liaison", path: "/liaison", status: "live" }],
  },
  {
    section: "Personnel & Role Management",
    icon: Users,
    modules: [
      { key: "personnel", label: "Personnel", path: "/personnel", status: "live" },
      { key: "certifications", label: "Certifications", path: "/personnel/certifications", status: "live" },
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
    modules: [{ key: "pio", label: "Public Information", path: "/pio", status: "live" }],
  },
  {
    section: "GIS",
    icon: Map,
    modules: [{ key: "gis", label: "GIS", path: "/gis", status: "live" }],
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
