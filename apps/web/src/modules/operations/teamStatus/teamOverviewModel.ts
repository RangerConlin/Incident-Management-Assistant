import type { OrgPosition } from "../../../api/types";

export const ASSIGNABLE_UNIT_CLASSIFICATIONS = new Set(["section", "branch", "division", "group", "unit"]);

// Canonical operational team codes and labels mirror desktop
// utils.constants.TEAM_TYPE_DETAILS. The master team-type catalog describes
// resource taxonomies (for example "gtm"/"fixedwing") and is not the shape
// persisted on an operations team ("GT"/"AIR").
export const TEAM_TYPE_OPTIONS = [
  { value: "GT", label: "Ground Team" },
  { value: "UDF", label: "Urban DF Team" },
  { value: "LSAR", label: "Land SAR" },
  { value: "DF", label: "Direction Finding Team" },
  { value: "GT/UAS", label: "Ground/UAS Team" },
  { value: "UDF/UAS", label: "UDF/UAS Team" },
  { value: "UAS", label: "UAS Team" },
  { value: "AIR", label: "Aircraft" },
  { value: "K9", label: "K9 Team" },
  { value: "UTIL", label: "Utility/Support" },
] as const;

const STATUS_KEYS: Record<string, string> = {
  "en route": "enroute",
  "on scene": "arrival",
  "returning to base": "returning",
  returning: "returning",
  rest: "crew rest",
  "post incident management": "post incident",
};

export function statusKeyForValue(status: string): string {
  const normalized = status.trim().toLowerCase();
  return STATUS_KEYS[normalized] ?? normalized;
}

export function assignableUnitOptions(positions: OrgPosition[]): { value: number; label: string }[] {
  const children = new Map<number | null, OrgPosition[]>();
  for (const position of positions) {
    const key = position.parent_position_id ?? null;
    children.set(key, [...(children.get(key) ?? []), position]);
  }
  for (const siblings of children.values()) {
    siblings.sort((a, b) => (a.sort_order - b.sort_order) || a.title.localeCompare(b.title));
  }

  const options: { value: number; label: string }[] = [];
  const visit = (parentId: number | null, depth: number) => {
    for (const position of children.get(parentId) ?? []) {
      if (ASSIGNABLE_UNIT_CLASSIFICATIONS.has(position.classification)) {
        options.push({
          value: position.position_id,
          label: `${"\u00a0".repeat(depth * 4)}${position.title} (${position.classification})`,
        });
      }
      visit(position.position_id, depth + 1);
    }
  };
  visit(null, 0);
  return options;
}
