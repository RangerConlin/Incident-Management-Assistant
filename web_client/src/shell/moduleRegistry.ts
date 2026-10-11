// Single source of truth for the sidebar nav. Grouped by the ICS-section
// taxonomy in Design Documents/designplan.md's Module Overview / product_structure.md's
// Module Inventory. Every future module's first pass starts by flipping its
// entry here from "planned" to "live" and pointing `path` at its route — no
// other shell code changes.

export interface ModuleEntry {
  key: string;
  label: string;
  path: string;
  status: "live" | "planned";
}

export interface ModuleSection {
  section: string;
  /** Short glyph for the icon rail (AppShell) — 2-3 chars, no icon font in this app yet. */
  icon: string;
  modules: ModuleEntry[];
}

export const MODULE_REGISTRY: ModuleSection[] = [
  {
    section: "Command",
    icon: "CM",
    modules: [{ key: "command-dashboard", label: "Command Dashboard", path: "/command", status: "planned" }],
  },
  {
    section: "Planning",
    icon: "PL",
    modules: [
      { key: "planning-dashboard", label: "Planning Dashboard", path: "/planning", status: "planned" },
      { key: "strategic-objectives", label: "Strategic Objectives", path: "/planning/objectives", status: "planned" },
    ],
  },
  {
    section: "Operations",
    icon: "OP",
    modules: [
      { key: "team-status-board", label: "Team Status Board", path: "/ops/teams", status: "live" },
      { key: "task-status-board", label: "Task Status Board", path: "/ops/tasks", status: "live" },
      { key: "taskings", label: "Taskings", path: "/ops/taskings", status: "planned" },
    ],
  },
  {
    section: "Logistics",
    icon: "LG",
    modules: [
      { key: "logistics-dashboard", label: "Logistics", path: "/logistics", status: "planned" },
      { key: "resource-requests", label: "Resource Requests", path: "/logistics/resource-requests", status: "planned" },
      { key: "checkin", label: "Check-In", path: "/logistics/checkin", status: "planned" },
    ],
  },
  {
    section: "Communications",
    icon: "CO",
    modules: [{ key: "communications", label: "Communications", path: "/comms", status: "planned" }],
  },
  {
    section: "Medical & Safety",
    icon: "MS",
    modules: [
      { key: "medical", label: "Medical", path: "/medical", status: "planned" },
      { key: "safety", label: "Safety / CAP ORM", path: "/safety", status: "planned" },
      { key: "weather", label: "Weather", path: "/weather", status: "planned" },
    ],
  },
  {
    section: "Intel",
    icon: "IN",
    modules: [{ key: "intel", label: "Intel", path: "/intel", status: "planned" }],
  },
  {
    section: "Liaison",
    icon: "LI",
    modules: [{ key: "liaison", label: "Liaison", path: "/liaison", status: "planned" }],
  },
  {
    section: "Personnel & Role Management",
    icon: "PR",
    modules: [
      { key: "personnel", label: "Personnel", path: "/personnel", status: "planned" },
      { key: "certifications", label: "Certifications", path: "/personnel/certifications", status: "planned" },
    ],
  },
  {
    section: "Reference Library",
    icon: "RL",
    modules: [{ key: "reference-library", label: "Reference Library", path: "/reference-library", status: "planned" }],
  },
  {
    section: "ICS Forms & Documentation",
    icon: "FM",
    modules: [{ key: "forms", label: "Forms", path: "/forms", status: "planned" }],
  },
  {
    section: "Finance/Admin",
    icon: "FA",
    modules: [{ key: "finance", label: "Finance/Admin", path: "/finance", status: "planned" }],
  },
  {
    section: "Public Information",
    icon: "PI",
    modules: [{ key: "pio", label: "Public Information", path: "/pio", status: "planned" }],
  },
  {
    section: "GIS",
    icon: "GS",
    modules: [{ key: "gis", label: "GIS", path: "/gis", status: "planned" }],
  },
  {
    section: "Toolkits",
    icon: "TK",
    modules: [
      { key: "sar-toolkit", label: "SAR Toolkit", path: "/toolkits/sar", status: "planned" },
      { key: "disaster-toolkit", label: "Disaster Response Toolkit", path: "/toolkits/disaster", status: "planned" },
      { key: "planned-event-toolkit", label: "Planned Event Toolkit", path: "/toolkits/planned-event", status: "planned" },
      { key: "initial-response-toolkit", label: "Initial Response Toolkit", path: "/toolkits/initial-response", status: "planned" },
    ],
  },
  {
    section: "Admin",
    icon: "AD",
    modules: [
      { key: "admin-catalogs", label: "Admin Catalogs", path: "/admin/catalogs", status: "planned" },
      { key: "ui-customization", label: "UI Customization", path: "/admin/ui-customization", status: "planned" },
    ],
  },
];

/** The section (if any) whose modules include this pathname — drives both
 * the icon rail's active state and the module sub-tab row. */
export function findSectionForPath(pathname: string): ModuleSection | undefined {
  return MODULE_REGISTRY.find((section) => section.modules.some((m) => pathname.startsWith(m.path)));
}

export function findLiveModule(pathname: string): ModuleEntry | undefined {
  for (const section of MODULE_REGISTRY) {
    const match = section.modules.find((m) => pathname.startsWith(m.path));
    if (match) return match;
  }
  return undefined;
}
