// Minimal WKT reader for the shapes gis.py's SpatialFeaturesRepository
// actually stores today (POINT/LINESTRING/POLYGON — see
// modules/gis/map_window/tools/draw_tools.py on the desktop side, which
// writes the same three). WKT coordinates are "lon lat"; every return here
// is "lat lon" pairs, Leaflet's order. Anything else (MULTI*, empty, or
// malformed text) returns null — the caller skips that feature rather than
// guessing at a shape.

export type ParsedGeometry =
  | { type: "Point"; latlngs: [number, number] }
  | { type: "LineString"; latlngs: [number, number][] }
  | { type: "Polygon"; latlngs: [number, number][] };

function parseCoordPairs(text: string): [number, number][] {
  return text
    .split(",")
    .map((pair) =>
      pair
        .trim()
        .split(/\s+/)
        .map(Number)
    )
    .filter((pair) => pair.length >= 2 && pair.every((n) => Number.isFinite(n)))
    .map(([lon, lat]) => [lat, lon] as [number, number]);
}

export function parseWkt(wkt: string | null | undefined): ParsedGeometry | null {
  const trimmed = (wkt ?? "").trim();
  const match = trimmed.match(/^(\w+)\s*\(([\s\S]*)\)\s*$/);
  if (!match) return null;
  const type = match[1].toUpperCase();
  const body = match[2].trim();

  if (type === "POINT") {
    const points = parseCoordPairs(body);
    return points[0] ? { type: "Point", latlngs: points[0] } : null;
  }
  if (type === "LINESTRING") {
    const points = parseCoordPairs(body);
    return points.length >= 2 ? { type: "LineString", latlngs: points } : null;
  }
  if (type === "POLYGON") {
    // Outer ring only — "(ring1),(ring2),..."; holes aren't rendered.
    const outerRing = body.replace(/^\(/, "").split(")")[0];
    const points = parseCoordPairs(outerRing);
    return points.length >= 3 ? { type: "Polygon", latlngs: points } : null;
  }
  return null;
}
